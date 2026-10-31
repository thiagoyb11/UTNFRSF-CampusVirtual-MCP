# Estructura autenticada del Campus Virtual UTN FRSF

## Alcance de la inspección

Inspección realizada el **31 de octubre de 2026**, con **Lightpanda 1.0.2**, Python global y una cuenta autorizada en el campus real. Se inició sesión, se visitaron la portada, el Dashboard, el calendario y dos asignaturas. Se verificaron esquemas de extracción contra esas páginas.

Este documento es una referencia para implementar consultas y construir llamadas al MCP nativo de Lightpanda. Todavía no implementa herramientas de materias o calendario. Los fragmentos HTML están simplificados y anonimizados; los identificadores entre `<...>` se obtienen del DOM en cada consulta.

Se contrastaron **Sistemas y Procesos de Negocio** y **Bases de Datos No SQL**. Ambas páginas usan `format-topics`; se comprobó el mismo patrón de secciones y actividades, con contenidos y cantidades diferentes. No se presupone que todos los cursos utilicen ese formato.

## Hallazgo principal: portada y Dashboard son páginas distintas

| Página | Ruta | Identificación observada | Contenido de interés |
| --- | --- | --- | --- |
| Portada | `/` | `body#page-site-index` | Árbol de materias en el bloque de navegación. |
| Dashboard | `/my/` | `body#page-my-index` | Calendario mensual, próximos eventos y Timeline. |
| Calendario | `/calendar/view.php?view=upcoming` | `body#page-calendar-view` | Eventos con materia, tipo y enlaces a la actividad. |
| Asignatura | `/course/view.php?id=<course_id>` | `body#page-course-view-topics` | Secciones, recursos y actividades de una materia. |

En la portada inspeccionada **no estaba el widget de calendario**. Para combinar materias y fechas hay que leer la portada y luego `/my/`, manteniendo la misma sesión. La ruta `/calendar/view.php` abrió próximos eventos en esta cuenta; para no depender de preferencias, usar el enlace observado con `view=upcoming`.

El tema observado es Adaptable (`theme_adaptable`). Lightpanda mostró varios rótulos de interfaz en inglés aunque los cursos y actividades tengan títulos en español. Priorizar clases y `data-*` frente a textos como “Navigation”, “Calendar” o “Upcoming events”.

## Convenciones para las llamadas

Los ejemplos presuponen **una sesión ya autenticada en la misma instancia de Lightpanda**. El `login()` del MCP del campus y un proceso independiente iniciado con `lightpanda mcp` no comparten automáticamente sus cookies. La inspección se hizo con el servicio de login y las operaciones del SDK sobre la misma `CampusSession`.

En Inspector, seleccionar la herramienta indicada y completar sus argumentos. Los nombres nativos usan camelCase (`waitForSelector`, `findElement`, `nodeDetails`, `maxBytes`); el SDK de Python ofrece sus equivalentes snake_case.

**`extract.schema` es un string en el MCP nativo.** En las secciones de extracción, el bloque JSON es el contenido que se pega como texto en ese campo. No es un JSON Schema con `type` y `properties`. En Python, `page.extract(schema=un_diccionario)` hace la conversión; con un cliente MCP genérico se usa:

```python
await client.call_tool("extract", {"schema": json.dumps(schema)})
```

Los esquemas siguientes fueron ejecutados mediante el SDK contra el campus real. Los resultados incluyen strings o `null`; convertir IDs y fechas en la capa de servicio. `"selector": ""` dentro de `fields` referencia al elemento que representa el registro.

## 1. Sidebar y listado de materias

### HTML observado

```html
<aside id="block-region-side-post" class="block-region">
  <section class="block_navigation block" data-block="navigation" role="navigation">
    <div class="content">
      <ul class="block_tree list" role="tree">
        <!-- ramas de categoría, carrera y año -->
        <li class="type_course depth_6 contains_branch" role="treeitem" aria-expanded="false">
          <p class="tree_item branch" id="expandable_branch_20_<course_id>">
            <a href="https://campusvirtual.frsf.utn.edu.ar/course/view.php?id=<course_id>">
              Nombre de la asignatura
            </a>
          </p>
        </li>
      </ul>
    </div>
  </section>
</aside>
```

