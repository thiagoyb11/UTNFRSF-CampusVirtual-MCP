# Actividades del mes

La herramienta MCP `list_monthly_activities` consulta las actividades que aparecen en el calendario de la cuenta. Se autentica con el `.env` privado y comparte la sesión de `login`. No requiere llamar a `login` previamente.

## Probar en Inspector

Iniciá Inspector desde la raíz del repositorio con Python global:

```bash
npx --yes @modelcontextprotocol/inspector /opt/homebrew/bin/python3 -m utnfrsf_campus_mcp
```

Conectate, abrí **Tools** y seleccioná **list_monthly_activities**. Para el mes actual usá `{}`. Para elegir un mes:

```json
{"year": 2026, "month": 10}
```

Para obtener solamente vencimientos y cierres:

```json
{"year": 2026, "month": 10, "deadlines_only": true}
```

`year` y `month` se indican juntos o se omiten ambos. Los rangos son 1970–9998 y 1–12. Sin argumentos, el mes se determina en la zona horaria de la cuenta del campus, no en UTC.

## JSON de salida

Ejemplo ilustrativo con datos ficticios y una actividad:

```json
{
  "year": 2026,
  "month": 10,
  "timezone": "America/Argentina/Buenos_Aires",
  "timezone_source": "campus",
  "deadlines_only": false,
  "source_url": "https://campusvirtual.frsf.utn.edu.ar/calendar/view.php?view=month&time=1790823600",
  "fetched_at": "2026-10-31T15:00:00Z",
  "total": 1,
  "activities": [
    {
      "event_id": 100,
      "activity_id": 200,
      "name": "Trabajo práctico de ejemplo",
      "event_name": "Vencimiento del trabajo práctico de ejemplo",
      "module": "assign",
      "event_type": "due",
      "starts_at": "2026-10-20T23:59:00-03:00",
      "ends_at": null,
      "deadline_at": "2026-10-20T23:59:00-03:00",
      "deadline_kind": "due",
      "course": {
        "id": 300,
        "name": "Asignatura de ejemplo",
        "url": "https://campusvirtual.frsf.utn.edu.ar/course/view.php?id=300"
      },
      "activity_url": "https://campusvirtual.frsf.utn.edu.ar/mod/assign/view.php?id=200",
      "calendar_url": "https://campusvirtual.frsf.utn.edu.ar/calendar/view.php?view=day&course=300&time=1792551540#event_100"
    }
  ],
  "warnings": [
    "El calendario no confirma si una actividad está entregada o pendiente. Solo incluye eventos visibles para la cuenta y sus filtros del campus."
  ]
}
```

- `deadline_kind: "due"` indica vencimiento; `"close"`, un evento de cierre. No se confunde el vencimiento con el cierre definitivo de entregas que una actividad podría configurar por separado.
- Las aperturas, asistencias y otros eventos mantienen su `event_type`, con `deadline_at` y `deadline_kind` en `null`. Los intervalos incluyen `ends_at`; se incluyen si se superponen con el mes.
- Un mismo módulo puede tener varios eventos de apertura, vencimiento o cierre. Se conserva cada evento y se eliminan sus repeticiones entre días por `event_id`.
- Se devuelven eventos de todo el mes, incluso los pasados. No se consulta el estado de entrega ni se deduce que un evento sea un trabajo pendiente. Actividades sin evento de calendario quedan fuera del alcance.
- Si la zona del campus no es IANA o falta, se usa `UTN_CAMPUS_TIMEZONE`, se marca `timezone_source: "configuration"` y se agrega una advertencia.

## Extracción y enlaces

Lightpanda abre `/my/` y comprueba autenticación y el bloque `[data-block="calendar_month"] .calendarwrapper` observado en la inspección. Desde esa misma página utiliza el módulo JavaScript `core_calendar/repository`, comprobando que exista `getCalendarMonthData`. La llamada pide el calendario general (`courseid=1`, observado en este campus), un mes completo y la vista `month`.

