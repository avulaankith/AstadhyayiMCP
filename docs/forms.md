# Stored rūpāṇi: contracts and coverage

Version 0.2.0 retrieves all entries in the selected upstream form collections.
It does not enumerate every possible Sanskrit form. All tools use the common
evidence, snapshot and error envelopes in [the original contracts](phase-1-tool-contracts.md).
Live `tools/list` schemas specify every field and reject unknown arguments.

## Sources and verified encodings

The full profile pins revision `5744762f010d677cfb43f347a42d02796cf615d6` of
[the official data repository](https://github.com/ashtadhyayi-com/data/tree/5744762f010d677cfb43f347a42d02796cf615d6).
It adds these seventeen files to the five core files:

| Paths relative to repository root | Encoding |
| --- | --- |
| `dhatu/dhatuforms_vidyut_{derivation}_{prayoga}.txt` (10 files) | Baseindex → pada/lakāra key → nine semicolon-separated slots |
| `dhatu/dhatuforms_vidyut_{derivation}_krut.txt` (5 files) | Baseindex → pratyaya → semicolon-separated groups, normally four comma-separated columns |
| `dhatu/dhatuforms_krut.txt` | Baseindex → pratyaya → comma-separated alternatives, without gender columns |
| `shabda/data2.txt` | Catalog records containing 24 semicolon-separated case/number slots |

Derivations are `shuddha`, `nich`, `san`, `yang`, `yangluk`; prayogas are
`kartari`, `karmani`. Source family `vidyut` identifies the precomputed files;
`upstream` identifies the separate kṛdanta collection. These are distinct sources,
and duplicate forms are not merged into an assertion of independent attestation.

The website's [JavaScript reader](https://ashtadhyayi.com/ashtadhyayi-1786933362.js),
particularly `DhatuConstants`, `Dhatu.getKritRowHtml`, `ShabdaConstants` and the
śabda table reader, was inspected alongside the raw data to verify these mappings:

- Finite keys begin with `p` or `a` (returned as pada `P` or `A`), followed by
  `lat`, `lit`, `lut`, `lrut`, `lot`, `lang`, `vidhiling`, `ashirling`, `lung`, or
  `lrung`. `let` is recognized by the adapter but has no stored fields at this revision.
- Finite slots run through `prathama`, `madhyama`, `uttama`, each with singular,
  dual, plural (`vacana` 1, 2, 3). Commas or slashes separate alternatives.
- Vidyut kṛdanta columns are stem/indeclinable, masculine, feminine, neuter;
  slashes separate alternatives within columns. The first column's role is
  `stem_or_indeclinable`; it is not asserted to be an inflected noun paradigm.
- Śabda rows are vibhaktis 1–7 followed by vocative (8), each with three numbers.
  Hyphens separate alternatives. Empty strings and lone hyphens yield empty
  variant lists while remaining intact in `raw_text`. Gender codes are `P`
  (masculine), `S` (feminine), `N` (neuter), `A` (upstream all-gender designation).

The catalog has 9,007 śabda entries. Each shuddha/nich/san Vidyut file has 2,229
root rows; each yang/yangluk file has 1,782. The separate kṛdanta file has 1,983
rows, including an empty row. All stored root identifiers link to the dhātu catalog
at this revision. Counts are observations of this snapshot, not grammatical limits.

The yangluk kṛdanta source has 408 irregular groups across 204 fields, with two
or six columns where four are expected. Such groups remain whole with role
`unparsed`, no inferred gender and a warning. Other groups in the same field can
still be decoded, yielding `parse_status: "partial"`. Schema drift in mandatory
catalog fields or finite/nominal slot counts prevents snapshot activation.

## Tool inputs

All query tools require `query` (1–256 code points, not whitespace-only), accept
`offset` ≥ 0 and `limit` 1–50, and return `next_offset` for continued traversal.
The three query-based `get_*` tools below default to 20 results; search and reverse lookup
default to 10. Pagination is stable within a loaded snapshot.

| Tool | Additional arguments |
| --- | --- |
| `get_shabda` | `by: text` (default) or `upstream_id`; optional `linga: P/S/N/A` |
| `search_shabdas` | Optional `linga`; literal ranked search of word and available meaning fields |
| `get_dhatu_forms` | `by: text/upstream_id/baseindex`; optional `category: tinanta/krdanta`, `family: vidyut/upstream`, `derivation`, `prayoga`, `pada: P/A`, `lakara`, `pratyaya`, `purusha`, `vacana: 1/2/3` |
| `get_shabda_forms` | Same identity/gender arguments as `get_shabda`; optional `vibhakti: 1..8`, `vacana: 1..3` |
| `lookup_form` | `kind: all` (default), `dhatu`, or `shabda`; `include_vocative_alias: true` (default) |
| `get_form_coverage` | No arguments |

Finite-only filters cannot be combined with kṛdanta-only filters. The separate
upstream kṛdanta source has no derivation label, so `family: upstream` cannot be
combined with `derivation`. Invalid combinations return `INVALID_INPUT`.
Text identity lookup uses NFC and whitespace normalization and retains every
matching lexical entry. Exact IDs retain upstream spelling and padding.

Examples:

```json
{"query":"01.0001","by":"baseindex","derivation":"shuddha","prayoga":"kartari","lakara":"lat","pada":"P"}
```

For `get_dhatu_forms`, this returns the stored nine-slot paradigm beginning
`भवति`. Remove the filters and follow every `next_offset` to retrieve all stored
paradigm fields for that root across the loaded sources.

```json
{"query":"@rAma1","by":"upstream_id","vibhakti":5,"vacana":1}
```

For `get_shabda_forms`, this returns alternatives `रामाद्`, `रामात्` while retaining
the original source field and exact slot text `रामाद्-रामात्`.

## Output semantics for agents

Form results include `matched_lemma_ids`, paginated `results`, per-lemma/source
`coverage`, `scope: stored-upstream-paradigms`, and `exhaustive: false`. A result is
one source paradigm field, not one alternative. Each evidence object includes:

- Source dimensions, lexical ID, baseindex where applicable, and original source key.
- Full unchanged `raw_text`, decoded `cells`, `parse_status`, and `warnings`.
- Cells with unchanged slot/group text, variants, zero-based group/slot coordinates,
  role, and applicable person, number, case and gender metadata.
- Provenance pointing to the exact original field, including pinned URL, hash,
  JSON Pointer and download timestamp. Filtered cells still cite the full raw field.

An unknown lemma returns `NOT_FOUND`. A known lemma without matching form fields
returns success with zero results. Coverage distinguishes `present`, `empty`,
`absent`, and `not_loaded`; available keys are reported before field filters.
If no selected source is loaded, the tool returns `SOURCE_NOT_LOADED`.
`get_form_coverage` works even with a core snapshot and lists the missing sources.

Reverse lookup checks normalized exact alternatives, retaining every occurrence
across lexical entries, cases, numbers, genders and sources. For example, `रामौ`
matches nominative and accusative dual and, by default, stored vocative `हे रामौ`.
The latter is explicitly labelled `vocative_particle_removed`; disable the alias
to require the full stored expression. `भवति` matches both finite verbs and noun
forms. There is no accent removal, transliteration, sandhi splitting or contextual
disambiguation. Results report searched/missing sources and unparsed-group counts.
An unparsed group is searchable only as a whole, not as guessed constituent forms.

No match does not establish grammatical invalidity. Future anvaya and sandhi
agents must preserve these candidates and their evidence while applying separately
validated context, sandhi, compound, prefix and generation capabilities. A finite
stored catalog cannot cover arbitrary Sanskrit composition.

## Validation and attribution

Offline tests cover all derivation families, stored lakāras, both prayogas and
padas, person/number slots, all case/number slots, gender ambiguity, pronouns,
restricted-number paradigms, alternatives, malformed source groups, Unicode,
pagination, provenance, failed-import rollback and both MCP stdio modes.

The opt-in integration audit traverses every field and slot in all seventeen
actual source files, reconstructs the original text, checks catalog linkage,
accounts for the known malformed groups, exercises reverse ambiguity, and checks
representation of all ten gaṇas. It never downloads data implicitly:

```sh
uv run ashtadhyayi-mcp --data-dir .data sync --profile full
ASHTADHYAYI_INTEGRATION_DATA_DIR=.data uv run pytest
```

These tests establish retrieval fidelity, not independent grammatical correctness
of every precomputed output. Fixtures retain original source attribution and
record pointers; synthetic malformed snapshots are explicitly test data.
Credit Ashtadhyayi.com, Neelesh Bodas and contributors, and Vidyut/Ambuda contributors
for the labelled precomputed collections. See [third-party notices](../THIRD_PARTY_NOTICES.md).
