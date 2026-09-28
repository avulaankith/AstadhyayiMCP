import itertools
import json

import pytest
from conftest import SYNTHETIC_REVISION
from pydantic import ValidationError

from ashtadhyayi_mcp.adapters import load_active
from ashtadhyayi_mcp.domain import DataError
from ashtadhyayi_mcp.form_adapter import decode_form
from ashtadhyayi_mcp.form_models import (
    CoverageInput,
    DhatuFormsInput,
    FormLookupInput,
    ShabdaFormsInput,
    ShabdaInput,
    ShabdaSearchInput,
)
from ashtadhyayi_mcp.form_sources import FORM_SOURCES, SHABDA_PATH, SOURCE_BY_PATH
from ashtadhyayi_mcp.forms import FormRetrieval
from ashtadhyayi_mcp.services import Retrieval
from ashtadhyayi_mcp.sync import sync


def dhatu_args(**kwargs):
    return DhatuFormsInput(query="01.0001", by="baseindex", **kwargs)


def resolve(document, pointer):
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


@pytest.mark.parametrize(
    ("derivation", "expected"),
    [
        ("shuddha", "भवति"),
        ("nich", "भावयति"),
        ("san", "बुभूषति"),
        ("yang", "बोभूयते"),
        ("yangluk", "बोभवीति"),
    ],
)
def test_five_derivation_families_from_source(forms, derivation, expected):
    page = forms.get_dhatu_forms(dhatu_args(derivation=derivation, prayoga="kartari", lakara="lat"))
    assert any(expected in cell.variants for row in page.data.results for cell in row.data.cells)
    assert all(r.data.derivation == derivation for r in page.data.results)
    assert page.data.exhaustive is False


@pytest.mark.parametrize(
    "lakara",
    [
        "lat",
        "lit",
        "lut",
        "lrut",
        "lot",
        "lang",
        "vidhiling",
        "ashirling",
        "lung",
        "lrung",
    ],
)
@pytest.mark.parametrize("prayoga", ["kartari", "karmani"])
def test_all_stored_lakaras_and_both_prayogas(forms, lakara, prayoga):
    page = forms.get_dhatu_forms(dhatu_args(derivation="shuddha", prayoga=prayoga, lakara=lakara))
    assert page.data.total >= 1
    for row in page.data.results:
        assert row.data.lakara == lakara
        assert row.data.prayoga == prayoga
        assert len(row.data.cells) == 9
        assert [c.purusha for c in row.data.cells] == (
            ["prathama"] * 3 + ["madhyama"] * 3 + ["uttama"] * 3
        )
        assert [c.vacana for c in row.data.cells] == [1, 2, 3] * 3
        assert ";".join(c.raw_text for c in row.data.cells) == row.data.raw_text


def test_ubhaya_and_pada_filter(forms):
    roots = forms.get_dhatu_forms(
        DhatuFormsInput(
            query="08.0010",
            by="baseindex",
            derivation="shuddha",
            lakara="lat",
            prayoga="kartari",
        )
    ).data
    assert {row.data.pada for row in roots.results} == {"P", "A"}
    singular = forms.get_dhatu_forms(
        DhatuFormsInput(
            query="08.0010",
            by="baseindex",
            derivation="shuddha",
            lakara="lat",
            prayoga="kartari",
            pada="P",
            purusha="uttama",
            vacana=1,
        )
    ).data
    assert singular.total == 1
    assert singular.results[0].data.cells[0].variants == ["करोमि"]


def test_dhatu_ambiguity_and_complete_pagination(forms):
    all_rows = []
    offset = 0
    while True:
        page = forms.get_dhatu_forms(DhatuFormsInput(query="भू", offset=offset, limit=50)).data
        assert len(page.matched_lemma_ids) == 3
        all_rows.extend(page.results)
        if page.next_offset is None:
            break
        offset = page.next_offset
    assert len(all_rows) == page.total
    assert (
        len({(r.data.lemma_id, r.provenance.source_path, r.data.source_key) for r in all_rows})
        == page.total
    )
    assert {r.provenance.source_path for r in all_rows} == {
        s.path for s in FORM_SOURCES if s.category != "subanta"
    }
    assert forms.get_dhatu_forms(dhatu_args(offset=100000)).data.results == []


