"""Errores de dominio con mensajes seguros para mostrar al asistente."""


class LoginError(Exception):
    """Solo recibe códigos y mensajes propios, nunca respuestas del navegador."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class CalendarError(Exception):
    """Error de consulta con código y mensaje aptos para el cliente MCP."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class CourseError(Exception):
    """Fallo seguro al identificar o consultar las asignaturas de la cuenta."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class DownloadError(Exception):
    """Fallo seguro de una descarga autenticada o de su destino local."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
