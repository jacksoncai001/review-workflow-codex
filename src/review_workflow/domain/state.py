"""Persistent Phase 0–7 state engine with exact post-answer resume."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from review_workflow.adapters.filesystem import atomic_write_json, resolve_workspace_path
from review_workflow.domain.models import (
    AcquisitionRequest,
    ArtifactRecord,
    DisclosureRecord,
    ExecutionProfile,
    ProjectConfig,
    PublicationMode,
    ReviewType,
    StrictModel,
    utc_now,
)
from review_workflow.domain.phases import (
    PhaseId,
    RunStatus,
    TransitionError,
    validate_forward_transition,
)

STATE_SCHEMA_VERSION = 2


class GateError(ValueError):
    """Raised when a mandatory human gate is absent or mismatched."""


class AnswerPacketError(ValueError):
    """Raised when an answer does not match the outstanding question packet."""


class ResumeAction(StrictModel):
    action: str = Field(min_length=1, max_length=120)
    phase: PhaseId
    step: str = Field(min_length=1, max_length=255)
    parameters: dict[str, Any] = Field(default_factory=dict)


class OutstandingQuestion(StrictModel):
    packet_id: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)


class GateRecord(StrictModel):
    gate_id: str
    status: Literal["pending", "approved"] = "pending"
    approved_by: str | None = None
    approved_at: datetime | None = None


class WorkflowEvent(StrictModel):
    event_id: str
    event_type: str
    phase: PhaseId
    step: str
    timestamp: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowStateV2(StrictModel):
    schema_version: Literal[2] = 2
    project_id: str
    workspace_root: Path
    review_type: ReviewType
    execution_profile: ExecutionProfile
    publication_mode: PublicationMode
    phase: PhaseId = PhaseId.PREFLIGHT
    step: str = "created"
    status: RunStatus = RunStatus.READY
    loop_counters: dict[str, int] = Field(default_factory=dict)
    artifacts: dict[str, ArtifactRecord] = Field(default_factory=dict)
    decisions: dict[str, Any] = Field(default_factory=dict)
    return_stack: list[dict[str, Any]] = Field(default_factory=list)
    current_gate: GateRecord | None = None
    outstanding_question: OutstandingQuestion | None = None
    resume_action: ResumeAction | None = None
    acquisition_requests: list[AcquisitionRequest] = Field(default_factory=list)
    external_disclosures: list[DisclosureRecord] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


GATE_ON_ENTRY: dict[PhaseId, str] = {
    PhaseId.PHASE_2E: "phase_2e_outline",
    PhaseId.PHASE_5: "phase_5_citation",
    PhaseId.PHASE_6: "phase_6_review",
    PhaseId.PHASE_7: "phase_7_final",
}

GATE_REQUIRED_TO_EXIT: dict[PhaseId, str] = {
    PhaseId.PHASE_2E: "phase_2e_outline",
    PhaseId.PHASE_5: "phase_5_citation",
    PhaseId.PHASE_6: "phase_6_review",
}


class WorkflowEngine:
    """Own workflow state and persist every accepted mutation."""

    def __init__(self, workspace: Path, state: WorkflowStateV2) -> None:
        self.workspace = workspace.resolve(strict=False)
        self.state = state

    @classmethod
    def create(cls, config: ProjectConfig) -> WorkflowEngine:
        workspace = config.workspace_root.resolve(strict=False)
        workspace.mkdir(parents=True, exist_ok=True)
        state_path = resolve_workspace_path(workspace, Path("state.json"))
        if state_path.exists():
            raise FileExistsError(f"Workflow state already exists: {state_path}")
        resolve_workspace_path(workspace, Path("audit")).mkdir(parents=True, exist_ok=True)
        state = WorkflowStateV2(
            project_id=config.project_id,
            workspace_root=workspace,
            review_type=config.review_type,
            execution_profile=config.execution_profile,
            publication_mode=config.publication_mode,
        )
        engine = cls(workspace, state)
        engine._commit("project_created", {"schema_version": STATE_SCHEMA_VERSION})
        return engine

    @classmethod
    def load(cls, workspace: Path) -> WorkflowEngine:
        root = workspace.resolve(strict=False)
        state_path = resolve_workspace_path(root, Path("state.json"))
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        state = WorkflowStateV2.model_validate(payload)
        if state.workspace_root.resolve(strict=False) != root:
            raise ValueError("state.json workspace_root does not match the opened workspace")
        return cls(root, state)

    @classmethod
    def relocate(cls, workspace: Path) -> WorkflowEngine:
        """Explicitly rebind a copied workspace and record the migration event."""
        root = workspace.resolve(strict=False)
        state_path = resolve_workspace_path(root, Path("state.json"))
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        state = WorkflowStateV2.model_validate(payload)
        previous = state.workspace_root.resolve(strict=False)
        if previous == root:
            return cls(root, state)
        state.workspace_root = root
        engine = cls(root, state)
        resolve_workspace_path(root, Path("audit")).mkdir(parents=True, exist_ok=True)
        engine._commit(
            "workspace_relocated",
            {"previous_workspace_root": str(previous), "workspace_root": str(root)},
        )
        return engine

    def transition(self, target: PhaseId, step: str | None = None) -> None:
        if self.state.status in {
            RunStatus.WAITING_USER,
            RunStatus.WAITING_ACQUISITION,
            RunStatus.PAUSED_BY_USER,
            RunStatus.COMPLETED,
        }:
            raise TransitionError(f"Cannot transition while status is {self.state.status.value}")
        if (
            self.state.phase is PhaseId.PHASE_2A
            and target is PhaseId.PHASE_2B
            and self.state.loop_counters.get("mutual_scoping_rounds", 0) < 3
        ):
            raise TransitionError(
                "Phase 2B requires at least three completed reciprocal scoping rounds"
            )
        validate_forward_transition(self.state.phase, target)
        required_gate = GATE_REQUIRED_TO_EXIT.get(self.state.phase)
        if required_gate:
            gate = self.state.current_gate
            if gate is None or gate.gate_id != required_gate or gate.status != "approved":
                raise GateError(f"Gate {required_gate} must be approved before leaving phase")
        self.state.phase = target
        self.state.step = step or f"entered_{target.value}"
        self.state.status = RunStatus.RUNNING
        gate_id = GATE_ON_ENTRY.get(target)
        self.state.current_gate = GateRecord(gate_id=gate_id) if gate_id else None
        self._commit("phase_transitioned", {"target": target.value})

    def approve_gate(self, gate_id: str, approved_by: str) -> None:
        gate = self.state.current_gate
        if gate is None or gate.gate_id != gate_id:
            raise GateError(f"Current gate is not {gate_id}")
        if gate.status == "approved":
            raise GateError(f"Gate already approved: {gate_id}")
        self.state.current_gate = gate.model_copy(
            update={"status": "approved", "approved_by": approved_by, "approved_at": utc_now()}
        )
        self.state.decisions[f"gate:{gate_id}"] = {
            "approved_by": approved_by,
            "approved_at": self.state.current_gate.approved_at.isoformat(),
        }
        self._commit("gate_approved", {"gate_id": gate_id, "approved_by": approved_by})

    def wait_for_user(
        self,
        packet_id: str,
        question_payload: Mapping[str, Any],
        resume_action: ResumeAction,
        *,
        acquisition: bool = False,
    ) -> None:
        if self.state.outstanding_question is not None:
            raise AnswerPacketError("A question packet is already outstanding")
        self.state.outstanding_question = OutstandingQuestion(
            packet_id=packet_id,
            payload=dict(question_payload),
        )
        self.state.resume_action = resume_action
        self.state.status = RunStatus.WAITING_ACQUISITION if acquisition else RunStatus.WAITING_USER
        self._commit(
            "waiting_for_answer",
            {"packet_id": packet_id, "resume_action": resume_action.model_dump(mode="json")},
        )

    def record_answer(
        self,
        packet_id: str,
        answer_payload: Mapping[str, Any],
    ) -> ResumeAction:
        outstanding = self.state.outstanding_question
        resume = self.state.resume_action
        if outstanding is None or resume is None:
            raise AnswerPacketError("No answer is currently expected")
        if outstanding.packet_id != packet_id:
            raise AnswerPacketError(
                f"Answer packet {packet_id!r} does not match {outstanding.packet_id!r}"
            )
        self.state.decisions[f"answer:{packet_id}"] = dict(answer_payload)
        self.state.outstanding_question = None
        self.state.resume_action = None
        self.state.phase = resume.phase
        self.state.step = resume.step
        self.state.status = RunStatus.RUNNING
        self._commit(
            "answer_recorded",
            {"packet_id": packet_id, "resume_action": resume.model_dump(mode="json")},
        )
        return resume

    def begin_literature_refresh(
        self,
        *,
        refresh_id: str,
        search_lanes: list[str],
        resume_action: ResumeAction,
    ) -> None:
        """Persist an initial or Phase 2A search cycle before external discovery starts."""
        if self.state.status is not RunStatus.RUNNING or self.state.phase not in {
            PhaseId.PHASE_0,
            PhaseId.PHASE_2A,
        }:
            raise TransitionError(
                "Literature refresh can start only from a running Phase 0 or Phase 2A"
            )
        if not search_lanes:
            raise ValueError("Literature refresh requires at least one search lane")
        key = f"literature_refresh:{refresh_id}"
        if key in self.state.decisions:
            raise ValueError(f"Literature refresh already exists: {refresh_id}")
        origin_phase = self.state.phase
        self.state.phase = PhaseId.PHASE_0
        self.state.step = f"literature_refresh:{refresh_id}"
        self.state.status = RunStatus.RUNNING
        self.state.resume_action = resume_action
        self.state.decisions[key] = {
            "refresh_id": refresh_id,
            "status": "search_required",
            "search_lanes": search_lanes,
            "acquisition_request_ids": [],
            "origin_phase": origin_phase.value,
        }
        self._commit(
            "literature_refresh_started",
            {
                "refresh_id": refresh_id,
                "search_lanes": search_lanes,
                "resume_action": resume_action.model_dump(mode="json"),
            },
        )

    def wait_for_literature_acquisition(
        self,
        *,
        refresh_id: str,
        request_ids: list[str],
    ) -> None:
        """Wait for unresolved recommendation files without losing the Phase 2A resume."""
        if self.state.phase is not PhaseId.PHASE_0 or self.state.resume_action is None:
            raise TransitionError("No Phase 0 literature refresh is active")
        packet_id = f"acquisition:{refresh_id}"
        self.state.outstanding_question = OutstandingQuestion(
            packet_id=packet_id,
            payload={
                "packet_type": "acquisition",
                "refresh_id": refresh_id,
                "request_ids": request_ids,
            },
        )
        self.state.status = RunStatus.WAITING_ACQUISITION
        self._commit(
            "waiting_for_acquisition",
            {"refresh_id": refresh_id, "request_ids": request_ids},
        )

    def wait_for_recommended_reading(
        self,
        *,
        refresh_id: str,
        recommendation_ids: list[str],
        corpus_counts: Mapping[str, int],
    ) -> str:
        """Require operator reading before resuming the saved workflow action."""
        key = f"literature_refresh:{refresh_id}"
        decision = self.state.decisions.get(key)
        if decision is None or self.state.resume_action is None:
            raise ValueError(f"No active literature refresh: {refresh_id}")
        if self.state.phase is not PhaseId.PHASE_0:
            raise TransitionError("Recommended-reading wait can start only from Phase 0")
        if decision.get("status") not in {"acquisition_wait", "corpus_refresh"}:
            raise ValueError("Literature discovery has not reached acquisition completion")
        packet_id = f"recommended-reading:{refresh_id}"
        self.state.decisions[key] = {
            **decision,
            "status": "reading_required",
            "corpus_counts": dict(corpus_counts),
            "recommendation_ids": recommendation_ids,
        }
        self.state.step = f"recommended_reading:{refresh_id}"
        self.state.status = RunStatus.WAITING_USER
        self.state.outstanding_question = OutstandingQuestion(
            packet_id=packet_id,
            payload={
                "packet_type": "recommended_reading",
                "refresh_id": refresh_id,
                "recommendation_ids": recommendation_ids,
            },
        )
        self._commit(
            "waiting_for_recommended_reading",
            {
                "refresh_id": refresh_id,
                "corpus_counts": dict(corpus_counts),
                "recommendation_ids": recommendation_ids,
            },
        )
        return packet_id

    def pause(self, reason: str) -> None:
        if self.state.status is RunStatus.COMPLETED:
            raise TransitionError("A completed workflow cannot be paused")
        self.state.status = RunStatus.PAUSED_BY_USER
        self._commit("paused_by_user", {"reason": reason})

    def record_decision(
        self,
        key: str,
        payload: Mapping[str, Any],
        *,
        loop_counter: tuple[str, int] | None = None,
    ) -> None:
        """Persist a validated decision and an optional loop counter atomically."""
        self.state.decisions[key] = dict(payload)
        if loop_counter is not None:
            counter_name, counter_value = loop_counter
            self.state.loop_counters[counter_name] = counter_value
        self._commit("decision_recorded", {"key": key})

    def register_artifact(self, record: ArtifactRecord) -> None:
        """Persist one artifact after dependency validation by the application layer."""
        self.state.artifacts[record.artifact_id] = record
        self._commit("artifact_registered", {"artifact_id": record.artifact_id})

    def replace_artifact(
        self,
        record: ArtifactRecord,
        *,
        artifacts: Mapping[str, ArtifactRecord] | None = None,
        invalidated_artifacts: list[str] | None = None,
    ) -> None:
        """Persist a validated replacement version of an existing artifact."""
        if record.artifact_id not in self.state.artifacts:
            raise ValueError(f"Unknown artifact: {record.artifact_id}")
        previous_hash = self.state.artifacts[record.artifact_id].content_hash
        if artifacts is not None:
            self.state.artifacts = dict(artifacts)
        else:
            self.state.artifacts[record.artifact_id] = record
        self._commit(
            "artifact_replaced",
            {
                "artifact_id": record.artifact_id,
                "previous_hash": previous_hash,
                "content_hash": record.content_hash,
                "invalidated_artifacts": invalidated_artifacts or [],
            },
        )

    def apply_return(
        self,
        *,
        return_payload: Mapping[str, Any],
        artifacts: Mapping[str, ArtifactRecord],
    ) -> None:
        """Apply a validated backward repair transition and preserve its resume target."""
        return_phase = PhaseId(str(return_payload["return_phase"]))
        resume = ResumeAction.model_validate(return_payload["resume_action"])
        self.state.artifacts = dict(artifacts)
        self.state.return_stack.append(dict(return_payload))
        self.state.phase = return_phase
        self.state.step = f"repair:{return_payload['failure_id']}"
        self.state.status = RunStatus.RUNNING
        self.state.current_gate = None
        self.state.outstanding_question = None
        self.state.resume_action = resume
        self._commit(
            "return_applied",
            {
                "failure_id": return_payload["failure_id"],
                "return_phase": return_phase.value,
            },
        )

    def resume_after_repair(self, failure_id: str) -> ResumeAction:
        """Resume the exact saved origin after application-level repair validation."""
        if not self.state.return_stack:
            raise ValueError("No return event is active")
        latest = self.state.return_stack[-1]
        if latest.get("failure_id") != failure_id:
            raise ValueError(f"Active return event is not {failure_id}")
        resume = self.state.resume_action
        if resume is None:
            raise ValueError("The active return event has no resume action")
        self.state.phase = resume.phase
        self.state.step = resume.step
        self.state.status = RunStatus.RUNNING
        self.state.resume_action = None
        gate_id = GATE_ON_ENTRY.get(resume.phase)
        self.state.current_gate = GateRecord(gate_id=gate_id) if gate_id else None
        self._commit(
            "repair_completed",
            {"failure_id": failure_id, "resume_action": resume.model_dump(mode="json")},
        )
        return resume

    def add_acquisition_request(self, request: AcquisitionRequest) -> None:
        """Persist a new acquisition request without silently replacing an existing one."""
        if any(item.request_id == request.request_id for item in self.state.acquisition_requests):
            raise ValueError(f"Acquisition request already exists: {request.request_id}")
        self.state.acquisition_requests.append(request)
        self._commit("acquisition_requested", {"request_id": request.request_id})

    def replace_acquisition_request(self, request: AcquisitionRequest) -> None:
        """Persist an allowed status update to an acquisition request."""
        for index, item in enumerate(self.state.acquisition_requests):
            if item.request_id == request.request_id:
                self.state.acquisition_requests[index] = request
                self._commit("acquisition_updated", {"request_id": request.request_id})
                return
        raise ValueError(f"Unknown acquisition request: {request.request_id}")

    def add_disclosure(self, record: DisclosureRecord) -> None:
        """Persist a consent record after append-only ledger validation."""
        if any(
            item.disclosure_id == record.disclosure_id for item in self.state.external_disclosures
        ):
            raise ValueError(f"Disclosure record already exists: {record.disclosure_id}")
        self.state.external_disclosures.append(record)
        self._commit("privacy_decision_recorded", {"disclosure_id": record.disclosure_id})

    def complete(self) -> None:
        if self.state.phase is not PhaseId.PHASE_7:
            raise TransitionError("Workflow can complete only from Phase 7")
        gate = self.state.current_gate
        if gate is None or gate.gate_id != "phase_7_final" or gate.status != "approved":
            raise GateError("Gate phase_7_final must be approved before completion")
        self.state.status = RunStatus.COMPLETED
        self.state.step = "completed"
        self._commit("workflow_completed", {})

    def _commit(self, event_type: str, details: dict[str, Any]) -> None:
        event = WorkflowEvent(
            event_id=f"evt-{uuid.uuid4().hex}",
            event_type=event_type,
            phase=self.state.phase,
            step=self.state.step,
            details=details,
        )
        self.state.events.append(event)
        self.state.updated_at = event.timestamp
        atomic_write_json(
            resolve_workspace_path(self.workspace, Path("state.json")),
            self.state.model_dump(mode="json"),
        )
        event_path = resolve_workspace_path(self.workspace, Path("audit/events.jsonl"))
        line = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        with event_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
