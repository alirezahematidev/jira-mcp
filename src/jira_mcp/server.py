"""MCP server exposing Jira operations as tools.

Run with::

    jira-mcp            # console script (stdio transport)
    python -m jira_mcp  # equivalent

The server reads its configuration from the environment (see ``config.py`` and
``.env.example``).
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import JiraClient, JiraError
from .config import JiraSettings, load_settings
from .formatting import (
    format_comment,
    format_issue,
    format_project,
    format_search_results,
    format_transition,
    format_user,
)

mcp = FastMCP(
    "jira",
    instructions=(
        "Tools for reading and managing Atlassian Jira issues, projects, "
        "comments, workflow transitions, and agile boards. Issue keys look "
        "like 'PROJ-123'. Use search_issues with JQL for flexible queries."
    ),
)

class ToolError(RuntimeError):
    """A user-facing error message surfaced to the MCP client."""


# Lazily-initialised singletons. The settings are validated at startup (main);
# the client is created on first use, inside the server's event loop.
_settings: JiraSettings | None = None
_client: JiraClient | None = None


def _get_settings() -> JiraSettings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def _get_client() -> JiraClient:
    global _client
    if _client is None:
        _client = JiraClient(_get_settings())
    return _client


def _require_writable() -> None:
    if _get_settings().read_only:
        raise ToolError(
            "This server is running in read-only mode (JIRA_READ_ONLY=true); "
            "modifying operations are disabled."
        )


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_current_user() -> dict[str, Any]:
    """Return the account the server is authenticated as. Useful as a connectivity check."""
    try:
        return format_user(await _get_client().myself())
    except JiraError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def search_issues(
    jql: str,
    max_results: int = 25,
    start_at: int = 0,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Search issues using a JQL query.

    Args:
        jql: A Jira Query Language string, e.g.
            "project = PROJ AND status = 'In Progress' ORDER BY created DESC".
        max_results: Maximum issues to return (1-100).
        start_at: Zero-based index of the first result, for pagination.
        fields: Optional list of field names to fetch. Defaults to a useful summary set.
    """
    client = _get_client()
    max_results = max(1, min(max_results, 100))
    try:
        data = await client.search_issues(
            jql, max_results=max_results, start_at=start_at, fields=fields
        )
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return format_search_results(data, base_url=client.settings.url)


@mcp.tool()
async def get_issue(issue_key: str, include_comments: bool = False) -> dict[str, Any]:
    """Fetch a single issue by key (e.g. "PROJ-123").

    Args:
        issue_key: The issue key.
        include_comments: When true, also include the issue's comments.
    """
    client = _get_client()
    try:
        issue = await client.get_issue(issue_key)
        result = format_issue(issue, base_url=client.settings.url)
        if include_comments:
            comments = await client.get_comments(issue_key)
            result["comments"] = [
                format_comment(c) for c in comments.get("comments", [])
            ]
        return result
    except JiraError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def get_comments(issue_key: str, max_results: int = 50) -> dict[str, Any]:
    """List comments on an issue."""
    client = _get_client()
    try:
        data = await client.get_comments(issue_key, max_results=max_results)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {
        "issue": issue_key,
        "total": data.get("total", 0),
        "comments": [format_comment(c) for c in data.get("comments", [])],
    }


@mcp.tool()
async def list_transitions(issue_key: str) -> list[dict[str, Any]]:
    """List the workflow transitions currently available for an issue.

    Returns transition ids/names; pass an id to transition_issue.
    """
    client = _get_client()
    try:
        transitions = await client.get_transitions(issue_key)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return [format_transition(t) for t in transitions]


@mcp.tool()
async def list_projects(max_results: int = 50) -> list[dict[str, Any]]:
    """List accessible Jira projects."""
    client = _get_client()
    try:
        projects = await client.list_projects(max_results=max_results)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return [format_project(p) for p in projects]


