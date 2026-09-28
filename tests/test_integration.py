import json
import os
from pathlib import Path

import pytest

from ashtadhyayi_mcp.adapters import PINNED_REVISION, load_active
from ashtadhyayi_mcp.domain import ContextInput, DhatuInput, SearchInput, SutraInput
from ashtadhyayi_mcp.services import Retrieval

pytestmark = pytest.mark.integration


def resolve(document, pointer):
    for part in pointer.lstrip("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def test_full_upstream_snapshot_and_provenance():
    directory = os.environ.get("ASHTADHYAYI_INTEGRATION_DATA_DIR")
    if not directory:
        pytest.skip("Set ASHTADHYAYI_INTEGRATION_DATA_DIR to a synced snapshot cache")
    root = Path(directory)
    corpus = load_active(root)
    assert corpus.manifest.upstream_revision == PINNED_REVISION, "Sync the regression revision"
    assert len(corpus.sutras) == 3983
    assert len(corpus.dhatus) == 2259
    service = Retrieval(corpus)
    for number, text in [("6.1.77", "इको यणचि"), ("6.1.87", "आद्गुणः")]:
        assert service.get_sutra(SutraInput(number=number)).data.sutra.data.text == text
    assert service.get_dhatu(DhatuInput(query="भू")).data.total == 3
    for query in ["यण्", "गुण", "सवर्ण", "इको यणचि"]:
        assert service.search_sutras(SearchInput(query=query)).data.total > 0
    assert "6.1.77" in [
        hit.record.data.number
        for hit in service.search_sutras(SearchInput(query="यण्", limit=50)).data.results
    ]
    snapshot = root / "snapshots" / (root / "current").read_text().strip()
    documents = {path: json.loads((snapshot / path).read_bytes()) for path in corpus.manifest.files}
    for record in [*corpus.sutras, *corpus.dhatus]:
        prov = record.provenance
        assert (
            resolve(documents[prov.source_path], prov.source_pointer) == record.data.upstream_record
        )
    for number in ["6.1.77", "6.1.87", "8.2.1"]:
        chunks = service.get_sutra(
            SutraInput(
                number=number,
                commentary_offset=7,
                commentary_limit=19,
            )
        ).data.commentaries
        for chunk in chunks:
            prov = chunk.provenance
            text = resolve(documents[prov.source_path], prov.source_pointer)
            assert chunk.data.text == text[chunk.data.offset : chunk.data.offset + 19]
            assert chunk.data.total_characters == len(text)
    boundary = service.get_sutra_context(ContextInput(number="1.1.75", after=1)).data
    assert boundary.following[0].data.number == "1.2.1"
