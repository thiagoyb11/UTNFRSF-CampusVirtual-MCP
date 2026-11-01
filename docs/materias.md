# Listado de materias por MCP

`list_courses()` permite descubrir las materias antes de usar herramientas que necesitan `course_id`. No recibe parámetros ni credenciales; autentica con la configuración privada del servidor y reutiliza la sesión de Lightpanda.

## Contrato

Invocación MCP: `list_courses` con argumentos `{}`.

| Campo | Significado |
| --- | --- |
| `scope` | Siempre `Grado`: rama My courses → Grado visible para la cuenta. |
| `source_url` | Portada del campus donde se consulta el árbol de navegación. |
| `fetched_at` | Momento de finalización de la consulta, ISO 8601 con zona UTC. |
| `total` | Cantidad de materias únicas devueltas. |
| `courses` | Lista ordenada de `{id, name, url}` con nombre completo y enlace canónico. |
| `complete` | Siempre `true` en respuestas exitosas; una extracción incompleta produce un error MCP. |

Incluye Sistemas y Básicas y todos los períodos presentes en esa rama, incluidos años anteriores. Excluye Ingreso, Extensión y el catálogo general de la facultad. `complete` solo describe ese alcance; no afirma que estén listadas todas las materias del campus.

Los nombres similares y las distintas ediciones de una materia conservan sus propios IDs. La herramienta no elige una por coincidencia parcial. Los enlaces se validan contra el origen del campus y se normalizan para eliminar parámetros adicionales; los duplicados idénticos se unifican y los contradictorios producen error.

## Límites y errores

Se consulta la portada y se extrae la rama Grado sin abrir cada materia. No hay filtros, paginación ni expansión de categorías por AJAX en esta versión. Una rama dinámica pendiente no se entrega como listado completo. El máximo es 1000 materias; se extrae un registro adicional para detectar el exceso. La consulta dispone de 30 segundos después de autenticar; el login mantiene su propio presupuesto configurado.

- `COURSES_INCOMPLETE`: contenido pendiente o lista no confirmada; volver a consultar más tarde o inspeccionar la estructura si persiste.
- `COURSES_NAVIGATION_UNSUPPORTED`: no se reconoce una única rama My courses → Grado.
- `COURSES_INVALID_COURSE`: nombre o enlace inválido, o IDs duplicados contradictorios.
- `COURSES_LIMIT_EXCEEDED`: más de 1000 registros; requiere ampliar el recorrido explícitamente.
- `COURSES_SESSION_EXPIRED`, `COURSES_ACCESS_DENIED`, `COURSES_RATE_LIMITED`, `COURSES_HTTP_ERROR`, `COURSES_TIMEOUT` y `COURSES_BROWSER_ERROR`: fallos de acceso o navegador diferenciados.
- Los errores `LOGIN_*` conservan el código del servicio de autenticación. Los fallos inesperados se ocultan detrás de `COURSES_INTERNAL_ERROR`, sin devolver excepciones privadas del navegador.

Una rama Grado reconocida y completamente cargada puede devolver `courses=[]`, `total=0`. Una rama ausente, una redirección al login o un fallo de extracción nunca equivalen a ese resultado.

Las anotaciones MCP declaran lectura, operación no destructiva e idempotente y acceso al campus externo. No hay escrituras académicas.

## Implementación y verificación

`tools/courses.py` delega en `CourseService.list_courses()`, que agrega procedencia y alcance al helper `list_degree_courses()`. Este último sigue siendo reutilizado por recursos. La autenticación ocurre antes de adquirir la sesión, sin anidar el lock ni construir otro navegador. Los selectores y la validación están en `parsers/courses.py`; se conserva la [estructura previamente observada](guia-get-course-resources.md).

El **31 de octubre de 2026**, a las **21:25:47 y 21:25:49 UTC−03:00** (`2026-11-01T00:25:47Z` y `2026-11-01T00:25:49Z`), el cliente oficial de MCP descubrió `list_courses` y realizó dos llamadas consecutivas contra el campus real mediante el entrypoint stdio. Ambas devolvieron **30 materias**, alcance `Grado`, `complete=true`, IDs únicos y las dos ediciones visibles de Seminario Integrador. El proceso compartió sesión y se cerró al terminar; no se modificaron entregas ni otros datos académicos.

Las pruebas locales con el cliente MCP y datos sintéticos comprueban salida estructurada, anotaciones, procedencia, fecha con zona, materias de distintos períodos, vacío válido, sesión vencida, rama incompleta, navegación inesperada y ocultamiento de errores privados. El descubrimiento y la propagación de errores también se probaron en un subproceso stdio. Comandos y resultado de la suite en [desarrollo](desarrollo.md#controles-locales).

Para usar la herramienta nueva en un host ya conectado, reiniciar su conexión o proceso MCP. La configuración existente del servidor del campus sigue siendo válida; Lightpanda se inicia desde su adaptador interno. Esto permite descubrir materias mediante MCP sin ejecutar el helper aparte desde una terminal; no cambia los permisos del entorno que lance el servidor.

Quedan pendientes la búsqueda y los filtros de materias (F02) y los mecanismos generales de continuación de inventarios grandes (F43). No se afirma compatibilidad con ramas que no fueron observadas o requieren carga dinámica.
