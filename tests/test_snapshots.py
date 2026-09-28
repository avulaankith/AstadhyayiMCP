import hashlib
import json

import pytest
from conftest import SYNTHETIC_REVISION

from ashtadhyayi_mcp.adapters import decode_json, load_active
from ashtadhyayi_mcp.domain import DataError
from ashtadhyayi_mcp.sync import sync


def active_directory(data_dir):
    return data_dir / "snapshots" / (data_dir / "current").read_text().strip()


def test_sync_real_bytes_and_file_provenance(data_dir):
    corpus = load_active(data_dir)
    path = active_directory(data_dir)
    for record in [*corpus.sutras, *corpus.dhatus]:
        source = record.provenance
        raw = (path / source.source_path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source.source_sha256
        value = json.loads(raw)
        for segment in source.source_pointer.strip("/").split("/"):
            value = value[int(segment)] if isinstance(value, list) else value[segment]
        assert value == record.data.upstream_record
        assert source.upstream_revision == SYNTHETIC_REVISION


def test_failed_sync_does_not_replace_active_snapshot(data_dir, fetcher):
    previous = (data_dir / "current").read_bytes()
    calls = 0

    def broken(url, maximum):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("synthetic interrupted download")
        return fetcher(url, maximum)

    with pytest.raises(OSError):
        sync(data_dir, SYNTHETIC_REVISION, fetcher=broken)
    assert (data_dir / "current").read_bytes() == previous
    assert load_active(data_dir).sutras
    assert not list((data_dir / "snapshots").glob(".pending-*"))


@pytest.mark.parametrize("change", ["duplicate", "identity", "type", "empty", "commentary"])
def test_invalid_upstream_never_activates(tmp_path, documents, fetcher, change):
    records = documents["sutraani/data.txt"]["data"]
    if change == "duplicate":
        records.append(records[0])
    elif change == "identity":
        records[0]["n"] = "2"
    elif change == "type":
        records[0]["s"] = 123
    elif change == "empty":
        records.clear()
    else:
        documents["sutraani/kashika.txt"]["61077"] = {"bad": "shape"}
    with pytest.raises(DataError) as exc:
        sync(tmp_path, SYNTHETIC_REVISION, fetcher=fetcher)
    assert exc.value.error.code == "UPSTREAM_SCHEMA_ERROR"
    assert not (tmp_path / "current").exists()


def test_hash_corruption_fails_closed(data_dir):
    path = active_directory(data_dir) / "sutraani/data.txt"
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"name"', b'"nAme"', 1))
    with pytest.raises(DataError, match="Hash mismatch"):
        load_active(data_dir)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b"\xff",
        b"{}broken",
        b'{"a":1e999}',
        b'{"a":"\\ud800"}',
    ],
)
def test_malformed_json_rejected(raw):
    with pytest.raises(ValueError):
        decode_json(raw)


def test_branch_resolved_once_and_downloads_pinned(tmp_path, fetcher):
    urls = []

    def branch_fetch(url, maximum):
        urls.append(url)
        if "api.github.com" in url:
            return json.dumps({"sha": SYNTHETIC_REVISION}).encode()
        return fetcher(url, maximum)

    sync(tmp_path, "master", fetcher=branch_fetch)
    assert len([url for url in urls if "api.github.com" in url]) == 1
    assert all(SYNTHETIC_REVISION in url for url in urls[1:])


def test_manifest_path_traversal_rejected(data_dir):
    path = active_directory(data_dir) / "manifest.json"
    data = json.loads(path.read_text())
    data["files"]["../../anything"] = data["files"]["sutraani/data.txt"]
    path.write_text(json.dumps(data))
    with pytest.raises(DataError):
        load_active(data_dir)


def test_unmatched_commentary_is_reported_not_synthesized(tmp_path, documents, fetcher, caplog):
    documents["sutraani/kashika.txt"]["p1"] = "synthetic non-sūtra heading"
    sync(tmp_path, SYNTHETIC_REVISION, fetcher=fetcher)
    assert "unmatched IDs" in caplog.text
    assert all(s.data.upstream_id != "p1" for s in load_active(tmp_path).sutras)
