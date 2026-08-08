from __future__ import annotations

import asyncio
from pathlib import Path

from review_workflow.application.service import WorkflowService
from review_workflow.mcp.server import mcp, project_status_tool

REQUIRED_TOOLS = {
    "project_init",
    "project_status",
    "project_relocate",
    "preflight_check",
    "phase_next",
    "gate_approve",
    "workflow_complete",
    "question_packet_open",
    "question_packet_get",
    "recommended_reading_acknowledge",
    "answer_packet_record",
    "artifact_register",
    "artifact_list",
    "return_route",
    "return_resume",
    "literature_discover",
    "literature_refresh_complete",
    "source_inventory",
    "evidence_search",
    "acquisition_request_list",
    "acquisition_request_create",
    "acquisition_download",
    "acquisition_download_open",
    "acquisition_request_dismiss",
    "acquisition_import",
    "privacy_decision_record",
    "reproducibility_bundle_create",
}


def test_mcp_exposes_small_declared_tool_surface_with_read_annotations() -> None:
    tools = asyncio.run(mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == REQUIRED_TOOLS
    assert by_name["project_status"].annotations.readOnlyHint is True
    assert by_name["project_init"].annotations.readOnlyHint is False
    assert by_name["source_inventory"].annotations.destructiveHint is False


def test_mcp_status_tool_matches_shared_service(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    service = WorkflowService()
    service.project_init(
        workspace=workspace,
        project_id="synthetic-review",
        review_type="technical",
        execution_profile="windows-lite",
        publication_mode="single",
    )

    assert project_status_tool(str(workspace)) == service.project_status(workspace)
