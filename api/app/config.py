from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_JWT_SECRET = "dev-only-change-me"  # noqa: S105 (placeholder, not a credential)
_LOCAL_ENVS = {"dev", "test", "local"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"

    database_url: str = "postgresql+psycopg://loanflow:loanflow@db:5432/loanflow"

    jwt_secret: str = _INSECURE_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 14

    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    upload_dir: str = "var/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_documents_per_file: int = 20
    allowed_upload_content_types: str = "application/pdf,image/png,image/jpeg"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_upload_content_type_set(self) -> set[str]:
        return {c.strip() for c in self.allowed_upload_content_types.split(",") if c.strip()}

    @model_validator(mode="after")
    def _reject_insecure_secret_outside_local(self) -> "Settings":
        if self.environment.lower() in _LOCAL_ENVS:
            return self
        if self.jwt_secret == _INSECURE_JWT_SECRET or len(self.jwt_secret) < 32:
            raise ValueError(
                "JWT_SECRET must be set to a strong value (>=32 chars) when "
                f"ENVIRONMENT is {self.environment!r}. Generate one with "
                '`python -c "import secrets; print(secrets.token_urlsafe(48))"`.'
            )
        return self


settings = Settings()
