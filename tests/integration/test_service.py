from __future__ import annotations

import json
import shutil
from pathlib import Path

import httpx
import pytest

from review_workflow.application.service import WorkflowService
from review_workflow.domain.phases import PhaseId
from review_workflow.domain.state import WorkflowEngine

CODEX_QUESTIONS = [
    "Who is the primary reader?",
    "What decision should the review support?",
    "Which nearest review must this paper differ from?",
]


def initialize(service: WorkflowService, workspace: Path) -> None:
    service.project_init(
        workspace=workspace,
        project_id="synthetic-review",
        review_type="technical",
        execution_profile="windows-lite",
        publication_mode="single",
    )


def advance_to_2a(service: WorkflowService, workspace: Path) -> None:
    for phase in (PhaseId.PHASE_0, PhaseId.PHASE_1, PhaseId.PHASE_2A):
        service.phase_next(workspace=workspace, target=phase.value)


def test_project_init_status_and_standard_workspace_layout(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()

    created = service.project_init(
        workspace=workspace,
        project_id="synthetic-review",
        review_type="technical",
        execution_profile="windows-lite",
        publication_mode="companion",
    )
    status = service.project_status(workspace)

    assert created["status"] == "READY"
    assert status["schema_version"] == 2
    assert status["publication_mode"] == "companion"
    for relative in (
        "inputs",
        "corpus/extractions",
        "corpus/index",
        "phases/phase-0",
        "phases/phase-7",
        "manuscripts",
        "decisions",
        "acquisitions",
        "audit",
        "logs",
    ):
        assert (workspace / relative).is_dir()


def test_question_open_answer_records_complete_reciprocal_round_and_resumes(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    advance_to_2a(service, workspace)

    packet = service.question_packet_open(workspace, CODEX_QUESTIONS)
    waiting = service.question_packet_get(workspace)

    assert packet["round_number"] == 1
    assert waiting["packet_id"] == packet["packet_id"]
    assert service.project_status(workspace)["status"] == "WAITING_USER"

    result = service.answer_packet_record(
        workspace=workspace,
        packet_id=packet["packet_id"],
        answer_payload={
            "operator_answers": ["Researchers", "Choose methods", "Review X"],
            "operator_questions": [
                "What evidence is strongest?",
                "Which boundary is risky?",
                "What should a newcomer read first?",
            ],
            "codex_answers": ["Direct validation", "Proxy equivalence", "Anchor review"],
            "changed_assumptions": ["Newcomers are a secondary reader"],
            "unresolved_tensions": ["Scope breadth"],
            "new_search_lanes": [],
        },
    )

    status = service.project_status(workspace)
    assert result["resume_action"]["step"] == "round_1_synthesize"
    assert status["status"] == "RUNNING"
    assert status["loop_counters"]["mutual_scoping_rounds"] == 1
    assert status["decisions"]["scoping_round:1"]["operator_questions"][0].startswith("What")


def test_artifact_registration_hashes_file_and_return_route_invalidates_descendants(
    tmp_path: Path,
) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    evidence_path = workspace / "phases/phase-1/evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"evidence":true}\n', encoding="utf-8")
    outline_path = workspace / "phases/phase-2/outline.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.write_text('{"outline":true}\n', encoding="utf-8")

    evidence = service.artifact_register(
        workspace=workspace,
        artifact_id="evidence-001",
        kind="evidence_matrix",
        relative_path="phases/phase-1/evidence.json",
        producer="test",
        phase="1",
        dependencies=[],
    )
    service.artifact_register(
        workspace=workspace,
        artifact_id="outline-001",
        kind="outline",
        relative_path="phases/phase-2/outline.json",
        producer="test",
        phase="2E",
        dependencies=["evidence-001"],
    )

    routed = service.return_route(
        workspace=workspace,
        failure_payload={
            "failure_id": "failure-001",
            "kind": "extraction_or_identity",
            "reason": "Evidence extraction lost a required page locator",
            "invalidated_artifacts": ["evidence-001"],
            "preserved_artifacts": [],
        },
    )

    artifacts = {item["artifact_id"]: item for item in service.artifact_list(workspace)}
    assert len(evidence["content_hash"]) == 64
    assert routed["return_phase"] == "1"
    assert artifacts["outline-001"]["status"] == "stale"


def test_return_resume_requires_replaced_changed_and_descendant_artifacts(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    advance_to_2a(service, workspace)
    evidence_path = workspace / "phases/phase-1/evidence.json"
    outline_path = workspace / "phases/phase-2/outline.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text('{"version":1}\n', encoding="utf-8")
    outline_path.write_text('{"version":1}\n', encoding="utf-8")
    service.artifact_register(
        workspace=workspace,
        artifact_id="evidence-001",
        kind="extraction_record",
        relative_path="phases/phase-1/evidence.json",
        producer="test",
        phase="1",
        dependencies=[],
    )
    service.artifact_register(
        workspace=workspace,
        artifact_id="outline-001",
        kind="outline",
        relative_path="phases/phase-2/outline.json",
        producer="test",
        phase="2E",
        dependencies=["evidence-001"],
    )
    service.return_route(
        workspace=workspace,
        failure_payload={
            "failure_id": "failure-repair-001",
            "kind": "extraction_or_identity",
            "reason": "A locator is wrong",
            "origin_phase": "2A",
            "origin_step": "round_1_synthesize",
            "invalidated_artifacts": ["evidence-001"],
            "preserved_artifacts": [],
        },
    )

    with pytest.raises(ValueError, match="changed artifact"):
        service.return_resume(workspace=workspace, failure_id="failure-repair-001")
    evidence_path.write_text('{"version":2}\n', encoding="utf-8")
    service.artifact_register(
        workspace=workspace,
        artifact_id="evidence-001",
        kind="extraction_record",
        relative_path="phases/phase-1/evidence.json",
        producer="operator-repair",
        phase="1",
        dependencies=[],
        replace_existing=True,
    )
    outline_path.write_text('{"version":2}\n', encoding="utf-8")
    service.artifact_register(
        workspace=workspace,
        artifact_id="outline-001",
        kind="outline",
        relative_path="phases/phase-2/outline.json",
        producer="codex-repair",
        phase="2E",
        dependencies=["evidence-001"],
        replace_existing=True,
    )

    with pytest.raises(ValueError, match="resolution note"):
        service.return_resume(workspace=workspace, failure_id="failure-repair-001")
    with pytest.raises(ValueError, match="does not match the stop condition"):
        service.return_resume(
            workspace=workspace,
            failure_id="failure-repair-001",
            resolution_note="The extraction was rebuilt and its page locator was checked.",
            evidence_artifact_ids=["outline-001"],
        )
    resumed = service.return_resume(
        workspace=workspace,
        failure_id="failure-repair-001",
        resolution_note="The extraction was rebuilt and its page locator was checked.",
        evidence_artifact_ids=["evidence-001"],
    )

    assert resumed["phase"] == "2A"
    assert resumed["step"] == "round_1_synthesize"
    assert resumed["resume_action"] is None
    resolution = resumed["decisions"]["return_resolution:failure-repair-001"]
    assert resolution["stop_condition"]
    assert resolution["evidence"][0]["artifact_id"] == "evidence-001"


def test_replacing_artifact_outside_return_invalidates_its_descendants(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    evidence = workspace / "phases/phase-1/evidence.json"
    outline = workspace / "phases/phase-2/outline.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    outline.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text('{"version":1}\n', encoding="utf-8")
    outline.write_text('{"version":1}\n', encoding="utf-8")
    service.artifact_register(
        workspace=workspace,
        artifact_id="evidence",
        kind="evidence_matrix",
        relative_path="phases/phase-1/evidence.json",
        producer="test",
        phase="1",
        dependencies=[],
    )
    service.artifact_register(
        workspace=workspace,
        artifact_id="outline",
        kind="outline",
        relative_path="phases/phase-2/outline.json",
        producer="test",
        phase="2E",
        dependencies=["evidence"],
    )
    evidence.write_text('{"version":2}\n', encoding="utf-8")

    service.artifact_register(
        workspace=workspace,
        artifact_id="evidence",
        kind="evidence_matrix",
        relative_path="phases/phase-1/evidence.json",
        producer="operator",
        phase="1",
        dependencies=[],
        replace_existing=True,
    )

    records = {item["artifact_id"]: item for item in service.artifact_list(workspace)}
    assert records["outline"]["status"] == "stale"


def test_preflight_core_status_does_not_require_extraction_extras(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)

    report = service.preflight_check(workspace)

    assert report["python_supported"] is True
    assert report["workspace_writable"] is True
    assert "grobid" in report["tools"]


def test_human_gate_can_be_approved_and_workflow_completed(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    for phase in (PhaseId.PHASE_0, PhaseId.PHASE_1, PhaseId.PHASE_2A):
        service.phase_next(workspace=workspace, target=phase.value)
    WorkflowEngine.load(workspace).record_decision(
        "synthetic_scoping_protocol",
        {"rounds": 3},
        loop_counter=("mutual_scoping_rounds", 3),
    )
    for phase in (
        PhaseId.PHASE_2B,
        PhaseId.PHASE_2C,
        PhaseId.PHASE_2D,
        PhaseId.PHASE_2E,
    ):
        service.phase_next(workspace=workspace, target=phase.value)
    service.gate_approve(
        workspace=workspace,
        gate_id="phase_2e_outline",
        approved_by="operator",
    )
    for phase, gate_id in (
        (PhaseId.PHASE_3, None),
        (PhaseId.PHASE_4, None),
        (PhaseId.PHASE_5, "phase_5_citation"),
        (PhaseId.PHASE_6, "phase_6_review"),
        (PhaseId.PHASE_7, "phase_7_final"),
    ):
        service.phase_next(workspace=workspace, target=phase.value)
        if gate_id:
            service.gate_approve(workspace=workspace, gate_id=gate_id, approved_by="operator")

    for kind in (
        "source_manifest",
        "extraction_record",
        "scope_brief",
        "architecture_scorecard",
        "claim_matrix",
        "manuscript",
        "citation_audit",
        "review_report",
    ):
        path = workspace / "phases/phase-7" / f"{kind}.json"
        path.write_text(json.dumps({"kind": kind}) + "\n", encoding="utf-8")
        service.artifact_register(
            workspace=workspace,
            artifact_id=f"test-{kind}",
            kind=kind,
            relative_path=f"phases/phase-7/{kind}.json",
            producer="test",
            phase="7",
            dependencies=[],
        )
    service.reproducibility_bundle_create(workspace)

    completed = service.workflow_complete(workspace)

    assert completed["status"] == "COMPLETED"
    assert completed["decisions"]["gate:phase_7_final"]["approved_by"] == "operator"


def test_acquisition_request_can_be_created_and_listed(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)

    created = service.acquisition_request_create(
        workspace=workspace,
        request_payload={
            "request_id": "request-anchor-001",
            "title": "A complementary review",
            "doi": "10.1000/review",
            "authors": ["A. Author"],
            "year": 2024,
            "landing_url": "https://doi.org/10.1000/review",
            "priority": "P0",
            "reason": "Needed to test the nearest-review distinction",
            "affected_claim_ids": [],
            "evidence_type": "nearest review",
        },
    )

    assert created["status"] == "open"
    assert service.acquisition_request_list(workspace) == [created]


def test_acquisition_request_dismissal_requires_and_records_rationale(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    service.acquisition_request_create(
        workspace=workspace,
        request_payload={
            "request_id": "request-unavailable-001",
            "title": "Unavailable complementary review",
            "landing_url": "https://doi.org/10.1000/unavailable",
            "priority": "P1",
            "reason": "Potentially useful contrast",
            "evidence_type": "contrast",
        },
    )

    with pytest.raises(ValueError):
        service.acquisition_request_dismiss(
            workspace=workspace,
            request_id="request-unavailable-001",
            rationale="",
        )
    dismissed = service.acquisition_request_dismiss(
        workspace=workspace,
        request_id="request-unavailable-001",
        rationale="No lawful full text was available; retain metadata only and lower the claim.",
    )

    assert dismissed["status"] == "dismissed"
    assert dismissed["resolution_note"].startswith("No lawful full text")
    status = service.project_status(workspace)
    assert (
        status["decisions"]["acquisition_resolution:request-unavailable-001"]["status"]
        == "dismissed"
    )


def test_lawful_open_pdf_can_be_downloaded_validated_and_fulfill_request(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    initialize(service, workspace)
    service.acquisition_request_create(
        workspace=workspace,
        request_payload={
            "request_id": "request-open-001",
            "title": "Open complementary paper",
            "doi": "10.1000/open",
            "authors": [],
            "year": 2024,
            "landing_url": "https://example.org/article",
            "priority": "P1",
            "reason": "Needed for a contrasting interpretation",
            "affected_claim_ids": [],
            "evidence_type": "contrast",
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.org/article.pdf"
        return httpx.Response(
            200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-" + b"x" * 2048,
            request=request,
        )

    record = service.acquisition_download(
        workspace=workspace,
        request_id="request-open-001",
        pdf_url="https://example.org/article.pdf",
        expected_identity={"doi": "10.1000/open", "title": "Open complementary paper"},
        access_basis="open_access",
        license_or_terms="CC BY 4.0",
        observed_doi="10.1000/open",
        observed_title="Open complementary paper",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert Path(record["path"]).is_relative_to(workspace)
    assert record["matched_by"] == "doi"
    assert service.acquisition_request_list(workspace)[0]["status"] == "fulfilled"


def test_explicit_relocation_resumes_a_copied_workspace_without_mutating_original(
    tmp_path: Path,
) -> None:
    original = (tmp_path / "computer-a" / "workspace").resolve()
    moved = (tmp_path / "computer-b" / "workspace").resolve()
    service = WorkflowService()
    initialize(service, original)
    original_state = (original / "state.json").read_bytes()
    shutil.copytree(original, moved)

    with pytest.raises(ValueError, match="workspace_root"):
        service.project_status(moved)
    relocated = service.project_relocate(moved)

    assert Path(relocated["workspace_root"]) == moved
    assert relocated["events"][-1]["event_type"] == "workspace_relocated"
    assert (original / "state.json").read_bytes() == original_state
