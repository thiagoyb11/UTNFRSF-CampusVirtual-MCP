# Carga de archivos y entregas

## Diseño inicial y alcance

La estructura y el contrato se documentaron antes de implementar el código. El flujo separa preparación local, carga temporal, guardado y confirmación adicional cuando exista. Guardar puede entregar directamente: el resultado siempre depende del estado posterior del campus.

La implementación académica soporta tareas Moodle `assign`. El helper `FileUploadHelper.upload_files(files)` puede reutilizarse con otros gestores compatibles, pero otros módulos requieren inspeccionar sus formularios antes de exponer su operación de entrega. No se reemplazan entregas existentes ni se suben carpetas normales; pueden enviarse comprimidas como ZIP. Se admite cualquier archivo que permita la actividad, respetando sus límites.

Se usa Lightpanda para autenticar, consultar y comprobar la cuenta y el destino. Los tokens, cookies y formularios privados permanecen en memoria; no aparecen en respuestas MCP ni en esta documentación. No se sustituye Lightpanda por Chromium.

## Estructura observada

Inspeccionada el 31 de octubre de 2026 en el TP 6 de Análisis Numérico:

- Vista `/mod/assign/view.php?id=<activity_id>`, `body#page-mod-assign-view` y `M.cfg.courseId` para verificar materia. Un formulario GET con `id` y `action=editsubmission` ofrece edición.
- Edición `body#page-mod-assign-editsubmission`: formulario POST con `id`, `userid`, `lastmodified`, `action=savesubmission`, `sesskey`, `_qf__mod_assign_submission_form`, `files_filemanager` y botón `submitbutton`. El ID del draft es distinto del ID de actividad.
- Gestor `[data-fieldtype="filemanager"]`, `.filemanager`, `.fp-restrictions`. La llamada inline `M.form_filemanager.init(Y, {...})` contiene `itemid`, límites, tipos, contexto y repositorios.
- El `object[data]` en `<noscript>` apunta a `/repository/draftfiles_manager.php`, con curso, contexto, itemid y token. Su URL es privada.
- Los repositorios se identifican mediante `type=upload` y un ID dinámico. No se fijan IDs ni se depende del idioma del selector.
- El TP 6 admitía un archivo de **20971520 bytes (20 MiB)** y cualquier tipo. Estos límites no son valores globales.

## Transporte de archivos

Lightpanda 1.0.2 no expone una operación nativa de carga de archivos locales; `fill` sobre el input real no pudo seleccionarlos. Se implementó explícitamente el helper con sesión y contexto observados.

### API AJAX del campus

Se verifica la presencia del contrato en `/repository/filepicker.js` del propio campus. El destino es `/repository/repository_ajax.php?action=upload`; `action` no se duplica en el cuerpo. Se envían `repo_id`, `p`, `page`, `env`, `sesskey`, `client_id`, `itemid`, `maxbytes`, `areamaxbytes`, `ctx_id`, `savepath`, `title`, `author`, `license`, los tipos explícitos cuando existan y `repo_upload_file`.

La carga usa multipart HTTP en streaming con las cookies de Lightpanda, su User-Agent real, Origin del campus, Referer de la página de edición y `X-Requested-With: XMLHttpRequest`. Los parámetros `course`, `subdirs` y `maxfiles` del gestor sin JS no se copian al API AJAX; curso y límites se validan localmente. Los tipos vacíos admiten cualquier archivo; no se inventa un campo `accepted_types=*` al transferir.

### Formulario oficial sin JavaScript

Cuando no se confirma la API, el helper sigue los enlaces reales del gestor a `filepicker.php?action=plugins` y descubre un formulario POST multipart con `repo_upload_file` y `action=upload`. Conserva sus campos y verifica que siga ligado al mismo contexto.

Este formulario puede transferirse con `File`/`FormData` dentro de Lightpanda. Cuando está disponible `DataTransfer`, se asigna un `FileList` a un input real y se envía mediante `click`. Los bytes se leen en fragmentos de 256 KiB. Si esas APIs no están disponibles, se utiliza el transporte HTTP explícito. La elección ocurre antes de escribir; no se cambia de transporte tras rechazar un POST. Esta vía antigua se probó localmente, pero no completó una carga real del campus.

