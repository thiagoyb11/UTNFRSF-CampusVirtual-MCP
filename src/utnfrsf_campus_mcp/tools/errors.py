"""Traducción única de excepciones a errores MCP para todas las herramientas."""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from utnfrsf_campus_mcp.errors import CampusError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Mensaje genérico de cada área para fallos inesperados. Nunca se reenvía la excepción
# original: puede contener valores de formularios, URLs con tokens o credenciales. Las
# áreas que escriben en el campus recuerdan consultar el estado antes de repetir.
INTERNAL_ERRORS: dict[str, str] = {
    "login": "LOGIN_INTERNAL_ERROR: No se pudo completar el acceso.",
    "calendar": "CALENDAR_INTERNAL_ERROR: No se pudo completar la consulta mensual.",
    "courses": "COURSES_INTERNAL_ERROR: No se pudo completar el listado.",
    "resources": "RESOURCES_INTERNAL_ERROR: No se pudo completar la consulta.",
    "downloads": "DOWNLOAD_INTERNAL_ERROR: No se pudo completar la descarga.",
    "forums": "FORUM_INTERNAL_ERROR: No se pudo completar la consulta.",
    "submissions": (
        "SUBMISSION_INTERNAL_ERROR: No se completó la operación; "
        "verificá el estado antes de repetir escrituras."
    ),
    "local_files": "UPLOAD_LOCAL_FILE_ERROR: No se pudieron preparar los archivos.",
}


def _translate(area: str, exc: Exception) -> ToolError:
    # Los errores de dominio ya traen un código y un mensaje seguros: se reenvían tal cual.
    if isinstance(exc, CampusError):
        return ToolError(str(exc))
    # El tipo de la excepción sirve para diagnosticar y no expone su contenido.
    logger.warning("Fallo inesperado en %s: %s", area, type(exc).__name__)
    return ToolError(INTERNAL_ERRORS[area])


def tool_errors(area: str) -> Callable[[F], F]:
    """Envuelve una herramienta para que solo emita errores MCP con código y texto seguros.

    Conserva firma, anotaciones y docstring (functools.wraps), que el SDK de MCP usa para
    generar el esquema de la herramienta. Admite funciones síncronas y asíncronas.
    """
    if area not in INTERNAL_ERRORS:
        raise ValueError(f"Área de errores desconocida: {area}")

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await fn(*args, **kwargs)
                except ToolError:
                    raise
                except Exception as exc:
                    raise _translate(area, exc) from None

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except ToolError:
                raise
            except Exception as exc:
                raise _translate(area, exc) from None

        return sync_wrapper  # type: ignore[return-value]

    return decorator
