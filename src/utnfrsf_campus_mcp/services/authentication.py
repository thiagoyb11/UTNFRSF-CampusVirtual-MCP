"""Login del campus con formulario real, sesión compartida y reintentos acotados."""

import json
import logging
import random
from urllib.parse import urljoin

from anyio import fail_after, sleep
from lightpanda import AsyncSession, LightpandaError, ToolError

from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import LoginError
from utnfrsf_campus_mcp.models import LoginResult
from utnfrsf_campus_mcp.parsers.login import (
    LOGIN_PAGE_STATE_SCRIPT,
    LOGIN_RESOLVED_SCRIPT,
    is_rate_limited_message,
    same_origin,
    select_login_form,
)

logger = logging.getLogger(__name__)


class _RateLimited(Exception):
    """Señal interna; no contiene el mensaje original ni datos de la página."""


class AuthenticationService:
    def __init__(
        self,
        settings: Settings,
        session: CampusSession,
        *,
        login_url: str = urljoin(CAMPUS_BASE_URL, "login/index.php"),
    ) -> None:
        self._settings = settings
        self._session = session
        self._login_url = login_url

    async def login(self) -> LoginResult:
        """Lee credenciales privadas; solo reintenta un límite de solicitudes explícito."""
        username, password = self._settings.username, self._settings.password
        if (
            username is None
            or not username.get_secret_value().strip()
            or password is None
            or not password.get_secret_value()
        ):
            raise LoginError(
                "LOGIN_CREDENTIALS_MISSING",
                "Definí UTN_CAMPUS_USERNAME y UTN_CAMPUS_PASSWORD en .env y reiniciá el servidor.",
            )

        # bucle principal del login
        try:
            with fail_after(self._settings.login_timeout_seconds):
                async with self._session.acquire() as page:
                    for attempt in range(1, self._settings.login_max_attempts + 1):
                        try:
                            return await self._attempt(
                                page,
                                username.get_secret_value(),
                                password.get_secret_value(),
                                attempt,
                            )
                        except LightpandaError as exc:
                            if not is_rate_limited_message(str(exc)):
                                # Solo el tipo de fallo: el mensaje completo podría citar datos.
                                reason = str(exc).split(":", 1)[0][:60]
                                logger.warning("Fallo del navegador en el login: %s", reason)
                                raise LoginError(
                                    "LOGIN_BROWSER_ERROR",
                                    "Lightpanda no pudo completar el acceso. "
                                    "No se reenvió el formulario.",
                                ) from None
                        # el error boludo que te tira el campus a veces, continua reintentando
                        except _RateLimited:
                            pass

                        if attempt == self._settings.login_max_attempts:
                            raise LoginError(
                                "LOGIN_RATE_LIMITED",
                                "El campus mantiene el límite de solicitudes "
                                f"tras {attempt} intentos. "
                                "Esperá antes de volver a intentar.",
                            )
                        delay = min(
                            self._settings.login_retry_delay_seconds * 2 ** (attempt - 1), 30
                        )
                        await sleep(delay + random.uniform(0, min(delay * 0.2, 1)))
        except TimeoutError:
            raise LoginError(
                "LOGIN_TIMEOUT",
                "Se agotó el tiempo de acceso. No se reintentó un resultado incierto.",
            ) from None
        except LightpandaError:
            raise LoginError(
                "LOGIN_BROWSER_ERROR", "No se pudo iniciar o mantener la sesión de Lightpanda."
            ) from None

        raise LoginError("LOGIN_UNVERIFIED", "No se pudo verificar el resultado del acceso.")

    async def _attempt(
        self, page: AsyncSession, username: str, password: str, attempt: int
    ) -> LoginResult:
        # Cada reintento vuelve a GET /login/index.php y descubre IDs nuevos.
        # No se reutiliza el formulario ni su token de un intento anterior.
        result = await page.goto(
            url=self._login_url,
            timeout=self._settings.navigation_timeout_ms,
            wait_until="domcontentloaded",
        )
        self._check_http(result.http_status)
        state = await self._read_state(page)
        if state.get("authenticated"):
            return LoginResult(
                attempts=attempt,
                already_authenticated=True,
                message="La sesión ya está autenticada en el campus.",
            )

        form = select_login_form(await page.detect_forms(), self._login_url)
        form_selector = await self._selector(page, form.form_id)
        buttons = await page.find_element(role="button")
        matching = []
        for button in buttons:
            node_id = button.get("backendNodeId")
            if type(node_id) is not int or node_id <= 0:
                continue
            selector = await self._selector(page, node_id)
            if await self._form_is_safe(page, form_selector, selector):
                matching.append((node_id, selector))
        if len(matching) != 1:
            raise LoginError(
                "LOGIN_FORM_UNSUPPORTED", "No se identificó un botón de acceso inequívoco."
            )

        button_id, button_selector = matching[0]

        # Completa el nombre de usuario
        await page.fill(backend_node_id=form.username_id, value=username)
        await self._require_safe_form(page, form_selector, button_selector)

        # Completa la contraseña
        await page.fill(backend_node_id=form.password_id, value=password)
        await self._require_safe_form(page, form_selector, button_selector)

        # Manda el formulario (ingresa)
        result = await page.click(backend_node_id=button_id)

        self._check_http(result.http_status)

        try:
            await page.wait_for_script(
                script=LOGIN_RESOLVED_SCRIPT,
                timeout=self._settings.navigation_timeout_ms,
            )
        except ToolError as exc:
            if is_rate_limited_message(str(exc)):
                raise _RateLimited from None
            # Una espera agotada no autoriza a volver a enviar. Se inspecciona
            # el estado final y se falla de forma explícita si no hay evidencia.

        state = await self._read_state(page)
        if state.get("authenticated"):
            return LoginResult(attempts=attempt, message="Sesión autenticada en el campus.")
        if state.get("login_error"):
            raise LoginError(
                "LOGIN_REJECTED",
                "El campus rechazó el acceso. Revisá las credenciales o los avisos del sitio.",
            )
        raise LoginError(
            "LOGIN_UNVERIFIED",
            "El campus no confirmó una sesión autenticada. Puede requerir un paso interactivo.",
        )

    @staticmethod
    def _check_http(status: int | None) -> None:
        if status == 429:
            raise _RateLimited
        if status is not None and status >= 400:
            raise LoginError("LOGIN_HTTP_ERROR", f"El campus respondió con HTTP {status}.")

    async def _read_state(self, page: AsyncSession) -> dict:
        state = await page.evaluate(script=LOGIN_PAGE_STATE_SCRIPT)
        if not isinstance(state, dict):
            raise LoginError("LOGIN_UNVERIFIED", "No se pudo inspeccionar el estado del acceso.")
        if state.get("rate_limited"):
            raise _RateLimited
        if not same_origin(str(state.get("url", "")), self._login_url):
            raise LoginError(
                "LOGIN_INTERACTION_REQUIRED",
                "El acceso redirigió fuera del campus y requiere revisión.",
            )
        return state

    @staticmethod
    async def _selector(page: AsyncSession, node_id: int) -> str:
        details = await page.node_details(backend_node_id=node_id)
        selector = details.get("selector") if isinstance(details, dict) else None
        if not isinstance(selector, str) or not selector:
            raise LoginError(
                "LOGIN_FORM_UNSUPPORTED", "No se pudo verificar un elemento del formulario."
            )
        return selector

    async def _form_is_safe(self, page: AsyncSession, form: str, button: str) -> bool:
        # Solo devuelve un booleano. No lee valores de inputs ni tokens ocultos.
        script = f"""(() => {{
            const form = document.querySelector({json.dumps(form)});
            const button = document.querySelector({json.dumps(button)});
            const expected = new URL({json.dumps(self._login_url)});
            if (!form || !button || !form.contains(button) || button.disabled) return false;
            const isSubmit = button.matches('button, input[type="submit"]') &&
                (button.getAttribute('type') || 'submit').toLowerCase() === 'submit';
            if (!isSubmit) return false;
            const action = new URL(form.getAttribute('action') || location.href, location.href);
            const override = button.getAttribute('formaction');
            return location.origin === expected.origin &&
                action.origin === expected.origin && action.pathname === expected.pathname &&
                (form.getAttribute('method') || 'get').toLowerCase() === 'post' && !override;
        }})()"""
        return await page.evaluate(script=script) is True

    async def _require_safe_form(self, page: AsyncSession, form: str, button: str) -> None:
        if not await self._form_is_safe(page, form, button):
            raise LoginError(
                "LOGIN_FORM_CHANGED", "El formulario cambió antes del envío; se detuvo el acceso."
            )
