"""Herramienta MCP de lectura de enlaces de una asignatura."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from utnfrsf_campus_mcp.errors import CourseError, LoginError
from utnfrsf_campus_mcp.models import CourseResources
from utnfrsf_campus_mcp.services.resources import ResourceService


def register_resources(server: MCPServer, service: ResourceService) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    async def get_course_resources(
        course_id: Annotated[int, Field(gt=0, description="ID de la asignatura de Grado.")],
    ) -> CourseResources:
        """Lista los enlaces de una asignatura, incluidas tareas y archivos PDF, ZIP y otros.

        Recorre secciones topics/onetopic accesibles; lee carpetas, recursos, enlaces URL,
        páginas y adjuntos de consignas de tareas. Devuelve links con sección, módulo y
        source_url. Los enlaces de tareas abren la actividad de entrega; no envía archivos.
        Autentica con .env. No visita sitios externos ni descarga binarios. Solo contenido
        visible para la cuenta: no inventa enlaces de actividades o secciones restringidas.
        Revisá complete, pending_urls y warnings antes de asumir que el inventario es completo.
        No recorre conversaciones de foros, intentos de exámenes ni sitios externos.
        """
        try:
            return await service.get_course_resources(course_id)
        except (CourseError, LoginError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("RESOURCES_INTERNAL_ERROR: No se pudo completar la consulta.") from None
