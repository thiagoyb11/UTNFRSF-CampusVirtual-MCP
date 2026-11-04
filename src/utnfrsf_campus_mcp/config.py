"""Configuración local y credenciales que nunca se publican mediante MCP."""

from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CAMPUS_BASE_URL = "https://campusvirtual.frsf.utn.edu.ar/"


class Settings(BaseSettings):
    """Lee .env y variables UTN_CAMPUS_*; el entorno tiene prioridad."""

    model_config = SettingsConfigDict(
        env_prefix="UTN_CAMPUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    timezone: str = "America/Argentina/Cordoba"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    browser_timeout_seconds: float = Field(default=45, gt=0, le=300, allow_inf_nan=False)
    browser_idle_seconds: float = Field(default=60, gt=0, le=3600, allow_inf_nan=False)
    navigation_timeout_ms: int = Field(default=30_000, gt=0, le=120_000)
    lightpanda_binary: Path | None = None
    username: SecretStr | None = Field(default=None, repr=False, exclude=True)
    password: SecretStr | None = Field(default=None, repr=False, exclude=True)
    login_max_attempts: int = Field(default=3, ge=1, le=5)
    login_retry_delay_seconds: float = Field(default=2, ge=0.5, le=30, allow_inf_nan=False)
    login_timeout_seconds: float = Field(default=90, gt=0, le=180, allow_inf_nan=False)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("La zona horaria debe ser un identificador IANA válido.") from exc
        return value