El bloque también se relaciona con el drawer `#theme_adaptable-drawers-sidepost`. Usar `[data-block="navigation"]` como raíz de extracción para no depender de su posición visual.

### Selectores comprobados

| Elemento | Selector |
| --- | --- |
| Bloque | `[data-block="navigation"]` |
| Árbol | `[data-block="navigation"] ul.block_tree[role="tree"]` |
| Materia | `[data-block="navigation"] li.type_course` |
| Enlace de materia | `[data-block="navigation"] li.type_course > p.tree_item > a[href*="/course/view.php"]` |

Los IDs `random..._label...`, `random..._group`, la profundidad `depth_N` y los `backendNodeId` no deben fijarse en el código. Algunas ramas estaban colapsadas (`aria-expanded="false"`), pero sus enlaces ya estaban en el DOM: la extracción no necesitó expandirlas.

### Secuencia de lectura

Herramienta **`goto`**, argumentos:

```json
{
  "url": "https://campusvirtual.frsf.utn.edu.ar/",
  "waitUntil": "domcontentloaded",
  "timeout": 20000
}
```

Herramienta **`waitForSelector`**, argumentos:

```json
{
  "selector": "[data-block=\"navigation\"] li.type_course > p.tree_item > a[href*=\"/course/view.php\"]",
  "timeout": 10000
}
```

Herramienta **`extract`**, contenido del campo `schema`:

```json
{
  "courses": [
    {
      "selector": "[data-block=\"navigation\"] li.type_course > p.tree_item > a[href*=\"/course/view.php\"]",
      "fields": {
        "name": "",
        "url": {
          "selector": "",
          "attr": "href"
        }
      }
    }
  ]
}
```

Se obtuvieron **35 materias** con el selector específico en esta cuenta. Buscar todos los enlaces `/course/view.php` de la página devolvía además un enlace de otro bloque sin texto, por lo que no equivale a leer la sidebar. El árbol incluye cursos de distintos años; no asumir que todos son del período actual.

El `course_id` se obtiene del parámetro `id` de cada URL, no de un ID aleatorio del árbol. Deduplicar por ese identificador si una vista agrega enlaces repetidos.

Para entrar en una materia, el `click` sobre su enlace se comprobó en el campus real. También se puede usar `goto` con el `url` extraído. Un selector reutilizable, después de resolver un ID, es:

```css
[data-block="navigation"] li.type_course > p.tree_item > a[href*="/course/view.php?id=<course_id>"]
```

## 2. Dashboard: tres componentes distintos

En `/my/` se observaron:

| Componente | Selector | Uso |
| --- | --- | --- |
| Próximos eventos | `[data-block="calendar_upcoming"]` | Lista resumida de eventos cercanos. |
| Calendario mensual | `[data-block="calendar_month"]` | Días y eventos del mes mostrado. |
| Timeline | `[data-block="timeline"]` | Vista dinámica de actividades que requieren acción. |

Para navegar, usar `goto` con `url` igual a `https://campusvirtual.frsf.utn.edu.ar/my/`. Después esperar el componente requerido; la presencia del bloque no garantiza que todas sus partes dinámicas hayan terminado de cargar.

### Próximos eventos

HTML resumido:

```html
<section class="block_calendar_upcoming block" data-block="calendar_upcoming">
  <div class="content">
    <div class="calendarwrapper">
      <div class="event" data-region="event-item" data-eventtype-course="1">
        <div class="overflow-auto">
          <h4>
            <a data-action="view-event" data-type="event" data-event-id="<event_id>"
               href="/calendar/view.php?view=day&course=<course_id>&time=<timestamp>#event_<event_id>">
              Nombre del evento
            </a>
          </h4>
          <div class="date small"><a href="/calendar/view.php?view=day&time=<timestamp>">Fecha</a></div>
        </div>
      </div>
    </div>
  </div>
</section>
```

