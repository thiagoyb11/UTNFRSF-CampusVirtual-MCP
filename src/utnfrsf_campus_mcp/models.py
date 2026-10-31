"""Modelos de las capacidades disponibles en la base inicial."""

from typing import Literal

from pydantic import BaseModel


class ServerInfo(BaseModel):
    """Información pública del servidor, sin probar acceso al campus."""

    name: str
    version: str
    stage: Literal["bootstrap"] = "bootstrap"
    browser: Literal["lightpanda"] = "lightpanda"
    campus_url: str
    timezone: str
    campus_features_ready: bool = False
    message: str
