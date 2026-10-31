"""Herramientas académicas; los formularios, tokens y ejecución quedan internos."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from utnfrsf_campus_mcp.errors import DownloadError, LoginError, SubmissionError
from utnfrsf_campus_mcp.models import (
    PreparedSubmission,
    SubmissionResult,
    SubmissionStatus,
    UploadedFiles,
)
from utnfrsf_campus_mcp.services.submissions import SubmissionService

Id = Annotated[int, Field(gt=0, description="ID de la materia o módulo, según el parámetro.")]
Files = Annotated[
    list[str],
    Field(
        min_length=1,
        max_length=100,
        description="Rutas locales de archivos regulares; no carpetas.",
    ),
]


def register_submissions(server: MCPServer, service: SubmissionService) -> None:
    read = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
    write = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
    )

    async def call(method, *args):
        try:
            return await method(*args)
        except (SubmissionError, LoginError, DownloadError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError(
                "SUBMISSION_INTERNAL_ERROR: No se completó la operación; "
                "verificá el estado antes de repetir escrituras."
            ) from None

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        )
    )
    def prepare_submission(course_id: Id, activity_id: Id, files: Files) -> PreparedSubmission:
        """Prepara archivos y hashes localmente; no inicia sesión ni escribe en el campus."""
        try:
            return service.prepare_submission(course_id, activity_id, files)
        except SubmissionError as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError(
                "UPLOAD_LOCAL_FILE_ERROR: No se pudieron preparar los archivos."
            ) from None

    @server.tool(annotations=read)
    async def get_submission_status(course_id: Id, activity_id: Id) -> SubmissionStatus:
        """Consulta estado y archivos de una tarea assign, conservando la evidencia original."""
        return await call(service.get_submission_status, course_id, activity_id)

    @server.tool(annotations=write)
    async def upload_files(course_id: Id, activity_id: Id, files: Files) -> UploadedFiles:
        """Carga y verifica archivos en el área temporal de una tarea abierta; devuelve un recibo.

        Respeta los tipos, tamaños y cantidad admitidos por la actividad. Admite archivos de
        cualquier tipo permitido, incluidos ZIP; rechaza carpetas y reemplazos de entregas.
        No guarda ni envía la entrega. El recibo dura 30 minutos en este proceso MCP.
        """
        return await call(service.upload_files, course_id, activity_id, files)

    @server.tool(annotations=write)
    async def submit_assignment(
        upload_id: str, finalize: bool = False, accept_statement: bool = False
    ) -> SubmissionResult:
        """Guarda la carga del recibo como entrega y verifica el resultado en el campus.

        Guardar puede entregar definitivamente si la actividad no utiliza borradores.
        finalize=true completa además la confirmación de envío cuando exista. Una declaración
        de autoría requiere accept_statement=true explícito. No reemplaza entregas existentes
        ni reenvía POSTs de resultado incierto. Solo invocar para una entrega autorizada con
        esos archivos y destino; upload_files por sí sola no autoriza este guardado.
        """
        return await call(service.submit_assignment, upload_id, finalize, accept_statement)
