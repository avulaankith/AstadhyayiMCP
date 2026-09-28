"""Form retrieval contracts: raw evidence and explicitly decoded table coordinates."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .domain import DhatuInput, Evidence, Model, Nonnegative, Provenance, SearchInput, ShabdaData
from .form_sources import Category, Derivation, Family, Lakara, Prayoga

Purusha = Literal["prathama", "madhyama", "uttama"]
Linga = Literal["P", "S", "N", "A"]


class ShabdaInput(SearchInput):
    by: Literal["text", "upstream_id"] = "text"
    linga: Linga | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class ShabdaSearchInput(SearchInput):
    linga: Linga | None = None


class ShabdaResult(Model):
    query: str
    total: Annotated[int, Field(ge=1)]
    offset: Nonnegative
    limit: Annotated[int, Field(ge=1)]
    next_offset: Nonnegative | None
    matches: list[Evidence[ShabdaData]]


class DhatuFormsInput(DhatuInput):
    category: Literal["tinanta", "krdanta"] | None = None
    derivation: Derivation | None = None
    prayoga: Prayoga | None = None
    family: Literal["vidyut", "upstream"] | None = None
    pada: Literal["P", "A"] | None = None
    lakara: Lakara | None = None
    pratyaya: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    purusha: Purusha | None = None
    vacana: Annotated[int, Field(ge=1, le=3)] | None = None

    @model_validator(mode="after")
    def compatible(self) -> "DhatuFormsInput":
        finite = any(
            v is not None for v in (self.prayoga, self.pada, self.lakara, self.purusha, self.vacana)
        )
        if self.pratyaya is not None and not self.pratyaya.strip():
            raise ValueError("Pratyaya cannot be blank")
        if (
            self.category == "krdanta" or self.pratyaya is not None or self.family == "upstream"
        ) and finite:
            raise ValueError("Finite-verb filters cannot be combined with krdanta filters")
        if self.category == "tinanta" and (self.pratyaya is not None or self.family == "upstream"):
            raise ValueError("Tinanta filters cannot select the upstream krdanta collection")
        if self.family == "upstream" and self.derivation is not None:
            raise ValueError("The upstream krdanta file does not encode a derivation label")
        return self


class ShabdaFormsInput(ShabdaInput):
    vibhakti: Annotated[int, Field(ge=1, le=8)] | None = None
    vacana: Annotated[int, Field(ge=1, le=3)] | None = None


class FormLookupInput(SearchInput):
    kind: Literal["dhatu", "shabda", "all"] = "all"
    include_vocative_alias: bool = True


class CoverageInput(Model):
    pass


class FormCell(Model):
    group_index: Nonnegative
    slot_index: Nonnegative
    raw_text: str
    variants: list[str]
    purusha: Purusha | None = None
    vacana: Annotated[int, Field(ge=1, le=3)] | None = None
    vibhakti: Annotated[int, Field(ge=1, le=8)] | None = None
    linga: Linga | None = None
    role: Literal[
        "finite", "declined", "stem_or_indeclinable", "gender_form", "unspecified", "unparsed"
    ]


class FormData(Model):
    lemma_id: str | None
    baseindex: str | None
    source_family: Family
    category: Category
    derivation: Derivation | None
    prayoga: Prayoga | None
    source_key: str
    pada: Literal["P", "A"] | None
    lakara: str | None
    pratyaya: str | None
    raw_text: str
    cells: list[FormCell]
    parse_status: Literal["decoded", "partial", "unparsed"]
    warnings: list[str]


class FormCoverage(Model):
    lemma_id: str
    source_path: str
    status: Literal["present", "empty", "absent", "not_loaded"]
    source_identifier: str
    available_keys: list[str]
    # None for absent/unloaded entries; scope is always this snapshot.
    provenance: Provenance | None


class FormsResult(Model):
    query: str
    matched_lemma_ids: list[str]
    total: Nonnegative
    offset: Nonnegative
    limit: Annotated[int, Field(ge=1)]
    next_offset: Nonnegative | None
    results: list[Evidence[FormData]]
    coverage: list[FormCoverage]
    exhaustive: Literal[False] = False
    scope: Literal["stored-upstream-paradigms"] = "stored-upstream-paradigms"


class FormMatch(Model):
    lemma_id: str | None
    baseindex: str | None
    source_family: Family
    category: Category
    derivation: Derivation | None
    prayoga: Prayoga | None
    source_key: str
    pada: Literal["P", "A"] | None
    lakara: str | None
    pratyaya: str | None
    cell: FormCell
    matched_variant: str
    match_kind: Literal["normalized_exact", "vocative_particle_removed"]
    parse_status: Literal["decoded", "partial", "unparsed"]


class FormLookupResult(Model):
    query: str
    normalized_query: str
    total: Nonnegative
    offset: Nonnegative
    limit: Annotated[int, Field(ge=1)]
    next_offset: Nonnegative | None
    results: list[Evidence[FormMatch]]
    searched_sources: list[str]
    missing_sources: list[str]
    unparsed_groups: Nonnegative
    exhaustive: Literal[False] = False
    interpretation: str = (
        "Matches are stored form occurrences, not context-resolved analyses. "
        "No match does not establish invalidity; sandhi and generation are not performed."
    )


class SourceCoverageData(Model):
    source_path: str
    family: Family
    category: Category
    derivation: Derivation | None
    prayoga: Prayoga | None
    records: Nonnegative
    paradigm_fields: Nonnegative
    unparsed_groups: Nonnegative
    unlinked_identifiers: list[str]
    available_keys: list[str]


class CoverageResult(Model):
    sources: list[Evidence[SourceCoverageData]]
    missing_sources: list[str]
    exhaustive: Literal[False] = False
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Coverage is limited to the loaded upstream files, not all possible Sanskrit words.",
            "Vidyut-labelled files contain precomputed outputs, not independently attested forms.",
            "No runtime generation, arbitrary prefix composition, compound derivation, sandhi "
            "validation or śloka anvaya is performed.",
            "Empty slots and absent paradigms do not establish grammatical invalidity.",
            "Malformed groups remain retrievable as raw text without inferred grammatical labels.",
        ]
    )
