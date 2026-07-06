"""e-Gov (Japan) citation helpers + JSON law-tree walker.

e-Gov's law_data endpoint returns the full text of a law as a JSON-serialized element tree
(``{"tag": ..., "attr": {...}, "children": [...]}``), the JSON equivalent of the XML the
older e-Gov v1 API used to serve. There is no AKN/ELI here, so we do not parse a namespace -
we walk the tag/attr/children tree directly.

Citation contract:
- ``eli_uri``: Japan has no ELI. We use the durable e-Gov viewer URL
  (``https://laws.e-gov.go.jp/law/{law_id}``), keyed on the stable ``law_id`` e-Gov assigns
  to every law - never invented. See ``models.ELI_NOTE``.
- ``human_readable_citation``: ``law_title（law_num）``, the standard Japanese convention
  (e.g. "民法（明治二十九年法律第八十九号）").
- ``source_url``: the machine-readable API URL used to fetch the law (``/api/2/law_data/{law_id}``).
"""

from __future__ import annotations

from typing import Any

VIEWER_BASE = "https://laws.e-gov.go.jp/law"
API_BASE = "https://laws.e-gov.go.jp/api/2"

_BLOCK_TAGS = frozenset(
    {
        "Paragraph",
        "Item",
        "Subitem1",
        "Subitem2",
        "Subitem3",
        "ArticleTitle",
        "ArticleCaption",
        "Sentence",
        "TableStructTitle",
    }
)


def viewer_url(law_id: str) -> str:
    return f"{VIEWER_BASE}/{law_id}"


def api_law_data_url(law_id: str) -> str:
    return f"{API_BASE}/law_data/{law_id}"


def human_citation(law_title: str | None, law_num: str | None) -> str | None:
    if law_title and law_num:
        return f"{law_title}（{law_num}）"
    return law_title or law_num


def build_summary(entry: dict[str, Any]) -> dict[str, Any]:
    """Build a citation-carrying summary from a ``/laws`` or ``/keyword`` list item.

    ``entry`` is one element of the ``laws``/``items`` array: a dict with ``law_info`` and
    ``revision_info`` (and for ``/keyword`` results, ``sentences``).
    """
    law_info = entry.get("law_info") or {}
    revision_info = entry.get("revision_info") or {}
    law_id = law_info.get("law_id")
    law_title = revision_info.get("law_title")
    law_num = law_info.get("law_num")
    out: dict[str, Any] = {
        "law_id": law_id,
        "law_title": law_title,
        "law_num": law_num,
        "law_type": law_info.get("law_type"),
        "promulgation_date": law_info.get("promulgation_date"),
        "human_readable_citation": human_citation(law_title, law_num),
    }
    if law_id:
        out["eli_uri"] = viewer_url(law_id)
        out["source_url"] = api_law_data_url(law_id)
    return out


def build_metadata(law_data: dict[str, Any]) -> dict[str, Any]:
    """Build metadata (no body text) from a ``/law_data/{law_id}`` response."""
    law_info = law_data.get("law_info") or {}
    revision_info = law_data.get("revision_info") or {}
    law_id = law_info.get("law_id")
    law_title = revision_info.get("law_title")
    law_num = law_info.get("law_num")
    out: dict[str, Any] = {
        "law_id": law_id,
        "law_title": law_title,
        "law_num": law_num,
        "law_type": law_info.get("law_type"),
        "promulgation_date": law_info.get("promulgation_date"),
        "amendment_law_id": revision_info.get("amendment_law_id"),
        "amendment_enforcement_date": revision_info.get("amendment_enforcement_date"),
        "human_readable_citation": human_citation(law_title, law_num),
    }
    if law_id:
        out["eli_uri"] = viewer_url(law_id)
        out["source_url"] = api_law_data_url(law_id)
    return out


def _flatten(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_flatten(c) for c in node)
    if isinstance(node, dict):
        children = node.get("children") or []
        inner = "".join(_flatten(c) for c in children)
        return inner + "\n" if node.get("tag") in _BLOCK_TAGS else inner
    return ""


def _find_node(node: Any, tag: str, num: str | None = None) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if node.get("tag") == tag and (num is None or (node.get("attr") or {}).get("Num") == num):
            return node
        for child in node.get("children") or []:
            found = _find_node(child, tag, num)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_node(child, tag, num)
            if found is not None:
                return found
    return None


def extract_article(law_full_text: dict[str, Any], article_num: str) -> dict[str, Any] | None:
    """Find one ``Article`` node by its e-Gov ``Num`` attribute (e.g. ``"1"``, ``"3_2"``).

    Returns ``{"caption": ..., "text": ...}`` or ``None`` if no article has that ``Num``.
    """
    node = _find_node(law_full_text, "Article", article_num)
    if node is None:
        return None
    caption_node = _find_node(node, "ArticleCaption")
    caption = _flatten(caption_node).strip() if caption_node else None
    text = _flatten(node).strip()
    return {"caption": caption or None, "text": text or None}
