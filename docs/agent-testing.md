# Test with an agent

A real Codex CLI agent was tested against the locally synced full corpus on
2026-09-28. This is distinct from the built-in `demo`, which only extracts source
quotations and does not call a language model.

## Observed agent results

The agent completed all six requested tasks using seven successful MCP calls:

| Task | Observed result |
| --- | --- |
| Coverage | 17 form sources, no missing sources, 408 unparsed groups |
| भू / 01.0001, shuddha kartari laṭ parasmaipada | All nine forms, with correct person/number coordinates |
| राम / @rAma1, ablative singular | Both `रामाद्` and `रामात्` |
| Reverse lookup | `रामौ`: 3 occurrences; `भवति`: 5, preserving lexical and grammatical ambiguity |
| Missing surface | Zero matches; agent explicitly avoided claiming grammatical invalidity |
| Sūtra 6.1.77 | `इको यणचि`, with source citation and no requested commentaries |

The agent cited immutable upstream URLs, credited Ashtadhyayi.com, Neelesh Bodas
and contributors, and explained that sandhi validation and śloka anvaya are not
implemented. We checked the actual tool responses against the expected source
values; this was not based only on the agent saying that it passed.

The run also exposed an agent mistake: five initial requests used `limit: 100`,
above the advertised maximum of 50. The server rejected them with `INVALID_INPUT`;
the agent removed the invalid limit and recovered on all five calls. Thus the
outcomes passed, but first-attempt tool argument selection was imperfect.

Artifacts: [agent answer](test-results/agent-answer.md),
[actual MCP call arguments and responses](test-results/agent-tool-calls.json).
The trace excludes unrelated Codex session metadata. The agent performed no shell
commands or repository edits. One successful scenario run does not establish
reliability for arbitrary prompts or models.

## Prepare this checkout

```sh
cd /Users/ankith/github/AstadhyayiMCP
uv sync --locked
uv run ashtadhyayi-mcp --data-dir .data status
```

Status should show 17 form sources and 9,007 śabdas. If no full snapshot is loaded:

```sh
uv run ashtadhyayi-mcp --data-dir .data sync --profile full
```

The full snapshot is already downloaded in this checkout. No need to sync it again
for each test. The MCP itself runs offline; the Codex agent requires its normal
model connection and login, and receives the public data returned by the tools.
Normal account/model usage applies.

## Repeat the agent test without changing your configuration

With Codex CLI on PATH and logged in, run:

```sh
uv run python examples/test_agent.py
```

This starts a read-only, ephemeral Codex session with only this MCP configured
through command-line overrides. It does not register the server globally.
It uses [this prompt](../examples/agent-test-prompt.md) and writes:

- `/tmp/ashtadhyayi-agent-test/answer.md`: final agent answer.
- `/tmp/ashtadhyayi-agent-test/events.jsonl`: actual tool calls and responses.
- `/tmp/ashtadhyayi-agent-test/stderr.log`: startup or authentication diagnostics.

Read the answer and compare it with the observed-results table above. Exit code 0
means the agent session completed; it is not an automatic correctness grade.
Inspect `mcp_tool_call` events to verify retrieval actually happened and that any
failed calls were recovered. Each run overwrites files in the selected output
directory; use `--output-dir /tmp/my-second-agent-test` to retain separate runs.
The wrapper stops after 300 seconds if the model does not finish.

If Codex is not on PATH, pass its executable explicitly. In this IDE installation:

```sh
uv run python examples/test_agent.py \
  --codex /Users/ankith/.vscode/extensions/openai.chatgpt-26.917.62051-darwin-arm64/bin/macos-aarch64/codex
```

The IDE extension path changes when the extension updates. Prefer `codex` on PATH
for ongoing use. Run `codex login` if the logs report missing authentication.
The wrapper was written for the installed CLI, including its `--ignore-user-config`
and `--ephemeral` options; an older CLI may need updating.

## Use it interactively in Codex CLI or the Codex IDE extension

Register the local stdio server once:

```sh
codex mcp add ashtadhyayi -- \
  /Users/ankith/github/AstadhyayiMCP/.venv/bin/ashtadhyayi-mcp \
  --data-dir /Users/ankith/github/AstadhyayiMCP/.data serve

codex mcp list
```

This writes a persistent entry in your Codex configuration. Start a fresh Codex
session after adding it. In the CLI, `/mcp` lets you inspect available connections.
You do not start `serve` in a separate terminal: the MCP client launches it.
Codex CLI and the Codex IDE extension share MCP configuration, as described in the
[official OpenAI documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
Other editors' agents may use different configuration formats.

Try these prompts, one at a time:

> Use the ashtadhyayi MCP to retrieve all nine forms for dhātu baseindex 01.0001,
> shuddha, kartari, lat, pada P. Present person by number and cite the source.

> Use the ashtadhyayi MCP to retrieve राम masculine ablative singular. Preserve
> all alternatives and show the original stored slot.

> Use lookup_form for रामौ and भवति. Show every candidate, lexical ID, case or
> person, number and source. Explain vocative aliases. Do not choose a single
> analysis without sentence context. Follow next_offset until all pages are read.

> Look up __absent_test_form__. Does the result establish that it is invalid
> Sanskrit? Explain using the MCP coverage limitations.

> Use the MCP to explain what evidence it can provide for analysing a śloka.
> Separate stored-form evidence from sandhi or anvaya judgments it cannot establish.

A good answer must use tool calls, preserve ambiguity, provide citations and
avoid presenting unavailable grammar capabilities as implemented. Tool `limit`
must be 1–50; omitted defaults work for these small examples. For all stored forms
of a root, request `get_dhatu_forms` without morphology filters and traverse every
`next_offset`; one page is not necessarily complete.

To unregister later:

```sh
codex mcp remove ashtadhyayi
```

## Troubleshooting and model-free checks

- `SOURCE_NOT_LOADED`: sync the full profile into the same directory named in
  the MCP command, then restart the agent session.
- `DATA_UNAVAILABLE`: run `status` with that exact data directory and inspect its
  error. A mismatched default cache path is a common configuration mistake.
- Server absent from tools: check `codex mcp list`, absolute executable/data paths,
  and the client startup logs. `serve` waiting silently is normal for stdio.
- No tool calls: explicitly ask the agent to use `ashtadhyayi`; inspect the trace
  rather than accepting a plausible answer from memory.

For deterministic tests without model access:

```sh
ASHTADHYAYI_INTEGRATION_DATA_DIR=.data uv run pytest -q
uv run ashtadhyayi-mcp --data-dir .data demo '6.1.77'
```

The demo exercises MCP retrieval but is not an LLM-agent evaluation. See the
[201-test report](testing-results.md) for the automated suite's measured coverage.
