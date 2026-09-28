import asyncio
import json
import os
import socket
import threading
import time
from pathlib import Path

import jsonschema
import pytest
import uvicorn
from mcp import Client
from starlette.testclient import TestClient

from ashtadhyayi_mcp.domain import DataError
from ashtadhyayi_mcp.http import create_http_app


def test_health_and_http_request_boundaries(form_data_dir):
    with TestClient(create_http_app(form_data_dir, public_host="grammar.example")) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert len(health.json()["snapshot"]["loaded_form_sources"]) == 17
        headers = {"host": "grammar.example", "accept": "application/json, text/event-stream"}
        assert client.post("/mcp", json={}, headers=headers).status_code == 400
        assert (
            client.post("/mcp", json={}, headers={**headers, "host": "evil.example"}).status_code
            == 421
        )
        assert (
            client.post(
                "/mcp", json={}, headers={**headers, "origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert client.post("/mcp", content=b"x" * 65537, headers=headers).status_code == 413
        assert client.get("/.well-known/oauth-authorization-server").status_code == 404
        assert client.get("/missing").status_code == 404


def test_http_missing_snapshot_fails_startup(tmp_path):
    with pytest.raises(DataError):
        create_http_app(tmp_path)


@pytest.mark.parametrize("host", ["https://example.com", "*.example.com", "bad/path"])
def test_http_invalid_public_host(form_data_dir, host):
    with pytest.raises(ValueError):
        create_http_app(form_data_dir, public_host=host)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("full", [False, pytest.param(True, marks=pytest.mark.integration)])
def test_http_all_tools_and_recovery(form_data_dir, mode, full):
    directory = form_data_dir
    if full:
        configured = os.environ.get("ASHTADHYAYI_INTEGRATION_DATA_DIR")
        if not configured:
            pytest.skip("Set ASHTADHYAYI_INTEGRATION_DATA_DIR for full-corpus HTTP testing")
        directory = Path(configured)
    app = create_http_app(directory)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert server.started

            async def run():
                async with Client(
                    f"http://127.0.0.1:{port}/mcp", mode=mode, read_timeout_seconds=20
                ) as client:
                    tools = {t.name: t for t in (await client.list_tools()).tools}
                    calls = {
                        "get_sutra": {"number": "6.1.77"},
                        "search_sutras": {"query": "यण्"},
                        "get_sutra_context": {"number": "6.1.77"},
                        "get_dhatu": {"query": "भू"},
                        "search_dhatus": {"query": "सत्तायाम्"},
                        "get_shabda": {"query": "तद्"},
                        "search_shabdas": {"query": "राम"},
                        "get_dhatu_forms": {"query": "भू", "lakara": "lat"},
                        "get_shabda_forms": {"query": "राम", "vibhakti": 5},
                        "lookup_form": {"query": "रामौ"},
                        "get_form_coverage": {},
                    }
                    assert tools.keys() == calls.keys()
                    for name, arguments in calls.items():
                        result = await client.call_tool(name, arguments)
                        assert not result.is_error, (name, result)
                        jsonschema.validate(result.structured_content, tools[name].output_schema)
                        assert json.loads(result.content[0].text) == result.structured_content
                    invalid = await client.call_tool("lookup_form", {"query": "रामौ", "limit": 100})
                    assert invalid.is_error
                    recovered = await client.call_tool("lookup_form", {"query": "रामौ"})
                    assert recovered.structured_content["data"]["total"] == 3

            asyncio.run(asyncio.wait_for(run(), 60))
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()
