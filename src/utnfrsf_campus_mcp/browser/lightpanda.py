"""Ciclo de vida de Lightpanda mediante su SDK oficial de Python."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from lightpanda import AsyncBrowser, AsyncSession

from utnfrsf_campus_mcp.config import Settings


class LightpandaBrowser:
    """Abre una sesión aislada por operación y libera sus recursos al salir.

    Esta base no conserva cookies entre operaciones. El flujo autenticado
    necesitará un gestor de sesión compartida, según el roadmap.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Crea el proceso y la sesión solo cuando un servicio los solicita."""
        binary = self._settings.lightpanda_binary
        async with AsyncBrowser(
            binary=str(binary) if binary is not None else None,
            timeout=self._settings.browser_timeout_seconds,
            verbose=False,
        ) as browser:
            async with browser.session() as page:
                yield page
