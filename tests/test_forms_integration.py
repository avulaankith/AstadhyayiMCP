"""Full-source audits: opt-in; do not fetch the network during testing."""

import os
from pathlib import Path

import pytest

from ashtadhyayi_mcp.adapters import PINNED_REVISION, load_active
from ashtadhyayi_mcp.form_adapter import cells_for, decode_form
from ashtadhyayi_mcp.form_models import DhatuFormsInput, FormLookupInput
from ashtadhyayi_mcp.form_sources import FORM_SOURCES, SHABDA_PATH
from ashtadhyayi_mcp.forms import FormRetrieval
from ashtadhyayi_mcp.services import Retrieval

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def full_corpus():
    directory = os.environ.get("ASHTADHYAYI_INTEGRATION_DATA_DIR")
    if not directory:
        pytest.skip("Set ASHTADHYAYI_INTEGRATION_DATA_DIR to a full synced snapshot")
    corpus = load_active(Path(directory))
    if len(corpus.form_coverage) != 17:
        pytest.skip("Full form profile not synced; run sync --profile full")
    assert corpus.manifest.upstream_revision == PINNED_REVISION
    return corpus


@pytest.mark.parametrize("source", FORM_SOURCES, ids=lambda s: s.path)
def test_every_stored_form_field_decodes_losslessly(full_corpus, source):
    """Walk every field and slot, not just a few well-known roots or stems."""
    if source.path == SHABDA_PATH:
        assert len(full_corpus.shabdas) == 9007
        for record in full_corpus.shabdas:
            raw = record.data.upstream_record["forms"]
            cells = list(cells_for(source, raw, record.data.linga))
            assert len(cells) == 24
            assert ";".join(c.raw_text for c in cells) == raw
            assert [(c.vibhakti, c.vacana) for c in cells] == [
                (case, number) for case in range(1, 9) for number in range(1, 4)
            ]
        return
    fields_checked = bad_groups = 0
    rows = full_corpus.dhatu_forms[source.path]
    assert rows
    for baseindex, row in rows.items():
        for key, raw in row.items():
            data = decode_form(source, None, baseindex, key, raw)
            fields_checked += 1
            assert data.raw_text == raw
            if source.category == "tinanta":
                assert len(data.cells) == 9
                assert ";".join(c.raw_text for c in data.cells) == raw
                assert data.lakara == key[1:]
                assert data.pada.lower() == key[0]
            elif source.family == "upstream":
                assert len(data.cells) == 1
                assert data.cells[0].raw_text == raw
                assert data.cells[0].linga is None
            else:
                reconstructed = []
                for group_index, group in enumerate(raw.split(";")):
                    cells = [c for c in data.cells if c.group_index == group_index]
                    if len(group.split(",")) == 4:
                        assert [c.linga for c in cells] == [None, "P", "S", "N"]
                        reconstructed.append(",".join(c.raw_text for c in cells))
                    else:
                        bad_groups += 1
                        assert len(cells) == 1 and cells[0].role == "unparsed"
                        assert cells[0].linga is None and cells[0].vacana is None
                        reconstructed.append(cells[0].raw_text)
                assert ";".join(reconstructed) == raw
            for cell in data.cells:
                for variant in cell.variants:
                    assert variant in cell.raw_text
    report = next(s.data for s in full_corpus.form_coverage if s.data.source_path == source.path)
    assert fields_checked == report.paradigm_fields
    assert bad_groups == report.unparsed_groups
    assert not report.unlinked_identifiers


def test_full_coverage_gaps_and_all_ten_ganas(full_corpus):
    assert len(full_corpus.form_coverage) == 17
    assert sum(s.data.unparsed_groups for s in full_corpus.form_coverage) == 408
    basics = full_corpus.dhatu_forms["dhatu/dhatuforms_vidyut_shuddha_kartari.txt"]
    assert {
        d.data.upstream_record["gana"] for d in full_corpus.dhatus if d.data.baseindex in basics
    } == {str(gana) for gana in range(1, 11)}
    # Never pretend that all 2,259 catalog entries have forms in every source.
    assert len(basics) == 2229
    assert len(full_corpus.dhatu_forms["dhatu/dhatuforms_vidyut_yang_kartari.txt"]) == 1782
    assert len(full_corpus.dhatu_forms["dhatu/dhatuforms_krut.txt"]) == 1983
    forms = FormRetrieval(Retrieval(full_corpus))
    missing = next(d for d in full_corpus.dhatus if d.data.baseindex not in basics)
    result = forms.get_dhatu_forms(
        DhatuFormsInput(
            query=missing.data.upstream_id,
            by="upstream_id",
            derivation="shuddha",
            prayoga="kartari",
        )
    ).data
    assert result.total == 0 and result.coverage[0].status == "absent"
    assert result.coverage[0].provenance is None
    # लेट् is a supported key encoding, but these files do not store it.
    assert forms.get_dhatu_forms(DhatuFormsInput(query="भू", lakara="let")).data.total == 0


