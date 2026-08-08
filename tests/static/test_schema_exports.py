from __future__ import annotations

import json
from pathlib import Path

from review_workflow.adapters.discovery import RecommendationCard
from review_workflow.adapters.extraction import ExtractionResult
from review_workflow.domain.citation_audit import CitationAuditReport
from review_workflow.domain.claims import ClaimRecord
from review_workflow.domain.loops import QuestionPacket, ReturnEvent, ScopeBrief
from review_workflow.domain.manuscript import SectionContract
from review_workflow.domain.models import AcquisitionRequest
from review_workflow.domain.review import ReviewFinding
from review_workflow.domain.scoring import ArchitectureCandidate
from review_workflow.domain.state import WorkflowStateV2

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = {
    "acquisition-request.schema.json": AcquisitionRequest,
    "architecture-candidate.schema.json": ArchitectureCandidate,
    "citation-audit.schema.json": CitationAuditReport,
    "claim-record.schema.json": ClaimRecord,
    "extraction-result.schema.json": ExtractionResult,
    "question-packet.schema.json": QuestionPacket,
    "recommendation-card.schema.json": RecommendationCard,
    "return-event.schema.json": ReturnEvent,
    "review-finding.schema.json": ReviewFinding,
    "scope-brief.schema.json": ScopeBrief,
    "section-contract.schema.json": SectionContract,
    "workflow-state-v2.schema.json": WorkflowStateV2,
}


def test_exported_json_schemas_match_canonical_pydantic_models() -> None:
    schema_root = ROOT / "schemas"

    assert {path.name for path in schema_root.glob("*.json")} == set(SCHEMAS)
    for filename, model in SCHEMAS.items():
        payload = json.loads((schema_root / filename).read_text(encoding="utf-8"))
        assert payload == model.model_json_schema()
