"""Sesión del campus: abre Lightpanda bajo demanda y lo cierra al quedar inactivo."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from anyio import CancelScope, Lock
from lightpanda import AsyncSession, LightpandaError

from utnfrsf_campus_mcp.browser.lightpanda import LightpandaBrowser

logger = logging.getLogger(__name__)
# Fallos que indican un navegador caído o inaccesible (proceso muerto, socket cerrado).
BROWSER_ERRORS = (LightpandaError, OSError)


class CampusSession:
    """Serializa el acceso a una página compartida mientras haya actividad.

    Las cookies viven en el proceso: al cerrarlo, la próxima herramienta vuelve a
    iniciar sesión. Una retención mantiene abierto el navegador entre operaciones
    que dependen de la misma sesión, como una carga temporal pendiente de guardar.
    """

    def __init__(self, browser: LightpandaBrowser, idle_seconds: float = 60) -> None:
        # _stack guarda el contexto abierto del navegador para poder cerrarlo después.
        # _holds: retenciones activas (clave → instante de vencimiento).
        # _watcher: tarea en segundo plano que cierra el navegador por inactividad.
        self._browser = browser
        self._idle_seconds = idle_seconds
        self._stack = AsyncExitStack()
        self._page: AsyncSession | None = None
        self._lock = Lock()
        self._last_used = 0.0
        self._holds: dict[str, float] = {}
        self._watcher: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[AsyncSession]:
        # El lock garantiza que una sola operación navegue a la vez sobre la página compartida.
        async with self._lock:
            # Si el proceso murió, se descarta y se abre uno nuevo en lugar de fallar.
            if self._page is not None and not await self._is_alive(self._page):
                logger.warning("Lightpanda dejó de responder; se abrirá un navegador nuevo.")
                await self._shutdown()
            # Apertura perezosa del navegador y del vigilante de inactividad.
            if self._page is None:
                self._page = await self._stack.enter_async_context(self._browser.session())
            if self._watcher is None:
                self._watcher = asyncio.create_task(self._close_when_idle())
            # Al terminar la operación (bien o mal) se reinicia el contador de inactividad.
            try:
                yield self._page
            finally:
                self._last_used = time.monotonic()

    def hold(self, key: str, seconds: float) -> None:
        """Evita el cierre por inactividad hasta liberar la clave o agotar el plazo."""
        self._holds[key] = time.monotonic() + seconds

    def release_hold(self, key: str) -> None:
        self._holds.pop(key, None)

    async def close(self) -> None:
        # Blindado contra cancelación: al apagar el servidor el cierre debe completarse igual.
        with CancelScope(shield=True):
            async with self._lock:
                if self._watcher is not None:
                    self._watcher.cancel()
                    self._watcher = None
                await self._shutdown()

    @staticmethod
    async def _is_alive(page: AsyncSession) -> bool:
        # Evaluar una expresión trivial basta para saber si el proceso sigue respondiendo.
        try:
            await page.evaluate(script="1")
        except BROWSER_ERRORS as exc:
            logger.warning("Lightpanda no respondió: %s", type(exc).__name__)
            return False
        return True

    def _close_at(self) -> float:
        # Se cierra cuando vencen tanto la inactividad como todas las retenciones activas.
        return max((self._last_used + self._idle_seconds, *self._holds.values()))

    async def _close_when_idle(self) -> None:
        while True:
            # Acotado para notar pronto una retención liberada.
            remaining = self._close_at() - time.monotonic()
            await asyncio.sleep(min(max(remaining, 0.05), self._idle_seconds))
            # Se vuelve a comprobar con el lock tomado: pudo haber actividad durante la espera.
            async with self._lock:
                if time.monotonic() >= self._close_at():
                    self._watcher = None
                    await self._shutdown()
                    return

    async def _shutdown(self) -> None:
        """Cierra el proceso; un navegador ya caído no debe impedir abrir otro."""
        # Se reemplaza el stack antes de cerrarlo, así el estado queda limpio aunque falle aclose.
        stack, self._stack = self._stack, AsyncExitStack()
        self._page = None
        self._holds.clear()
        try:
            await stack.aclose()
        except BROWSER_ERRORS as exc:
            logger.warning("Lightpanda no cerró limpiamente: %s", type(exc).__name__)
