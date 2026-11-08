"""Inventario de enlaces de un curso: secciones, tareas, materiales y carpetas."""

import logging
from datetime import UTC, datetime
from urllib.parse import urljoin

from anyio import fail_after
from lightpanda import AsyncSession, LightpandaError

from utnfrsf_campus_mcp.browser.resources import (
    COURSE_CONTENT_SCRIPT,
    FOLDER_CONTENT_SCRIPT,
    MODULE_OWNER_SCRIPT,
    PAGE_CONTENT_SCRIPT,
    SECTION_CONTENT_SCRIPT,
    read_module_links,
)
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import (
    ContentBlock,
    Course,
    CourseLink,
    CourseResources,
    CourseSection,
    PageContent,
    SectionContent,
    UnlinkedActivity,
)
from utnfrsf_campus_mcp.parsers.content import html_to_markdown
from utnfrsf_campus_mcp.parsers.login import (
    LOGIN_PAGE_STATE_SCRIPT,
    is_rate_limited_message,
    same_origin,
)
from utnfrsf_campus_mcp.parsers.resources import (
    integer,
    invalid_resources,
    make_link,
    module_target,
    module_view_url,
    parse_course_page,
    section_target,
)
from utnfrsf_campus_mcp.services.courses import CourseService

logger = logging.getLogger(__name__)
MAX_PAGES = 500
MAX_LINKS = 10000
QUERY_TIMEOUT_SECONDS = 180
_FATAL_CODES = {
    "RESOURCES_SESSION_EXPIRED",
    "RESOURCES_ACCESS_DENIED",
    "RESOURCES_RATE_LIMITED",
}


