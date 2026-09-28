# Test results — 2026-09-28

**201 tests passed, 0 failed, 0 errors, 0 skipped in 30.70 seconds.**
The original 182-test suite also passed before adding 19 integration cases.
No application defect was found in these runs; changes were additional tests and this report.

## Environment and reproducibility

- Application: 0.2.0, local working tree (not a committed release).
- Python: 3.14.3; platform: macOS-27.0-arm64-arm-64bit-Mach-O.
- Corpus: 22 locally synced files, revision `5744762f010d677cfb43f347a42d02796cf615d6`.
- Original data credit: Ashtadhyayi.com — Neelesh Bodas and contributors;
  Vidyut/Ambuda contributors for the labelled collections. See [notices](../THIRD_PARTY_NOTICES.md).
- Tests used existing snapshots and attributed fixtures; they performed no upstream downloads.

```sh
ASHTADHYAYI_INTEGRATION_DATA_DIR=.data .venv/bin/pytest -q --durations=15 --junitxml=/tmp/ashtadhyayi-tests-final.xml
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
uv --cache-dir /tmp/ashtadhyayi-uv-cache pip check
uv --cache-dir /tmp/ashtadhyayi-uv-cache build --offline
```

Raw results: [JUnit XML](test-results/junit.xml), [corpus counts and timing measurements](test-results/metrics.json).

## Test breakdown

| Module | Passed cases | Result |
| --- | ---: | --- |
| `tests.test_demo` | 7 | PASS |
| `tests.test_forms` | 98 | PASS |
| `tests.test_forms_integration` | 38 | PASS |
| `tests.test_forms_mcp` | 9 | PASS |
| `tests.test_integration` | 1 | PASS |
| `tests.test_mcp` | 12 | PASS |
| `tests.test_retrieval` | 19 | PASS |
| `tests.test_snapshots` | 17 | PASS |

## What was verified

- Full corpus traversal: **507,628 stored paradigm fields**, representing
  **3,551,190 adapter cells**, across all 17 form sources. Cell counts include
  empty slots, stems and preserved unparsed groups; they are not unique word counts.
- All **9,007 śabda tables / 216,168 nominal slots**; all ten represented gaṇas;
  five derivation families, finite and kṛdanta collections, both prayogas and padas.
- Exact source-text reconstruction, original hashes and record linkage; all
  **408 malformed groups** accounted for without guessed gender labels.
- Golden cases for person/number, case/number, gender ambiguity, pronouns,
  alternatives, restricted-number tables, Unicode preservation and missing data.
- Added 17 parametrized reverse-lookup tests sampling beginning, middle and end
  records of every collection when their first field has a usable form. Queries
  come from raw source strings independently of the decoder; pagination must
  recover the original source identity. This samples reverse retrieval, while
  the separate parser audit traverses every field.
- Added two full-corpus stdio tests: **all 11 tools** in both `auto` and `legacy`
  modes, JSON output-schema validation, matching structured/text responses,
  pinned provenance, error handling and recovery on the same session.
- Existing regression tests cover interrupted sync, invalid input, malformed JSON,
  source corruption, path traversal, atomic activation, partial/core snapshots,
  pagination, source pointers and evidence-first demo behavior.

## Quality and package checks

| Check | Result |
| --- | --- |
| Ruff lint | PASS |
| Ruff formatting | PASS — 31 Python files |
| Strict mypy | PASS — 13 source files |
| Installed dependency compatibility | PASS — 40 packages checked |
| Source distribution and wheel build | PASS |
| Wheel installed in a fresh temporary virtual environment | PASS |
| Installed wheel tested outside repository directory | PASS |
| Installed wheel stdio discovery and full-corpus reverse lookup, both modes | PASS |
| Wheel includes third-party notices and excludes downloaded corpus/fixtures | PASS |

The fresh installation used the built wheel and cached dependency resolution;
its stdio tests exercised the installed console entry point, not the editable source tree.
No package was published.

## Local timing observations

Full-corpus Dispatcher initialization: **839.62 ms**.
The following are single first/repeated calls through the in-process Dispatcher
with `limit: 50`; they include result construction but exclude stdio transport.
Each repeated response was checked for exact equality with its first response.
These observations are not a load test, percentile benchmark or latency guarantee.

| Query | Stored occurrences | First call (ms) | Cached repeat (ms) |
| --- | ---: | ---: | ---: |
| `भवति` | 5 | 201.21 | 0.075 |
| `रामौ` | 3 | 227.33 | 0.052 |
| `कुर्वन्ति` | 1 | 192.01 | 0.042 |
| `भूत्वा` | 7 | 195.58 | 0.077 |
| `भावयति` | 6 | 197.45 | 0.063 |
| `बुभूषति` | 3 | 193.46 | 0.053 |
| `रामात्` | 1 | 198.98 | 0.049 |
| `हे रामौ` | 1 | 193.04 | 0.056 |
| `__absent_test_form__` | 0 | 187.11 | 0.037 |

Full-corpus stdio cases, including startup, discovery, all tool calls, error
recovery and shutdown: **2.18 s (`auto`)**, **2.09 s (`legacy`)**.

## Limits of these results

The tests establish faithful retrieval and protocol behavior. They do not prove
independent grammatical correctness of every upstream or generated form, and do
not test sandhi validation or śloka anvaya, which are not implemented. Reverse
lookup was sampled across every source, not invoked separately for millions of
surfaces. Python 3.12, Windows, Linux, external MCP host UIs and concurrent-client
load were not exercised locally; this run used Python 3.14.3 on macOS ARM64.
