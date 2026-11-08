"""Información del proyecto disponible sin acceso a una cuenta del campus."""

from collections.abc import Iterable
from importlib.metadata import version

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.models import Capability, ServerInfo
from utnfrsf_campus_mcp.services.capabilities import CAPABILITIES, PENDING_FEATURES_DOC


def get_server_info(settings: Settings, registered_tools: Iterable[str]) -> ServerInfo:
    """Describe la base instalada sin iniciar Lightpanda ni autenticar al usuario.

    `registered_tools` proviene del servidor en ejecución. Solo se publican las
    capacidades de herramientas realmente registradas, de modo que el catálogo
    nunca anuncia una herramienta ausente. Si una herramienta registrada no tiene
    entrada en el catálogo, se informa en `undocumented_tools` en lugar de ocultarla.
    """
    # Orden alfabético y sin duplicados, para una respuesta estable entre llamadas.
    registered = sorted(set(registered_tools))

    # Filtra el catálogo conservando su orden, que agrupa las herramientas por área.
    capabilities = [item for item in CAPABILITIES if item.tool in registered]
    documented = {item.tool for item in capabilities}
    undocumented = [name for name in registered if name not in documented]

    return ServerInfo(
        name="UTN FRSF Campus Virtual MCP",
        version=version("utnfrsf-campusvirtual-mcp"),
        campus_url=CAMPUS_BASE_URL,
        timezone=settings.timezone,
        registered_tools=registered,
        capabilities=capabilities,
        undocumented_tools=undocumented,
        pending_features_doc=PENDING_FEATURES_DOC,
        message=_summary(capabilities, undocumented),
    )


def _summary(capabilities: list[Capability], undocumented: list[str]) -> str:
    """Resume cuántas herramientas hay en cada nivel de validación."""
    # Cuenta las herramientas por nivel de evidencia declarado en el catálogo.
    counts = {"campus_verified": 0, "campus_partial": 0, "local_tests": 0}
    for item in capabilities:
        counts[item.status] += 1

    text = (
        f"{len(capabilities)} herramientas con estado declarado: "
        f"{counts['campus_verified']} verificadas en el campus, "
        f"{counts['campus_partial']} verificadas parcialmente y "
        f"{counts['local_tests']} solo con pruebas locales. "
        "Revisá capabilities[].pending antes de asumir un alcance completo; "
        "esta respuesta no comprueba la sesión del campus."
    )

    # Una herramienta sin estado declarado se nombra explícitamente en vez de ocultarse.
    if undocumented:
        text += f" Herramientas sin estado declarado: {', '.join(undocumented)}."

    return text
