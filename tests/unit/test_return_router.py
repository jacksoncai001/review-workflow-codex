from __future__ import annotations

import pytest

from review_workflow.domain.loops import FailureKind, FailureSignal, ReturnRouter
from review_workflow.domain.phases import PhaseId


@pytest.mark.parametrize(
    ("kind", "expected_phase"),
    [
        (FailureKind.MISSING_LITERATURE, PhaseId.PHASE_0),
        (FailureKind.EXTRACTION_OR_IDENTITY, PhaseId.PHASE_1),
        (FailureKind.POSITIONING_OR_ARCHITECTURE, PhaseId.PHASE_2A),
        (FailureKind.CLAIM_EVIDENCE, PhaseId.PHASE_3),
        (FailureKind.PROSE_OR_VISUAL, PhaseId.PHASE_4),
        (FailureKind.CITATION_SEMANTIC_MISMATCH, PhaseId.PHASE_3),
        (FailureKind.REVIEW_FAILURE, PhaseId.PHASE_4),
    ],
)
def test_router_uses_earliest_phase_that_can_repair_failure(
    kind: FailureKind,
    expected_phase: PhaseId,
) -> None:
    event = ReturnRouter.route(
        FailureSignal(
            failure_id="failure-001",
            kind=kind,
            reason="Seeded test failure",
            invalidated_artifacts=["draft-001"],
            preserved_artifacts=["source-001"],
        )
    )

    assert event.return_phase is expected_phase
    assert event.resume_action.parameters["failure_id"] == "failure-001"
    assert event.stop_condition


@pytest.mark.parametrize("repair_phase", [PhaseId.PHASE_3, PhaseId.PHASE_4, PhaseId.PHASE_5])
def test_citation_mismatch_accepts_cause_selected_phase(repair_phase: PhaseId) -> None:
    event = ReturnRouter.route(
        FailureSignal(
            failure_id="citation-001",
            kind=FailureKind.CITATION_SEMANTIC_MISMATCH,
            reason="Claim scope exceeds the cited sentence",
            repair_phase=repair_phase,
        )
    )

    assert event.return_phase is repair_phase


@pytest.mark.parametrize("repair_phase", [PhaseId.PHASE_4, PhaseId.PHASE_5, PhaseId.PHASE_6])
def test_review_failure_accepts_cause_selected_phase(repair_phase: PhaseId) -> None:
    event = ReturnRouter.route(
        FailureSignal(
            failure_id="review-001",
            kind=FailureKind.REVIEW_FAILURE,
            reason="Reviewer found a major scientific framing defect",
            repair_phase=repair_phase,
        )
    )

    assert event.return_phase is repair_phase


def test_router_rejects_invalid_repair_phase() -> None:
    with pytest.raises(ValueError, match="not valid"):
        ReturnRouter.route(
            FailureSignal(
                failure_id="citation-002",
                kind=FailureKind.CITATION_SEMANTIC_MISMATCH,
                reason="Mismatch",
                repair_phase=PhaseId.PHASE_1,
            )
        )
