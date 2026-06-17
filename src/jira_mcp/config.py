"""Configuration loading for the Jira MCP server.

Targets the company's self-hosted Jira (Server / Data Center). Authentication
is a personal access token (PAT); users supply ``JIRA_HOST`` and ``JIRA_PAT``.
See ``.env.example``.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JiraSettings(BaseSettings):
    """Runtime configuration for connecting to Jira."""

    model_config = SettingsConfigDict(
        env_prefix="JIRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required — the values a user must provide.
    host: str | None = Field(
        default=None,
        description="Base URL of the self-hosted Jira instance.",
    )
    pat: str | None = Field(default=None, description="Jira personal access token.")

    # behaviour
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds.")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates.")
    read_only: bool = Field(
        default=False,
        description="When true, tools that create/update/delete data are disabled.",
    )

    @model_validator(mode="after")
    def _validate(self) -> JiraSettings:
        if not self.host or not self.pat:
            raise ValueError("Set JIRA_HOST and JIRA_PAT.")
        self.host = self.host.rstrip("/")
        if not self.host.startswith(("http://", "https://")):
            raise ValueError("JIRA_HOST must start with http:// or https://")
        return self


def load_settings() -> JiraSettings:
    """Load and validate settings from the environment."""
    return JiraSettings()  # type: ignore[call-arg]
