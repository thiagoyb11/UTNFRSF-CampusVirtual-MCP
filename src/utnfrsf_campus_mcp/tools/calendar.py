"""Contrato MCP de la consulta mensual, sin argumentos de identidad ni ejecución arbitraria."""

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from utnfrsf_campus_mcp.errors import CalendarError, LoginError
from utnfrsf_campus_mcp.models import MonthlyActivities
from utnfrsf_campus_mcp.services.calendar import CalendarService


def register_calendar(server: MCPServer, service: CalendarService) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        )
    )
    async def list_monthly_activities(
        year: Annotated[
            int | None, Field(ge=1970, le=9998, description="Año; junto con month.")
        ] = None,
        month: Annotated[int | None, Field(ge=1, le=12, description="Mes entre 1 y 12.")] = None,
        deadlines_only: Annotated[
            bool, Field(description="Solo vencimientos (due) y cierres (close).")
        ] = False,
    ) -> MonthlyActivities:
        """Lista en JSON las actividades del calendario mensual de todas las asignaturas.

        Omití year y month para consultar el mes actual en la zona del campus, o indicá ambos.
        Incluye nombre, asignatura, fechas ISO 8601 con hora y offset, y activity_url directo.
        deadline_at solo se completa para due/close; aperturas y asistencias conservan su tipo.
        No confirma entregas pendientes. Autentica con .env y consulta solo eventos visibles
        para la cuenta y sus filtros de calendario. No depende del idioma de la interfaz.
        """
        try:
            return await service.list_monthly_activities(year, month, deadlines_only)
        except (CalendarError, LoginError) as exc:
            raise ToolError(str(exc)) from None
        except Exception:
            raise ToolError(
                "CALENDAR_INTERNAL_ERROR: No se pudo completar la consulta mensual."
            ) from None
