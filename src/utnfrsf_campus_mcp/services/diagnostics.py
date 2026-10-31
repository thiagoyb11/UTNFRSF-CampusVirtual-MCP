"""Información del proyecto disponible sin acceso a una cuenta del campus."""

from importlib.metadata import version

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.models import ServerInfo


def get_server_info(settings: Settings) -> ServerInfo:
    """Describe la base instalada sin iniciar Lightpanda ni autenticar al usuario."""
    return ServerInfo(
        name="UTN FRSF Campus Virtual MCP",
        version=version("utnfrsf-campusvirtual-mcp"),
        campus_url=CAMPUS_BASE_URL,
        timezone=settings.timezone,
        message=(
            "Login y consulta mensual de actividades verificados contra el campus real. "
            "get_course_resources lista enlaces por asignatura; se verificó en un curso topics. "
            "Falta validar onetopic. download_resources descarga archivos del campus; "
            "las entregas todavía no están implementadas."
        ),
    )
