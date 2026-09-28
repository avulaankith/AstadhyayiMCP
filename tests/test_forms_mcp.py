import asyncio
import json
import sys

import jsonschema
import pytest
from mcp import Client, StdioServerParameters

from ashtadhyayi_mcp.server import Dispatcher, tool_definitions


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_all_new_tools_over_real_stdio(form_data_dir, mode):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "ashtadhyayi_mcp.cli",
                "--data-dir",
                str(form_data_dir),
                "serve",
            ],
        )
        async with Client(params, mode=mode, read_timeout_seconds=20) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            calls = {
                "get_shabda": {"query": "तद्"},
                "search_shabdas": {"query": "राम"},
                "get_dhatu_forms": {"query": "भू", "lakara": "lat"},
                "get_shabda_forms": {"query": "राम", "vibhakti": 5},
                "lookup_form": {"query": "रामौ"},
                "get_form_coverage": {},
            }
            for name, args in calls.items():
                result = await client.call_tool(name, args)
                assert not result.is_error
                jsonschema.validate(result.structured_content, tools[name].output_schema)
                assert json.loads(result.content[0].text) == result.structured_content
            error = await client.call_tool("get_shabda_forms", {"query": "absent-lemma"})
            assert error.is_error and error.structured_content["error"]["code"] == "NOT_FOUND"

    asyncio.run(asyncio.wait_for(run(), 40))


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("get_shabda_forms", {"query": "राम", "vibhakti": 9}),
        ("get_shabda", {"query": "राम", "linga": "bogus"}),
        ("lookup_form", {"query": " \n\t"}),
        ("lookup_form", {"query": "रामौ", "kind": "sandhi"}),
        ("get_dhatu_forms", {"query": "भू", "lakara": "lat", "pratyaya": "क्त"}),
        ("get_form_coverage", {"anything": 1}),
    ],
)
def test_new_tools_strict_input_and_structured_errors(form_data_dir, name, args):
    result = Dispatcher(form_data_dir).call(name, args)
    assert result.is_error and result.structured_content["error"]["code"] == "INVALID_INPUT"
    schema = next(t.output_schema for t in tool_definitions() if t.name == name)
    jsonschema.validate(result.structured_content, schema)


def test_older_snapshot_explicitly_reports_unloaded_sources(data_dir):
    dispatcher = Dispatcher(data_dir)
    for name in (
        "get_shabda",
        "search_shabdas",
        "get_shabda_forms",
        "get_dhatu_forms",
        "lookup_form",
    ):
        response = dispatcher.call(name, {"query": "भू"})
        assert response.is_error
        assert response.structured_content["error"]["code"] == "SOURCE_NOT_LOADED"
    coverage = dispatcher.call("get_form_coverage", {}).structured_content["data"]
    assert len(coverage["missing_sources"]) == 17
