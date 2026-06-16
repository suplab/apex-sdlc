from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required
    DATABASE_URL: str = Field(..., description="Async PostgreSQL connection URL")
    REDIS_URL: str = Field(..., description="Redis connection URL")
    SECRET_KEY: str = Field(..., description="Secret key for signing tokens")

    # Application
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")

    # External integrations (optional)
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    GITHUB_TOKEN: str = Field(default="", description="GitHub personal access token")
    JIRA_BASE_URL: str = Field(default="", description="Jira instance base URL")
    JIRA_EMAIL: str = Field(default="", description="Jira service account email")
    JIRA_API_TOKEN: str = Field(default="", description="Jira API token")
    CONFLUENCE_BASE_URL: str = Field(default="", description="Confluence base URL")
    CONFLUENCE_TOKEN: str = Field(default="", description="Confluence API token")
    S3_ARTIFACT_BUCKET: str = Field(default="", description="S3 bucket for artifacts")
    AWS_REGION: str = Field(default="eu-west-1", description="AWS region")


def get_settings() -> Settings:
    """Return application settings singleton."""
    return Settings()  # type: ignore[call-arg]
