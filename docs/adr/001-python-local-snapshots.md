# ADR-001: Python, official MCP SDK, and local snapshots

Status: accepted and implemented. Date: 2026-09-28. The user approved this architecture and requested explicit source credit.

## Context

Phase 1 retrieves structured UTF-8 JSON/text from a modest corpus. It requires strong source preservation, validation, deterministic search, reproducible snapshots, and five local MCP tools. There is no frontend, derivation engine, vector search, or remote service requirement.

The [official SDK index](https://modelcontextprotocol.io/docs/2026-07-28/sdk) lists both Python and TypeScript as Tier 1. The inspected [Python SDK](https://github.com/modelcontextprotocol/python-sdk) describes stable v2, typed tools, clients and stdio. The inspected [TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) also describes stable v2, split server/client packages and schema-library integration. These are current documentation observations, not a tested dependency installation.

## Decision

Prefer Python 3.12+ with the official `mcp` v2 SDK and explicit Pydantic models. Resolve and lock a released SDK version during Stage 2; do not use an unpinned Git branch. Use `uv` for dependency locking and local commands. Use standard-library JSON, Unicode, hashing, filesystem, and HTTP facilities where sufficient. Development tools: pytest, Ruff, and a static type checker. Do not add a separate third-party FastMCP distribution.

| Criterion | Python | TypeScript |
| --- | --- | --- |
| Validation | Pydantic models fit heterogeneous source records and typed projections | Zod/another Standard Schema implementation fits equally well |
| Unicode inspection | Standard-library `unicodedata`, code-point string iteration, and JSON | Good Unicode strings; code-point offsets require avoiding UTF-16 indexing |
| Development | No compile step; data validation and fixtures are straightforward | Adds TypeScript/build configuration, but good Node packaging |
| MCP | Official Tier 1 SDK | Official Tier 1 SDK |
| Project fit | Small data-oriented CLI/service | Especially useful if a Node application already exists |

Python is selected for simpler data inspection, Unicode handling, and packaging for this repository, not because TypeScript cannot meet the requirements.

Use [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio) for the local subprocess workflow. Let the SDK implement protocol details. Publish explicit output schemas, return structured content and a compatible serialized JSON text block, and honor current [tool result conventions](https://modelcontextprotocol.io/specification/2026-07-28/server/tools). Keep retrieval independent of transport so HTTP can be added later.

Use immutable local snapshots and in-memory indexes. Sync is a separate CLI command with network access; MCP calls are offline and read-only. Default data profile imports only the two catalogs and three commentary files. No database, LLM dependency, embeddings, framework, or cloud infrastructure.

## Consequences

The installation needs a Python runtime. First use needs an explicit data sync. Users must resync to see upstream updates; results always expose their revision. An SDK integration test must verify the chosen client's protocol compatibility. Commentary rendering and encoded grammatical metadata remain source-preserving rather than becoming a new interpretation engine.

Implemented commands: `uv sync --locked`, `uv run ashtadhyayi-mcp sync`, `uv run pytest`, `uv run ashtadhyayi-mcp serve`. Version 0.1.0 pins official MCP SDK 2.2.0. Real stdio tests cover modern and legacy modes. The small package uses modules rather than one directory per conceptual layer; see [architecture](../architecture.md).
