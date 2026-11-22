# Cambios

Este archivo registra los cambios visibles para quien usa el servidor MCP: herramientas, parámetros, respuestas, códigos de error y configuración. Los IDs `Fnn` remiten al [inventario de funcionalidades](docs/funcionalidades-pendientes.md).

## Política de compatibilidad

El proyecto sigue [Semantic Versioning](https://semver.org/lang/es/). El contrato público incluye los nombres y parámetros de las herramientas, los campos de sus respuestas estructuradas, los códigos de error (`LOGIN_REJECTED`, `CAMPUS_RATE_LIMITED`, etc.) y las variables `UTN_CAMPUS_*`.

- **Cambios aditivos** (herramienta, campo de respuesta, parámetro opcional, código de error o variable nuevos): versión de parche o menor. Un cliente no debe fallar ante campos o códigos desconocidos.
- **Cambios incompatibles** (quitar o renombrar algo, cambiar un tipo, volver obligatorio un parámetro): mientras la versión sea 0.x, solo en una versión menor (0.2 → 0.3) y listados en **Incompatibles**. Desde 1.0, solo en una versión mayor.
- El texto de los mensajes de error puede cambiar en cualquier versión; el código antes de `:` es lo estable.
- `get_server_info` informa en cada llamada qué herramientas existen y su nivel de verificación; es la fuente para saber qué está disponible.

## 0.2.0 — sin publicar

Primera versión preparada para que otra persona la instale. Todavía es una vista previa: varias herramientas tienen verificación parcial contra el campus (ver `get_server_info`).

### Agregado

- Herramientas de lectura: `list_courses` (F01), `get_section_content`, `get_page_content` y `get_folder_content` (F14), `list_forum_discussions` y `get_forum_discussion` (F32), `get_assignment_feedback` (F29).
- Herramientas de materiales y entregas: `get_course_resources`, `download_resources`, `get_submission_status`, `prepare_submission`, `upload_files` y `submit_assignment`.
- `get_server_info` publica el nivel de evidencia de cada herramienta (F45).
- Pausa compartida ante HTTP 429 entre todas las herramientas (F41). Código nuevo `CAMPUS_RATE_LIMITED` y variables `UTN_CAMPUS_RATE_LIMIT_COOLDOWN_SECONDS` (30) y `UTN_CAMPUS_RATE_LIMIT_MAX_WAIT_SECONDS` (10).
- Lightpanda se cierra tras `UTN_CAMPUS_BROWSER_IDLE_SECONDS` sin uso y se reabre bajo demanda.
- `download_resources` descarga los archivos de la devolución de una tarea (por ejemplo, el PDF anotado por el docente) y los entregados por la cuenta: se indican las URLs de `get_assignment_feedback` con el id de la tarea como `module_id`, y se verifican contra esa devolución.
- `scripts/smoke_mcp.py` y CI con lint, formato e instalación desde `uv.lock` en Linux y macOS (F46).

### Cambiado

- Las herramientas traducen los errores en un único lugar (F50). Ahora cualquier error de dominio llega con su código, aunque provenga de otra área (por ejemplo, un `COURSES_*` dentro de una consulta de foros); antes algunos se reemplazaban por el genérico `*_INTERNAL_ERROR`. Los mensajes genéricos no cambiaron.

### Incompatibles

- `get_server_info` ya no devuelve `stage` ni `campus_features_ready`; usar `registered_tools` y `capabilities` (F45, 1 de noviembre de 2026).

### Plataformas

- macOS y Linux con glibc 2.35 o superior; Python 3.11 o posterior. Windows no está soportado porque Lightpanda 1.0.2 no publica binario; usar WSL 2.

## 0.1.0 — 31 de octubre de 2026

- Servidor MCP por stdio con `get_server_info`, `login` y `list_monthly_activities`. Sin publicar como versión.
