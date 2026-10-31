"""Modelos de las capacidades disponibles en la base inicial."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel


class ServerInfo(BaseModel):
    """Información pública del servidor, sin probar acceso al campus."""

    name: str
    version: str
    stage: Literal["calendar"] = "calendar"
    browser: Literal["lightpanda"] = "lightpanda"
    campus_url: str
    timezone: str
    campus_features_ready: bool = True
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
