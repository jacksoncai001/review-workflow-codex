from __future__ import annotations

from pathlib import Path

import pytest

from review_workflow.domain.artifacts import ArtifactCycleError, ArtifactGraph
from review_workflow.domain.models import ArtifactRecord, ArtifactStatus
from review_workflow.domain.phases import PhaseId


def record(artifact_id: str, dependencies: list[str] | None = None) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        kind="test",
        relative_path=Path(f"artifacts/{artifact_id}.json"),
        content_hash=(artifact_id[0] if artifact_id[0] in "abcdef" else "a") * 64,
        producer="test",
        phase="1",
        dependencies=dependencies or [],
        status=ArtifactStatus.VERIFIED,
    )


def populated_graph() -> ArtifactGraph:
    graph = ArtifactGraph()
    graph.register(record("source"))
    graph.register(record("extraction", ["source"]))
    graph.register(record("evidence", ["extraction"]))
    graph.register(record("outline", ["evidence"]))
    graph.register(record("claim", ["outline", "evidence"]))
    graph.register(record("draft", ["claim"]))
    graph.register(record("audit", ["draft", "claim"]))
    graph.register(record("unrelated"))
    return graph


def test_invalidate_descendants_is_recursive_and_preserves_independent_artifacts() -> None:
    graph = populated_graph()

    report = graph.invalidate_descendants(
        changed_ids={"outline"},
        reason="operator selected a new architecture",
        return_phase=PhaseId.PHASE_2B,
    )

    assert report.invalidated_artifacts == ["claim", "draft", "audit"]
    assert set(report.preserved_artifacts) == {
        "source",
        "extraction",
        "evidence",
        "outline",
        "unrelated",
    }
    assert graph.records["claim"].status is ArtifactStatus.STALE
    assert graph.records["evidence"].status is ArtifactStatus.VERIFIED


def test_changing_source_invalidates_every_descendant_but_not_unrelated() -> None:
    graph = populated_graph()

    report = graph.invalidate_descendants(
        changed_ids={"source"},
        reason="source file hash changed",
        return_phase=PhaseId.PHASE_1,
    )

    assert set(report.invalidated_artifacts) == {
        "extraction",
        "evidence",
        "outline",
        "claim",
        "draft",
        "audit",
    }
    assert graph.records["unrelated"].status is ArtifactStatus.VERIFIED


def test_register_rejects_cycles() -> None:
    graph = ArtifactGraph()
    graph.register(record("aaa"))
    graph.register(record("bbb", ["aaa"]))

    with pytest.raises(ArtifactCycleError):
        graph.replace(record("aaa", ["bbb"]))
