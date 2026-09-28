"""Explicit network import; never invoked by a scholarly MCP tool."""

import hashlib
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from . import __version__
from .adapters import (
    ALL_PATHS,
    MAX_FILE_BYTES,
    PATHS,
    RAW_BASE,
    FileInfo,
    Manifest,
    decode_json,
    load_snapshot,
)
from .domain import DataError

Fetcher = Callable[[str, int], bytes]


def fetch(url: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": f"ashtadhyayi-mcp/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw: bytes = response.read(max_bytes + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise DataError(
            "DATA_UNAVAILABLE", "Upstream download failed; existing snapshot unchanged"
        ) from exc
    if len(raw) > max_bytes:
        raise DataError("UPSTREAM_SCHEMA_ERROR", "Upstream file exceeds the download size limit")
    return raw


def sync(
    data_dir: Path,
    revision: str,
    *,
    fetcher: Fetcher = fetch,
    profile: Literal["core", "full"] = "core",
) -> Manifest:
    """Stage, verify, then atomically replace only the active pointer."""
    if re.fullmatch(r"[0-9a-f]{40}", revision):
        commit = revision
    else:
        if not revision or len(revision) > 200:
            raise DataError("INVALID_INPUT", "Supply a commit, branch, or tag")
        ref = urllib.parse.quote(revision, safe="")
        try:
            doc = decode_json(
                fetcher(
                    f"https://api.github.com/repos/ashtadhyayi-com/data/commits/{ref}",
                    1_000_000,
                )
            )
            commit = doc["sha"]
            if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError("Invalid commit")
        except (ValueError, KeyError, TypeError) as exc:
            raise DataError("UPSTREAM_SCHEMA_ERROR", "Cannot resolve upstream revision") from exc
    snapshots = data_dir / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=snapshots))
    pointer: Path | None = None
    try:
        files: dict[str, FileInfo] = {}
        for path in ALL_PATHS if profile == "full" else PATHS:
            raw = fetcher(f"{RAW_BASE}/{commit}/{path}", MAX_FILE_BYTES)
            if len(raw) > MAX_FILE_BYTES:
                raise DataError("UPSTREAM_SCHEMA_ERROR", "Upstream file exceeds size limit")
            target = stage / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            files[path] = FileInfo(
                sha256=hashlib.sha256(raw).hexdigest(),
                size=len(raw),
                retrieved_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        manifest = Manifest(upstream_revision=commit, files=files)
        (stage / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        load_snapshot(stage)
        snapshot_name = f"{commit}-{uuid.uuid4().hex}"
        stage.rename(snapshots / snapshot_name)
        pointer = data_dir / f".current-{uuid.uuid4().hex}"
        pointer.write_text(snapshot_name + "\n", encoding="utf-8")
        os.replace(pointer, data_dir / "current")
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if pointer is not None:
            pointer.unlink(missing_ok=True)
