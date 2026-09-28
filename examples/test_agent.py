"""Run a real Codex agent against this checkout's MCP without changing user config."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--data-dir", type=Path, default=root / ".data")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/ashtadhyayi-agent-test"))
    args = parser.parse_args()
    if not args.codex:
        parser.error("Codex CLI is not on PATH; supply --codex /absolute/path/to/codex")
    data_dir = args.data_dir.resolve()
    if not (data_dir / "current").is_file():
        parser.error("Sync a full snapshot first: ashtadhyayi-mcp --data-dir .data sync")
    # JSON strings/arrays are compatible with TOML basic strings for these paths.
    import json

    command = [
        args.codex,
        "--no-daemon",
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "-c",
        "mcp_servers.ashtadhyayi.command=" + json.dumps(sys.executable),
        "-c",
        "mcp_servers.ashtadhyayi.args="
        + json.dumps(["-m", "ashtadhyayi_mcp.cli", "--data-dir", str(data_dir), "serve"]),
        "-c",
        "mcp_servers.ashtadhyayi.startup_timeout_sec=30",
        "--json",
        "-o",
        str(args.output_dir.resolve() / "answer.md"),
        "-",
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prompt = (root / "examples/agent-test-prompt.md").read_text()
    print("Running Codex with the local MCP. This uses your existing Codex login.", flush=True)
    try:
        with (
            (args.output_dir / "events.jsonl").open("w") as events,
            (args.output_dir / "stderr.log").open("w") as errors,
        ):
            result = subprocess.run(
                command,
                input=prompt,
                text=True,
                stdout=events,
                stderr=errors,
                cwd=root,
                timeout=300,
                check=False,
            )
    except subprocess.TimeoutExpired:
        print(f"Agent exceeded 300 seconds; inspect {args.output_dir}/stderr.log", file=sys.stderr)
        return 1
    print(f"Agent exit code: {result.returncode}. Logs: {args.output_dir.resolve()}")
    answer = args.output_dir / "answer.md"
    if result.returncode == 0 and answer.is_file():
        print(answer.read_text())
    else:
        print("Agent did not finish successfully; inspect stderr.log and events.jsonl.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
