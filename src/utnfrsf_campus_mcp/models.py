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