Selector del registro: `[data-block="calendar_upcoming"] [data-region="event-item"]`. Se verificaron **9 eventos** en esta visita. `extract`, contenido de `schema`:

```json
{
  "events": [
    {
      "selector": "[data-block=\"calendar_upcoming\"] [data-region=\"event-item\"]",
      "fields": {
        "title": "a[data-action=\"view-event\"]",
        "event_id": {
          "selector": "a[data-action=\"view-event\"]",
          "attr": "data-event-id"
        },
        "url": {
          "selector": "a[data-action=\"view-event\"]",
          "attr": "href"
        },
        "date_label": ".date",
        "date_urls": [
          {
            "selector": ".date a",
            "attr": "href"
          }
        ]
      }
    }
  ]
}
```

Conservar `date_label` y todos los `date_urls`. En eventos con duración, el enlace del título y el de la fecha no siempre llevaban el mismo `time`; no reducirlos automáticamente a una única fecha de vencimiento. El enlace del título también permite resolver el curso y el `event_id`.

El footer contiene `.gotocal a` hacia `/calendar/view.php?view=upcoming`. Esa es una ruta observada para pasar de la lista resumida al calendario detallado.

### Calendario mensual

Raíz: `[data-block="calendar_month"] [data-region="calendar"]`.

```html
<div class="calendarwrapper" data-view="monthblock"
     data-month="<month>" data-year="<year>" data-courseid="1">
  <div class="calendar-controls">
    <a class="arrow_link previous" data-month="<previous_month>" href="/calendar/view.php?view=month&time=<timestamp>">...</a>
    <a class="arrow_link next" data-month="<next_month>" href="/calendar/view.php?view=month&time=<timestamp>">...</a>
  </div>
  <table class="calendarmonth calendartable">
    <td class="day hasevent" data-region="day" data-day="<day>" data-day-timestamp="<timestamp>">
      <div data-region="day-content">
        <ul>
          <li data-region="event-item" data-event-component="mod_assign" data-event-eventtype="due">
            <a data-action="view-event" data-event-id="<event_id>" href="/mod/assign/view.php?id=<module_id>">
              <span class="eventname">Nombre del evento</span>
            </a>
          </li>
          <li data-action="view-more-events">...</li>
        </ul>
      </div>
    </td>
  </table>
</div>
```

Los tipos del ejemplo se completan con los atributos de cada evento: también se observaron eventos de asistencia. No todos son tareas o entregas pendientes.

| Dato | Selector o atributo |
| --- | --- |
| Mes y año | `.calendarwrapper[data-month][data-year]` dentro del bloque |
| Días con eventos | `td[data-region="day"].hasevent` |
| Evento de un día | `[data-region="event-item"] a[data-action="view-event"]` |
| Hay más eventos | `[data-action="view-more-events"]` |
| Mes anterior/siguiente | `.calendar-controls a.previous` / `.calendar-controls a.next` |
| Filtro de curso | `select[name="course"].cal_courses_flt` |

`data-day-timestamp` representa el día; **no es la fecha exacta de cada evento**. Los enlaces de día con `data-action="view-day-link"` tenían un `href` `#`: requieren el manejador de la interfaz. Para navegar por URL, extraer el enlace de un evento o los enlaces reales de mes.

Se observaron **19 días con eventos** en el mes mostrado. Esquema verificado:

```json
{
  "days": [
    {
      "selector": "[data-block=\"calendar_month\"] td[data-region=\"day\"].hasevent",
      "fields": {
        "day": {
          "selector": "",
          "attr": "data-day"
        },
        "day_timestamp": {
          "selector": "",
          "attr": "data-day-timestamp"
        },
        "events": [
          {
            "selector": "[data-region=\"event-item\"] a[data-action=\"view-event\"]",
            "fields": {
              "name": ".eventname",
              "event_id": {
                "selector": "",
                "attr": "data-event-id"
              },
              "url": {
                "selector": "",
                "attr": "href"
              }
            }
          }
        ]
      }
    }
  ]
}
```

