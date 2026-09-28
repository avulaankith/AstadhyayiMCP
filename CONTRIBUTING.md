# Contributing

Install Python 3.12+ and uv, then run `uv sync --locked`. Before submitting changes:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

For adapter changes, sync the pinned data with `sync --profile full` and run the opt-in integration test
described in README. Tests must not fetch the network implicitly. Keep meaningful
regressions for provenance, Unicode, ambiguity, errors and transport behavior.
The full form audit must traverse every source field and slot, reconstruct its
original text, and account for malformed groups. Add attributed golden cases for
new encodings; do not equate round-trip fidelity with grammatical correctness.

Never hard-code a grammatical answer into implementation code. Expected answers
belong in attributed regression fixtures. Preserve original source strings,
unknown metadata fields, and per-source provenance. Keep normalization confined
to search copies. Report absence rather than inferring missing scholarship.

Do not commit downloaded corpora, local snapshots, credentials, or virtual
environments. Small fixture excerpts must include original file hashes, revision,
and JSON Pointers, and must remain excluded from our code license.

Correct scholarly text through the upstream workflow, not local replacement
rules. The [upstream README](https://github.com/ashtadhyayi-com/data) directs
commentary and form edits through the website's edit button where possible.
Software bugs belong in this project. Cite the exact revision and source path
when reporting an adapter issue.

Keep the server free of model calls, derivation engines, vector databases, and
transport-specific business logic. The demonstration client is replaceable and
must not become part of the authoritative retrieval layer.
