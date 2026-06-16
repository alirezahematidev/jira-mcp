import httpx
import pytest
import respx

from jira_mcp.client import JiraClient, JiraError
from jira_mcp.config import JiraSettings

CLOUD = "https://example.atlassian.net"
SERVER = "https://jira.local"


def cloud_settings():
    return JiraSettings(
        url=CLOUD, auth_type="basic", email="me@example.com", api_token="t"
    )


def server_settings():
    return JiraSettings(url=SERVER, auth_type="bearer", personal_token="pat")


@pytest.fixture
async def cloud():
    client = JiraClient(cloud_settings())
    yield client
    await client.aclose()


@pytest.fixture
async def server():
    client = JiraClient(server_settings())
    yield client
    await client.aclose()


def test_api_version_selection():
    assert JiraClient(cloud_settings()).api_version == "3"
    assert JiraClient(server_settings()).api_version == "2"


@respx.mock
async def test_get_issue(cloud):
    route = respx.get(f"{CLOUD}/rest/api/3/issue/PROJ-1").mock(
        return_value=httpx.Response(200, json={"key": "PROJ-1", "fields": {"summary": "s"}})
    )
    issue = await cloud.get_issue("PROJ-1")
    assert route.called
    assert issue["key"] == "PROJ-1"


@respx.mock
async def test_search_issues_posts_jql(cloud):
    route = respx.post(f"{CLOUD}/rest/api/3/search").mock(
        return_value=httpx.Response(200, json={"issues": [], "total": 0})
    )
    await cloud.search_issues("project = PROJ", max_results=10)
    assert route.called
    sent = route.calls.last.request
    assert b"project = PROJ" in sent.content


@respx.mock
async def test_create_issue_encodes_adf_on_cloud(cloud):
    route = respx.post(f"{CLOUD}/rest/api/3/issue").mock(
        return_value=httpx.Response(201, json={"key": "PROJ-9"})
    )
    await cloud.create_issue(
        project_key="PROJ", summary="hi", issue_type="Task", description="body"
    )
    import json

    body = json.loads(route.calls.last.request.content)
    # On cloud, description should be an ADF document, not a plain string.
    assert body["fields"]["description"]["type"] == "doc"


@respx.mock
async def test_create_issue_plain_text_on_server(server):
    route = respx.post(f"{SERVER}/rest/api/2/issue").mock(
        return_value=httpx.Response(201, json={"key": "PROJ-9"})
    )
    await server.create_issue(
        project_key="PROJ", summary="hi", issue_type="Task", description="body"
    )
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["fields"]["description"] == "body"


@respx.mock
async def test_assign_issue_uses_account_id_on_cloud(cloud):
    route = respx.put(f"{CLOUD}/rest/api/3/issue/PROJ-1/assignee").mock(
        return_value=httpx.Response(204)
    )
    await cloud.assign_issue("PROJ-1", "5b10ac")
    import json

    body = json.loads(route.calls.last.request.content)
    assert body == {"accountId": "5b10ac"}


@respx.mock
async def test_assign_issue_uses_name_on_server(server):
    route = respx.put(f"{SERVER}/rest/api/2/issue/PROJ-1/assignee").mock(
        return_value=httpx.Response(204)
    )
    await server.assign_issue("PROJ-1", "bob")
    import json

    body = json.loads(route.calls.last.request.content)
    assert body == {"name": "bob"}


@respx.mock
async def test_transition_with_comment(cloud):
    route = respx.post(f"{CLOUD}/rest/api/3/issue/PROJ-1/transitions").mock(
        return_value=httpx.Response(204)
    )
    await cloud.transition_issue("PROJ-1", "31", comment="done")
    import json

    body = json.loads(route.calls.last.request.content)
    assert body["transition"]["id"] == "31"
    assert "update" in body


@respx.mock
async def test_error_message_extraction(cloud):
    respx.get(f"{CLOUD}/rest/api/3/issue/BAD-1").mock(
        return_value=httpx.Response(
            400, json={"errorMessages": ["Issue does not exist"], "errors": {}}
        )
    )
    with pytest.raises(JiraError) as exc:
        await cloud.get_issue("BAD-1")
    assert exc.value.status_code == 400
    assert "Issue does not exist" in str(exc.value)


@respx.mock
async def test_field_errors_extraction(cloud):
    respx.post(f"{CLOUD}/rest/api/3/issue").mock(
        return_value=httpx.Response(
            400, json={"errorMessages": [], "errors": {"summary": "is required"}}
        )
    )
    with pytest.raises(JiraError) as exc:
        await cloud.create_issue(project_key="P", summary="", issue_type="Task")
    assert "summary: is required" in str(exc.value)


@respx.mock
async def test_list_projects_cloud_uses_search(cloud):
    route = respx.get(f"{CLOUD}/rest/api/3/project/search").mock(
        return_value=httpx.Response(200, json={"values": [{"key": "PROJ"}]})
    )
    projects = await cloud.list_projects()
    assert route.called
    assert projects[0]["key"] == "PROJ"


@respx.mock
async def test_network_error_becomes_jira_error(cloud):
    respx.get(f"{CLOUD}/rest/api/3/myself").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(JiraError) as exc:
        await cloud.myself()
    assert exc.value.status_code == 0