class ResourceService:
    def __init__(self, settings: Settings, session: CampusSession, courses: CourseService) -> None:
        self._settings = settings
        self._session = session
        self._courses = courses

    async def get_course_resources(self, course_id: int) -> CourseResources:
        # El helper autentica antes de adquirir el lock. No se anidan adquisiciones.
        course = await self.find_course(course_id)
        # Estado del recorrido: secciones vistas, enlaces (sin duplicados por URL, sección y
        # módulo), actividades sin enlace, páginas pendientes de leer y avisos de alcance.
        sections: dict[int, CourseSection] = {}
        links: dict[tuple[str, int, int | None], CourseLink] = {}
        unlinked: dict[tuple[int, int], UnlinkedActivity] = {}
        pending = {course.url: None}
        warnings: list[str] = []
        format_name = None
        visited_pages = 0

        # Registra un aviso una sola vez.
        def warn(message: str) -> None:
            if message not in warnings:
                warnings.append(message)

        # Agrega un enlace respetando el tope de 10000.
        def add_link(link: CourseLink) -> None:
            key = (link.url, link.section_index, link.module_id)
            if len(links) >= MAX_LINKS and key not in links:
                raise CourseError("RESOURCES_LIMIT_EXCEEDED", "Se alcanzaron los 10000 enlaces.")
            links.setdefault(key, link)

        try:
            with fail_after(QUERY_TIMEOUT_SECONDS):
                async with self._session.acquire() as page:
                    # Fase 1: recorrido en anchura de las secciones. Se empieza por la portada
                    # del curso y se encolan las secciones que aparecen en la navegación.
                    queue = [course.url]
                    visited_sections: set[str] = set()
                    while queue:
                        if visited_pages >= MAX_PAGES:
                            warn("RESOURCES_LIMIT_EXCEEDED: Se alcanzó el límite de páginas.")
                            break
                        url = queue.pop(0)
                        if url in visited_sections:
                            continue
                        await self._open_course(page, url)
                        payload = await page.evaluate(script=COURSE_CONTENT_SCRIPT)
                        parsed = parse_course_page(payload, course_id)
                        current_format, found_sections, found_links, found_unlinked, navigation = (
                            parsed
                        )
                        # Todas las páginas del curso deben tener el mismo formato.
                        if format_name is not None and format_name != current_format:
                            raise invalid_resources()
                        format_name = current_format
                        # Evita contar como visitada una pestaña que redirige a otra sección.
                        target = section_target(url, course_id, course.url)
                        if target and target[0] not in {s.index for s in found_sections}:
                            warn("RESOURCES_SECTION_MISSING: Una sección no devolvió su contenido.")
                            visited_sections.add(url)
                            continue
                        # Página leída: se incorporan sus secciones, enlaces y actividades.
                        visited_pages += 1
                        visited_sections.add(url)
                        pending.pop(url, None)
                        for section in found_sections:
                            previous = sections.get(section.index)
                            if previous and not section.name:
                                section.name = previous.name
                            sections[section.index] = section
                        for link in found_links:
                            add_link(link)
                        for activity in found_unlinked:
                            unlinked[(activity.section_index, activity.module_id)] = activity
                        # Secciones vistas en la navegación: se registran y, si están habilitadas
                        # y todavía no se leyeron, se encolan para la próxima vuelta.
                        for section in navigation:
                            previous = sections.get(section.index)
                            if previous is None:
                                sections[section.index] = section
                            else:
                                previous.name = previous.name or section.name
                                previous.available = previous.available and section.available
                            if section.available and not sections[section.index].visited:
                                if (
                                    section.url not in pending
                                    and section.url not in visited_sections
                                ):
                                    pending[section.url] = None
                                    queue.append(section.url)
                        if current_format == "onetopic" and not navigation:
                            warn(
                                "RESOURCES_SECTIONS_UNVERIFIED: "
                                "No se encontró navegación de secciones."
                            )
                    # Fase 2: se abre la página de cada recurso, carpeta, tarea, página y URL para
                    # obtener los archivos y enlaces que no aparecen en la portada del curso.
                    # Solo se amplían módulos observados y conocidos. Nunca se siguen URLs externas,
                    # enlaces a edición/envío, archivos binarios ni enlaces arbitrarios del HTML.
                    modules: dict[str, list[CourseLink]] = {}
                    for link in list(links.values()):
                        target = module_target(link.url)
                        if (
                            target
                            and target == (link.module_type, link.module_id)
                            and target[0] in ("resource", "folder", "assign", "page", "url")
                        ):
                            modules.setdefault(module_view_url(*target), []).append(link)
                    pending.update(dict.fromkeys(modules))
                    for url, parents in modules.items():
                        if visited_pages >= MAX_PAGES:
                            warn("RESOURCES_LIMIT_EXCEEDED: Se alcanzó el límite de páginas.")
                            break
                        visited_pages += 1
                        data = await read_module_links(page, url)
                        if not isinstance(data, dict):
                            raise invalid_resources()
                        # Sesión vencida, acceso denegado o 429 cortan todo; otros fallos de un
                        # módulo solo lo dejan pendiente y se informa con un aviso.
                        code = data.get("error")
                        if code in _FATAL_CODES:
                            raise CourseError(code, "No se pudo verificar el acceso al recurso.")
                        if code or data.get("truncated") is not False:
                            warn(
                                "RESOURCES_MODULE_INCOMPLETE: "
                                "Quedaron páginas de recursos sin resolver."
                            )
                            continue
                        rows = data.get("links")
                        if not isinstance(rows, list):
                            raise invalid_resources()
                        # Los enlaces encontrados heredan sección y módulo de quien los listó.
                        for parent in parents:
                            for row in rows:
                                link = make_link(
                                    row,
                                    url,
                                    parent.section_index,
                                    parent.module_id,
                                    parent.module_type,
                                )
                                if link:
                                    add_link(link)
                        pending.pop(url, None)
                    await self.require_session(page)
        # Si falla antes de leer la primera página, es un error. Si ya hay datos, se devuelve
        # el alcance parcial con complete=false y el motivo en warnings, salvo fallos de acceso.
        except CourseError as exc:
            if format_name is None or exc.code in _FATAL_CODES:
                raise
            warn(str(exc))
        except TimeoutError:
            if format_name is None:
                raise CourseError("RESOURCES_TIMEOUT", "Se agotó el tiempo de consulta.") from None
            warn("RESOURCES_TIMEOUT: Se agotó el tiempo; se devuelve el alcance consultado.")
        except LightpandaError as exc:
            code = (
                "RESOURCES_RATE_LIMITED"
                if is_rate_limited_message(str(exc))
                else "RESOURCES_BROWSER_ERROR"
            )
            if format_name is None or code in _FATAL_CODES:
                raise CourseError(code, "Lightpanda no pudo completar la consulta.") from None
            warn("RESOURCES_BROWSER_ERROR: Lightpanda interrumpió la consulta.")
        return CourseResources(
            course=course,
            format=format_name,
            fetched_at=datetime.now(UTC),
            total=len(links),
            links=list(links.values()),
            sections=list(sections.values()),
            unlinked_activities=list(unlinked.values()),
            complete=not pending and not warnings,
            pending_urls=list(pending),
            warnings=warnings,
        )

    # Resuelve un course_id a su materia de Grado (con el listado reciente en caché); un ID
    # que no está en Grado no se acepta.
    async def find_course(self, course_id: int) -> Course:
        if type(course_id) is not int or course_id <= 0:
            raise CourseError("RESOURCES_INVALID_COURSE", "Indicá un course_id entero positivo.")
        courses = await self._courses.recent_degree_courses()
        matches = [course for course in courses if course.id == course_id]
        if len(matches) != 1:
            raise CourseError("RESOURCES_COURSE_NOT_FOUND", "La asignatura no aparece en Grado.")
        return matches[0]

    async def module_file_urls(
        self, course_id: int, module_id: int, module_type: str
    ) -> tuple[Course, set[str]]:
        """Lee solo la página del módulo: confirma que es de la materia y lista sus archivos.

        Es la verificación de pertenencia de las descargas; evita recorrer el curso entero.
        """
        course = await self.find_course(course_id)
        url = module_view_url(module_type, module_id)
        # Abre la página del módulo, lee a qué materia y tipo pertenece y lista sus enlaces.
        try:
            with fail_after(QUERY_TIMEOUT_SECONDS):
                async with self._session.acquire() as page:
                    await self.open_page(page, url)
                    owner = await page.evaluate(script=MODULE_OWNER_SCRIPT)
                    data = await read_module_links(page, url)
        except TimeoutError:
            raise CourseError("RESOURCES_TIMEOUT", "Se agotó el tiempo de consulta.") from None
        except LightpandaError as exc:
            raise self.browser_error(exc) from None
        if not isinstance(owner, dict) or not isinstance(data, dict):
            raise invalid_resources()
        if owner.get("access_denied"):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso al módulo.")
        # El módulo debe ser del tipo esperado y de la materia indicada.
        if owner.get("body") != f"page-mod-{module_type}-view" or str(
            owner.get("course_id")
        ) != str(course_id):
            raise CourseError(
                "RESOURCES_MODULE_NOT_FOUND", "El módulo no es de ese tipo o de la materia."
            )
        # La lista de enlaces debe estar completa: un recorte podría ocultar un archivo pedido.
        code = data.get("error")
        if code in _FATAL_CODES:
            raise CourseError(code, "No se pudo verificar el acceso al módulo.")
        rows = data.get("links")
        if code or data.get("truncated") is not False or not isinstance(rows, list):
            raise CourseError(
                "RESOURCES_MODULE_INCOMPLETE", "No se pudieron leer los archivos del módulo."
            )
        # La sección no interviene en la verificación; make_link solo normaliza y clasifica.
        links = (make_link(row, url, 0, module_id, module_type) for row in rows)
        return course, {link.url for link in links if link and link.kind == "file"}

    async def get_section_content(self, course_id: int, section: int) -> SectionContent:
        """Lee resumen, etiquetas y descripciones de una sección; no sigue enlaces."""
        if type(section) is not int or section < 0:
            raise CourseError("RESOURCES_INVALID_SECTION", "Indicá una sección entera positiva.")
        # Abre la sección pedida y extrae su HTML con el índice ya validado como entero.
        course = await self.find_course(course_id)
        url = urljoin(CAMPUS_BASE_URL, f"course/view.php?id={course_id}&section={section}")
        script = SECTION_CONTENT_SCRIPT.replace("__SECTION__", str(section))
        try:
            with fail_after(QUERY_TIMEOUT_SECONDS):
                async with self._session.acquire() as page:
                    await self._open_course(page, url)
                    data = await page.evaluate(script=script)
                    await self.require_session(page)
        except TimeoutError:
            raise CourseError("RESOURCES_TIMEOUT", "Se agotó el tiempo de consulta.") from None
        except LightpandaError as exc:
            raise self.browser_error(exc) from None
        # Debe ser la página de esta materia, accesible y con la sección visible.
        if not isinstance(data, dict) or data.get("present") is not True:
            raise invalid_resources()
        if str(data.get("course_id")) != str(course_id):
            raise CourseError("RESOURCES_ACCESS_DENIED", "La página no es de la asignatura.")
        if data.get("access_denied"):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso al curso.")
        if data.get("found") is not True:
            raise CourseError(
                "RESOURCES_SECTION_NOT_FOUND", "La sección no existe o no es visible."
            )
        return self._section_content(course, section, url, data)

    @staticmethod
    def _section_content(course: Course, section: int, url: str, data: dict) -> SectionContent:
        # Arma la respuesta: un bloque para el resumen de la sección y uno por cada etiqueta o
        # descripción de actividad, cada uno convertido a Markdown.
        blocks: list[ContentBlock] = []
        warnings: list[str] = []
        embeds: list[str] = []

        # Convierte un fragmento y lo agrega si tiene texto o una restricción de acceso visible.
        def add(kind, html, module_id=None, name=None, availability=None) -> None:
            parsed = html_to_markdown(html or "", url)
            embeds.extend(host for host in parsed.embeds if host not in embeds)
            if parsed.truncated:
                warnings.append("CONTENT_TRUNCATED: Un bloque superó el límite de texto.")
            if parsed.text or availability:
                blocks.append(
                    ContentBlock(
                        kind=kind,
                        module_id=module_id,
                        name=name,
                        text=parsed.text,
                        links=parsed.links,
                        availability=availability,
                        truncated=parsed.truncated,
                    )
                )

        # Las etiquetas (label) son texto suelto de la cátedra; el resto son descripciones.
        add("summary", data.get("summary"))
        for row in data.get("activities") or []:
            kind = "label" if "modtype_label" in str(row.get("classes")) else "description"
            add(
                kind,
                row.get("html"),
                integer(row.get("id"), 1),
                row.get("name"),
                row.get("availability"),
            )
        # Avisos de alcance: recortes y contenido embebido que no se leyó.
        if data.get("truncated"):
            warnings.append("CONTENT_TRUNCATED: La sección superó el límite de actividades.")
        if embeds:
            warnings.append(
                "CONTENT_EMBEDS_OMITTED: Hay contenido embebido de " + ", ".join(embeds)
            )
        return SectionContent(
            course=course,
            section_index=section,
            section_name=data.get("name"),
            source_url=url,
            fetched_at=datetime.now(UTC),
            blocks=blocks,
            complete=not warnings,
            warnings=list(dict.fromkeys(warnings)),
        )

    async def get_page_content(self, course_id: int, module_id: int) -> PageContent:
        """Lee un módulo page de la asignatura indicada; no sigue enlaces."""
        return await self._module_text(course_id, module_id, "page", PAGE_CONTENT_SCRIPT)

    async def get_folder_content(self, course_id: int, module_id: int) -> PageContent:
        """Lee la descripción de un módulo folder; sus archivos están en el inventario."""
        return await self._module_text(course_id, module_id, "folder", FOLDER_CONTENT_SCRIPT)

    async def _module_text(
        self, course_id: int, module_id: int, kind: str, script: str
    ) -> PageContent:
        # Lectura común de módulos de texto (page y folder): abre la página del módulo,
        # verifica tipo y materia, y convierte su HTML a Markdown.
        if type(module_id) is not int or module_id <= 0:
            raise CourseError("RESOURCES_INVALID_MODULE", "Indicá un module_id entero positivo.")
        course = await self.find_course(course_id)
        url = urljoin(CAMPUS_BASE_URL, f"mod/{kind}/view.php?id={module_id}")
        try:
            with fail_after(QUERY_TIMEOUT_SECONDS):
                async with self._session.acquire() as page:
                    await self.open_page(page, url)
                    data = await page.evaluate(script=script)
                    await self.require_session(page)
        except TimeoutError:
            raise CourseError("RESOURCES_TIMEOUT", "Se agotó el tiempo de consulta.") from None
        except LightpandaError as exc:
            raise self.browser_error(exc) from None
        if not isinstance(data, dict):
            raise invalid_resources()
        if data.get("access_denied"):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso a la página.")
        if data.get("body") != f"page-mod-{kind}-view" or str(data.get("course_id")) != str(
            course_id
        ):
            raise CourseError(
                "RESOURCES_MODULE_NOT_FOUND", "El módulo no es de ese tipo o de la materia."
            )
        if data.get("html") is None:
            raise invalid_resources()
        parsed = html_to_markdown(data["html"], url)
        warnings = []
        if parsed.truncated:
            warnings.append("CONTENT_TRUNCATED: El módulo superó el límite de texto.")
        if parsed.embeds:
            warnings.append(
                "CONTENT_EMBEDS_OMITTED: Hay contenido embebido de " + ", ".join(parsed.embeds)
            )
        return PageContent(
            course=course,
            module_id=module_id,
            name=data.get("name"),
            source_url=url,
            fetched_at=datetime.now(UTC),
            text=parsed.text,
            links=parsed.links,
            complete=not warnings,
            warnings=warnings,
        )

    @staticmethod
    def browser_error(exc: LightpandaError) -> CourseError:
        # Traduce un fallo de Lightpanda; en el log queda solo el tipo, nunca el mensaje completo.
        if is_rate_limited_message(str(exc)):
            return CourseError("RESOURCES_RATE_LIMITED", "El campus limitó las solicitudes.")
        logger.warning("Fallo del navegador: %s", str(exc).split(":", 1)[0][:60])
        return CourseError("RESOURCES_BROWSER_ERROR", "Lightpanda no pudo completar la consulta.")

    # Como open_page, pero además espera a que cargue el contenido del curso.
    async def _open_course(self, page: AsyncSession, url: str) -> None:
        await self.open_page(page, url)
        await page.wait_for_selector(
            selector="#region-main .course-content", timeout=self._settings.navigation_timeout_ms
        )

    # Navegación segura usada por recursos y foros: solo destinos del campus, estado HTTP
    # clasificado, sesión verificada y espera de la región principal de la página.
    async def open_page(self, page: AsyncSession, url: str) -> None:
        if not same_origin(url, CAMPUS_BASE_URL):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El destino está fuera del campus.")
        result = await page.goto(
            url=url, timeout=self._settings.navigation_timeout_ms, wait_until="domcontentloaded"
        )
        status = result.http_status
        if status == 429:
            raise CourseError("RESOURCES_RATE_LIMITED", "El campus limitó las solicitudes.")
        if status in (401, 403):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso al curso.")
        if status is None or status >= 400:
            raise CourseError("RESOURCES_HTTP_ERROR", "No se pudo cargar la asignatura.")
        await self.require_session(page)
        await page.wait_for_selector(
            selector="#region-main", timeout=self._settings.navigation_timeout_ms
        )

    @staticmethod
    async def require_session(page: AsyncSession) -> None:
        # La página actual debe seguir en el campus, sin límite de solicitudes y con sesión.
        state = await page.evaluate(script=LOGIN_PAGE_STATE_SCRIPT)
        if not isinstance(state, dict):
            raise invalid_resources()
        if not same_origin(str(state.get("url", "")), CAMPUS_BASE_URL):
            raise CourseError("RESOURCES_ACCESS_DENIED", "El navegador salió del campus.")
        if state.get("rate_limited"):
            raise CourseError("RESOURCES_RATE_LIMITED", "El campus limitó las solicitudes.")
        if state.get("authenticated") is not True:
            raise CourseError("RESOURCES_SESSION_EXPIRED", "La sesión dejó de estar activa.")
