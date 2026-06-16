import pytest

from jira_mcp.config import DEFAULT_JIRA_URL, JiraSettings


def _base(**kw):
    args = dict(email="me@digikala.com", api_token="token")
    args.update(kw)
    return JiraSettings(**args)


def test_url_defaults_to_company_host():
    s = _base()
    assert s.url == DEFAULT_JIRA_URL
    assert s.url == "https://works.digikala.com"


def test_url_trailing_slash_trimmed():
    s = _base(url="https://works.digikala.com/")
    assert s.url == "https://works.digikala.com"


def test_requires_email_and_token():
    with pytest.raises(ValueError):
        JiraSettings(email=None, api_token=None)
    with pytest.raises(ValueError):
        JiraSettings(email="me@digikala.com")  # missing token


def test_invalid_url_scheme():
    with pytest.raises(ValueError):
        _base(url="ftp://example.com")
