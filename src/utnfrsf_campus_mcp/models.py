"""Modelos de las capacidades disponibles en la base inicial."""

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel

# Nivel de evidencia de una herramienta. Se ordena de menor a mayor:
# - local_tests: solo pruebas locales con fixtures o dobles del adaptador.
# - campus_partial: verificada en el campus real para una parte de su alcance.
# - campus_verified: su alcance documentado se comprobó en el campus real.
CapabilityStatus = Literal["local_tests", "campus_partial", "campus_verified"]

# Efecto observable de una llamada; debe coincidir con las anotaciones MCP:
# - none: no lee el campus ni archivos del usuario.
# - local_read: lee archivos locales, sin peticiones al campus.
# - session: abre o reutiliza la sesión del campus, sin datos académicos.
# - campus_read: consulta el campus sin modificar datos académicos ni locales.
# - local_write: lee el campus y escribe archivos locales, como descargas.
# - campus_write: modifica datos del campus, como cargas temporales o entregas.
CapabilityEffect = Literal[
    "none", "local_read", "session", "campus_read", "local_write", "campus_write"
]


class Capability(BaseModel):
    """Estado declarado de una herramienta MCP registrada."""

    tool: str
    feature_ids: list[str]
    effect: CapabilityEffect
    status: CapabilityStatus
    verified_on: date | None
    scope: str
    pending: list[str]
    docs: str


class ServerInfo(BaseModel):
    """Información pública del servidor, sin probar acceso al campus."""

    name: str
    version: str
    browser: Literal["lightpanda"] = "lightpanda"
    campus_url: str
    timezone: str
    registered_tools: list[str]
    capabilities: list[Capability]
    undocumented_tools: list[str]
    pending_features_doc: str
    message: str


class LoginResult(BaseModel):
    """Confirmación de sesión; no contiene identidad, tokens ni credenciales."""

    status: Literal["authenticated"] = "authenticated"
    already_authenticated: bool = False
    attempts: int
    message: str


class Course(BaseModel):
    """Asignatura identificada por su ID, nombre completo y enlace al campus."""

    id: int
    name: str
    url: str


class CourseList(BaseModel):
    """Materias visibles en Grado; una extracción incompleta produce un error."""

    scope: Literal["Grado"] = "Grado"
    source_url: str
    fetched_at: AwareDatetime
    total: int
    courses: list[Course]
    complete: Literal[True] = True


class CalendarActivity(BaseModel):
    """Evento de actividad; un cierre y un vencimiento son eventos diferentes."""

    event_id: int
    activity_id: int
    name: str
    event_name: str
    module: str
    event_type: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None
    deadline_at: AwareDatetime | None
    deadline_kind: Literal["due", "close"] | None
    course: Course
    activity_url: str
    calendar_url: str


class MonthlyActivities(BaseModel):
    """Calendario del mes visible para la cuenta; no confirma el estado de entrega."""

    year: int
    month: int
    timezone: str
    timezone_source: Literal["campus", "configuration"]
    deadlines_only: bool
    source_url: str
    fetched_at: AwareDatetime
    total: int
    activities: list[CalendarActivity]
    warnings: list[str]


class CourseSection(BaseModel):
    """Sección observada, incluso si no tiene enlace habilitado."""

    index: int
    id: int | None = None
    name: str | None = None
    url: str | None = None
    available: bool = True
    visited: bool = False


class CourseLink(BaseModel):
    """Enlace con su procedencia; file indica destino, no descarga verificada."""

    name: str
    url: str
    kind: Literal["file", "assignment", "folder", "resource", "activity", "external", "link"]
    section_index: int
    module_id: int | None = None
    module_type: str | None = None
    source_url: str


class UnlinkedActivity(BaseModel):
    """Actividad observada sin un href disponible; nunca se fabrica su URL."""

    module_id: int
    module_type: str
    name: str
    section_index: int
    availability: str | None = None


class CourseResources(BaseModel):
    """Inventario de enlaces del curso y alcance efectivo de la consulta."""

    course: Course
    format: Literal["topics", "onetopic"]
    fetched_at: AwareDatetime
    total: int
    links: list[CourseLink]
    sections: list[CourseSection]
    unlinked_activities: list[UnlinkedActivity]
    complete: bool
    pending_urls: list[str]
    warnings: list[str]


class DownloadedFile(BaseModel):
    """Archivo completo guardado localmente sin sobrescribir archivos existentes."""

    name: str
    path: str
    source_url: str
    size_bytes: int
    sha256: str
    content_type: str
    downloaded_at: AwareDatetime


class DownloadFailure(BaseModel):
    source_url: str
    code: str
    message: str


class DownloadedResources(BaseModel):
    course: Course
    module_id: int
    complete: bool
    files: list[DownloadedFile]
    failures: list[DownloadFailure]


class LocalSubmissionFile(BaseModel):
    path: str
    name: str
    size_bytes: int
    sha256: str


class PreparedSubmission(BaseModel):
    course_id: int
    activity_id: int
    files: list[LocalSubmissionFile]


class SubmissionFile(BaseModel):
    name: str
    url: str


class SubmissionStatus(BaseModel):
    course_id: int
    activity_id: int
    name: str
    source_url: str
    state: Literal["new", "draft", "submitted", "reopened", "unknown"]
    can_edit: bool
    files: list[SubmissionFile]
    evidence: list[str]


class UploadLimits(BaseModel):
    max_files: int
    max_file_bytes: int
    max_area_bytes: int
    accepted_types: list[str]


class UploadedFiles(BaseModel):
    upload_id: str
    stage: Literal["temporary"] = "temporary"
    course_id: int
    activity_id: int
    files: list[LocalSubmissionFile]
    limits: UploadLimits
    verified: bool = True
    message: str = "Archivos verificados en el área temporal; la entrega no se guardó."


class SubmissionResult(BaseModel):
    upload_id: str
    stage: Literal["saved", "submitted", "uncertain"]
    status: SubmissionStatus | None
    files_verified: bool
    message: str
