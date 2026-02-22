from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class PBSSettings(BaseModel):
    api_base_url: str = Field(default="https://data-api.health.gov.au/pbs/api/v3")
    subscription_key: str = Field(default="")


class SyncSettings(BaseModel):
    check_on_startup: bool = False
    force_refresh_on_startup: bool = False


class DatabaseSettings(BaseModel):
    type: str = Field(default="sqlite")
    path: str = Field(default="data/pbs_data.db")
    host: Optional[str] = None
    port: int = 5432
    database: str = Field(default="pbs_explorer")
    username: Optional[str] = None
    password: Optional[str] = None


class ServerSettings(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = False
    # NOTE: The default CORS allow_origins was changed from ["*"] to ["http://localhost:8000"]
    # for improved security. To configure CORS in production (for example, to restore a
    # permissive setting or to specify multiple allowed origins), set the
    # PBS_EXPLORER_SERVER_ALLOW_ORIGINS environment variable to a comma-separated list,
    # e.g. "https://example.com,https://admin.example.com" or "*".
    allow_origins: List[str] = Field(
        default_factory=lambda: os.getenv(
            "PBS_EXPLORER_SERVER_ALLOW_ORIGINS", "http://localhost:8000"
        ).split(",")
    )
    allow_credentials: bool = True
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "PUT"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    admin_api_key: str = Field(default="")


class LoggingSettings(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    json_output: bool = Field(default=False)


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
    settings.server.admin_api_key = _get_env("ADMIN_API_KEY", settings.server.admin_api_key) or ""

    settings.logging.level = _get_env("LOG_LEVEL", settings.logging.level) or settings.logging.level
    settings.logging.format = _get_env("LOG_FORMAT", settings.logging.format) or settings.logging.format
    settings.logging.json_output = _get_bool("LOG_JSON", settings.logging.json_output)

    return settings
