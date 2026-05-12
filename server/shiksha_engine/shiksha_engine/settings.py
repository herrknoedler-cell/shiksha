"""Settings — Pydantic-Settings, env-driven, validated."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_env: str = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    app_log_level: str = Field(default="info")

    # ---- Database ----
    database_url: str = Field(default="postgresql+psycopg2://shiksha:shiksha@localhost:5432/shiksha")
    db_schema: str = Field(default="shiksha_core")

    # ---- JWT ----
    jwt_secret: str = Field(default="dev-secret-replace-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_lifetime_days: int = Field(default=30)

    # ---- WebAuthn ----
    webauthn_rp_id: str = Field(default="localhost")
    webauthn_rp_name: str = Field(default="SHIKSHA")
    webauthn_origin: str = Field(default="http://localhost:8000")

    # ---- Anthropic ----
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-sonnet-4-5-20250929")
    anthropic_max_tokens: int = Field(default=300)

    # ---- CORS ----
    allowed_origins: str = Field(default="http://localhost:8000")

    # ---- Rate Limit ----
    rate_limit_per_operator_per_day: int = Field(default=200)

    # ---- Editions ----
    editions_dir: str = Field(default="editions")

    # ---- Email (Phase 2 — OTP-Notausgang) ----
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="shiksha@shiksha.world")

    # ---- Bridge zur alten Welt (Phase 1.5) ----
    # Interne URL des alten kita_compliance_routers, der via shiksha.tun.zone
    # erreichbar ist. Im Produktionsumfeld z.B. "http://127.0.0.1:8002".
    # Leer = Bridge ist deaktiviert (alle /api/v1/bridge/* Calls geben 503).
    bridge_old_base_url: str = Field(default="")
    bridge_timeout_seconds: float = Field(default=10.0)

    # ---- Computed ----
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def editions_path(self) -> Path:
        return Path(self.editions_dir)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Singleton-Pattern für Settings (cached)."""
    return Settings()
