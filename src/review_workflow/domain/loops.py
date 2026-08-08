"""Reciprocal scoping, literature-refresh, return, and revision loop policies."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from review_workflow.domain.models import ReviewType, StrictModel
from review_workflow.domain.phases import PhaseId
from review_workflow.domain.state import ResumeAction

QuestionText = Annotated[str, Field(min_length=3, max_length=1000)]
AnswerText = Annotated[str, Field(min_length=1, max_length=5000)]


class QuestionPacket(StrictModel):
    """Questions Codex presents at the start of one reciprocal round."""

    schema_version: int = 1
    round_number: int = Field(ge=1)
    codex_questions: list[QuestionText] = Field(min_length=3, max_length=5)
    operator_questions_required_min: Literal[3] = 3
    operator_questions_required_max: Literal[5] = 5


class ScopingRound(StrictModel):
    """Completed two-way record for one scoping round."""

    schema_version: int = 1
    round_number: int = Field(ge=1)
    codex_questions: list[QuestionText] = Field(min_length=3, max_length=5)
    operator_answers: list[AnswerText] = Field(min_length=3, max_length=5)
    operator_questions: list[QuestionText] = Field(min_length=3, max_length=5)
    codex_answers: list[AnswerText] = Field(min_length=3, max_length=5)
    changed_assumptions: list[str] = Field(default_factory=list)
    unresolved_tensions: list[str] = Field(default_factory=list)
    new_search_lanes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def answer_counts_match_question_counts(self) -> ScopingRound:
        if len(self.operator_answers) != len(self.codex_questions):
            raise ValueError("operator_answers must match codex_questions one-for-one")
        if len(self.codex_answers) != len(self.operator_questions):
            raise ValueError("codex_answers must match operator_questions one-for-one")
        return self


class ScopeBrief(StrictModel):
    """Scientific scope fields required before architecture competition."""

    schema_version: int = 1
    review_type: ReviewType | None = None
    target_readers: list[str] = Field(default_factory=list)
    reader_decision: str | None = None
    scope_includes: list[str] = Field(default_factory=list)
    scope_excludes: list[str] = Field(default_factory=list)
    nearest_review_ids: list[str] = Field(default_factory=list)
    nearest_review_distinction: str | None = None
    unresolved_problem: str | None = None
    proposed_contribution: str | None = None
    evidence_feasibility: Literal["feasible", "uncertain", "infeasible"] | None = None

    def missing_requirements(self) -> list[str]:
        checks: list[tuple[str, bool]] = [
            ("review_type", self.review_type is not None),
            ("target_readers", bool(self.target_readers)),
            ("reader_decision", bool(self.reader_decision)),
            ("scope_includes", bool(self.scope_includes)),
            ("scope_excludes", bool(self.scope_excludes)),
            ("nearest_review_ids", bool(self.nearest_review_ids)),
            ("nearest_review_distinction", bool(self.nearest_review_distinction)),
            ("unresolved_problem", bool(self.unresolved_problem)),
            ("proposed_contribution", bool(self.proposed_contribution)),
            ("evidence_feasibility", self.evidence_feasibility == "feasible"),
        ]
        return [name for name, satisfied in checks if not satisfied]


class LoopEvaluation(StrictModel):
    status: Literal["continue", "complete", "return_required"]
    missing_requirements: list[str] = Field(default_factory=list)
    return_phase: PhaseId | None = None
    resume_action: ResumeAction | None = None
    search_lanes: list[str] = Field(default_factory=list)


class MutualScopingLoop:
    """Enforce at least three complete reciprocal scoping rounds."""

    def __init__(self, rounds: list[ScopingRound] | None = None) -> None:
        self.rounds = list(rounds or [])
        self._pending_search_lanes: dict[int, list[str]] = {
            record.round_number: list(record.new_search_lanes)
            for record in self.rounds
            if record.new_search_lanes
        }

    def next_packet(self, codex_questions: list[str]) -> QuestionPacket:
        return QuestionPacket(
            round_number=len(self.rounds) + 1,
            codex_questions=codex_questions,
        )

    def record_round(self, record: ScopingRound) -> None:
        expected = len(self.rounds) + 1
        if record.round_number != expected:
            raise ValueError(f"Expected scoping round {expected}, received {record.round_number}")
        self.rounds.append(record)
        if record.new_search_lanes:
            self._pending_search_lanes[record.round_number] = list(record.new_search_lanes)

    def mark_search_lanes_resolved(self, round_number: int) -> None:
        self._pending_search_lanes.pop(round_number, None)

    def evaluate(self, scope_brief: ScopeBrief) -> LoopEvaluation:
        if self._pending_search_lanes:
            round_number = min(self._pending_search_lanes)
            lanes = self._pending_search_lanes[round_number]
            return LoopEvaluation(
                status="return_required",
                return_phase=PhaseId.PHASE_0,
                resume_action=ResumeAction(
                    action="resume_scoping_after_literature_refresh",
                    phase=PhaseId.PHASE_2A,
                    step=f"round_{round_number}_after_literature_refresh",
                    parameters={"round_number": round_number, "search_lanes": lanes},
                ),
                search_lanes=lanes,
            )
        missing = scope_brief.missing_requirements()
        if len(self.rounds) < 3:
            missing = ["minimum_three_rounds", *missing]
        if missing:
            return LoopEvaluation(status="continue", missing_requirements=missing)
        return LoopEvaluation(status="complete")


class FailureKind(StrEnum):
    MISSING_LITERATURE = "missing_literature"
    EXTRACTION_OR_IDENTITY = "extraction_or_identity"
    POSITIONING_OR_ARCHITECTURE = "positioning_or_architecture"
    CLAIM_EVIDENCE = "claim_evidence"
    PROSE_OR_VISUAL = "prose_or_visual"
    CITATION_SEMANTIC_MISMATCH = "citation_semantic_mismatch"
    REVIEW_FAILURE = "review_failure"


class FailureSignal(StrictModel):
    failure_id: str = Field(min_length=3, max_length=160)
    kind: FailureKind
    reason: str = Field(min_length=3, max_length=3000)
    repair_phase: PhaseId | None = None
    origin_phase: PhaseId | None = None
    origin_step: str | None = None
    invalidated_artifacts: list[str] = Field(default_factory=list)
    preserved_artifacts: list[str] = Field(default_factory=list)


class ReturnEvent(StrictModel):
    schema_version: int = 1
    failure_id: str
    trigger_condition: str
    return_phase: PhaseId
    reason: str
    changed_artifacts: list[str] = Field(default_factory=list)
    prior_hashes: dict[str, str] = Field(default_factory=dict)
    invalidated_artifacts: list[str]
    preserved_artifacts: list[str]
    resume_action: ResumeAction
    stop_condition: str


class ReturnRouter:
    """Choose the earliest phase able to repair a classified failure."""

    _fixed_phase: dict[FailureKind, PhaseId] = {
        FailureKind.MISSING_LITERATURE: PhaseId.PHASE_0,
        FailureKind.EXTRACTION_OR_IDENTITY: PhaseId.PHASE_1,
        FailureKind.POSITIONING_OR_ARCHITECTURE: PhaseId.PHASE_2A,
        FailureKind.CLAIM_EVIDENCE: PhaseId.PHASE_3,
        FailureKind.PROSE_OR_VISUAL: PhaseId.PHASE_4,
        FailureKind.CITATION_SEMANTIC_MISMATCH: PhaseId.PHASE_3,
        FailureKind.REVIEW_FAILURE: PhaseId.PHASE_4,
    }
    _allowed_override: dict[FailureKind, set[PhaseId]] = {
        FailureKind.CITATION_SEMANTIC_MISMATCH: {
            PhaseId.PHASE_3,
            PhaseId.PHASE_4,
            PhaseId.PHASE_5,
        },
        FailureKind.REVIEW_FAILURE: {
            PhaseId.PHASE_4,
            PhaseId.PHASE_5,
            PhaseId.PHASE_6,
        },
    }
    _stop_condition: dict[FailureKind, str] = {
        FailureKind.MISSING_LITERATURE: (
            "The material evidence gap is resolved or explicitly downgraded with rationale."
        ),
        FailureKind.EXTRACTION_OR_IDENTITY: (
            "Required pages, structures, identity, figures, and tables pass extraction checks."
        ),
        FailureKind.POSITIONING_OR_ARCHITECTURE: (
            "The architecture passes reader, differentiation, value, and evidence thresholds."
        ),
        FailureKind.CLAIM_EVIDENCE: (
            "Every affected claim has support, locator, direction, and a defensible claim ceiling."
        ),
        FailureKind.PROSE_OR_VISUAL: (
            "The affected block or visual passes its section contract without whole-paper "
            "regeneration."
        ),
        FailureKind.CITATION_SEMANTIC_MISMATCH: (
            "The sentence, citation, locator, direction, scope, and strength align."
        ),
        FailureKind.REVIEW_FAILURE: (
            "No P0 review concern remains and the accepted stopping rule is satisfied."
        ),
    }

    @classmethod
    def route(cls, signal: FailureSignal) -> ReturnEvent:
        return_phase = cls._fixed_phase[signal.kind]
        if signal.repair_phase is not None:
            allowed = cls._allowed_override.get(signal.kind, {return_phase})
            if signal.repair_phase not in allowed:
                raise ValueError(
                    f"Repair phase {signal.repair_phase.value} is not valid for {signal.kind.value}"
                )
            return_phase = signal.repair_phase
        resume_phase = signal.origin_phase or return_phase
        resume_step = signal.origin_step or f"resume_after_{signal.failure_id}"
        return ReturnEvent(
            failure_id=signal.failure_id,
            trigger_condition=signal.kind.value,
            return_phase=return_phase,
            reason=signal.reason,
            changed_artifacts=signal.invalidated_artifacts,
            invalidated_artifacts=signal.invalidated_artifacts,
            preserved_artifacts=signal.preserved_artifacts,
            resume_action=ResumeAction(
                action="resume_after_repair",
                phase=resume_phase,
                step=resume_step,
                parameters={"failure_id": signal.failure_id, "repair_phase": return_phase.value},
            ),
            stop_condition=cls._stop_condition[signal.kind],
        )
