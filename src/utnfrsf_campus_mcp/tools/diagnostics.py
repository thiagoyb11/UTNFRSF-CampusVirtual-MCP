"""Herramientas de diagnóstico sin acceso al campus ni efectos externos."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from utnfrsf_campus_mcp.config import Settings
from utnfrsf_campus_mcp.models import ServerInfo
from utnfrsf_campus_mcp.services.diagnostics import get_server_info as read_server_info


def register_diagnostics(server: MCPServer, settings: Settings) -> None:
    """Publica solo capacidades disponibles; no registra herramientas ficticias."""

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    def get_server_info() -> ServerInfo:
        """Consulta la versión y alcance del MCP. No verifica una sesión del campus."""
        return read_server_info(settings)
