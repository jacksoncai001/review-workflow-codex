"""Export canonical Pydantic contracts as deterministic JSON Schema files."""

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


def main() -> None:
    schema_root = Path(__file__).resolve().parents[1] / "schemas"
    schema_root.mkdir(parents=True, exist_ok=True)
    expected = set(SCHEMAS)
    for existing in schema_root.glob("*.json"):
        if existing.name not in expected:
            existing.unlink()
    for filename, model in SCHEMAS.items():
        payload = json.dumps(
            model.model_json_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        (schema_root / filename).write_text(payload + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
