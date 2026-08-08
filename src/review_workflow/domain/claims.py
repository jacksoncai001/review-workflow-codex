"""Phase 3 claim-level evidence contracts and scientific claim ceilings."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from review_workflow.domain.models import StrictModel
from review_workflow.domain.phases import PhaseId


class ClaimType(StrEnum):
    DEFINITION = "definition"
    OBSERVATION = "observation"
    COMPARISON = "comparison"
    TREND = "trend"
    CONSENSUS = "consensus"
    CAUSAL = "causal"
    NOVELTY = "novelty"


class ClaimStrength(StrEnum):
    TENTATIVE = "tentative"
    QUALIFIED = "qualified"
    STRONG = "strong"
    ABSOLUTE = "absolute"


class EvidenceBasis(StrEnum):
    FULL_TEXT = "full_text"
    ABSTRACT = "abstract"
    METADATA = "metadata"


class SupportDirection(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"


class StudyDesign(StrEnum):
    EXPERIMENTAL = "experimental"
    MECHANISTIC = "mechanistic"
    OBSERVATIONAL = "observational"
    SIMULATION = "simulation"
    REVIEW = "review"
    UNKNOWN = "unknown"


class EvidenceLink(StrictModel):
    source_id: str
    basis: EvidenceBasis
    locator: str | None = None
    support_direction: SupportDirection
    study_design: StudyDesign = StudyDesign.UNKNOWN
    independence_group: str | None = None


class ClaimRecord(StrictModel):
    schema_version: int = 1
    claim_id: str
    text: str = Field(min_length=3)
    claim_type: ClaimType
    strength: ClaimStrength
    is_core: bool = False
    evidence: list[EvidenceLink] = Field(default_factory=list)
    claim_ceiling: str = Field(min_length=3)
    uncertainty: str = Field(min_length=3)
    counterevidence: list[str] = Field(default_factory=list)
    prohibited_extrapolations: list[str] = Field(default_factory=list)
    search_boundary: str | None = None


class ClaimFinding(StrictModel):
    code: str
    message: str
    severity: str = "error"
    repair_phase: PhaseId = PhaseId.PHASE_3


class ClaimGateResult(StrictModel):
    claim_id: str
    eligible: bool
    findings: list[ClaimFinding] = Field(default_factory=list)

    @property
    def codes(self) -> list[str]:
        return [finding.code for finding in self.findings]


class ClaimGate:
    """Evaluate evidence basis, independence, locator, and claim-type ceilings."""

    @staticmethod
    def evaluate(claim: ClaimRecord) -> ClaimGateResult:
        findings: list[ClaimFinding] = []
        supporting = [
            link
            for link in claim.evidence
            if link.support_direction in {SupportDirection.SUPPORTS, SupportDirection.MIXED}
        ]
        full_text_support = [link for link in supporting if link.basis is EvidenceBasis.FULL_TEXT]

        if claim.is_core and not full_text_support:
            findings.append(
                ClaimFinding(
                    code="core_claim_requires_full_text",
                    message="A core claim needs supporting verified full text.",
                )
            )
        if any(
            link.basis is EvidenceBasis.FULL_TEXT and not link.locator for link in claim.evidence
        ):
            findings.append(
                ClaimFinding(
                    code="full_text_locator_missing",
                    message=(
                        "Every full-text evidence link needs a page/section/table/figure locator."
                    ),
                )
            )
        if claim.claim_type in {ClaimType.TREND, ClaimType.CONSENSUS}:
            independent = {link.independence_group or link.source_id for link in full_text_support}
            if len(independent) < 2 and claim.strength not in {
                ClaimStrength.TENTATIVE,
                ClaimStrength.QUALIFIED,
            }:
                findings.append(
                    ClaimFinding(
                        code="multi_source_claim_requires_independent_sources",
                        message=(
                            "A strong trend or consensus requires at least two independent "
                            "full-text sources."
                        ),
                    )
                )
        if claim.claim_type is ClaimType.CAUSAL:
            causal_support = [
                link
                for link in full_text_support
                if link.study_design in {StudyDesign.EXPERIMENTAL, StudyDesign.MECHANISTIC}
            ]
            if not causal_support:
                findings.append(
                    ClaimFinding(
                        code="causal_claim_lacks_causal_design",
                        message=(
                            "A causal claim needs experimental or mechanistic full-text evidence."
                        ),
                    )
                )
        if claim.claim_type is ClaimType.NOVELTY:
            if claim.strength is ClaimStrength.ABSOLUTE:
                findings.append(
                    ClaimFinding(
                        code="absolute_novelty_prohibited",
                        message="Global first-ever or no-prior-work novelty claims are prohibited.",
                    )
                )
            if not claim.search_boundary:
                findings.append(
                    ClaimFinding(
                        code="novelty_search_boundary_missing",
                        message="A novelty claim must name its bounded search basis and date.",
                    )
                )
        if not supporting:
            findings.append(
                ClaimFinding(
                    code="supporting_evidence_missing",
                    message="The claim has no supporting or mixed-direction evidence link.",
                )
            )
        return ClaimGateResult(
            claim_id=claim.claim_id,
            eligible=not findings,
            findings=findings,
        )