Se leen `timestart`, `timeduration`, `eventtype`, `modulename`, `course` y `url`. No se interpretan fechas traducidas ni se buscan botones por sus etiquetas. El acceso también selecciona el botón submit dentro del formulario verificado, sin depender del texto “Acceder”.

El enlace del calendario puede abrir un popup. `activity_url` usa el enlace del módulo incluido en los datos del evento; evita tener que buscar o pulsar “Go to activity”. Como alternativa se acepta el enlace de acción si apunta al mismo módulo. Se valida origen, ruta e ID, y se conserva únicamente `/mod/<módulo>/view.php?id=<id>`. No se devuelve `action=editsubmission`, tokens ni URLs de edición/eliminación. La consulta no abre ni envía una entrega.

Se comprueban todos los días del mes y `initialeventsloaded` antes de devolver resultados. Una carga parcial, un enlace ausente, una sesión vencida o un formato inesperado produce un error MCP; no se devuelve una lista vacía como si fuera un mes sin actividades. Se limita la consulta a 1000 eventos únicos, 10000 apariciones entre días y 60 segundos después de autenticar. No hay reintentos de la consulta mensual; los reintentos de login mantienen su política propia.

Los errores incluyen `CALENDAR_INVALID_MONTH`, `CALENDAR_SESSION_EXPIRED`, `CALENDAR_ACCESS_DENIED`, `CALENDAR_API_UNAVAILABLE`, `CALENDAR_FORMAT_UNSUPPORTED`, `CALENDAR_ACTIVITY_LINK_MISSING`, `CALENDAR_RATE_LIMITED` y `CALENDAR_BROWSER_ERROR`. La disponibilidad del módulo y la forma del resultado se validan en cada llamada; no hay fallback a otro navegador ni a fechas deducidas del texto.

## Evidencia y validación real

La implementación aprovecha la [estructura observada del campus](estructura-campus.md) y el contrato documentado en el código oficial de Moodle: [repositorio del calendario](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/calendar/amd/src/repository.js), [datos de eventos y tiempos](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/calendar/classes/external/event_exporter_base.php), [enlace directo al módulo](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/calendar/classes/external/calendar_event_exporter.php) y [vista mensual](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/calendar/classes/external/month_exporter.php). Además de esas referencias, se confirmó la disponibilidad de `core_calendar/repository` y su contrato al ejecutar la consulta en el campus real.

**Validación real: 31 de octubre de 2026, con Lightpanda y la cuenta configurada en `.env`.** La llamada mediante el cliente MCP devolvió 33 eventos de actividad de octubre: 15 asistencias, 9 vencimientos, 5 aperturas y 4 cierres, de 5 asignaturas. También funcionaron la consulta sin mes explícito y `deadlines_only=true`, que devolvió los mismos 13 eventos de vencimiento o cierre presentes en la consulta completa. La zona informada por el campus fue `America/Argentina/Buenos_Aires`.

Se abrió un popup de vencimiento desde el calendario mensual y se cotejó su enlace con el `activity_url` del JSON: coincidieron ruta e ID de módulo. El modal real usa `[data-region="modal-container"][role="dialog"]` y `[data-region="footer"] a[href]`. Para abrirlo con un clic es necesario esperar a que carguen los módulos JavaScript del calendario; la herramienta evita esa dependencia leyendo el enlace desde el evento. No se pulsó el enlace de entrega ni se modificaron actividades.

Una consulta real recibió `CALENDAR_REQUEST_FAILED`; las ejecuciones posteriores completaron la lectura. El fallo no se convirtió en una lista vacía y la herramienta mantiene su política de no reintentar automáticamente la consulta mensual. Las cantidades anteriores describen una cuenta y un momento concretos; no son valores fijos ni prueban el estado de las entregas.

La restricción del sandbox que había impedido iniciar Lightpanda se resolvió al cambiar los permisos de la sesión. Los resultados JSON y diagnósticos reales permanecen en `.local/`, fuera de Git.