def test_krut_sources_not_merged_or_mislabelled(forms):
    page = forms.get_dhatu_forms(dhatu_args(pratyaya="क्त", limit=50)).data
    assert {r.data.source_family for r in page.results} == {"vidyut", "upstream"}
    original = next(r for r in page.results if r.data.source_family == "upstream")
    assert original.data.raw_text == "भूतः,भूता"
    assert original.data.cells[0].role == "unspecified"
    assert original.data.cells[0].linga is None
    generated = next(r for r in page.results if r.data.derivation == "shuddha")
    assert [c.linga for c in generated.data.cells[:4]] == [None, "P", "S", "N"]
    assert generated.data.cells[0].variants == ["भूत"]
    assert generated.data.cells[1].variants == ["भूतः"]


def test_real_malformed_group_retained_without_gender_inference(forms):
    page = forms.get_dhatu_forms(
        DhatuFormsInput(
            query="01.0097",
            by="baseindex",
            derivation="yangluk",
            pratyaya="शतृ",
        )
    ).data
    row = page.results[0].data
    assert row.parse_status == "partial"
    assert row.warnings
    bad = [c for c in row.cells if c.role == "unparsed"]
    assert len(bad) == 2
    assert all(c.linga is None and c.vacana is None for c in bad)
    assert all(c.raw_text in row.raw_text for c in bad)
    assert row.raw_text.startswith("वर्वृकत्,वर्वृकत्/वर्वृकद्;")


@pytest.mark.parametrize(
    ("word", "first", "gender"),
    [
        ("राम", "रामः", "P"),
        ("फल", "फलम्", "N"),
        ("नदी", "नदी", "S"),
        ("गुरु", "गुरुः", "P"),
        ("मातृ", "माता", "S"),
        ("राजन्", "राजा", "P"),
        ("अस्मद्", "अहम्", "A"),
        ("युष्मद्", "त्वम्", "A"),
    ],
)
def test_noun_pronoun_consonant_and_vowel_stems(forms, word, first, gender):
    page = forms.get_shabda_forms(ShabdaFormsInput(query=word, linga=gender)).data
    assert page.total >= 1
    row = page.results[0].data
    assert row.cells[0].variants[0] == first
    assert len(row.cells) == 24
    assert ";".join(c.raw_text for c in row.cells) == row.raw_text
    assert all(c.linga == gender for c in row.cells)
    assert [(c.vibhakti, c.vacana) for c in row.cells] == list(
        itertools.product(range(1, 9), range(1, 4))
    )


@pytest.mark.parametrize(("vibhakti", "vacana"), list(itertools.product(range(1, 9), range(1, 4))))
def test_case_number_filters_do_not_shift_slots(forms, vibhakti, vacana):
    data = (
        forms.get_shabda_forms(
            ShabdaFormsInput(
                query="राम",
                vibhakti=vibhakti,
                vacana=vacana,
            )
        )
        .data.results[0]
        .data
    )
    assert len(data.cells) == 1
    assert data.cells[0].slot_index == (vibhakti - 1) * 3 + vacana - 1
    assert data.cells[0].raw_text == data.raw_text.split(";")[data.cells[0].slot_index]


def test_empty_slots_and_alternatives(forms):
    dvi = forms.get_shabda_forms(ShabdaFormsInput(query="द्वि", linga="P")).data.results[0].data
    assert dvi.cells[0].raw_text == "" and dvi.cells[0].variants == []
    assert dvi.cells[1].variants == ["द्वौ"]
    assert dvi.cells[2].raw_text == "" and dvi.cells[2].vacana == 3
    assert all(not c.variants for c in dvi.cells[21:])
    rama = forms.get_shabda_forms(ShabdaFormsInput(query="राम", vibhakti=5, vacana=1)).data
    assert rama.results[0].data.cells[0].variants == ["रामाद्", "रामात्"]
    asmad = forms.get_shabda_forms(ShabdaFormsInput(query="अस्मद्", vibhakti=2, vacana=1)).data
    assert asmad.results[0].data.cells[0].variants == ["माम्", "मा"]


