from __future__ import annotations

import pytest

from review_workflow.domain.phases import (
    PhaseId,
    TransitionError,
    validate_forward_transition,
)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PhaseId.PREFLIGHT, PhaseId.PHASE_0),
        (PhaseId.PHASE_0, PhaseId.PHASE_1),
        (PhaseId.PHASE_1, PhaseId.PHASE_2A),
        (PhaseId.PHASE_2A, PhaseId.PHASE_2B),
        (PhaseId.PHASE_2B, PhaseId.PHASE_2C),
        (PhaseId.PHASE_2C, PhaseId.PHASE_2D),
        (PhaseId.PHASE_2D, PhaseId.PHASE_2E),
        (PhaseId.PHASE_2E, PhaseId.PHASE_3),
        (PhaseId.PHASE_3, PhaseId.PHASE_4),
        (PhaseId.PHASE_4, PhaseId.PHASE_5),
        (PhaseId.PHASE_5, PhaseId.PHASE_6),
        (PhaseId.PHASE_6, PhaseId.PHASE_7),
    ],
)
def test_validate_forward_transition_accepts_registry_edges(
    source: PhaseId, target: PhaseId
) -> None:
    validate_forward_transition(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (PhaseId.PHASE_0, PhaseId.PHASE_2A),
        (PhaseId.PHASE_2E, PhaseId.PHASE_5),
        (PhaseId.PHASE_5, PhaseId.PHASE_3),
        (PhaseId.PHASE_7, PhaseId.PHASE_0),
    ],
)
def test_validate_forward_transition_rejects_arbitrary_jumps(
    source: PhaseId,
    target: PhaseId,
) -> None:
    with pytest.raises(TransitionError):
        validate_forward_transition(source, target)
