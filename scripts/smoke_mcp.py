"""Comprobación de humo del servidor instalado, sin cuenta del campus ni red.

Arranca el MCP como subproceso stdio con el intérprete actual, lista las herramientas y
verifica que get_server_info documente exactamente las registradas. Una herramienta que
requiere sesión debe fallar con LOGIN_CREDENTIALS_MISSING, nunca con un resultado vacío.
No se conecta al campus. Uso:

    python3 scripts/smoke_mcp.py                 # solo el protocolo MCP
    python3 scripts/smoke_mcp.py --with-lightpanda  # además abre Lightpanda sobre un servidor local
"""

import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import anyio
from mcp import Client, StdioServerParameters

PAGE = b"<!doctype html><title>smoke</title><p id='p'>sin red</p><script>"
PAGE += b"document.getElementById('p').textContent = 'js-ok';</script>"


class _Page(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *args) -> None:
        pass


async def check_lightpanda() -> str | None:
    """Abre el navegador del paquete instalado sobre una página local y ejecuta JavaScript."""
    from utnfrsf_campus_mcp.browser.lightpanda import LightpandaBrowser
    from utnfrsf_campus_mcp.config import Settings

    with ThreadingHTTPServer(("127.0.0.1", 0), _Page) as httpd:
        Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            settings = Settings(_env_file=None)
            async with LightpandaBrowser(settings).session() as page:
                await page.goto(url=f"http://127.0.0.1:{httpd.server_port}/")
                text = await page.evaluate(script="document.getElementById('p').textContent")
        finally:
            httpd.shutdown()
    return None if text == "js-ok" else f"Lightpanda devolvió {text!r} en la página local."


async def main() -> int:
    # Directorio vacío y entorno sin UTN_CAMPUS_*: no se leen .env ni credenciales privadas.
    env = {key: value for key, value in os.environ.items() if not key.startswith("UTN_CAMPUS_")}
    with tempfile.TemporaryDirectory() as cwd:
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "utnfrsf_campus_mcp"], cwd=cwd, env=env
        )
        async with Client(parameters, read_timeout_seconds=30) as client:
            tools = {tool.name for tool in (await client.list_tools()).tools}
            info = await client.call_tool("get_server_info", {})
            courses = await client.call_tool("list_courses", {})

    problems = []
    if info.is_error:
        problems.append("get_server_info devolvió un error.")
    else:
        data = info.structured_content
        if set(data["registered_tools"]) != tools:
            problems.append("registered_tools no coincide con las herramientas listadas.")
        if data["undocumented_tools"]:
            problems.append(f"Herramientas sin capacidad: {data['undocumented_tools']}")
    if not courses.is_error or "LOGIN_CREDENTIALS_MISSING" not in courses.content[0].text:
        problems.append("list_courses sin credenciales no informó LOGIN_CREDENTIALS_MISSING.")

    if "--with-lightpanda" in sys.argv[1:]:
        problem = await check_lightpanda()
        if problem:
            problems.append(problem)
        else:
            print("OK: Lightpanda ejecutó JavaScript en una página local.")

    for problem in problems:
        print(f"ERROR: {problem}", file=sys.stderr)
    if not problems:
        print(f"OK: {len(tools)} herramientas registradas y documentadas.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(anyio.run(main))
