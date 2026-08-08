"""Small, explicit local MCP surface for Codex orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from review_workflow.application.service import WorkflowService

INSTRUCTIONS = (
    "Local-first review workflow for narrative, critical, and technical reviews. "
    "Original PDFs and drafts are read-only inputs. Write generated artifacts only inside the "
    "configured review workspace. Use project_status before mutations, honor WAITING_USER and "
    "WAITING_ACQUISITION, and never send full text or draft prose externally without a recorded "
    "disclosure. Resume from state.json; do not infer a later phase from chat history."
)

mcp = FastMCP("review-workflow-codex", instructions=INSTRUCTIONS)
service = WorkflowService()

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
LOCAL_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=False,
)


@mcp.tool(name="project_init", annotations=LOCAL_WRITE)
def project_init_tool(
    workspace: str,
    project_id: str,
    review_type: str,
    execution_profile: str = "windows-lite",
    publication_mode: str = "single",
) -> dict[str, Any]:
    """Create an isolated workspace and schema-v2 state."""
    return service.project_init(
        workspace=Path(workspace),
        project_id=project_id,
        review_type=review_type,
        execution_profile=execution_profile,
        publication_mode=publication_mode,
    )


@mcp.tool(name="project_status", annotations=READ_ONLY)
def project_status_tool(workspace: str) -> dict[str, Any]:
    """Read the canonical resumable project state."""
    return service.project_status(Path(workspace))


@mcp.tool(name="project_relocate", annotations=LOCAL_WRITE)
def project_relocate_tool(workspace: str) -> dict[str, Any]:
    """Rebind a copied workspace to a new absolute path and record the migration."""
    return service.project_relocate(Path(workspace))


@mcp.tool(name="preflight_check", annotations=READ_ONLY)
def preflight_check_tool(workspace: str) -> dict[str, Any]:
    """Inspect runtime and extraction-service availability."""
    return service.preflight_check(Path(workspace))


@mcp.tool(name="phase_next", annotations=LOCAL_WRITE)
def phase_next_tool(workspace: str, target: str) -> dict[str, Any]:
    """Advance exactly one legal workflow phase."""
    return service.phase_next(workspace=Path(workspace), target=target)


@mcp.tool(name="gate_approve", annotations=LOCAL_WRITE)
def gate_approve_tool(workspace: str, gate_id: str, approved_by: str) -> dict[str, Any]:
    """Record the operator's explicit approval at the current mandatory checkpoint."""
    return service.gate_approve(
        workspace=Path(workspace),
        gate_id=gate_id,
        approved_by=approved_by,
    )


@mcp.tool(name="workflow_complete", annotations=LOCAL_WRITE)
def workflow_complete_tool(workspace: str) -> dict[str, Any]:
    """Mark a Phase 7 workflow complete after final operator approval."""
    return service.workflow_complete(Path(workspace))


@mcp.tool(name="question_packet_open", annotations=LOCAL_WRITE)
def question_packet_open_tool(workspace: str, codex_questions: list[str]) -> dict[str, Any]:
    """Open the next three-to-five-question Codex half of a reciprocal round."""
    return service.question_packet_open(Path(workspace), codex_questions)


@mcp.tool(name="question_packet_get", annotations=READ_ONLY)
def question_packet_get_tool(workspace: str) -> dict[str, Any]:
    """Read the outstanding question packet."""
    return service.question_packet_get(Path(workspace))


@mcp.tool(name="recommended_reading_acknowledge", annotations=LOCAL_WRITE)
def recommended_reading_acknowledge_tool(
    workspace: str,
    packet_id: str,
    reading_notes: list[str],
) -> dict[str, Any]:
    """Record the operator's reading notes and resume the exact saved workflow action."""
    return service.recommended_reading_acknowledge(
        workspace=Path(workspace),
        packet_id=packet_id,
        reading_notes=reading_notes,
    )


@mcp.tool(name="answer_packet_record", annotations=LOCAL_WRITE)
def answer_packet_record_tool(
    workspace: str,
    packet_id: str,
    answer_payload: dict[str, Any],
) -> dict[str, Any]:
    """Validate both sides of one reciprocal round and resume its exact saved action."""
    return service.answer_packet_record(
        workspace=Path(workspace),
        packet_id=packet_id,
        answer_payload=answer_payload,
    )


