import pytest

from jira_mcp.config import JiraSettings


def _base(**kw):
    args = dict(host="https://works.digikala.com", pat="token")
    args.update(kw)
    return JiraSettings(**args)


def test_host_trailing_slash_trimmed():
    s = _base(host="https://works.digikala.com/")
    assert s.host == "https://works.digikala.com"


def test_requires_host_and_pat():
    with pytest.raises(ValueError):
        JiraSettings(host=None, pat=None)
    with pytest.raises(ValueError):
        JiraSettings(host="https://works.digikala.com")  # missing pat
    with pytest.raises(ValueError):
        JiraSettings(pat="token")  # missing host


def test_invalid_host_scheme():
    with pytest.raises(ValueError):
        _base(host="ftp://example.com")
