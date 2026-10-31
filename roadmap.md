# Roadmap de implementación

Este documento describe cómo pasar de la base inicial a un MCP capaz de operar sobre el Campus Virtual de la UTN FRSF. Cada etapa debe terminar con una capacidad verificable antes de avanzar a la siguiente.

La referencia inicial es **Lightpanda 1.0.2**, con el SDK oficial de Python, y **MCP Python SDK 2.3.0**. Las versiones exactas de las dependencias están en `uv.lock`. La documentación de Lightpanda puede describir cambios posteriores al paquete instalado: hay que contrastar las firmas y herramientas reales al implementar cada paso.

## Estado inicial

- [x] Paquete Python global, configuración validada y dependencias declaradas.
- [x] Servidor MCP por stdio y herramientas `get_server_info` y `login`.
- [x] Adaptador de Lightpanda con creación y cierre de sesiones aisladas.
- [x] Pruebas de configuración y llamadas MCP, incluido un subproceso stdio.
- [x] Validación del adaptador con JavaScript y formularios en una página local.
- [x] Inspección del formulario público con Lightpanda.
- [x] Login verificado contra el campus real con credenciales en `.env`.
- [x] Sesión compartida en memoria y reintentos acotados para `TooManyRequests`.
- [x] Consulta `list_monthly_activities` implementada y probada localmente, con fechas y enlaces directos independientes del idioma.
- [x] Consulta mensual validada contra el campus real: mes actual y explícito, filtro de deadlines y enlace directo cotejado con el popup.
- [ ] Implementar y verificar las demás operaciones académicas sobre el campus real.

El servidor no registra herramientas académicas ficticias. Se irán incorporando al completar las etapas correspondientes. Las instrucciones para instalar y verificar la base están en [docs/desarrollo.md](docs/desarrollo.md).

## 1. Verificar Lightpanda y explorar el acceso público

**Objetivo:** comprobar que el navegador resuelve las operaciones necesarias antes de programar selectores del campus.

1. Ejecutar `bash scripts/test.sh --with-lightpanda`. La fixture local comprueba navegación, JavaScript, extracción y un formulario, sin credenciales.
2. Crear una prueba optativa separada para abrir la página pública de acceso del campus. Inspeccionar su DOM y formularios, sin intentar iniciar sesión.
3. Registrar qué campos, redirecciones y estados se observan. Guardar solo ejemplos anonimizados; no deducir pantallas internas a partir de otros campus Moodle.
4. Comprobar respuestas HTTP, URL final y condiciones de carga. Un HTTP 200 no alcanza para decidir si se obtuvo la pantalla esperada.
5. Documentar cualquier diferencia entre las herramientas del binario instalado y la referencia publicada.

