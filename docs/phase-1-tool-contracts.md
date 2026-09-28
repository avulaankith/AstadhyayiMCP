# Phase-1 tool contracts

Status: implemented in version 0.1.0 after architecture approval. See [research](stage-1-research.md) for verified field mappings and [ADR](adr/001-python-local-snapshots.md) for the SDK choice. Pydantic-generated live schemas are published by MCP `tools/list`.

Version 0.2.0 adds six [śabda and form tools](forms.md), bringing the total to eleven.
The five original contracts below remain supported.

## Common rules

Inputs below are JSON Schema objects. Unknown parameters are rejected. Defaults are applied by the service, not merely documented in JSON Schema. Strings have Unicode-code-point limits. Reject whitespace-only queries. Sūtra input accepts ASCII or Devanāgarī digits separated by ASCII dots, trims surrounding whitespace, and maps digits deterministically to canonical unpadded ASCII coordinates. Check chapter 1–8, pāda 1–4, positive sūtra ordinal; syntactic validity does not imply corpus membership.

Outputs use the algebraic contracts below. All declared object fields are required in serialized output, nullable fields explicitly include `null`, and objects reject undeclared fields except `JsonObject` source records. Arrays can be empty unless otherwise specified. `JsonValue` means any valid JSON value, including nested objects/arrays; non-finite numbers are rejected on import. These contracts are Pydantic models and generated MCP output schemas.

```text
JsonObject = map<string, JsonValue>
Timestamp = RFC 3339 UTC string
SutraNumber = ASCII string matching ^[1-8]\.[1-4]\.[1-9][0-9]*$
Source = "sutrartha" | "sutrartha_english" | "kashika"

Provenance = {
  provider: "ashtadhyayi-com",
  repository: "https://github.com/ashtadhyayi-com/data",
  source_path: string,
  source_identifier: string,
  source_pointer: string,          // RFC 6901 JSON Pointer into original document
  upstream_revision: string,      // 40 lowercase hex commit SHA
  source_sha256: string,          // 64 lowercase hex; original full-file bytes
  retrieved_at: Timestamp,        // actual snapshot download time
  source_url: string              // immutable raw.githubusercontent.com URL
}

Evidence<T> = { data: T, provenance: Provenance }

SutraData = {
  number: SutraNumber,            // derived from source a, p, n
  upstream_id: string,            // source i
  text: string,                  // exact source s
  upstream_record: JsonObject     // complete original record, unchanged
}

DhatuData = {
  upstream_id: string,            // source i
  baseindex: string,              // source baseindex, padding retained
  text: string,                   // source dhatu
  aupadeshik: string,             // source aupadeshik
  upstream_record: JsonObject     // complete original record, unchanged
}

CommentaryChunk = Evidence<{
  source: Source,
  field: "sa" | "sd" | "text",
  text: string,                  // exact slice of original source string
  format: "upstream-markup",
  offset: integer >= 0,          // Unicode code points, not bytes or UTF-16 units
  total_characters: integer >= 0,
  next_offset: integer >= 0 | null
}>

Coverage = {
  source: Source,
  field: "sa" | "sd" | "text",
  status: "present" | "empty" | "absent",
  provenance: Provenance | null
}

Snapshot = {
  upstream_revision: string,     // same pinned commit for all results
  adapter_version: string,
  loaded_commentary_sources: Source[],
  loaded_form_sources: string[]  // source paths; added in 0.2.0
}

Error = {
  code: "INVALID_INPUT" | "NOT_FOUND" | "DATA_UNAVAILABLE" |
        "SOURCE_NOT_LOADED" | "UPSTREAM_SCHEMA_ERROR",
  message: string,
  details: JsonObject
}

Result<T> =
  { status: "ok", snapshot: Snapshot, data: T }
  | { status: "error", error: Error }
```

`Coverage.provenance` is present for existing values, including empty strings, and null for absent values. An absence claim is scoped to this snapshot, source and field; it does not claim that scholarship elsewhere lacks an explanation. A failed download is a snapshot error, not empty commentary. Missing configured files prevent snapshot activation.

