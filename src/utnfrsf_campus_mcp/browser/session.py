"""Sesión del campus compartida durante la vida del servidor MCP."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from anyio import CancelScope, Lock
from lightpanda import AsyncSession

from utnfrsf_campus_mcp.browser.lightpanda import LightpandaBrowser


class CampusSession:
    """Conserva la página y cookies; serializa el acceso y arranca bajo demanda."""

    def __init__(self, browser: LightpandaBrowser) -> None:
        self._browser = browser
        self._stack = AsyncExitStack()
        self._page: AsyncSession | None = None
        self._lock = Lock()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[AsyncSession]:
        async with self._lock:
            if self._page is None:
                self._page = await self._stack.enter_async_context(self._browser.session())
            yield self._page

    async def close(self) -> None:
        with CancelScope(shield=True):
            async with self._lock:
                try:
                    await self._stack.aclose()
                finally:
                    self._page = None
