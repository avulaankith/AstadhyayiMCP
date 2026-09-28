import json
from pathlib import Path

import pytest

from ashtadhyayi_mcp.adapters import Corpus, Manifest
from ashtadhyayi_mcp.domain import DhatuData, Evidence, SutraData
from ashtadhyayi_mcp.services import Retrieval
from ashtadhyayi_mcp.sync import sync

SYNTHETIC_REVISION = "0" * 40


@pytest.fixture
def excerpts():
    return json.loads((Path(__file__).parent / "fixtures/upstream-excerpts.json").read_text())


@pytest.fixture
def corpus(excerpts):
    return Corpus(
        Manifest.model_validate(excerpts["manifest"]),
        [Evidence[SutraData].model_validate(item) for item in excerpts["sutras"]],
        [Evidence[DhatuData].model_validate(item) for item in excerpts["dhatus"]],
        excerpts["commentaries"],
    )


@pytest.fixture
def service(corpus):
    return Retrieval(corpus)


@pytest.fixture
def documents(excerpts):
    return {
        "sutraani/data.txt": {
            "name": "sutraani",
            "data": [item["data"]["upstream_record"] for item in excerpts["sutras"]],
        },
        "dhatu/data.txt": {
            "name": "dhatu",
            "data": [item["data"]["upstream_record"] for item in excerpts["dhatus"]],
        },
        **{f"sutraani/{key}.txt": value for key, value in excerpts["commentaries"].items()},
    }


@pytest.fixture
def fetcher(documents):
    def fetch(url, maximum):
        path = url.split(f"/{SYNTHETIC_REVISION}/", 1)[1]
        return json.dumps(documents[path], ensure_ascii=False).encode("utf-8")

    return fetch


@pytest.fixture
def data_dir(tmp_path, fetcher):
    sync(tmp_path, SYNTHETIC_REVISION, fetcher=fetcher)
    return tmp_path


@pytest.fixture
def form_excerpts():
    return json.loads((Path(__file__).parent / "fixtures/form-excerpts.json").read_text())


@pytest.fixture
def form_documents(documents, form_excerpts):
    documents["dhatu/data.txt"]["data"] = [d["record"] for d in form_excerpts["dhatus"]]
    documents["shabda/data2.txt"] = {
        "name": "shabdapatha_v2",
        "data": [s["record"] for s in form_excerpts["shabdas"]],
    }
    documents.update(form_excerpts["forms"])
    return documents


@pytest.fixture
def form_fetcher(form_documents):
    def fetch(url, maximum):
        path = url.split(f"/{SYNTHETIC_REVISION}/", 1)[1]
        return json.dumps(form_documents[path], ensure_ascii=False).encode("utf-8")

    return fetch


@pytest.fixture
def form_data_dir(tmp_path, form_fetcher):
    directory = tmp_path / "full"
    sync(directory, SYNTHETIC_REVISION, fetcher=form_fetcher, profile="full")
    return directory


@pytest.fixture
def forms(form_data_dir):
    from ashtadhyayi_mcp.adapters import load_active
    from ashtadhyayi_mcp.forms import FormRetrieval

    return FormRetrieval(Retrieval(load_active(form_data_dir)))