Each fragment's pointer resolves to the full original string; `offset`/`total_characters` specify its returned slice. `field="text"` identifies a direct string map value, not an upstream JSON key. Language and author are not inferred from fragment content. Source labels and the notices document provide attribution scope.

## get_sutra

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["number"],
  "properties": {
    "number": {"type": "string", "minLength": 1, "maxLength": 32},
    "commentaries": {
      "type": "array", "uniqueItems": true, "maxItems": 3,
      "items": {"enum": ["sutrartha", "sutrartha_english", "kashika"]},
      "default": ["sutrartha", "sutrartha_english", "kashika"]
    },
    "commentary_offset": {"type": "integer", "minimum": 0, "default": 0},
    "commentary_limit": {"type": "integer", "minimum": 1, "maximum": 8000, "default": 2000}
  }
}
```

Output: `Result<{sutra: Evidence<SutraData>, commentaries: CommentaryChunk[], coverage: Coverage[]}>`.

Return the sūtra even if an individual commentary field is empty or absent. `commentaries: []` requests catalog-only retrieval and yields empty commentary and coverage arrays. Otherwise return coverage for the two `sutrartha` fields and each selected direct-string source. Produce chunks only for nonempty fields. Apply `commentary_offset` and `commentary_limit` independently to each selected string. When offset exceeds a string's length, return an empty slice at offset equal to its length with `next_offset=null`; other longer fields can still have another page. Use each fragment's `next_offset` to request more. This intentionally simple contract may repeat shorter-field empty slices but never silently drops text.

At the inspected revision the longest combined default commentary is 37,538 code points, so explicit pagination is preferable to returning an unbounded wall of text. Chunk boundaries preserve code points; joining consecutive chunks reconstructs the exact original string. Clients should join chunks before display if a boundary separates combining marks.

Example: `{"number":"6.1.77"}`. Expected source `text`: `इको यणचि`. Catalog provenance points to `sutraani/data.txt`, ID `61077`, `/data/2516`; commentary provenance points to its separate file and `/61077/sa`, `/61077/sd`, or `/61077`.

## search_sutras

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["query"],
  "properties": {
    "query": {"type": "string", "minLength": 1, "maxLength": 256},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    "offset": {"type": "integer", "minimum": 0, "default": 0}
  }
}
```

```text
Match = {
  field: string,                 // source field: s, pc, ss, e, etc.
  kind: "exact" | "token" | "substring",
  matched_text: string,          // original field / pc lexical segment
  provenance: Provenance        // pointer to actual source field
}

SearchHit<T> = {
  record: Evidence<T>,
  score: 1 | 2 | 3,              // deterministic ranking, never confidence
  matches: Match[]               // at least one; retain each matching field
}

SearchPage<T> = {
  query: string,                 // exact caller string
  normalized_query: string,
  algorithm: "lexical-v1",
  total: integer >= 0,
  offset: integer >= 0,
  limit: integer >= 1,
  next_offset: integer >= 0 | null,
  results: SearchHit<T>[]
}
```

Output: `Result<SearchPage<SutraData>>`. No commentary bodies in search results. Index `s`, lexical segments of `pc`, `ss`, `e`. On search copies apply NFC and collapse Unicode whitespace to a single space, trim ends, and preserve all other characters. Token boundaries are whitespace plus `।`, `॥`, comma, semicolon, colon, parentheses, square brackets, and double quotes; do not split combining marks or avagraha. An exact full query match ranks 3, exact token match ranks 2, literal substring ranks 1. Choose the best kind per field and highest score per record. Sort descending score then numeric `(a,p,n)`. No stemming, case folding, accent removal, or cross-token AND matching. Numeric identifiers belong to `get_sutra`.

Example: `{"query":"यण्"}` includes 6.1.77 based on the source `pc`/`ss`, with matching field provenance. Empty results are success with `total=0`. Offset beyond the end yields an empty page.