Si aparece “más”, la cuadrícula puede estar resumiendo los eventos. El calendario mensual tampoco representa solo fechas futuras: incluye días pasados del mes. No usar su cantidad como total de pendientes.

Los selectores del filtro y de las flechas se inspeccionaron; sus cambios interactivos no se ejecutaron en esta revisión. Para cambiar mes mediante `goto`, utilizar el `href` obtenido del control, sin inventar timestamps. El valor observado para “todos los cursos” fue `1`; conviene leer las opciones en cada sesión en vez de asumir `0`.

### Timeline: no confundir el HTML inicial con un resultado vacío

Se observaron estos nodos:

```css
[data-block="timeline"] [data-region="event-list-container"]
[data-block="timeline"] [data-region="event-list-loading-placeholder"]
[data-block="timeline"] [data-region="event-list-content"]
[data-block="timeline"] [data-region="no-events-empty-message"]
```

El contenedor tenía `data-days-offset`, `data-days-limit` y `data-midnight`. La vista por cursos usaba `[data-region="view-courses"]` con `data-limit` y `data-offset`.

En el DOM inspeccionado, `event-list-content` estaba vacío, seguía existiendo el placeholder y los mensajes “No activities require action” tenían la clase `hidden`. Por lo tanto, **no se verificó una lista de tareas de Timeline ya cargada ni la ausencia de tareas pendientes**. Leer el texto completo del bloque habría incluido esos mensajes ocultos y permitido una conclusión errónea. Falta comprobar su carga dinámica antes de implementar un parser de Timeline.

Para la primera consulta de fechas, los eventos de calendario son una fuente ya comprobada. Para afirmar que una actividad requiere acción, habrá que verificar además su estado; un evento del calendario no prueba por sí solo que el trabajo esté sin entregar.

## 3. Calendario detallado y clasificación de vencimientos

`goto`, argumentos:

```json
{
  "url": "https://campusvirtual.frsf.utn.edu.ar/calendar/view.php?view=upcoming",
  "timeout": 20000
}
```

Esperar `#region-main .event[data-event-id]` cuando existan eventos. Una espera agotada no demuestra que la lista esté vacía: revisar primero autenticación, vista cargada y mensajes de la página.

HTML resumido:

```html
<div class="calendarwrapper" data-view="upcoming">
  <div class="event" data-type="event" data-event-id="<event_id>"
       data-course-id="<course_id>" data-event-component="mod_assign" data-event-eventtype="due">
    <div class="card">
      <div class="card-header"><h3 class="name">Nombre del evento</h3></div>
      <div class="description card-body">
        <!-- fecha, tipo de evento y enlace a la materia -->
      </div>
      <div class="card-footer">
        <a class="card-link" href="/mod/assign/view.php?id=<module_id>&amp;action=editsubmission">...</a>
      </div>
    </div>
  </div>
</div>
```

El contenedor brinda mejor clasificación que el widget resumido. Combinaciones efectivamente observadas:

| `data-event-component` | `data-event-eventtype` | Qué representa |
| --- | --- | --- |
| `mod_assign` | `due` | Vencimiento de una actividad de entrega. |
| `mod_attendance` | `attendance` | Evento de asistencia. |
| `mod_feedback` | `close` | Cierre de una encuesta. |

Para seleccionar vencimientos de trabajos sin filtrar por el idioma del título:

```css
#region-main .event[data-event-component="mod_assign"][data-event-eventtype="due"]
```

Se extrajeron **9 eventos** en la vista visitada. Esquema verificado, contenido de `schema`:

