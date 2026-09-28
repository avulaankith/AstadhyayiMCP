# Fixture provenance

`upstream-excerpts.json` contains selected unmodified catalog records and the
commentary entries for 6.1.77 and 6.1.87, extracted from the five pinned files
downloaded by this project's sync command. Credit: **Ashtadhyayi.com — Neelesh Bodas
and contributors**. See [third-party notices](../../THIRD_PARTY_NOTICES.md).

Each evidence object retains its original full-file hash, commit, JSON Pointer,
and actual file download time. The manifest describes the full original files,
**not this excerpt file**. This fixture is loaded directly into the domain model;
it is not a complete snapshot and must not be installed as one. Missing neighbors
or commentary in this fixture say nothing about full upstream coverage.

Snapshot/import tests construct a separate synthetic mini-snapshot from these
records using revision `0000000000000000000000000000000000000000` and hashes of the
synthetic file bytes. Those test files deliberately make no claim to be an actual
upstream revision. Full provenance resolution is checked by opt-in integration
tests against a real downloaded snapshot.

`form-excerpts.json` contains seven selected dhātu catalog records, seventeen
śabda records, and their stored entries from all sixteen dhātu-form collections.
Its manifest describes the full original downloads, and catalog excerpts record
their original JSON Pointers. Form-map entries retain original baseindex/key
pointers. The file includes a known irregular yangluk kṛdanta entry so the parser
must preserve malformed groups instead of silently repairing them. Full-profile
test snapshots use the all-zero synthetic revision as described above; actual
upstream hashes are checked separately in integration tests.
