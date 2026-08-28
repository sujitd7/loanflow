from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://loanflow:loanflow@db:5432/loanflow"
    purge_after_days: int = 30
    housekeeping_cron: str = "0 2 * * *"
    log_level: str = "INFO"


settings = Settings()
