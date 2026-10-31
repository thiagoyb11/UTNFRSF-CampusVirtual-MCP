# Enlaces de una asignatura

`get_course_resources(course_id)` devuelve los enlaces del contenido de una asignatura de **My courses → Grado**. Incluye actividades de entrega, recursos, archivos PDF/ZIP y otros formatos, enlaces externos y enlaces embebidos en resúmenes o etiquetas. Conserva la sección, el módulo y la página donde se encontró cada enlace.

En Inspector, seleccioná `get_course_resources` e indicá el ID que aparece en la URL de la materia (`/course/view.php?id=...`). Ejemplo con un ID ficticio:

```json
{"course_id": 12}
```

El ID debe pertenecer al listado de Grado de la cuenta. Se reutilizan el login privado y la sesión de las demás herramientas. No se aceptan credenciales ni URLs arbitrarias como argumentos.

## Respuesta

- `course`: ID, nombre y enlace canónico de la materia.
- `links`: enlaces con `name`, `url`, `kind`, `section_index`, `module_id`, `module_type` y `source_url`.
- `total`: cantidad de registros de `links`.
- `sections`: ordinal e ID de sección, nombre disponible, URL, disponibilidad observada y si se visitó.
- `unlinked_activities`: actividades sin enlace, con su tipo y evidencia de disponibilidad. Incluye etiquetas sin enlace y actividades restringidas; no se inventan sus destinos.
- `fetched_at`: instante de consulta en UTC.
- `complete`, `pending_urls`, `warnings`: alcance efectivo del inventario.

`kind` distingue `assignment`, `resource`, `folder`, `activity`, `file`, `external` y `link`. Los enlaces de tareas abren la actividad de entrega y no prueban que haya una entrega pendiente. Un enlace a `/mod/resource/view.php` sigue siendo un acceso al recurso; se devuelve además el destino `/pluginfile.php/...` cuando se puede leer su página. `file` clasifica un destino observado por ruta/extensión; no certifica su MIME ni la integridad de una descarga.

Se deduplica por URL, sección y módulo. La misma URL en dos secciones conserva ambas procedencias; `total` cuenta esos registros. Los archivos con el mismo nombre y rutas distintas se conservan.

## Recorrido y límites

1. El helper existente valida la pertenencia del curso a Grado antes de abrirlo.
2. Se leen todas las secciones presentes de `topics`. Para `onetopic`, se descubren y recorren secuencialmente los enlaces de pestañas y de la sidebar del curso. Se respetan pestañas deshabilitadas aunque tengan `href`.
3. Se extraen enlaces de todas las actividades y de los resúmenes, sin filtrar por títulos como “Bibliografía” o “Material”. Los nombres repetidos no identifican una sección.
4. Se amplían las páginas de módulos `resource`, `folder`, `assign`, `page` y `url`. En carpetas se incluyen todos los archivos presentes en el árbol HTML, incluidas rutas de subcarpetas. En tareas se leen enlaces de la consigna (`#intro` y `.activity-description`); se excluyen formularios y tablas de entregas personales.
5. Los GET de módulos se ejecutan en Lightpanda con cookies del mismo origen y `redirect: error`. Los destinos externos se devuelven como enlaces y no se visitan. Si un recurso URL redirige, se conserva el enlace original y se informa la página pendiente.

Para recursos se usa `forceview=1`, parámetro de lectura documentado en el [código de Moodle](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/mod/resource/view.php), para obtener la página con el enlace al archivo incluso cuando su modo de visualización habitual redirige a una descarga. Su compatibilidad en este campus queda pendiente de validación real; una respuesta inesperada produce resultado parcial, nunca una URL binaria inventada.

El inventario cubre el contenido de secciones y esas páginas de módulos. Devuelve los enlaces de entrada a foros, cuestionarios y otros módulos, sin recorrer conversaciones, intentos, capítulos de libros ni sitios externos. No ejecuta descargas, cargas de archivos ni envíos. Omite anclas locales, esquemas distintos de HTTP(S) y URLs con credenciales o parámetros identificables como secretos.

Límites después de resolver el curso: 180 segundos, 500 páginas y 10000 registros. La extracción DOM admite hasta 5000 elementos por colección, y las páginas de módulos hasta 2 millones de caracteres de HTML. Un límite, timeout, formato inesperado o recurso sin resolver deja `complete=false`, advertencias y las URLs pendientes conocidas. Si no se puede comprobar la navegación de un curso `onetopic`, se indica la incertidumbre aunque su primera sección esté vacía.

`complete=true` significa que se terminó ese recorrido de contenido accesible, dentro del alcance anterior. No significa que se hayan accedido secciones restringidas ni validado los binarios. Los errores de sesión, acceso denegado y límite de solicitudes son explícitos y no se convierten en listas vacías.

## Implementación y comprobación

- `browser/resources.py`: selectores y lectura de páginas en Lightpanda.
- `parsers/resources.py`: normalización, clasificación y validación sin red.
- `services/resources.py`: recorrido secuencial, deduplicación y alcance parcial.
- `tools/resources.py`: contrato MCP tipado y errores seguros.

Se implementó sobre las [estructuras documentadas del campus](guia-get-course-resources.md). Las pruebas locales con snapshots sintéticos y el cliente MCP oficial cubren ambos formatos, secciones repetidas/deshabilitadas, restricciones, carpetas con nombres repetidos, archivos, tareas, expiración de sesión y resultados incompletos. También se ejecutaron los selectores sobre un DOM sintético con jsdom, sin sustituir Lightpanda como navegador del proyecto.

**Validación real, 31 de octubre de 2026:** la llamada `get_course_resources` mediante el cliente MCP oficial completó Análisis Numérico (`topics`): 9 secciones y 189 enlaces únicos, incluidos 6 enlaces de tareas, 8 carpetas y 137 archivos (111 PDF y 1 ZIP). Devolvió `complete=true`, sin pendientes ni advertencias. El resultado privado queda en `.local/`, fuera de Git. No se descargaron binarios ni se modificaron entregas. Quedan pendientes la comprobación integral de `onetopic` y del parámetro `forceview` de recursos individuales; esta materia no contenía módulos `resource`.

El intento anterior había fallado porque el entorno restringido impedía abrir el puerto local de Lightpanda; al repetirlo con acceso habilitado se pudo completar la consulta.
