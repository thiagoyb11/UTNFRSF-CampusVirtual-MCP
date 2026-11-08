"""Calendario independiente del idioma; contrato Moodle validado antes de normalizar."""

import calendar
import re
from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import CalendarError
from utnfrsf_campus_mcp.models import CalendarActivity, Course
from utnfrsf_campus_mcp.parsers.login import same_origin

# Atributos observados en /my/. No se consultan etiquetas traducidas ni valores de inputs.
CALENDAR_CONTEXT_SCRIPT = r"""(() => {
    const wrapper = document.querySelector('[data-block="calendar_month"] .calendarwrapper');
    return {url: location.href, timezone: globalThis.M?.cfg?.usertimezone,
        course_id: wrapper?.getAttribute('data-courseid')};
})()"""


# Error genérico de formato: cualquier dato inesperado invalida el mes entero, para no
# devolver un calendario incompleto como si estuviera completo.
def invalid_calendar() -> CalendarError:
    return CalendarError(
        "CALENDAR_FORMAT_UNSUPPORTED",
        "No se pudo verificar el calendario completo. El formato del campus puede haber cambiado.",
    )


def resolve_timezone(value: Any, fallback: str) -> tuple[ZoneInfo, str]:
    # Usa la zona del perfil del campus si es válida; si no, la configurada, e informa cuál.
    if isinstance(value, str):
        try:
            return ZoneInfo(value), "campus"
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo(fallback), "configuration"


def month_bounds(year: int, month: int, zone: ZoneInfo) -> tuple[datetime, datetime]:
    # Intervalo [inicio del mes, inicio del mes siguiente); diciembre pasa a enero del año próximo.
    start = datetime(year, month, 1, tzinfo=zone)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=zone)
    return start, end


