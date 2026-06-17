"""Async HTTP client wrapping the Jira REST API (Server / Data Center).

Targets self-hosted Jira: REST API v2, plain-text rich-text fields, and
username-based user references. Authentication is a bearer personal access
token (PAT).
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import JiraSettings

API = "/rest/api/2"
AGILE = "/rest/agile/1.0"


class JiraError(RuntimeError):
    """Raised when the Jira API returns an error response."""

    def __init__(self, status_code: int, message: str, *, url: str | None = None):
        self.status_code = status_code
        self.url = url
        super().__init__(message)


class JiraClient:
    """A thin async wrapper around the self-hosted Jira REST API.

    Use as an async context manager so the underlying connection pool is
    cleaned up::

        async with JiraClient(settings) as jira:
            issue = await jira.get_issue("PROJ-1")
    """

    def __init__(self, settings: JiraSettings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self._client = client or self._build_client(settings)

    @staticmethod
    def _build_client(settings: JiraSettings) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=settings.host,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.pat}",
            },
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

    # --- system / users -----------------------------------------------------

    async def myself(self) -> dict[str, Any]:
        return await self._request("GET", f"{API}/myself")

    async def search_users(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        return await self._request(
            "GET",
            f"{API}/user/search",
            params={"username": query, "maxResults": max_results},
        )

    # --- projects -----------------------------------------------------------

    async def list_projects(self, max_results: int = 50) -> list[dict[str, Any]]:
        # Server/DC returns the full list; max_results is applied client-side.
        projects = await self._request("GET", f"{API}/project")
        return projects[:max_results] if isinstance(projects, list) else projects

    async def get_project(self, project_key: str) -> dict[str, Any]:
        return await self._request("GET", f"{API}/project/{project_key}")

    # --- issues -------------------------------------------------------------

    async def search_issues(
        self,
        jql: str,
        *,
        max_results: int = 25,
        start_at: int = 0,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"jql": jql, "maxResults": max_results, "startAt": start_at}
        if fields:
            body["fields"] = fields
        return await self._request("POST", f"{API}/search", json=body)

    async def get_issue(
        self, issue_key: str, *, fields: list[str] | None = None, expand: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(fields)
        if expand:
            params["expand"] = expand
        return await self._request("GET", f"{API}/issue/{issue_key}", params=params)

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
            fields["description"] = description
        if priority:
            fields["priority"] = {"name": priority}
        if assignee:
            fields["assignee"] = {"name": assignee}
        if labels:
            fields["labels"] = labels
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if extra_fields:
            fields.update(extra_fields)
        return await self._request("POST", f"{API}/issue", json={"fields": fields})

    async def update_issue(self, issue_key: str, fields: dict[str, Any]) -> None:
        await self._request("PUT", f"{API}/issue/{issue_key}", json={"fields": fields})

    async def delete_issue(self, issue_key: str, *, delete_subtasks: bool = False) -> None:
        await self._request(
            "DELETE",
            f"{API}/issue/{issue_key}",
            params={"deleteSubtasks": str(delete_subtasks).lower()},
        )

    async def assign_issue(self, issue_key: str, assignee: str | None) -> None:
        # ``assignee=None`` clears the assignee.
        await self._request(
            "PUT", f"{API}/issue/{issue_key}/assignee", json={"name": assignee}
        )

    # --- comments -----------------------------------------------------------

    async def get_comments(self, issue_key: str, max_results: int = 50) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"{API}/issue/{issue_key}/comment",
            params={"maxResults": max_results},
        )

    async def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"{API}/issue/{issue_key}/comment", json={"body": body}
        )

    # --- transitions / workflow --------------------------------------------

    async def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"{API}/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    async def transition_issue(
        self, issue_key: str, transition_id: str, *, comment: str | None = None
    ) -> None:
        body: dict[str, Any] = {"transition": {"id": transition_id}}
        if comment:
            body["update"] = {"comment": [{"add": {"body": comment}}]}
        await self._request("POST", f"{API}/issue/{issue_key}/transitions", json=body)

    # --- worklog ------------------------------------------------------------

    async def add_worklog(
        self, issue_key: str, *, time_spent: str, comment: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"timeSpent": time_spent}
        if comment:
            body["comment"] = comment
        return await self._request("POST", f"{API}/issue/{issue_key}/worklog", json=body)

    # --- links --------------------------------------------------------------

    async def link_issues(self, inward_key: str, outward_key: str, link_type: str) -> None:
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        }
        await self._request("POST", f"{API}/issueLink", json=body)

    # --- agile (boards / sprints) -------------------------------------------

    async def list_boards(
        self, *, project_key: str | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": max_results}
        if project_key:
            params["projectKeyOrId"] = project_key
        return await self._request("GET", f"{AGILE}/board", params=params)

    async def list_sprints(
        self, board_id: int, *, state: str | None = None, max_results: int = 50
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"maxResults": max_results}
        if state:
            params["state"] = state
        return await self._request("GET", f"{AGILE}/board/{board_id}/sprint", params=params)
