# Análisis del campus y funcionalidades pendientes

Última revisión: **1 de noviembre de 2026**.

Este documento es el inventario de funcionalidades pendientes del proyecto. Combina el código actual, la documentación de inspecciones anteriores y una nueva comprobación de lectura con Lightpanda. Incluye implementaciones faltantes, ampliaciones y validaciones pendientes; no todo requiere crear una herramienta nueva.

## Alcance y evidencia

Se revisaron el registro MCP, los modelos y los servicios de autenticación, materias, calendario, recursos, descargas y entregas. Se consultaron el Dashboard, Análisis Numérico y Bases de Datos No SQL en una sesión autorizada, sin enviar formularios académicos ni modificar la entrega de prueba existente.

La inspección anterior de Diseño de Sistemas, Probabilidad y Estadística y Física II aporta evidencia de otros formatos y módulos. No se recorrieron todas las materias ni todas las pantallas del campus. Ver un enlace a calificaciones o mensajes confirma ese acceso en la interfaz, no su estructura interna ni todos los permisos de la cuenta.

Referencias del repositorio:

- [Registro de herramientas](../src/utnfrsf_campus_mcp/server.py), [modelos](../src/utnfrsf_campus_mcp/models.py) y [helper de materias](../src/utnfrsf_campus_mcp/services/courses.py).
- [Estructura del campus](estructura-campus.md) e [inspección de formatos y recursos](guia-get-course-resources.md).
- Contratos y evidencias de [materias](materias.md), [calendario](calendario.md), [recursos](recursos.md), [descargas](descargas.md) y [entregas](entregas.md).

Los diagnósticos de la nueva lectura permanecen en `.local/`, fuera de Git. Este documento no incluye datos personales, cookies, tokens ni contenido privado de alumnos.

## Qué ofrece el campus observado

| Área | Evidencia | Implicación para el MCP |
| --- | --- | --- |
| Materias y navegación | Árbol My courses → Grado y acceso a My courses. | `list_courses` permite descubrir materias por MCP; búsqueda y filtros siguen pendientes. |
| Dashboard | Calendario mensual, próximos eventos, Timeline y cursos recientes. | El resumen mensual actual cubre solo una parte de la organización diaria. |
| Cursos `topics` | Análisis Numérico: 9 secciones; 3 foros, 8 carpetas, 1 página y 6 tareas. No SQL: 8 secciones; 12 tareas, 25 recursos, 5 enlaces, 4 cuestionarios, 1 foro, 1 asistencia y 1 carpeta. | Los cursos mezclan bibliografía, comunicación y evaluación; listar enlaces no equivale a entender cada actividad. |
| Cursos `onetopic` | Inspecciones previas de Probabilidad y Física II: secciones por pestañas, algunas deshabilitadas. | Hay que distinguir implementación del recorrido y validación integral sobre cursos reales. |
| Materiales | Archivos, carpetas, páginas, enlaces externos y etiquetas con contenido embebido. | Falta lectura de contenido estructurado y operaciones cómodas sobre conjuntos de archivos. |
| Entregas | Flujo `assign` inspeccionado y una entrega sintética verificada en el TP 6. | Existe una base funcional; faltan edición, variantes de formularios y ampliación de cobertura. |
| Foros y novedades | Módulos de foro; en Análisis Numérico también bloques `news_items`, `search_forums` y `recent_activity`. | Las novedades y sus adjuntos siguen fuera de las consultas académicas del MCP. |
| Calificaciones, mensajes y notificaciones | Enlaces de navegación observados a reportes de notas, mensajería y notificaciones. | Son áreas candidatas; sus pantallas necesitan inspección específica. |
| Otros módulos | `quiz` y `attendance` observados; `choice` en Diseño y eventos `feedback` documentados en calendario. | Requieren parsers y contratos propios; no son tareas `assign`. |
| Archivos privados e insignias | Bloques `private_files` y `badges` en Dashboard. | Son ampliaciones opcionales, de menor prioridad que tareas y materiales. |

Los tipos y cantidades anteriores corresponden a las páginas inspeccionadas, no a un inventario de toda la facultad. No se presupone que esta instalación habilite todas las funcionalidades de Moodle.

## Progreso real del proyecto

El MCP ya cubre un recorrido útil: iniciar sesión, obtener fechas y recursos, descargar archivos y entregar archivos en una tarea compatible. No conviene asignar un porcentaje global de avance: el campus tiene módulos y configuraciones cuya presencia y permisos todavía no se relevaron.

Hay **dieciséis herramientas registradas**:

