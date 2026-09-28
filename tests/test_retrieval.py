import json

import pytest

from ashtadhyayi_mcp.domain import (
    ContextInput,
    DataError,
    DhatuInput,
    SearchInput,
    SutraInput,
)
from ashtadhyayi_mcp.indexing import normalize
from ashtadhyayi_mcp.services import Retrieval


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        ("6.1.77", "इको यणचि"),
        ("6.1.87", "आद्गुणः"),
        ("६.१.७७", "इको यणचि"),
    ],
)
def test_upstream_sutra(service, number, expected):
    result = service.get_sutra(SutraInput(number=number)).data
    assert result.sutra.data.text == expected
    assert result.sutra.provenance.source_path == "sutraani/data.txt"
    assert result.sutra.provenance.upstream_revision == "5744762f010d677cfb43f347a42d02796cf615d6"
    for commentary in result.commentaries:
        assert commentary.provenance.source_path != "sutraani/data.txt"
        assert commentary.provenance.source_pointer.startswith("/" + result.sutra.data.upstream_id)


def test_yan_is_source_metadata_not_phonetic_guess(service):
    hits = service.search_sutras(SearchInput(query="यण्", limit=50)).data.results
    hit = next(hit for hit in hits if hit.record.data.number == "6.1.77")
    assert any(match.field == "pc" and match.matched_text == "यण्" for match in hit.matches)
    assert all(match.provenance.source_pointer.endswith("/" + match.field) for match in hit.matches)
    assert "यण्" not in hit.record.data.text


def test_query_and_source_whitespace_preserved(service):
    result = service.search_sutras(SearchInput(query="  इको\n यणचि  ")).data
    assert result.query == "  इको\n यणचि  "
    assert result.normalized_query == "इको यणचि"
    assert result.results[0].record.data.number == "6.1.77"
    assert result.results[0].record.data.upstream_record["ss"].endswith(" ")


@pytest.mark.parametrize("query", ["गुण", "सवर्ण", "इको यणचि"])
def test_lexical_examples(service, query):
    # The small fixture may not contain every matching full-corpus record.
    result = service.search_sutras(SearchInput(query=query))
    for hit in result.data.results:
        assert any(normalize(query) in normalize(match.matched_text) for match in hit.matches)


def test_search_stable_pagination(service):
    all_hits = service.search_sutras(SearchInput(query="अ", limit=50)).data
    first = service.search_sutras(SearchInput(query="अ", limit=1)).data
    second = service.search_sutras(SearchInput(query="अ", limit=1, offset=1)).data
    assert first.total == all_hits.total
    assert first.results + second.results == all_hits.results[:2]
    assert first.next_offset == 1
    assert service.search_sutras(SearchInput(query="अ", offset=10000)).data.results == []
    assert service.search_sutras(SearchInput(query="no-such-sanskrit-string")).data.total == 0


@pytest.mark.parametrize(
    ("number", "code"),
    [
        ("9.1.1", "INVALID_INPUT"),
        ("1.5.1", "INVALID_INPUT"),
        ("6.1.0", "INVALID_INPUT"),
        ("abc", "INVALID_INPUT"),
        ("8.4.999", "NOT_FOUND"),
    ],
)
def test_bad_or_absent_number(service, number, code):
    with pytest.raises(DataError) as exc:
        service.get_sutra(SutraInput(number=number))
    assert exc.value.error.code == code


def test_dhatu_ambiguity_and_exact_identifiers(service):
    roots = service.get_dhatu(DhatuInput(query="भू")).data
    assert roots.total == 3
    assert [r.data.upstream_id for r in roots.matches] == ["1010001", "1100277", "1100382"]
    exact = service.get_dhatu(DhatuInput(query="01.0001", by="baseindex")).data.matches[0]
    assert exact.data.upstream_record["artha"] == "सत्तायाम्"
    assert exact.provenance.source_path == "dhatu/data.txt"
    assert "upasargas" in exact.data.upstream_record
    assert service.get_dhatu(DhatuInput(query="1010001", by="upstream_id")).data.total == 1
    assert service.get_dhatu(DhatuInput(query="भू", offset=100)).data.matches == []
    with pytest.raises(DataError):
        service.get_dhatu(DhatuInput(query="1.1", by="baseindex"))
    hits = service.search_dhatus(SearchInput(query="सत्तायाम्")).data.results
    assert hits[0].record.data.upstream_id == "1010001"


def test_context_is_adjacency_with_raw_source_fields(service):
    result = service.get_sutra_context(ContextInput(number="6.1.77")).data
    assert [r.data.number for r in result.preceding] == ["6.1.75", "6.1.76"]
    assert [r.data.number for r in result.following] == ["6.1.78", "6.1.79"]
    assert result.contextual_metadata.data["ad"] == "संहितायाम्$6$1$72"
    assert result.relationship == "corpus-adjacency"
    assert service.get_sutra_context(ContextInput(number="1.1.1")).data.preceding == []
    assert service.get_sutra_context(ContextInput(number="8.4.68")).data.following == []
    boundary = service.get_sutra_context(ContextInput(number="1.1.75", after=1)).data
    assert boundary.following[0].data.number == "1.2.1"


def test_commentary_absence_empty_and_unloaded_distinguished(corpus):
    corpus.commentaries["sutrartha"]["61077"]["sa"] = ""
    del corpus.commentaries["sutrartha"]["61077"]["sd"]
    result = (
        Retrieval(corpus)
        .get_sutra(
            SutraInput(
                number="6.1.77",
                commentaries=["sutrartha"],
            )
        )
        .data
    )
    assert [c.status for c in result.coverage] == ["empty", "absent"]
    assert result.coverage[0].provenance is not None
    assert result.coverage[1].provenance is None
    assert not result.commentaries
    del corpus.commentaries["sutrartha"]
    with pytest.raises(DataError) as exc:
        Retrieval(corpus).get_sutra(SutraInput(number="6.1.77"))
    assert exc.value.error.code == "SOURCE_NOT_LOADED"


def test_unicode_chunks_reconstruct_exact_source(corpus):
    # Explicitly synthetic Unicode stress string, not a grammatical assertion.
    original = "क़ क\u093c ॐ अ॑ अ॒ अ॔ ऽ ं ः क्\u200cष क्\u200dष\n\t😀 । ॥  "
    corpus.commentaries["sutrartha"]["61077"]["sa"] = original
    service = Retrieval(corpus)
    assembled = ""
    offset = 0
    while True:
        result = service.get_sutra(
            SutraInput(
                number="6.1.77",
                commentaries=["sutrartha"],
                commentary_offset=offset,
                commentary_limit=3,
            )
        ).data
        chunk = next(c.data for c in result.commentaries if c.data.field == "sa")
        assembled += chunk.text
        assert json.loads(chunk.model_dump_json())["text"] == chunk.text
        if chunk.next_offset is None:
            break
        offset = chunk.next_offset
    assert assembled == original
    assert normalize("क़") == normalize("क\u093c")
    for mark in ("॑", "॒", "॔", "ऽ", "ं", "ः", "्", "\u200c", "\u200d"):
        assert mark in normalize(original)


def test_unknown_metadata_survives(corpus):
    corpus.sutras[0].data.upstream_record["future_field"] = {"note": ["अ॑", 1, None]}
    result = Retrieval(corpus).get_sutra(SutraInput(number="1.1.1", commentaries=[]))
    assert result.data.sutra.data.upstream_record["future_field"] == {"note": ["अ॑", 1, None]}
