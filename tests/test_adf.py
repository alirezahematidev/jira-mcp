from jira_mcp.adf import adf_to_text, text_to_adf


def test_text_to_adf_single_paragraph():
    doc = text_to_adf("hello world")
    assert doc["type"] == "doc"
    assert doc["version"] == 1
    assert doc["content"][0]["content"][0] == {"type": "text", "text": "hello world"}


def test_text_to_adf_multiple_paragraphs_and_hardbreaks():
    doc = text_to_adf("line1\nline2\n\npara2")
    # two paragraphs
    assert len(doc["content"]) == 2
    first = doc["content"][0]["content"]
    assert {"type": "hardBreak"} in first


def test_text_to_adf_empty_is_valid():
    doc = text_to_adf("")
    assert doc["content"] == [{"type": "paragraph", "content": []}]


def test_adf_to_text_roundtrip():
    text = "first line\nsecond line\n\nsecond paragraph"
    assert adf_to_text(text_to_adf(text)) == text


def test_adf_to_text_handles_plain_string():
    assert adf_to_text("plain") == "plain"


def test_adf_to_text_extracts_mentions():
    doc = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "hi "},
                    {"type": "mention", "attrs": {"id": "123", "text": "@Bob"}},
                ],
            }
        ],
    }
    assert adf_to_text(doc) == "hi @Bob"


def test_adf_to_text_none():
    assert adf_to_text(None) == ""
