"""FastMCP entry point - Japan e-Gov law search API tools.

Run:

    python -m jp_eli_mcp.server

Configuration via env:

- ``JP_ELI_CACHE_DIR`` (default ``~/.matematic/cache/jp-eli``)
- ``JP_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``JP_ELI_BASE_URL`` (default ``https://laws.e-gov.go.jp/api/2``)
"""

from __future__ import annotations

import os
import re

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import _flatten, build_metadata, build_summary, extract_article
from . import runtime
from .client import DEFAULT_BASE_URL, EGovClient
from .models import (
    ArticleText,
    KeywordHit,
    KeywordSearchResult,
    LawMetadata,
    LawSearchResult,
    LawSummary,
    LawText,
)

_MAX_FULL_TEXT_CHARS = 300_000
_TAG_RE = re.compile(r"</?span[^>]*>")

INSTRUCTIONS = """\
This MCP server exposes Japan's official e-Gov law search API (laws.e-gov.go.jp), run by the Digital Agency. It serves national legislation (laws, cabinet orders, ministerial ordinances) as structured data. Japan has no ELI scheme; every response carries a stable `eli_uri` (the durable e-Gov viewer URL, keyed on the law's own `law_id`), a `human_readable_citation` (law title + law number, the Japanese convention) and a `source_url` (the machine-readable API URL). See `eli_note` on every response for the honest explanation.

## Call order

1. `jp_search_laws` - find laws by title (`law_title`, e.g. "民法" for the Civil Code). Returns `law_id` for each match.
2. `jp_search_by_keyword` - full-text search across all laws (`keyword`). Returns matching laws with highlighted snippets.
3. `jp_get_law` - metadata for a law by `law_id`: title, law number, promulgation date, latest amendment. No body text.
4. `jp_get_article` - the text of one article of a law, by `law_id` and `article_num` (the e-Gov `Num` attribute, e.g. `"1"` for Article 1, `"3_2"` for a branch article like 第三条の二).
5. `jp_get_full_text` - the full text of a law by `law_id`. Large laws (e.g. the Civil Code) are truncated at roughly 300,000 characters; prefer `jp_get_article` for a specific provision.

## Hard constraints

- **No native ELI** - Japan has not deployed ELI. `eli_uri` is the e-Gov viewer URL (`https://laws.e-gov.go.jp/law/{law_id}`), never invented; see `eli_note`.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **No modification of official text** - returned verbatim from e-Gov.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/jp-eli-mcp.jsonl`.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing, empty, or out of range.
- `not_found` - no law matches that `law_id`, or no article matches that `article_num`.
- `upstream_error` - an e-Gov API error (HTTP, timeout, malformed JSON). Retry once before surfacing.

## Response style

- Cite laws as `human_readable_citation` with the viewer URL: "民法（明治二十九年法律第八十九号）, https://laws.e-gov.go.jp/law/129AC0000000089".
- NEVER invent a `law_id`, `eli_uri` or article number - take each from the tool output.
"""


