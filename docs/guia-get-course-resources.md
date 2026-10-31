# Guía de inspección para implementar `get_course_resources()`

Inspección del **31 de octubre de 2026** sobre el campus real, con Lightpanda 1.0.2 y la cuenta autorizada de `.env`. Se revisaron **cuatro materias: dos específicas de Sistemas y dos básicas**, siguiendo la distribución solicitada. Este documento complementa [estructura-campus.md](estructura-campus.md): las observaciones anteriores de `topics` no se pueden generalizar a todas las materias.

Está implementado el helper interno `CourseService.list_degree_courses()`. **`get_course_resources()` todavía no está implementada ni registrada como herramienta MCP.** La inspección consultó páginas, pestañas y carpetas; no descargó bibliografía ni modificó entregas, grupos o inscripciones.

## 1. Helper para My courses → Grado

Archivos:

- `src/utnfrsf_campus_mcp/services/courses.py`: `CourseService.list_degree_courses()` autentica con el servicio existente, adquiere la sesión compartida y abre `/`.
- `src/utnfrsf_campus_mcp/parsers/courses.py`: `DEGREE_COURSES_SCHEMA` describe la extracción nativa con `page.extract(schema=...)`; `parse_degree_courses()` selecciona Grado y valida y normaliza su contenido en Python. No se ejecuta JavaScript propio para listar asignaturas.
- `models.Course`: devuelve `id`, `name` y `url`. Se conserva el orden de la sidebar y se deduplica por ID.

Uso desde otro servicio o script de desarrollo:

```python
from utnfrsf_campus_mcp.browser.lightpanda import LightpandaBrowser
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import Settings
from utnfrsf_campus_mcp.services.authentication import AuthenticationService
from utnfrsf_campus_mcp.services.courses import CourseService


async def inspect_courses():
    settings = Settings()
    session = CampusSession(LightpandaBrowser(settings))
    try:
        authentication = AuthenticationService(settings, session)
        courses = await CourseService(settings, session, authentication).list_degree_courses()
        return [course.model_dump() for course in courses]
    finally:
        await session.close()
```

En el servidor se deben pasar los mismos `Settings`, `CampusSession` y `AuthenticationService` que usan las otras operaciones. No construir otro navegador por cada recurso ni adquirir `session.acquire()` antes de llamar a este helper: el login y el helper adquieren ese mismo lock.

### Estructura real del árbol

```text
[data-block="navigation"]
└── li.type_system
    ├── p.tree_item > a[href=".../my/courses.php"]
    └── ul
        ├── li > p.tree_item > span: Grado
        │   └── ul
        │       ├── Ingeniería en Sistemas de Información → años → li.type_course
        │       └── Materias Básicas → años → li.type_course
        ├── Ingreso
        └── Secretaría de Extensión Universitaria
```

Hay otro enlace a `/my/courses.php` en un nodo `type_custom` que no contiene este árbol. La etiqueta “My courses” puede traducirse; el helper identifica el nodo por **tipo y ruta**, no por ese texto.

**Límite de identificación de Grado:** la categoría aparece como un `span` sin URL, ID de categoría ni `data-node-key`; sus IDs `random...` son temporales. Se compara exactamente el nombre académico **Grado**, indicado por el usuario y almacenado como categoría del sitio. Es contenido académico, no una traducción de la interfaz según el usuario. Si el campus renombra esa categoría, el helper falla explícitamente; no selecciona la primera rama por posición ni todas las materias como fallback.

La extracción anidada devuelve grupos y cursos mediante selectores CSS (`:has` identifica la rama de My courses); la elección del grupo Grado, los límites y la validación de URLs quedan en Python. `extract` también detecta categorías con carga pendiente y usa `limit=1001` para poder rechazar listados que superen el máximo de 1000. Se volvió a comprobar contra el campus real: las mismas 30 asignaturas que con la implementación anterior.

Los descendientes ya estaban en el HTML aunque las categorías tenían `aria-expanded="false"`. No hizo falta expandirlas. Los cursos se extraen **solo dentro de Grado** con:

```css
li.type_course > p.tree_item > a[href]
```

Se usa `title` para el nombre completo: algunos textos visibles terminan en `...`. El ID se valida a partir de `/course/view.php?id=<course_id>`; se devuelve una URL canónica con ese único parámetro. No se filtra por año ni por sufijos del nombre: Grado incluye Sistemas y Básicas de varios años.

**Resultado real:** 30 asignaturas de Grado. Las cuatro materias de la muestra están incluidas; los cursos de Ingreso y Pasantías quedaron excluidos. No se versionó el listado de inscripciones completo.

