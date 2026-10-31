"""Lectura del repositorio del calendario desde la sesión Lightpanda autenticada."""

from lightpanda import AsyncSession

from utnfrsf_campus_mcp.errors import CalendarError
from utnfrsf_campus_mcp.parsers.calendar import invalid_calendar

# Contrato público de core_calendar/repository (Moodle). Se comprueba su presencia
# en el campus en cada llamada. No se construye una petición HTTP con tokens propios.
# La proyección evita devolver HTML, editurl, deleteurl, identidad y sesskey a Python.
_MONTH_SCRIPT = r"""
return await new Promise(resolve => {
    const fail = code => resolve({error: code});
    const cleanLink = raw => {
        if (typeof raw !== 'string') return null;
        try {
            const url = new URL(raw, location.href);
            const ids = url.searchParams.getAll('id');
            if (url.origin !== location.origin || url.username || url.password ||
                ids.length !== 1) {
                return null;
            }
            return url.origin + url.pathname + '?id=' + encodeURIComponent(ids[0]);
        } catch (_) { return null; }
    };
    if (typeof globalThis.require !== 'function') return fail('CALENDAR_API_UNAVAILABLE');
    globalThis.require(['core_calendar/repository'], repository => {
        if (typeof repository?.getCalendarMonthData !== 'function') {
            return fail('CALENDAR_API_UNAVAILABLE');
        }
        Promise.resolve().then(() => repository.getCalendarMonthData(
            __YEAR__, __MONTH__, 1, 0, false, false, 1, 'month'
        )).then(month => {
            try {
                if (!Array.isArray(month?.weeks) || month.weeks.length > 6) {
                    return fail('CALENDAR_FORMAT_UNSUPPORTED');
                }
                let count = 0;
                const weeks = month.weeks.map(week => {
                    if (!Array.isArray(week.days) || week.days.length > 7) throw Error();
                    return {days: week.days.map(day => {
                        if (!Array.isArray(day.events)) throw Error();
                        count += day.events.length;
                        if (count > 10000) throw Error();
                        return {mday: day.mday, year: day.year, timestamp: day.timestamp,
                            hasevents: day.hasevents,
                            events: day.events.map(event => ({
                                id: event.id, name: event.name, activityname: event.activityname,
                                modulename: event.modulename, eventtype: event.eventtype,
                                timestart: event.timestart, timeduration: event.timeduration,
                                url: cleanLink(event.url),
                                action: event.action ? {url: cleanLink(event.action.url)} : null,
                                course: event.course ? {
                                    id: event.course.id, fullname: event.course.fullname
                                } : null
                            }))};
                    })};
                });
                resolve({data: {date: {year: month.date?.year, mon: month.date?.mon},
                    initialeventsloaded: month.initialeventsloaded, courseid: month.courseid,
                    categoryid: month.categoryid, weeks}});
            } catch (_) { fail('CALENDAR_FORMAT_UNSUPPORTED'); }
        }).catch(error => {
            // Solo códigos predefinidos, nunca el mensaje remoto o su stack.
            const code = error?.errorcode;
            if (['invalidsesskey', 'requireloginerror', 'servicerequireslogin'].includes(code)) {
                fail('CALENDAR_SESSION_EXPIRED');
            } else if (['nopermissions', 'accessexception'].includes(code)) {
                fail('CALENDAR_ACCESS_DENIED');
            } else if (error?.status === 429 || error?.statusCode === 429) {
                fail('CALENDAR_RATE_LIMITED');
            } else { fail('CALENDAR_REQUEST_FAILED'); }
        });
    }, () => fail('CALENDAR_API_UNAVAILABLE'));
});
"""

_MESSAGES = {
    "CALENDAR_API_UNAVAILABLE": "El campus no ofrece el repositorio de calendario compatible.",
    "CALENDAR_SESSION_EXPIRED": "La sesión venció. Volvé a ejecutar login antes de consultar.",
    "CALENDAR_ACCESS_DENIED": "La cuenta no tiene permiso para consultar el calendario.",
    "CALENDAR_RATE_LIMITED": "El campus limitó las solicitudes. Esperá antes de reintentar.",
    "CALENDAR_REQUEST_FAILED": "El campus no completó la consulta. No se devolvió un mes vacío.",
}


async def read_calendar_month(page: AsyncSession, year: int, month: int, wait_ms: int) -> dict:
    """Una consulta de lectura para todo el mes, incluidos eventos plegados en el HTML."""
    script = _MONTH_SCRIPT.replace("__YEAR__", str(year)).replace("__MONTH__", str(month))
    response = await page.evaluate(script=script, timeout=wait_ms)
    if not isinstance(response, dict):
        raise invalid_calendar()
    if "error" in response:
        code = response["error"]
        if isinstance(code, str) and code in _MESSAGES:
            raise CalendarError(code, _MESSAGES[code])
        raise invalid_calendar()
    data = response.get("data")
    if not isinstance(data, dict):
        raise invalid_calendar()
    return data
