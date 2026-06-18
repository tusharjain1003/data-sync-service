from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str = "postgresql+asyncpg://localhost:5432/data_sync_dev"

    hubspot_access_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_id: str = ""
    stripe_secret_key: str = ""

    app_env: str = "development"
    use_mock_connectors: bool = True
    enable_demo_routes: bool = False
    log_level: str = "INFO"


settings = Settings()
