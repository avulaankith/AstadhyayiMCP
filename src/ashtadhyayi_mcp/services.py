"""Retrieval and query semantics; contains no MCP transport code."""

from typing import Literal, TypeVar

from .adapters import Corpus, canonical_number
from .domain import (
    CommentaryData,
    ContextInput,
    ContextResult,
    Coverage,
    DataError,
    DhatuData,
    DhatuInput,
    DhatuResult,
    Evidence,
    SearchInput,
    SearchPage,
    Success,
    SutraData,
    SutraInput,
    SutraResult,
)
from .indexing import LexicalIndex, SearchIndex, normalize

T = TypeVar("T")
R = TypeVar("R", SutraData, DhatuData)


def next_offset(total: int, offset: int, limit: int) -> int | None:
    return offset + limit if offset + limit < total else None


class Retrieval:
    def __init__(self, corpus: Corpus) -> None:
        self.corpus = corpus
        self.sutras = {s.data.number: s for s in corpus.sutras}
        self.positions = {s.data.number: i for i, s in enumerate(corpus.sutras)}
        self.sutra_index: SearchIndex[SutraData] = LexicalIndex(
            corpus.sutras,
            ("s", "pc", "ss", "e"),
        )
        self.dhatu_index: SearchIndex[DhatuData] = LexicalIndex(
            corpus.dhatus,
            ("dhatu", "aupadeshik", "artha", "artha_english", "artha_hindi", "searchterms"),
        )
        self.dhatu_lookup: dict[str, dict[str, list[Evidence[DhatuData]]]] = {
            "text": {},
            "baseindex": {},
            "upstream_id": {},
        }
        for record in corpus.dhatus:
            for by, values in (
                ("text", {normalize(record.data.text), normalize(record.data.aupadeshik)}),
                ("baseindex", {record.data.baseindex}),
                ("upstream_id", {record.data.upstream_id}),
            ):
                for value in values:
                    self.dhatu_lookup[by].setdefault(value, []).append(record)

    def success(self, data: T) -> Success[T]:
        return Success(snapshot=self.corpus.snapshot, data=data)

    def _sutra(self, number: str) -> Evidence[SutraData]:
        canonical = canonical_number(number)
        if canonical not in self.sutras:
            raise DataError("NOT_FOUND", f"Sūtra {canonical} is absent from this snapshot")
        return self.sutras[canonical]

    def get_sutra(self, args: SutraInput) -> Success[SutraResult]:
        sutra = self._sutra(args.number)
        identifier = sutra.data.upstream_id
        chunks: list[Evidence[CommentaryData]] = []
        coverage: list[Coverage] = []
        for source in args.commentaries:
            if source not in self.corpus.commentaries:
                raise DataError("SOURCE_NOT_LOADED", f"Commentary source {source} is not loaded")
            values = self.corpus.commentaries[source]
            fields: tuple[Literal["sa", "sd", "text"], ...] = (
                ("sa", "sd") if source == "sutrartha" else ("text",)
            )
            for field in fields:
                pointer = f"/{identifier}" + (f"/{field}" if field != "text" else "")
                raw = values.get(identifier)
                text = raw.get(field) if source == "sutrartha" and raw is not None else raw
                provenance = (
                    self.corpus.provenance(
                        f"sutraani/{source}.txt",
                        identifier,
                        pointer,
                    )
                    if text is not None
                    else None
                )
                coverage.append(
                    Coverage(
                        source=source,
                        field=field,
                        status="absent" if text is None else "present" if text else "empty",
                        provenance=provenance,
                    )
                )
                if not text or provenance is None:
                    continue
                offset = min(args.commentary_offset, len(text))
                chunks.append(
                    Evidence(
                        data=CommentaryData(
                            source=source,
                            field=field,
                            text=text[offset : offset + args.commentary_limit],
                            offset=offset,
                            total_characters=len(text),
                            next_offset=next_offset(len(text), offset, args.commentary_limit),
                        ),
                        provenance=provenance,
                    )
                )
        return self.success(SutraResult(sutra=sutra, commentaries=chunks, coverage=coverage))

    def get_sutra_context(self, args: ContextInput) -> Success[ContextResult]:
        sutra = self._sutra(args.number)
        position = self.positions[sutra.data.number]
        record = sutra.data.upstream_record
        return self.success(
            ContextResult(
                requested=sutra,
                preceding=self.corpus.sutras[max(0, position - args.before) : position],
                following=self.corpus.sutras[position + 1 : position + 1 + args.after],
                contextual_metadata=Evidence(
                    data={
                        key: record[key]
                        for key in ("an", "ad", "pc", "ss", "type")
                        if key in record
                    },
                    provenance=sutra.provenance,
                ),
            )
        )

    def get_dhatu(self, args: DhatuInput) -> Success[DhatuResult]:
        query = normalize(args.query) if args.by == "text" else args.query.strip()
        records = self.dhatu_lookup[args.by].get(query, [])
        if not records:
            raise DataError("NOT_FOUND", "No matching dhātu in this snapshot")
        return self.success(
            DhatuResult(
                query=args.query,
                by=args.by,
                total=len(records),
                offset=args.offset,
                limit=args.limit,
                next_offset=next_offset(len(records), args.offset, args.limit),
                matches=records[args.offset : args.offset + args.limit],
            )
        )

    def _search(self, args: SearchInput, index: SearchIndex[R]) -> Success[SearchPage[R]]:
        query = normalize(args.query)
        hits = index.search(query)
        return self.success(
            SearchPage(
                query=args.query,
                normalized_query=query,
                total=len(hits),
                offset=args.offset,
                limit=args.limit,
                next_offset=next_offset(len(hits), args.offset, args.limit),
                results=hits[args.offset : args.offset + args.limit],
            )
        )

    def search_sutras(self, args: SearchInput) -> Success[SearchPage[SutraData]]:
        return self._search(args, self.sutra_index)

    def search_dhatus(self, args: SearchInput) -> Success[SearchPage[DhatuData]]:
        return self._search(args, self.dhatu_index)
