"""Normalización pura de enlaces y snapshots del contenido de una asignatura."""

import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit, urlunsplit

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import CourseLink, CourseSection, UnlinkedActivity
from utnfrsf_campus_mcp.parsers.login import same_origin

_FILE_SUFFIXES = {
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".txt",
    ".csv",
    ".ipynb",
    ".py",
    ".sql",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".mp3",
    ".mp4",
}
_SECRET = re.compile(r"sesskey|token|password|secret|authorization|signature|api[_-]?key", re.I)
_MODULE_PATH = re.compile(r"/mod/([a-z][a-z0-9_]*)/view\.php\Z")
# Módulos cuyos archivos de pluginfile.php se listan en la propia página del módulo.
_MODULE_FILE_PATH = re.compile(r"/pluginfile\.php/[0-9]+/mod_(resource|folder|assign|page)/")


# Error genérico cuando la página no tiene la estructura esperada de Moodle.
def invalid_resources() -> CourseError:
    return CourseError(
        "RESOURCES_FORMAT_UNSUPPORTED", "No se pudo verificar la estructura del curso."
    )


# Convierte a entero solo dígitos ASCII (acepta "12" o 12, rechaza True, "-1" o "1e3").
def integer(value: Any, minimum: int = 0) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise invalid_resources()
    result = int(value)
    if result < minimum:
        raise invalid_resources()
    return result


def clean_link(raw: Any, source_url: str) -> str | None:
    """Devuelve HTTP(S) sin secretos. Los destinos externos se listan, nunca se visitan."""
    if not isinstance(raw, str) or not raw.strip() or raw.strip().startswith("#"):
        return None
    try:
        # Resuelve enlaces relativos y descarta esquemas no web, usuario/contraseña en la URL
        # y parámetros con apariencia de secreto (sesskey, token, ...).
        url = urljoin(source_url, raw.strip())
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or _SECRET.search(unquote(parts.query))
            or _SECRET.search(unquote(parts.fragment))
        ):
            return None
        # Fuerza validación de puertos incluso en enlaces que solo se devolverán.
        _ = parts.port
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return None


# Si la URL es mod/<tipo>/view.php?id=<n> del campus, devuelve (tipo, n); si no, None.
def module_target(url: str) -> tuple[str, int] | None:
    if not same_origin(url, CAMPUS_BASE_URL):
        return None
    parts = urlsplit(url)
    match = _MODULE_PATH.fullmatch(parts.path)
    ids = parse_qs(parts.query).get("id", [])
    if not match or len(ids) != 1 or not re.fullmatch(r"[1-9][0-9]*", ids[0]):
        return None
    return match[1], int(ids[0])


def module_view_url(module_type: str, module_id: int) -> str:
    """Página de lectura de un módulo; forceview evita que mod/resource redirija al archivo."""
    url = urljoin(CAMPUS_BASE_URL, f"mod/{module_type}/view.php?" + urlencode({"id": module_id}))
    return url + "&forceview=1" if module_type == "resource" else url


def file_module_type(url: str) -> str | None:
    """Tipo del módulo dueño de un archivo, según su ruta de pluginfile.php."""
    if not same_origin(url, CAMPUS_BASE_URL):
        return None
    match = _MODULE_FILE_PATH.match(urlsplit(url).path)
    return match[1] if match else None


# Si el enlace lleva a una sección de esta misma materia, devuelve (índice, URL canónica).
def section_target(raw: Any, course_id: int, source_url: str) -> tuple[int, str] | None:
    url = clean_link(raw, source_url)
    if not url or not same_origin(url, CAMPUS_BASE_URL):
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if parts.path != "/course/view.php" or query.get("id") != [str(course_id)]:
        return None
    values = query.get("section", [])
    if len(values) != 1:
        return None
    index = integer(values[0])
    return index, urljoin(
        CAMPUS_BASE_URL,
        "course/view.php?"
        + urlencode(
            {
                "id": course_id,
                "section": index,
            }
        ),
    )


def make_link(
    row: Any,
    source_url: str,
    section_index: int,
    module_id: int | None = None,
    module_type: str | None = None,
) -> CourseLink | None:
    if not isinstance(row, dict):
        raise invalid_resources()
    url = clean_link(row.get("url"), source_url)
    if not url:
        return None
    # Clasifica el enlace: externo, archivo (pluginfile o extensión conocida), actividad de
    # Moodle según su tipo, o enlace interno genérico.
    parts = urlsplit(url)
    target = module_target(url)
    if not same_origin(url, CAMPUS_BASE_URL):
        kind = "external"
    elif (
        "/pluginfile.php/" in parts.path
        or PurePosixPath(unquote(parts.path)).suffix.lower() in _FILE_SUFFIXES
    ):
        kind = "file"
    elif target:
        kind = {"assign": "assignment", "folder": "folder", "resource": "resource"}.get(
            target[0], "activity"
        )
    else:
        kind = "link"
    # Nombre visible normalizado; si no hay, el nombre del archivo de la URL.
    name = row.get("name")
    return CourseLink(
        name=" ".join(name.split())
        if isinstance(name, str) and name.strip()
        else unquote(PurePosixPath(parts.path).name) or url,
        url=url,
        kind=kind,
        section_index=section_index,
        module_id=module_id,
        module_type=module_type,
        source_url=source_url,
    )


