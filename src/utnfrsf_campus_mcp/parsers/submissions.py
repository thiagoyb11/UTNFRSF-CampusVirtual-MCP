"""Formularios Moodle, límites y archivos locales; no realiza peticiones ni escrituras remotas."""

import hashlib
import json
import mimetypes
import re
import stat
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import SubmissionError
from utnfrsf_campus_mcp.models import LocalSubmissionFile, PreparedSubmission, UploadLimits
from utnfrsf_campus_mcp.parsers.login import same_origin

# Límite local por archivo y clases CSS con las que Moodle marca el estado de la entrega
# y de la calificación (independientes del idioma de la interfaz).
MAX_LOCAL_FILE_BYTES = 200 * 1024 * 1024
SUBMISSION_STATE_CLASS = re.compile(r"\bsubmissionstatus(new|draft|submitted|reopened)\b")
GRADING_STATE_CLASS = re.compile(r"\bsubmission(?:not)?graded\b")


# Atajo para construir errores de entrega.
def fail(code: str, message: str) -> SubmissionError:
    return SubmissionError(code, message)


# Lista blanca de destinos: la URL debe ser del campus y tener una de las rutas permitidas.
def require_url(url: str, paths: tuple[str, ...]) -> str:
    if not same_origin(url, CAMPUS_BASE_URL) or urlsplit(url).path not in paths:
        raise fail(
            "SUBMISSION_ACCESS_DENIED", "El destino no pertenece al flujo permitido del campus."
        )
    return url


def parse_submission_state(classes: str, has_files: bool) -> str:
    """Deduce el estado de las clases de la tabla, sin depender del idioma de la interfaz.

    Sin entrega, Moodle deja la celda de estado sin clase propia. Se exige la fila de
    calificación para no confundir un cambio de formato con una tarea sin entregar.
    """
    codes = SUBMISSION_STATE_CLASS.findall(classes)
    if len(set(codes)) == 1:
        return codes[0]
    if not codes and not has_files and GRADING_STATE_CLASS.search(classes):
        return "new"
    return "unknown"


# Formulario HTML leído de una página: destino, método, campos con sus valores actuales,
# campos de archivo, obligatorios, casillas y botones de envío.
# repr=False evita que tokens como sesskey terminen impresos en logs o errores.
@dataclass(repr=False)
class CampusForm:
    action: str
    method: str
    enctype: str
    fields: dict[str, str] = field(default_factory=dict)
    file_fields: list[str] = field(default_factory=list)
    required: set[str] = field(default_factory=set)
    checkboxes: set[str] = field(default_factory=set)
    submits: dict[str, str] = field(default_factory=dict)


class CampusHTML(HTMLParser):
    """Datos privados de formulario; nunca serializar esta instancia en respuestas MCP."""

    def __init__(self, html: str, url: str):
        # Analiza la página completa al construirse: formularios, enlaces, objetos embebidos,
        # scripts y señales de login o error.
        super().__init__(convert_charrefs=True)
        self.url = url
        self.forms: list[CampusForm] = []
        self.links: list[tuple[str, str]] = []
        self.objects: list[str] = []
        self.scripts: list[str] = []
        self.body_id = ""
        self.error = False
        self.login = False
        self._form = None
        self._link = None
        self._script = None
        self._textarea = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.body_id = attrs.get("id") or ""
            self.login = (
                self.body_id == "page-login-index"
                or "notloggedin" in (attrs.get("class") or "").split()
            )
        if {"errorbox", "alert-danger"}.intersection((attrs.get("class") or "").split()):
            self.error = True
        if tag == "script":
            self._script = []
        if tag == "object" and attrs.get("data"):
            self.objects.append(urljoin(self.url, attrs["data"]))
        if tag == "a" and attrs.get("href"):
            self._link = (urljoin(self.url, attrs["href"]), [])
        if tag == "form":
            self._form = CampusForm(
                urljoin(self.url, attrs.get("action") or self.url),
                (attrs.get("method") or "get").lower(),
                (attrs.get("enctype") or "").lower(),
            )
            self.forms.append(self._form)
        # Controles dentro de un formulario: se clasifican por tipo. Los deshabilitados no se
        # envían, igual que en un navegador; las casillas solo aportan valor si están marcadas.
        if tag not in ("input", "button", "textarea", "select") or self._form is None:
            return
        name = attrs.get("name")
        if not name or "disabled" in attrs:
            return
        kind = (attrs.get("type") or ("submit" if tag == "button" else "text")).lower()
        if "required" in attrs or attrs.get("aria-required") == "true":
            self._form.required.add(name)
        if kind == "file":
            self._form.file_fields.append(name)
        elif kind == "submit":
            self._form.submits[name] = attrs.get("value") or ""
        elif kind in ("checkbox", "radio"):
            self._form.checkboxes.add(name)
            if "checked" in attrs:
                self._form.fields[name] = attrs.get("value") or "1"
        else:
            self._form.fields[name] = attrs.get("value") or ""
            if tag == "textarea":
                self._textarea = (self._form, name)

    # El texto se agrega al elemento abierto: valor de un textarea, código de un script o
    # texto visible de un enlace.
    def handle_data(self, data):
        if self._textarea is not None:
            form, name = self._textarea
            form.fields[name] += data
        if self._script is not None:
            self._script.append(data)
        if self._link is not None:
            self._link[1].append(data)

    def handle_endtag(self, tag):
        if tag == "textarea":
            self._textarea = None
        if tag == "form":
            self._form = None
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], "".join(self._link[1]).strip()))
            self._link = None
        if tag == "script" and self._script is not None:
            self.scripts.append("".join(self._script))
            self._script = None

    # Falla si la respuesta resultó ser la página de login o una página de error.
    def require_access(self):
        if self.login:
            raise fail(
                "SUBMISSION_SESSION_EXPIRED", "El campus solicita iniciar sesión nuevamente."
            )
        if self.error:
            raise fail(
                "SUBMISSION_ACCESS_DENIED",
                "El campus devolvió una página de error o acceso denegado.",
            )


