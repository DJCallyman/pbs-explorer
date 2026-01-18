from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseModel, Field


class PBSSettings(BaseModel):
    api_base_url: str = Field(default="https://data-api.health.gov.au/pbs/api/v3")
    subscription_key: str = Field(default="")


class SyncSettings(BaseModel):
    check_on_startup: bool = True
    force_refresh_on_startup: bool = False
    auto_sync_enabled: bool = True
    auto_sync_interval_hours: int = 24
    max_data_age_days: int = 30
    sync_latest_only: bool = False
    batch_size: int = 1000
    max_concurrent_requests: int = 5
    use_cache: bool = False
    cache_ttl_seconds: int = 3600


class DatabaseSettings(BaseModel):
    type: str = Field(default="sqlite")
    path: str = Field(default="pbs_data.db")
    host: Optional[str] = None
    port: int = 5432
    database: str = Field(default="pbs_explorer")
    username: Optional[str] = None
    password: Optional[str] = None


class ServerSettings(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = False
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])


class LoggingSettings(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


class Settings(BaseModel):
    pbs: PBSSettings = PBSSettings()
    sync: SyncSettings = SyncSettings()
    database: DatabaseSettings = DatabaseSettings()
    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(f"PBS_EXPLORER_{name}")
    if value is None or value == "":
        return default
    return value


def _get_int(name: str, default: int) -> int:
    value = _get_env(name)
    return int(value) if value is not None else default


def _get_bool(name: str, default: bool) -> bool:
    value = _get_env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_list(name: str, default: List[str]) -> List[str]:
    value = _get_env(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()

    settings.pbs.api_base_url = _get_env("PBS_API_BASE_URL", settings.pbs.api_base_url) or ""
    settings.pbs.subscription_key = _get_env("PBS_SUBSCRIPTION_KEY", settings.pbs.subscription_key) or ""

    settings.sync.check_on_startup = _get_bool("SYNC_CHECK_ON_STARTUP", settings.sync.check_on_startup)
    settings.sync.force_refresh_on_startup = _get_bool(
        "SYNC_FORCE_REFRESH_ON_STARTUP", settings.sync.force_refresh_on_startup
    )
    settings.sync.auto_sync_enabled = _get_bool("SYNC_AUTO_ENABLED", settings.sync.auto_sync_enabled)
    settings.sync.auto_sync_interval_hours = _get_int(
        "SYNC_AUTO_INTERVAL_HOURS", settings.sync.auto_sync_interval_hours
    )
    settings.sync.max_data_age_days = _get_int("SYNC_MAX_DATA_AGE_DAYS", settings.sync.max_data_age_days)
    settings.sync.sync_latest_only = _get_bool("SYNC_LATEST_ONLY", settings.sync.sync_latest_only)
    settings.sync.batch_size = _get_int("SYNC_BATCH_SIZE", settings.sync.batch_size)
    settings.sync.max_concurrent_requests = _get_int(
        "SYNC_MAX_CONCURRENT_REQUESTS", settings.sync.max_concurrent_requests
    )
    settings.sync.use_cache = _get_bool("SYNC_USE_CACHE", settings.sync.use_cache)
    settings.sync.cache_ttl_seconds = _get_int("SYNC_CACHE_TTL_SECONDS", settings.sync.cache_ttl_seconds)

    settings.database.type = _get_env("DB_TYPE", settings.database.type) or "sqlite"
    settings.database.path = _get_env("DB_PATH", settings.database.path) or "pbs_data.db"
    settings.database.host = _get_env("DB_HOST", settings.database.host or "") or None
    settings.database.port = _get_int("DB_PORT", settings.database.port)
    settings.database.database = _get_env("DB_NAME", settings.database.database) or "pbs_explorer"
    settings.database.username = _get_env("DB_USER", settings.database.username or "") or None
    settings.database.password = _get_env("DB_PASSWORD", settings.database.password or "") or None

    settings.server.host = _get_env("SERVER_HOST", settings.server.host) or "0.0.0.0"
    settings.server.port = _get_int("SERVER_PORT", settings.server.port)
    settings.server.debug = _get_bool("SERVER_DEBUG", settings.server.debug)
    settings.server.allow_origins = _get_list("SERVER_ALLOW_ORIGINS", settings.server.allow_origins)
    settings.server.allow_credentials = _get_bool(
        "SERVER_ALLOW_CREDENTIALS", settings.server.allow_credentials
    )
    settings.server.allow_methods = _get_list("SERVER_ALLOW_METHODS", settings.server.allow_methods)
    settings.server.allow_headers = _get_list("SERVER_ALLOW_HEADERS", settings.server.allow_headers)

    settings.logging.level = _get_env("LOG_LEVEL", settings.logging.level) or settings.logging.level
    settings.logging.format = _get_env("LOG_FORMAT", settings.logging.format) or settings.logging.format

    return settings