| Herramienta | Estado actual | Límite relevante |
| --- | --- | --- |
| `get_server_info` | Implementada, sin acceso a la cuenta; publica el estado de cada herramienta (F45). | Declara el nivel de evidencia documentado; no comprueba la sesión ni la disponibilidad actual del campus. |
| `login` | Implementada y verificada en el campus. | Sesión en memoria; no hay una herramienta específica de estado/cierre o recuperación del navegador. |
| `list_courses` | Implementada y verificada mediante MCP stdio: dos llamadas consecutivas, 30 materias por llamada. | Solo My courses → Grado; incluye períodos anteriores, sin búsqueda, paginación ni expansión AJAX. Una rama incompleta o más de 1000 registros producen error. |
| `list_monthly_activities` | Implementada y verificada, incluido filtro de vencimientos/cierres. | Consulta un mes; no determina qué trabajos siguen pendientes ni descubre actividades sin evento. |
| `get_course_resources` | Implementada; Análisis Numérico devolvió 189 registros de enlaces y alcance completo. | `complete` se refiere a su recorrido documentado; no incluye todos los contenidos de foros, intentos o libros. `onetopic` y `resource` con `forceview` requieren validación real integral. |
| `get_section_content` | Implementada y verificada en `topics` y `onetopic`. | Texto de una sección por llamada; no sigue enlaces. |
| `get_page_content` | Implementada y verificada en dos páginas reales. | Solo módulos `page`. |
| `get_folder_content` | Implementada y verificada en tres carpetas reales. | Solo la descripción; los archivos están en el inventario. |
| `list_forum_discussions` | Implementada y verificada en foros de Avisos. | Detecta paginación, pero no la recorre. |
| `get_forum_discussion` | Implementada y verificada con mensajes anidados. | Adjuntos sin verificar en un caso real. |
| `download_resources` | Implementada para cualquier tipo; tres PDF de Libros descargados y comprobados. | Selección de 1 a 10 enlaces de un módulo por llamada, mismo origen, sin redirecciones ni sincronización incremental. La prueba real citada es de PDF; otros tipos tienen pruebas locales. |
| `get_submission_status` | Implementada y verificada en TP 6; `new` sin entrega comprobado el 4 de noviembre de 2026. | Estado de una tarea y archivos; no ofrece un detalle completo de consigna, plazos, restricciones o devolución. |
| `get_assignment_feedback` | Implementada y verificada mediante MCP en siete tareas reales el 9 de noviembre de 2026 (F29). | Nota, fecha, docente y comentarios; archivos devueltos, anotaciones PDF y rúbricas sin caso real. No distingue una tarea sin calificar de una nota no publicada. |
| `prepare_submission` | Implementada, exclusivamente local. | No consulta si el campus admite esos archivos; los límites reales se validan durante la carga. |
| `upload_files` | Implementada y verificada con un TXT sintético de 125 bytes en TP 6. | Solo flujo académico `assign`; rechaza entregas existentes. Recibo temporal de 30 minutos en el mismo proceso. |
| `submit_assignment` | Guardado y estado `submitted` verificados en TP 6, con bytes comprobados. | Borradores y confirmación adicional se probaron localmente; faltan otras configuraciones reales. |

`CourseService.list_degree_courses()` es la base interna de la herramienta `list_courses` y del inventario de recursos. Lista Grado; no es un descubrimiento general de toda categoría del campus. La respuesta MCP agrega alcance, fuente, fecha de consulta y total; ver [contrato de materias](materias.md).

La arquitectura separa herramientas, servicios, parsers y navegador. Ya hay comprobaciones de origen, sesión, resultados parciales y hashes, además de protección frente a reemplazos y reenvíos inciertos. Esas capacidades no deben figurar como si faltaran desde cero.

La auditoría documental anterior citaba **138 pruebas locales** y **3 integraciones de transporte con Lightpanda sobre un servidor sintético**. Con la incorporación de `list_courses`, `bash scripts/test.sh` aprobó **145 pruebas locales**, con **13 integraciones optativas omitidas**, además de lint y formato. La herramienta nueva se verificó por separado contra el campus mediante MCP stdio; no se repitieron las integraciones de transporte ni escrituras académicas. Los tests están ignorados por preferencia del proyecto y no están disponibles en un clon limpio. Con el catálogo de capacidades de F45, la misma ejecución aprobó **151 pruebas locales**, con las mismas **13 integraciones optativas omitidas**, además de lint y formato.

## Cómo usar y mantener esta lista

- `[ ]` indica trabajo pendiente; `[x]`, criterio de cierre satisfecho. Un elemento parcial o por validar permanece pendiente.
- **Falta:** no existe la capacidad. **Parcial:** existe una base aprovechable. **Validar:** existe implementación y falta evidencia. **Explorar:** primero hay que comprobar disponibilidad, interfaz y permisos.
- **P0:** confiabilidad de los recorridos actuales. **P1:** siguiente núcleo de uso cotidiano. **P2:** ampliación útil. **P3:** opcional, condicionada a necesidad y disponibilidad.
- Los IDs `F01`–`F50` son estables. No renumerar al completar elementos. Los nombres de herramientas futuros son propuestas, salvo las ya registradas.
- Al implementar una funcionalidad, actualizar su estado, alcance, evidencia y pendientes en el mismo cambio. Marcarla terminada solo cuando cumpla su criterio; distinguir pruebas locales de verificación real.
- Este archivo mantiene el detalle de pendientes. [roadmap.md](../roadmap.md) mantiene el orden general de trabajo; los contratos específicos viven en sus respectivas guías. Evitar listas contradictorias.

## A. Descubrimiento de materias y actividades