```json
{
  "events": [
    {
      "selector": "#region-main .event[data-event-id]",
      "fields": {
        "name": "h3.name",
        "event_id": {
          "selector": "",
          "attr": "data-event-id"
        },
        "course_id": {
          "selector": "",
          "attr": "data-course-id"
        },
        "description": ".description",
        "links": [
          {
            "selector": ".description a[href]",
            "attr": "href"
          }
        ],
        "component": {
          "selector": "",
          "attr": "data-event-component"
        },
        "event_type": {
          "selector": "",
          "attr": "data-event-eventtype"
        },
        "course_name": ".description a[href*=\"/course/view.php\"]",
        "date_urls": [
          {
            "selector": ".description a[href*=\"/calendar/view.php\"]",
            "attr": "href"
          }
        ],
        "action_url": {
          "selector": ".card-footer a[href]",
          "attr": "href"
        },
        "action_label": ".card-footer a[href]"
      }
    }
  ]
}
```

`event_id`, `course_id` y el `id` del módulo son identificadores distintos. El enlace de la actividad puede estar en `.card-footer`, fuera de `.description`.

Un enlace como `action=editsubmission` abre el flujo de entrega. En esta inspección solo se leyó su atributo: **no se siguió ni se enviaron archivos**. Para futuras consultas de una actividad, construir su URL de lectura con el módulo identificado y sin parámetros de edición.

Los rótulos pueden ser relativos (“Tomorrow”) o depender del idioma. Las URLs observadas transportan `time` como Unix timestamp en segundos. Conservar el texto y los enlaces originales; en eventos con duración, confirmar qué instante representa cada enlace. El campus informó `America/Argentina/Buenos_Aires` en `M.cfg.usertimezone`: esa zona observada debe conservarse como procedencia de la interpretación.

No se comprobó aquí el límite de alcance de “próximos eventos” ni su exhaustividad para un rango arbitrario. Nueve registros es el resultado de esta visita, no una garantía de que no haya otros eventos fuera del rango de la vista.

## 4. Estructura de una asignatura

Se entró en una asignatura mediante `click` desde la sidebar y luego se contrastó una segunda materia. Las dos tenían:

```html
<body id="page-course-view-topics" class="format-topics ... loggedin ...">
  <section id="region-main">
    <div class="course-content">
      <ul class="topics">
        <li id="section-<index>" class="section course-section"
            data-sectionid="<index>" data-id="<section_db_id>" data-sectionname="Nombre">
          <div class="section-item">
            <div class="course-section-header">
              <a role="button" aria-expanded="true" aria-controls="coursecontentcollapseid<section_db_id>">...</a>
              <h3 class="sectionname">Nombre</h3>
            </div>
            <div id="coursecontentcollapseid<section_db_id>" class="content collapse show">
              <ul class="section">
                <li id="module-<module_id>" class="activity resource modtype_resource" data-id="<module_id>">
                  <div class="activity-item" data-region="activity-card" data-activityname="Nombre del recurso">
                    <div class="activityname">
                      <a class="aalink stretched-link" href="/mod/resource/view.php?id=<module_id>">
                        <span class="instancename">Nombre del recurso</span>
                      </a>
                    </div>
                  </div>
                </li>
              </ul>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </section>
</body>
```

La primera materia tenía 11 secciones; Bases de Datos No SQL tenía 8 secciones y se extrajeron 49 actividades. La sidebar de una materia también incluye participantes, notas y enlaces de secciones; mantener el filtro `li.type_course` para no confundirlos con cursos.

### Secciones

`goto` con la URL de curso obtenida de la sidebar y luego `waitForSelector` sobre:

```css
#region-main .course-content li.section[data-sectionid]
```

Esquema verificado de `extract`:

```json
{
  "sections": [
    {
      "selector": "#region-main .course-content li.section[data-sectionid]",
      "fields": {
        "name": ".sectionname",
        "index": {
          "selector": "",
          "attr": "data-sectionid"
        },
        "section_db_id": {
          "selector": "",
          "attr": "data-id"
        },
        "dom_id": {
          "selector": "",
          "attr": "id"
        }
      }
    }
  ]
}
```

No usar solo el nombre de la sección como identificador: en No SQL se repite “Material” en distintas secciones (tres en la revisión ampliada).