def test_shabda_ambiguity_and_catalog_search(forms):
    page = forms.get_shabda(ShabdaInput(query="तद्")).data
    assert page.total == 3 and {r.data.linga for r in page.matches} == {"P", "S", "N"}
    exact = forms.get_shabda(ShabdaInput(query="@tad2", by="upstream_id")).data
    assert exact.total == 1 and exact.matches[0].data.linga == "S"
    assert forms.search_shabdas(ShabdaSearchInput(query="राम")).data.total >= 1
    assert forms.search_shabdas(ShabdaSearchInput(query="तद्", linga="N")).data.total == 1
    assert forms.get_shabda(ShabdaInput(query="तद्", limit=1, offset=1)).data.next_offset == 2


def test_reverse_lookup_preserves_case_ambiguity_and_vocative_alias(forms):
    page = forms.lookup_form(FormLookupInput(query="रामौ", kind="shabda")).data
    assert {(r.data.cell.vibhakti, r.data.cell.vacana) for r in page.results} == {
        (1, 2),
        (2, 2),
        (8, 2),
    }
    vocative = next(r for r in page.results if r.data.cell.vibhakti == 8)
    assert vocative.data.matched_variant == "हे रामौ"
    assert vocative.data.match_kind == "vocative_particle_removed"
    assert (
        forms.lookup_form(
            FormLookupInput(
                query="रामौ",
                kind="shabda",
                include_vocative_alias=False,
            )
        ).data.total
        == 2
    )
    assert forms.lookup_form(FormLookupInput(query="हे रामौ", kind="shabda")).data.total == 1
    first = forms.lookup_form(FormLookupInput(query="रामौ", limit=1)).data
    second = forms.lookup_form(FormLookupInput(query="रामौ", limit=1, offset=1)).data
    assert first.results + second.results == page.results[:2]
    assert forms.lookup_form(FormLookupInput(query="रामौ", offset=100)).data.results == []


def test_reverse_exact_not_substring_and_no_inferred_invalidity(forms):
    for text in ("ामौ", "future-form-not-stored"):
        page = forms.lookup_form(FormLookupInput(query=text)).data
        assert page.total == 0 and not page.exhaustive
        assert "does not establish invalidity" in page.interpretation
    assert forms.lookup_form(FormLookupInput(query="भवति", kind="dhatu")).data.total >= 1
    assert forms.lookup_form(FormLookupInput(query="रामात्")).data.results[0].data.cell.vibhakti == 5
    assert forms.lookup_form(FormLookupInput(query="  रामौ  ")).data.query == "  रामौ  "
    assert forms.lookup_form(FormLookupInput(query="रामौ")).data.query == "रामौ"


@pytest.mark.parametrize("path", [s.path for s in FORM_SOURCES])
def test_each_collection_is_reverse_searchable(forms, path):
    if path == SHABDA_PATH:
        row = forms.get_shabda_forms(ShabdaFormsInput(query="राम")).data.results[0]
    else:
        spec = SOURCE_BY_PATH[path]
        rows = forms.get_dhatu_forms(
            dhatu_args(
                category=spec.category,
                derivation=spec.derivation,
                prayoga=spec.prayoga,
                family=spec.family,
                limit=50,
            )
        ).data.results
        row = next(r for r in rows if r.provenance.source_path == path)
    variant = next(v for c in row.data.cells for v in c.variants)
    offset = 0
    found = False
    while True:
        page = forms.lookup_form(FormLookupInput(query=variant, limit=50, offset=offset)).data
        found |= any(r.provenance == row.provenance for r in page.results)
        if page.next_offset is None:
            break
        offset = page.next_offset
    assert found, (path, variant)


