# Constitution of jp-eli-mcp

Version: 0.1.0
Date: 2026-07-06
Licence: Apache-2.0

`jp-eli-mcp` is an MCP server for Japan's official e-Gov law search API
(`laws.e-gov.go.jp`). It searches, fetches, and cites national legislation as structured JSON.
Case law is out of scope for this MVP.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV),
adapted for a jurisdiction without ELI.

---

## Art. 1. Public data only

The e-Gov law search API is the official, public source of Japanese national legislation,
published by the Digital Agency as open data (keyless REST/JSON). The server is read-only
against e-Gov and sends nothing beyond the requested title, keyword, `law_id`, or article number.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/jp-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to write
= the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server talks
only to `laws.e-gov.go.jp` and the local filesystem. Authentication: none; own backoff + cache.

## Art. 4. A durable identifier and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: Japan has no ELI. This is the durable e-Gov viewer URL
  (`https://laws.e-gov.go.jp/law/{law_id}`), keyed on the stable `law_id` e-Gov itself assigns -
  never invented. `eli_note` on every response says so explicitly.
- `human_readable_citation`: law title + law number, the Japanese convention (e.g.
  "民法（明治二十九年法律第八十九号）").
- `source_url`: the machine-readable API URL used to fetch the law (`/api/2/law_data/{law_id}`).

---

## Open points

1. **Case law** - the Courts in Japan (裁判所) publish judgments separately; not covered by this
   connector. A future `jp-case-law-mcp` would be a distinct source.
2. **Article numbering edge cases** - branch articles (枝番号, e.g. 第三条の二) are addressed via
   e-Gov's own `Num` attribute (e.g. `"3_2"`); Suppl. Provisions articles are a separate tree and
   not yet distinguished from main-body articles in `jp_get_article`.

## Ewolucja konstytucji

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-07-06. Author: Wieslaw Mazur / MateMatic.
