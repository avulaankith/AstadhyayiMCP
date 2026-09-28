"""Replaceable evidence-first client; the default answerer only quotes sources."""

import re
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from mcp import Client, StdioServerParameters, types

AGENT_INSTRUCTION = (
    "When answering factual questions about Pāṇinian grammar that can be resolved "
    "through the Aṣṭādhyāyī MCP, retrieve the evidence first. Never invent a sūtra "
    "number, sūtra text, commentary, or grammatical attribution. Clearly distinguish "
    "retrieved source material from your own explanation. If the available sources "
    "do not establish the answer, state that the evidence is insufficient."
)


class ToolClient(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> types.CallToolResult: ...


# A future provider can consume question, instruction, and retrieved evidence.
# The built-in path deliberately has no provider dependency or model-generated prose.
Answerer = Callable[[str, str, dict[str, Any]], Awaitable[str]]


async def answer_question(
    client: ToolClient,
    question: str,
    *,
    answerer: Answerer | None = None,
) -> str:
    number = re.search(r"[0-9०-९]+\.[0-9०-९]+\.[0-9०-९]+", question)
    if number:
        selected = number.group()
    else:
        # Remove a question phrase, not Sanskrit morphology or grammatical content.
        query = re.split(r"\s+इत्यस्य\b", question, maxsplit=1)[0].strip(" ?？")
        response = await client.call_tool("search_sutras", {"query": query})
        result = response.structured_content
        if response.is_error or not isinstance(result, dict) or result.get("status") != "ok":
            return "The evidence is insufficient: retrieval failed. No grammatical answer supplied."
        page = result["data"]
        if page["total"] == 0:
            return "The evidence is insufficient: no matching sūtra was retrieved."
        if page["total"] != 1:
            return "Multiple sūtras match. Please supply a sūtra number; evidence is ambiguous."
        selected = page["results"][0]["record"]["data"]["number"]
    response = await client.call_tool(
        "get_sutra",
        {
            "number": selected,
            "commentaries": ["sutrartha", "sutrartha_english"],
        },
    )
    result = response.structured_content
    if response.is_error or not isinstance(result, dict) or result.get("status") != "ok":
        return "The evidence is insufficient: the requested sūtra could not be retrieved."
    evidence = result["data"]
    record = evidence["sutra"]
    text = record["data"]
    provenance = record["provenance"]
    lines = [
        "Retrieved source material — Ashtadhyayi.com, Neelesh Bodas and contributors:",
        f"{text['number']}: {text['text']}",
        f"Source: {provenance['source_url']}#{provenance['source_pointer']}",
    ]
    quotes = [c for c in evidence["commentaries"] if c["data"]["field"] in ("sa", "text")]
    for comment in quotes:
        data, source = comment["data"], comment["provenance"]
        lines.extend(
            [
                f"Source quotation ({data['source']}/{data['field']}): {data['text']}",
                f"Source: {source['source_url']}#{source['source_pointer']}",
            ]
        )
        if data["next_offset"] is not None:
            lines.append(f"Excerpt only; remaining text starts at offset {data['next_offset']}.")
    if not quotes:
        lines.append("The retrieved evidence is insufficient to provide an explanation.")
    if answerer is not None:
        explanation = await answerer(question, AGENT_INSTRUCTION, result)
        lines.extend(["Agent explanation (not source text):", explanation])
    else:
        lines.append("This extractive demo adds no independent grammatical explanation.")
    return "\n\n".join(lines)


async def demonstrate(question: str, data_dir: Path) -> str:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ashtadhyayi_mcp.cli", "--data-dir", str(data_dir.resolve()), "serve"],
    )
    async with Client(server, read_timeout_seconds=30) as client:
        return await answer_question(client, question)
