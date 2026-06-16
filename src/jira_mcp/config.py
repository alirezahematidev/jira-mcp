"""Configuration loading for the Jira MCP server.

The Jira host is hardcoded to the company instance and authentication is always
HTTP basic (email + API token). Users only need to supply ``JIRA_EMAIL`` and
``JIRA_API_TOKEN``. See ``.env.example``.
"""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Company Jira instance. Override with JIRA_URL only if it ever moves.
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
        description="Base URL of the Jira instance (hardcoded to the company host).",
    )

    # Credentials — the only values a user must provide.
    email: str | None = Field(default=None, description="Atlassian account email.")
    api_token: str | None = Field(default=None, description="Jira API token.")

    # Deployment flavour. email + API token via basic auth is the Jira Cloud
    # model, so default to Cloud (REST v3 + ADF). Set JIRA_IS_CLOUD=false if the
    # host is actually Server / Data Center (REST v2 + plain text).
    is_cloud: bool = Field(default=True, description="Use the Jira Cloud REST API (v3 + ADF).")

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
            raise ValueError(
                "Set JIRA_EMAIL and JIRA_API_TOKEN. Create an API token at "
                "https://id.atlassian.com/manage-profile/security/api-tokens"
            )
        return self


def load_settings() -> JiraSettings:
    """Load and validate settings from the environment."""
    return JiraSettings()  # type: ignore[call-arg]
