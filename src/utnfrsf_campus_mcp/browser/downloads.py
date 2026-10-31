"""Transporte HTTP binario con cookies de Lightpanda, sin redirecciones ni secretos en disco."""

import hashlib
import json
import os
import re
import tempfile
import time
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from http.client import HTTPException
from http.cookiejar import Cookie, CookieJar
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import DownloadError
from utnfrsf_campus_mcp.models import DownloadedFile
from utnfrsf_campus_mcp.parsers.login import same_origin

MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 180


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def session_cookie_jar(payload: Any) -> CookieJar:
    """Filtra dominio, path, secure y expiración. Nunca devuelve cookies al cliente MCP."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            # Lightpanda 1.0.2 devuelve una cookie por línea, con Domain/Path/Secure.
            # SimpleCookie conserva esos atributos sin imprimir nombres ni valores.
            parsed = SimpleCookie()
            try:
                parsed.load(payload)
            except CookieError:
                raise DownloadError(
                    "DOWNLOAD_COOKIES_UNSUPPORTED", "No se pudo leer la sesión del navegador."
                ) from None
            payload = [
                {
                    "name": name,
                    "value": morsel.value,
                    "domain": morsel["domain"],
                    "path": morsel["path"],
                    "secure": bool(morsel["secure"]),
                }
                for name, morsel in parsed.items()
            ]
    entries = payload.get("cookies") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise DownloadError(
            "DOWNLOAD_COOKIES_UNSUPPORTED", "No se pudo leer la sesión del navegador."
        )
    host = urlsplit(CAMPUS_BASE_URL).hostname
    jar = CookieJar()
    for row in entries:
        if not isinstance(row, dict):
            raise DownloadError(
                "DOWNLOAD_COOKIES_UNSUPPORTED", "La sesión tiene un formato inesperado."
            )
        domain = str(row.get("domain", "")).lower()
        cookie_host = domain.lstrip(".")
        if not cookie_host or not (host == cookie_host or host.endswith("." + cookie_host)):
            continue
        name, value = row.get("name"), row.get("value")
        if (
            not isinstance(name, str)
            or not isinstance(value, str)
            or not re.fullmatch(r"[!#$%&\'*+.^_`|~0-9A-Za-z-]+", name)
            or any(c in value for c in "\r\n;")
        ):
            raise DownloadError(
                "DOWNLOAD_COOKIES_UNSUPPORTED", "No se pudo usar la sesión del navegador."
            )
        expires = row.get("expires")
        expires = int(expires) if isinstance(expires, (float, int)) and expires > 0 else None
        jar.set_cookie(
            Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=domain.startswith("."),
                domain_initial_dot=domain.startswith("."),
                path=row.get("path") or "/",
                path_specified=True,
                secure=bool(row.get("secure")),
                expires=expires,
                discard=expires is None,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )
    if not list(jar):
        raise DownloadError(
            "DOWNLOAD_SESSION_MISSING", "No se encontraron cookies válidas del campus."
        )
    return jar


class _CampusPageDetector(HTMLParser):
    """Reconoce login y errores de Moodle sin rechazar archivos HTML legítimos."""

    def __init__(self) -> None:
        super().__init__()
        self.moodle_body = False
        self.login = False
        self.error = False
        self.login_form = False
        self.login_fields: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "body":
            body_id = attributes.get("id") or ""
            self.moodle_body = body_id.startswith("page-")
            self.login = body_id == "page-login-index" or (
                self.moodle_body and "notloggedin" in classes
            )
        if tag == "form":
            action = attributes.get("action") or ""
            self.login_form = urlsplit(action).path.endswith("/login/index.php")
            self.login_fields.clear()
        if tag == "input" and self.login_form:
            self.login_fields.add(attributes.get("name"))
            if {"username", "password"} <= self.login_fields:
                self.login = True
        if self.moodle_body and {"alert-danger", "errorbox"}.intersection(classes):
            self.error = True

    def handle_endtag(self, tag):
        if tag == "form":
            self.login_form = False
            self.login_fields.clear()


def safe_file_name(url: str) -> str:
    name = unicodedata.normalize("NFKC", unquote(urlsplit(url).path).split("/")[-1])
    name = re.sub(r"[\\/:\x00-\x1f\x7f]", "_", name).strip(" .")
    name = name or "download"
    suffix = Path(name).suffix
    if len(suffix.encode("utf-8")) > 32:
        suffix = ""
    stem = name[: -len(suffix)] if suffix else name
    budget = 200 - len(suffix.encode("utf-8"))
    return stem.encode("utf-8")[:budget].decode("utf-8", errors="ignore") + suffix


def download_file(url: str, jar: CookieJar, destination: Path) -> DownloadedFile:
    """Escribe primero un temporal privado, valida la transferencia y publica sin sobrescritura."""
    if not same_origin(url, CAMPUS_BASE_URL) or not urlsplit(url).path.startswith(
        "/pluginfile.php/"
    ):
        raise DownloadError(
            "DOWNLOAD_INVALID_URL", "Solo se descargan archivos observados del campus."
        )
    name = safe_file_name(url)
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    descriptor, temporary_name = tempfile.mkstemp(prefix=".partial-", dir=destination)
    temporary = Path(temporary_name)
    try:
        opener = build_opener(_NoRedirect(), HTTPCookieProcessor(jar))
        request = Request(url, headers={"Accept": "*/*"})
        started = time.monotonic()
        digest = hashlib.sha256()
        size = 0
        html_detector = None
        with os.fdopen(descriptor, "wb") as output, opener.open(request, timeout=30) as response:
            if response.status != 200 or not same_origin(response.url, CAMPUS_BASE_URL):
                raise DownloadError(
                    "DOWNLOAD_HTTP_ERROR", "El campus no devolvió el archivo solicitado."
                )
            content_type = response.headers.get_content_type()
            length = response.headers.get("Content-Length")
            try:
                expected = int(length) if length is not None else None
            except ValueError:
                raise DownloadError(
                    "DOWNLOAD_HTTP_ERROR", "El tamaño informado no es válido."
                ) from None
            if expected is not None and not 0 <= expected <= MAX_DOWNLOAD_BYTES:
                raise DownloadError(
                    "DOWNLOAD_TOO_LARGE", "El tamaño del archivo está fuera del límite permitido."
                )
            while block := response.read(64 * 1024):
                if time.monotonic() - started > DOWNLOAD_TIMEOUT_SECONDS:
                    raise DownloadError(
                        "DOWNLOAD_TIMEOUT", "Se agotó el tiempo de descarga del archivo."
                    )
                if size == 0 and (
                    content_type in ("text/html", "application/xhtml+xml")
                    or block.lstrip().lower().startswith((b"<!doctype html", b"<html", b"<body"))
                ):
                    html_detector = _CampusPageDetector()
                if html_detector is not None:
                    html_detector.feed(block.decode("utf-8", errors="replace"))
                    if html_detector.login:
                        raise DownloadError(
                            "DOWNLOAD_SESSION_EXPIRED", "El campus devolvió la página de acceso."
                        )
                    if html_detector.error:
                        raise DownloadError(
                            "DOWNLOAD_ACCESS_DENIED", "El campus devolvió una página de error."
                        )
                size += len(block)
                if size > MAX_DOWNLOAD_BYTES:
                    raise DownloadError(
                        "DOWNLOAD_TOO_LARGE", "El archivo supera el límite de 200 MiB."
                    )
                digest.update(block)
                output.write(block)
            if expected is not None and size != expected:
                raise DownloadError(
                    "DOWNLOAD_INCOMPLETE",
                    "El tamaño recibido no coincide con el informado por el campus.",
                )
            output.flush()
            os.fsync(output.fileno())
        # Hard link publica de manera atómica y falla si el nombre ya existe.
        # Un sufijo evita reemplazar descargas anteriores, incluso bajo concurrencia.
        for index in range(1000):
            original = Path(name)
            candidate = destination / (
                name if index == 0 else f"{original.stem} ({index}){original.suffix}"
            )
            try:
                os.link(temporary, candidate)
                return DownloadedFile(
                    name=candidate.name,
                    path=str(candidate),
                    source_url=url,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    content_type=content_type,
                    downloaded_at=datetime.now(UTC),
                )
            except FileExistsError:
                continue
        raise DownloadError(
            "DOWNLOAD_DESTINATION_FULL", "No se encontró un nombre de archivo libre."
        )
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            code, message = (
                "DOWNLOAD_REDIRECT",
                "El campus redirigió la descarga; verificá la sesión.",
            )
        elif exc.code in (401, 403):
            code, message = "DOWNLOAD_ACCESS_DENIED", "El campus denegó el acceso al archivo."
        elif exc.code == 429:
            code, message = "DOWNLOAD_RATE_LIMITED", "El campus limitó las solicitudes."
        else:
            code, message = "DOWNLOAD_HTTP_ERROR", "No se pudo descargar el archivo."
        exc.close()
        raise DownloadError(code, message) from None
    except HTTPException:
        raise DownloadError(
            "DOWNLOAD_INCOMPLETE", "La respuesta de descarga se interrumpió."
        ) from None
    except (TimeoutError, URLError):
        raise DownloadError(
            "DOWNLOAD_NETWORK_ERROR", "No se pudo completar la conexión de descarga."
        ) from None
    except OSError:
        raise DownloadError(
            "DOWNLOAD_IO_ERROR", "No se pudo guardar el archivo en el destino local."
        ) from None
    finally:
        temporary.unlink(missing_ok=True)