| Identificador | Significado |
| --- | --- |
| `course/view.php?id=...` | ID de la materia. |
| `li.section[data-sectionid]` | Índice de la sección dentro del curso; empieza en 0. |
| `li.section[data-id]` | ID de la sección en la plataforma. |
| `li.activity[data-id]` | ID del módulo de actividad. |
| `data-event-id` | ID del evento de calendario. |
| `backendNodeId` | Identificador temporal del nodo en Lightpanda. |

Las secciones tenían controles `a[role="button"][aria-controls][aria-expanded]` y paneles `.collapse.show`. Leer primero el DOM: el contenido puede existir aunque la sección esté colapsada. Si hace falta expandir, comprobar el `aria-expanded` del control dentro de la sección elegida y hacer un único `click`; no alternarlo sin revisar el estado. La expansión no se probó en esta revisión.

### Actividades y bibliografía

Selector de registro: `#region-main li.activity`. Nombre limpio: atributo `data-activityname` de `.activity-item`. El texto de `.activityname` incluía sufijos de accesibilidad como “File” o “Assignment”; el atributo evitó mezclarlos con el título en la extracción verificada.

Esquema comprobado:

```json
{
  "activities": [
    {
      "selector": "#region-main li.activity",
      "fields": {
        "module_id": {
          "selector": "",
          "attr": "data-id"
        },
        "classes": {
          "selector": "",
          "attr": "class"
        },
        "name": {
          "selector": ".activity-item",
          "attr": "data-activityname"
        },
        "url": {
          "selector": "a.aalink[href]",
          "attr": "href"
        },
        "availability": ".availabilityinfo"
      }
    }
  ]
}
```

El campo `availability` es opcional y puede ser `null`; no lo interpretar como prueba de acceso. En la primera materia se observaron actividades restringidas que mostraban texto pero no un enlace navegable. Si `url` es `null`, conservar el ítem y no inventar un `href` usando su ID.

Tipos observados en estas materias:

| Clase | Enlace observado | Uso para próximas herramientas |
| --- | --- | --- |
| `modtype_resource` | `/mod/resource/view.php?id=...` | Recurso de archivo; no es todavía la URL binaria final. |
| `modtype_folder` | `/mod/folder/view.php?id=...` | Carpeta de materiales. |
| `modtype_url` | `/mod/url/view.php?id=...` | Recurso que representa un enlace, posiblemente externo. |
| `modtype_assign` | `/mod/assign/view.php?id=...` | Actividad de entrega. |
| `modtype_forum` | `/mod/forum/view.php?id=...` | Foro. |
| `modtype_attendance` | `/mod/attendance/view.php?id=...` | Asistencia. |
| `modtype_label` | Puede no tener enlace | Texto o encabezado dentro de una sección. |

Para bibliografía, identificar primero la sección por su nombre y su ID/índice. En una materia se llamaba “BIBLIOGRAFÍA”; en otra, “Material”, repetido en distintas unidades. Luego limitar `li.activity` a esa sección y clasificar por `modtype_resource`, `modtype_folder` y `modtype_url`. No asumir que todos los archivos están bajo un título único.

Se inspeccionaron los enlaces a archivos, carpetas y entregas dentro del curso. No se descargaron recursos ni se inspeccionaron todavía las páginas internas de cada tipo de módulo.

## 5. Leer HTML cuando haga falta ajustar un selector

Herramienta `html`, argumentos de ejemplo sobre el bloque de navegación ya observado:

```json
{
  "selector": "[data-block=\"navigation\"]",
  "maxBytes": 12000,
  "strip": {
    "js": true,
    "css": true
  }
}
```

El mismo patrón puede apuntar a `[data-block="calendar_upcoming"]` o a una sección de curso específica. Si se alcanza `maxBytes`, el resultado puede estar truncado: no asumir que faltan los elementos posteriores.

No aplicar `strip.shell` al estudiar la sidebar ni eliminar elementos invisibles cuando se necesite leer ramas colapsadas. Evitar un volcado de todo el documento: otros bloques contienen perfiles, usuarios conectados y datos ajenos a esta tarea.

