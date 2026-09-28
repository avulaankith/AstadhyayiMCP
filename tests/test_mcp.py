import asyncio
import json
import sys

import jsonschema
import pytest
from mcp import Client, StdioServerParameters

from ashtadhyayi_mcp.server import Dispatcher, tool_definitions


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_real_stdio_discovery_and_all_tools(data_dir, mode):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "ashtadhyayi_mcp.cli",
                "--data-dir",
                str(data_dir),
                "serve",
            ],
        )
        async with Client(params, mode=mode, read_timeout_seconds=15) as client:
            definitions = (await client.list_tools()).tools
            assert len(definitions) == 11
            calls = {
                "get_sutra": {"number": "६.१.७७"},
                "search_sutras": {"query": "यण्"},
                "get_sutra_context": {"number": "6.1.77"},
                "get_dhatu": {"query": "भू"},
                "search_dhatus": {"query": "सत्तायाम्"},
            }
            for tool in definitions:
                assert tool.annotations.read_only_hint
                assert tool.input_schema["additionalProperties"] is False
                if tool.name not in calls:
                    continue  # Full-profile tools have their own subprocess matrix.
                result = await client.call_tool(tool.name, calls[tool.name])
                assert not result.is_error
                jsonschema.validate(result.structured_content, tool.output_schema)
                assert json.loads(result.content[0].text) == result.structured_content
            absent = await client.call_tool("get_sutra", {"number": "8.4.999"})
            assert absent.is_error
            assert absent.structured_content["error"]["code"] == "NOT_FOUND"
            invalid = await client.call_tool("get_sutra", {"number": "nope"})
            assert invalid.is_error
            assert invalid.structured_content["error"]["code"] == "INVALID_INPUT"

    # Also verifies EOF shuts down the subprocess instead of leaving it running.
    asyncio.run(asyncio.wait_for(run(), timeout=30))


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_sutra", {"number": "6.1.77", "unexpected": True}),
        ("get_sutra", {"number": 61077}),
        ("get_sutra", {"number": "6.1.77", "commentaries": ["kashika", "kashika"]}),
        ("search_sutras", {"query": " \n\t"}),
        ("search_sutras", {"query": "यण्", "limit": True}),
        ("search_sutras", {"query": "यण्", "limit": 51}),
        ("search_dhatus", {"query": "भू", "offset": -1}),
        ("get_sutra_context", {"number": "6.1.77", "after": 6}),
    ],
)
def test_invalid_arguments_have_structured_error(data_dir, tool, arguments):
    result = Dispatcher(data_dir).call(tool, arguments)
    assert result.is_error
    assert result.structured_content["error"]["code"] == "INVALID_INPUT"
    definition = next(t for t in tool_definitions() if t.name == tool)
    jsonschema.validate(result.structured_content, definition.output_schema)


def test_no_snapshot_does_not_look_like_empty_corpus(tmp_path):
    result = Dispatcher(tmp_path).call("search_sutras", {"query": "यण्"})
    assert result.is_error
    assert result.structured_content["error"]["code"] == "DATA_UNAVAILABLE"


def test_every_published_schema_is_valid():
    for tool in tool_definitions():
        jsonschema.Draft202012Validator.check_schema(tool.input_schema)
        jsonschema.Draft202012Validator.check_schema(tool.output_schema)
