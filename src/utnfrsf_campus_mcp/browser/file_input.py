"""Puente de bytes locales a File/FormData en Lightpanda, sin simular un input de texto."""

import base64
import json
import logging
import mimetypes
import time
import uuid

from anyio import open_file
from lightpanda import AsyncSession

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.models import LocalSubmissionFile
from utnfrsf_campus_mcp.parsers.login import same_origin
from utnfrsf_campus_mcp.parsers.submissions import CampusForm, fail, require_url

_logger = logging.getLogger(__name__)

# Comprueba que el navegador tenga las APIs necesarias para armar un archivo en memoria.
UPLOAD_API_SUPPORTED_SCRIPT = (
    "typeof File === 'function' && typeof FormData === 'function' && "
    "typeof Uint8Array === 'function'"
)


async def upload_browser_file(
    page: AsyncSession, form: CampusForm, file: LocalSubmissionFile
) -> None:
    """Una sola petición; una redirección se reconcilia leyendo el draft, sin seguirla."""
    # Solo se sube a los dos endpoints de carga de Moodle.
    require_url(form.action, ("/repository/filepicker.php", "/repository/repository_ajax.php"))
    # Variable global con nombre aleatorio donde el navegador acumula el archivo y el resultado.
    key = "__campus_upload_" + uuid.uuid4().hex
    slot = f"globalThis[{json.dumps(key)}]"
    await page.evaluate(script=f"{slot} = {{chunks: [], done: false}}; true")
    try:
        # 1. Copia el archivo al navegador en bloques de 256 KiB codificados en base64.
        async with await open_file(file.path, "rb") as source:
            while block := await source.read(256 * 1024):
                encoded = json.dumps(base64.b64encode(block).decode("ascii"))
                await page.evaluate(
                    script=f"""(() => {{
                    const raw = atob({encoded});
                    {slot}.chunks.push(Uint8Array.from(raw, ch => ch.charCodeAt(0)));
                    return true;
                }})()"""
                )
        # 2. Arma el File y elige cómo enviarlo: un formulario nativo con <input type=file>
        #    (filepicker.php, si DataTransfer funciona) o un POST con FormData y fetch.
        fields = json.dumps(form.fields)
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        script = f"""(() => {{
            const context = {slot};
            const file = new File(context.chunks, {json.dumps(file.name)},
                {{type: {json.dumps(mime)}}});
            context.chunks = [];
            if (typeof DataTransfer === 'function' &&
                new URL({json.dumps(form.action)}, location.href).pathname ===
                    '/repository/filepicker.php') {{
                try {{
                    const nativeForm = document.createElement('form');
                    nativeForm.id = {json.dumps(key)};
                    nativeForm.method = 'post';
                    nativeForm.action = {json.dumps(form.action)};
                    nativeForm.enctype = 'multipart/form-data';
                    for (const [name, value] of Object.entries({fields})) {{
                        const input = document.createElement('input');
                        input.type = 'hidden'; input.name = name; input.value = value;
                        nativeForm.appendChild(input);
                    }}
                    const input = document.createElement('input');
                    input.type = 'file'; input.name = 'repo_upload_file';
                    const transfer = new DataTransfer(); transfer.items.add(file);
                    input.files = transfer.files;
                    if (input.files.length !== 1 || input.files[0].size !== file.size) {{
                        throw Error();
                    }}
                    nativeForm.appendChild(input);
                    const submit = document.createElement('button'); submit.type = 'submit';
                    submit.id = {json.dumps(key + "_submit")}; nativeForm.appendChild(submit);
                    document.body.appendChild(nativeForm);
                    return {{native: true}};
                }} catch (_) {{
                    // FileList no soportado: usar FormData antes de cualquier POST.
                }}
            }}
            const form = new FormData();
            for (const [name, value] of Object.entries({fields})) form.append(name, value);
            form.append('repo_upload_file', file);
            fetch({json.dumps(form.action)}, {{method: 'POST', credentials: 'same-origin',
                redirect: 'error', body: form,
                headers: {{'X-Requested-With': 'XMLHttpRequest'}}}}).then(async response => {{
                    context.status = response.status;
                    context.metadata = {{
                        retry_after: response.headers.get('retry-after'),
                        content_type: response.headers.get('content-type'),
                        server: response.headers.get('server'),
                        challenge: response.headers.get('cf-mitigated') === 'challenge'
                    }};
                    if (response.status >= 400) {{
                        const text = await response.text();
                        context.metadata.rate_limit_text =
                            /TooManyRequests|Too Many Requests|rate.limit|demasiadas/i.test(text);
                        context.metadata.upload_error =
                            /upload|multipart|archivo|virus/i.test(text);
                    }}
                    context.done = true;
                }}).catch(() => {{ context.status = 0; context.done = true; }});
            return true;
        }})()"""
        mode = await page.evaluate(script=script)
        # 3a. Formulario nativo: se pulsa su botón y se valida la respuesta de la navegación.
        if isinstance(mode, dict) and mode.get("native") is True:
            result = await page.click(selector="#" + key + "_submit")
            if result.http_status == 429:
                raise fail(
                    "SUBMISSION_RATE_LIMITED",
                    "El campus limitó el formulario nativo; no se reenvió.",
                )
            if result.url and not same_origin(result.url, CAMPUS_BASE_URL):
                raise fail("SUBMISSION_ACCESS_DENIED", "El formulario redirigió fuera del campus.")
            return
        # 3b. fetch: se consulta el estado hasta que termine, con un presupuesto de 180 s.
        started = time.monotonic()
        while time.monotonic() - started < 180:
            result = await page.evaluate(
                script=f"""(() => {{
                const context = {slot};
                return {{done: context?.done === true, status: context?.status || 0,
                    metadata: context?.metadata || {{}}}};
            }})()"""
            )
            if isinstance(result, dict) and result.get("done"):
                status = result.get("status")
                # Ante un 429 se registran solo metadatos (cabeceras y banderas), nunca el
                # cuerpo de la respuesta, y no se reintenta.
                if status == 429:
                    metadata = result.get("metadata", {})
                    _logger.warning(
                        "Carga HTTP 429: %s",
                        {
                            key: metadata.get(key)
                            for key in (
                                "retry_after",
                                "content_type",
                                "server",
                                "challenge",
                                "rate_limit_text",
                                "upload_error",
                            )
                        },
                    )
                    raise fail(
                        "SUBMISSION_RATE_LIMITED",
                        "El campus limitó la carga desde el navegador; no se reintentó.",
                    )
                if status in (401, 403):
                    raise fail("SUBMISSION_ACCESS_DENIED", "El campus denegó la carga de archivos.")
                # Otro estado no prueba ni éxito ni fracaso: hay que revisar el área temporal.
                if status != 200:
                    raise fail(
                        "SUBMISSION_WRITE_UNCERTAIN",
                        "La carga requiere verificar el área temporal.",
                    )
                return
            # Espera hasta 5 s a que termine; si vence, el bucle vuelve a consultar el estado.
            try:
                await page.wait_for_script(script=f"{slot}?.done === true", timeout=5000)
            except Exception:
                pass
        raise fail(
            "SUBMISSION_WRITE_UNCERTAIN",
            "La carga no terminó dentro del presupuesto; verificá el área temporal.",
        )
    finally:
        # Libera los bytes que quedaron en memoria del navegador.
        try:
            await page.evaluate(script=f"delete globalThis[{json.dumps(key)}]; true")
        except Exception:
            pass  # Una navegación nativa destruye el contexto anterior y sus buffers.


# Confirma que el filepicker de este Moodle usa el endpoint y el campo de carga esperados,
# leyendo su JavaScript público, antes de intentar subir archivos.
DISCOVER_UPLOAD_API_SCRIPT = r"""return await (async () => {
    try {
        const response = await fetch(new URL('/repository/filepicker.js', location.href), {
            credentials: 'same-origin', redirect: 'error'
        });
        if (!response.ok) return false;
        const text = await response.text();
        return text.includes('/repository/repository_ajax.php') &&
            text.includes('repo_upload_file') && text.includes('create_upload_form');
    } catch (_) { return false; }
})()"""