class ToolError(Exception):
    """Structured error for jp-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({"invalid_arg", "not_found", "upstream_error"})

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

mcp: FastMCP = FastMCP(name="jp-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("JP_ELI_BASE_URL", runtime.base_url("eli", DEFAULT_BASE_URL)).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "No law found in e-Gov for that law_id.")
    if isinstance(exc, (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"e-Gov API error: {type(exc).__name__}: {exc}")
    return exc


def _clean_snippet(text: str | None) -> str:
    return _TAG_RE.sub("", text or "").strip()


# ---------------------------------------------------------------------------
# jp_search_laws
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def jp_search_laws(law_title: str, limit: int = 10) -> LawSearchResult:
    """Search Japanese laws by (partial) title.

    Args:
        law_title: e.g. ``"民法"`` (Civil Code) or ``"個人情報の保護に関する法律"``.
        limit: max results, 1-100 (default 10).

    Returns:
        ``LawSearchResult`` with ``items: list[LawSummary]``, each carrying the citation contract.
    """
    audit = _audit()
    if not law_title.strip():
        raise ToolError("invalid_arg", "law_title must not be empty.")
    if not 1 <= limit <= 100:
        raise ToolError("invalid_arg", f"limit={limit} must be in 1..100.")
    input_hash = hash_input({"law_title": law_title, "limit": limit})

    with timer() as t:
        try:
            async with EGovClient(base_url=_base_url()) as client:
                data = await client.search_by_title(law_title, limit)
        except Exception as exc:
            audit.log(tool="jp_search_laws", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = [LawSummary.model_validate(build_summary(law)) for law in data.get("laws", [])]
    result = LawSearchResult(query=law_title, total_count=data.get("total_count", len(items)), items=items)
    audit.log(tool="jp_search_laws", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# jp_search_by_keyword
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def jp_search_by_keyword(keyword: str, limit: int = 10, offset: int = 0) -> KeywordSearchResult:
    """Full-text search across all Japanese laws for a keyword.

    Args:
        keyword: e.g. ``"個人情報"`` (personal information).
        limit: max results, 1-100 (default 10).
        offset: pagination offset (default 0).

    Returns:
        ``KeywordSearchResult`` with ``items: list[KeywordHit]``, each with highlighted snippets.
    """
    audit = _audit()
    if not keyword.strip():
        raise ToolError("invalid_arg", "keyword must not be empty.")
    if not 1 <= limit <= 100:
        raise ToolError("invalid_arg", f"limit={limit} must be in 1..100.")
    if offset < 0:
        raise ToolError("invalid_arg", f"offset={offset} must be >= 0.")
    input_hash = hash_input({"keyword": keyword, "limit": limit, "offset": offset})

    with timer() as t:
        try:
            async with EGovClient(base_url=_base_url()) as client:
                data = await client.search_by_keyword(keyword, limit, offset)
        except Exception as exc:
            audit.log(tool="jp_search_by_keyword", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    items = []
    for entry in data.get("items", []):
        summary = build_summary(entry)
        summary["snippets"] = [_clean_snippet(s.get("text")) for s in entry.get("sentences", [])]
        items.append(KeywordHit.model_validate(summary))
    result = KeywordSearchResult(
        keyword=keyword,
        total_count=data.get("total_count", len(items)),
        next_offset=data.get("next_offset"),
        items=items,
    )
    audit.log(tool="jp_search_by_keyword", input_hash=input_hash, output_count_or_size=len(items),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# jp_get_law
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def jp_get_law(law_id: str) -> LawMetadata:
    """Fetch metadata for a law by its e-Gov ``law_id`` (no body text).

    Args:
        law_id: e.g. ``"129AC0000000089"`` (the Civil Code).

    Returns:
        ``LawMetadata`` with ``eli_uri``, ``human_readable_citation``, ``source_url``.
    """
    audit = _audit()
    if not law_id.strip():
        raise ToolError("invalid_arg", "law_id must not be empty.")
    input_hash = hash_input({"law_id": law_id})

    with timer() as t:
        try:
            async with EGovClient(base_url=_base_url()) as client:
                data = await client.get_law_data(law_id)
        except Exception as exc:
            audit.log(tool="jp_get_law", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if not data.get("law_info"):
        raise ToolError("not_found", f"No law found for law_id={law_id!r}.")
    metadata = LawMetadata.model_validate(build_metadata(data))
    audit.log(tool="jp_get_law", input_hash=input_hash, output_count_or_size=1,
              duration_ms=t.duration_ms, status="ok")
    return metadata


# ---------------------------------------------------------------------------
# jp_get_article
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def jp_get_article(law_id: str, article_num: str) -> ArticleText:
    """Fetch the text of one article of a law.

    Args:
        law_id: e.g. ``"129AC0000000089"`` (the Civil Code).
        article_num: the e-Gov ``Num`` attribute, e.g. ``"1"`` for Article 1, ``"3_2"`` for
            a branch article (第三条の二).

    Returns:
        ``ArticleText`` with ``eli_uri``, ``human_readable_citation``, ``source_url`` and ``text``.
    """
    audit = _audit()
    if not law_id.strip():
        raise ToolError("invalid_arg", "law_id must not be empty.")
    if not article_num.strip():
        raise ToolError("invalid_arg", "article_num must not be empty.")
    input_hash = hash_input({"law_id": law_id, "article_num": article_num})

    with timer() as t:
        try:
            async with EGovClient(base_url=_base_url()) as client:
                data = await client.get_law_data(law_id)
        except Exception as exc:
            audit.log(tool="jp_get_article", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if not data.get("law_info"):
        raise ToolError("not_found", f"No law found for law_id={law_id!r}.")
    article = extract_article(data.get("law_full_text") or {}, article_num)
    if article is None:
        raise ToolError("not_found", f"No article Num={article_num!r} in law_id={law_id!r}.")

    meta = build_metadata(data)
    result = ArticleText(
        law_id=law_id,
        article_num=article_num,
        caption=article.get("caption"),
        text=article.get("text"),
        eli_uri=meta.get("eli_uri"),
        human_readable_citation=meta.get("human_readable_citation"),
        source_url=meta.get("source_url"),
    )
    audit.log(tool="jp_get_article", input_hash=input_hash,
              output_count_or_size=len(article.get("text") or ""),
              duration_ms=t.duration_ms, status="ok")
    return result


# ---------------------------------------------------------------------------
# jp_get_full_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def jp_get_full_text(law_id: str) -> LawText:
    """Fetch the full text of a law by ``law_id``. Large laws are truncated.

    Args:
        law_id: e.g. ``"129AC0000000089"`` (the Civil Code).

    Returns:
        ``LawText`` with ``eli_uri``, ``human_readable_citation``, ``source_url``, ``content``
        and ``truncated`` (True if the text was cut at ~300,000 characters - use
        ``jp_get_article`` for a specific provision instead).
    """
    audit = _audit()
    if not law_id.strip():
        raise ToolError("invalid_arg", "law_id must not be empty.")
    input_hash = hash_input({"law_id": law_id})

    with timer() as t:
        try:
            async with EGovClient(base_url=_base_url()) as client:
                data = await client.get_law_data(law_id)
        except Exception as exc:
            audit.log(tool="jp_get_full_text", input_hash=input_hash, output_count_or_size=0,
                      duration_ms=t.duration_ms if t.duration_ms else 0, status="error",
                      error=f"{type(exc).__name__}: {exc}")
            raise _map_upstream(exc) from exc

    if not data.get("law_info"):
        raise ToolError("not_found", f"No law found for law_id={law_id!r}.")

    full_text = _flatten(data.get("law_full_text") or {}).strip()
    truncated = len(full_text) > _MAX_FULL_TEXT_CHARS
    content = full_text[:_MAX_FULL_TEXT_CHARS] if truncated else full_text

    meta = build_metadata(data)
    result = LawText(
        law_id=law_id,
        eli_uri=meta.get("eli_uri"),
        human_readable_citation=meta.get("human_readable_citation"),
        source_url=meta.get("source_url"),
        content=content,
        byte_size=len(content.encode("utf-8")),
        truncated=truncated,
    )
    audit.log(tool="jp_get_full_text", input_hash=input_hash, output_count_or_size=result.byte_size or 0,
              duration_ms=t.duration_ms, status="ok")
    return result


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
