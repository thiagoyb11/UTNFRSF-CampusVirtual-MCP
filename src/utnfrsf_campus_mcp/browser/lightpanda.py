"""Ciclo de vida de Lightpanda mediante su SDK oficial de Python."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from lightpanda import AsyncBrowser, AsyncSession

from utnfrsf_campus_mcp.config import Settings


class LightpandaBrowser:
    """Abre una sesión aislada por operación y libera sus recursos al salir.

    Este adaptador proporciona el bloque de ciclo de vida. CampusSession
    lo mantiene abierto mientras hay actividad y lo cierra al quedar inactivo.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Crea el proceso y la sesión solo cuando un servicio los solicita."""
        # Sin binario configurado, el SDK usa el Lightpanda que encuentre instalado.
        binary = self._settings.lightpanda_binary
        async with AsyncBrowser(
            binary=str(binary) if binary is not None else None,
            timeout=self._settings.browser_timeout_seconds,
            verbose=False,
            # El binario corta a 15 s y 8 s por defecto, aunque goto admita más:
            # el campus tuvo picos de más de 20 s.
            args=(
                "--http-timeout",
                str(self._settings.navigation_timeout_ms),
                "--http-connect-timeout",
                str(self._settings.navigation_timeout_ms),
            ),
        ) as browser:
            # Una única pestaña por proceso; al salir del bloque se cierran pestaña y proceso.
            async with browser.session() as page:
                yield page
