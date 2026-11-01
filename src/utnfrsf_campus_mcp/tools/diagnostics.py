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
    async def get_server_info() -> ServerInfo:
        """Consulta versión, zona horaria y el estado real de cada herramienta registrada.

        No abre Lightpanda ni verifica la sesión del campus. Cada elemento de
        capabilities indica efecto (none, local, read, write), nivel de evidencia
        (local_tests, campus_partial, campus_verified), fecha de verificación real,
        alcance, límites pendientes, IDs relacionados del inventario y documentación.
        undocumented_tools lista herramientas registradas sin estado declarado.
        """
        # Se consulta el registro en cada llamada: las herramientas se registran
        # después de esta, y así el resultado refleja el servidor en ejecución.
        tools = await server.list_tools()
        return read_server_info(settings, (tool.name for tool in tools))
