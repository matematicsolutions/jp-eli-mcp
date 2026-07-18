# jp-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/jp-eli-mcp -->

An MCP server for Japan's official **e-Gov** law search API (`laws.e-gov.go.jp`), run by the
Digital Agency. It searches, fetches, and cites national legislation - acts, cabinet orders,
ministerial ordinances - with a verifiable citation on every response.

Part of the MateMatic `eu-legal-mcp` production line, extended into Asia. Same citation contract
(a stable identifier + a human-readable citation + a source URL) as the 18 EU/EEA connectors,
adapted for a jurisdiction with no ELI scheme.

> **Scope.** Discovery is by law title (`jp_search_laws`) or full-text keyword
> (`jp_search_by_keyword`); fetch a specific article (`jp_get_article`) or the full text
> (`jp_get_full_text`, truncated for very large laws such as the Civil Code). Every response
> carries a `dataset_note`.
>
> **Licence.** e-Gov law data is official public information published by the Japanese
> government as open data (keyless, REST/JSON). This connector relays it with attribution and a
> `source_url`.

## The tools

| Tool | What it does |
|---|---|
| `jp_search_laws` | Search laws by (partial) title. |
| `jp_search_by_keyword` | Full-text search across all laws, with highlighted snippets. |
| `jp_get_law` | Metadata for a law by `law_id`: title, law number, promulgation date. |
| `jp_get_article` | The text of one article of a law, by `law_id` and `article_num`. |
| `jp_get_full_text` | The full text of a law (truncated at ~300,000 characters). |

Every response carries the contract: `eli_uri` (Japan has no ELI - this is the durable e-Gov
viewer URL, e.g. `https://laws.e-gov.go.jp/law/129AC0000000089`, see `eli_note`),
`human_readable_citation` (e.g. `民法（明治二十九年法律第八十九号）`), and `source_url` (the
machine-readable API URL).

## Install

Not yet on PyPI - install from source until the first release ships:

```bash
git clone https://github.com/matematicsolutions/jp-eli-mcp
cd jp-eli-mcp
pip install -e .
```

Once released, this will be `uvx jp-eli-mcp`.

Configuration via env:

- `JP_ELI_BASE_URL` - default `https://laws.e-gov.go.jp/api/2`
- `JP_ELI_CACHE_DIR` - default `~/.matematic/cache/jp-eli`
- `JP_ELI_AUDIT_DIR` - default `~/.matematic/audit`

No API key. e-Gov's law search API is keyless.

### Configure (Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "jp-eli-mcp": { "command": "jp-eli-mcp" }
  }
}
```

### Windows 11 with Smart App Control

Smart App Control blocks unsigned executables, which covers `uvx.exe`, `pip.exe`
and the `jp-eli-mcp.exe` launcher that pip writes at install time. The `python.exe` and
`py.exe` from the python.org installer are signed by the Python Software
Foundation, so running the module through the interpreter works:

```bash
python -m pip install jp-eli-mcp
python -m jp_eli_mcp
```

`pip.exe` is blocked for the same reason, so install with `python -m pip`, not
`pip install`. If `python` is not on PATH, use the Windows launcher: `py -3 -m jp_eli_mcp`.

```json
{ "mcpServers": { "jp-eli-mcp": { "command": "python", "args": ["-m", "jp_eli_mcp"] } } }
```

Do not turn Smart App Control off to work around this - it cannot be re-enabled
without reinstalling Windows.

## Governance

- **Public data only** - read-only against e-Gov; no client data leaves the machine.
- **Audit log** - every tool call appends one JSON line to `~/.matematic/audit/jp-eli-mcp.jsonl`.
- **Vendor-neutral** - talks only to `laws.e-gov.go.jp`; no LLM provider, no telemetry.
- **Verifiable citations** - every response is independently checkable via `source_url`.

See `CONSTITUTION.md` and `DISCOVERY.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_instructions_drift.py -v   # offline
pytest tests/test_smoke.py -v                # hits live e-Gov
```

## Licence

Apache-2.0. © Matematic Solutions / Wieslaw Mazur.