## 6. Orden recomendado de consultas

1. Verificar autenticación en la misma sesión.
2. Abrir `/` y extraer el árbol de materias con el selector específico.
3. Abrir `/my/` para calendario mensual y lista resumida de próximos eventos.
4. Abrir el enlace observado `view=upcoming` para obtener curso, componente, tipo de evento y enlace de actividad.
5. Resolver una materia por el ID de su URL, abrirla y extraer secciones y actividades.
6. Relacionar IDs de curso, módulo y evento en la capa de servicio; conservar fechas y señales de resultados parciales.

Usar selectores dinámicos descubiertos en el DOM. No fijar IDs `inst...`, `random...`, tablas `month-detailed-...`, ni los identificadores temporales del navegador.

## Evidencia y límites

| Comprobación | Resultado real observado |
| --- | --- |
| Login | Sesión autenticada con Lightpanda y credenciales privadas. |
| Sidebar | 35 registros mediante el esquema incluido. |
| Dashboard | Bloques `calendar_month`, `calendar_upcoming` y `timeline`. |
| Próximos eventos | 9 registros en el widget y 9 en la vista detallada. |
| Mes mostrado | 19 días con eventos; la cuadrícula puede resumirlos. |
| Entrada a materia | Navegación por `click` desde la sidebar confirmada. |
| Repetición de estructura | Dos materias `format-topics` con el mismo patrón base. |
| Extracción de segunda materia | 8 secciones y 49 actividades. |
| Timeline cargado | No confirmado; se observaron placeholders y mensajes vacíos ocultos. |
| Cambios de filtro/mes, popovers y expansión | Se inspeccionaron los controles; no se ejercitaron todos sus manejadores. |
| Descargas y envíos | No realizados en esta inspección. |

Las cantidades corresponden a una cuenta y un momento concretos. Este documento conserva estructura y llamadas, no la lista de inscripciones ni las tareas privadas del estudiante. Las observaciones locales quedaron fuera de Git.

Referencia de parámetros nativos: [herramientas del MCP de Lightpanda](https://lightpanda.io/docs/reference/mcp-tools). Para el uso desde Python: [SDK de Lightpanda](https://lightpanda.io/docs/reference/python).


## Implementación posterior: consulta mensual

`list_monthly_activities` aprovecha el bloque mensual observado y consulta los datos estructurados de `core_calendar/repository` desde Lightpanda. El 31 de octubre de 2026 se verificó la llamada MCP contra el campus real: 33 eventos del mes y 13 al filtrar vencimientos/cierres. Se confirmó el contrato del repositorio y se comparó el enlace directo con el popup real. Ver [calendario: extracción, enlaces y validación](calendario.md).

El popup de calendario usa `[data-region="modal-container"][role="dialog"]`, con regiones `modal`, `header`, `title`, `body` y `footer`. El enlace a la actividad está en `[data-region="footer"] a[href]`; debe validarse como una ruta `/mod/<módulo>/view.php?id=<cmid>`. No buscar su texto traducible. Antes de pulsar un evento hay que esperar la carga de los módulos `core_calendar/calendar`, `core_calendar/summary_modal` y `core_calendar/popover`, observados en esta sesión. Hay otros elementos `[role="dialog"]` de notificaciones, por lo que ese selector por sí solo no identifica el popup de una tarea.


## Ampliación: Grado y formatos de cuatro materias

La revisión posterior de dos materias de Sistemas y dos Básicas encontró tanto `format-topics` como `format-onetopic`. En este último formato, el DOM inicial solo incluye la sección activa y puede no existir una barra de pestañas. Consultá [la guía para implementar get_course_resources()](guia-get-course-resources.md) para el recorrido por secciones, las carpetas y las restricciones. El helper `CourseService.list_degree_courses()` lista únicamente My courses → Grado; no debe confundirse con el selector general de cursos de la inspección inicial.
