"""Tests for the MCP tool layer, exercising the lazy client + read-only guard."""

import httpx
import pytest
import respx

from jira_mcp import server
from jira_mcp.client import JiraClient
from jira_mcp.config import JiraSettings

JIRA = "https://works.digikala.com"


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module globals around each test."""
    server._settings = None
    server._client = None
    server._fields = None
    yield
    if server._client is not None:
        # Tests run in an event loop; close via the loop if still open.
        server._client = None
    server._settings = None
    server._fields = None


def _install(read_only=False):
    settings = JiraSettings(
        host=JIRA,
        pat="t",
        read_only=read_only,
    )
    server._settings = settings
    server._client = JiraClient(settings)


@respx.mock
async def test_get_current_user_tool():
    _install()
    respx.get(f"{JIRA}/rest/api/2/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "abc", "displayName": "Me"})
    )
    out = await server.get_current_user()
    assert out["display_name"] == "Me"
    await server._client.aclose()


@respx.mock
async def test_search_issues_clamps_max_results():
    _install()
    route = respx.post(f"{JIRA}/rest/api/2/search").mock(
        return_value=httpx.Response(200, json={"issues": [], "total": 0})
    )
    await server.search_issues("project = P", max_results=9999)
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["maxResults"] == 100
    await server._client.aclose()


@respx.mock
async def test_get_issue_with_comments():
    _install()
    respx.get(f"{JIRA}/rest/api/2/issue/P-1").mock(
        return_value=httpx.Response(200, json={"key": "P-1", "fields": {"summary": "s"}})
    )
    respx.get(f"{JIRA}/rest/api/2/issue/P-1/comment").mock(
        return_value=httpx.Response(
            200,
            json={"comments": [{"id": "1", "author": {"displayName": "A"}, "body": "hi"}]},
        )
    )
    out = await server.get_issue("P-1", include_comments=True)
    assert out["key"] == "P-1"
    assert out["comments"][0]["body"] == "hi"
    await server._client.aclose()


async def test_write_tool_blocked_in_read_only():
    _install(read_only=True)
    with pytest.raises(server.ToolError):
        await server.create_issue(project_key="P", summary="x")
    await server._client.aclose()


async def test_update_issue_requires_fields():
    _install()
    with pytest.raises(server.ToolError):
        await server.update_issue("P-1")
    await server._client.aclose()


FIELDS = [
    {"id": "summary", "name": "Summary", "custom": False, "schema": {"type": "string"}},
    {"id": "customfield_100", "name": "Tester", "custom": True, "schema": {"type": "user"}},
    {
        "id": "customfield_200",
        "name": "Testers",
        "custom": True,
        "schema": {"type": "array", "items": "user"},
    },
]


@respx.mock
async def test_update_issue_resolves_custom_fields_by_name():
    _install()
    respx.get(f"{JIRA}/rest/api/2/field").mock(return_value=httpx.Response(200, json=FIELDS))
    route = respx.put(f"{JIRA}/rest/api/2/issue/P-1").mock(return_value=httpx.Response(204))

    await server.update_issue("P-1", custom_fields={"tester": "jdoe", "Testers": ["a", "b"]})

    import json

    sent = json.loads(route.calls.last.request.content)["fields"]
    assert sent["customfield_100"] == {"name": "jdoe"}
    assert sent["customfield_200"] == [{"name": "a"}, {"name": "b"}]
    await server._client.aclose()


@respx.mock
async def test_update_issue_unknown_custom_field():
    _install()
    respx.get(f"{JIRA}/rest/api/2/field").mock(return_value=httpx.Response(200, json=FIELDS))
    with pytest.raises(server.ToolError, match="list_fields"):
        await server.update_issue("P-1", custom_fields={"Nope": "x"})
    await server._client.aclose()


@respx.mock
async def test_create_issue_returns_url():
    _install()
    respx.post(f"{JIRA}/rest/api/2/issue").mock(
        return_value=httpx.Response(201, json={"key": "P-7"})
    )
    out = await server.create_issue(project_key="P", summary="hi")
    assert out["key"] == "P-7"
    assert out["url"].endswith("/browse/P-7")
    await server._client.aclose()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-06-20", "2026-06-20T00:00:00.000+0000"),
        ("2026-06-20T14:30:00", "2026-06-20T14:30:00.000+0000"),
        ("2026-06-20T14:30:00Z", "2026-06-20T14:30:00.000+0000"),
        ("2026-06-20T14:30:00+03:30", "2026-06-20T14:30:00.000+0330"),
    ],
)
def test_to_jira_datetime(value, expected):
    assert server._to_jira_datetime(value) == expected


def test_to_jira_datetime_rejects_garbage():
    with pytest.raises(server.ToolError):
        server._to_jira_datetime("not-a-date")


@respx.mock
async def test_add_worklog_normalizes_started_and_sets_estimate():
    _install()
    route = respx.post(f"{JIRA}/rest/api/2/issue/P-1/worklog").mock(
        return_value=httpx.Response(201, json={"id": "9", "timeSpent": "2h", "started": "x"})
    )
    out = await server.add_worklog(
        "P-1",
        time_spent="2h",
        comment="done",
        started="2026-06-20",
        new_remaining_estimate="1h",
    )
    import json

    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["started"] == "2026-06-20T00:00:00.000+0000"
    assert request.url.params["newEstimate"] == "1h"
    assert out["remaining_estimate"] == "1h"
    await server._client.aclose()


@respx.mock
async def test_move_issue_to_sprint():
    _install()
    route = respx.post(f"{JIRA}/rest/agile/1.0/sprint/42/issue").mock(
        return_value=httpx.Response(204)
    )
    out = await server.move_issue_to_sprint("P-1", 42)
    import json

    body = json.loads(route.calls.last.request.content)
    assert body == {"issues": ["P-1"]}
    assert out == {"key": "P-1", "sprint_id": 42, "status": "ok"}
    await server._client.aclose()


async def test_move_issue_to_sprint_blocked_in_read_only():
    _install(read_only=True)
    with pytest.raises(server.ToolError):
        await server.move_issue_to_sprint("P-1", 42)
    await server._client.aclose()


@respx.mock
async def test_update_comment_returns_formatted_comment():
    _install()
    respx.put(f"{JIRA}/rest/api/2/issue/P-1/comment/5").mock(
        return_value=httpx.Response(
            200, json={"id": "5", "author": {"displayName": "A"}, "body": "edited"}
        )
    )
    out = await server.update_comment("P-1", "5", "edited")
    assert out["id"] == "5"
    assert out["body"] == "edited"
    await server._client.aclose()


@respx.mock
async def test_delete_comment():
    _install()
    route = respx.delete(f"{JIRA}/rest/api/2/issue/P-1/comment/5").mock(
        return_value=httpx.Response(204)
    )
    out = await server.delete_comment("P-1", "5")
    assert route.called
    assert out == {"issue": "P-1", "comment_id": "5", "deleted": True}
    await server._client.aclose()


async def test_comment_edits_blocked_in_read_only():
    _install(read_only=True)
    with pytest.raises(server.ToolError):
        await server.update_comment("P-1", "5", "edited")
    with pytest.raises(server.ToolError):
        await server.delete_comment("P-1", "5")
    await server._client.aclose()


@respx.mock
async def test_jira_error_becomes_tool_error():
    _install()
    respx.get(f"{JIRA}/rest/api/2/issue/BAD").mock(
        return_value=httpx.Response(404, json={"errorMessages": ["not found"]})
    )
    with pytest.raises(server.ToolError) as exc:
        await server.get_issue("BAD")
    assert "not found" in str(exc.value)
    await server._client.aclose()