# Validadores estrictos de los campos de Moodle: enteros reales (no bool ni str) y textos no vacíos.
def _integer(value: Any, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise invalid_calendar()
    return value


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise invalid_calendar()
    # Moodle puede devolver nombres formateados con HTML; nunca se exponen como markup.
    return unescape(re.sub(r"<[^>]*>", "", value)).strip()


def activity_link(raw: Any, module: str) -> tuple[str, int] | None:
    """Acepta enlaces reales del módulo; conserva solo su ID, sin acciones ni tokens."""
    if not isinstance(raw, str) or not raw:
        return None
    # Debe ser mod/<módulo>/view.php del campus con un único id numérico; se reconstruye
    # limpia para descartar parámetros extra.
    url = urljoin(CAMPUS_BASE_URL, unescape(raw))
    if not same_origin(url, CAMPUS_BASE_URL):
        return None
    parts = urlsplit(url)
    if parts.path != f"/mod/{module}/view.php":
        return None
    ids = parse_qs(parts.query).get("id", [])
    if len(ids) != 1 or not ids[0].isascii() or not ids[0].isdigit() or int(ids[0]) <= 0:
        return None
    module_id = int(ids[0])
    return urljoin(CAMPUS_BASE_URL, f"mod/{module}/view.php?id={module_id}"), module_id


def parse_month(
    payload: Any, year: int, month: int, zone: ZoneInfo, *, deadlines_only: bool
) -> list[CalendarActivity]:
    """Exige todos los días del mes y eventos cargados; deduplica eventos de varios días."""
    # 1. La respuesta debe ser del mes pedido y con los eventos ya cargados.
    if not isinstance(payload, dict) or payload.get("initialeventsloaded") is not True:
        raise invalid_calendar()
    date = payload.get("date")
    if not isinstance(date, dict) or (date.get("year"), date.get("mon")) != (year, month):
        raise invalid_calendar()
    # El contrato solicita el calendario general, nunca una materia o categoría particular.
    if payload.get("courseid") != 1 or payload.get("categoryid", 0) not in (0, None):
        raise invalid_calendar()
    weeks = payload.get("weeks")
    if not isinstance(weeks, list) or not 4 <= len(weeks) <= 6:
        raise invalid_calendar()
    # 2. Recorre semanas y días: cada día del mes debe aparecer una sola vez y su timestamp
    #    debe corresponder a esa fecha. Un evento de varios días aparece repetido; se guarda
    #    una sola vez y se exige que sus datos esenciales coincidan en todas las copias.
    days: set[int] = set()
    events: dict[int, dict] = {}
    occurrences = 0
    for week in weeks:
        if not isinstance(week, dict) or not isinstance(week.get("days"), list):
            raise invalid_calendar()
        for day in week["days"]:
            if not isinstance(day, dict):
                raise invalid_calendar()
            number = _integer(day.get("mday"), 1)
            if day.get("year") != year or number in days:
                raise invalid_calendar()
            try:
                day_date = datetime.fromtimestamp(_integer(day.get("timestamp"), 1), zone)
            except (ValueError, OverflowError, OSError):
                raise invalid_calendar() from None
            if (day_date.year, day_date.month, day_date.day) != (year, month, number):
                raise invalid_calendar()
            days.add(number)
            items = day.get("events")
            if not isinstance(items, list) or day.get("hasevents") is not bool(items):
                raise invalid_calendar()
            occurrences += len(items)
            if occurrences > 10_000:
                raise CalendarError(
                    "CALENDAR_LIMIT_EXCEEDED", "El mes supera el límite de eventos."
                )
            for item in items:
                if not isinstance(item, dict):
                    raise invalid_calendar()
                event_id = _integer(item.get("id"), 1)
                if event_id in events:
                    # Los campos decorativos (islastday, popupname) cambian entre días.
                    for key in (
                        "timestart",
                        "timeduration",
                        "eventtype",
                        "modulename",
                        "url",
                        "course",
                    ):
                        if item.get(key) != events[event_id].get(key):
                            raise invalid_calendar()
                else:
                    events[event_id] = item
    # 3. Tienen que haber llegado todos los días del mes, sin faltantes.
    if days != set(range(1, calendar.monthrange(year, month)[1] + 1)):
        raise invalid_calendar()
    if len(events) > 1000:
        raise CalendarError("CALENDAR_LIMIT_EXCEEDED", "El mes supera el límite de 1000 eventos.")
    # 4. Convierte cada evento vinculado a una actividad en un CalendarActivity.
    start, end = month_bounds(year, month, zone)
    result = []
    for event in events.values():
        module = event.get("modulename")
        if module in (None, ""):
            # Eventos personales, de sitio o de curso sin actividad vinculada.
            continue
        if not isinstance(module, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", module):
            raise invalid_calendar()
        # Inicio y fin en la zona del campus.
        timestamp = _integer(event.get("timestart"), 1)
        duration = _integer(event.get("timeduration"))
        try:
            starts_at = datetime.fromtimestamp(timestamp, zone)
            ends_at = datetime.fromtimestamp(timestamp + duration, zone)
        except (ValueError, OverflowError, OSError):
            raise invalid_calendar() from None
        # Solo los eventos "due" (vencimiento) y "close" (cierre) son fechas límite.
        event_type = _text(event.get("eventtype"))
        deadline_kind = event_type if event_type in ("due", "close") else None
        if deadline_kind and duration:
            # No asumir dónde cae el límite si un plugin usa un intervalo para due/close.
            raise invalid_calendar()
        deadline_at = starts_at if deadline_kind else None
        # Un intervalo académico pertenece al mes si se superpone; los deadlines por instante.
        if duration:
            belongs = starts_at < end and ends_at > start
        else:
            belongs = start <= starts_at < end
        if not belongs or (deadlines_only and deadline_at is None):
            continue
        # Enlace a la actividad: primero el del evento, si no, el de su acción. Sin ninguno,
        # se falla en lugar de omitir el evento en silencio.
        resolved = activity_link(event.get("url"), module)
        if resolved is None:
            action = event.get("action")
            resolved = activity_link(
                action.get("url") if isinstance(action, dict) else None, module
            )
        if resolved is None:
            raise CalendarError(
                "CALENDAR_ACTIVITY_LINK_MISSING",
                "Un evento no tiene un enlace verificable a su actividad. "
                "No se omitió en silencio.",
            )
        url, module_id = resolved
        course = event.get("course")
        if not isinstance(course, dict):
            raise invalid_calendar()
        course_id = _integer(course.get("id"), 1)
        # Enlace a la vista diaria del calendario, anclado al evento.
        calendar_url = (
            urljoin(
                CAMPUS_BASE_URL,
                "calendar/view.php?"
                + urlencode({"view": "day", "course": course_id, "time": timestamp}),
            )
            + f"#event_{event['id']}"
        )
        result.append(
            CalendarActivity(
                event_id=event["id"],
                activity_id=module_id,
                name=_text(event.get("activityname") or event.get("name")),
                event_name=_text(event.get("name")),
                module=module,
                event_type=event_type,
                starts_at=starts_at,
                ends_at=ends_at if duration else None,
                deadline_at=deadline_at,
                deadline_kind=deadline_kind,
                course=Course(
                    id=course_id,
                    name=_text(course.get("fullname")),
                    url=urljoin(CAMPUS_BASE_URL, f"course/view.php?id={course_id}"),
                ),
                activity_url=url,
                calendar_url=calendar_url,
            )
        )
    # Orden cronológico estable: por inicio y, ante empate, por id de evento.
    return sorted(result, key=lambda event: (event.starts_at.timestamp(), event.event_id))
