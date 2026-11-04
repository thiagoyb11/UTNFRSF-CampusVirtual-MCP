"""Descarga de archivos elegidos de un módulo de la asignatura, con verificación de pertenencia."""

from pathlib import Path

from anyio import to_thread

from utnfrsf_campus_mcp.browser.downloads import download_file, session_cookie_jar
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import DownloadError
from utnfrsf_campus_mcp.models import DownloadedResources, DownloadFailure
from utnfrsf_campus_mcp.parsers.resources import clean_link
from utnfrsf_campus_mcp.services.resources import ResourceService


class DownloadService:
    def __init__(self, resources: ResourceService, session: CampusSession) -> None:
        self._resources = resources
        self._session = session
        self._root = (Path.cwd() / "downloads").resolve()

    async def download_resources(
        self, course_id: int, module_id: int, urls: list[str]
    ) -> DownloadedResources:
        if (
            type(course_id) is not int
            or course_id <= 0
            or type(module_id) is not int
            or module_id <= 0
            or not isinstance(urls, list)
            or not 1 <= len(urls) <= 10
            or not all(isinstance(url, str) for url in urls)
            or len(set(urls)) != len(urls)
        ):
            raise DownloadError(
                "DOWNLOAD_INVALID_SELECTION",
                "Indicá un curso, módulo y entre 1 y 10 archivos únicos.",
            )
        for url in urls:
            if clean_link(url, CAMPUS_BASE_URL) != url:
                raise DownloadError(
                    "DOWNLOAD_INVALID_SELECTION", "Solo se aceptan enlaces válidos sin secretos."
                )
        inventory = await self._resources.get_course_resources(course_id)
        allowed = {
            row.url for row in inventory.links if row.module_id == module_id and row.kind == "file"
        }
        if not set(urls) <= allowed:
            raise DownloadError(
                "DOWNLOAD_NOT_IN_COURSE",
                "Los archivos deben figurar en el módulo indicado del curso.",
            )
        destination = self._root / f"course-{course_id}" / f"module-{module_id}"
        if not destination.resolve().is_relative_to(self._root):
            raise DownloadError(
                "DOWNLOAD_INVALID_DESTINATION", "El destino está fuera de downloads."
            )
        files, failures = [], []
        async with self._session.acquire() as page:
            await self._resources.require_session(page)
            cookies = session_cookie_jar(await page.get_cookies(url=CAMPUS_BASE_URL))
            for url in urls:
                try:
                    # La cancelación espera la limpieza del temporal en el worker.
                    files.append(await to_thread.run_sync(download_file, url, cookies, destination))
                except DownloadError as exc:
                    failures.append(
                        DownloadFailure(source_url=url, code=exc.code, message=str(exc))
                    )
                    if exc.code in (
                        "DOWNLOAD_SESSION_EXPIRED",
                        "DOWNLOAD_ACCESS_DENIED",
                        "DOWNLOAD_RATE_LIMITED",
                        "DOWNLOAD_REDIRECT",
                    ):
                        for pending in urls[len(files) + len(failures) :]:
                            failures.append(
                                DownloadFailure(
                                    source_url=pending,
                                    code="DOWNLOAD_NOT_ATTEMPTED",
                                    message="Descarga detenida por un fallo de acceso.",
                                )
                            )
                        break
        return DownloadedResources(
            course=inventory.course,
            module_id=module_id,
            complete=not failures,
            files=files,
            failures=failures,
        )
