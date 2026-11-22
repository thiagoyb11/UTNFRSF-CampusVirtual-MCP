"""Descarga de archivos elegidos de un módulo de la asignatura, con verificación de pertenencia."""

from pathlib import Path

from anyio import to_thread

from utnfrsf_campus_mcp.browser.downloads import download_file, session_cookie_jar
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import CourseError, DownloadError, SubmissionError
from utnfrsf_campus_mcp.models import Course, DownloadedResources, DownloadFailure
from utnfrsf_campus_mcp.parsers.resources import clean_link, file_module_type, is_assignment_file
from utnfrsf_campus_mcp.services.resources import ResourceService
from utnfrsf_campus_mcp.services.submissions import SubmissionService


class DownloadService:
    def __init__(
        self, resources: ResourceService, session: CampusSession, submissions: SubmissionService
    ) -> None:
        self._resources = resources
        self._submissions = submissions
        self._session = session
        # Raíz fija de descargas: el usuario no elige destino, para impedir escrituras arbitrarias.
        self._root = (Path.cwd() / "downloads").resolve()

    async def download_resources(
        self, course_id: int, module_id: int, urls: list[str]
    ) -> DownloadedResources:
        # 1. Validación local de la selección: IDs positivos y de 1 a 10 URLs sin repetir.
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
        # Cada URL debe coincidir con su versión limpia: sin credenciales, tokens ni otros esquemas.
        for url in urls:
            if clean_link(url, CAMPUS_BASE_URL) != url:
                raise DownloadError(
                    "DOWNLOAD_INVALID_SELECTION", "Solo se aceptan enlaces válidos sin secretos."
                )
        # 2. Verificación en el campus: todas las URLs deben figurar hoy en ese módulo.
        course, allowed = await self._module_files(course_id, module_id, urls)
        if not set(urls) <= allowed:
            raise DownloadError(
                "DOWNLOAD_NOT_IN_COURSE",
                "Los archivos deben figurar en el módulo indicado del curso.",
            )
        # 3. Carpeta de destino downloads/course-<id>/module-<id>, que no puede escapar de la raíz.
        destination = self._root / f"course-{course_id}" / f"module-{module_id}"
        if not destination.resolve().is_relative_to(self._root):
            raise DownloadError(
                "DOWNLOAD_INVALID_DESTINATION", "El destino está fuera de downloads."
            )
        # 4. Descarga: se copian en memoria las cookies de la sesión de Lightpanda y cada
        # archivo se baja por HTTP en un hilo aparte, para no bloquear el servidor.
        files, failures = [], []
        async with self._session.acquire() as page:
            await self._resources.require_session(page)
            cookies = session_cookie_jar(await page.get_cookies(url=CAMPUS_BASE_URL))
            for url in urls:
                try:
                    # La cancelación espera la limpieza del temporal en el worker.
                    files.append(await to_thread.run_sync(download_file, url, cookies, destination))
                except DownloadError as exc:
                    # Un fallo de un archivo se registra y se sigue con el próximo...
                    failures.append(
                        DownloadFailure(source_url=url, code=exc.code, message=str(exc))
                    )
                    # ...salvo los fallos de acceso, que afectarían a todos: se detiene la
                    # descarga y los archivos restantes quedan marcados como no intentados.
                    if exc.code == "DOWNLOAD_RATE_LIMITED":
                        self._session.rate_limit.note(exc.retry_after)
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
            course=course,
            module_id=module_id,
            complete=not failures,
            files=files,
            failures=failures,
        )

    async def _module_files(
        self, course_id: int, module_id: int, urls: list[str]
    ) -> tuple[Course, set[str]]:
        """Archivos que el campus muestra hoy en el módulo, para verificar la selección.

        Si la ruta de los archivos indica el tipo de módulo, alcanza con leer su página.
        Los archivos de devolución o de entrega de una tarea se verifican contra la página
        de la tarea. Si no, se recurre al inventario completo del curso, más lento pero general.
        """
        if all(is_assignment_file(url) for url in urls):
            return await self._assignment_files(course_id, module_id)
        types = {file_module_type(url) for url in urls}
        if len(types) == 1 and (module_type := types.pop()):
            try:
                return await self._resources.module_file_urls(course_id, module_id, module_type)
            except CourseError as exc:
                if exc.code == "RESOURCES_MODULE_NOT_FOUND":
                    raise DownloadError(
                        "DOWNLOAD_NOT_IN_COURSE",
                        "Los archivos deben figurar en el módulo indicado del curso.",
                    ) from None
                raise
        inventory = await self._resources.get_course_resources(course_id)
        allowed = {
            row.url for row in inventory.links if row.module_id == module_id and row.kind == "file"
        }
        return inventory.course, allowed

    async def _assignment_files(self, course_id: int, module_id: int) -> tuple[Course, set[str]]:
        """Archivos que la tarea muestra hoy en la devolución del docente y en la entrega.

        Reutiliza la lectura de get_assignment_feedback, que confirma que la página es esa
        tarea de esa materia. Si no hay devolución visible, solo quedan los entregados.
        """
        try:
            feedback = await self._submissions.get_assignment_feedback(course_id, module_id)
        except SubmissionError as exc:
            if exc.code == "SUBMISSION_INVALID_ACTIVITY":
                raise DownloadError(
                    "DOWNLOAD_NOT_IN_COURSE",
                    "Los archivos deben figurar en el módulo indicado del curso.",
                ) from None
            raise
        course = await self._resources.find_course(course_id)
        return course, {f.url for f in [*feedback.feedback_files, *feedback.submission_files]}
