"""Phase 5 structural and semantic claim-to-citation audit."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from review_workflow.domain.claims import (
    ClaimGate,
    ClaimRecord,
    SupportDirection,
)
from review_workflow.domain.models import ExecutionProfile, StrictModel
from review_workflow.domain.phases import PhaseId


class AuditRisk(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CitationOccurrence(StrictModel):
    citation_id: str
    claim_id: str
    source_id: str
    locator: str | None = None
    asserted_direction: SupportDirection
    claim_sentence_index: int = Field(ge=0)
    citation_sentence_index: int = Field(ge=0)


class BibliographicRecord(StrictModel):
    source_id: str
    title: str
    doi: str | None = None
    exists: bool
    metadata_verified: bool
    reference_listed: bool


class CitationAuditFinding(StrictModel):
    code: str
    risk: AuditRisk
    message: str
    repair_phase: PhaseId
    claim_id: str | None = None
    citation_id: str | None = None
    source_id: str | None = None


class CitationAuditReport(StrictModel):
    schema_version: int = 1
    findings: list[CitationAuditFinding] = Field(default_factory=list)
    automatic_checks_passed: bool
    requires_human_checkpoint: bool = True
    mandatory_manual_checks: list[str] = Field(default_factory=list)

    @property
    def codes(self) -> list[str]:
        return [finding.code for finding in self.findings]

    @property
    def high_risk_count(self) -> int:
        return sum(finding.risk is AuditRisk.HIGH for finding in self.findings)


class CitationAuditor:
    """Audit machine-checkable alignment and surface semantic checks for Phase 5."""

    @staticmethod
    def audit(
        *,
        claims: list[ClaimRecord],
        citations: list[CitationOccurrence],
        sources: list[BibliographicRecord],
        execution_profile: ExecutionProfile,
    ) -> CitationAuditReport:
        findings: list[CitationAuditFinding] = []
        claims_by_id = {claim.claim_id: claim for claim in claims}
        sources_by_id = {source.source_id: source for source in sources}

        for claim in claims:
            gate = ClaimGate.evaluate(claim)
            for claim_finding in gate.findings:
                findings.append(
                    CitationAuditFinding(
                        code=claim_finding.code,
                        risk=AuditRisk.HIGH,
                        message=claim_finding.message,
                        repair_phase=claim_finding.repair_phase,
                        claim_id=claim.claim_id,
                    )
                )

        cited_source_ids: set[str] = set()
        for citation in citations:
            cited_source_ids.add(citation.source_id)
            claim = claims_by_id.get(citation.claim_id)
            if claim is None:
                findings.append(
                    CitationAuditFinding(
                        code="citation_claim_unknown",
                        risk=AuditRisk.HIGH,
                        message="Citation points to an unknown claim ID.",
                        repair_phase=PhaseId.PHASE_3,
                        citation_id=citation.citation_id,
                    )
                )
                continue
            source = sources_by_id.get(citation.source_id)
            if source is None:
                findings.append(
                    CitationAuditFinding(
                        code="citation_source_unknown",
                        risk=AuditRisk.HIGH,
                        message=(
                            "Citation points to a source absent from the canonical bibliography."
                        ),
                        repair_phase=PhaseId.PHASE_0,
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        source_id=citation.source_id,
                    )
                )
                continue
            links = [link for link in claim.evidence if link.source_id == citation.source_id]
            if not links:
                findings.append(
                    CitationAuditFinding(
                        code="citation_source_not_linked_to_claim",
                        risk=AuditRisk.HIGH,
                        message="The cited source is not an evidence link for this claim.",
                        repair_phase=PhaseId.PHASE_3,
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        source_id=citation.source_id,
                    )
                )
            else:
                if citation.locator and not any(
                    link.locator == citation.locator for link in links if link.locator
                ):
                    findings.append(
                        CitationAuditFinding(
                            code="citation_locator_mismatch",
                            risk=AuditRisk.HIGH,
                            message="Citation locator does not match the claim evidence locator.",
                            repair_phase=PhaseId.PHASE_3,
                            claim_id=claim.claim_id,
                            citation_id=citation.citation_id,
                            source_id=citation.source_id,
                        )
                    )
                if not any(link.support_direction == citation.asserted_direction for link in links):
                    findings.append(
                        CitationAuditFinding(
                            code="citation_direction_mismatch",
                            risk=AuditRisk.HIGH,
                            message=(
                                "Citation support direction conflicts with the evidence record."
                            ),
                            repair_phase=PhaseId.PHASE_3,
                            claim_id=claim.claim_id,
                            citation_id=citation.citation_id,
                            source_id=citation.source_id,
                        )
                    )
            if abs(citation.claim_sentence_index - citation.citation_sentence_index) > 1:
                findings.append(
                    CitationAuditFinding(
                        code="citation_too_far_from_claim",
                        risk=AuditRisk.MEDIUM,
                        message="Citation is more than one sentence away from the mapped claim.",
                        repair_phase=PhaseId.PHASE_4,
                        claim_id=claim.claim_id,
                        citation_id=citation.citation_id,
                        source_id=citation.source_id,
                    )
                )

        for source in sources:
            if not source.exists or not source.metadata_verified:
                findings.append(
                    CitationAuditFinding(
                        code="reference_existence_unverified",
                        risk=AuditRisk.HIGH,
                        message="Reference existence or authoritative metadata is unverified.",
                        repair_phase=PhaseId.PHASE_0,
                        source_id=source.source_id,
                    )
                )
            if source.reference_listed and source.source_id not in cited_source_ids:
                findings.append(
                    CitationAuditFinding(
                        code="orphan_reference",
                        risk=AuditRisk.MEDIUM,
                        message="Reference-list entry has no mapped in-text citation.",
                        repair_phase=PhaseId.PHASE_5,
                        source_id=source.source_id,
                    )
                )
            if source.source_id in cited_source_ids and not source.reference_listed:
                findings.append(
                    CitationAuditFinding(
                        code="cited_source_missing_from_reference_list",
                        risk=AuditRisk.HIGH,
                        message="A cited source is absent from the reference list.",
                        repair_phase=PhaseId.PHASE_5,
                        source_id=source.source_id,
                    )
                )

        manual_checks = []
        if execution_profile is ExecutionProfile.WINDOWS_LITE:
            manual_checks.append("bibliography_and_intext_citation_structure")
        blocking = [
            finding for finding in findings if finding.risk in {AuditRisk.HIGH, AuditRisk.MEDIUM}
        ]
        return CitationAuditReport(
            findings=findings,
            automatic_checks_passed=not blocking,
            mandatory_manual_checks=manual_checks,
        )
