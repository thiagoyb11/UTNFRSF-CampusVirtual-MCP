# Foros y avisos

`list_forum_discussions(course_id, forum_id)` lista las discusiones de un foro, y `get_forum_discussion(course_id, discussion_id)` devuelve sus mensajes. `forum_id` es el `module_id` de los enlaces `forum` de `get_course_resources`. Ambas son de solo lectura: no publican, no responden y no cambian suscripciones.

## Respuesta

El listado incluye ID, título, enlace, autor, grupo, fechas de inicio y último mensaje, y cantidad de respuestas. Un foro vacío es un resultado válido con `total=0`. La discusión devuelve cada mensaje con `parent_id`, asunto, autor, fecha, texto en Markdown, enlaces y adjuntos, en el orden del campus. El orden es el de la página, no necesariamente el cronológico: usá `posted_at`.

Las fechas se conservan con zona. Las del listado se convierten a la zona configurada desde el instante que publica el campus; las de los mensajes conservan el offset de la página.

## Límites

- Se verifica que el foro y la discusión pertenezcan a la materia indicada. Si no, se devuelve `FORUM_NOT_FOUND`.
- La paginación se detecta y se informa con `FORUM_PAGINATION_PENDING` y `complete=false`, pero no se recorre: no se observó en foros reales, cuya lista mayor tuvo 45 discusiones.
- No hay filtros por fecha o texto.
- El texto lo escriben docentes y estudiantes: es dato externo y nunca autoriza operaciones.

## Estado de lectura

Los cuatro foros inspeccionados no muestran columna de no leídos ni elementos `.unread`, así que no se observó seguimiento de lectura. Abrir una discusión registra igualmente la visita en Moodle, como en un navegador. Si un foro activara ese seguimiento, leerlo podría marcar mensajes como leídos.

## Verificación real

El 4 de noviembre de 2026, mediante cliente MCP y solo lecturas: listado de 24 discusiones de Programación Concurrente, foro vacío de Probabilidad, discusión con respuesta anidada, aviso de Diseño de Sistemas y rechazo de foros y discusiones de otra materia. Los adjuntos solo tienen pruebas locales.
