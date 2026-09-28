# Third-party sources and attribution

## Ashtadhyayi.com

The scholarly source for this project's retrieval results is
**Ashtadhyayi.com — Neelesh Bodas and contributors**.

- Website: https://ashtadhyayi.com/
- Credits and source lineages: https://ashtadhyayi.com/credits
- Published data: https://github.com/ashtadhyayi-com/data
- Upstream editing workflow: https://github.com/ashtadhyayi-com/data-edit
- Researched revision: `5744762f010d677cfb43f347a42d02796cf615d6`

The upstream README allows use in projects with appropriate credit. Refer to the
[permission statement at the researched revision](https://github.com/ashtadhyayi-com/data/blob/5744762f010d677cfb43f347a42d02796cf615d6/README.md).
Neither inspected upstream repository had a standalone license file. We do not
assign an SPDX license to the data, relicense it as MIT, or claim all contributing
editions and transcriptions share the same permissions. The upstream credits page
documents multiple source lineages; consult it before redistributing a corpus.

Runtime downloads remain in a local cache outside the source package. This does
not remove the obligation to credit the original sources when reusing results.

## Loaded source collections

| Upstream path | Attribution scope |
| --- | --- |
| `sutraani/data.txt` | Ashtadhyayi.com sūtra catalog and metadata |
| `dhatu/data.txt` | Ashtadhyayi.com dhātu catalog and metadata |
| `sutraani/sutrartha.txt` | Ashtadhyayi.com explanations, fields `sa` and `sd` |
| `sutraani/sutrartha_english.txt` | Ashtadhyayi.com English explanations |
| `sutraani/kashika.txt` | Kāśikā text as digitized/published by Ashtadhyayi.com and its sources |
| `shabda/data2.txt` | Ashtadhyayi.com śabda catalog, metadata and stored declension tables |
| `dhatu/dhatuforms_krut.txt` | Upstream kṛdanta collection; retained separately from Vidyut-labelled files |
| `dhatu/dhatuforms_vidyut_{shuddha,nich,san,yang,yangluk}_{kartari,karmani,krut}.txt` | Precomputed Vidyut-labelled outputs distributed by Ashtadhyayi.com |

Credit also goes to [Vidyut / Ambuda contributors](https://github.com/ambuda-org/vidyut)
for the engine associated with the Vidyut-labelled collections. This package
retrieves those published strings; it does not run Vidyut or assert that generated
forms have independent textual attestation. Runtime provenance remains the actual
Ashtadhyayi.com file and commit, not an invented Vidyut source location.

These labels identify the actual collections used. They do not assert an
unverified author, editor, edition, or manuscript attribution. Each returned
object carries the precise source pointer and revision. The provider's text and
any future agent-generated explanation must remain distinct.

`tests/fixtures/upstream-excerpts.json` contains small excerpts from those files
for reproducible regression tests, with original pointers and full-file hashes.
They remain third-party material, excluded from the MIT license for our code.
`tests/fixtures/README.md` explains their provenance and use.
`tests/fixtures/form-excerpts.json` additionally preserves selected full paradigm
entries from every loaded form collection with original pointers and file metadata.
Those excerpts are likewise excluded from our code license.

## Software

This project uses the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
and [Pydantic](https://github.com/pydantic/pydantic), both published under MIT.
Installed dependencies retain their own license notices. `uv.lock` records exact
resolved package versions; this project's MIT license does not replace any
dependency's license.

This project is independent and does not imply endorsement by Ashtadhyayi.com or
the scholars and contributors whose work it retrieves.
