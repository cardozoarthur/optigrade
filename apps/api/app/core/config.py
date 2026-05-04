from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://optigrade:optigrade@localhost:55432/optigrade"
    api_cors_origins: str = "http://localhost:3000"
    optigrade_require_internal_secret: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4"
    optigrade_max_threads: int = 24
    optigrade_optimizer_profile: str = "balanced"
    optigrade_optimizer_bin: str | None = None
    optigrade_internal_api_secret: str | None = None
    next_public_app_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
