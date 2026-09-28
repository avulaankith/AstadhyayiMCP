"""Bounded form retrieval and ambiguity-preserving reverse lookup."""

from collections.abc import Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

from .domain import DataError, Evidence, SearchPage, ShabdaData, Success
from .form_adapter import decode_form, pointer_part
from .form_models import (
    CoverageInput,
    CoverageResult,
    DhatuFormsInput,
    FormCoverage,
    FormData,
    FormLookupInput,
    FormLookupResult,
    FormMatch,
    FormsResult,
    ShabdaFormsInput,
    ShabdaInput,
    ShabdaResult,
    ShabdaSearchInput,
)
from .form_sources import FORM_SOURCES, SHABDA_PATH, FormSource
from .indexing import LexicalIndex, normalize

if TYPE_CHECKING:
    from .services import Retrieval


def page_next(total: int, offset: int, limit: int) -> int | None:
    return offset + limit if offset + limit < total else None


class FormRetrieval:
    def __init__(self, retrieval: "Retrieval") -> None:
        self.retrieval = retrieval
        self.corpus = retrieval.corpus
        self.shabda_index = LexicalIndex(
            self.corpus.shabdas, ("word", "artha", "artha_eng", "artha_hin")
        )
        self.shabda_ids = {s.data.upstream_id: s for s in self.corpus.shabdas}
        self.shabda_words: dict[str, list[Evidence[ShabdaData]]] = {}
        for record in self.corpus.shabdas:
            self.shabda_words.setdefault(normalize(record.data.text), []).append(record)
        self.roots_by_base: dict[str, list[str]] = {}
        for root in self.corpus.dhatus:
            self.roots_by_base.setdefault(root.data.baseindex, []).append(root.data.upstream_id)
        # Bound cached reverse-query pages. Never store a giant per-surface inverted index.
        self._lookup_cached = lru_cache(maxsize=16)(self._lookup)

    def _require(self, paths: list[str]) -> None:
        if not any(path in self.corpus.manifest.files for path in paths):
            raise DataError("SOURCE_NOT_LOADED", "Form sources not loaded; run sync --profile full")

    def _shabdas(self, args: ShabdaInput) -> list[Evidence[ShabdaData]]:
        self._require([SHABDA_PATH])
        if args.by == "upstream_id":
            record = self.shabda_ids.get(args.query.strip())
            records = [record] if record is not None else []
        else:
            records = self.shabda_words.get(normalize(args.query), [])
        if args.linga is not None:
            records = [record for record in records if record.data.linga == args.linga]
        if not records:
            raise DataError("NOT_FOUND", "No matching śabda in this snapshot")
        return records

    def get_shabda(self, args: ShabdaInput) -> Success[ShabdaResult]:
        records = self._shabdas(args)
        return self.retrieval.success(
            ShabdaResult(
                query=args.query,
                total=len(records),
                offset=args.offset,
                limit=args.limit,
                next_offset=page_next(len(records), args.offset, args.limit),
                matches=records[args.offset : args.offset + args.limit],
            )
        )

    def search_shabdas(self, args: ShabdaSearchInput) -> Success[SearchPage[ShabdaData]]:
        self._require([SHABDA_PATH])
        query = normalize(args.query)
        hits = self.shabda_index.search(query)
        if args.linga is not None:
            hits = [h for h in hits if h.record.data.linga == args.linga]
        return self.retrieval.success(
            SearchPage(
                query=args.query,
                normalized_query=query,
                total=len(hits),
                offset=args.offset,
                limit=args.limit,
                next_offset=page_next(len(hits), args.offset, args.limit),
                results=hits[args.offset : args.offset + args.limit],
            )
        )

    @staticmethod
    def _selected(source: FormSource, args: DhatuFormsInput) -> bool:
        if source.category == "subanta":
            return False
        if any(
            value is not None and value != getattr(source, name)
            for name, value in (
                ("category", args.category),
                ("derivation", args.derivation),
                ("prayoga", args.prayoga),
                ("family", args.family),
            )
        ):
            return False
        if args.pratyaya is not None and source.category != "krdanta":
            return False
        if any(x is not None for x in (args.pada, args.lakara, args.purusha, args.vacana)):
            return source.category == "tinanta"
        return True

    def get_dhatu_forms(self, args: DhatuFormsInput) -> Success[FormsResult]:
        selected = [s for s in FORM_SOURCES if self._selected(s, args)]
        self._require([s.path for s in selected])
        query = normalize(args.query) if args.by == "text" else args.query.strip()
        roots = self.retrieval.dhatu_lookup[args.by].get(query, [])
        if not roots:
            raise DataError("NOT_FOUND", "No matching dhātu in this snapshot")
        rows: list[Evidence[FormData]] = []
        coverage: list[FormCoverage] = []
        total = 0
        for root in roots:
            base, identifier = root.data.baseindex, root.data.upstream_id
            for source in selected:
                path = source.path
                loaded = path in self.corpus.dhatu_forms
                fields = self.corpus.dhatu_forms.get(path, {}).get(base)
                coverage.append(
                    FormCoverage(
                        lemma_id=identifier,
                        source_path=path,
                        source_identifier=base,
                        status="not_loaded"
                        if not loaded
                        else "absent"
                        if fields is None
                        else "present"
                        if any(fields.values())
                        else "empty",
                        available_keys=sorted(fields) if fields else [],
                        provenance=self.corpus.provenance(path, base, "/" + pointer_part(base))
                        if fields is not None
                        else None,
                    )
                )
                for key, raw in (fields or {}).items():
                    if source.category == "tinanta":
                        if args.pada and key[0] != args.pada.lower():
                            continue
                        if args.lakara and key[1:] != args.lakara:
                            continue
                    elif args.pratyaya is not None and normalize(key) != normalize(args.pratyaya):
                        continue
                    # Page paradigms; preserve all variants inside each selected row.
                    if args.offset <= total < args.offset + args.limit:
                        data = decode_form(source, identifier, base, key, raw)
                        data.cells = [
                            c
                            for c in data.cells
                            if (args.purusha is None or c.purusha == args.purusha)
                            and (args.vacana is None or c.vacana == args.vacana)
                        ]
                        rows.append(
                            Evidence(
                                data=data,
                                provenance=self.corpus.provenance(
                                    path,
                                    base,
                                    f"/{pointer_part(base)}/{pointer_part(key)}",
                                ),
                            )
                        )
                    total += 1
        return self.retrieval.success(
            FormsResult(
                query=args.query,
                matched_lemma_ids=[r.data.upstream_id for r in roots],
                total=total,
                offset=args.offset,
                limit=args.limit,
                next_offset=page_next(total, args.offset, args.limit),
                results=rows,
                coverage=coverage,
            )
        )

    def get_shabda_forms(self, args: ShabdaFormsInput) -> Success[FormsResult]:
        records = self._shabdas(args)
        source = next(s for s in FORM_SOURCES if s.path == SHABDA_PATH)
        rows = []
        coverage = []
        for record in records:
            raw = str(record.data.upstream_record["forms"])
            coverage.append(
                FormCoverage(
                    lemma_id=record.data.upstream_id,
                    source_path=SHABDA_PATH,
                    source_identifier=record.data.upstream_id,
                    available_keys=["forms"],
                    status="present" if raw.replace(";", "").strip("- ") else "empty",
                    provenance=record.provenance.model_copy(
                        update={
                            "source_pointer": record.provenance.source_pointer + "/forms",
                        }
                    ),
                )
            )
        for record in records[args.offset : args.offset + args.limit]:
            data = decode_form(
                source,
                record.data.upstream_id,
                None,
                "forms",
                str(record.data.upstream_record["forms"]),
                record.data.linga,
            )
            data.cells = [
                c
                for c in data.cells
                if (args.vibhakti is None or c.vibhakti == args.vibhakti)
                and (args.vacana is None or c.vacana == args.vacana)
            ]
            rows.append(
                Evidence(
                    data=data,
                    provenance=record.provenance.model_copy(
                        update={
                            "source_pointer": record.provenance.source_pointer + "/forms",
                        }
                    ),
                )
            )
        return self.retrieval.success(
            FormsResult(
                query=args.query,
                matched_lemma_ids=[s.data.upstream_id for s in records],
                total=len(records),
                offset=args.offset,
                limit=args.limit,
                next_offset=page_next(len(records), args.offset, args.limit),
                results=rows,
                coverage=coverage,
            )
        )

    def _candidates(
        self, source: FormSource, query: str
    ) -> Iterator[tuple[str | None, str | None, str, str, str, str | None]]:
        """Cheap normalized substring gate; exact variant checks follow decoding."""
        if source.path == SHABDA_PATH:
            for record in self.corpus.shabdas:
                raw = str(record.data.upstream_record["forms"])
                if query in normalize(raw):
                    yield (
                        record.data.upstream_id,
                        None,
                        "forms",
                        raw,
                        record.provenance.source_pointer + "/forms",
                        record.data.linga,
                    )
        else:
            for base, row in self.corpus.dhatu_forms.get(source.path, {}).items():
                for key, raw in row.items():
                    if query in normalize(raw):
                        for identifier in self.roots_by_base.get(base, [None]):
                            yield (
                                identifier,
                                base,
                                key,
                                raw,
                                f"/{pointer_part(base)}/{pointer_part(key)}",
                                None,
                            )

    def _lookup(
        self, query: str, kind: str, aliases: bool, offset: int, limit: int
    ) -> FormLookupResult:
        selected = [
            s
            for s in FORM_SOURCES
            if kind == "all" or (s.category == "subanta") == (kind == "shabda")
        ]
        self._require([s.path for s in selected])
        loaded = [s for s in selected if s.path in self.corpus.manifest.files]
        results: list[Evidence[FormMatch]] = []
        total = 0
        for source in loaded:
            for identifier, base, key, raw, pointer, linga in self._candidates(source, query):
                data = decode_form(source, identifier, base, key, raw, linga)
                for cell in data.cells:
                    for variant in cell.variants:
                        normalized = normalize(variant)
                        match: Literal["normalized_exact", "vocative_particle_removed"]
                        if normalized == query:
                            match = "normalized_exact"
                        elif (
                            aliases
                            and cell.vibhakti == 8
                            and normalized.startswith("हे ")
                            and normalized[3:] == query
                        ):
                            match = "vocative_particle_removed"
                        else:
                            continue
                        if offset <= total < offset + limit:
                            results.append(
                                Evidence(
                                    data=FormMatch(
                                        lemma_id=identifier,
                                        baseindex=base,
                                        source_family=source.family,
                                        category=source.category,
                                        derivation=source.derivation,
                                        prayoga=source.prayoga,
                                        source_key=key,
                                        pada=data.pada,
                                        lakara=data.lakara,
                                        pratyaya=data.pratyaya,
                                        cell=cell,
                                        matched_variant=variant,
                                        match_kind=match,
                                        parse_status=data.parse_status,
                                    ),
                                    provenance=self.corpus.provenance(
                                        source.path,
                                        base or identifier or key,
                                        pointer,
                                    ),
                                )
                            )
                        total += 1
        return FormLookupResult(
            query=query,
            normalized_query=query,
            total=total,
            offset=offset,
            limit=limit,
            next_offset=page_next(total, offset, limit),
            results=results,
            searched_sources=[s.path for s in loaded],
            missing_sources=[s.path for s in selected if s not in loaded],
            unparsed_groups=sum(
                s.data.unparsed_groups
                for s in self.corpus.form_coverage
                if s.data.source_path in {p.path for p in loaded}
            ),
        )

    def lookup_form(self, args: FormLookupInput) -> Success[FormLookupResult]:
        page = self._lookup_cached(
            normalize(args.query), args.kind, args.include_vocative_alias, args.offset, args.limit
        )
        # Avoid mutating cached pages when echoing the caller's original query.
        return self.retrieval.success(page.model_copy(update={"query": args.query}))

    def get_form_coverage(self, args: CoverageInput) -> Success[CoverageResult]:
        return self.retrieval.success(
            CoverageResult(
                sources=self.corpus.form_coverage,
                missing_sources=[
                    s.path for s in FORM_SOURCES if s.path not in self.corpus.manifest.files
                ],
            )
        )
