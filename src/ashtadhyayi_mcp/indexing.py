"""Deterministic lexical search; original evidence is never normalized in place."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar

from .domain import DhatuData, Evidence, Match, SearchHit, ShabdaData, SutraData

T = TypeVar("T", SutraData, DhatuData, ShabdaData)
TOKENS = re.compile(r'[\s।॥,;:()\[\]"]+')


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


class SearchIndex(Protocol[T]):
    def search(self, query: str) -> list[SearchHit[T]]: ...


@dataclass(frozen=True)
class Entry:
    field: str
    original: str
    normalized: str
    tokens: frozenset[str]


class LexicalIndex(Generic[T]):
    def __init__(self, records: list[Evidence[T]], fields: tuple[str, ...]) -> None:
        self.records: list[Evidence[T]] = records
        self.entries: list[list[Entry]] = []
        for record in records:
            entries = []
            for field in fields:
                raw = record.data.upstream_record.get(field)
                if not isinstance(raw, str):
                    continue
                values = (
                    [part.split("$", 1)[0] for part in raw.split("##")] if field == "pc" else [raw]
                )
                for value in values:
                    normalized = normalize(value)
                    if normalized:
                        entries.append(
                            Entry(field, value, normalized, frozenset(TOKENS.split(normalized)))
                        )
            self.entries.append(entries)

    def search(self, query: str) -> list[SearchHit[T]]:
        results: list[SearchHit[T]] = []
        for record, entries in zip(self.records, self.entries, strict=True):
            best: dict[str, tuple[Literal[1, 2, 3], Match]] = {}
            for entry in entries:
                score: Literal[1, 2, 3]
                kind: Literal["exact", "token", "substring"]
                if query == entry.normalized:
                    score, kind = 3, "exact"
                elif query in entry.tokens:
                    score, kind = 2, "token"
                elif query in entry.normalized:
                    score, kind = 1, "substring"
                else:
                    continue
                if entry.field in best and best[entry.field][0] >= score:
                    continue
                provenance = record.provenance.model_copy(
                    update={
                        "source_pointer": record.provenance.source_pointer + "/" + entry.field,
                    }
                )
                best[entry.field] = (
                    score,
                    Match(
                        field=entry.field,
                        kind=kind,
                        matched_text=entry.original,
                        provenance=provenance,
                    ),
                )
            if best:
                results.append(
                    SearchHit(
                        record=record,
                        score=max(value[0] for value in best.values()),
                        matches=[value[1] for value in best.values()],
                    )
                )
        # Input records are numerically ordered; stable sorting retains that tie-break.
        results.sort(key=lambda hit: -hit.score)
        return results
