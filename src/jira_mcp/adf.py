"""Helpers for Atlassian Document Format (ADF).

Jira Cloud's REST API v3 represents rich-text fields (descriptions, comments,
etc.) as ADF documents rather than plain strings. These helpers convert between
plain text and a minimal ADF document so callers can keep working with strings.
"""

from __future__ import annotations

from typing import Any


def text_to_adf(text: str) -> dict[str, Any]:
    """Convert plain text into a minimal ADF document.

    Each line separated by a blank line becomes its own paragraph; single
    newlines within a block become hard breaks. Empty input yields an empty
    paragraph (Jira rejects a document with no content).
    """
    text = text or ""
    blocks = text.split("\n\n")
    content: list[dict[str, Any]] = []

    for block in blocks:
        lines = block.split("\n")
        nodes: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            if line:
                nodes.append({"type": "text", "text": line})
            if i < len(lines) - 1:
                nodes.append({"type": "hardBreak"})
        content.append({"type": "paragraph", "content": nodes})

    if not content:
        content = [{"type": "paragraph", "content": []}]

    return {"type": "doc", "version": 1, "content": content}


def adf_to_text(node: Any) -> str:
    """Extract plain text from an ADF document (or any ADF node).

    This is a best-effort flattening: paragraphs and list items become lines,
    hard breaks become newlines. Unknown node types are traversed for any
    nested text content. Non-ADF input (e.g. a plain string) is returned as-is.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node

    parts: list[str] = []
    _walk(node, parts)
    text = "".join(parts)
    # Collapse the excess blank lines produced by block separators.
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


# Block node types separated by a blank line when flattened (mirrors the "\n\n"
# paragraph separator used by ``text_to_adf``, so the conversion round-trips).
_PARAGRAPH_TYPES = {"paragraph", "heading", "blockquote", "codeBlock"}
# Block node types separated by a single newline (list items, rules).
_LINE_TYPES = {"listItem", "rule"}


def _walk(node: Any, parts: list[str]) -> None:
    if isinstance(node, list):
        for child in node:
            _walk(child, parts)
        return
    if not isinstance(node, dict):
        return

    node_type = node.get("type")
    if node_type == "text":
        parts.append(node.get("text", ""))
        return
    if node_type == "hardBreak":
        parts.append("\n")
        return
    if node_type == "mention":
        attrs = node.get("attrs", {})
        parts.append(attrs.get("text") or f"@{attrs.get('id', '')}")
        return

    _walk(node.get("content", []), parts)

    if node_type in _PARAGRAPH_TYPES:
        parts.append("\n\n")
    elif node_type in _LINE_TYPES:
        parts.append("\n")
