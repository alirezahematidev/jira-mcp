"""Configuration loading for the Jira MCP server.

Targets the company's self-hosted Jira (Server / Data Center). The host is
hardcoded and authentication is always HTTP basic; users only supply
``JIRA_EMAIL`` and ``JIRA_API_TOKEN``. See ``.env.example``.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Company self-hosted Jira instance. Override with JIRA_URL only if it moves.
DEFAULT_JIRA_URL = "https://works.digikala.com"


class JiraSettings(BaseSettings):
    """Runtime configuration for connecting to Jira."""

    model_config = SettingsConfigDict(
        env_prefix="JIRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = Field(
        default=DEFAULT_JIRA_URL,
        description="Base URL of the self-hosted Jira instance.",
    )

    # Credentials — the only values a user must provide.
    email: str | None = Field(default=None, description="Jira login (email or username).")
    api_token: str | None = Field(default=None, description="Jira API token / password.")

    # behaviour
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds.")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates.")
    read_only: bool = Field(
        default=False,
        description="When true, tools that create/update/delete data are disabled.",
    )

    @model_validator(mode="after")
    def _validate(self) -> JiraSettings:
        self.url = self.url.rstrip("/")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("JIRA_URL must start with http:// or https://")
        if not self.email or not self.api_token:
            raise ValueError("Set JIRA_EMAIL and JIRA_API_TOKEN.")
        return self


def load_settings() -> JiraSettings:
    """Load and validate settings from the environment."""
    return JiraSettings()  # type: ignore[call-arg]
