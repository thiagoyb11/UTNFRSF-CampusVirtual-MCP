# UTN FRSF · Campus Virtual MCP

Un servidor MCP para conectar asistentes de inteligencia artificial con el [Campus Virtual de la UTN Facultad Regional Santa Fe](https://campusvirtual.frsf.utn.edu.ar/).

Su objetivo es facilitar las tareas cotidianas del estudiante desde un asistente, usando su cuenta del campus.

> Proyecto en desarrollo. Incluye inicio de sesión, consulta mensual de actividades y listado de enlaces por asignatura y flujo de carga/entrega de tareas. La carga y entrega se verificaron en una tarea real autorizada.

`login()` usa las credenciales del `.env` privado. `list_monthly_activities()` devuelve JSON con las fechas, horarios, asignaturas y enlaces directos de las actividades del calendario. Podés probarlas en Inspector siguiendo la [guía de desarrollo](docs/desarrollo.md). Los parámetros y ejemplos de la consulta mensual están en [su guía](docs/calendario.md).

`list_courses()` devuelve las materias visibles en Grado, con ID, nombre y enlace, incluidos años anteriores. Permite encontrar la materia antes de consultar recursos o entregas. Ver [alcance y verificación](docs/materias.md).

`get_course_resources(course_id)` lista los enlaces de una materia, incluidas tareas, archivos y materiales de carpetas. Recorre secciones y devuelve el alcance de la consulta. Ver [uso y límites](docs/recursos.md); verificada en Análisis Numérico (`topics`); queda pendiente la validación integral de `onetopic`.

`get_section_content(course_id, section)`, `get_page_content(course_id, module_id)` y `get_folder_content(course_id, module_id)` leen como Markdown el texto publicado en secciones, páginas y descripciones de carpetas, incluidas tablas como los cronogramas.

`download_resources(course_id, module_id, urls)` descarga archivos de cualquier tipo del módulo indicado a `downloads/`, valida la transferencia y devuelve rutas, tamaños y hashes. Ver [uso y límites](docs/descargas.md).

`get_server_info()` indica qué herramientas están verificadas en el campus, cuáles solo parcialmente y cuáles tienen solo pruebas locales, con sus límites conocidos.

`get_assignment_feedback()` muestra la devolución del docente en una tarea: nota, fecha, quién corrigió, comentarios y archivos devueltos.

`get_submission_status()` consulta una tarea; `prepare_submission()` valida archivos localmente; `upload_files()` los carga a un área temporal; `submit_assignment()` guarda y, opcionalmente, finaliza la entrega. Ver [contrato y verificación](docs/entregas.md). La carga y el guardado se verificaron mediante MCP en el TP 6 de Análisis Numérico, con estado final enviado y comprobación de los bytes.

## Funciones previstas

- Consultar materias, actividades y consignas.
- Revisar fechas de entrega y eventos del calendario.
- Descargar bibliografía, apuntes y otros materiales.
- Enviar trabajos prácticos, consultar el estado de las entregas y leer sus devoluciones.

## Cómo funciona

El asistente recibe un pedido en lenguaje natural, como “¿qué trabajos vencen esta semana?” o “descargá la bibliografía de esta materia”. A través de MCP, solicita las acciones necesarias al servidor.

El servidor utiliza [Lightpanda](https://lightpanda.io/), un navegador que funciona en segundo plano, para acceder al campus, consultar información o realizar la acción solicitada. Luego devuelve el resultado al asistente.

El acceso se limita a las materias y recursos disponibles para la cuenta del estudiante.

## Estructura

```text
src/utnfrsf_campus_mcp/
├── server.py       # Arranque del servidor MCP.
├── config.py       # Configuración desde .env y variables de entorno.
├── models.py       # Modelos de datos.
├── browser/        # Integración con Lightpanda.
├── parsers/        # Extracción de información del campus.
├── services/       # Lógica de las funcionalidades.
└── tools/          # Herramientas expuestas al asistente.
docs/               # Documentación de desarrollo.
examples/           # Ejemplos de configuración MCP.
.env.example        # Plantilla de configuración local.
pyproject.toml      # Paquete y dependencias.
uv.lock             # Versiones de dependencias.
roadmap.md          # Plan de implementación.
AGENTS.md           # Guía para agentes de desarrollo.
```

Documentación técnica: [desarrollo local](docs/desarrollo.md) · [roadmap](roadmap.md) · [análisis y funcionalidades pendientes](docs/funcionalidades-pendientes.md).

## Licencia

[MIT](LICENSE). Proyecto independiente, sin afiliación oficial con la UTN.
