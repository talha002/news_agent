"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gmail_email: str
    gmail_app_password: str
    mcp_api_token: str

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    daily_dev_sender: str = "informer@daily.dev"
    daily_dev_subject_filter: str = "Daily Digest"
    default_email_limit: int = 10
    request_timeout: int = 30
    max_article_length: int = 20000
    imap_timeout: int = 30

    @property
    def gmail_imap_server(self) -> str:
        return "imap.gmail.com"


settings = Settings()
