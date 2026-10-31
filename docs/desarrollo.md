# Desarrollo y ejecución

## Python global

El proyecto usa Python global 3.11 o posterior. No se crea un entorno virtual. En esta computadora, usá `/opt/homebrew/bin/python3` (Python 3.15); `/usr/bin/python3` es 3.9 y no es compatible.

Desde la raíz del repositorio, la instalación para este macOS con Homebrew es:

```bash
/opt/homebrew/bin/python3 -m pip install --user --break-system-packages -e . --group dev
```

Los paquetes quedan disponibles para el intérprete global en la instalación del usuario. `--group dev` incorpora las herramientas de desarrollo; se puede omitir para instalar solo el MCP. En otros sistemas, usá el ejecutable global compatible y las opciones de pip correspondientes.

Lightpanda incluye su navegador en el paquete de Python. No hace falta instalar Chromium ni levantar un servidor CDP separado. Ver la [guía del SDK de Python](https://lightpanda.io/docs/guides/use-python).

## Ejecutar el MCP

```bash
/opt/homebrew/bin/python3 -m utnfrsf_campus_mcp --help
/opt/homebrew/bin/python3 -m utnfrsf_campus_mcp --version
/opt/homebrew/bin/python3 -m utnfrsf_campus_mcp
```

El último comando espera mensajes MCP en stdin y escribe el protocolo en stdout. Los logs van a stderr. No abre un chat ni una ventana de navegador.

Las herramientas disponibles son:

- **`get_server_info`**: informa versión y alcance, sin abrir el navegador.
- **`login`**: inicia o verifica la sesión del campus usando las credenciales privadas de configuración. No recibe argumentos.
- **`list_monthly_activities`**: devuelve JSON con las actividades del mes, asignaturas, fechas y enlaces directos. Parámetros y ejemplos en [actividades del mes](calendario.md). Verificada contra el campus real el 31 de octubre de 2026: mes actual, mes explícito, filtro de deadlines y enlace del popup.

## Configurar el acceso

Si todavía no existe un `.env`, copiá `.env.example` y completá los valores en ese archivo privado:

```dotenv
UTN_CAMPUS_USERNAME=
UTN_CAMPUS_PASSWORD=
```

No sobrescribas un `.env` existente ni guardes las credenciales en archivos versionados. `.env` está ignorado por Git. Se lee desde el directorio de trabajo y las variables de entorno tienen prioridad. Reiniciá el servidor si cambiás la configuración.

| Variable | Valor inicial | Uso |
| --- | --- | --- |
| `UTN_CAMPUS_USERNAME` | Vacío | Usuario del campus, mantenido fuera del esquema MCP. |
| `UTN_CAMPUS_PASSWORD` | Vacío | Contraseña, excluida de representaciones y respuestas. |
| `UTN_CAMPUS_TIMEZONE` | `America/Argentina/Cordoba` | Zona horaria IANA. |
| `UTN_CAMPUS_LOG_LEVEL` | `INFO` | Nivel de logging, en mayúsculas. |
| `UTN_CAMPUS_BROWSER_TIMEOUT_SECONDS` | `30` | Espera de respuesta del proceso Lightpanda. |
| `UTN_CAMPUS_NAVIGATION_TIMEOUT_MS` | `10000` | Espera de navegación y resolución del acceso. |
| `UTN_CAMPUS_LOGIN_MAX_ATTEMPTS` | `3` | Total máximo de intentos; solo se repite ante límites de solicitudes. |
| `UTN_CAMPUS_LOGIN_RETRY_DELAY_SECONDS` | `2` | Espera inicial, con crecimiento exponencial y variación aleatoria. |
| `UTN_CAMPUS_LOGIN_TIMEOUT_SECONDS` | `90` | Presupuesto total del login, incluidas las esperas. |
| `UTN_CAMPUS_LIGHTPANDA_BINARY` | Sin valor | Ruta opcional a otro binario compatible. |

## Probar en Inspector

Desde la raíz del proyecto:

```bash
npx --yes @modelcontextprotocol/inspector /opt/homebrew/bin/python3 -m utnfrsf_campus_mcp
```

Conectate, abrí **Tools**, seleccioná **login** y ejecutalo sin parámetros (`{}`). No introduzcas las credenciales en los argumentos de Inspector.

Una respuesta confirmada tiene esta forma:

```json
{
  "status": "authenticated",
  "already_authenticated": false,
  "attempts": 1,
  "message": "Sesión autenticada en el campus."
}
```

`login` navega a la página de acceso, usa `detect_forms`, encuentra con `find_element` el botón submit perteneciente al formulario, sin buscar su texto traducido, completa los campos con `fill` y envía con `click`. Los nombres `username` y `password`, los selectores y el destino del formulario se comprobaron en el campus público con Lightpanda. Se verifica un identificador de usuario autenticado en la configuración de la página y la ausencia del formulario de login; no se declara éxito solo por un HTTP 200.

Ante HTTP 429, un error `TooManyRequests` o una página con ese mensaje, espera y vuelve a la página de login para descubrir un formulario nuevo. No reenvía a ciegas el POST anterior. Las credenciales rechazadas y los resultados inciertos no se reintentan automáticamente. Los fallos se devuelven como errores MCP con códigos como `LOGIN_CREDENTIALS_MISSING`, `LOGIN_RATE_LIMITED` o `LOGIN_REJECTED`, sin incluir mensajes crudos del navegador.

La sesión se conserva en memoria durante la ejecución del proceso MCP y se cierra cuando el servidor termina. No se persisten cookies en disco. Una redirección externa o un paso interactivo no soportado produce un error explícito.

**Validación real:** el login se ejecutó mediante la herramienta MCP contra el Campus Virtual UTN FRSF el 31 de octubre de 2026 y confirmó una sesión autenticada en el primer intento. No se registraron las credenciales ni se realizaron otras acciones académicas.

## Conectar otro host MCP

[examples/mcp.json](../examples/mcp.json) usa el formato `mcpServers`. Ajustá `cwd` a la ruta absoluta del proyecto y `command` al Python global compatible de tu sistema. El directorio de trabajo determina qué `.env` se carga.

## Organización

- `server.py`: registro de herramientas y cierre de recursos con el ciclo de vida del servidor.
- `config.py` y `models.py`: configuración privada y respuestas públicas tipadas.
- `browser/`: adaptador de Lightpanda y sesión compartida con acceso serializado.
- `parsers/login.py`: identificación del formulario y señales de estado de la página.
- `services/authentication.py`: flujo de acceso y política de reintentos.
- `services/courses.py`: helper interno `CourseService.list_degree_courses()` para My courses → Grado, con normalización en `parsers/courses.py`. No agrega una herramienta a Inspector. Uso y estructura de materias en [la guía para recursos](guia-get-course-resources.md).
- `browser/calendar.py`: lectura del módulo de calendario de Moodle en Lightpanda.
- `parsers/calendar.py` y `services/calendar.py`: validación del mes, fechas, enlaces y consulta mensual.
- `tools/`: adaptación de los servicios a MCP, sin parámetros de credenciales.

## Controles locales

Los tests y `scripts/test.sh` son archivos locales ignorados por Git. No están incluidos en un clon nuevo. Cuando estén disponibles, usan el intérprete global:

```bash
bash scripts/test.sh
bash scripts/test.sh --with-lightpanda
```

Los controles de código se pueden ejecutar directamente:

```bash
/opt/homebrew/bin/python3 -m ruff check .
/opt/homebrew/bin/python3 -m ruff format --check .
```

`pyproject.toml` declara las dependencias y `uv.lock` conserva su resolución. Se puede actualizar el lockfile con `uv lock --python /opt/homebrew/bin/python3`; este comando no crea un entorno virtual. No uses `uv sync` ni `uv run` en este proyecto.
