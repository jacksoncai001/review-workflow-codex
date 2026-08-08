from __future__ import annotations

import pytest
from pydantic import ValidationError

from review_workflow.domain.loops import (
    MutualScopingLoop,
    QuestionPacket,
    ScopeBrief,
    ScopingRound,
)
from review_workflow.domain.models import ReviewType
from review_workflow.domain.phases import PhaseId


def questions(prefix: str, count: int = 3) -> list[str]:
    return [f"{prefix} question {index}?" for index in range(1, count + 1)]


def completed_round(round_number: int, *, search_lanes: list[str] | None = None) -> ScopingRound:
    return ScopingRound(
        round_number=round_number,
        codex_questions=questions("Codex"),
        operator_answers=[f"Operator answer {index}" for index in range(1, 4)],
        operator_questions=questions("Operator"),
        codex_answers=[f"Codex answer {index}" for index in range(1, 4)],
        changed_assumptions=["Target reader clarified"] if round_number == 1 else [],
        unresolved_tensions=[] if round_number == 3 else ["Scope still broad"],
        new_search_lanes=search_lanes or [],
    )


def complete_scope_brief() -> ScopeBrief:
    return ScopeBrief(
        review_type=ReviewType.TECHNICAL,
        target_readers=["diagnostic researchers", "fuel-cell engineers new to magnetic methods"],
        reader_decision="Decide which external-field methods can support which diagnostic claims",
        scope_includes=["non-invasive measurements", "validation evidence"],
        scope_excludes=["systematic review", "unverified CDD equivalence"],
        nearest_review_ids=["doi:10.1000/nearest-review"],
        nearest_review_distinction="Maps each measurement chain to a defensible claim ceiling",
        unresolved_problem="Earlier reviews do not connect measurement assumptions to claim limits",
        proposed_contribution="A newcomer-friendly claim ladder with validation requirements",
        evidence_feasibility="feasible",
    )


def test_question_packet_requires_three_to_five_codex_questions() -> None:
    with pytest.raises(ValidationError):
        QuestionPacket(round_number=1, codex_questions=questions("Codex", 2))

    packet = QuestionPacket(round_number=1, codex_questions=questions("Codex", 5))

    assert packet.operator_questions_required_min == 3
    assert packet.operator_questions_required_max == 5


def test_scoping_round_requires_matching_three_to_five_questions_from_both_sides() -> None:
    with pytest.raises(ValidationError):
        ScopingRound(
            round_number=1,
            codex_questions=questions("Codex"),
            operator_answers=["Only one answer"],
            operator_questions=questions("Operator"),
            codex_answers=["A", "B", "C"],
        )

    record = completed_round(1)

    assert len(record.codex_questions) + len(record.operator_questions) == 6


def test_loop_cannot_complete_before_three_rounds() -> None:
    loop = MutualScopingLoop()
    loop.record_round(completed_round(1))
    loop.record_round(completed_round(2))

    evaluation = loop.evaluate(complete_scope_brief())

    assert evaluation.status == "continue"
    assert "minimum_three_rounds" in evaluation.missing_requirements


def test_loop_completes_after_three_rounds_and_complete_scope() -> None:
    loop = MutualScopingLoop()
    for round_number in range(1, 4):
        loop.record_round(completed_round(round_number))

    evaluation = loop.evaluate(complete_scope_brief())

    assert evaluation.status == "complete"
    assert evaluation.missing_requirements == []


def test_missing_target_reader_or_nearest_review_distinction_prevents_completion() -> None:
    loop = MutualScopingLoop()
    for round_number in range(1, 4):
        loop.record_round(completed_round(round_number))
    brief = complete_scope_brief().model_copy(
        update={"target_readers": [], "nearest_review_distinction": None}
    )

    evaluation = loop.evaluate(brief)

    assert evaluation.status == "continue"
    assert "target_readers" in evaluation.missing_requirements
    assert "nearest_review_distinction" in evaluation.missing_requirements


def test_new_search_lane_returns_to_phase_0_then_resumes_same_scoping_round() -> None:
    loop = MutualScopingLoop()
    loop.record_round(
        completed_round(1, search_lanes=["validation under stack current transients"])
    )

    evaluation = loop.evaluate(complete_scope_brief())

    assert evaluation.status == "return_required"
    assert evaluation.return_phase is PhaseId.PHASE_0
    assert evaluation.resume_action is not None
    assert evaluation.resume_action.phase is PhaseId.PHASE_2A
    assert evaluation.resume_action.step == "round_1_after_literature_refresh"


def test_rounds_must_be_recorded_consecutively() -> None:
    loop = MutualScopingLoop()

    with pytest.raises(ValueError, match="Expected scoping round 1"):
        loop.record_round(completed_round(2))
