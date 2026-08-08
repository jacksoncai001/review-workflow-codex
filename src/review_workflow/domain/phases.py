"""Canonical Phase 0–7 registry and legal forward transitions."""

from __future__ import annotations

from enum import StrEnum


class TransitionError(ValueError):
    """Raised when a caller attempts an unregistered phase transition."""


class PhaseId(StrEnum):
    PREFLIGHT = "preflight"
    PHASE_0 = "0"
    PHASE_1 = "1"
    PHASE_2A = "2A"
    PHASE_2B = "2B"
    PHASE_2C = "2C"
    PHASE_2D = "2D"
    PHASE_2E = "2E"
    PHASE_3 = "3"
    PHASE_4 = "4"
    PHASE_5 = "5"
    PHASE_6 = "6"
    PHASE_7 = "7"


class RunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    WAITING_ACQUISITION = "WAITING_ACQUISITION"
    PAUSED_BY_USER = "PAUSED_BY_USER"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"


FORWARD_TRANSITIONS: dict[PhaseId, PhaseId] = {
    PhaseId.PREFLIGHT: PhaseId.PHASE_0,
    PhaseId.PHASE_0: PhaseId.PHASE_1,
    PhaseId.PHASE_1: PhaseId.PHASE_2A,
    PhaseId.PHASE_2A: PhaseId.PHASE_2B,
    PhaseId.PHASE_2B: PhaseId.PHASE_2C,
    PhaseId.PHASE_2C: PhaseId.PHASE_2D,
    PhaseId.PHASE_2D: PhaseId.PHASE_2E,
    PhaseId.PHASE_2E: PhaseId.PHASE_3,
    PhaseId.PHASE_3: PhaseId.PHASE_4,
    PhaseId.PHASE_4: PhaseId.PHASE_5,
    PhaseId.PHASE_5: PhaseId.PHASE_6,
    PhaseId.PHASE_6: PhaseId.PHASE_7,
}


def validate_forward_transition(source: PhaseId, target: PhaseId) -> None:
    """Require ``target`` to be the single registered successor of ``source``."""
    expected = FORWARD_TRANSITIONS.get(source)
    if expected is not target:
        raise TransitionError(
            f"Illegal forward transition {source.value!r} -> {target.value!r}; "
            f"expected {expected.value!r}"
            if expected
            else f"Phase {source.value!r} has no successor"
        )
