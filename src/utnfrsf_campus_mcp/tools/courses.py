"""Herramienta MCP de descubrimiento de materias de Grado."""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from utnfrsf_campus_mcp.errors import CourseError, LoginError
from utnfrsf_campus_mcp.models import CourseList
from utnfrsf_campus_mcp.services.courses import CourseService


def register_courses(server: MCPServer, service: CourseService) -> None:
    # Solo lee el campus; repetirla no tiene efectos, por eso es idempotente.
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    async def list_courses() -> CourseList:
        """Lista las materias visibles en My courses → Grado, con ID, nombre completo y URL.

        Sin parámetros. Autentica con la configuración privada de .env y comparte la sesión
        de Lightpanda con las demás herramientas. Incluye Sistemas y Básicas y todos los
        años presentes en esa rama; excluye Ingreso, Extensión y el catálogo general.
        Devuelve scope=Grado, source_url, fetched_at, total, courses y complete=true.
        Una rama pendiente, un límite o un fallo de sesión/parsing producen un error MCP,
        nunca una lista vacía exitosa. No abre cada materia ni modifica datos académicos.
        Los nombres parecidos se devuelven como materias distintas con sus respectivos IDs.
        """
        # Errores conocidos se reenvían con su código; cualquier otro se oculta tras uno genérico.
        try:
            return await service.list_courses()
        except (CourseError, LoginError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("COURSES_INTERNAL_ERROR: No se pudo completar el listado.") from None
