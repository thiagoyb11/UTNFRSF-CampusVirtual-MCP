"""Estados, preparación, carga temporal y entrega de tareas con verificación posterior."""

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urljoin, urlsplit

from anyio import CancelScope, to_thread
from lightpanda import AsyncSession

from utnfrsf_campus_mcp.browser.downloads import session_cookie_jar
from utnfrsf_campus_mcp.browser.file_input import (
    DISCOVER_UPLOAD_API_SCRIPT,
    UPLOAD_API_SUPPORTED_SCRIPT,
    upload_browser_file,
)
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.browser.submissions import SUBMISSION_STATE_SCRIPT
from utnfrsf_campus_mcp.browser.uploads import CampusHTTP, FileUploadHelper
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import SubmissionError
from utnfrsf_campus_mcp.models import (
    PreparedSubmission,
    SubmissionFile,
    SubmissionResult,
    SubmissionStatus,
    UploadedFiles,
)
from utnfrsf_campus_mcp.parsers.login import LOGIN_PAGE_STATE_SCRIPT, same_origin
from utnfrsf_campus_mcp.parsers.resources import clean_link
from utnfrsf_campus_mcp.parsers.submissions import (
    CampusForm,
    fail,
    filemanager_options,
    parse_limits,
    prepare_submission,
    require_url,
    validate_files,
)
from utnfrsf_campus_mcp.services.authentication import AuthenticationService


@dataclass(repr=False)
class _UploadContext:
    plan: PreparedSubmission
    account_id: int
    before: SubmissionStatus
    form: CampusForm
    manager_url: str
    created_at: float = field(default_factory=time.monotonic)
    phase: str = "temporary"
    result: SubmissionResult | None = None


def _fingerprint(status: SubmissionStatus) -> str:
    return json.dumps(
        [
            status.state,
            [(f.name, f.url) for f in status.files],
            status.evidence[3] if len(status.evidence) > 3 else None,
        ],
        sort_keys=True,
    )


