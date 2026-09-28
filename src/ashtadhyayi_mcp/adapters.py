"""Read pinned JSON files, validate identity, and retain source values verbatim."""

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, ValidationError, field_validator

from . import __version__
from .domain import (
    SOURCES,
    DataError,
    DhatuData,
    Digest,
    Evidence,
    Model,
    Provenance,
    Sha,
    ShabdaData,
    Snapshot,
    Source,
    SutraData,
)
from .form_models import SourceCoverageData
from .form_sources import FORM_PATHS

PINNED_REVISION = "5744762f010d677cfb43f347a42d02796cf615d6"
RAW_BASE = "https://raw.githubusercontent.com/ashtadhyayi-com/data"
CATALOGS = ("sutraani/data.txt", "dhatu/data.txt")
PATHS = (*CATALOGS, *(f"sutraani/{source}.txt" for source in SOURCES))
ALL_PATHS = (*PATHS, *FORM_PATHS)
MAX_FILE_BYTES = 32 * 1024 * 1024
LOG = logging.getLogger(__name__)


class FileInfo(Model):
    sha256: Digest
    size: Annotated[int, Field(ge=0, le=MAX_FILE_BYTES)]
    retrieved_at: str

    @field_validator("retrieved_at")
    @classmethod
    def utc_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Expected RFC 3339 UTC timestamp") from exc
        offset = parsed.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("Expected UTC timestamp")
        return value


class Manifest(Model):
    version: Annotated[int, Field(ge=1, le=1)] = 1
    upstream_revision: Sha
    files: dict[str, FileInfo]

    @field_validator("files")
    @classmethod
    def allowlisted_paths(cls, files: dict[str, FileInfo]) -> dict[str, FileInfo]:
        if not set(CATALOGS) <= files.keys() or not files.keys() <= set(ALL_PATHS):
            raise ValueError("Manifest requires both catalogs and only allowlisted sources")
        return files