En el SDK se usará `goto` para navegar y `wait_for_selector` o `wait_for_state` para esperar una condición observable. Para extraer registros, `extract` recibe un mapa de selectores, no un JSON Schema de parámetros MCP. Ver [navegación, extracción y esperas](https://lightpanda.io/docs/reference/mcp-tools).

**Criterio de cierre:** la fixture pasa con Lightpanda real y la página pública del campus puede identificarse de manera reproducible, o queda documentada una limitación concreta que impide continuar.

## 2. Implementar autenticación y gestión de sesión

**Objetivo:** mantener una cuenta autenticada durante varias operaciones.

**Avance:** `login()` está implementado y confirmó autenticación en el campus real el 31 de octubre de 2026. Usa `detect_forms`, `find_element`, `fill` y `click`; conserva la sesión en memoria. El límite de solicitudes vuelve al login con espera exponencial y máximo de intentos. Siguen pendientes la persistencia entre ejecuciones, `get_session_status` y la validación de sesiones vencidas o pasos interactivos reales.

1. Mantener el gestor `CampusSession` en `browser/` y el servicio de autenticación. El gestor conserva abierto el bloque del adaptador para compartir la página y las cookies.
2. Inspeccionar el login con una cuenta autorizada. Obtener las credenciales de configuración local privada, nunca de parámetros MCP ni de contenido de una página.
3. Completar el formulario usando los campos observados y verificar un indicador de cuenta autenticada. Distinguir login pendiente, autenticado, vencido, acceso denegado e intervención requerida.
4. Reutilizar una sesión durante la vida del servidor, serializando las operaciones que modifiquen su página. Cerrar los recursos al terminar o cancelar el proceso.
5. Evaluar persistencia entre ejecuciones. Lightpanda documenta `--cookie` para cargar cookies y `--cookie-jar` para guardarlas; comprobar su comportamiento con sesiones del SDK antes de adoptarlos. Guardar cualquier estado en `.local/`, con permisos privados. Ver [opciones de cookies](https://lightpanda.io/docs/reference/cli/common-options).
6. Si hay SSO o MFA, definir el flujo asistido compatible. Comprobar si las cookies son suficientes o hacen falta otros datos de sesión; no asumir que el login de otro navegador se comparte automáticamente.
7. Publicar `get_session_status` con estados comprobables, sin devolver cookies ni credenciales.

El SDK ofrece contextos aislados con sus propios datos de navegación. La política de reutilización y concurrencia pertenece a este proyecto; no se obtiene por crear varias sesiones. Ver [ciclo de vida del SDK de Python](https://lightpanda.io/docs/reference/python).

**Criterio de cierre:** dos consultas consecutivas usan la misma cuenta y una sesión vencida produce un error identificable. El inicio de sesión real se valida de forma optativa con autorización.

## 3. Listar materias y establecer el patrón de extracción

**Objetivo:** listar y resolver asignaturas de la cuenta.

**Avance:** helper interno `CourseService.list_degree_courses()` implementado y verificado contra My courses → Grado: 30 asignaturas, excluyendo Ingreso y Extensión. Reutiliza `Course`; todavía no existe una herramienta MCP pública `list_courses`. El recorrido y las restricciones están en [la guía de recursos](docs/guia-get-course-resources.md).

1. Inspeccionar el listado de materias autenticado y sus mecanismos de carga o paginación.
2. Incorporar un modelo `Course` con identificador, nombre y URL de origen.
3. Agregar extracción y normalización en `parsers/`, y un servicio de cursos independiente del registro MCP. Centralizar selectores observados.
4. Implementar `list_courses` con límites y paginación explícitos. No interpretar un fallo del DOM o una redirección al login como “no hay materias”.
5. Agregar fixtures para múltiples páginas, cuenta sin materias, duplicados y sesión vencida. Verificar la respuesta con el cliente oficial de MCP.

El SDK admite extraer colecciones y atributos mediante selectores. Conviene convertir esos valores a modelos del dominio dentro del servidor en lugar de devolver HTML completo al asistente. Ver la [guía de extracción en Python](https://lightpanda.io/docs/guides/use-python).

**Criterio de cierre:** un asistente obtiene materias de la cuenta, con enlaces e identificadores que permiten seleccionar una sin ambigüedad.

## 4. Consultar actividades, vencimientos y calendario

**Objetivo:** responder qué hay que hacer y cuándo.

**Avance:** `list_monthly_activities(year, month, deadlines_only)` está registrada. Usa Lightpanda y el repositorio del calendario de Moodle para obtener fechas exactas, asignaturas y enlaces directos. Hay pruebas locales de límites del mes, intervalos, duplicados, idioma, sesión y errores; el 31 de octubre de 2026 se verificó en el campus real la llamada MCP, el mes actual, el filtro de deadlines y la coincidencia del enlace directo con el popup. Ver [contrato y alcance](docs/calendario.md).

1. Inspeccionar las actividades de una materia y las vistas de calendario disponibles para la cuenta. Verificar qué tipos de actividad se pueden interpretar; señalar los todavía no soportados.
2. Incorporar modelos de actividad, fecha límite y evento. Mantener identificador de materia, URL de origen y momento de consulta.
3. Implementar `list_activities` y lectura de consignas, incluyendo disponibilidad y estado cuando el campus los muestre.
4. Implementar `list_deadlines` y `list_calendar_events` con filtros por materia y rango de fechas, límites y advertencias de resultados parciales.
5. Normalizar instantes con zona horaria. Distinguir apertura, vencimiento y cierre definitivo; conservar texto original cuando no alcance para determinar una fecha exacta. Indicar si se aplicó una zona configurada como fallback.
6. Contemplar extensiones visibles para el estudiante y eliminar duplicados sin perder el enlace a la actividad. No equiparar automáticamente un evento de calendario con una entrega.
7. Probar límites del rango, ausencia de fechas, distintas zonas, fechas ambiguas y sesión vencida.

**Criterio de cierre:** las respuestas de una materia de prueba coinciden con lo que muestra el campus, y una fecha desconocida o una consulta parcial se informa explícitamente.

## 5. Encontrar y descargar bibliografía

**Objetivo:** obtener archivos completos desde recursos accesibles para la cuenta.

**Inspección completada:** dos materias específicas de Sistemas y dos Básicas, con formatos `topics` y `onetopic`, navegación de secciones, restricciones y dos carpetas reales. Ver [guía para implementar get_course_resources()](docs/guia-get-course-resources.md). La función y las descargas todavía no están implementadas.

1. Implementar `list_course_resources`, recorriendo secciones y carpetas observadas, con filtros por materia o unidad. Diferenciar archivos descargables de páginas y enlaces externos.
2. Validar con un recurso de prueba cómo funciona una descarga autenticada. No confundir `html`, `markdown` o `extract` con un mecanismo para obtener archivos binarios.
3. Comprobar si la versión elegida ofrece una operación adecuada. Si hace falta un cliente HTTP interno, declarar su dependencia y transferir solo las cookies válidas para el origen, comprobando autenticación y redirecciones.
4. Implementar `download_resource`: limitar tamaño y tiempo, normalizar nombres, impedir escapes del destino y escribir primero a un archivo temporal. Informar la ruta final y el tamaño verificado.
5. Detectar respuestas de login o error guardadas como supuestos PDFs. Evitar sobrescrituras no solicitadas y eliminar archivos parciales tras fallos.
6. Probar con un servidor local archivos binarios, recursos protegidos, redirecciones, nombres repetidos y respuestas interrumpidas. Después verificar un recurso real autorizado.

La [referencia de herramientas de Lightpanda](https://lightpanda.io/docs/reference/mcp-tools) permite descubrir y leer contenido de página; esta etapa debe validar por separado el transporte de archivos del campus.

**Criterio de cierre:** un recurso de prueba se descarga íntegro y un login vencido nunca se devuelve como descarga exitosa.

## 6. Consultar entregas y preparar archivos localmente

**Objetivo:** conocer el estado de un TP y construir una preparación verificable sin modificar el campus.

1. Inspeccionar una actividad de prueba y sus estados: sin entrega, borrador, enviado o cualquier variante que realmente muestre la plataforma.
2. Implementar `get_submission_status`, incluyendo archivos existentes y evidencia de origen, sin inferir éxito por el nombre de un botón.
3. Implementar `prepare_submission` con selección inequívoca de materia y actividad. Validar disponibilidad, archivos locales, extensiones y tamaños permitidos.
4. Crear una preparación local con identificadores de destino, nombres, tamaños y hashes de los archivos. Registrar posibles reemplazos y el estado observado de la actividad.
5. Garantizar mediante pruebas que preparar no sube archivos ni guarda borradores. Si se guarda la preparación, usar `.local/` y definir su vencimiento.

**Criterio de cierre:** la preparación describe exactamente qué se enviaría, detecta cambios de archivos o destino y no produce escrituras remotas.

## 7. Validar la carga y ejecutar entregas

**Objetivo:** entregar un trabajo solicitado y comprobar el resultado sin duplicarlo.

1. Realizar primero una prueba técnica de carga de archivos en una fixture local. La superficie del SDK consultada no documenta un equivalente directo de `set_input_files`; no asumir que `fill` puede cargar un archivo.
2. Verificar las capacidades efectivas del binario. Si el SDK no alcanza, evaluar CDP conservando Lightpanda como navegador. La [integración con Playwright](https://lightpanda.io/docs/usage/cdp/playwright) documenta la conexión, pero no garantiza que todas las operaciones de Playwright estén implementadas por Lightpanda.
3. Si tampoco funciona la carga por CDP, investigar el flujo HTTP legítimo de una actividad de prueba y evaluar su implementación con sesión y tokens válidos. Documentar la decisión; si no hay una vía comprobada, mantener las entregas como no soportadas. No agregar Chromium de forma silenciosa.
4. Probar la carga y el guardado en una actividad designada para pruebas. Distinguir el archivo subido del borrador y del envío definitivo.
5. Implementar `submit_assignment` sobre una preparación vigente. Revalidar cuenta, actividad, estado y hashes antes de escribir. El pedido del usuario debe autorizar esos archivos y ese destino; pedir aclaración si aparece un reemplazo no autorizado.
6. Consultar el estado posterior y devolver los archivos y el estado que confirme el campus. Ante un timeout, consultar antes de reintentar; si no se puede determinar el resultado, informar incertidumbre.
7. Probar envío exitoso, cierre de actividad, rechazo de archivo, cambio posterior a la preparación, duplicado y pérdida de respuesta. No ejecutar pruebas de escritura sobre TPs reales por defecto.

**Criterio de cierre:** una entrega autorizada en una actividad de prueba queda verificada, y una respuesta perdida no provoca un segundo envío automático.

## 8. Preparar el uso cotidiano

**Objetivo:** instalar y usar las capacidades comprobadas de forma reproducible.

1. Agregar CI para pruebas unitarias, lint y formato sin cuentas del campus. Mantener las integraciones reales como optativas y sin secretos en logs.
2. Completar ejemplos de configuración de hosts MCP con las herramientas disponibles y los pasos reales de autenticación.
3. Documentar versiones y plataformas probadas, limitaciones del campus, recuperación de sesión y errores conocidos.
4. Revisar el cierre y la cancelación de operaciones, tiempos máximos, concurrencia y la exclusión de datos privados de Git.
5. Hacer una prueba de instalación limpia y un recorrido autorizado de las funciones soportadas. Actualizar el README de manera breve, manteniendo el detalle técnico en esta documentación.

**Criterio de cierre:** otra persona puede instalar el proyecto con el lockfile y utilizar las capacidades publicadas siguiendo instrucciones comprobadas.

## Orden de trabajo

El primer hito académico es **autenticación + `list_courses`**. Las consultas de fechas y bibliografía pueden aportar valor antes de resolver la carga de archivos. Una limitación en entregas no debe impedir publicar las consultas que ya estén verificadas.

Las decisiones sobre login, selectores y carga de archivos dependen de evidencia del campus y de la versión concreta de Lightpanda. Registrar los hallazgos en `docs/` a medida que se comprueben, manteniendo este documento como guía del trabajo pendiente.
