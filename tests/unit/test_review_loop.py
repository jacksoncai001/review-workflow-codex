from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_workflow.domain.review import (
    ConcernDisposition,
    ReviewFinding,
    ReviewLoop,
    ReviewSeverity,
)


def test_review_finding_accepts_only_approved_dispositions() -> None:
    finding = ReviewFinding(
        finding_id="R-001",
        severity=ReviewSeverity.P1,
        category="scientific framing",
        message="The scope boundary is unclear.",
        disposition=ConcernDisposition.ADDRESSED,
        disposition_rationale="Boundary paragraph added and claim matrix updated.",
    )

    assert finding.disposition is ConcernDisposition.ADDRESSED

    with pytest.raises(ValidationError):
        ReviewFinding(
            finding_id="R-002",
            severity=ReviewSeverity.P1,
            category="method",
            message="Unclear validation.",
            disposition="ignored",
            disposition_rationale="No action",
        )


def test_non_pending_disposition_requires_rationale() -> None:
    with pytest.raises(ValidationError, match="rationale"):
        ReviewFinding(
            finding_id="R-003",
            severity=ReviewSeverity.P2,
            category="reader",
            message="Terminology is dense.",
            disposition=ConcernDisposition.ACCEPTED_AS_LIMITATION,
        )


def test_review_continues_when_p0_remains_before_round_limit() -> None:
    decision = ReviewLoop.decide(rounds_completed=1, score_delta=1.0, p0_count=1)

    assert decision.action == "continue"


def test_p0_after_two_rounds_returns_for_upstream_repair_not_early_stop() -> None:
    decision = ReviewLoop.decide(rounds_completed=2, score_delta=1.0, p0_count=1)

    assert decision.action == "return_required"
    assert decision.return_phase.value in {"4", "5", "6"}


def test_no_p0_and_small_score_delta_stops_bounded_review() -> None:
    decision = ReviewLoop.decide(rounds_completed=1, score_delta=2.9, p0_count=0)

    assert decision.action == "stop"
    assert decision.reason == "score_delta_below_3_and_no_p0"


def test_two_broad_rounds_is_hard_default_limit() -> None:
    decision = ReviewLoop.decide(rounds_completed=2, score_delta=8.0, p0_count=0)

    assert decision.action == "stop"
    assert decision.reason == "maximum_two_broad_rounds"