## get_sutra_context

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["number"],
  "properties": {
    "number": {"type": "string", "minLength": 1, "maxLength": 32},
    "before": {"type": "integer", "minimum": 0, "maximum": 5, "default": 2},
    "after": {"type": "integer", "minimum": 0, "maximum": 5, "default": 2}
  }
}
```

Output:

```text
Result<{
  requested: Evidence<SutraData>,
  preceding: Evidence<SutraData>[],
  following: Evidence<SutraData>[],
  ordering: "numeric-a-p-n",
  relationship: "corpus-adjacency",
  contextual_metadata: Evidence<JsonObject>
}>
```

Neighbors are catalog records in ascending numerical order; `preceding` lists oldest-to-nearest. Return fewer at corpus boundaries, never fabricate missing numbers. Chapter boundaries do not stop traversal. `contextual_metadata.data` is exactly the existing subset of `an`, `ad`, `pc`, `ss`, `type` from the requested record; provenance identifies that source record. No parsed semantic graph or inferred adhikāra is returned. No commentary bodies in this tool; retrieve them through `get_sutra`.

## get_dhatu

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["query"],
  "properties": {
    "query": {"type": "string", "minLength": 1, "maxLength": 256},
    "by": {"enum": ["text", "upstream_id", "baseindex"], "default": "text"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
    "offset": {"type": "integer", "minimum": 0, "default": 0}
  }
}
```

Output:

```text
Result<{
  query: string,
  by: "text" | "upstream_id" | "baseindex",
  total: integer >= 1,
  offset: integer >= 0,
  limit: integer >= 1,
  next_offset: integer >= 0 | null,
  matches: Evidence<DhatuData>[]
}>
```

`by=text` matches NFC/whitespace-normalized equality against `dhatu` or `aupadeshik`; union matches by ID, sort numerically by upstream ID. There is no textual disambiguation or first-match selection. Identifier modes trim surrounding whitespace and match the exact stored identifier; `01.0001` is not equivalent to `1.1`. No matches returns `NOT_FOUND`. If matches exist but pagination is beyond the end, return success with empty `matches` and the true total.

Examples: `{"query":"भू"}` returns three matches at the inspected revision. `{"query":"1010001","by":"upstream_id"}` identifies one record. Each includes all original upstream fields, even ones the canonical model does not interpret.

## search_dhatus

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["query"],
  "properties": {
    "query": {"type": "string", "minLength": 1, "maxLength": 256},
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    "offset": {"type": "integer", "minimum": 0, "default": 0}
  }
}
```

Output: `Result<SearchPage<DhatuData>>`. Same literal normalization, ranking, empty-page behavior and evidence as sūtra search; ties by numeric upstream ID. Index the string fields `dhatu`, `aupadeshik`, `artha`, `artha_english`, `artha_hindi`, and `searchterms` when present. Do not flatten nested metadata into searchable text or interpret missing English meanings. Unexpected non-string searchable values are reported during import; original metadata survives.

## MCP mapping and failure semantics

Expose these five tools with explicit input/output schemas and `readOnlyHint=true`, `destructiveHint=false`, `idempotentHint=true`, `openWorldHint=false` (calls use only the loaded snapshot). Sync remains outside MCP. The tool adapter returns each `Result` through MCP `structuredContent` and the equivalent serialized JSON text content. Use SDK result types for the negotiated protocol version.

Service errors set MCP `isError=true`; successful results, including empty searches, set it false. Schema violations and invalid identifiers produce actionable `INVALID_INPUT` tool errors where the SDK supports them; malformed JSON-RPC or unknown methods remain SDK protocol errors. No raw stack trace or local secret is returned. An unavailable snapshot yields `DATA_UNAVAILABLE`, never fabricated empty scholarly data. Results are versioned through package/adapter version and pinned snapshot.

Modern and legacy stdio modes are covered by subprocess tests using the official SDK. No custom protocol dialect is implemented.
