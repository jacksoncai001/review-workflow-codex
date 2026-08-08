"""Safe filesystem primitives for project workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class WorkspaceBoundaryError(ValueError):
    """Raised when a requested path resolves outside the workspace."""


def resolve_workspace_path(workspace_root: Path, candidate: Path) -> Path:
    """Resolve a candidate and require it to remain inside ``workspace_root``."""
    root = workspace_root.resolve(strict=False)
    target = (
        candidate.resolve(strict=False) if candidate.is_absolute() else (root / candidate).resolve()
    )
    if not target.is_relative_to(root):
        raise WorkspaceBoundaryError(f"Path is outside the configured workspace: {target}")
    return target


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomically replace a UTF-8 JSON file without damaging an existing file."""
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    destination = path.resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically replace a UTF-8 text file."""
    destination = path.resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
