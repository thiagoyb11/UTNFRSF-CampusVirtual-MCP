"""Herramienta login sin parámetros de credenciales visibles para el modelo."""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from utnfrsf_campus_mcp.errors import LoginError
from utnfrsf_campus_mcp.models import LoginResult
from utnfrsf_campus_mcp.services.authentication import AuthenticationService


def register_authentication(server: MCPServer, service: AuthenticationService) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    async def login() -> LoginResult:
        """Inicia sesión en UTN FRSF con las credenciales locales de .env.

        Conserva la sesión mientras haya actividad; Lightpanda se cierra al quedar
        inactivo. Reintenta TooManyRequests de forma acotada, volviendo a la página
        de acceso.
        """
        try:
            return await service.login()
        except LoginError as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            # No enviar al modelo mensajes del navegador que puedan contener
            # valores de formularios, URLs con tokens o credenciales.
            raise ToolError("LOGIN_INTERNAL_ERROR: No se pudo completar el acceso.") from None
