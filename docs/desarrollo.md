# Desarrollo local

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Python 3.11 o posterior. `.python-version` selecciona Python 3.12 para el entorno de desarrollo; uv puede descargarlo si falta.
- Una plataforma con wheel de Lightpanda compatible. Para la versión bloqueada hay paquetes para macOS y Linux; en Windows se necesita un entorno Linux compatible, como WSL.

El paquete `lightpanda` incluye su navegador. No hace falta instalar Chromium ni ejecutar un servidor CDP separado para esta base. También se puede seleccionar un binario compatible mediante `UTN_CAMPUS_LIGHTPANDA_BINARY`. Ver la [guía de Python de Lightpanda](https://lightpanda.io/docs/guides/use-python).

## Instalar y ejecutar

Desde la raíz del repositorio:

```bash
uv sync --locked --dev
uv run --locked utnfrsf-campus-mcp --help
uv run --locked utnfrsf-campus-mcp --version
```

Para iniciar el servidor:

```bash
uv run --locked utnfrsf-campus-mcp
```

Este comando espera mensajes MCP en stdin y devuelve el protocolo en stdout. No abre un chat ni una ventana de navegador. Los logs van a stderr. También está disponible `uv run --locked python -m utnfrsf_campus_mcp`.

La única herramienta registrada es **`get_server_info`**: devuelve la versión y aclara que las operaciones del campus todavía no están disponibles. No inicia Lightpanda, no autentica una cuenta y no realiza peticiones al campus.

## Configuración

La configuración es opcional. Los valores predeterminados permiten arrancar sin `.env`.

```bash
cp .env.example .env
```

El archivo se lee desde el directorio de trabajo. Las variables de entorno tienen prioridad sobre `.env`.

| Variable | Valor inicial | Uso |
| --- | --- | --- |
| `UTN_CAMPUS_TIMEZONE` | `America/Argentina/Cordoba` | Zona horaria IANA para el proyecto. |
| `UTN_CAMPUS_LOG_LEVEL` | `INFO` | Nivel de logging, en mayúsculas. |
| `UTN_CAMPUS_BROWSER_TIMEOUT_SECONDS` | `30` | Espera de respuesta del proceso Lightpanda. |
| `UTN_CAMPUS_NAVIGATION_TIMEOUT_MS` | `10000` | Límite previsto para llamadas de navegación; la prueba local ya lo utiliza. |
| `UTN_CAMPUS_LIGHTPANDA_BINARY` | Sin valor | Ruta opcional al navegador; normalmente se usa el binario del paquete. |

Todavía no hay variables de usuario o contraseña porque el login no está implementado. No guardes secretos en el ejemplo ni en archivos versionados.

## Conectar un host MCP

[examples/mcp.json](../examples/mcp.json) contiene un ejemplo para hosts que utilizan la configuración `mcpServers` con `command` y `args`. Reemplazá la ruta del proyecto y, si el host no encuentra `uv`, usá la ruta absoluta de su ejecutable.

Primero ejecutá `uv sync --locked --dev`. Luego incorporá la configuración según las instrucciones de tu host. No ejecutes `lightpanda mcp` en lugar del comando del proyecto: eso expondría el MCP genérico de Lightpanda.

## Estructura

```text
src/utnfrsf_campus_mcp/
├── server.py             # Construcción del servidor y entrypoint stdio.
├── config.py             # Configuración validada.
├── models.py             # Respuestas tipadas implementadas.
├── tools/diagnostics.py  # Registro de get_server_info.
├── services/diagnostics.py
├── browser/lightpanda.py # Sesiones y ciclo de vida del navegador.
└── parsers/              # Espacio para extracción y normalización futuras.
tests/
├── fixtures/             # HTML sintético, sin datos del campus.
└── integration/          # Pruebas optativas con Lightpanda real.
```

El adaptador abre una sesión aislada por bloque y la cierra junto con el proceso. No conserva autenticación entre operaciones. El gestor de sesión autenticada se desarrollará en el [roadmap](../roadmap.md).

## Verificación

Los tests y `scripts/test.sh` se mantienen como archivos locales, excluidos de Git. Los comandos de pruebas de esta sección requieren que esos archivos estén presentes; no se incluyen en un clon nuevo. Los controles de Ruff sí se pueden ejecutar sobre el código versionado.

```bash
bash scripts/test.sh
```

El script sincroniza el entorno con el lockfile y ejecuta Ruff, la comprobación de formato y pytest. Las pruebas habituales verifican configuración, descubrimiento de herramientas y llamadas MCP, incluido el transporte stdio real.

Para incluir la integración con Lightpanda:

```bash
bash scripts/test.sh --with-lightpanda
```

La integración levanta una página de prueba en `127.0.0.1` y comprueba JavaScript, extracción y un formulario. No usa cuentas ni se conecta al campus. Pasar esta prueba no acredita compatibilidad con el sitio real.

También podés ejecutar los controles individualmente:

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

Para regenerar el lockfile después de modificar dependencias, usá `uv lock` y volvé a ejecutar los controles. `uv.lock` se versiona; `.venv/`, `.local/`, `.env` y `downloads/` quedan fuera de Git.

Si el entorno no permite escribir en la caché global de uv, definí `UV_CACHE_DIR` con una ruta escribible. El script de verificación ya usa `.local/uv-cache` como alternativa predeterminada.