def test_returned_raw_evidence_resolves_exactly(forms, form_documents):
    rows = forms.get_dhatu_forms(dhatu_args(limit=50)).data.results
    rows += forms.get_shabda_forms(ShabdaFormsInput(query="तद्")).data.results
    for row in rows:
        assert (
            resolve(form_documents[row.provenance.source_path], row.provenance.source_pointer)
            == row.data.raw_text
        )
    for hit in forms.lookup_form(FormLookupInput(query="भवति")).data.results:
        raw = resolve(form_documents[hit.provenance.source_path], hit.provenance.source_pointer)
        assert hit.data.cell.raw_text in raw
        assert hit.data.matched_variant in raw


def test_coverage_core_snapshot_and_partial_snapshot(data_dir, forms):
    core = FormRetrieval(Retrieval(load_active(data_dir)))
    coverage = core.get_form_coverage(CoverageInput()).data
    assert len(coverage.missing_sources) == 17 and not coverage.sources
    with pytest.raises(DataError) as exc:
        core.get_shabda_forms(ShabdaFormsInput(query="राम"))
    assert exc.value.error.code == "SOURCE_NOT_LOADED"
    # A source can be absent from a valid optional profile; others remain usable.
    absent_path = "dhatu/dhatuforms_vidyut_nich_kartari.txt"
    del forms.corpus.manifest.files[absent_path]
    del forms.corpus.dhatu_forms[absent_path]
    page = forms.get_dhatu_forms(dhatu_args()).data
    assert any(c.source_path == absent_path and c.status == "not_loaded" for c in page.coverage)
    assert absent_path in forms.lookup_form(FormLookupInput(query="भवति")).data.missing_sources


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": "krdanta", "lakara": "lat"},
        {"pratyaya": "क्त", "purusha": "prathama"},
        {"category": "tinanta", "pratyaya": "क्त"},
        {"family": "upstream", "derivation": "nich"},
        {"vacana": 4},
        {"pada": "U"},
        {"pratyaya": "  "},
        {"limit": True},
    ],
)
def test_invalid_or_incompatible_filters(kwargs):
    with pytest.raises(ValidationError):
        dhatu_args(**kwargs)


@pytest.mark.parametrize("bad", ["shabda_slots", "verb_slots", "key", "type", "duplicate"])
def test_invalid_forms_fail_sync_atomically(tmp_path, form_documents, form_fetcher, bad):
    sync(tmp_path, SYNTHETIC_REVISION, profile="full", fetcher=form_fetcher)
    previous = (tmp_path / "current").read_bytes()
    path = "dhatu/dhatuforms_vidyut_shuddha_kartari.txt"
    if bad == "shabda_slots":
        form_documents[SHABDA_PATH]["data"][0]["forms"] = "wrong;length"
    elif bad == "verb_slots":
        form_documents[path]["01.0001"]["plat"] = "wrong;length"
    elif bad == "key":
        form_documents[path]["01.0001"]["newkey"] = ";" * 8
    elif bad == "type":
        form_documents[path]["01.0001"]["plat"] = None
    else:
        form_documents[SHABDA_PATH]["data"].append(form_documents[SHABDA_PATH]["data"][0])
    with pytest.raises(DataError):
        sync(tmp_path, SYNTHETIC_REVISION, profile="full", fetcher=form_fetcher)
    assert previous == (tmp_path / "current").read_bytes()


def test_form_unicode_empty_and_variants_decoder_roundtrip():
    source = SOURCE_BY_PATH[SHABDA_PATH]
    slots = ["क़-क\u093c", "अ॑", "अ॒", "क्\u200cष", "क्\u200dष", "ऽ", "ं", "ः", ""] + [""] * 15
    raw = ";".join(slots)
    data = decode_form(source, "synthetic", None, "forms", raw, "P")
    assert ";".join(c.raw_text for c in data.cells) == raw
    assert json.loads(data.model_dump_json())["raw_text"] == raw
    assert data.cells[0].variants == ["क़", "क\u093c"]
