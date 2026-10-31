"""Carga multipart sobre el formulario oficial sin JS, autenticado con Lightpanda."""

import hashlib
import mimetypes
import time
import uuid
from collections.abc import Callable, Iterator
from http.client import HTTPException
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener

from utnfrsf_campus_mcp.browser.downloads import _NoRedirect
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import SubmissionError
from utnfrsf_campus_mcp.models import LocalSubmissionFile, UploadLimits
from utnfrsf_campus_mcp.parsers.submissions import (
    CampusForm,
    CampusHTML,
    draft_links,
    fail,
    find_link,
    prepare_submission,
    require_url,
    validate_files,
)

_FORM_PATHS = (
    "/repository/filepicker.php",
    "/repository/repository_ajax.php",
    "/repository/draftfiles_manager.php",
    "/mod/assign/view.php",
)


class CampusHTTP:
    """Cookies y tokens privados; cada POST se ejecuta exactamente una vez."""

    def __init__(
        self,
        cookies: CookieJar,
        user_agent: str = "CampusVirtualMCP/0.1",
        referer: str | None = None,
    ):
        self._user_agent = user_agent
        self._referer = require_url(referer, _FORM_PATHS) if referer else None
        self._opener = build_opener(_NoRedirect(), HTTPCookieProcessor(cookies))

    def document(self, url: str, data=None, headers=None, _read_attempt: int = 0) -> CampusHTML:
        require_url(url, _FORM_PATHS)
        writing = data is not None
        method = "POST" if writing else "GET"
        try:
            request_headers = {"User-Agent": self._user_agent, **(headers or {})}
            if writing:
                origin = urlsplit(CAMPUS_BASE_URL)
                request_headers.update(
                    {
                        "Origin": origin.scheme + "://" + origin.netloc,
                        "Referer": self._referer or url,
                    }
                )
                if urlsplit(url).path == "/repository/repository_ajax.php":
                    request_headers["X-Requested-With"] = "XMLHttpRequest"
            request = Request(url, data=data, headers=request_headers, method=method)
            with self._opener.open(request, timeout=60) as response:
                require_url(response.url, _FORM_PATHS)
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise fail(
                        "SUBMISSION_FORMAT_UNSUPPORTED",
                        "El formulario excede el límite de lectura.",
                    )
                result = CampusHTML(raw.decode("utf-8", errors="replace"), response.url)
                result.require_access()
                return result
        except HTTPError as exc:
            status, location = exc.code, exc.headers.get("Location")
            retry_after = exc.headers.get("Retry-After", "2")
            exc.close()
            if status == 429 and not writing and _read_attempt < 2:
                if not retry_after.isdigit() or int(retry_after) > 15:
                    raise fail(
                        "SUBMISSION_RATE_LIMITED",
                        "El campus pide esperar antes de leer el formulario.",
                    ) from None
                time.sleep(max(1, int(retry_after)))
                return self.document(url, _read_attempt=_read_attempt + 1)
            if status in (301, 302, 303) and location:
                target = urljoin(url, location)
                if urlsplit(target).path == "/login/index.php":
                    raise fail(
                        "SUBMISSION_SESSION_EXPIRED", "La sesión dejó de estar activa."
                    ) from None
                require_url(target, _FORM_PATHS)
                # Nunca reenviar el POST ni sus bytes a la redirección.
                if not writing:
                    raise fail(
                        "SUBMISSION_UNEXPECTED_REDIRECT",
                        "El formulario requiere una redirección no soportada.",
                    ) from None
                return self.document(target)
            code = "SUBMISSION_RATE_LIMITED" if status == 429 else "SUBMISSION_ACCESS_DENIED"
            raise fail(
                code, f"HTTP {status} en {method} {urlsplit(url).path}; no se reenvió el POST."
            ) from None
        except (OSError, URLError, HTTPException, TimeoutError):
            code = "SUBMISSION_WRITE_UNCERTAIN" if writing else "SUBMISSION_NETWORK_ERROR"
            raise fail(
                code, "No se pudo confirmar la respuesta del campus; no se reintentó."
            ) from None

    def post_form(self, form: CampusForm, fields: dict[str, str]) -> CampusHTML:
        return self.document(
            form.action,
            urlencode(fields).encode(),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

    def hash_file(self, url: str, maximum: int) -> tuple[int, str]:
        if not urlsplit(url).path.startswith(("/draftfile.php/", "/pluginfile.php/")):
            raise fail(
                "UPLOAD_VERIFICATION_FAILED",
                "El campus no devolvió un enlace de archivo verificable.",
            )
        from utnfrsf_campus_mcp.parsers.login import same_origin

        if not same_origin(url, CAMPUS_BASE_URL):
            raise fail("UPLOAD_VERIFICATION_FAILED", "El archivo de verificación salió del campus.")
        digest = hashlib.sha256()
        size = 0
        started = time.monotonic()
        try:
            with self._opener.open(Request(url), timeout=30) as response:
                while block := response.read(64 * 1024):
                    size += len(block)
                    if size > maximum or time.monotonic() - started > 180:
                        raise fail(
                            "UPLOAD_VERIFICATION_FAILED",
                            "La verificación supera el tamaño o tiempo permitido.",
                        )
                    digest.update(block)
            return size, digest.hexdigest()
        except (OSError, URLError, HTTPException, TimeoutError):
            raise fail(
                "UPLOAD_VERIFICATION_FAILED", "No se pudo verificar el archivo del campus."
            ) from None


class MultipartFile:
    """Iterable con Content-Length conocido: no carga el archivo entero en memoria."""

    def __init__(self, fields: dict[str, str], field_name: str, file: LocalSubmissionFile):
        self.boundary = "CampusMCP" + uuid.uuid4().hex
        self.file = file
        self.prefix = b""
        for name, value in fields.items():
            if any(c in name for c in '\r\n"'):
                raise fail(
                    "UPLOAD_FORM_UNSUPPORTED", "Un campo multipart tiene un nombre inesperado."
                )
            self.prefix += (
                f"--{self.boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            ).encode()
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self.prefix += (
            f"--{self.boundary}\r\nContent-Disposition: form-data; "
            f'name="{field_name}"; filename="{file.name}"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode()
        self.suffix = f"\r\n--{self.boundary}--\r\n".encode()
        self.length = len(self.prefix) + file.size_bytes + len(self.suffix)

    def __iter__(self) -> Iterator[bytes]:
        yield self.prefix
        digest = hashlib.sha256()
        size = 0
        with open(self.file.path, "rb") as source:
            while block := source.read(64 * 1024):
                size += len(block)
                digest.update(block)
                yield block
        if size != self.file.size_bytes or digest.hexdigest() != self.file.sha256:
            raise fail(
                "SUBMISSION_WRITE_UNCERTAIN",
                "El archivo cambió durante la transferencia; revisá el área temporal.",
            )
        yield self.suffix


class FileUploadHelper:
    """upload_files(files) queda ligado a un gestor observado, no a una URL del usuario."""

    def __init__(
        self,
        http: CampusHTTP,
        manager_url: str,
        limits: UploadLimits,
        upload_transport: Callable | None = None,
        ajax_form: CampusForm | None = None,
    ):
        self.http, self.manager_url, self.limits = http, manager_url, limits
        self._upload_transport = upload_transport
        self._ajax_form = ajax_form
        require_url(manager_url, ("/repository/draftfiles_manager.php",))
        self._binding = parse_qs(urlsplit(manager_url).query)
        for name in ("itemid", "course", "ctx_id", "sesskey"):
            if len(self._binding.get(name, [])) != 1:
                raise fail(
                    "UPLOAD_MANAGER_UNSUPPORTED", "El gestor no identifica un contexto único."
                )
        self.itemid = self._binding["itemid"][0]

    def _bind(self, url: str):
        require_url(url, ("/repository/filepicker.php", "/repository/draftfiles_manager.php"))
        query = parse_qs(urlsplit(url).query)
        if any(
            query.get(key) != self._binding[key]
            for key in ("itemid", "course", "ctx_id", "sesskey")
        ):
            raise fail(
                "UPLOAD_CONTEXT_CHANGED", "El selector cambió de cuenta, curso o área temporal."
            )

    def listing(self) -> dict[str, str]:
        return draft_links(self.http.document(self.manager_url), self.itemid)

    def _upload_form(self) -> CampusForm:
        if self._ajax_form is not None:
            require_url(self._ajax_form.action, ("/repository/repository_ajax.php",))
            for key in ("itemid", "ctx_id", "sesskey"):
                if self._ajax_form.fields.get(key) != self._binding[key][0]:
                    raise fail("UPLOAD_CONTEXT_CHANGED", "El formulario AJAX cambió de contexto.")
            return self._ajax_form
        manager = self.http.document(self.manager_url)
        plugins_url = find_link(manager, "/repository/filepicker.php", "plugins")
        self._bind(plugins_url)
        plugins = self.http.document(plugins_url)
        candidates = list(
            dict.fromkeys(
                url
                for url, _ in plugins.links
                if urlsplit(url).path == "/repository/filepicker.php"
                and parse_qs(urlsplit(url).query).get("action") == ["list"]
            )
        )
        if len(candidates) > 10:
            raise fail("UPLOAD_FORM_UNSUPPORTED", "El selector supera el límite de repositorios.")
        for url in candidates:
            self._bind(url)
            document = self.http.document(url)
            matches = [
                f
                for f in document.forms
                if f.file_fields == ["repo_upload_file"]
                and f.method == "post"
                and f.enctype == "multipart/form-data"
                and f.fields.get("action") == "upload"
            ]
            if len(matches) == 1:
                self._bind(matches[0].action)
                return matches[0]
        raise fail(
            "UPLOAD_FORM_UNSUPPORTED", "No se encontró el formulario oficial de carga local."
        )

    def upload_files(self, files: list[LocalSubmissionFile]) -> list[LocalSubmissionFile]:
        existing = self.listing()
        existing_bytes = sum(
            self.http.hash_file(url, 200 * 1024 * 1024)[0] for url in existing.values()
        )
        validate_files(files, self.limits, list(existing), existing_bytes)
        fresh = prepare_submission(1, 1, [file.path for file in files]).files
        if fresh != files:
            raise fail("UPLOAD_FILE_CHANGED", "Los archivos cambiaron después de prepararlos.")
        uploaded = []
        for file in files:
            form = self._upload_form()
            body = MultipartFile(form.fields, "repo_upload_file", file)
            uncertain = None
            try:
                if self._upload_transport is not None:
                    self._upload_transport(form, file)
                else:
                    self.http.document(
                        form.action,
                        body,
                        {
                            "Content-Type": "multipart/form-data; boundary=" + body.boundary,
                            "Content-Length": str(body.length),
                        },
                    )
            except SubmissionError as exc:
                if exc.code != "SUBMISSION_WRITE_UNCERTAIN":
                    raise
                uncertain = exc
            # Reconciliar antes de considerar una repetición; nunca se reenvía el POST.
            try:
                after = self.listing()
                url = after.get(file.name)
                if url is None or self.http.hash_file(url, file.size_bytes + 1) != (
                    file.size_bytes,
                    file.sha256,
                ):
                    raise fail(
                        "UPLOAD_VERIFICATION_FAILED",
                        "No se confirmó el archivo completo en el área temporal.",
                    )
            except SubmissionError:
                raise fail(
                    "SUBMISSION_WRITE_UNCERTAIN" if uncertain else "UPLOAD_PARTIAL",
                    "La carga no quedó verificada. "
                    f"Archivos anteriores confirmados: {len(uploaded)}. "
                    "No se guardó la entrega.",
                ) from None
            uploaded.append(file)
        return uploaded
