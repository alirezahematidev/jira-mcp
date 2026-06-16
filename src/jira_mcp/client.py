"""Async HTTP client wrapping the Jira REST API.

Supports both Jira Cloud (REST API v3, rich text as ADF) and Jira Server / Data
Center (REST API v2, plain-text rich fields). The version and text encoding are
selected automatically from the configured authentication mode / URL.
"""

from __future__ import annotations

from typing import Any

import httpx

from .adf import adf_to_text, text_to_adf
from .config import JiraSettings


class JiraError(RuntimeError):
    """Raised when the Jira API returns an error response."""

    def __init__(self, status_code: int, message: str, *, url: str | None = None):
        self.status_code = status_code
        self.url = url
        super().__init__(message)


class JiraClient:
    """A thin async wrapper around the Jira REST API.

    Use as an async context manager so the underlying connection pool is
    cleaned up::

        async with JiraClient(settings) as jira:
            issue = await jira.get_issue("PROJ-1")
    """

    def __init__(self, settings: JiraSettings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        # Cloud uses API v3 (ADF); Server/DC uses v2 (wiki/plain text).
        self.api_version = "3" if settings.is_cloud else "2"
        self._owns_client = client is None
        self._client = client or self._build_client(settings)

    @staticmethod
    def _build_client(settings: JiraSettings) -> httpx.AsyncClient:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        return httpx.AsyncClient(
            base_url=settings.url,
            headers=headers,
            auth=httpx.BasicAuth(settings.email or "", settings.api_token or ""),
            timeout=settings.timeout,
            verify=settings.verify_ssl,
        )

    async def __aenter__(self) -> JiraClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # --- low level ----------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        try:
            resp = await self._client.request(method, path, params=params, json=json)
        except httpx.HTTPError as exc:  # network / timeout errors
            raise JiraError(0, f"Request to Jira failed: {exc}", url=path) from exc

        if resp.is_success:
            if resp.status_code == 204 or not resp.content:
                return None
            ctype = resp.headers.get("content-type", "")
            return resp.json() if "application/json" in ctype else resp.text

        raise JiraError(resp.status_code, self._error_message(resp), url=str(resp.url))

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            return f"HTTP {resp.status_code}: {resp.text[:500] or resp.reason_phrase}"
        messages: list[str] = []
        if isinstance(data, dict):
            messages.extend(data.get("errorMessages") or [])
            errors = data.get("errors")
            if isinstance(errors, dict):
                messages.extend(f"{k}: {v}" for k, v in errors.items())
            if not messages and data.get("message"):
                messages.append(str(data["message"]))
        return f"HTTP {resp.status_code}: " + ("; ".join(messages) or resp.reason_phrase)

    def _api(self, path: str) -> str:
        return f"/rest/api/{self.api_version}{path}"

    def _agile(self, path: str) -> str:
        return f"/rest/agile/1.0{path}"

    def _encode_text(self, text: str) -> Any:
        """Encode a rich-text field for the active API version."""
        return text_to_adf(text) if self.api_version == "3" else text

    # --- system / users -----------------------------------------------------

    async def myself(self) -> dict[str, Any]:
        return await self._request("GET", self._api("/myself"))

    async def search_users(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        # Cloud uses ?query=, Server/DC uses ?username=.
        param = "query" if self.settings.is_cloud else "username"
        return await self._request(
            "GET",
            self._api("/user/search"),
            params={param: query, "maxResults": max_results},
        )

    # --- projects -----------------------------------------------------------

    async def list_projects(self, max_results: int = 50) -> list[dict[str, Any]]:
        if self.api_version == "3":
            data = await self._request(
                "GET",
                self._api("/project/search"),
                params={"maxResults": max_results},
            )
            return data.get("values", [])
        return await self._request("GET", self._api("/project"))

    async def get_project(self, project_key: str) -> dict[str, Any]:
        return await self._request("GET", self._api(f"/project/{project_key}"))

    async def get_project_statuses(self, project_key: str) -> list[dict[str, Any]]:
        return await self._request("GET", self._api(f"/project/{project_key}/statuses"))

    # --- issues -------------------------------------------------------------

    async def search_issues(
        self,
        jql: str,
        *,
        max_results: int = 25,
        start_at: int = 0,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "startAt": start_at,
        }
        if fields:
            body["fields"] = fields
        return await self._request("POST", self._api("/search"), json=body)

    async def get_issue(
        self, issue_key: str, *, fields: list[str] | None = None, expand: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = expand
        return await self._request("GET", self._api(f"/issue/{issue_key}"), params=params)

    async def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str,
        description: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        parent_key: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description:
            fields["description"] = self._encode_text(description)
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = self._account_ref(assignee)
        if labels:
            fields["labels"] = labels
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if extra_fields:
            fields.update(extra_fields)
        return await self._request("POST", self._api("/issue"), json={"fields": fields})

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        await self._request("PUT", self._api(f"/issue/{issue_key}"), json={"fields": fields})

    async def delete_issue(self, issue_key: str, *, delete_subtasks: bool = False) -> None:
        await self._request(
            "DELETE",
            self._api(f"/issue/{issue_key}"),
            params={"deleteSubtasks": str(delete_subtasks).lower()},
        )

    def _account_ref(self, user: str) -> dict[str, Any]:
        """Build a user reference for the active API version.

        Cloud identifies users by accountId; Server/DC by username/name.
        """
        return {"accountId": user} if self.settings.is_cloud else {"name": user}

    async def assign_issue(self, issue_key: str, assignee: str | None) -> None:
        # ``assignee=None`` clears the assignee.
        if assignee is None:
            body = {"accountId": None} if self.settings.is_cloud else {"name": None}
        else:
            body = self._account_ref(assignee)
        await self._request("PUT", self._api(f"/issue/{issue_key}/assignee"), json=body)

    # --- comments -----------------------------------------------------------

    async def get_comments(self, issue_key: str, max_results: int = 50) -> dict[str, Any]:
        return await self._request(
            "GET",
            self._api(f"/issue/{issue_key}/comment"),
            params={"maxResults": max_results},
        )

    async def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._api(f"/issue/{issue_key}/comment"),
            json={"body": self._encode_text(body)},
        )

    # --- transitions / workflow --------------------------------------------

    async def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request("GET", self._api(f"/issue/{issue_key}/transitions"))
        return data.get("transitions", [])

    async def transition_issue(
        self, issue_key: str, transition_id: str, *, comment: str | None = None
    ) -> None:
        body: dict[str, Any] = {"transition": {"id": transition_id}}
        if comment:
            body["update"] = {"comment": [{"add": {"body": self._encode_text(comment)}}]}
        await self._request("POST", self._api(f"/issue/{issue_key}/transitions"), json=body)

    # --- worklog ------------------------------------------------------------

    async def add_worklog(
        self, issue_key: str, *, time_spent: str, comment: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"timeSpent": time_spent}
        if comment:
            body["comment"] = self._encode_text(comment)
        return await self._request(
            "POST", self._api(f"/issue/{issue_key}/worklog"), json=body
        )

    # --- links --------------------------------------------------------------

    async def link_issues(
        self, inward_key: str, outward_key: str, link_type: str
    ) -> None:
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        await self._request("POST", self._api("/issueLink"), json=body)

    # --- agile (boards / sprints) -------------------------------------------

    async def list_boards(
        self, *, project_key: str | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": max_results}
        if project_key:
            params["projectKeyOrId"] = project_key
        return await self._request("GET", self._agile("/board"), params=params)

    async def list_sprints(
        self, board_id: int, *, state: str | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": max_results}
        if state:
            params["state"] = state
        return await self._request(
            "GET", self._agile(f"/board/{board_id}/sprint"), params=params
        )

    # --- formatting helpers -------------------------------------------------

    def render_text(self, value: Any) -> str:
        """Render a rich-text field value to plain text regardless of version."""
        return adf_to_text(value)
