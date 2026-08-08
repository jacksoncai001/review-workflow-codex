from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_workflow.adapters.filesystem import (
    WorkspaceBoundaryError,
    atomic_write_json,
    resolve_workspace_path,
    sha256_file,
)


def test_resolve_workspace_path_accepts_nested_relative_path(tmp_path: Path) -> None:
    workspace = tmp_path / "review-workspace"
    workspace.mkdir()

    resolved = resolve_workspace_path(workspace, Path("phases/phase-0/results.json"))

    assert resolved == (workspace / "phases/phase-0/results.json").resolve()


@pytest.mark.parametrize(
    "candidate_factory",
    [
        lambda root: Path("..") / "outside.json",
        lambda root: root.parent / f"{root.name}-evil" / "state.json",
        lambda root: root.parent / "outside" / "state.json",
    ],
)
def test_resolve_workspace_path_rejects_escape(
    tmp_path: Path,
    candidate_factory,
) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    workspace.mkdir()

    with pytest.raises(WorkspaceBoundaryError):
        resolve_workspace_path(workspace, candidate_factory(workspace))


def test_atomic_write_json_preserves_previous_file_when_serialization_fails(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "state.json"
    destination.write_text('{"status":"READY"}\n', encoding="utf-8")

    with pytest.raises(TypeError):
        atomic_write_json(destination, {"not_json": object()})

    assert destination.read_text(encoding="utf-8") == '{"status":"READY"}\n'
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_atomic_write_json_replaces_file_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / "state.json"

    atomic_write_json(destination, {"schema_version": 2, "status": "RUNNING"})

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "schema_version": 2,
        "status": "RUNNING",
    }
    assert list(tmp_path.glob(".state.json.*.tmp")) == []
    assert len(sha256_file(destination)) == 64