def decode_json(raw: bytes) -> Any:
    """Reject duplicate keys and nonstandard numeric values rather than dropping data."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"Nonstandard JSON number: {value}")

    result = json.loads(
        raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant
    )

    def validate(value: Any) -> None:
        if isinstance(value, str):
            value.encode("utf-8")  # Reject escaped lone surrogates, preserving valid text.
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        elif isinstance(value, dict):
            for key, item in value.items():
                validate(key)
                validate(item)
        elif isinstance(value, list):
            for item in value:
                validate(item)

    validate(result)
    return result


def canonical_number(value: str) -> str:
    text = value.strip().translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    if not re.fullmatch(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,6}", text):
        raise DataError("INVALID_INPUT", "Use a sūtra number such as 6.1.77 or ६.१.७७")
    a, p, n = map(int, text.split("."))
    if not 1 <= a <= 8 or not 1 <= p <= 4 or n < 1:
        raise DataError("INVALID_INPUT", "Chapter must be 1–8, pāda 1–4, and ordinal positive")
    return f"{a}.{p}.{n}"


@dataclass
class Corpus:
    manifest: Manifest
    sutras: list[Evidence[SutraData]]
    dhatus: list[Evidence[DhatuData]]
    commentaries: dict[Source, dict[str, Any]]
    shabdas: list[Evidence[ShabdaData]] = field(default_factory=list)
    dhatu_forms: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    form_coverage: list[Evidence[SourceCoverageData]] = field(default_factory=list)

    @property
    def snapshot(self) -> Snapshot:
        return Snapshot(
            upstream_revision=self.manifest.upstream_revision,
            adapter_version=__version__,
            loaded_commentary_sources=list(self.commentaries),
            loaded_form_sources=[p for p in FORM_PATHS if p in self.manifest.files],
        )

    def provenance(self, path: str, identifier: str, pointer: str) -> Provenance:
        meta = self.manifest.files[path]
        return Provenance(
            source_path=path,
            source_identifier=identifier,
            source_pointer=pointer,
            upstream_revision=self.manifest.upstream_revision,
            source_sha256=meta.sha256,
            retrieved_at=meta.retrieved_at,
            source_url=f"{RAW_BASE}/{self.manifest.upstream_revision}/{path}",
        )


def _strings(record: Any, fields: tuple[str, ...]) -> None:
    if not isinstance(record, dict) or any(
        not isinstance(record.get(field), str) for field in fields
    ):
        raise ValueError(f"Expected string fields: {', '.join(fields)}")


def parse_corpus(manifest: Manifest, documents: dict[str, Any]) -> Corpus:
    """Pure adapter; pointers always address the original unsorted document."""
    corpus = Corpus(manifest, [], [], {})
    try:
        for path, name in zip(CATALOGS, ("sutraani", "dhatu"), strict=True):
            doc = documents[path]
            if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
                raise ValueError(f"{path}: expected a data array")
            # The catalog name is descriptive; identity comes from validated records.
            if not isinstance(doc.get("name"), str):
                raise ValueError(f"{path}: expected a name string")
            seen: set[str] = set()
            numbers: set[str] = set()
            for index, record in enumerate(doc["data"]):
                _strings(record, ("i",))
                identifier = record["i"]
                if not re.fullmatch(r"[0-9]+", identifier) or identifier in seen:
                    raise ValueError(f"{path}: invalid or duplicate ID")
                seen.add(identifier)
                provenance = corpus.provenance(path, identifier, f"/data/{index}")
                if name == "sutraani":
                    _strings(record, ("a", "p", "n", "s"))
                    number = canonical_number(".".join(record[k] for k in ("a", "p", "n")))
                    a, p, n = map(int, number.split("."))
                    if identifier != f"{a}{p}{n:03d}" or number in numbers:
                        raise ValueError("Inconsistent sūtra ID or duplicate number")
                    numbers.add(number)
                    for field in ("pc", "ss", "e"):
                        if field in record:
                            _strings(record, (field,))
                    corpus.sutras.append(
                        Evidence(
                            data=SutraData(
                                number=number,
                                upstream_id=identifier,
                                text=record["s"],
                                upstream_record=record,
                            ),
                            provenance=provenance,
                        )
                    )
                else:
                    _strings(record, ("baseindex", "dhatu", "aupadeshik"))
                    for field in ("artha", "artha_english", "artha_hindi", "searchterms"):
                        if field in record:
                            _strings(record, (field,))
                    corpus.dhatus.append(
                        Evidence(
                            data=DhatuData(
                                upstream_id=identifier,
                                baseindex=record["baseindex"],
                                text=record["dhatu"],
                                aupadeshik=record["aupadeshik"],
                                upstream_record=record,
                            ),
                            provenance=provenance,
                        )
                    )
            if not seen:
                raise ValueError(f"{path}: empty catalog")
        ids = {s.data.upstream_id for s in corpus.sutras}
        for source in SOURCES:
            path = f"sutraani/{source}.txt"
            if path not in manifest.files:
                continue
            comments = documents[path]
            if not isinstance(comments, dict):
                raise ValueError(f"{path}: expected an ID map")
            for value in comments.values():
                if source == "sutrartha":
                    if not isinstance(value, dict):
                        raise ValueError("sutrartha values must be objects")
                    for field in ("sa", "sd"):
                        if field in value:
                            _strings(value, (field,))
                elif not isinstance(value, str):
                    raise ValueError(f"{path}: expected string values")
            unmatched = set(comments) - ids
            if unmatched:
                LOG.warning("%s has %d unmatched IDs; no sūtras synthesized", path, len(unmatched))
            corpus.commentaries[source] = comments
        corpus.sutras.sort(key=lambda s: tuple(map(int, s.data.number.split("."))))
        corpus.dhatus.sort(key=lambda d: int(d.data.upstream_id))
    except (KeyError, TypeError, ValueError, DataError) as exc:
        raise DataError("UPSTREAM_SCHEMA_ERROR", f"Invalid upstream structure: {exc}") from exc
    from .form_adapter import parse_form_documents

    parse_form_documents(corpus, documents)
    return corpus


def load_snapshot(directory: Path) -> Corpus:
    try:
        manifest = Manifest.model_validate(decode_json((directory / "manifest.json").read_bytes()))
        documents = {}
        for path, info in manifest.files.items():
            file = directory / path
            if file.stat().st_size != info.size:
                raise ValueError(f"Size mismatch: {path}")
            raw = file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != info.sha256:
                raise ValueError(f"Hash mismatch: {path}")
            documents[path] = decode_json(raw)
        return parse_corpus(manifest, documents)
    except OSError as exc:
        raise DataError(
            "DATA_UNAVAILABLE", "Snapshot files unavailable; run the sync command"
        ) from exc
    except (ValueError, ValidationError) as exc:
        raise DataError("UPSTREAM_SCHEMA_ERROR", f"Snapshot validation failed: {exc}") from exc


def load_active(data_dir: Path) -> Corpus:
    try:
        active = (data_dir / "current").read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{40}-[0-9a-f]{32}", active):
            raise DataError("DATA_UNAVAILABLE", "Invalid active snapshot pointer")
        return load_snapshot(data_dir / "snapshots" / active)
    except OSError as exc:
        raise DataError(
            "DATA_UNAVAILABLE", "No snapshot available; run ashtadhyayi-mcp sync"
        ) from exc