- [x] **F01 — Exponer el listado de materias por MCP.** **P1 · Implementada y verificada.**
  - `list_courses()` registrada sin parámetros, sobre `list_degree_courses()` y la sesión compartida de Lightpanda. Devuelve ID, nombre y URL de cada materia, `scope=Grado`, fuente, fecha con zona, total y `complete=true`; los fallos de sesión, parsing, carga pendiente y límite son errores MCP.
  - **Evidencia:** 31 de octubre de 2026, cliente oficial MCP sobre el entrypoint stdio contra el campus real: dos llamadas consecutivas de 30 materias, IDs únicos y ambas ediciones visibles de Seminario. Pruebas locales con fixtures para vacío válido, períodos distintos, errores de sesión/navegación/listado incompleto y ocultamiento de excepciones; descubrimiento también comprobado en subproceso stdio. Ver [contrato y verificación](materias.md).
  - **Cierre satisfecho:** el asistente puede descubrir los IDs por MCP. Alcance My courses → Grado, incluidas Sistemas y Básicas y períodos anteriores; no catálogo general ni Ingreso/Extensión. Búsquedas y filtros quedan en F02; expansión AJAX y continuación de inventarios requieren trabajo adicional (F43). Las ramas pendientes y los listados de más de 1000 registros se rechazan explícitamente.

- [ ] **F02 — Buscar y filtrar materias.** **P1 · Parcial.**
  - Buscar por nombre y filtrar por año, categoría o carrera cuando esos datos estén realmente disponibles. Resolver coincidencias múltiples y conservar materias de años anteriores.
  - **Cierre:** búsquedas ambiguas devuelven candidatos; los filtros se basan en datos observados, sin convertir un nombre parecido en autorización de escritura. Depende de F01.

- [ ] **F03 — Consultar el detalle de una materia.** **P1 · Falta.**
  - Devolver descripción, formato, secciones y datos académicos visibles sin recorrer todos los archivos. Incorporar docentes o contactos solo si la interfaz los ofrece y resultan necesarios.
  - **Cierre:** respuesta estructurada con fuente y campos ausentes explícitos; funciona con `topics` y contempla `onetopic`.

- [ ] **F04 — Listar actividades de una materia como actividades.** **P1 · Parcial.**
  - Construir un inventario de tareas, cuestionarios, foros y otros módulos, incluso sin evento de calendario. Evitar usar múltiples enlaces del mismo módulo como múltiples actividades.
  - **Cierre:** una fila por ID de módulo con tipo, sección, disponibilidad observada y URL cuando exista; no inventa acceso a actividades restringidas.

- [ ] **F05 — Leer la consigna y el detalle de una actividad.** **P1 · Parcial.**
  - Extraer enunciado, descripción, adjuntos de la cátedra, condiciones de acceso y datos específicos del módulo. Hoy el inventario extrae enlaces de algunas consignas, pero no devuelve su contenido completo.
  - **Cierre:** detalle trazable al módulo correcto; diferencia consigna, adjuntos y entrega personal. Empezar por `assign` y `page`; otros módulos se inspeccionan por separado.

- [ ] **F06 — Buscar recursos y actividades dentro de materias elegidas.** **P2 · Parcial.**
  - Filtrar por texto, sección, tipo de módulo y extensión sin descargar todo ni exigir al asistente recorrer una respuesta enorme.
  - **Cierre:** resultados conservan procedencia y alcance; búsqueda por nombre y búsqueda en contenido se distinguen. La búsqueda en contenido se incorpora solo con lectores compatibles.

## B. Agenda y trabajos pendientes

- [ ] **F07 — Consultar por rango de fechas.** **P1 · Parcial.**
  - Admitir hoy, semana o un intervalo que cruce meses, reutilizando el calendario existente.
  - **Cierre:** filtra en la zona correcta, conserva eventos que se superponen y deduplica por evento sin fusionar apertura, vencimiento y cierre de una misma actividad.

- [ ] **F08 — Filtrar agenda por materia y tipo de evento.** **P1 · Parcial.**
  - Permitir seleccionar cursos y tipos además del booleano `deadlines_only` actual.
  - **Cierre:** filtra por IDs y tipos observados; comunica filtros activos, cobertura y eventos excluidos sin afirmar que no existen otras actividades.

- [ ] **F09 — Listar trabajos realmente pendientes.** **P1 · Falta.**
  - Combinar actividades de la materia, fechas y estado de entrega. Incluir tareas sin evento y separar sin entregar, borrador, enviado, vencido y estado desconocido cuando se puedan comprobar.
  - **Cierre:** una tarea enviada no aparece como pendiente por conservar su evento; una consulta fallida no se transforma en “sin pendientes”. Depende de F04, F05 y F10.

