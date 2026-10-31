"""Identificación del formulario observado y clasificación del estado de página."""

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit

from utnfrsf_campus_mcp.errors import LoginError

# Los nombres username/password y el POST a login/index.php se comprobaron
# con detectForms en la página pública. Nunca se extraen los valores ocultos.
LOGIN_PAGE_STATE_SCRIPT = r"""(() => {
    const body = document.body;
    const text = body ? body.innerText : '';
    const userId = Number(globalThis.M?.cfg?.userId || 0);
    const loginForm = [...document.forms].some(form =>
        form.querySelector('input[name="username"]') &&
        form.querySelector('input[name="password"][type="password"]'));
    const error = [...document.querySelectorAll('[role="alert"], .alert-danger')]
        .some(element => element.textContent.trim());
    return {
        url: location.href,
        authenticated: Number.isSafeInteger(userId) && userId > 0 && !loginForm &&
            !body?.classList.contains('notloggedin'),
        login_form: loginForm,
        login_error: error,
        rate_limited: /too[\s_-]*many[\s_-]*requests|demasiadas\s+solicitudes/i.test(text)
    };
})()"""

LOGIN_RESOLVED_SCRIPT = f"""(() => {{
    const state = {LOGIN_PAGE_STATE_SCRIPT};
    return state.authenticated || state.rate_limited || state.login_error ||
        location.origin !== new URL(globalThis.M?.cfg?.wwwroot || location.href).origin;
}})()"""


def is_rate_limited_message(message: str) -> bool:
    """Reconoce el error de Lightpanda sin copiarlo a logs ni respuestas MCP."""
    return bool(
        re.search(r"too[\s_-]*many[\s_-]*requests|\b429\b|demasiadas\s+solicitudes", message, re.I)
    )


def same_origin(url: str, base_url: str) -> bool:
    """Compara esquema, host y puerto sin aceptar usuario o contraseña en URL."""
    try:
        target, base = urlsplit(url), urlsplit(base_url)
        return (
            target.username is None
            and target.password is None
            and (target.scheme, target.hostname, target.port)
            == (base.scheme, base.hostname, base.port)
        )
    except ValueError:
        return False


@dataclass(frozen=True)
class LoginForm:
    form_id: int
    username_id: int
    password_id: int


def select_login_form(payload: Any, login_url: str) -> LoginForm:
    """Acepta exactamente un formulario POST al destino esperado."""
    forms = payload.get("forms", []) if isinstance(payload, dict) else payload
    candidates = []
    for form in forms if isinstance(forms, list) else []:
        if not isinstance(form, dict):
            continue
        fields = [field for field in form.get("fields", []) if isinstance(field, dict)]
        usernames = [field for field in fields if field.get("name") == "username"]
        passwords = [
            field
            for field in fields
            if field.get("name") == "password" and field.get("inputType") == "password"
        ]
        if len(usernames) != 1 or len(passwords) != 1:
            continue
        action = urljoin(login_url, str(form.get("action", "")))
        if (
            str(form.get("method", "")).lower() != "post"
            or not same_origin(action, login_url)
            or urlsplit(action).path != urlsplit(login_url).path
            or any(field.get("disabled") for field in (usernames[0], passwords[0]))
        ):
            continue
        ids = [
            form.get("backendNodeId"),
            *(f.get("backendNodeId") for f in (usernames[0], passwords[0])),
        ]
        if all(type(value) is int and value > 0 for value in ids):
            candidates.append(LoginForm(*ids))
    if len(candidates) != 1:
        raise LoginError(
            "LOGIN_FORM_UNSUPPORTED", "No se pudo identificar un formulario de acceso inequívoco."
        )
    return candidates[0]
