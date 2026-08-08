from __future__ import annotations

from pathlib import Path

from review_workflow.adapters.extraction import (
    ExtractionRouter,
    ExtractionTool,
    ToolAvailability,
    compute_extraction_id,
)
from review_workflow.domain.models import ExecutionProfile


def test_windows_lite_routes_pdf_without_grobid_and_requires_phase_5_manual_check() -> None:
    router = ExtractionRouter(
        profile=ExecutionProfile.WINDOWS_LITE,
        available_tools=ToolAvailability(
            markitdown=True,
            docling=True,
            grobid=False,
            pypdf=True,
        ),
    )

    plan = router.route(Path("article.pdf"))

    assert ExtractionTool.DOCLING in plan.parsers
    assert ExtractionTool.GROBID not in plan.parsers
    assert "bibliography_and_intext_citation_structure" in plan.mandatory_manual_checks
    assert "grobid_unavailable" in plan.degraded_capabilities


def test_full_profile_routes_pdf_through_docling_grobid_and_baseline() -> None:
    router = ExtractionRouter(
        profile=ExecutionProfile.FULL,
        available_tools=ToolAvailability(
            markitdown=True,
            docling=True,
            grobid=True,
            pypdf=True,
        ),
    )

    plan = router.route(Path("article.pdf"))

    assert plan.parsers == [
        ExtractionTool.DOCLING,
        ExtractionTool.GROBID,
        ExtractionTool.MARKITDOWN,
    ]
    assert plan.degraded_capabilities == []
    assert plan.mandatory_manual_checks == []


def test_docx_uses_markitdown_without_grobid_in_both_profiles() -> None:
    router = ExtractionRouter(
        profile=ExecutionProfile.FULL,
        available_tools=ToolAvailability(markitdown=True, docling=True, grobid=True, pypdf=True),
    )

    plan = router.route(Path("draft.docx"))

    assert plan.parsers == [ExtractionTool.MARKITDOWN]


def test_pdf_falls_back_to_pypdf_when_layout_tools_are_missing() -> None:
    router = ExtractionRouter(
        profile=ExecutionProfile.WINDOWS_LITE,
        available_tools=ToolAvailability(pypdf=True),
    )

    plan = router.route(Path("article.pdf"))

    assert plan.parsers == [ExtractionTool.PYPDF]
    assert "layout_figures_tables_may_be_incomplete" in plan.degraded_capabilities


def test_extraction_id_changes_with_parser_version_or_config() -> None:
    baseline = compute_extraction_id(
        source_hash="a" * 64,
        parser="docling",
        parser_version="2.0",
        parser_config={"ocr": True},
        schema_version=1,
    )
    changed_version = compute_extraction_id(
        source_hash="a" * 64,
        parser="docling",
        parser_version="2.1",
        parser_config={"ocr": True},
        schema_version=1,
    )
    changed_config = compute_extraction_id(
        source_hash="a" * 64,
        parser="docling",
        parser_version="2.0",
        parser_config={"ocr": False},
        schema_version=1,
    )

    assert len({baseline, changed_version, changed_config}) == 3
