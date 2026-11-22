"""Errores de dominio con mensajes seguros para mostrar al asistente."""

# Todas las excepciones siguen el mismo patrón: un código estable (por ejemplo
# DOWNLOAD_NOT_IN_COURSE) que el código puede comparar, y un mensaje en español para el
# usuario. str(exc) produce "CODIGO: mensaje", que es lo que reciben las herramientas MCP.
# Hay una clase por área; todas heredan de CampusError, que tools/errors.py traduce a un
# error MCP en un único lugar.


class CampusError(Exception):
    """Base de los errores de dominio: código estable y mensaje seguro para el cliente."""

    def __init__(self, code: str, message: str, retry_after: float | None = None) -> None:
        self.code = code
        # Segundos que pidió el campus (Retry-After) ante un límite de solicitudes, si los dio.
        self.retry_after = retry_after
        super().__init__(f"{code}: {message}")


class LoginError(CampusError):
    """Solo recibe códigos y mensajes propios, nunca respuestas del navegador."""


class CalendarError(CampusError):
    """Error de consulta con código y mensaje aptos para el cliente MCP."""


class CourseError(CampusError):
    """Fallo seguro al identificar o consultar las asignaturas de la cuenta."""


class DownloadError(CampusError):
    """Fallo seguro de una descarga autenticada o de su destino local."""


class SubmissionError(CampusError):
    """Error de carga o entrega sin respuestas remotas, tokens ni credenciales."""
