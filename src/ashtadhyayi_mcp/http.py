"""Public read-only MCP over the official SDK's stateless Streamable HTTP transport."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .domain import DataError
from .server import Dispatcher, create_server


def create_http_app(data_dir: Path, *, public_host: str | None = None) -> Starlette:
    dispatcher = Dispatcher(data_dir)
    if dispatcher.failure is not None:
        error = dispatcher.failure.error
        raise DataError(error.code, error.message)
    assert dispatcher.service is not None
    snapshot = dispatcher.service.corpus.snapshot.model_dump(mode="json")
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*", "https://chatgpt.com"]
    if public_host:
        if any(c in public_host for c in "/?#@* \t\n\r"):
            raise ValueError(
                "Public host must be a hostname, optionally with port; no URL or wildcard"
            )
        hosts.append(public_host)
        origins.append("https://" + public_host)
    manager = StreamableHTTPSessionManager(
        create_server(data_dir, dispatcher=dispatcher),
        stateless=True,
        json_response=True,
        max_request_body_size=64 * 1024,
        security_settings=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins),
    )

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "snapshot": snapshot})

    return Starlette(
        routes=[
            Route("/healthz", health, methods=["GET"]),
            Route("/mcp", StreamableHTTPASGIApp(manager), methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )
