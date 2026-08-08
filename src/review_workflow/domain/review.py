"""Bounded adversarial-review findings and stopping policy."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from review_workflow.domain.models import StrictModel
from review_workflow.domain.phases import PhaseId


class ReviewSeverity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class ConcernDisposition(StrEnum):
    PENDING = "pending"
    ADDRESSED = "addressed"
    DISAGREED_WITH_REASON = "disagreed_with_reason"
    ACCEPTED_AS_LIMITATION = "accepted_as_limitation"


class ReviewFinding(StrictModel):
    schema_version: int = 1
    finding_id: str
    severity: ReviewSeverity
    category: str
    message: str
    disposition: ConcernDisposition = ConcernDisposition.PENDING
    disposition_rationale: str | None = None

    @model_validator(mode="after")
    def resolved_finding_requires_rationale(self) -> ReviewFinding:
        if self.disposition is not ConcernDisposition.PENDING and not self.disposition_rationale:
            raise ValueError("A non-pending disposition requires a rationale")
        return self


class ReviewDecision(StrictModel):
    action: Literal["continue", "stop", "return_required"]
    reason: str
    return_phase: PhaseId | None = None


class ReviewLoop:
    """Maximum-two-round policy with no early stop while P0 concerns remain."""

    @staticmethod
    def decide(rounds_completed: int, score_delta: float, p0_count: int) -> ReviewDecision:
        if rounds_completed < 0 or p0_count < 0:
            raise ValueError("Round and P0 counts cannot be negative")
        if p0_count > 0:
            if rounds_completed >= 2:
                return ReviewDecision(
                    action="return_required",
                    reason="p0_remains_after_two_rounds",
                    return_phase=PhaseId.PHASE_4,
                )
            return ReviewDecision(action="continue", reason="p0_requires_another_review_round")
        if rounds_completed >= 2:
            return ReviewDecision(action="stop", reason="maximum_two_broad_rounds")
        if score_delta < 3:
            return ReviewDecision(action="stop", reason="score_delta_below_3_and_no_p0")
        return ReviewDecision(action="continue", reason="material_improvement_still_available")
