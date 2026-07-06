"""Smoke tests - require internet, hit the live e-Gov API.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import pytest

from jp_eli_mcp.server import jp_get_article, jp_get_law, jp_search_by_keyword, jp_search_laws

# Minpou / the Civil Code - Meiji 29 Law No. 89.
CIVIL_CODE_ID = "129AC0000000089"


@pytest.mark.asyncio
async def test_smoke_search_laws() -> None:
    result = await jp_search_laws("民法", limit=5)
    assert result.total_count > 0, "expected at least one match for 民法"
    assert any(item.law_id == CIVIL_CODE_ID for item in result.items), (
        f"expected {CIVIL_CODE_ID} among matches: {[i.law_id for i in result.items]}"
    )
    for item in result.items:
        assert item.eli_uri is not None and "laws.e-gov.go.jp/law" in item.eli_uri
        assert item.source_url is not None and item.source_url.startswith("https://")


@pytest.mark.asyncio
async def test_smoke_search_by_keyword() -> None:
    result = await jp_search_by_keyword("個人情報", limit=3)
    assert result.total_count > 0, "expected matches for 個人情報"
    assert len(result.items) > 0
    for item in result.items:
        assert item.eli_uri is not None


@pytest.mark.asyncio
async def test_smoke_get_law() -> None:
    law = await jp_get_law(CIVIL_CODE_ID)
    assert law.eli_uri == f"https://laws.e-gov.go.jp/law/{CIVIL_CODE_ID}"
    assert law.human_readable_citation is not None and "民法" in law.human_readable_citation
    assert law.source_url is not None and CIVIL_CODE_ID in law.source_url


@pytest.mark.asyncio
async def test_smoke_get_article() -> None:
    article = await jp_get_article(CIVIL_CODE_ID, "1")
    assert article.text is not None and len(article.text) > 0
    assert article.eli_uri is not None
    assert article.human_readable_citation is not None