def test_full_reverse_lookup_preserves_cross_part_of_speech_ambiguity(full_corpus):
    forms = FormRetrieval(Retrieval(full_corpus))
    page = forms.lookup_form(FormLookupInput(query="भवति", limit=50)).data
    assert {r.data.category for r in page.results} >= {"tinanta", "subanta"}
    assert page.unparsed_groups == 408
    assert page.missing_sources == [] and page.exhaustive is False
    for result in page.results:
        prov = result.provenance
        assert prov.upstream_revision == PINNED_REVISION
        assert prov.source_sha256 == full_corpus.manifest.files[prov.source_path].sha256
        if result.data.category != "subanta":
            assert prov.source_pointer.startswith("/" + result.data.baseindex + "/")
            raw = full_corpus.dhatu_forms[prov.source_path][result.data.baseindex][
                result.data.source_key
            ]
            assert result.data.matched_variant in raw
    for query in ("रामौ", "कुर्वन्ति", "भूत्वा", "भावयति", "बुभूषति", "रामात्"):
        assert forms.lookup_form(FormLookupInput(query=query, limit=50)).data.total > 0


@pytest.mark.parametrize("source", FORM_SOURCES, ids=lambda s: s.path)
def test_full_reverse_samples_from_every_collection(full_corpus, source):
    """Select source values independently of the decoder, then recover their identity."""
    import re

    forms = FormRetrieval(Retrieval(full_corpus))
    if source.path == SHABDA_PATH:
        records = full_corpus.shabdas
        samples = [records[i] for i in (0, len(records) // 2, len(records) - 1)]
        candidates = [
            (r.data.upstream_id, "forms", r.data.upstream_record["forms"]) for r in samples
        ]
    else:
        rows = list(full_corpus.dhatu_forms[source.path].items())
        candidates = [
            (base, key, raw)
            for i in (0, len(rows) // 2, len(rows) - 1)
            for base, fields in [rows[i]]
            for key, raw in list(fields.items())[:1]
        ]
    checked = 0
    for identifier, key, raw in candidates:
        first_group = raw.split(";")[0]
        if source.category == "subanta":
            variants = first_group.split("-")
        elif source.category == "tinanta" or source.family == "upstream":
            variants = re.split(r"[,/]", first_group)
        else:
            columns = first_group.split(",")
            if len(columns) != 4:
                continue  # Malformed groups have separate raw-preservation tests.
            variants = columns[0].split("/")
        query = next((v.strip() for v in variants if v.strip() not in ("", "-")), None)
        if query is None:
            continue
        assert len(query) <= 256
        offset = 0
        found = False
        while True:
            page = forms.lookup_form(
                FormLookupInput(query=query, limit=50, offset=offset, include_vocative_alias=False)
            ).data
            for result in page.results:
                match = result.data
                if (
                    result.provenance.source_path == source.path
                    and (match.lemma_id if source.category == "subanta" else match.baseindex)
                    == identifier
                    and match.source_key == key
                ):
                    assert match.matched_variant.strip() == query
                    assert match.cell.group_index == 0
                    found = True
            if page.next_offset is None:
                break
            assert page.next_offset > offset
            offset = page.next_offset
        assert found, (source.path, identifier, key, query)
        checked += 1
    assert checked > 0


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_full_corpus_all_tools_over_stdio(full_corpus, mode):
    import asyncio
    import json
    import sys

    import jsonschema
    from mcp import Client, StdioServerParameters

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "ashtadhyayi_mcp.cli",
                "--data-dir",
                os.environ["ASHTADHYAYI_INTEGRATION_DATA_DIR"],
                "serve",
            ],
        )
        calls = {
            "get_sutra": {"number": "6.1.77"},
            "search_sutras": {"query": "यण्"},
            "get_sutra_context": {"number": "6.1.77"},
            "get_dhatu": {"query": "भू"},
            "search_dhatus": {"query": "सत्तायाम्"},
            "get_shabda": {"query": "तद्"},
            "search_shabdas": {"query": "राम"},
            "get_dhatu_forms": {"query": "भू", "limit": 50},
            "get_shabda_forms": {"query": "तद्"},
            "lookup_form": {"query": "भवति"},
            "get_form_coverage": {},
        }
        async with Client(params, mode=mode, read_timeout_seconds=30) as client:
            definitions = {t.name: t for t in (await client.list_tools()).tools}
            assert definitions.keys() == calls.keys()
            for name, arguments in calls.items():
                result = await client.call_tool(name, arguments)
                assert not result.is_error, (name, result)
                body = result.structured_content
                jsonschema.validate(body, definitions[name].output_schema)
                assert json.loads(result.content[0].text) == body
                assert body["snapshot"]["upstream_revision"] == PINNED_REVISION
                assert len(body["snapshot"]["loaded_form_sources"]) == 17
                if name == "get_form_coverage":
                    assert body["data"]["missing_sources"] == []
                if name == "lookup_form":
                    assert {r["data"]["category"] for r in body["data"]["results"]} >= {
                        "tinanta",
                        "subanta",
                    }
            bad = await client.call_tool("lookup_form", {"query": "भवति", "limit": 51})
            assert bad.is_error
            assert bad.structured_content["error"]["code"] == "INVALID_INPUT"
            # An invalid request must not poison the live session.
            recovered = await client.call_tool("lookup_form", {"query": "रामौ"})
            assert not recovered.is_error
            assert recovered.structured_content["data"]["total"] >= 3

    asyncio.run(asyncio.wait_for(run(), timeout=90))
