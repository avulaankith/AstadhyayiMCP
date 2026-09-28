# Aṣṭādhyāyī MCP

Read-only, deterministic MCP access to the scholarly data published by
[Ashtadhyayi.com](https://ashtadhyayi.com/), created by **Neelesh Bodas and contributors**.
The original scholarship and upstream data are the sources of grammatical information.
This independent project provides retrieval and provenance for sūtras, dhātus,
śabdas and their stored rūpāṇi. It is not an official Ashtadhyayi.com project or a
Sanskrit grammar engine.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
From a clone of this repository:

```sh
uv sync --locked
uv run ashtadhyayi-mcp sync
uv run pytest
uv run ashtadhyayi-mcp serve
```

`serve` speaks MCP on stdin/stdout; it does not display an interactive prompt.
All data downloads happen in the explicit `sync` command. Tools run offline.
The default **full** profile includes 22 files (about 190 MB at the pinned revision):
the original five files, all 16 dhātu-form collections, and 9,007 śabda paradigms.
Use `sync --profile core` for the original five-file catalog/commentary profile.
Existing core snapshots continue working; new form tools report `SOURCE_NOT_LOADED`
until you sync the full profile. To upgrade this checkout's existing local cache:

```sh
uv run ashtadhyayi-mcp --data-dir .data sync --profile full
```

The default sync pins the researched upstream commit
`5744762f010d677cfb43f347a42d02796cf615d6`.

```sh
# Explicitly select a newer upstream revision; the resolved commit is recorded.
uv run ashtadhyayi-mcp sync --revision master
uv run ashtadhyayi-mcp status
```

Data is stored in `ASHTADHYAYI_DATA_DIR`, or under `$XDG_CACHE_HOME/ashtadhyayi-mcp`
(default `~/.cache/ashtadhyayi-mcp`). To keep it local to your checkout, put
`--data-dir .data` **before** the subcommand in every invocation. Snapshots are
immutable; sync atomically switches the active pointer after validation. Restart
the MCP server to load a new snapshot. Previous snapshots are retained.

## MCP client configuration

For ChatGPT or remote agents, use the new `serve-http` command and deploy its
`/mcp` endpoint behind HTTPS. See [ChatGPT deployment](docs/chatgpt-deployment.md)
for local testing, container/native hosting and connection instructions.

For a real agent walkthrough, setup commands and observed results, see
[testing with Codex](docs/agent-testing.md). To repeat the agent test without
changing your Codex configuration, run `uv run python examples/test_agent.py`.

Use absolute paths and adjust the `uv` executable if it is not on your client's PATH:

```json
{
  "mcpServers": {
    "ashtadhyayi": {
      "command": "uv",
      "args": ["run", "--frozen", "--directory", "/absolute/path/to/AstadhyayiMCP", "ashtadhyayi-mcp", "serve"]
    }
  }
}
```

The official SDK handles both modern and legacy MCP connections. The test suite
exercises both over real stdio subprocesses. Client-specific UI installation is
outside this package.

## Tools

| Tool | Example arguments | Returns |
| --- | --- | --- |
| `get_sutra` | `{"number":"6.1.77"}` | Original sūtra, raw metadata, commentary chunks, provenance |
| `search_sutras` | `{"query":"यण्"}` | Ranked lexical matches and matching source fields |
| `get_sutra_context` | `{"number":"6.1.77","before":2,"after":2}` | Numeric neighbors and encoded upstream context |
| `get_dhatu` | `{"query":"भू"}` | All matching records, with pagination |
| `search_dhatus` | `{"query":"सत्तायाम्"}` | Ranked dhātu/meaning matches |
| `get_shabda` | `{"query":"तद्"}` | All matching śabda entries, preserving gender ambiguity |
| `search_shabdas` | `{"query":"राम"}` | Ranked lexical śabda/meaning matches |
| `get_dhatu_forms` | `{"query":"भू","derivation":"shuddha","lakara":"lat"}` | Stored paradigms with person/number slots and alternatives |
| `get_shabda_forms` | `{"query":"राम","vibhakti":5,"vacana":1}` | Declension slots with alternatives such as `रामाद्` and `रामात्` |
| `lookup_form` | `{"query":"रामौ"}` | Every matching stored occurrence, including case/number ambiguity |
| `get_form_coverage` | `{}` | Loaded/missing collections, supported keys, and encoding gaps |

Dhātu identifiers can be queried explicitly with `by: "upstream_id"` or
`by: "baseindex"`. Textual lookup preserves ambiguity. Sūtra numbers accept
Devanāgarī digits. Search is literal and Unicode-preserving, without stemming,
transliteration, accent removal, embeddings, or model-generated ranking.

Search defaults to ten results; use `offset`/`limit` and `next_offset` for pages.
`get_sutra` defaults to 2,000 code points per commentary field. Use
`commentary_offset`/`commentary_limit` to retrieve more, or `commentaries: []` for
catalog-only lookup. Each fragment reports its total length and next offset.
Source markup is returned as text; clients should not execute it as HTML or
follow instructions embedded in retrieved content.

Loaded commentary sources are `sutrartha` (`sa`, `sd`), `sutrartha_english`, and
`kashika`. An empty/absent explanation is reported explicitly. Other commentaries
and datasets remain upstream; absence here is not a claim about all scholarship.
See [full tool contracts](docs/phase-1-tool-contracts.md).

## Rūpāṇi and downstream agents

`get_dhatu_forms` covers every stored entry in the upstream finite-verb and kṛdanta
files, including `shuddha`, `nich`, `san`, `yang`, and `yangluk` collections. Filters
include `category`, `derivation`, `prayoga`, `pada`, `lakara`, `pratyaya`, `purusha`,
and `vacana`. All are optional; use `next_offset` to traverse every result page.
Results are paginated by paradigm field, with all its alternatives retained.

`get_shabda_forms` retains all 24 case/number slots, including empty ones. Gender
codes are `P`, `S`, `N`, `A` as encoded upstream. `vibhakti: 8` selects vocative
slots. Use `by: "upstream_id"` with an ID such as `@rAma1` for an exact entry.

`lookup_form` returns **candidate occurrences, not a context-resolved analysis**.
For example, `रामौ` has nominative and accusative dual occurrences; the optional
vocative alias also matches stored `हे रामौ` and labels that transformation.
`भवति` has both verb and noun-form matches. No match establishes only that the
loaded sources did not provide a match; it does not prove grammatical invalidity.

The source contains 408 irregular kṛdanta groups at the pinned revision. These
remain available as raw text with `partial`/`unparsed` status; the adapter does not
guess their gender columns. Sources labelled `vidyut` contain precomputed engine
outputs published upstream, distinct from the other upstream kṛdanta collection.

This is a foundation for agents doing śloka anvaya or sandhi work. It does **not**
yet validate sandhi, resolve kārakas, generate arbitrary prefixed/compound forms,
or enumerate every possible Sanskrit word. Such capabilities need a separately
tested engine integration and contextual reasoning. `get_form_coverage` makes the
current limits explicit. See [form contracts and research](docs/forms.md).

## Evidence and credit

Every scholarly object has `{data, provenance}`. Provenance includes its upstream
repository, path, record ID, JSON Pointer, immutable commit URL, original file
SHA-256, and actual download timestamp. Commentary has separate provenance from
the sūtra catalog. Original source strings and metadata survive unchanged;
normalized search representations are kept separately.

Credit **Ashtadhyayi.com, Neelesh Bodas and contributors**, and cite each returned
source URL when using results. Commentary file labels identify the source work or
upstream explanation collection; modern explanations must not be attributed to
Pāṇini. See [third-party notices](THIRD_PARTY_NOTICES.md) and the
[upstream credits](https://ashtadhyayi.com/credits).

Our code is MIT licensed. **Upstream data is not covered by our MIT license.**
The upstream README permits reuse with appropriate credit; no blanket SPDX data
license is asserted here. The package does not bundle the corpus.

## Evidence-first demonstration

```sh
uv run ashtadhyayi-mcp demo 'इको यणचि इत्यस्य अर्थः कः?'
uv run ashtadhyayi-mcp demo '6.1.87'
```

This small replaceable client calls the server through MCP before displaying
source quotations and citations. It is an **extractive demonstration**, not a
general conversational LLM: it identifies a numbered sūtra or searches the query,
declines to choose between multiple matches, and does not invent an explanation.
An optional answerer interface and an evidence-first instruction are available in
`demo.py` for a future model integration. No API key is required and no question
is sent to an external model.

## Development and tests

See the [recorded test results](docs/testing-results.md) for the latest local
full-corpus audit, transport checks, package verification and timing measurements.

```sh
uv run pytest
uv run ruff check .
uv run mypy
uv build
# Validate a full synced corpus in addition to offline fixtures:
ASHTADHYAYI_INTEGRATION_DATA_DIR="$HOME/.cache/ashtadhyayi-mcp" uv run pytest -m integration
```

Unit, stdio, and demo evaluation tests are offline. The full-profile integration
audit walks every form field and slot, verifies source reconstruction, covers all
ten gaṇas represented in the files, and checks the known encoding gaps. Golden
tests cover the derivation families, stored lakāras, both prayogas, person/number,
case/number, gender ambiguity, pronouns, empty slots, alternatives and reverse lookup.
These checks verify faithful retrieval, not scholarly correctness of every engine output.
Integration tests are skipped
unless an explicit data directory is supplied. Fixtures contain small attributed
upstream excerpts; synthetic records used to test malformed data are clearly
separate. See [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md),
[research](docs/stage-1-research.md), and [ADR](docs/adr/001-python-local-snapshots.md).