Los errores `COURSES_NAVIGATION_UNSUPPORTED`, `COURSES_INCOMPLETE`, `COURSES_INVALID_COURSE`, `COURSES_LIMIT_EXCEEDED`, `COURSES_SESSION_EXPIRED`, `COURSES_ACCESS_DENIED`, `COURSES_RATE_LIMITED`, `COURSES_HTTP_ERROR`, `COURSES_TIMEOUT` y `COURSES_BROWSER_ERROR` no se convierten en un resultado vacío. Se limita la extracción a 1000 cursos y 30 segundos después del login. Un error de login conserva su código `LOGIN_*`.

La carga AJAX de categorías sí afecta la integridad del listado. La de secciones **dentro de un curso** no: el helper no necesita expandir los contenidos de cada materia para listar sus nombres.

## 2. Materias comparadas y alcance real

| Grupo | Materia | ID | Formato | Lo efectivamente inspeccionado |
| --- | --- | --- | --- | --- |
| Sistemas | Bases de Datos No SQL, 2026 | 7503 | `topics` | 8 secciones y 49 actividades en la página principal; una carpeta. |
| Sistemas | Diseño de Sistemas de Información, 2026 | 7476 | `topics` | 11 secciones y 57 actividades en la página principal; una carpeta. |
| Básicas | Probabilidad y Estadística, 2026 | 7723 | `onetopic` | Navegación a 14 secciones; contenido de las secciones 0, 1, 3, 5 y 11: 33 actividades en la muestra. |
| Básicas | Física II, 2025, comisión de Sistemas | 7119 | `onetopic` | 27 pestañas, 19 habilitadas y 8 deshabilitadas; contenido de las secciones 0, 1, 2 y 8: 45 actividades en la muestra. |

Las cantidades de las materias básicas **no son totales de recursos de todo el curso**. Se visitaron secciones representativas para contrastar el formato, los enlaces, las restricciones y los tipos de material; no se rastrearon todos los contenidos.

Los cursos de la muestra son evidencia de estructura. La implementación debe aceptar IDs/enlaces procedentes del helper, sin fijar estos cuatro IDs como configuración.

## 3. Patrón común de secciones y actividades

Ambos formatos usan estos contenedores, comprobados en las cuatro materias:

```css
#region-main .course-content
#region-main .course-content li.section[data-sectionid]
#region-main li.activity[data-id]
```

Los módulos mantienen el mismo patrón:

```html
<li class="activity activity-wrapper resource modtype_resource"
    id="module-<cmid>" data-for="cmitem" data-id="<cmid>">
  <div class="activity-item" data-region="activity-card"
       data-activityname="Nombre del material">
    <!-- Otros contenedores omitidos -->
    <a class="aalink stretched-link" href="/mod/resource/view.php?id=<cmid>">...</a>
  </div>
</li>
```

| Dato | Fuente | Precaución |
| --- | --- | --- |
| ID de curso | URL `/course/view.php?id=...` | No confundirlo con un ID de módulo. |
| Índice de sección | `li.section[data-sectionid]` o `data-number` | Es el ordinal del curso, incluido 0; coincide con `section=` en las URLs observadas. |
| ID de sección | `li.section[data-id]` | Es el ID de base de datos, distinto del ordinal. |
| ID de módulo | `li.activity[data-id]` | Coincide con `module-<cmid>` y el `id` de `/mod/.../view.php`. |
| Nombre de actividad | `.activity-item[data-region="activity-card"]` → `data-activityname` | Evita agregar sufijos traducibles como “File”. |
| Tipo de actividad | Clase `modtype_<tipo>` de `li.activity` | No deducirlo del título ni del texto accesible del icono. |
| Enlace principal | `a.aalink[href]` dentro del módulo | Puede faltar; no fabricarlo para actividades restringidas. |
| Restricciones | `.availabilityinfo` / `[data-region="availabilityinfo"]` | Conservar evidencia; no interpretar sus frases traducidas como un enum de permisos. |

Esquema de `extract` compatible con el SDK usado, aplicado a la página o sección actual:

```python
schema = {
    "activities": [
        {
            "selector": "#region-main li.activity[data-id]",
            "fields": {
                "module_id": {"selector": "", "attr": "data-id"},
                "classes": {"selector": "", "attr": "class"},
                "name": {"selector": "[data-region='activity-card']", "attr": "data-activityname"},
                "activity_url": {"selector": "a.aalink[href]", "attr": "href"},
                "availability": ".availabilityinfo",
            },
        }
    ],
}
activities = await page.extract(schema=schema)
```

Para conservar la relación sección → módulo, extraer por sección o usar `evaluate` con `activity.closest('li.section[data-sectionid]')`. No asignar todos los módulos al primer título visible.

## 4. Diferencias que cambian el recorrido

### `topics`: secciones presentes simultáneamente

En No SQL y Diseño:

```css
body#page-course-view-topics.format-topics
#region-main .course-content ul.topics
```