# Busca en los scripts de la página la llamada M.form_filemanager.init(...) del área temporal
# indicada y devuelve su configuración JSON (límites y tipos aceptados). Debe haber una sola.
def filemanager_options(document: CampusHTML, draft_id: str) -> dict:
    configs = []
    for script in document.scripts:
        for match in re.finditer(r"M\.form_filemanager\.init\(\s*[^,]+,\s*", script):
            try:
                config, _ = json.JSONDecoder().raw_decode(script[match.end() :])
            except ValueError:
                continue
            if isinstance(config, dict) and str(config.get("itemid")) == draft_id:
                configs.append(config)
    if len(configs) != 1:
        raise fail(
            "UPLOAD_MANAGER_UNSUPPORTED",
            "No se pudo verificar la configuración del gestor de archivos.",
        )
    return configs[0]


# Convierte esa configuración en límites: cantidad de archivos, tamaño por archivo, tamaño
# total y tipos aceptados (lista vacía = cualquier tipo).
def parse_limits(config: dict) -> UploadLimits:
    try:
        accepted = config["accepted_types"]
        if isinstance(accepted, str):
            accepted = re.split(r"[\s,]+", accepted.strip()) if accepted.strip() else []
        if not isinstance(accepted, list) or not all(isinstance(t, str) for t in accepted):
            raise ValueError
        return UploadLimits(
            max_files=int(config["maxfiles"]),
            max_file_bytes=int(config["maxbytes"]),
            max_area_bytes=int(config["areamaxbytes"]),
            accepted_types=accepted or ["*"],
        )
    except (KeyError, ValueError, TypeError):
        raise fail(
            "UPLOAD_LIMITS_UNSUPPORTED", "No se pudieron confirmar los límites de carga."
        ) from None


def prepare_submission(course_id: int, activity_id: int, files: list[str]) -> PreparedSubmission:
    """Solo I/O local. No autentica, navega ni crea un draft remoto."""
    if (
        type(course_id) is not int
        or course_id <= 0
        or type(activity_id) is not int
        or activity_id <= 0
        or not isinstance(files, list)
        or not 1 <= len(files) <= 100
    ):
        raise fail(
            "UPLOAD_INVALID_FILES", "Indicá curso, actividad y entre 1 y 100 archivos locales."
        )
    # Por cada ruta: debe ser un archivo regular, de hasta 200 MiB, con un nombre apto para
    # multipart y no repetido (sin distinguir mayúsculas). Se calcula su SHA-256 y se
    # confirma que no cambió de tamaño mientras se leía.
    manifests = []
    names = set()
    for path in files:
        if not isinstance(path, str) or not path.strip():
            raise fail("UPLOAD_INVALID_FILES", "Cada archivo debe tener una ruta local.")
        try:
            local = Path(path).expanduser().resolve(strict=True)
            info = local.stat()
            if not stat.S_ISREG(info.st_mode):
                raise fail(
                    "UPLOAD_NOT_REGULAR_FILE",
                    "Solo se admiten archivos regulares; comprimí las carpetas antes de subirlas.",
                )
            if info.st_size > MAX_LOCAL_FILE_BYTES:
                raise fail("UPLOAD_FILE_TOO_LARGE", "Un archivo supera el límite local de 200 MiB.")
            name = local.name
            if any(c in name for c in '\r\n"\\'):
                raise fail(
                    "UPLOAD_INVALID_FILENAME",
                    "Un nombre contiene caracteres no admitidos para multipart.",
                )
            key = unicodedata.normalize("NFC", name).casefold()
            if key in names:
                raise fail(
                    "UPLOAD_DUPLICATE_NAME", "No se pueden subir dos archivos con el mismo nombre."
                )
            names.add(key)
            with local.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            if local.stat().st_size != info.st_size:
                raise fail("UPLOAD_FILE_CHANGED", "Un archivo cambió durante su preparación.")
            manifests.append(
                LocalSubmissionFile(
                    path=str(local), name=name, size_bytes=info.st_size, sha256=digest
                )
            )
        except OSError:
            raise fail(
                "UPLOAD_LOCAL_FILE_ERROR", "No se pudo leer uno de los archivos locales."
            ) from None
    return PreparedSubmission(course_id=course_id, activity_id=activity_id, files=manifests)


