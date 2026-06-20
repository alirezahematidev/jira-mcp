import json

import httpx
import pytest
import respx

from jira_mcp.client import JiraClient, JiraError
from jira_mcp.config import JiraSettings

JIRA = "https://works.digikala.com"


def settings():
    return JiraSettings(host=JIRA, pat="t")


@pytest.fixture
async def jira():
    client = JiraClient(settings())
    yield client
    await client.aclose()


@respx.mock
async def test_get_issue(jira):
    route = respx.get(f"{JIRA}/rest/api/2/issue/PROJ-1").mock(
        return_value=httpx.Response(200, json={"key": "PROJ-1", "fields": {"summary": "s"}})
    )
    issue = await jira.get_issue("PROJ-1")
    assert route.called
    assert issue["key"] == "PROJ-1"


@respx.mock
async def test_search_issues_posts_jql(jira):
    route = respx.post(f"{JIRA}/rest/api/2/search").mock(
        return_value=httpx.Response(200, json={"issues": [], "total": 0})
    )
    await jira.search_issues("project = PROJ", max_results=10)
    assert route.called
    assert b"project = PROJ" in route.calls.last.request.content


@respx.mock
async def test_create_issue_uses_plain_text_description(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue").mock(
        return_value=httpx.Response(201, json={"key": "PROJ-9"})
    )
    await jira.create_issue(
        project_key="PROJ", summary="hi", issue_type="Task", description="body"
    )
    body = json.loads(route.calls.last.request.content)
    assert body["fields"]["description"] == "body"


@respx.mock
async def test_create_issue_assignee_by_name(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue").mock(
        return_value=httpx.Response(201, json={"key": "PROJ-9"})
    )
    await jira.create_issue(
        project_key="PROJ", summary="hi", issue_type="Task", assignee="bob"
    )
    body = json.loads(route.calls.last.request.content)
    assert body["fields"]["assignee"] == {"name": "bob"}


@respx.mock
async def test_assign_issue_uses_name(jira):
    route = respx.put(f"{JIRA}/rest/api/2/issue/PROJ-1/assignee").mock(
        return_value=httpx.Response(204)
    )
    await jira.assign_issue("PROJ-1", "bob")
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "bob"}


@respx.mock
async def test_unassign_sends_null_name(jira):
    route = respx.put(f"{JIRA}/rest/api/2/issue/PROJ-1/assignee").mock(
        return_value=httpx.Response(204)
    )
    await jira.assign_issue("PROJ-1", None)
    body = json.loads(route.calls.last.request.content)
    assert body == {"name": None}


@respx.mock
async def test_transition_with_comment(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue/PROJ-1/transitions").mock(
        return_value=httpx.Response(204)
    )
    await jira.transition_issue("PROJ-1", "31", comment="done")
    body = json.loads(route.calls.last.request.content)
    assert body["transition"]["id"] == "31"
    assert body["update"]["comment"][0]["add"]["body"] == "done"


@respx.mock
async def test_add_worklog_minimal(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue/PROJ-1/worklog").mock(
        return_value=httpx.Response(201, json={"id": "1", "timeSpent": "1h"})
    )
    await jira.add_worklog("PROJ-1", time_spent="1h")
    body = json.loads(route.calls.last.request.content)
    assert body == {"timeSpent": "1h"}
    assert "adjustEstimate" not in route.calls.last.request.url.params


@respx.mock
async def test_add_worklog_full_fields(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue/PROJ-1/worklog").mock(
        return_value=httpx.Response(201, json={"id": "2", "timeSpent": "3h 30m"})
    )
    await jira.add_worklog(
        "PROJ-1",
        time_spent="3h 30m",
        comment="fixed the bug",
        started="2026-06-20T00:00:00.000+0000",
        new_estimate="2h",
    )
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["timeSpent"] == "3h 30m"
    assert body["comment"] == "fixed the bug"
    assert body["started"] == "2026-06-20T00:00:00.000+0000"
    assert request.url.params["adjustEstimate"] == "new"
    assert request.url.params["newEstimate"] == "2h"


@respx.mock
async def test_add_worklog_zero_estimate_is_sent(jira):
    route = respx.post(f"{JIRA}/rest/api/2/issue/PROJ-1/worklog").mock(
        return_value=httpx.Response(201, json={"id": "3", "timeSpent": "1h"})
    )
    await jira.add_worklog("PROJ-1", time_spent="1h", new_estimate="0")
    params = route.calls.last.request.url.params
    assert params["adjustEstimate"] == "new"
    assert params["newEstimate"] == "0"


@respx.mock
async def test_search_users_uses_username_param(jira):
    route = respx.get(f"{JIRA}/rest/api/2/user/search").mock(
        return_value=httpx.Response(200, json=[{"name": "bob"}])
    )
    await jira.search_users("bob")
    assert route.called
    assert route.calls.last.request.url.params["username"] == "bob"


@respx.mock
async def test_list_projects(jira):
    route = respx.get(f"{JIRA}/rest/api/2/project").mock(
        return_value=httpx.Response(200, json=[{"key": "PROJ"}, {"key": "OTHER"}])
    )
    projects = await jira.list_projects(max_results=1)
    assert route.called
    assert projects == [{"key": "PROJ"}]  # max_results applied client-side


@respx.mock
async def test_error_message_extraction(jira):
    respx.get(f"{JIRA}/rest/api/2/issue/BAD-1").mock(
        return_value=httpx.Response(
            400, json={"errorMessages": ["Issue does not exist"], "errors": {}}
        )
    )
    with pytest.raises(JiraError) as exc:
        await jira.get_issue("BAD-1")
    assert exc.value.status_code == 400
    assert "Issue does not exist" in str(exc.value)


@respx.mock
async def test_field_errors_extraction(jira):
    respx.post(f"{JIRA}/rest/api/2/issue").mock(
        return_value=httpx.Response(
            400, json={"errorMessages": [], "errors": {"summary": "is required"}}
        )
    )
    with pytest.raises(JiraError) as exc:
        await jira.create_issue(project_key="P", summary="", issue_type="Task")
    assert "summary: is required" in str(exc.value)


@respx.mock
async def test_network_error_becomes_jira_error(jira):
    respx.get(f"{JIRA}/rest/api/2/myself").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(JiraError) as exc:
        await jira.myself()
    assert exc.value.status_code == 0