class SubmissionService:
    def __init__(
        self, settings: Settings, session: CampusSession, authentication: AuthenticationService
    ):
        self._settings, self._session, self._authentication = settings, session, authentication
        self._uploads: dict[str, _UploadContext] = {}

    @staticmethod
    def prepare_submission(
        course_id: int, activity_id: int, files: list[str]
    ) -> PreparedSubmission:
        return prepare_submission(course_id, activity_id, files)

    async def _read_status(self, page: AsyncSession, course_id: int, activity_id: int):
        if (
            type(course_id) is not int
            or course_id <= 0
            or type(activity_id) is not int
            or activity_id <= 0
        ):
            raise fail(
                "SUBMISSION_INVALID_ACTIVITY", "Indicá IDs enteros positivos de curso y actividad."
            )
        url = urljoin(CAMPUS_BASE_URL, f"mod/assign/view.php?id={activity_id}")
        result = await page.goto(
            url=url, timeout=self._settings.navigation_timeout_ms, wait_until="domcontentloaded"
        )
        if result.http_status != 200:
            raise fail("SUBMISSION_ACCESS_DENIED", "No se pudo abrir la tarea indicada.")
        session = await page.evaluate(script=LOGIN_PAGE_STATE_SCRIPT)
        if not isinstance(session, dict) or session.get("authenticated") is not True:
            raise fail("SUBMISSION_SESSION_EXPIRED", "La sesión no está activa.")
        if not same_origin(str(session.get("url", "")), CAMPUS_BASE_URL):
            raise fail("SUBMISSION_ACCESS_DENIED", "La navegación salió del campus.")
        await page.wait_for_selector(
            selector="#region-main", timeout=self._settings.navigation_timeout_ms
        )
        raw = await page.evaluate(script=SUBMISSION_STATE_SCRIPT)
        if (
            not isinstance(raw, dict)
            or str(raw.get("course_id")) != str(course_id)
            or raw.get("body") != "page-mod-assign-view"
            or raw.get("error")
            or not same_origin(str(raw.get("url", "")), CAMPUS_BASE_URL)
            or parse_qs(urlsplit(raw["url"]).query).get("id") != [str(activity_id)]
        ):
            raise fail(
                "SUBMISSION_INVALID_ACTIVITY",
                "La página no corresponde a la tarea y materia solicitadas.",
            )
        rows = raw.get("rows")
        if not isinstance(rows, list) or not rows:
            raise fail(
                "SUBMISSION_FORMAT_UNSUPPORTED",
                "No se pudo verificar la tabla de estado de la cuenta.",
            )
        classes = " ".join(r.get("classes", "") for r in rows)
        codes = re.findall(r"\bsubmissionstatus(new|draft|submitted|reopened)\b", classes)
        state = codes[0] if len(set(codes)) == 1 else "unknown"
        actions = {}
        for action in raw.get("actions", []):
            target = require_url(action["url"], ("/mod/assign/view.php",))
            if parse_qs(urlsplit(target).query).get("id") != [str(activity_id)]:
                raise fail("SUBMISSION_CONTEXT_CHANGED", "Una acción corresponde a otra tarea.")
            if action["action"] in actions and actions[action["action"]] != target:
                raise fail("SUBMISSION_FORMAT_UNSUPPORTED", "Hay acciones ambiguas en la tarea.")
            actions[action["action"]] = target
        files = []
        for row in raw.get("files", []):
            if (
                not same_origin(row["url"], CAMPUS_BASE_URL)
                or clean_link(row["url"], CAMPUS_BASE_URL) != row["url"]
            ):
                raise fail("SUBMISSION_ACCESS_DENIED", "Un archivo de entrega salió del campus.")
            files.append(SubmissionFile(**row))
        status = SubmissionStatus(
            course_id=course_id,
            activity_id=activity_id,
            name=raw.get("name") or f"Tarea {activity_id}",
            source_url=url,
            state=state,
            can_edit="editsubmission" in actions,
            files=files,
            evidence=[row.get("text", "") for row in rows],
        )
        account_id = int(raw.get("account_id", 0))
        if account_id <= 0:
            raise fail(
                "SUBMISSION_SESSION_EXPIRED", "No se pudo identificar la sesión de la cuenta."
            )
        return status, actions, account_id

    async def get_submission_status(self, course_id: int, activity_id: int) -> SubmissionStatus:
        if (
            type(course_id) is not int
            or course_id <= 0
            or type(activity_id) is not int
            or activity_id <= 0
        ):
            raise fail(
                "SUBMISSION_INVALID_ACTIVITY", "Indicá IDs enteros positivos de curso y actividad."
            )
        await self._authentication.login()
        async with self._session.acquire() as page:
            return (await self._read_status(page, course_id, activity_id))[0]

    async def _http(self, page, referer: str | None = None):
        user_agent = await page.evaluate(script="navigator.userAgent")
        return CampusHTTP(
            session_cookie_jar(await page.get_cookies(url=CAMPUS_BASE_URL)),
            user_agent if isinstance(user_agent, str) else "CampusVirtualMCP/0.1",
            referer=referer,
        )

    async def upload_files(
        self, course_id: int, activity_id: int, files: list[str]
    ) -> UploadedFiles:
        plan = prepare_submission(course_id, activity_id, files)
        self._uploads = {
            k: v for k, v in self._uploads.items() if time.monotonic() - v.created_at < 1800
        }
        if len(self._uploads) >= 32:
            raise fail("UPLOAD_TOO_MANY_RECEIPTS", "Hay demasiadas cargas recientes en memoria.")
        await self._authentication.login()
        async with self._session.acquire() as page:
            before, actions, account = await self._read_status(page, course_id, activity_id)
            if before.files or before.state in ("draft", "submitted", "reopened"):
                raise fail(
                    "SUBMISSION_ALREADY_EXISTS",
                    "La tarea ya tiene una entrega; no se modificó ni reemplazó.",
                )
            if not before.can_edit:
                raise fail(
                    "SUBMISSION_NOT_EDITABLE", "El campus no ofrece edición para esta tarea."
                )
            http = await self._http(page, actions["editsubmission"])
            document = await to_thread.run_sync(http.document, actions["editsubmission"])
            forms = [
                f
                for f in document.forms
                if f.method == "post" and f.fields.get("_qf__mod_assign_submission_form") == "1"
            ]
            if document.body_id != "page-mod-assign-editsubmission" or len(forms) != 1:
                raise fail(
                    "SUBMISSION_FORM_UNSUPPORTED", "No se identificó el formulario de entrega."
                )
            form = forms[0]
            require_url(form.action, ("/mod/assign/view.php",))
            if (
                form.fields.get("id") != str(activity_id)
                or form.fields.get("action") != "savesubmission"
                or form.fields.get("userid") not in ("0", str(account))
                or "sesskey" not in form.fields
                or "submitbutton" not in form.submits
            ):
                raise fail(
                    "SUBMISSION_CONTEXT_CHANGED", "El formulario cambió de destino o de cuenta."
                )
            if any(
                value.strip()
                for name, value in form.fields.items()
                if name.startswith("onlinetext_editor[") and name.endswith("[text]")
            ):
                raise fail(
                    "SUBMISSION_ALREADY_EXISTS", "La tarea ya contiene texto; no se reemplazó."
                )
            draft_id = form.fields.get("files_filemanager", "")
            if not draft_id.isdigit() or int(draft_id) <= 0:
                raise fail(
                    "UPLOAD_MANAGER_UNSUPPORTED",
                    "La tarea no ofrece el gestor de archivos compatible.",
                )
            config = filemanager_options(document, draft_id)
            limits = parse_limits(config)
            objects = [
                url
                for url in document.objects
                if urlsplit(url).path == "/repository/draftfiles_manager.php"
                and parse_qs(urlsplit(url).query).get("itemid") == [draft_id]
                and parse_qs(urlsplit(url).query).get("course") == [str(course_id)]
            ]
            if len(objects) != 1 or int(config.get("filecount", -1)) != 0:
                raise fail(
                    "UPLOAD_MANAGER_UNSUPPORTED",
                    "El gestor no identifica una única área temporal vacía.",
                )
            upload_transport = None
            if await page.evaluate(script=UPLOAD_API_SUPPORTED_SCRIPT) is True:
                loop = asyncio.get_running_loop()

                def upload_transport(form, file):
                    future = asyncio.run_coroutine_threadsafe(
                        upload_browser_file(page, form, file), loop
                    )
                    try:
                        return future.result(timeout=240)
                    except SubmissionError:
                        raise
                    except TimeoutError:
                        future.cancel()
                        raise fail(
                            "SUBMISSION_WRITE_UNCERTAIN",
                            "La carga agotó el tiempo; revisá el área temporal.",
                        ) from None
                    except Exception:
                        raise fail(
                            "SUBMISSION_WRITE_UNCERTAIN",
                            "Se debe verificar la carga realizada por el navegador.",
                        ) from None

            ajax_form = None
            if await page.evaluate(script=DISCOVER_UPLOAD_API_SCRIPT) is True:
                picker = config.get("filepicker", {})
                repos = picker.get("repositories", {})
                entries = list(repos.values()) if isinstance(repos, dict) else repos
                uploads = [r for r in entries if r.get("type") == "upload"]
                if len(uploads) != 1:
                    raise fail(
                        "UPLOAD_FORM_UNSUPPORTED", "No se identificó un repositorio de carga único."
                    )
                binding = parse_qs(urlsplit(objects[0]).query)
                # Solo los parámetros del cliente AJAX; course/subdirs/maxfiles
                # pertenecen al gestor sin JS y se validan localmente.
                fields = {key: binding[key][0] for key in ("ctx_id", "sesskey", "itemid")}
                fields.update(
                    {
                        "repo_id": str(uploads[0]["id"]),
                        "itemid": draft_id,
                        "p": "",
                        "page": "",
                        "maxbytes": str(config["maxbytes"]),
                        "areamaxbytes": str(config["areamaxbytes"]),
                        "savepath": "/",
                        "env": "filemanager",
                        "client_id": str(config.get("client_id", "")),
                        "title": "",
                        "license": str(picker.get("defaultlicense", "")),
                        "author": str(picker.get("author", "")),
                    }
                )
                raw_types = config.get("accepted_types", [])
                if isinstance(raw_types, str):
                    raw_types = [raw_types] if raw_types and raw_types != "*" else []
                for index, value in enumerate(raw_types):
                    fields[f"accepted_types[{index}]"] = value
                ajax_form = CampusForm(
                    urljoin(CAMPUS_BASE_URL, "repository/repository_ajax.php?action=upload"),
                    "post",
                    "multipart/form-data",
                    fields=fields,
                    file_fields=["repo_upload_file"],
                )
                # El API AJAX usa HTTP con el contexto del formulario observado.
                # El puente File/FileList se reserva para el formulario sin JavaScript.
                upload_transport = None
            helper = FileUploadHelper(http, objects[0], limits, upload_transport, ajax_form)
            with CancelScope(shield=True):
                verified = await to_thread.run_sync(helper.upload_files, plan.files)
                # Mantiene comprobación local y de cuenta separadas del POST de entrega.
                after, _, current_account = await self._read_status(page, course_id, activity_id)
                if current_account != account or _fingerprint(after) != _fingerprint(before):
                    raise fail(
                        "SUBMISSION_CONTEXT_CHANGED",
                        "La tarea cambió durante la carga temporal; no se guardó.",
                    )
                receipt = uuid.uuid4().hex
                self._uploads[receipt] = _UploadContext(plan, account, before, form, objects[0])
                return UploadedFiles(
                    upload_id=receipt,
                    course_id=course_id,
                    activity_id=activity_id,
                    files=verified,
                    limits=limits,
                )

    @staticmethod
    def _save_fields(form: CampusForm, accept_statement: bool) -> dict[str, str]:
        fields = dict(form.fields)
        for name in form.checkboxes:
            if name != "submissionstatement":
                if name in form.required:
                    raise fail(
                        "SUBMISSION_FORM_UNSUPPORTED",
                        "La tarea exige un campo adicional no soportado.",
                    )
                continue
            if not accept_statement:
                raise fail(
                    "SUBMISSION_STATEMENT_REQUIRED",
                    "La declaración de entrega requiere aceptación explícita.",
                )
            fields[name] = "1"
        if any(not fields.get(name) for name in form.required if name != "files_filemanager"):
            raise fail(
                "SUBMISSION_REQUIRED_FIELD",
                "El formulario tiene campos obligatorios sin completar.",
            )
        if "submitbutton" not in form.submits:
            raise fail(
                "SUBMISSION_FORM_UNSUPPORTED",
                "El formulario no tiene un botón de guardado verificable.",
            )
        fields["submitbutton"] = form.submits["submitbutton"]
        return fields

    async def _verify_files(
        self, http: CampusHTTP, status: SubmissionStatus, plan: PreparedSubmission
    ) -> bool:
        links = {f.name: f.url for f in status.files}
        if set(links) != {f.name for f in plan.files}:
            return False
        for file in plan.files:
            actual = await to_thread.run_sync(http.hash_file, links[file.name], file.size_bytes + 1)
            if actual != (file.size_bytes, file.sha256):
                return False
        return True

    async def submit_assignment(
        self, upload_id: str, finalize: bool = False, accept_statement: bool = False
    ) -> SubmissionResult:
        context = self._uploads.get(upload_id)
        if context is None or time.monotonic() - context.created_at >= 1800:
            raise fail(
                "UPLOAD_RECEIPT_EXPIRED", "El recibo no existe o venció; no se reenvió la entrega."
            )
        if context.phase in ("submitted", "uncertain") or context.phase == "saved" and not finalize:
            if context.result is None:
                raise fail("SUBMISSION_IN_PROGRESS", "El recibo ya está siendo procesado.")
            return context.result
        plan = context.plan
        fresh = prepare_submission(plan.course_id, plan.activity_id, [f.path for f in plan.files])
        if fresh.files != plan.files:
            raise fail(
                "UPLOAD_FILE_CHANGED", "Los archivos locales cambiaron; no se guardó la entrega."
            )
        await self._authentication.login()
        async with self._session.acquire() as page:
            status, actions, account = await self._read_status(
                page, plan.course_id, plan.activity_id
            )
            if account != context.account_id:
                raise fail(
                    "SUBMISSION_CONTEXT_CHANGED", "La cuenta cambió después de preparar la carga."
                )
            http = await self._http(page, actions.get("editsubmission", status.source_url))
            if context.phase == "temporary":
                if _fingerprint(status) != _fingerprint(context.before) or not status.can_edit:
                    raise fail(
                        "SUBMISSION_CONTEXT_CHANGED",
                        "El estado de la tarea cambió antes del guardado.",
                    )
                current_edit = await to_thread.run_sync(http.document, actions["editsubmission"])
                current_forms = [
                    f
                    for f in current_edit.forms
                    if f.fields.get("_qf__mod_assign_submission_form") == "1" and f.method == "post"
                ]
                if len(current_forms) != 1:
                    raise fail("SUBMISSION_FORM_UNSUPPORTED", "El formulario de entrega cambió.")
                current_form = current_forms[0]
                if (
                    set(current_form.fields) != set(context.form.fields)
                    or current_form.required != context.form.required
                    or current_form.checkboxes != context.form.checkboxes
                    or any(
                        current_form.fields.get(k) != context.form.fields.get(k)
                        for k in ("id", "userid", "sesskey", "action")
                    )
                ):
                    raise fail(
                        "SUBMISSION_CONTEXT_CHANGED", "El formulario o sus restricciones cambiaron."
                    )
                current_draft = current_form.fields.get("files_filemanager", "")
                current_limits = parse_limits(filemanager_options(current_edit, current_draft))
                validate_files(plan.files, current_limits, [])
                fields = self._save_fields(context.form, accept_statement)
                # Comprobar el draft completo justo antes de convertirlo en una entrega.
                helper = FileUploadHelper(
                    http,
                    context.manager_url,
                    parse_limits(
                        {
                            "maxfiles": len(plan.files),
                            "maxbytes": 0,
                            "areamaxbytes": -1,
                            "accepted_types": ["*"],
                        }
                    ),
                )
                links = await to_thread.run_sync(helper.listing)
                if set(links) != {f.name for f in plan.files}:
                    raise fail("UPLOAD_DRAFT_CHANGED", "El área temporal cambió antes de guardar.")
                for file in plan.files:
                    actual = await to_thread.run_sync(
                        http.hash_file, links[file.name], file.size_bytes + 1
                    )
                    if actual != (file.size_bytes, file.sha256):
                        raise fail("UPLOAD_DRAFT_CHANGED", "Los bytes del área temporal cambiaron.")
                with CancelScope(shield=True):
                    context.phase = "uncertain"
                    try:
                        await to_thread.run_sync(http.post_form, context.form, fields)
                    except Exception:
                        pass  # Siempre se reconcilia el estado posterior, sin reenviar.
                    context.result = await self._reconcile(page, http, upload_id, context)
                if context.phase != "saved" or not finalize:
                    return context.result
                status, actions, account = await self._read_status(
                    page, plan.course_id, plan.activity_id
                )
            if context.phase == "saved" and finalize:
                if account != context.account_id or not await self._verify_files(
                    http, status, plan
                ):
                    raise fail(
                        "SUBMISSION_CONTEXT_CHANGED",
                        "La entrega guardada cambió antes de finalizar.",
                    )
                targets = [actions[a] for a in ("submit", "submitforgrading") if a in actions]
                if len(targets) != 1:
                    return context.result
                confirmation = await to_thread.run_sync(http.document, targets[0])
                forms = [
                    f
                    for f in confirmation.forms
                    if f.method == "post"
                    and f.fields.get("id") == str(plan.activity_id)
                    and "sesskey" in f.fields
                    and f.fields.get("action") in ("submit", "submitforgrading")
                    and any(k.startswith("_qf__mod_assign_") for k in f.fields)
                ]
                if len(forms) != 1:
                    raise fail(
                        "SUBMISSION_CONFIRMATION_UNSUPPORTED",
                        "No se identificó una confirmación de entrega compatible.",
                    )
                require_url(forms[0].action, ("/mod/assign/view.php",))
                fields = self._save_fields(forms[0], accept_statement)
                with CancelScope(shield=True):
                    context.phase = "uncertain"
                    try:
                        await to_thread.run_sync(http.post_form, forms[0], fields)
                    except Exception:
                        pass
                    context.result = await self._reconcile(page, http, upload_id, context)
            return context.result

    async def _reconcile(self, page, http, upload_id, context) -> SubmissionResult:
        status = None
        verified = False
        try:
            status, _, account = await self._read_status(
                page, context.plan.course_id, context.plan.activity_id
            )
            verified = account == context.account_id and await self._verify_files(
                http, status, context.plan
            )
        except Exception:
            pass
        if verified and status.state in ("submitted", "draft"):
            context.phase = "submitted" if status.state == "submitted" else "saved"
        else:
            context.phase = "uncertain"
        return SubmissionResult(
            upload_id=upload_id,
            stage=context.phase,
            status=status,
            files_verified=verified,
            message=(
                "Entrega verificada en el campus."
                if context.phase == "submitted"
                else "Borrador verificado; falta el envío definitivo."
                if context.phase == "saved"
                else "Resultado incierto: no se reintentó la escritura. "
                "Consultá el estado antes de continuar."
            ),
        )
