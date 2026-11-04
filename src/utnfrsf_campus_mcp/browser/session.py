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
BROWSER_ERRORS = (LightpandaError, OSError)


class CampusSession:
    """Serializa el acceso a una página compartida mientras haya actividad.

    Las cookies viven en el proceso: al cerrarlo, la próxima herramienta vuelve a
    iniciar sesión. Una retención mantiene abierto el navegador entre operaciones
    que dependen de la misma sesión, como una carga temporal pendiente de guardar.
    """

    def __init__(self, browser: LightpandaBrowser, idle_seconds: float = 60) -> None:
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
        async with self._lock:
            if self._page is not None and not await self._is_alive(self._page):
                logger.warning("Lightpanda dejó de responder; se abrirá un navegador nuevo.")
                await self._shutdown()
            if self._page is None:
                self._page = await self._stack.enter_async_context(self._browser.session())
            if self._watcher is None:
                self._watcher = asyncio.create_task(self._close_when_idle())
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
        with CancelScope(shield=True):
            async with self._lock:
                if self._watcher is not None:
                    self._watcher.cancel()
                    self._watcher = None
                await self._shutdown()

    @staticmethod
    async def _is_alive(page: AsyncSession) -> bool:
        try:
            await page.evaluate(script="1")
        except BROWSER_ERRORS as exc:
            logger.warning("Lightpanda no respondió: %s", type(exc).__name__)
            return False
        return True

    def _close_at(self) -> float:
        return max((self._last_used + self._idle_seconds, *self._holds.values()))

    async def _close_when_idle(self) -> None:
        while True:
            # Acotado para notar pronto una retención liberada.
            remaining = self._close_at() - time.monotonic()
            await asyncio.sleep(min(max(remaining, 0.05), self._idle_seconds))
            async with self._lock:
                if time.monotonic() >= self._close_at():
                    self._watcher = None
                    await self._shutdown()
                    return

    async def _shutdown(self) -> None:
        """Cierra el proceso; un navegador ya caído no debe impedir abrir otro."""
        stack, self._stack = self._stack, AsyncExitStack()
        self._page = None
        self._holds.clear()
        try:
            await stack.aclose()
        except BROWSER_ERRORS as exc:
            logger.warning("Lightpanda no cerró limpiamente: %s", type(exc).__name__)
