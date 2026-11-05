"""Consulta mensual de actividades de todas las asignaturas visibles para la cuenta."""

from datetime import UTC, datetime
from urllib.parse import urljoin

from anyio import fail_after
from lightpanda import AsyncSession, LightpandaError

from utnfrsf_campus_mcp.browser.calendar import read_calendar_month
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import CalendarError
from utnfrsf_campus_mcp.models import MonthlyActivities
from utnfrsf_campus_mcp.parsers.calendar import (
    CALENDAR_CONTEXT_SCRIPT,
    invalid_calendar,
    month_bounds,
    parse_month,
    resolve_timezone,
)
from utnfrsf_campus_mcp.parsers.login import (
    LOGIN_PAGE_STATE_SCRIPT,
    is_rate_limited_message,
    same_origin,
)
from utnfrsf_campus_mcp.services.authentication import AuthenticationService


class CalendarService:
    def __init__(
        self, settings: Settings, session: CampusSession, authentication: AuthenticationService
    ) -> None:
        self._settings = settings
        self._session = session
        self._authentication = authentication

    async def list_monthly_activities(
        self, year: int | None = None, month: int | None = None, deadlines_only: bool = False
    ) -> MonthlyActivities:
        # También se valida al invocar el servicio directamente, antes de acceder a la red.
        if (year is None) != (month is None) or (
            year is not None
            and (
                type(year) is not int
                or not 1970 <= year <= 9998
                or type(month) is not int
                or not 1 <= month <= 12
            )
        ):
            raise CalendarError(
                "CALENDAR_INVALID_MONTH",
                "Indicá year (1970–9998) y month (1–12) juntos, u omití ambos.",
            )
        # El login y la consulta comparten el mismo lock; nunca se adquiere recursivamente.
        await self._authentication.login()
        try:
            with fail_after(60):
                async with self._session.acquire() as page:
                    result = await page.goto(
                        url=urljoin(CAMPUS_BASE_URL, "my/"),
                        timeout=self._settings.navigation_timeout_ms,
                        wait_until="domcontentloaded",
                    )
                    self._check_http(result.http_status)
                    await self._require_session(page)
                    await page.wait_for_selector(
                        selector='[data-block="calendar_month"] .calendarwrapper',
                        timeout=self._settings.navigation_timeout_ms,
                    )
                    context = await page.evaluate(script=CALENDAR_CONTEXT_SCRIPT)
                    if not isinstance(context, dict) or context.get("course_id") != "1":
                        raise invalid_calendar()
                    if not same_origin(str(context.get("url", "")), CAMPUS_BASE_URL):
                        raise CalendarError(
                            "CALENDAR_ACCESS_DENIED", "El navegador salió del campus."
                        )
                    zone, zone_source = resolve_timezone(
                        context.get("timezone"), self._settings.timezone
                    )
                    now = datetime.now(zone)
                    year = now.year if year is None else year
                    month = now.month if month is None else month
                    payload = await read_calendar_month(
                        page, year, month, self._settings.navigation_timeout_ms
                    )
                    await self._require_session(page)
                    activities = parse_month(
                        payload, year, month, zone, deadlines_only=deadlines_only
                    )
                    start, _ = month_bounds(year, month, zone)
                    warnings = [
                        "El calendario no confirma si una actividad está entregada o pendiente. "
                        "Solo incluye eventos visibles para la cuenta y sus filtros del campus."
                    ]
                    if zone_source == "configuration":
                        warnings.append(
                            "El campus no informó una zona IANA; se usó la configurada."
                        )
                    return MonthlyActivities(
                        year=year,
                        month=month,
                        timezone=zone.key,
                        timezone_source=zone_source,
                        deadlines_only=deadlines_only,
                        source_url=urljoin(
                            CAMPUS_BASE_URL,
                            f"calendar/view.php?view=month&time={int(start.timestamp())}",
                        ),
                        fetched_at=datetime.now(UTC),
                        total=len(activities),
                        activities=activities,
                        warnings=warnings,
                    )
        except TimeoutError:
            raise CalendarError(
                "CALENDAR_TIMEOUT", "Se agotó el tiempo de consulta del mes."
            ) from None
        except LightpandaError as exc:
            if is_rate_limited_message(str(exc)):
                raise CalendarError(
                    "CALENDAR_RATE_LIMITED", "El campus limitó las solicitudes. Esperá y reintentá."
                ) from None
            raise CalendarError(
                "CALENDAR_BROWSER_ERROR", "Lightpanda no pudo completar la consulta mensual."
            ) from None

    @staticmethod
    def _check_http(status: int | None) -> None:
        if status == 429:
            raise CalendarError("CALENDAR_RATE_LIMITED", "El campus limitó las solicitudes.")
        if status in (401, 403):
            raise CalendarError(
                "CALENDAR_ACCESS_DENIED", "El campus denegó el acceso al calendario."
            )
        if status is None or status >= 400:
            raise CalendarError(
                "CALENDAR_HTTP_ERROR", "No se pudo cargar el calendario del campus."
            )

    @staticmethod
    async def _require_session(page: AsyncSession) -> None:
        state = await page.evaluate(script=LOGIN_PAGE_STATE_SCRIPT)
        if not isinstance(state, dict):
            raise invalid_calendar()
        if not same_origin(str(state.get("url", "")), CAMPUS_BASE_URL):
            raise CalendarError("CALENDAR_ACCESS_DENIED", "El navegador salió del campus.")
        if state.get("rate_limited"):
            raise CalendarError("CALENDAR_RATE_LIMITED", "El campus limitó las solicitudes.")
        if state.get("authenticated") is not True:
            raise CalendarError(
                "CALENDAR_SESSION_EXPIRED", "La sesión no está autenticada. Volvé a ejecutar login."
            )
