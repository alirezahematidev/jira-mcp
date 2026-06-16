from jira_mcp.formatting import (
    format_comment,
    format_issue,
    format_search_results,
    format_transition,
    format_user,
)

ISSUE = {
    "key": "PROJ-1",
    "fields": {
        "summary": "Fix the bug",
        "status": {"name": "In Progress"},
        "issuetype": {"name": "Bug"},
        "priority": {"name": "High"},
        "assignee": {"displayName": "Alice"},
        "reporter": {"displayName": "Bob"},
        "labels": ["backend"],
        "description": "the description",
        "created": "2024-01-01T00:00:00.000+0000",
        "updated": "2024-01-02T00:00:00.000+0000",
        "parent": {"key": "PROJ-0"},
    },
}


def test_format_issue_extracts_fields_and_url():
    out = format_issue(ISSUE, base_url="https://example.atlassian.net")
    assert out["key"] == "PROJ-1"
    assert out["status"] == "In Progress"
    assert out["assignee"] == "Alice"
    assert out["parent"] == "PROJ-0"
    assert out["url"] == "https://example.atlassian.net/browse/PROJ-1"


def test_format_issue_drops_empty_fields():
    out = format_issue({"key": "X-1", "fields": {"summary": "s"}})
    assert "assignee" not in out
    assert "labels" not in out


def test_format_search_results():
    out = format_search_results(
        {"issues": [ISSUE], "total": 1, "startAt": 0, "maxResults": 25}
    )
    assert out["total"] == 1
    assert out["count"] == 1
    assert out["issues"][0]["key"] == "PROJ-1"


def test_format_comment_plain_text_body():
    comment = {
        "id": "10",
        "author": {"displayName": "Alice"},
        "created": "2024-01-01",
        "body": "hello world",
    }
    out = format_comment(comment)
    assert out["author"] == "Alice"
    assert out["body"] == "hello world"


def test_format_transition():
    out = format_transition({"id": "31", "name": "Done", "to": {"name": "Done"}})
    assert out == {"id": "31", "name": "Done", "to_status": "Done"}


def test_format_user_drops_none():
    out = format_user({"name": "alice", "displayName": "Alice", "active": True})
    assert out["name"] == "alice"
    assert "email" not in out
