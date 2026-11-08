"""Consulta de materias de Grado para MCP y otros servicios académicos."""

import time
from datetime import UTC, datetime

from anyio import fail_after
from lightpanda import LightpandaError

from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import Course, CourseList
from utnfrsf_campus_mcp.parsers.courses import DEGREE_COURSES_SCHEMA, parse_degree_courses
from utnfrsf_campus_mcp.parsers.login import (
    LOGIN_PAGE_STATE_SCRIPT,
    is_rate_limited_message,
    same_origin,
)
from utnfrsf_campus_mcp.services.authentication import AuthenticationService

# Las materias de Grado cambian pocas veces por cuatrimestre: validar un course_id no
# justifica volver a leer la portada en cada herramienta.
COURSES_CACHE_SECONDS = 600


class CourseService:
    def __init__(
        self, settings: Settings, session: CampusSession, authentication: AuthenticationService
    ) -> None:
        self._settings = settings
        self._session = session
        self._authentication = authentication
        self._cached: tuple[float, list[Course]] | None = None

    async def recent_degree_courses(self) -> list[Course]:
        """Reutiliza el último listado de Grado si es reciente; si no, lo vuelve a consultar.

        Siempre confirma la sesión: el navegador se cierra por inactividad y con él las cookies.
        """
        if self._cached is None or time.monotonic() - self._cached[0] > COURSES_CACHE_SECONDS:
            return await self.list_degree_courses()
        await self._authentication.login()
        return list(self._cached[1])

    async def list_courses(self) -> CourseList:
        """Publica el alcance y la procedencia de un listado completo de Grado."""
        courses = await self.list_degree_courses()
        return CourseList(
            source_url=CAMPUS_BASE_URL,
            fetched_at=datetime.now(UTC),
            total=len(courses),
            courses=courses,
        )

    async def list_degree_courses(self) -> list[Course]:
        """Lista My courses → Grado (incluye Sistemas y Básicas) sin expandir ramas ni abrir cursos.

        Conserva el orden de la sidebar y los años disponibles para la cuenta. Es la base
        interna de list_courses y del inventario de recursos; reutiliza Course y la sesión.
        """
        # El login se hace antes de tomar el lock: login() también lo adquiere y no se anida.
        await self._authentication.login()
        try:
            with fail_after(30):
                async with self._session.acquire() as page:
                    # La portada del campus contiene el bloque de navegación con My courses.
                    result = await page.goto(
                        url=CAMPUS_BASE_URL,
                        timeout=self._settings.navigation_timeout_ms,
                        wait_until="domcontentloaded",
                    )
                    # Clasifica la respuesta HTTP antes de leer el contenido.
                    if result.http_status == 429:
                        raise CourseError(
                            "COURSES_RATE_LIMITED", "El campus limitó las solicitudes."
                        )
                    if result.http_status in (401, 403):
                        raise CourseError("COURSES_ACCESS_DENIED", "El campus denegó el acceso.")
                    if result.http_status is None or result.http_status >= 400:
                        raise CourseError("COURSES_HTTP_ERROR", "No se pudo cargar la portada.")
                    # Confirma que seguimos en el campus, sin límite de solicitudes y con sesión.
                    state = await page.evaluate(script=LOGIN_PAGE_STATE_SCRIPT)
                    if not isinstance(state, dict) or not same_origin(
                        str(state.get("url", "")), CAMPUS_BASE_URL
                    ):
                        raise CourseError(
                            "COURSES_ACCESS_DENIED", "No se pudo verificar el origen."
                        )
                    if state.get("rate_limited"):
                        raise CourseError(
                            "COURSES_RATE_LIMITED", "El campus limitó las solicitudes."
                        )
                    if state.get("authenticated") is not True:
                        raise CourseError(
                            "COURSES_SESSION_EXPIRED", "La sesión dejó de estar activa."
                        )
                    # Espera el bloque de navegación, extrae la rama Grado y renueva la caché.
                    await page.wait_for_selector(
                        selector='[data-block="navigation"]',
                        timeout=self._settings.navigation_timeout_ms,
                    )
                    courses = parse_degree_courses(await page.extract(schema=DEGREE_COURSES_SCHEMA))
                    self._cached = (time.monotonic(), courses)
                    return list(courses)
        # Los errores del navegador se reducen a códigos propios; su texto nunca se reenvía.
        except TimeoutError:
            raise CourseError(
                "COURSES_TIMEOUT", "Se agotó el tiempo de consulta de Grado."
            ) from None
        except LightpandaError as exc:
            if is_rate_limited_message(str(exc)):
                raise CourseError(
                    "COURSES_RATE_LIMITED", "El campus limitó las solicitudes. Esperá y reintentá."
                ) from None
            raise CourseError(
                "COURSES_BROWSER_ERROR", "Lightpanda no pudo consultar las asignaturas de Grado."
            ) from None
