from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List
import os


def _read_key(path: str, fallback: str) -> str:
    """Read a secret from file (written by setup) or return fallback."""
    try:
        with open(path) as f:
            val = f.read().strip()
            if val:
                return val
    except (FileNotFoundError, PermissionError):
        pass
    return fallback


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vergabe:vergabe@postgres:5432/vergabe"
    redis_url: str = "redis://redis:6379/0"
    # Read from /data volume (written by setup.py) or env var
    secret_key: str = _read_key("/data/secret.key", os.getenv("SECRET_KEY", "changeme"))
    admin_password: str = _read_key("/data/admin.key", os.getenv("ADMIN_PASSWORD", "admin"))
    anthropic_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "vergabe@localhost"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.secret_key in ("changeme", ""):
                raise ValueError("SECRET_KEY must be set to a strong value in production")
            if self.admin_password in ("admin", ""):
                raise ValueError("ADMIN_PASSWORD must be set to a strong value in production")
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
