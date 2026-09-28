"""Validated wire contracts, independent of MCP and upstream I/O."""

from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

Source = Literal["sutrartha", "sutrartha_english", "kashika"]
SOURCES: tuple[Source, ...] = ("sutrartha", "sutrartha_english", "kashika")
JsonObject = dict[str, JsonValue]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Nonnegative = Annotated[int, Field(ge=0)]
Query = Annotated[str, Field(min_length=1, max_length=256)]
Number = Annotated[str, Field(min_length=1, max_length=32)]
T = TypeVar("T")
ErrorCode = Literal[
    "INVALID_INPUT",
    "NOT_FOUND",
    "DATA_UNAVAILABLE",
    "SOURCE_NOT_LOADED",
    "UPSTREAM_SCHEMA_ERROR",
]


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_serialization_defaults_required=True,
    )


class Provenance(Model):
    provider: Literal["ashtadhyayi-com"] = "ashtadhyayi-com"
    repository: Literal["https://github.com/ashtadhyayi-com/data"] = (
        "https://github.com/ashtadhyayi-com/data"
    )
    source_path: str
    source_identifier: str
    source_pointer: str
    upstream_revision: Sha
    source_sha256: Digest
    retrieved_at: str
    source_url: str


class Evidence(Model, Generic[T]):
    data: T
    provenance: Provenance


class SutraData(Model):
    number: Annotated[str, Field(pattern=r"^[1-8]\.[1-4]\.[1-9][0-9]*$")]
    upstream_id: str
    text: str
    upstream_record: JsonObject


class DhatuData(Model):
    upstream_id: str
    baseindex: str
    text: str
    aupadeshik: str
    upstream_record: JsonObject


class ShabdaData(Model):
    upstream_id: str
    text: str
    linga: str
    upstream_record: JsonObject


class CommentaryData(Model):
    source: Source
    field: Literal["sa", "sd", "text"]
    text: str
    format: Literal["upstream-markup"] = "upstream-markup"
    offset: Nonnegative
    total_characters: Nonnegative
    next_offset: Nonnegative | None


class Coverage(Model):
    source: Source
    field: Literal["sa", "sd", "text"]
    status: Literal["present", "empty", "absent"]
    provenance: Provenance | None


class Snapshot(Model):
    upstream_revision: Sha
    adapter_version: str
    loaded_commentary_sources: list[Source]
    loaded_form_sources: list[str] = Field(default_factory=list)


class Error(Model):
    code: ErrorCode
    message: str
    details: JsonObject = Field(default_factory=dict)


class Failure(Model):
    status: Literal["error"] = "error"
    error: Error


class Success(Model, Generic[T]):
    status: Literal["ok"] = "ok"
    snapshot: Snapshot
    data: T


class SutraResult(Model):
    sutra: Evidence[SutraData]
    commentaries: list[Evidence[CommentaryData]]
    coverage: list[Coverage]


class ContextResult(Model):
    requested: Evidence[SutraData]
    preceding: list[Evidence[SutraData]]
    following: list[Evidence[SutraData]]
    ordering: Literal["numeric-a-p-n"] = "numeric-a-p-n"
    relationship: Literal["corpus-adjacency"] = "corpus-adjacency"
    contextual_metadata: Evidence[JsonObject]


class Match(Model):
    field: str
    kind: Literal["exact", "token", "substring"]
    matched_text: str
    provenance: Provenance


class SearchHit(Model, Generic[T]):
    record: Evidence[T]
    score: Literal[1, 2, 3]
    matches: Annotated[list[Match], Field(min_length=1)]


class SearchPage(Model, Generic[T]):
    query: str
    normalized_query: str
    algorithm: Literal["lexical-v1"] = "lexical-v1"
    total: Nonnegative
    offset: Nonnegative
    limit: Annotated[int, Field(ge=1)]
    next_offset: Nonnegative | None
    results: list[SearchHit[T]]


class DhatuResult(Model):
    query: str
    by: Literal["text", "upstream_id", "baseindex"]
    total: Annotated[int, Field(ge=1)]
    offset: Nonnegative
    limit: Annotated[int, Field(ge=1)]
    next_offset: Nonnegative | None
    matches: list[Evidence[DhatuData]]


class SutraInput(Model):
    number: Number
    commentaries: Annotated[
        list[Source],
        Field(
            max_length=3,
            json_schema_extra={
                "uniqueItems": True,
            },
        ),
    ] = Field(
        default_factory=lambda: list(SOURCES),
        json_schema_extra={
            "uniqueItems": True,
            "default": list(SOURCES),
        },
    )
    commentary_offset: Nonnegative = 0
    commentary_limit: Annotated[int, Field(ge=1, le=8000)] = 2000

    @field_validator("commentaries")
    @classmethod
    def unique_sources(cls, value: list[Source]) -> list[Source]:
        if len(value) != len(set(value)):
            raise ValueError("Commentary sources must be unique")
        return value


class SearchInput(Model):
    query: Query
    limit: Annotated[int, Field(ge=1, le=50)] = 10
    offset: Nonnegative = 0

    @field_validator("query")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain non-whitespace text")
        return value


class ContextInput(Model):
    number: Number
    before: Annotated[int, Field(ge=0, le=5)] = 2
    after: Annotated[int, Field(ge=0, le=5)] = 2


class DhatuInput(SearchInput):
    by: Literal["text", "upstream_id", "baseindex"] = "text"
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class DataError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.error = Error(code=code, message=message)
        super().__init__(message)