Las secciones incluyen `data-sectionid`, `data-id`, `data-number` y `data-sectionname`. El nombre también aparece en `.sectionname`. Los controles de expansión tienen `aria-controls` y `aria-expanded`; el contenido puede estar en el DOM aunque se encuentre colapsado. Conviene extraer primero y expandir solo si falta contenido.

No SQL tiene **tres secciones llamadas Material**. Diseño incluye una sección de bibliografía cuyo nombre tiene un error ortográfico. Por lo tanto, no es suficiente buscar “Bibliografía”, ni puede identificarse una sección solo por su nombre.

Distribución observada en las páginas completas:

| Tipo | No SQL | Diseño |
| --- | ---: | ---: |
| `resource` | 25 | 41 |
| `folder` | 1 | 5 |
| `url` | 5 | 0 |
| `assign` | 12 | 6 |
| `quiz` | 4 | 1 |
| `forum` | 1 | 2 |
| `attendance` | 1 | 0 |
| `choice` | 0 | 1 |
| `label` | 0 | 1 |

### `onetopic`: una sección por respuesta

En Probabilidad y Física II:

```css
body#page-course-view-onetopic.format-onetopic
#region-main .course-content .single-section ul.onetopic
```

La URL base mostró solo `section-0`. Navegar por enlaces observados con `?id=<course_id>&section=<ordinal>` cambió realmente `data-sectionid` al ordinal solicitado. Los módulos continuaron usando el patrón común de la sección anterior.

Las secciones inspeccionadas mantuvieron `data-sectionid`, `data-id` y `data-number`, pero **no tenían `data-sectionname`**, y el extractor `.sectionname` no produjo un nombre. El título de la sección puede recuperarse del enlace de navegación que llevó a ella, vinculado por curso + ordinal.

**Física II:** la barra es `ul.format_onetopic-tabs`; sus entradas son `li.nav-item` y sus enlaces `a.nav-link[href]`. Los IDs `onetabid-<section_db_id>` son observables, pero el recorrido debe usar las URLs reales y validar curso e índice. Algunas pestañas conservan un `href` aunque el enlace tenga `.disabled` y el contenedor `.dimmed.disabled`: no tratarlas como recursos disponibles ni intentar eludir esa restricción.

**Probabilidad:** no se encontró esa barra de pestañas, pero la sidebar contenía los enlaces de las 14 secciones. La alternativa verificada es localizar el nodo `li.type_course` de la materia actual en `[data-block="navigation"]` y sus descendientes:

```css
li.type_structure > p.tree_item > a[href]
```

Normalizar cada `href` con la URL actual, exigir origen del campus, ruta `/course/view.php`, el mismo `id` de curso y exactamente un `section` entero. Deduplicar por curso + ordinal. Esto evita confundir enlaces del menú de navegación general, el curso raíz y los de otra asignatura.

Algunas ramas `type_structure` tenían `data-requires-ajax="true"` y `data-loaded="false"`, pero **su enlace a la sección ya existía**. No hace falta expandirlas para conocer el destino: abrir ese enlace mediante `goto` cargó la sección. El contenido de otra pestaña no estaba escondido en el DOM inicial; había que navegar.

Para un listado completo, descubrir las secciones accesibles y recorrerlas secuencialmente con un conjunto de visitados y límites. Si se agota el tiempo o falta una sección, indicar el alcance parcial y los pendientes. No presentar la página inicial con 3 actividades de Probabilidad como si fuera todo el curso.

## 5. Tipos de recursos y páginas de carpetas

Para `get_course_resources()`, separar materiales de actividades de evaluación:

| Tipo observado | Qué se sabe | Tratamiento inicial recomendado |
| --- | --- | --- |
| `resource` | `/mod/resource/view.php?id=<cmid>`; suele mostrar iconos `/f/pdf` o `/f/powerpoint`. | Listar como archivo con su enlace de actividad. El icono solo es una pista; no prueba MIME, tamaño ni destino final. |
| `folder` | `/mod/folder/view.php?id=<cmid>` y árbol HTML de archivos. | Listar el contenedor y, si la función incluye expansión, sus archivos con referencia al módulo padre. |
| `url` | `/mod/url/view.php?id=<cmid>` en las cuatro materias combinadas. | Listar como enlace; no seguir automáticamente una redirección externa. |
| `label` | Varias etiquetas sin `a.aalink`; nombres genéricos repetidos. | Separar texto/encabezados de archivos. Inspeccionar enlaces embebidos si los hay; no inventar un enlace al módulo. |
| `assign`, `quiz`, `forum`, `attendance`, `choice` | Actividades académicas, no equivalentes a bibliografía. | No incluirlas como archivos por defecto. Sus posibles adjuntos requerirían una inspección específica posterior. |

