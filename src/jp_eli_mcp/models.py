"""Pydantic v2 models for the e-Gov law search API + jp-eli-mcp."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DATASET_NOTE = (
    "e-Gov (laws.e-gov.go.jp) is Japan's official portal for national legislation, run by "
    "the Digital Agency. Japan has no ELI scheme; eli_uri carries the durable e-Gov viewer "
    "URL keyed on law_id (see eli_note). Discover by law_title (jp_search_laws) or full-text "
    "keyword (jp_search_by_keyword), then fetch metadata or a specific article by law_id."
)

ELI_NOTE = (
    "Japan has not deployed ELI. eli_uri is the durable e-Gov viewer URL "
    "(https://laws.e-gov.go.jp/law/{law_id}), keyed on the stable law_id e-Gov assigns to "
    "every law - never invented."
)


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class LawSummary(_Tolerant):
    """One law as returned by search (title or keyword)."""

    law_id: str | None = None
    law_title: str | None = None
    law_num: str | None = None
    law_type: str | None = None
    promulgation_date: str | None = None

    # Citation contract (Art. IV CONSTITUTION).
    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None


class LawSearchResult(_Tolerant):
    """Result of ``jp_search_laws``."""

    query: str
    total_count: int
    items: list[LawSummary] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class KeywordHit(_Tolerant):
    """One hit of ``jp_search_by_keyword`` - a law with matching text snippets."""

    law_id: str | None = None
    law_title: str | None = None
    law_num: str | None = None
    snippets: list[str] = Field(default_factory=list)

    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None


class KeywordSearchResult(_Tolerant):
    """Result of ``jp_search_by_keyword``."""

    keyword: str
    total_count: int
    next_offset: int | None = None
    items: list[KeywordHit] = Field(default_factory=list)
    dataset_note: str = DATASET_NOTE


class LawMetadata(_Tolerant):
    """Result of ``jp_get_law`` - metadata only, no body text."""

    law_id: str
    law_title: str | None = None
    law_num: str | None = None
    law_type: str | None = None
    promulgation_date: str | None = None
    amendment_law_id: str | None = None
    amendment_enforcement_date: str | None = None

    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None
    dataset_note: str = DATASET_NOTE


class ArticleText(_Tolerant):
    """Result of ``jp_get_article`` - the text of one article of a law."""

    law_id: str
    article_num: str
    caption: str | None = None
    text: str | None = None

    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None
    dataset_note: str = DATASET_NOTE


class LawText(_Tolerant):
    """Result of ``jp_get_full_text`` - the full text of a law, possibly truncated."""

    law_id: str
    eli_uri: str | None = None
    eli_note: str = ELI_NOTE
    human_readable_citation: str | None = None
    source_url: str | None = None
    content: str | None = None
    byte_size: int | None = None
    truncated: bool = False
    dataset_note: str = DATASET_NOTE
