"""Herramienta login sin parámetros de credenciales visibles para el modelo."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from utnfrsf_campus_mcp.models import LoginResult
from utnfrsf_campus_mcp.services.authentication import AuthenticationService
from utnfrsf_campus_mcp.tools.errors import tool_errors


def register_authentication(server: MCPServer, service: AuthenticationService) -> None:
    # No es de solo lectura: iniciar sesión cambia el estado del navegador compartido.
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    @tool_errors("login")
    async def login() -> LoginResult:
        """Inicia sesión en UTN FRSF con las credenciales locales de .env.

        Conserva la sesión mientras haya actividad; Lightpanda se cierra al quedar
        inactivo. Reintenta TooManyRequests de forma acotada, volviendo a la página
        de acceso.
        """
        return await service.login()
