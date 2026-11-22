"""Freno compartido ante HTTP 429: coordina a todas las herramientas que usan el campus."""

import logging
import math
import time

from anyio import sleep

from utnfrsf_campus_mcp.errors import CampusError

logger = logging.getLogger(__name__)

# Tope para un Retry-After del campus: un valor absurdo no debe bloquear el servidor horas.
MAX_COOLDOWN_SECONDS = 600.0


class RateLimitError(CampusError):
    """El campus limitó solicitudes recientes y todavía no venció la espera."""


def is_rate_limit_code(code: str) -> bool:
    """Los códigos de dominio de límite de solicitudes terminan en _RATE_LIMITED."""
    return code.endswith("_RATE_LIMITED")


def parse_retry_after(value: str | None) -> float | None:
    """Acepta solo segundos enteros; una fecha HTTP u otro formato se ignora."""
    if value is None:
        return None
    value = value.strip()
    return float(value) if value.isdigit() else None


class RateLimitGate:
    """Recuerda el último 429 y frena la siguiente operación hasta que venza la espera.

    Nunca repite una operación: solo decide si la próxima puede empezar. Si falta poco,
    espera dentro del presupuesto (max_wait_seconds); si no, falla de inmediato con un
    error que indica cuántos segundos faltan, antes de enviar cualquier solicitud.
    """

    def __init__(self, cooldown_seconds: float = 30, max_wait_seconds: float = 10) -> None:
        self._cooldown = cooldown_seconds
        self._max_wait = max_wait_seconds
        self._until = 0.0

    def note(self, retry_after: float | None = None) -> None:
        """Registra un 429; Retry-After del campus tiene prioridad sobre el valor por defecto."""
        seconds = self._cooldown if retry_after is None else retry_after
        seconds = min(max(seconds, 0.0), MAX_COOLDOWN_SECONDS)
        self._until = max(self._until, time.monotonic() + seconds)
        logger.warning("El campus limitó solicitudes; pausa compartida de %.0f s.", seconds)

    def remaining(self) -> float:
        return max(self._until - time.monotonic(), 0.0)

    async def wait_or_fail(self) -> None:
        remaining = self.remaining()
        if remaining <= 0:
            return
        if remaining <= self._max_wait:
            await sleep(remaining)
            return
        raise RateLimitError(
            "CAMPUS_RATE_LIMITED",
            "El campus limitó solicitudes recientes. Esperá unos "
            f"{math.ceil(remaining)} s antes de reintentar; esta operación no envió nada.",
        )
