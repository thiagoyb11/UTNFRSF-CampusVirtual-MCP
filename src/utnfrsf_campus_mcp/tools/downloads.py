"""Contrato MCP de descarga a downloads/, sin cookies ni destinos arbitrarios."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from utnfrsf_campus_mcp.errors import CourseError, DownloadError, LoginError
from utnfrsf_campus_mcp.models import DownloadedResources
from utnfrsf_campus_mcp.services.downloads import DownloadService


def register_downloads(server: MCPServer, service: DownloadService) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    async def download_resources(
        course_id: Annotated[int, Field(gt=0, description="ID de la asignatura de Grado.")],
        module_id: Annotated[
            int, Field(gt=0, description="ID del módulo donde aparecen los archivos.")
        ],
        urls: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=10,
                description="Enlaces de archivo de get_course_resources, en el orden solicitado.",
            ),
        ],
    ) -> DownloadedResources:
        """Descarga entre 1 y 10 archivos del campus a downloads/course-ID/module-ID/.

        Verifica su pertenencia al módulo y a la materia con una consulta autenticada nueva.
        Usa la sesión de Lightpanda y un transporte HTTP binario del mismo origen. Valida
        respuesta HTTP y tamaño; calcula SHA-256 y detecta páginas de login/error de Moodle.
        Admite cualquier extensión y MIME; no valida el formato interno ni ejecuta archivos.
        No sigue redirecciones ni reemplaza archivos existentes. Devuelve rutas locales,
        tamaños, hashes y fallos por archivo. Solo archivos del campus, sin destinos externos.
        No modifica entregas del campus.
        """
        try:
            return await service.download_resources(course_id, module_id, urls)
        except (CourseError, DownloadError, LoginError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError("DOWNLOAD_INTERNAL_ERROR: No se pudo completar la descarga.") from None