@mcp.tool(name="artifact_register", annotations=LOCAL_WRITE)
def artifact_register_tool(
    workspace: str,
    artifact_id: str,
    kind: str,
    relative_path: str,
    producer: str,
    phase: str,
    dependencies: list[str],
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Hash and register a generated artifact with explicit dependencies."""
    return service.artifact_register(
        workspace=Path(workspace),
        artifact_id=artifact_id,
        kind=kind,
        relative_path=relative_path,
        producer=producer,
        phase=phase,
        dependencies=dependencies,
        replace_existing=replace_existing,
    )


@mcp.tool(name="artifact_list", annotations=READ_ONLY)
def artifact_list_tool(workspace: str) -> list[dict[str, Any]]:
    """List registered artifacts and their validity status."""
    return service.artifact_list(Path(workspace))


@mcp.tool(name="return_route", annotations=LOCAL_WRITE)
def return_route_tool(workspace: str, failure_payload: dict[str, Any]) -> dict[str, Any]:
    """Route a failure to its earliest repair phase and invalidate dependants."""
    return service.return_route(workspace=Path(workspace), failure_payload=failure_payload)


@mcp.tool(name="return_resume", annotations=LOCAL_WRITE)
def return_resume_tool(
    workspace: str,
    failure_id: str,
    resolution_note: str,
    evidence_artifact_ids: list[str],
) -> dict[str, Any]:
    """Verify repair evidence against the stop condition and resume the saved action."""
    return service.return_resume(
        workspace=Path(workspace),
        failure_id=failure_id,
        resolution_note=resolution_note,
        evidence_artifact_ids=evidence_artifact_ids,
    )


@mcp.tool(name="literature_discover", annotations=LOCAL_WRITE)
def literature_discover_tool(
    workspace: str,
    search_lanes: list[str],
    count: int = 3,
) -> dict[str, Any]:
    """Recommend two or three papers, auto-fetch licensed OA files, and queue the rest."""
    return service.literature_discover(
        workspace=Path(workspace),
        search_lanes=search_lanes,
        count=count,
    )


@mcp.tool(name="literature_refresh_complete", annotations=LOCAL_WRITE)
def literature_refresh_complete_tool(workspace: str, refresh_id: str) -> dict[str, Any]:
    """Merge resolved acquisitions and open the required recommendation-reading wait."""
    return service.literature_refresh_complete(
        workspace=Path(workspace),
        refresh_id=refresh_id,
    )


@mcp.tool(name="source_inventory", annotations=LOCAL_WRITE)
def source_inventory_tool(
    workspace: str,
    input_paths: list[str],
    run_extraction: bool = False,
) -> dict[str, Any]:
    """Hash read-only inputs and optionally build reusable local extractions and search index."""
    return service.source_inventory(
        workspace=Path(workspace),
        input_paths=input_paths,
        run_extraction=run_extraction,
    )


@mcp.tool(name="evidence_search", annotations=READ_ONLY)
def evidence_search_tool(workspace: str, query: str, top_k: int = 20) -> list[dict[str, Any]]:
    """Search local extracted chunks with page and section locators."""
    return service.evidence_search(workspace=Path(workspace), query=query, top_k=top_k)


@mcp.tool(name="acquisition_request_list", annotations=READ_ONLY)
def acquisition_request_list_tool(workspace: str) -> list[dict[str, Any]]:
    """List open, fulfilled, and dismissed acquisition requests."""
    return service.acquisition_request_list(Path(workspace))


@mcp.tool(name="acquisition_request_create", annotations=LOCAL_WRITE)
def acquisition_request_create_tool(
    workspace: str,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a traceable operator request for an inaccessible full-text source."""
    return service.acquisition_request_create(
        workspace=Path(workspace),
        request_payload=request_payload,
    )


@mcp.tool(name="acquisition_request_dismiss", annotations=LOCAL_WRITE)
def acquisition_request_dismiss_tool(
    workspace: str,
    request_id: str,
    rationale: str,
) -> dict[str, Any]:
    """Dismiss an unobtainable paper with a durable scientific rationale."""
    return service.acquisition_request_dismiss(
        workspace=Path(workspace),
        request_id=request_id,
        rationale=rationale,
    )


@mcp.tool(name="acquisition_import", annotations=LOCAL_WRITE)
def acquisition_import_tool(
    workspace: str,
    request_id: str,
    relative_path: str,
    expected_identity: dict[str, Any],
    download_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Validate an imported lawful PDF and fulfill its acquisition request."""
    return service.acquisition_import(
        workspace=Path(workspace),
        request_id=request_id,
        relative_path=relative_path,
        expected_identity=expected_identity,
        download_metadata=download_metadata,
    )


@mcp.tool(name="acquisition_download", annotations=LOCAL_WRITE)
def acquisition_download_tool(
    workspace: str,
    request_id: str,
    pdf_url: str,
    expected_identity: dict[str, Any],
    access_basis: str,
    license_or_terms: str,
    observed_doi: str | None = None,
    observed_title: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """Download and validate an explicitly lawful open PDF without login or paywall bypass."""
    return service.acquisition_download(
        workspace=Path(workspace),
        request_id=request_id,
        pdf_url=pdf_url,
        expected_identity=expected_identity,
        access_basis=access_basis,
        license_or_terms=license_or_terms,
        observed_doi=observed_doi,
        observed_title=observed_title,
        version=version,
    )


@mcp.tool(name="acquisition_download_open", annotations=LOCAL_WRITE)
def acquisition_download_open_tool(workspace: str, request_id: str) -> dict[str, Any]:
    """Download using the licensed open location already recorded by discovery."""
    return service.acquisition_download_open(
        workspace=Path(workspace),
        request_id=request_id,
    )


@mcp.tool(name="privacy_decision_record", annotations=LOCAL_WRITE)
def privacy_decision_record_tool(
    workspace: str,
    record_payload: dict[str, Any],
) -> dict[str, Any]:
    """Append explicit consent for external full-text or draft disclosure."""
    return service.privacy_decision_record(
        workspace=Path(workspace),
        record_payload=record_payload,
    )


@mcp.tool(name="reproducibility_bundle_create", annotations=LOCAL_WRITE)
def reproducibility_bundle_create_tool(workspace: str) -> dict[str, Any]:
    """Validate Phase 7 artifact coverage and write a migration-ready bundle manifest."""
    return service.reproducibility_bundle_create(Path(workspace))


def main() -> None:
    """Run the local stdio MCP server."""
    mcp.run(transport="stdio")