En los fragmentos revisados no se encontraron enlaces de archivos en resúmenes de sección ni en las regiones inspeccionadas de las etiquetas. Esto no garantiza que otras materias no los usen; conviene contemplar `.summary a[href]` y enlaces embebidos como fuentes adicionales sin mezclarlos con el enlace principal de una actividad.

### Dos carpetas verificadas

Se abrieron una carpeta de No SQL y otra de Diseño mediante sus `href` reales. Ambas mostraron:

```css
#region-main .foldertree
#region-main .foldertree .filemanager
#region-main .foldertree a[href]
```

El árbol contiene listas `ul > li`, contenedores `.fp-filename-icon`, `.fp-icon` y `.fp-filename`. Las dos carpetas inspeccionadas tenían respectivamente 2 y 1 archivos; los enlaces apuntaban a:

```text
/pluginfile.php/<context_id>/mod_folder/content/0/<ruta-del-archivo>?forcedownload=1
```

Ese `context_id` no es el ID de curso ni el de módulo. Conservar la URL real validada y el camino de carpetas; no construirla a partir del nombre mostrado. Deduplicar el mismo enlace y mantener el módulo padre. No asumir que dos archivos con igual nombre son el mismo recurso.

También había un formulario de descarga conjunta cuyo destino era `/mod/folder/download_folder.php`. **No se envió.** No se deben extraer tokens ocultos al listar, ni confundir ese formulario con un enlace individual de archivo. El helper de listado de asignaturas tampoco abre estas carpetas: esta revisión fue una inspección separada.

### Restricciones verificadas

En Probabilidad, las secciones 3 y 11 contenían actividades restringidas. Se observó:

```html
<div class="activity-availability availabilityinfo isrestricted"
     data-region="availabilityinfo">...</div>
```

Algunas actividades conservaban nombre e ID pero no `a.aalink`. Esto es distinto de una etiqueta sin enlace por diseño. Conservar el tipo y la evidencia de restricción; no completar un enlace inexistente con `/mod/<tipo>/view.php?id=<cmid>`. La ausencia de `.availabilityinfo` tampoco es una prueba de que un archivo se pueda descargar.

## 6. Secuencia sugerida para el siguiente agente

1. Reutilizar `CourseService.list_degree_courses()` y resolver el curso por ID. No seleccionar por una coincidencia parcial de nombre, ni limitar Grado a Sistemas dejando fuera Básicas.
2. Autenticar y navegar a la URL canónica del curso en la misma sesión. Validar origen, HTTP y autenticación antes de extraer.
3. Identificar el formato mediante `body` y los contenedores. Para `topics`, extraer las secciones presentes. Para `onetopic`, inventariar la barra de pestañas y/o los enlaces `type_structure` de la sidebar; respetar `.disabled` y recorrer solo destinos observados.
4. Extraer por sección los módulos, sus tipos, enlaces y restricciones. Identificar las secciones por ordinal e ID, aunque sus nombres se repitan o falten.
5. Listar `resource`, `folder` y `url`; definir explícitamente si se expanden carpetas y se incluyen enlaces embebidos. Mantener origen, curso, sección, módulo y relación padre de cada recurso.
6. Implementar normalización en parsers y recorrido en servicios, con un adaptador Lightpanda y registro MCP separados. Reutilizar el lock de `CampusSession`; no llamar a helpers que lo adquieren desde dentro del mismo lock.
7. Devolver datos tipados con procedencia y `fetched_at`, y un indicador de integridad o advertencias cuando queden secciones/carpetas pendientes. Un fallo de acceso o parsing no debe convertirse en una lista vacía exitosa.
8. Probar nombres duplicados, pestañas faltantes, barra de pestañas ausente, enlaces repetidos, restricciones sin enlace, carpetas anidadas, URLs externas y sesión vencida. Verificar el resultado real en ambas familias de formato.

Una primera respuesta útil puede incluir: `course`, `section_index`, `section_id`, `module_id`, `name`, `resource_type`, `activity_url`, archivos hijos cuando se hayan inspeccionado, evidencia de restricciones y URL de origen. Un enlace a `/mod/resource/view.php` todavía no prueba que exista una URL de descarga final; usar `null` cuando no se haya resuelto.

### Límites de esta evidencia

- No se implementó `get_course_resources()` ni se descargaron archivos binarios.
- No se siguieron los destinos externos de `mod_url` ni se inspeccionaron adjuntos de tareas, cuestionarios, foros, páginas o libros.
- No se recorrieron todas las pestañas de las materias básicas ni carpetas arbitrarias; las cantidades de la muestra están delimitadas arriba.
- No se forzaron pestañas deshabilitadas ni accesos restringidos por grupo.
- Los diagnósticos reales y el listado de asignaturas están en `.local/`, ignorado por Git. Las pruebas locales también permanecen ignoradas.
