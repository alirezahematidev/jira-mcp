import pytest

from jira_mcp.config import JiraSettings


def _base(**kw):
    args = dict(
        url="https://example.atlassian.net",
        auth_type="basic",
        email="me@example.com",
        api_token="token",
    )
    args.update(kw)
    return JiraSettings(**args)


def test_basic_auth_valid():
    s = _base()
    assert s.is_cloud is True
    assert s.url == "https://example.atlassian.net"


def test_url_trailing_slash_trimmed():
    s = _base(url="https://example.atlassian.net/")
    assert s.url == "https://example.atlassian.net"


def test_basic_auth_requires_email_and_token():
    with pytest.raises(ValueError):
        JiraSettings(url="https://x.atlassian.net", auth_type="basic")


def test_bearer_auth_requires_token():
    with pytest.raises(ValueError):
        JiraSettings(url="https://jira.local", auth_type="bearer")


def test_bearer_auth_valid_and_not_cloud():
    s = JiraSettings(
        url="https://jira.local", auth_type="bearer", personal_token="pat"
    )
    assert s.is_cloud is False


def test_invalid_url_scheme():
    with pytest.raises(ValueError):
        _base(url="ftp://example.com")
