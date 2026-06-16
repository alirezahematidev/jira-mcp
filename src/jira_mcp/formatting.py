"""Shape raw Jira API payloads into compact dicts for tool responses.

The Jira API returns large, deeply nested objects. These helpers extract the
fields that matter to a human/LLM reader so tool output stays small and
readable.
"""

from __future__ import annotations

from typing import Any

from .adf import adf_to_text


def _user(field: Any) -> str | None:
    if not isinstance(field, dict):
        return None
    return field.get("displayName") or field.get("name") or field.get("emailAddress")


def format_issue(issue: dict[str, Any], *, base_url: str = "") -> dict[str, Any]:
    """Reduce a full issue payload to its salient fields."""
    fields = issue.get("fields", {}) or {}
    key = issue.get("key")
    out: dict[str, Any] = {
        "key": key,
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "assignee": _user(fields.get("assignee")),
        "reporter": _user(fields.get("reporter")),
        "labels": fields.get("labels") or [],
        "created": fields.get("created"),
        "updated": fields.get("updated"),
    }
    if "description" in fields:
        out["description"] = adf_to_text(fields.get("description"))
    parent = fields.get("parent")
    if parent:
        out["parent"] = parent.get("key")
    if base_url and key:
        out["url"] = f"{base_url}/browse/{key}"
    return {k: v for k, v in out.items() if v not in (None, [], "")}


def format_search_results(
    data: dict[str, Any], *, base_url: str = ""
) -> dict[str, Any]:
    issues = data.get("issues", []) or []
    return {
        "total": data.get("total", len(issues)),
        "start_at": data.get("startAt", 0),
        "max_results": data.get("maxResults"),
        "count": len(issues),
        "issues": [format_issue(i, base_url=base_url) for i in issues],
    }


def format_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "author": _user(comment.get("author")),
        "created": comment.get("created"),
        "updated": comment.get("updated"),
        "body": adf_to_text(comment.get("body")),
    }


def format_project(project: dict[str, Any]) -> dict[str, Any]:
    out = {
        "key": project.get("key"),
        "id": project.get("id"),
        "name": project.get("name"),
        "lead": _user(project.get("lead")),
        "project_type": project.get("projectTypeKey"),
    }
    return {k: v for k, v in out.items() if v is not None}


def format_transition(transition: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": transition.get("id"),
        "name": transition.get("name"),
        "to_status": (transition.get("to") or {}).get("name"),
    }


def format_user(user: dict[str, Any]) -> dict[str, Any]:
    out = {
        "account_id": user.get("accountId"),
        "name": user.get("name"),
        "display_name": user.get("displayName"),
        "email": user.get("emailAddress"),
        "active": user.get("active"),
    }
    return {k: v for k, v in out.items() if v is not None}