def parse_course_page(
    payload: Any, course_id: int
) -> tuple[str, list[CourseSection], list[CourseLink], list[UnlinkedActivity], list[CourseSection]]:
    # Devuelve (formato, secciones leídas, enlaces, actividades sin enlace, navegación).
    # 1. La página debe ser la de este curso, completa, sin error y en un formato conocido.
    if not isinstance(payload, dict) or not payload.get("present"):
        raise invalid_resources()
    if payload.get("access_denied"):
        raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso al curso.")
    if payload.get("truncated") is not False:
        raise CourseError(
            "RESOURCES_LIMIT_EXCEEDED", "El contenido supera el límite de extracción."
        )
    source = clean_link(payload.get("url"), CAMPUS_BASE_URL)
    if not source or not same_origin(source, CAMPUS_BASE_URL):
        raise invalid_resources()
    parts = urlsplit(source)
    if (
        parts.path != "/course/view.php"
        or parse_qs(parts.query).get("id") != [str(course_id)]
        or str(payload.get("course_id")) != str(course_id)
    ):
        raise invalid_resources()
    format_name = payload.get("format")
    if format_name not in ("topics", "onetopic"):
        raise invalid_resources()
    sections, links, unlinked, navigation = [], [], [], []
    rows = payload.get("sections")
    if not isinstance(rows, list) or not rows:
        raise invalid_resources()
    # 2. Cada sección presente en la página queda marcada como visitada.
    for row in rows:
        index = integer(row["index"])
        sections.append(
            CourseSection(
                index=index,
                id=integer(row["id"], 1) if row.get("id") else None,
                name=row.get("name"),
                url=source,
                visited=True,
            )
        )
        activities, section_links = row.get("activities"), row.get("links")
        if not isinstance(activities, list) or not isinstance(section_links, list):
            raise invalid_resources()
        # 3. Actividades: el tipo sale de la clase CSS modtype_<tipo>. Su enlace principal debe
        #    apuntar al mismo módulo; sin enlace (restringida u oculta) se lista aparte.
        activity_urls = set()
        for activity in activities:
            module_id = integer(activity.get("id"), 1)
            types = re.findall(r"(?:^|\s)modtype_([a-z0-9_]+)(?=\s|$)", activity.get("classes", ""))
            if len(types) != 1:
                raise invalid_resources()
            module_type = types[0]
            name = activity.get("name") or module_type
            primary = make_link(
                {"name": name, "url": activity.get("url")}, source, index, module_id, module_type
            )
            if primary:
                target = module_target(primary.url)
                if target and target != (module_type, module_id):
                    raise invalid_resources()
                links.append(primary)
                activity_urls.add(primary.url)
            else:
                unlinked.append(
                    UnlinkedActivity(
                        module_id=module_id,
                        module_type=module_type,
                        name=name,
                        section_index=index,
                        availability=activity.get("availability"),
                    )
                )
            # Enlaces dentro de la descripción de la actividad, asociados a ese módulo.
            if not isinstance(activity.get("links"), list):
                raise invalid_resources()
            for embedded in activity["links"]:
                link = make_link(embedded, source, index, module_id, module_type)
                if link:
                    activity_urls.add(link.url)
                    links.append(link)
        # Resto de enlaces de la sección (resumen, etiquetas), sin repetir los de actividades.
        for embedded in section_links:
            link = make_link(embedded, source, index)
            if link and link.url not in activity_urls:
                links.append(link)
    # 4. Navegación: enlaces a otras secciones del curso, para recorrer las que no vinieron
    #    en esta página. Las marcadas como deshabilitadas no se visitan.
    nav = payload.get("navigation")
    if not isinstance(nav, list):
        raise invalid_resources()
    # Las pestañas tienen prioridad sobre la sidebar para respetar disabled.
    disabled = set()
    for row in nav:
        target = section_target(row.get("url"), course_id, source)
        if target and row.get("disabled") is True:
            disabled.add(target[0])
    for row in nav:
        target = section_target(row.get("url"), course_id, source)
        if target:
            index, url = target
            navigation.append(
                CourseSection(
                    index=index, name=row.get("name"), url=url, available=index not in disabled
                )
            )
    return format_name, sections, links, unlinked, navigation
