"""Configuration loading for the Jira MCP server.

Settings are read from environment variables (and an optional ``.env`` file).
See ``.env.example`` for the full list of supported variables.
"""

from __future__ import annotations

from typing import Literal

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

    url: str = Field(..., description="Base URL of the Jira instance, no trailing slash.")
    auth_type: Literal["basic", "bearer"] = Field(
        default="basic",
        description="'basic' for Jira Cloud (email + API token), 'bearer' for Server/DC PAT.",
    )

    # basic auth (Jira Cloud)
    email: str | None = Field(default=None, description="Atlassian account email (basic auth).")
    api_token: str | None = Field(default=None, description="Jira API token (basic auth).")

    # bearer auth (Jira Server / Data Center)
    personal_token: str | None = Field(
        default=None, description="Personal Access Token (bearer auth)."
    )

    # behaviour
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds.")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates.")
    read_only: bool = Field(
        default=False,
        description="When true, tools that create/update/delete data are disabled.",
    )

    @model_validator(mode="after")
    def _validate_auth(self) -> JiraSettings:
        # Normalise the URL.
        self.url = self.url.rstrip("/")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("JIRA_URL must start with http:// or https://")

        if self.auth_type == "basic":
            if not self.email or not self.api_token:
                raise ValueError(
                    "basic auth requires JIRA_EMAIL and JIRA_API_TOKEN to be set."
                )
        elif self.auth_type == "bearer":
            if not self.personal_token:
                raise ValueError("bearer auth requires JIRA_PERSONAL_TOKEN to be set.")
        return self

    @property
    def is_cloud(self) -> bool:
        """Heuristic: Atlassian Cloud instances live on *.atlassian.net."""
        return "atlassian.net" in self.url


def load_settings() -> JiraSettings:
    """Load and validate settings from the environment.

    Raises a ``ValueError`` (via pydantic) with an actionable message when the
    configuration is incomplete.
    """
    return JiraSettings()  # type: ignore[call-arg]
