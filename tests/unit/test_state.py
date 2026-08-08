from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_workflow.domain.models import ExecutionProfile, ProjectConfig, ReviewType
from review_workflow.domain.phases import PhaseId, RunStatus, TransitionError
from review_workflow.domain.state import (
    AnswerPacketError,
    GateError,
    ResumeAction,
    WorkflowEngine,
)


def make_engine(tmp_path: Path) -> WorkflowEngine:
    workspace = (tmp_path / "review-workspace").resolve()
    config = ProjectConfig(
        project_id="synthetic-review",
        workspace_root=workspace,
        review_type=ReviewType.TECHNICAL,
        execution_profile=ExecutionProfile.WINDOWS_LITE,
    )
    return WorkflowEngine.create(config)


def advance_to(engine: WorkflowEngine, target: PhaseId) -> None:
    order = [
        PhaseId.PHASE_0,
        PhaseId.PHASE_1,
        PhaseId.PHASE_2A,
        PhaseId.PHASE_2B,
        PhaseId.PHASE_2C,
        PhaseId.PHASE_2D,
        PhaseId.PHASE_2E,
        PhaseId.PHASE_3,
        PhaseId.PHASE_4,
        PhaseId.PHASE_5,
        PhaseId.PHASE_6,
        PhaseId.PHASE_7,
    ]
    for phase in order:
        if (
            phase is PhaseId.PHASE_2B
            and engine.state.loop_counters.get("mutual_scoping_rounds", 0) < 3
        ):
            engine.record_decision(
                "synthetic_scoping_protocol",
                {"rounds": 3},
                loop_counter=("mutual_scoping_rounds", 3),
            )
        if phase is PhaseId.PHASE_3:
            engine.approve_gate("phase_2e_outline", approved_by="operator")
        if phase is PhaseId.PHASE_6:
            engine.approve_gate("phase_5_citation", approved_by="operator")
        if phase is PhaseId.PHASE_7:
            engine.approve_gate("phase_6_review", approved_by="operator")
        engine.transition(phase, step=f"entered_{phase.value}")
        if phase is target:
            return


def test_create_persists_state_v2_and_load_round_trips(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)

    payload = json.loads((engine.workspace / "state.json").read_text(encoding="utf-8"))
    loaded = WorkflowEngine.load(engine.workspace)

    assert payload["schema_version"] == 2
    assert payload["phase"] == "preflight"
    assert loaded.state == engine.state
    assert (engine.workspace / "audit/events.jsonl").is_file()


def test_transition_rejects_jump_and_enforces_phase_2e_gate(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)

    with pytest.raises(TransitionError):
        engine.transition(PhaseId.PHASE_2A)

    advance_to(engine, PhaseId.PHASE_2E)

    assert engine.state.current_gate is not None
    assert engine.state.current_gate.gate_id == "phase_2e_outline"
    with pytest.raises(GateError):
        engine.transition(PhaseId.PHASE_3)

    engine.approve_gate("phase_2e_outline", approved_by="operator")
    engine.transition(PhaseId.PHASE_3)

    assert engine.state.phase is PhaseId.PHASE_3


def test_transition_to_phase_2b_requires_three_completed_scoping_rounds(
    tmp_path: Path,
) -> None:
    engine = make_engine(tmp_path)
    for phase in (PhaseId.PHASE_0, PhaseId.PHASE_1, PhaseId.PHASE_2A):
        engine.transition(phase)

    with pytest.raises(TransitionError, match="three completed reciprocal"):
        engine.transition(PhaseId.PHASE_2B)
    engine.record_decision(
        "scoping_protocol_complete",
        {"rounds": 3},
        loop_counter=("mutual_scoping_rounds", 3),
    )
    engine.transition(PhaseId.PHASE_2B)

    assert engine.state.phase is PhaseId.PHASE_2B


def test_record_answer_returns_exact_resume_action_and_continues_running(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    advance_to(engine, PhaseId.PHASE_2A)
    resume = ResumeAction(
        action="continue_scoping_round",
        phase=PhaseId.PHASE_2A,
        step="round_2_synthesize",
        parameters={"round": 2},
    )
    engine.wait_for_user(
        packet_id="scope-round-2",
        question_payload={"codex_questions": ["Who is the primary reader?"]},
        resume_action=resume,
    )

    returned = engine.record_answer(
        packet_id="scope-round-2",
        answer_payload={"operator_answers": ["Diagnostic researchers"]},
    )

    assert returned == resume
    assert engine.state.status is RunStatus.RUNNING
    assert engine.state.outstanding_question is None
    assert engine.state.resume_action is None
    assert engine.state.decisions["answer:scope-round-2"]["operator_answers"] == [
        "Diagnostic researchers"
    ]


def test_record_answer_rejects_wrong_packet_without_changing_state(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    resume = ResumeAction(
        action="continue_preflight",
        phase=PhaseId.PREFLIGHT,
        step="health_check",
    )
    engine.wait_for_user(
        packet_id="expected",
        question_payload={"question": "Proceed?"},
        resume_action=resume,
    )
    before = engine.state.model_copy(deep=True)

    with pytest.raises(AnswerPacketError):
        engine.record_answer("unexpected", {"answer": "yes"})

    assert engine.state == before


def test_complete_requires_phase_7_final_gate(tmp_path: Path) -> None:
    engine = make_engine(tmp_path)
    advance_to(engine, PhaseId.PHASE_7)

    with pytest.raises(GateError):
        engine.complete()

    engine.approve_gate("phase_7_final", approved_by="operator")
    engine.complete()

    assert engine.state.status is RunStatus.COMPLETED
