from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vergabe:vergabe@postgres:5432/vergabe"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "changeme"
    admin_password: str = "admin"
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    anthropic_api_key: str = ""
    summary_provider: str = "anthropic"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "vergabe@localhost"

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.secret_key in ("changeme", ""):
                raise ValueError("SECRET_KEY must be set in production")
            if self.admin_password in ("admin", ""):
                raise ValueError("ADMIN_PASSWORD must be set in production")
        return self

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
