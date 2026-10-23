"""Application configuration.

Everything tunable lives here so the behaviour under test and the behaviour in
production are driven by the same knobs.
"""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Savannah Clinic Booking API"
    app_version: str = "1.0.0"
    environment: str = "development"
    sql_echo: bool = False

    database_url: str = "postgresql+asyncpg://clinic:clinic@localhost:55432/clinic"

    # The clinic operates in one timezone. Working hours are expressed in this
    # timezone; everything is stored in UTC.
    clinic_timezone: str = "Africa/Nairobi"
    slot_minutes: int = 30

    # Bonus rule: a slot is not bookable if it starts less than this many
    # minutes from now (default 1 hour).
    min_booking_lead_minutes: int = 60

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.clinic_timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