Referencias: [SDK de Lightpanda](https://lightpanda.io/docs/reference/python), [cliente Moodle](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/repository/filepicker.js), [formulario sin JS](https://github.com/moodle/moodle/blob/MOODLE_405_STABLE/repository/filepicker.php).

## Herramientas MCP

| Función | Efecto |
| --- | --- |
| `get_submission_status(course_id, activity_id)` | Consulta estado, archivos y evidencia original de una tarea. |
| `prepare_submission(course_id, activity_id, files)` | Valida rutas y crea manifiestos con nombre, tamaño y SHA-256. Solo realiza I/O local. |
| `upload_files(course_id, activity_id, files)` | Carga temporalmente y comprueba bytes; devuelve `upload_id`. No guarda la entrega. |
| `submit_assignment(upload_id, finalize=False, accept_statement=False)` | Guarda y comprueba la entrega. `finalize=True` completa la confirmación adicional observada; una declaración requiere aceptación explícita. |

```python
# IDs ficticios; preparación local:
prepare_submission(course_id=12, activity_id=34, files=["/ruta/trabajo.zip"])
# Carga temporal; devuelve un recibo:
upload_files(course_id=12, activity_id=34, files=["/ruta/trabajo.zip"])
# Guardado de esa entrega autorizada; puede enviarla directamente:
submit_assignment(upload_id="recibo_devuelto", finalize=False)
```

El helper interno recibe manifiestos preparados. El cliente MCP proporciona rutas de archivos, curso y actividad; no puede inyectar tokens ni endpoints. Los recibos duran 30 minutos, solo existen en el proceso que cargó los archivos y se limitan a 32 recibos recientes. Reiniciar el servidor los invalida.

## Validación y resultados inciertos

Se admiten entre 1 y 100 archivos regulares a nivel local, sujetos al máximo menor del campus. Cada archivo tiene un límite local de 200 MiB. Se rechazan carpetas, nombres duplicados y archivos modificados después de prepararlos. Se respetan cantidad, tamaño por archivo, tamaño total y tipos del formulario. Los grupos semánticos de tipos no normalizados fallan explícitamente con `UPLOAD_TYPES_UNSUPPORTED`.

Antes de escribir se comprueban cuenta, curso, actividad, formulario, estado y restricciones. Se rechazan tareas con archivos, borradores, envíos o texto existentes. Antes de guardar se revalidan estado, formulario y hashes del draft completo. Se conserva `lastmodified` para el control de concurrencia del campus, sin interpretarlo como prueba de entrega.

Después de cargar se consulta el **mismo itemid** y se descargan sus enlaces `/draftfile.php/...` para comparar nombre, tamaño y SHA-256. Después de guardar se consulta la tarea y se verifican los archivos finales. Un HTTP 200 o un clic no prueban una entrega.

Los estados `new`, `draft`, `submitted` y `reopened` se obtienen de clases estructurales. Sin entrega, Moodle deja la celda de estado sin clase propia: se devuelve `new` si no hay archivos y la fila de calificación trae `submissionnotgraded` o `submissiongraded`, comprobado el 4 de noviembre de 2026 en tareas reales calificadas y sin calificar. Si faltan esas señales o se contradicen, se devuelve `unknown` con la evidencia original. El resultado de guardar puede ser `saved`, `submitted` o `uncertain`. Un recibo ya procesado no vuelve a guardar automáticamente.

El draft temporal pertenece a la sesión de Moodle: tras `upload_files`, el navegador se retiene hasta entregar o hasta que venza el recibo, en lugar de cerrarse por inactividad. Si Lightpanda cae en ese intervalo, la nueva sesión no reutiliza la carga y `submit_assignment` no reenvía a ciegas.

Cada POST de escritura se intenta una sola vez. Ante pérdida de respuesta se reconcilia leyendo el estado; si sigue incierto, no se reenvía. HTTP 429 se informa sin repetir la escritura. Las lecturas GET admiten hasta dos esperas acotadas según Retry-After. Durante el diagnóstico hubo 429 incluso en consultas del selector; no se atribuyeron todos a un único campo o encabezado.

## Verificación real completada

El usuario autorizó expresamente cargar y guardar una entrega sintética en el **TP 6 de Análisis Numérico**, confirmó que Guardar envía la entrega y pidió no hacer commits hasta verificarla. También indicó que podía deshacer la prueba; no se retiró automáticamente. El usuario la retiró después y el 4 de noviembre de 2026 la tarea figuraba sin entrega.

La prueba se ejecutó mediante las herramientas MCP el 31 de octubre de 2026, con curso `7478` y actividad `455726`. Tras los HTTP 429 del diagnóstico, se mantuvo una sesión preparada, se esperaron 90 segundos y se realizó una única carga:

- Archivo `codex-prueba-entrega.txt`, **125 bytes**, sin resolución académica del TP.
- `upload_files`: carga temporal verificada por tamaño y SHA-256.
- `submit_assignment(finalize=False)`: estado **`submitted`**, `files_verified=true` y evidencia **«Submitted for grading»**.
- Una consulta posterior independiente dentro del mismo proceso confirmó el archivo y el estado enviado.

La pausa pertenece a esta comprobación; no se afirma que 90 segundos resuelvan cualquier límite ni se incorporó un reenvío automático de escrituras. No se hicieron commits. Borradores y confirmaciones adicionales se verificaron en fixtures, no en esta tarea real.

## Código y controles locales

- `parsers/submissions.py`: preparación, formularios, configuración, restricciones y enlaces del draft.
- `browser/submissions.py`: estado y acciones de la tarea.
- `browser/uploads.py`: HTTP autenticado, multipart, helper y comprobación de bytes.
- `browser/file_input.py`: puente de archivos a las APIs del navegador y descubrimiento del cliente AJAX.
- `services/submissions.py`: carga, recibos, guardado y reconciliación.
- `tools/submissions.py`: registro de las cuatro herramientas.

Se ejecutaron **138 pruebas aprobadas**; 13 integraciones optativas omitidas por defecto. Las **tres** pruebas optativas de transporte con Lightpanda contra un servidor sintético aprobaron por separado. Se comprobaron tipos variados, carpetas rechazadas, restricciones, cambios concurrentes, recibos vencidos, borradores, guardado que envía directamente, declaración explícita y respuestas perdidas sin duplicar POSTs. Ruff verificó lint y formato. Los tests permanecen locales e ignorados según la preferencia del proyecto.