- [ ] **F10 — Consultar plazos y excepciones efectivos de una tarea.** **P1 · Parcial.**
  - Distinguir apertura, vencimiento, cierre definitivo, prórrogas y restricciones aplicables a la cuenta. No basta con el evento del calendario ni con el texto “Time remaining”.
  - Observación del usuario (1 de noviembre de 2026): una vez vencida la tarea, la vista `assign` deja de mostrar la fecha límite. Solo con entrega tardía o sin entregar figura un atraso del tipo «XX horas XX minutos XX segundos»; en una entrega a tiempo aparece la anticipación («Assignment was submitted 3 hours 46 mins early», Entrega #6 de Diseño, actividad `489575`). Ninguno de esos textos permite reconstruir un instante exacto: hay que buscar la fecha en otra fuente, como el calendario o el evento de la actividad, o devolverla ausente con el texto original.
  - **Cierre:** fechas con zona, fuente y significado, incluidas ausencias e incertidumbres; contrastar con una tarea que muestre esos datos.

- [ ] **F11 — Leer Timeline y próximos eventos del Dashboard.** **P2 · Explorar.**
  - Inspeccionar carga dinámica, filtros y paginación del Timeline, cuya presencia está confirmada pero cuya extracción completa no lo está. El bloque de próximos eventos ya tiene estructura documentada.
  - **Cierre:** espera una condición de carga real y distingue lista vacía, placeholder y error; no presenta Timeline como equivalente al calendario o al estado final de entrega.

## C. Materiales y descargas

- [ ] **F12 — Validar integralmente el inventario `onetopic`.** **P1 · Validar.**
  - Ejecutar la herramienta existente sobre una materia real con varias pestañas y restricciones. El algoritmo y las pruebas locales ya existen.
  - **Cierre:** comparar todas las secciones habilitadas de la materia elegida, enlaces y pendientes; documentar pestañas deshabilitadas y límites sin forzar accesos.

- [ ] **F13 — Validar recursos individuales y sus modos de descarga.** **P1 · Validar.**
  - Comprobar `forceview` en módulos `resource` reales y documentar modos que redirigen, incrustan o muestran el archivo. Análisis Numérico no contenía ese tipo de módulo.
  - **Cierre:** extrae un destino observado válido o informa el recurso como pendiente; no fabrica URLs binarias ni sigue una redirección externa con cookies.

- [x] **F14 — Leer contenido de páginas, etiquetas y secciones.** **P1 · Implementada y verificada.**
  - Ofrecer texto o Markdown de materiales publicados como HTML, conservando títulos y enlaces. El inventario actual devuelve enlaces, no un lector de contenido.
  - Evidencia (4 de noviembre de 2026, Probabilidad y Estadística): la portada `onetopic` usa un iframe de `view.genially.com` como menú, pero el cronograma es una tabla de Moodle en una etiqueta (`#module-480344`, `section=1`), legible desde el DOM. Decisión del usuario: ignorar Genially por completo, porque los enlaces de la barra lateral llevan a las mismas secciones del campus. El inventario solo devuelve el inicio truncado del nombre de esa etiqueta.
  - Implementación (4 de noviembre de 2026): `get_section_content`, `get_page_content` y `get_folder_content` (5 de noviembre) devuelven Markdown con fuente, sección o módulo, enlaces y advertencias; el conversor está en `parsers/content.py`. Evidencia real en `onetopic` y `topics`, con detalle en [recursos](recursos.md).
  - **Variantes pendientes:** otros módulos HTML, como libros o lecciones, y el nombre de sección en `onetopic`.
  - **Cierre satisfecho:** salida legible, con fuente y límites explícitos; conserva la relación con su sección y trata el contenido como datos externos.

- [ ] **F15 — Ampliar el descubrimiento de adjuntos por módulo.** **P2 · Parcial.**
  - Incorporar adjuntos de foros, devoluciones, cuestionarios u otros módulos después de inspeccionarlos. Reutilizar los enlaces de consignas que ya se extraen.
  - **Cierre:** cada archivo indica módulo y contexto; distingue material docente de archivos de la propia entrega y no recorre intentos o conversaciones sin alcance definido.

- [ ] **F16 — Descargar selecciones de varios módulos o una carpeta completa.** **P2 · Parcial.**
  - Orquestar lotes acotados sobre la descarga existente, con selección por carpeta o sección y conservación de subrutas cuando sea útil.
  - **Cierre:** manifiesto de archivos descargados, fallidos y no intentados; conserva procedencia y evita sobrescribir. El límite por llamada actual no se elimina sin un presupuesto equivalente.

- [ ] **F17 — Consultar metadatos de archivos antes de descargar.** **P2 · Parcial.**
  - Obtener nombre, tipo, tamaño o fecha remotos cuando el campus los informe. Hoy hay tipo inferido en el inventario y metadatos de una descarga ya realizada.
  - **Cierre:** diferencia valores informados e inferidos y admite metadatos desconocidos; no descarga archivos grandes solo para responder cuánto pesan.

- [ ] **F18 — Evitar descargas repetidas y sincronizar material seleccionado.** **P2 · Falta.**
  - Mantener un manifiesto local por selección; comparar identidad y metadatos disponibles, detectando cambios sin rastrear todas las materias.
  - **Cierre:** informa nuevos, conservados y modificados con evidencia; no interpreta el hash local como hash remoto. No borra archivos locales automáticamente.

## D. Entregas y archivos

- [ ] **F19 — Consultar preparación remota de una entrega sin subir archivos.** **P1 · Parcial.**
  - Exponer restricciones de la actividad: cantidad, tamaños, tipos, campos obligatorios, editabilidad y pasos de envío. Hoy se inspeccionan internamente durante la carga.
  - **Cierre:** permite conocer lo admitido antes de transferir bytes; conserva `prepare_submission` como operación exclusivamente local. Reutiliza F10.

- [ ] **F20 — Normalizar los grupos de tipos permitidos por Moodle.** **P1 · Parcial.**
  - Resolver grupos semánticos que hoy producen `UPLOAD_TYPES_UNSUPPORTED`, además de las extensiones y MIME explícitos ya soportados.
  - **Cierre:** mapea solo tipos comprobados en la configuración del campus; respeta restricciones, sin ampliar artificialmente los archivos admitidos.

- [ ] **F21 — Editar o reemplazar archivos de una entrega existente.** **P1 · Falta.**
  - Diseñar un flujo explícito de reemplazo, con selección de archivos y preservación de los restantes. Hoy la herramienta rechaza entregas existentes de forma deliberada.
  - **Cierre:** requiere autorización para ese cambio, revalida versión y estado y confirma el conjunto final por nombres y hashes; nunca reemplaza por coincidencia de nombre solamente.

- [ ] **F22 — Quitar archivos concretos de una carga o borrador.** **P2 · Falta.**
  - Permitir corregir una selección temporal o un borrador compatible, distinguiendo quitar un adjunto de retirar toda la entrega.
  - **Cierre:** elimina únicamente los archivos pedidos y confirma los restantes; informa si guardar la modificación también envía la entrega. Depende del flujo de edición F21.

- [ ] **F23 — Retirar o reabrir una entrega cuando el campus lo permita.** **P2 · Explorar.**
  - Inspeccionar si existe una acción disponible para la cuenta y el estado concreto. La posibilidad de deshacer la prueba indicada por el usuario no demuestra un mecanismo general automatizable.
  - **Cierre:** acción sobre una entrega identificada y expresamente solicitada; estado posterior comprobado, sin afirmar que todas las tareas permiten retirarla.

- [ ] **F24 — Entregar texto en línea y formularios mixtos.** **P2 · Parcial.**
  - Incorporar texto del editor, con o sin adjuntos, preservando los campos y la declaración exigidos. Actualmente se rechaza texto existente y no se ofrece composición de texto académico.
  - **Cierre:** el texto y los archivos finales coinciden con la selección autorizada; formatos y sanitización compatibles con el editor observado.

- [ ] **F25 — Soportar entregas grupales.** **P2 · Explorar.**
  - Inspeccionar identificación del grupo, requisitos y confirmaciones particulares. El flujo actual no cubre pasos grupales adicionales.
  - **Cierre:** se conoce el grupo afectado antes de escribir y se informa el alcance compartido; no se deducen permisos ni se modifican entregas de otro grupo.

- [ ] **F26 — Ampliar la validación real de variantes de entregas.** **P1 · Validar.**
  - Comprobar varios archivos, tipos restringidos, borradores, cierre, prórrogas y confirmación adicional en actividades designadas y autorizadas. El TP 6 comprobó un archivo y guardado que envía directamente.
  - **Cierre:** matriz de variantes con evidencia y límites; las pruebas de escritura siguen siendo optativas y nunca se ejecutan por defecto sobre tareas reales.

- [ ] **F27 — Consultar y recuperar el resultado de una carga interrumpida.** **P1 · Parcial.**
  - Exponer el estado de un recibo y una reconciliación explícita. Hoy la reconciliación existe dentro del servicio, pero los recibos vencen y se pierden al reiniciar.
  - **Cierre:** consultar no repite un POST. Cualquier recuperación tras reinicio revalida cuenta, destino, draft y hashes; no persiste cookies o tokens por comodidad ni inventa un recibo recuperado.

## E. Calificaciones y seguimiento

- [ ] **F28 — Consultar calificaciones por materia.** **P1 · Explorar.**
  - Inspeccionar los reportes enlazados y extraer ítems, valores, escalas y totales visibles para la cuenta.
  - **Cierre:** diferencia sin calificar, nota oculta y cero; conserva escalas y no calcula promedios con ponderaciones desconocidas. La navegación está observada, no su parser.

- [ ] **F29 — Leer devoluciones, rúbricas y archivos corregidos.** **P1 · Validar.**
  - Ampliar el detalle de tareas con comentarios del docente, calificación y adjuntos de devolución cuando existan.
  - **Implementado (9 de noviembre de 2026):** `get_assignment_feedback(course_id, activity_id)` lee el bloque `.feedback` de la tarea ya validada por `get_submission_status`. Devuelve nota original (puntos o escala) y, si es `x / y`, valor y máximo; fecha con zona; docente; comentarios por plugin; archivos devueltos separados de los entregados; filas originales como evidencia y `complete`/`warnings`. Clasifica filas por señales estructurales (perfil `/user/view.php`, clases `summary_assignfeedback_<plugin>`), no por etiquetas traducidas. Ver [entregas](entregas.md#devolución-del-docente).
  - **Verificado:** mediante MCP en siete tareas reales de cuatro materias: escalas («Aprobado», «Incompleto»), puntos sobre 100, comentarios de uno y varios párrafos, tarea sin comentarios y dos tareas sin devolución (`available=false`). Pruebas locales con fixtures sintéticas. El 11 de noviembre de 2026 se repitió mediante MCP en seis tareas entregadas de Bases de Datos No SQL, todas sin calificar (`available=false`, con sus archivos entregados), y en una tarea con nota sobre 100 de otra materia.
  - **Pendiente:** archivos devueltos (`assignfeedback_file`), anotaciones PDF (`assignfeedback_editpdf`) y rúbricas o guías no aparecieron en las tareas inspeccionadas; se detectan y se declaran incompletas, pero su extracción no se verificó. Un comentario resumido devuelve `full_view_url` sin seguirlo. Sin devolución visible no se distingue «sin calificar» de «no publicada».
  - **Cierre:** distingue archivos enviados de archivos devueltos y enlaza sus fuentes; las anotaciones de PDF o rúbricas se declaran incompletas si no pueden extraerse.

- [ ] **F30 — Consultar asistencia propia.** **P2 · Explorar.**
  - Inspeccionar sesiones y estados del módulo `attendance`; los eventos del calendario no prueban presencia ni ausencia.
  - **Cierre:** lista estados propios y sus fechas; calcula porcentajes solo si hay reglas y denominadores verificables. Registrar asistencia sería otra escritura y requiere un alcance propio.

- [ ] **F31 — Consultar progreso y finalización de actividades.** **P2 · Explorar.**
  - Comprobar si las materias muestran seguimiento de finalización y qué indicadores habilita cada una.
  - **Cierre:** diferencia finalización automática, manual y no configurada, sin tratar “visto” como aprobado ni marcar actividades por leerlas.

## F. Comunicación

- [x] **F32 — Leer avisos, foros y discusiones.** **P1 · Implementada y verificada.**
  - Pasar de enlaces de entrada a listados paginados de discusiones, mensajes y adjuntos, comenzando por avisos de la cátedra.
  - Implementación (4 de noviembre de 2026): `list_forum_discussions` y `get_forum_discussion`, documentadas en [foros](foros.md). Evidencia real en foros de Avisos: 24 discusiones de Programación Concurrente, foro vacío de Probabilidad, mensajes anidados y rechazo de foros y discusiones de otra materia.
  - **Estado de lectura:** los cuatro foros inspeccionados no tienen columna de no leídos ni elementos `.unread`, por lo que no se observó seguimiento de lectura. Moodle registra igualmente la visita.
  - **Variantes pendientes:** recorrer páginas, que se detectan pero no se observaron (la mayor lista tuvo 45 filas), y verificar adjuntos en un mensaje real.
  - **Cierre satisfecho:** conserva foro, discusión, autor visible, fecha y orden; informa paginación pendiente; se diagnosticó el estado de lectura.

- [ ] **F33 — Consultar notificaciones y no leídas.** **P2 · Explorar.**
  - Inspeccionar el centro de notificaciones enlazado desde Dashboard y cursos, con filtros y paginación.
  - **Cierre:** devuelve contenido y destino de la notificación; distingue leer de marcar como leída y no incluye preferencias ni controles como si fueran notificaciones.

- [ ] **F34 — Leer conversaciones seleccionadas.** **P2 · Explorar.**
  - Inspeccionar mensajería y sus permisos para listar conversaciones y leer la elegida, sin extraer una agenda completa de personas.
  - **Cierre:** destinatario y conversación inequívocos, paginación y adjuntos si existen; cualquier cambio automático de lectura queda documentado.

- [ ] **F35 — Publicar o responder en foros y mensajes.** **P3 · Explorar.**
  - Ampliación opcional posterior a F32 y F34, con destinatario, texto y adjuntos concretos.
  - **Cierre:** solo envía por pedido explícito y confirma la publicación mediante evidencia posterior; una consulta, un aviso o contenido leído nunca autoriza responder automáticamente.

## G. Otros módulos del campus

- [ ] **F36 — Consultar información de cuestionarios.** **P2 · Explorar.**
  - Leer disponibilidad, fechas, intentos permitidos e historial o resultados visibles, después de inspeccionar `quiz`.
  - **Cierre:** consulta sin iniciar ni enviar intentos y sin asumir acceso a preguntas o revisiones restringidas. Resolver exámenes automáticamente no forma parte de este pendiente.

- [ ] **F37 — Leer consultas y encuestas internas.** **P2 · Explorar.**
  - Inspeccionar `choice` y `feedback`: instrucciones, disponibilidad y estado de respuesta propio cuando pueda consultarse.
  - **Cierre:** cada módulo conserva su semántica; no se deduce el formulario a partir de un evento de cierre ni se envían respuestas durante la inspección.

- [ ] **F38 — Responder consultas o encuestas por pedido explícito.** **P3 · Explorar.**
  - Ampliación opcional de F37 para respuestas elegidas por el usuario en formularios compatibles.
  - **Cierre:** valida opciones, identidad y posibilidad de modificar respuestas; confirma el resultado sin confundir una respuesta anónima con una verificable nominalmente.

- [ ] **F39 — Gestionar archivos privados del usuario.** **P3 · Explorar.**
  - Inspeccionar el bloque `private_files` y su gestor. El helper de carga podría reutilizarse, pero el destino no es una tarea.
  - **Cierre:** listado, descarga y carga claramente separados de entregas; límites y operaciones de modificación comprobados para ese gestor.

- [ ] **F40 — Evaluar lectores para módulos adicionales.** **P3 · Explorar.**
  - Relevar libros con capítulos, wikis, bases de datos, lecciones u otros módulos solo si aparecen en las materias elegidas. Su existencia en Moodle no demuestra que estén habilitados aquí.
  - **Cierre:** inventario de tipos realmente encontrados y decisión documentada sobre soporte o exclusión; no se publica una herramienta para un módulo que no se pudo inspeccionar.

## H. Confiabilidad y mantenimiento del MCP

- [ ] **F41 — Coordinar límites de solicitudes entre servicios.** **P0 · Parcial.**
  - Unificar información de HTTP 429, Retry-After, presupuesto y espera entre login, inventarios, descargas y cargas. Existen controles locales, pero no una coordinación general.
  - **Cierre:** lecturas con esperas acotadas e información accionable; ninguna escritura se repite a ciegas. La pausa de 90 segundos que permitió la prueba del TP 6 no se convierte en garantía universal.

- [ ] **F42 — Recuperar sesión o navegador de forma controlada.** **P1 · Parcial.**
  - Detectar sesión vencida o proceso caído y ofrecer recuperación y cierre explícitos. La sesión compartida y su cierre al terminar ya existen.
  - Avance (4 de noviembre de 2026): `CampusSession` cierra Lightpanda tras 60 segundos sin actividad (configurable), lo reabre bajo demanda y reemplaza un proceso caído antes de cada operación. Una carga temporal retiene la sesión hasta entregarla o hasta que venza el recibo. Evidencia real, solo lectura, con cliente MCP y 5 segundos de inactividad: cierre sin procesos restantes, reapertura y recuperación tras matar el proceso, unos 8 segundos cada una. La retención solo tiene pruebas locales. Sigue pendiente la recuperación si el navegador cae en medio de una operación y una herramienta de estado. El `LOGIN_BROWSER_ERROR` intermitente se debía a picos de latencia del campus, de hasta 22,8 segundos también con `curl`, que superaban los límites de 10 segundos de `goto` y de 15 y 8 segundos del binario (`OperationTimedout`). Los tres pasaron a 30 segundos y el log registra el tipo de fallo.
  - **Cierre:** una lectura puede recuperar acceso con presupuesto acotado; una escritura interrumpida primero reconcilia su resultado. Las credenciales rechazadas no provocan bucles de login.

- [ ] **F43 — Paginar y continuar inventarios grandes.** **P1 · Parcial.**
  - Ofrecer filtros de expansión y continuación verificable al alcanzar límites. Hoy se informan `complete`, advertencias y URLs pendientes, pero no existe un mecanismo público de continuación.
  - **Cierre:** salida acotada con procedencia y estado; continuar no pierde secciones ni convierte pendientes en éxito. Revalidar pertenencia y disponibilidad de cada destino.

- [ ] **F44 — Informar progreso y cancelación de operaciones largas.** **P2 · Parcial.**
  - Mostrar avance en recorridos y transferencias, manteniendo limpieza y acceso serializado a la página. Ya existen timeouts, lock y protección de algunas fases de escritura.
  - **Cierre:** cancelar limpia temporales o devuelve un resultado incierto reconciliable; no deja una entrega aparentemente fallida que en realidad se reenviará. No escribir progreso en stdout fuera del protocolo MCP.

- [x] **F45 — Publicar el estado real de cada capacidad.** **P1 · Implementada y verificada.**
  - `get_server_info` reemplaza `stage="calendar"` y `campus_features_ready` por `registered_tools`, `capabilities`, `undocumented_tools` y `pending_features_doc`. Cada capacidad declara efecto (`none`, `local_read`, `session`, `campus_read`, `local_write`, `campus_write`), nivel de evidencia (`local_tests`, `campus_partial`, `campus_verified`), fecha de verificación real, alcance, límites, IDs relacionados de este inventario y documentación.
  - El catálogo vive en `services/capabilities.py`. La herramienta consulta el registro del servidor en cada llamada: no anuncia herramientas ausentes, y una herramienta registrada sin entrada aparece en `undocumented_tools`.
  - **Evidencia:** 1 de noviembre de 2026, pruebas locales: el catálogo coincide exactamente con las herramientas registradas; el efecto declarado coincide con las anotaciones MCP de lectura, mundo abierto e idempotencia; las fechas son coherentes con el nivel; los documentos y los IDs citados existen. Llamada por MCP stdio al entrypoint: 10 herramientas, 5 verificadas en el campus, 3 parcialmente y 2 solo locales. No requiere sesión del campus.
  - **Cierre satisfecho:** `get_server_info`, el README y este documento coinciden con las herramientas registradas y distinguen pruebas locales, verificación parcial y verificación completa. Mantener el catálogo en cada cambio de capacidad. Quitar `stage` y `campus_features_ready` es un cambio incompatible del contrato 0.1.0, registrado en F48.

- [ ] **F46 — Hacer reproducibles instalación y controles.** **P1 · Parcial.**
  - Verificar un clon limpio con Python global y dependencias declaradas; automatizar controles disponibles como lint y formato. Mantener explícito que los tests locales están ignorados.
  - **Cierre:** comandos documentados y ejecutables sin `.venv`, credenciales ni archivos privados. No diseñar CI que dependa de tests ausentes ni agregarlos forzadamente contra la preferencia vigente.

- [ ] **F47 — Unificar diagnósticos seguros y errores recuperables.** **P2 · Parcial.**
  - Homogeneizar códigos, categoría de fallo, operación afectada, alcance parcial y próximo paso. Ya hay códigos de dominio y ocultamiento de secretos.
  - **Cierre:** el cliente distingue sesión vencida, acceso denegado, recurso ausente, límite y escritura incierta sin recibir HTML privado, URLs secretas o excepciones crudas.

- [ ] **F48 — Definir compatibilidad y evolución de los contratos MCP.** **P2 · Parcial.**
  - Documentar qué campos son estables, cómo se agregan capacidades y cómo se anuncian cambios incompatibles. Conservar respuestas tipadas y anotaciones coherentes con los efectos reales.
  - Primer cambio incompatible registrado (F45, 1 de noviembre de 2026): `get_server_info` dejó de devolver `stage` y `campus_features_ready`. Los consumidores deben leer `capabilities` y `registered_tools`.
  - **Cierre:** ejemplos y contratos públicos coinciden con el servidor; agregar una capacidad no rompe consumidores existentes sin una migración documentada.

- [ ] **F49 — Mantener una guía local del año y de sus fechas.** **P1 · Parcial.**
  - La skill `/campus-init` (`.claude/skills/campus-init/`) recorre las materias de un año y genera `.local/campus/<año>/guia.md` y `fechas.json`. Extrae fechas de cronogramas y enunciados con su origen y confianza, conserva los conflictos entre fuentes y borra cada documento tras leerlo, solo por la ruta devuelta por `download_resources`.
  - **Evidencia:** 4 de noviembre de 2026, helper `campus_docs.py` probado con archivos sintéticos: extracción de XLSX, DOCX y PPTX, formatos no admitidos y rechazo de borrados fuera de `downloads/`, por symlink o por `..`. La extracción de PDF y XLSX se aplicó en forma manual sobre cronogramas reales durante una consulta previa. Primera ejecución real el mismo día con `/campus-init 2026`, solo lectura: 13 materias, 55 fechas, 18 documentos PDF y XLSX leídos y borrados, 15 vacíos declarados y ningún temporal restante. Detectó el día de semana erróneo de Seminario y que el enunciado del TP 6 confirma el campus frente al cronograma. Probabilidad, en formato `onetopic`, quedó con `complete=false` por un enlace externo pendiente.
  - **Pendiente:** comprobar una consulta posterior resuelta con la guía, lectura de avisos y etiquetas (F32, F14) y lectura de documentos en memoria desde el MCP, sin escribir en disco.
  - **Cierre:** una ejecución real genera ambos archivos, declara sus vacíos, no deja documentos temporales y una consulta posterior se resuelve usando la guía.

- [ ] **F50 — Centralizar la traducción de excepciones a errores MCP.** **P1 · Falta.**
  - Cada módulo de `tools/` repite el mismo par `except (<errores de dominio>) … except Exception …` (12 bloques en 7 archivos). Crear un manejador global único, por ejemplo un decorador o envoltorio aplicado al registrar las herramientas, que traduzca los errores de dominio a `ToolError` y asigne el código interno de cada área sin `if`/`else` por herramienta.
  - Conservar los mensajes y códigos actuales (`SUBMISSION_INTERNAL_ERROR`, `UPLOAD_LOCAL_FILE_ERROR` y equivalentes), el aviso de verificar el estado antes de repetir escrituras y el ocultamiento de excepciones crudas. Es la base de F47.
  - **Cierre:** ningún módulo de `tools/` contiene `try`/`except` propio para traducir errores; las pruebas locales cubren un error de dominio, uno de sesión y uno inesperado por área, con los mismos textos que hoy.

## Orden recomendado

1. **Estabilizar lo ya utilizado:** F41 y las validaciones F12, F13 y F26 (F45 completada el 1 de noviembre de 2026). No bloquea en paralelo las mejoras pequeñas de descubrimiento.
2. **Completar la consulta académica básica:** F01–F05, F07–F10 y F19. El objetivo es poder preguntar por una materia y sus trabajos sin aportar IDs o interpretar enlaces manualmente.
3. **Incorporar información cotidiana faltante:** lectura de páginas, calificaciones, devoluciones y avisos (F14, F28, F29 y F32). Inmediatamente después de F29, centralizar el manejo de excepciones de las herramientas (F50).
4. **Ampliar materiales y entregas:** búsqueda, lotes, metadatos, edición y reconciliación (F06, F15–F18, F20–F27), según necesidad.
5. **Evaluar otras áreas:** Timeline, seguimiento, comunicación y módulos opcionales tras inspeccionar sus pantallas y permisos.

Esta lista es una propuesta priorizada de trabajo, no una autorización para ejecutar las funcionalidades de escritura ni una promesa de que todos los módulos estarán disponibles. Al completar una funcionalidad, conservar su ID y registrar qué se verificó y qué variantes continúan pendientes.