def validate_files(
    files: list[LocalSubmissionFile],
    limits: UploadLimits,
    existing: list[str],
    existing_bytes: int = 0,
) -> None:
    # Valida contra los límites de la actividad, sumando lo que ya está en el área temporal:
    # cantidad, tamaño total, nombres repetidos, tamaño por archivo y tipos aceptados.
    if limits.max_files >= 0 and len(files) + len(existing) > limits.max_files:
        raise fail(
            "UPLOAD_TOO_MANY_FILES", f"La actividad admite como máximo {limits.max_files} archivos."
        )
    if (
        limits.max_area_bytes > 0
        and sum(f.size_bytes for f in files) + existing_bytes > limits.max_area_bytes
    ):
        raise fail("UPLOAD_AREA_TOO_LARGE", "Se supera el tamaño total permitido por la actividad.")
    old = {unicodedata.normalize("NFC", name).casefold() for name in existing}
    for file in files:
        if unicodedata.normalize("NFC", file.name).casefold() in old:
            raise fail(
                "UPLOAD_FILE_EXISTS", "Ya existe un archivo con ese nombre; no se reemplazó."
            )
        if limits.max_file_bytes > 0 and file.size_bytes > limits.max_file_bytes:
            raise fail("UPLOAD_FILE_TOO_LARGE", "Un archivo supera el límite de la actividad.")
        # Tipos aceptados: "*" admite todo; ".pdf" compara la extensión; "image/*" o
        # "application/pdf" comparan el MIME deducido del nombre.
        types = limits.accepted_types
        if "*" in types:
            continue
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if any(
            (t.startswith(".") and file.name.lower().endswith(t.lower()))
            or ("/" in t and (mime == t or t.endswith("/*") and mime.startswith(t[:-1])))
            for t in types
        ):
            continue
        if any(not t.startswith(".") and "/" not in t for t in types):
            raise fail(
                "UPLOAD_TYPES_UNSUPPORTED",
                "La actividad usa un grupo de tipos que requiere una normalización adicional.",
            )
        raise fail(
            "UPLOAD_TYPE_NOT_ALLOWED", "La actividad no admite el tipo de uno de los archivos."
        )


# Archivos del área temporal (draftfile.php/.../user/draft/<itemid>/...): nombre → enlace.
def draft_links(document: CampusHTML, itemid: str) -> dict[str, str]:
    result = {}
    for url, name in document.links:
        parts = urlsplit(url)
        if not same_origin(url, CAMPUS_BASE_URL) or not re.search(
            r"/user/draft/" + re.escape(itemid) + r"/", parts.path
        ):
            continue
        if parts.path.startswith("/draftfile.php/"):
            result[name] = url
    return result


# Devuelve el único enlace del campus con esa ruta y ese parámetro action; si hay cero o
# varios, falla en lugar de elegir uno.
def find_link(document: CampusHTML, path: str, action: str) -> str:
    matches = list(
        dict.fromkeys(
            url
            for url, _ in document.links
            if same_origin(url, CAMPUS_BASE_URL)
            and urlsplit(url).path == path
            and parse_qs(urlsplit(url).query).get("action") == [action]
        )
    )
    if len(matches) != 1:
        raise fail(
            "UPLOAD_FORM_UNSUPPORTED", "No se encontró un único enlace del selector de archivos."
        )
    return matches[0]
