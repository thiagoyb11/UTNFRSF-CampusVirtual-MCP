"""Arranque local del servidor MCP por stdio."""

import argparse
import logging
import sys
from importlib.metadata import version

from mcp.server import MCPServer
from pydantic import ValidationError

from utnfrsf_campus_mcp.config import Settings
from utnfrsf_campus_mcp.tools.diagnostics import register_diagnostics


def create_server(settings: Settings | None = None) -> MCPServer:
    """Construye el servidor sin abrir el navegador ni realizar peticiones de red."""
    config = settings if settings is not None else Settings()
    server = MCPServer("UTN FRSF Campus Virtual MCP")
    register_diagnostics(server, config)
    return server


def main() -> None:
    """Ejecuta el protocolo en stdout y conserva los logs en stderr."""
    parser = argparse.ArgumentParser(description="MCP del Campus Virtual UTN FRSF (stdio).")
    parser.add_argument("--version", action="version", version=version("utnfrsf-campusvirtual-mcp"))
    parser.parse_args()

    try:
        settings = Settings()
    except ValidationError as exc:
        fields = ", ".join(str(error["loc"][0]) for error in exc.errors())
        print(f"Configuración inválida ({fields}). Revisá .env y UTN_CAMPUS_*.", file=sys.stderr)
        raise SystemExit(2) from None

    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    create_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