@mcp.tool()
async def get_project(project_key: str) -> dict[str, Any]:
    """Fetch details for a single project by key (e.g. "PROJ")."""
    client = _get_client()
    try:
        return format_project(await client.get_project(project_key))
    except JiraError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def search_users(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Search for users by name or email. Returns usernames needed for assignment."""
    client = _get_client()
    try:
        users = await client.search_users(query, max_results=max_results)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return [format_user(u) for u in users]


@mcp.tool()
async def list_boards(
    project_key: str | None = None, max_results: int = 50
) -> dict[str, Any]:
    """List agile boards, optionally filtered to a project. (Jira Software only.)"""
    client = _get_client()
    try:
        data = await client.list_boards(project_key=project_key, max_results=max_results)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    boards = [
        {"id": b.get("id"), "name": b.get("name"), "type": b.get("type")}
        for b in data.get("values", [])
    ]
    return {"total": data.get("total", len(boards)), "boards": boards}


@mcp.tool()
async def list_sprints(
    board_id: int, state: str | None = None, max_results: int = 50
) -> dict[str, Any]:
    """List sprints on a board.

    Args:
        board_id: The agile board id (from list_boards).
        state: Optional filter: "active", "future", or "closed".
    """
    client = _get_client()
    try:
        data = await client.list_sprints(board_id, state=state, max_results=max_results)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    sprints = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "state": s.get("state"),
            "start": s.get("startDate"),
            "end": s.get("endDate"),
        }
        for s in data.get("values", [])
    ]
    return {"total": data.get("total", len(sprints)), "sprints": sprints}


# ---------------------------------------------------------------------------
# Write tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_issue(
    project_key: str,
    summary: str,
    issue_type: str = "Task",
    description: str | None = None,
    priority: str | None = None,
    assignee: str | None = None,
    labels: list[str] | None = None,
    parent_key: str | None = None,
) -> dict[str, Any]:
    """Create a new issue.

    Args:
        project_key: Target project key, e.g. "PROJ".
        summary: Issue title.
        issue_type: Issue type name, e.g. "Task", "Bug", "Story", "Sub-task".
        description: Optional plain-text description.
        priority: Optional priority name, e.g. "High".
        assignee: Optional assignee username (see search_users).
        labels: Optional list of labels.
        parent_key: Parent issue key, required when creating a Sub-task.
    """
    _require_writable()
    client = _get_client()
    try:
        created = await client.create_issue(
            project_key=project_key,
            summary=summary,
            issue_type=issue_type,
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
            parent_key=parent_key,
        )
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    key = created.get("key")
    return {"key": key, "url": f"{client.settings.url}/browse/{key}" if key else None}


@mcp.tool()
async def update_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    """Update fields on an existing issue. Only the provided fields are changed."""
    _require_writable()
    client = _get_client()
    fields: dict[str, Any] = {}
    if summary is not None:
        fields["summary"] = summary
    if description is not None:
        fields["description"] = description
    if priority is not None:
        fields["priority"] = {"name": priority}
    if labels is not None:
        fields["labels"] = labels
    if not fields:
        raise ToolError("No fields provided to update.")
    try:
        await client.update_issue(issue_key, fields)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"key": issue_key, "updated": list(fields.keys())}


@mcp.tool()
async def add_comment(issue_key: str, body: str) -> dict[str, Any]:
    """Add a comment to an issue."""
    _require_writable()
    client = _get_client()
    try:
        comment = await client.add_comment(issue_key, body)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return format_comment(comment)


@mcp.tool()
async def transition_issue(
    issue_key: str, transition_id: str, comment: str | None = None
) -> dict[str, Any]:
    """Move an issue through a workflow transition (e.g. to "Done").

    Call list_transitions first to get a valid transition_id for the issue.

    Args:
        issue_key: The issue to transition.
        transition_id: The transition id from list_transitions.
        comment: Optional comment to add as part of the transition.
    """
    _require_writable()
    client = _get_client()
    try:
        await client.transition_issue(issue_key, transition_id, comment=comment)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"key": issue_key, "transition_id": transition_id, "status": "ok"}


@mcp.tool()
async def assign_issue(issue_key: str, assignee: str | None) -> dict[str, Any]:
    """Assign an issue to a user (by username, see search_users), or pass null/empty to unassign."""
    _require_writable()
    client = _get_client()
    assignee = assignee or None
    try:
        await client.assign_issue(issue_key, assignee)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"key": issue_key, "assignee": assignee}


@mcp.tool()
async def add_worklog(
    issue_key: str, time_spent: str, comment: str | None = None
) -> dict[str, Any]:
    """Log work against an issue.

    Args:
        issue_key: The issue.
        time_spent: Jira duration string, e.g. "3h 30m", "1d", "45m".
        comment: Optional note about the work.
    """
    _require_writable()
    client = _get_client()
    try:
        log = await client.add_worklog(issue_key, time_spent=time_spent, comment=comment)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"id": log.get("id"), "issue": issue_key, "time_spent": log.get("timeSpent")}


@mcp.tool()
async def link_issues(
    inward_issue: str, outward_issue: str, link_type: str = "Relates"
) -> dict[str, Any]:
    """Create a link between two issues.

    Args:
        inward_issue: The "from" issue key.
        outward_issue: The "to" issue key.
        link_type: Link type name, e.g. "Relates", "Blocks", "Duplicate".
    """
    _require_writable()
    client = _get_client()
    try:
        await client.link_issues(inward_issue, outward_issue, link_type)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"inward": inward_issue, "outward": outward_issue, "type": link_type}


@mcp.tool()
async def delete_issue(issue_key: str, delete_subtasks: bool = False) -> dict[str, Any]:
    """Permanently delete an issue. This cannot be undone.

    Args:
        issue_key: The issue to delete.
        delete_subtasks: Required true if the issue has sub-tasks.
    """
    _require_writable()
    client = _get_client()
    try:
        await client.delete_issue(issue_key, delete_subtasks=delete_subtasks)
    except JiraError as exc:
        raise ToolError(str(exc)) from exc
    return {"key": issue_key, "deleted": True}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script entry point. Validates config, then serves over stdio."""
    try:
        _get_settings()
    except Exception as exc:  # pydantic ValidationError or ValueError
        print(f"jira-mcp: configuration error:\n{exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    mcp.run()


if __name__ == "__main__":
    main()
