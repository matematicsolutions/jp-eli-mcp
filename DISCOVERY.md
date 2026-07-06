# Discovery: e-Gov law search API (laws.e-gov.go.jp) - Japan

Date: 2026-07-06. **Status: CLOSED** for a search+fetch+cite MVP (confirmed by live probing).

Japan's e-Gov (電子政府の総合窓口) is the Digital Agency's official portal for national law.
Its "Houki Kensaku" (law search) API v2 is keyless, modern REST/JSON, and returns the full text
of every law as a JSON-serialized element tree. An existing MIT-licensed reference wrapper
(`ryoooo/e-gov-law-mcp`) confirmed the wire format was worth cross-checking against; this
connector is a from-scratch implementation against the live API, not a fork.

## Base API properties (CONFIRMED live 2026-07-06)

- **Base URL:** `https://laws.e-gov.go.jp/api/2`
- **Authentication:** none (open data).
- **Format:** JSON. Full law text is a JSON-serialized tag/attr/children tree (the JSON
  equivalent of the XML the older e-Gov v1 API served) - no AKN, no XML namespace.
- **ELI:** NO - Japan has not deployed ELI. The stable identifier is e-Gov's own `law_id`
  (e.g. `129AC0000000089` for the Civil Code, Meiji 29 Law No. 89).

## Endpoints (CONFIRMED)

| Endpoint | Notes |
|---|---|
| `GET /laws?law_title={title}&limit={n}` | search by (partial) law title; returns `law_info` + `revision_info` per match |
| `GET /keyword?keyword={kw}&limit={n}&offset={n}` | full-text search; returns matching laws with highlighted `<span>` snippets |
| `GET /law_data/{law_id}` | full law: `law_info`, `revision_info`, `law_full_text` (the tree, tag `Law` > `LawBody` > `MainProvision`/`SupplProvision` > `Part`/`Chapter`/`Article`...) |

Verified live: `GET /laws?law_title=民法` returns the Civil Code (`law_id=129AC0000000089`,
`law_num` in kanji era notation "明治二十九年法律第八十九号"); `GET /law_data/129AC0000000089`
returns 1.6 MB of full text with a well-formed `Article`/`Paragraph`/`Sentence` tree, `Num`
attributes throughout (e.g. `Part Num="1"`).

## Fields used (for the citation contract)

- `law_info.law_id` -> the durable identifier -> `eli_uri = https://laws.e-gov.go.jp/law/{law_id}`.
- `revision_info.law_title` + `law_info.law_num` -> `human_readable_citation` (`"title（law_num）"`).
- `/api/2/law_data/{law_id}` -> `source_url` (machine-readable original).
- `law_full_text` tree, `Article[Num=...]` -> `jp_get_article` (recursive walk, no XML dep).

## Citation contract (Article IV) - CLOSED for JP

- `eli_uri` = e-Gov viewer URL keyed on `law_id` (no native ELI; documented via `eli_note`).
- `human_readable_citation` = `law_title（law_num）`, e.g. "民法（明治二十九年法律第八十九号）".
- `source_url` = the `/law_data/{law_id}` API URL (the fetchable original).

## Tool mapping - search+fetch+cite MVP

| Tool | Endpoint |
|---|---|
| `jp_search_laws` | `/laws?law_title=` |
| `jp_search_by_keyword` | `/keyword?keyword=` |
| `jp_get_law` | `/law_data/{law_id}` (metadata only) |
| `jp_get_article` | `/law_data/{law_id}` (walk tree for `Article[Num=...]`) |
| `jp_get_full_text` | `/law_data/{law_id}` (full tree flattened to text, truncated ~300k chars) |

**Deferred:** case law (Courts of Japan publish judgments on a separate portal, not e-Gov).

## Differences vs the EU/EEA line

- No ELI, no AKN/XML - the source is native JSON with its own tag/attr/children tree; parsed
  with a small recursive walker, no XML library dependency at all (a first for this fleet).
- Discovery has a real full-text keyword search (unlike FI/IE/LU, which are coordinate-only).
- Article-level fetch is a first-class tool (`jp_get_article`) because whole-law text can be very
  large (the Civil Code alone is ~1.6 MB) - `jp_get_full_text` truncates and points back to it.

## Decision: BUILD

Keyless, modern JSON REST, a genuine full-text search endpoint, and a large market (~44,000
bengoshi, third-largest economy) make this the highest-ROI non-EU connector evaluated so far.
