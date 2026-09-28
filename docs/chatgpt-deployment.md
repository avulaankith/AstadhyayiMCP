# Deploy for ChatGPT

The server supports two transports: `serve` for local stdio clients and
`serve-http` for remote clients at `/mcp`. Both expose the same eleven tools and
source-preserving responses. `/healthz` returns the loaded snapshot revision.

This endpoint serves public, read-only scholarly data without authentication.
It exposes retrieval tools only, not sync or filesystem operations. Host and
Origin checks are enabled; configure the exact public hostname. The SDK limits
request bodies to 64 KiB here. Apply hosting-provider request/rate limits if you
open the endpoint to general traffic. HTTPS should terminate at the hosting
provider's proxy; the application listens on HTTP behind it.

## Run locally

```sh
uv sync --locked
uv run ashtadhyayi-mcp --data-dir .data status
uv run ashtadhyayi-mcp --data-dir .data serve-http --port 8000
```

If no snapshot is present, run `sync --profile full` first. Serving never downloads
upstream files. Missing or corrupt data fails HTTP startup instead of reporting
a healthy endpoint. To inspect readiness:

```sh
curl http://127.0.0.1:8000/healthz
```

A plain GET on `/mcp` is not a tool test; use an MCP client to initialize and call
tools. Automated HTTP tests exercise both supported protocol modes:

```sh
ASHTADHYAYI_INTEGRATION_DATA_DIR=.data uv run pytest -q tests/test_http.py
```

## Deploy to an existing server or container host

Use a persistent data directory: the full pinned snapshot downloads about 190 MB
and remains available between restarts. Additional syncs retain older snapshots.
One application worker loads the corpus; account for per-worker memory if you
later increase worker count. Actual capacity should be measured on your host.

The included container starts as a non-root user, downloads a full snapshot only
when the persistent directory has no `current` pointer, then starts HTTP:

```sh
docker build -t ashtadhyayi-mcp .
docker volume create ashtadhyayi-data
docker run --name ashtadhyayi-mcp \
  -p 127.0.0.1:8000:8000 \
  -v ashtadhyayi-data:/data \
  -e ASHTADHYAYI_PUBLIC_HOST=grammar.example.org \
  ashtadhyayi-mcp
```

Replace `grammar.example.org` with the actual deployment hostname, without
`https://` or a path. Set the same environment variable in a managed container
host. `PORT` defaults to 8000 and can be supplied by the host. A bind-mounted host
directory must be writable by the container's `mcp` user; the named-volume example
inherits the image directory's ownership.

For native Python hosting, use these phases:

```sh
# Install dependencies and application from the checkout.
uv sync --locked --no-dev
# Explicit deployment step; set ASHTADHYAYI_DATA_DIR to persistent storage.
uv run --no-dev ashtadhyayi-mcp sync --profile full
# Host start command; ASHTADHYAYI_PUBLIC_HOST and PORT come from host settings.
uv run --no-dev ashtadhyayi-mcp serve-http --host 0.0.0.0
```

Configure the HTTPS proxy to forward `/mcp` and `/healthz`, preserve the public
Host header, and support POST, GET and DELETE. Use `/healthz` as the readiness
path; allow time for first-start corpus download. The public MCP URL will be:

```text
https://grammar.example.org/mcp
```

The Docker recipe is provided for deployment; Docker is not installed in the
current development environment, so the image itself has not been built locally.
The native HTTP server is covered by real socket/client tests.

## Connect in ChatGPT

OpenAI's [connection guide](https://developers.openai.com/plugins/deploy/connect-chatgpt)
requires a reachable HTTPS MCP endpoint or Secure MCP Tunnel. The
[quickstart](https://developers.openai.com/plugins/build/app-quickstart) describes
these current UI steps (availability depends on account/workspace settings):

1. Enable Developer mode in ChatGPT settings.
2. Open Plugins, choose the plus button, and add your HTTPS URL ending in `/mcp`.
3. Name it Aṣṭādhyāyī and choose no authentication for this public-data deployment.
4. Start a new chat and select the connection from the tools/More menu.
5. Ask: “Use Aṣṭādhyāyī to look up रामौ. Preserve every case/number possibility,
   explain vocative aliases and cite the original sources.”

Expected at the pinned revision: three occurrences—nominative dual, accusative
dual, and the alias of stored `हे रामौ`. Follow with “Show all nine shuddha kartari
lat parasmaipada forms of dhātu 01.0001” and “Can this evidence alone validate
sandhi?” The latter should explain the server's limitations, not invent a validator.

Adding a developer-mode connection is separate from public plugin-directory
submission. No plugin submission is required for this development test. See
[agent testing](agent-testing.md) for more prompts and verified local Codex results.

## Deployment status

A hosting account/server and public hostname must be selected before a live URL
can be provisioned. Local HTTP tests do not establish successful ChatGPT connection;
that must be checked after deployment in the user's ChatGPT account.
