from __future__ import annotations

from review_workflow.domain.citation_audit import (
    BibliographicRecord,
    CitationAuditor,
    CitationOccurrence,
)
from review_workflow.domain.claims import (
    ClaimRecord,
    ClaimStrength,
    ClaimType,
    EvidenceBasis,
    EvidenceLink,
    StudyDesign,
    SupportDirection,
)
from review_workflow.domain.models import ExecutionProfile


def claim(
    *,
    claim_id: str = "claim-001",
    claim_type: ClaimType = ClaimType.OBSERVATION,
    strength: ClaimStrength = ClaimStrength.QUALIFIED,
    is_core: bool = False,
    source_id: str = "source-001",
    basis: EvidenceBasis = EvidenceBasis.FULL_TEXT,
    direction: SupportDirection = SupportDirection.SUPPORTS,
    locator: str | None = "p. 3, Methods",
    search_boundary: str | None = None,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        text="A deliberately bounded scientific claim.",
        claim_type=claim_type,
        strength=strength,
        is_core=is_core,
        evidence=[
            EvidenceLink(
                source_id=source_id,
                basis=basis,
                locator=locator,
                support_direction=direction,
                study_design=StudyDesign.EXPERIMENTAL,
                independence_group=source_id,
            )
        ],
        claim_ceiling="single-study observation",
        uncertainty="Generalisability remains uncertain.",
        search_boundary=search_boundary,
    )


def occurrence(**updates) -> CitationOccurrence:
    values = {
        "citation_id": "citation-001",
        "claim_id": "claim-001",
        "source_id": "source-001",
        "locator": "p. 3, Methods",
        "asserted_direction": SupportDirection.SUPPORTS,
        "claim_sentence_index": 10,
        "citation_sentence_index": 10,
    }
    values.update(updates)
    return CitationOccurrence(**values)


def source(source_id: str, **updates) -> BibliographicRecord:
    values = {
        "source_id": source_id,
        "title": f"Title for {source_id}",
        "doi": f"10.1000/{source_id}",
        "exists": True,
        "metadata_verified": True,
        "reference_listed": True,
    }
    values.update(updates)
    return BibliographicRecord(**values)


def audit(claims, citations, sources, profile=ExecutionProfile.FULL):
    return CitationAuditor.audit(
        claims=claims,
        citations=citations,
        sources=sources,
        execution_profile=profile,
    )


def test_correct_claim_citation_source_locator_and_direction_pass_automatic_checks() -> None:
    report = audit([claim()], [occurrence()], [source("source-001")])

    assert report.findings == []
    assert report.automatic_checks_passed is True
    assert report.requires_human_checkpoint is True


def test_wrong_source_and_wrong_locator_are_high_risk() -> None:
    report = audit(
        [claim()],
        [
            occurrence(citation_id="wrong-source", source_id="source-002"),
            occurrence(citation_id="wrong-locator", locator="p. 99"),
        ],
        [source("source-001"), source("source-002")],
    )

    assert "citation_source_not_linked_to_claim" in report.codes
    assert "citation_locator_mismatch" in report.codes
    assert report.high_risk_count >= 2


def test_support_direction_reversal_and_distant_citation_are_detected() -> None:
    report = audit(
        [claim(direction=SupportDirection.CONTRADICTS)],
        [occurrence(citation_sentence_index=13)],
        [source("source-001")],
    )

    assert "citation_direction_mismatch" in report.codes
    assert "citation_too_far_from_claim" in report.codes


def test_orphan_reference_and_unverified_existence_are_detected() -> None:
    report = audit(
        [claim()],
        [occurrence()],
        [
            source("source-001"),
            source("source-orphan", exists=False, metadata_verified=False),
        ],
    )

    assert "orphan_reference" in report.codes
    assert "reference_existence_unverified" in report.codes


def test_abstract_only_core_claim_and_absolute_novelty_are_forwarded_from_claim_gate() -> None:
    report = audit(
        [
            claim(claim_id="claim-core", is_core=True, basis=EvidenceBasis.ABSTRACT),
            claim(
                claim_id="claim-novelty",
                claim_type=ClaimType.NOVELTY,
                strength=ClaimStrength.ABSOLUTE,
            ),
        ],
        [],
        [source("source-001")],
    )

    assert "core_claim_requires_full_text" in report.codes
    assert "absolute_novelty_prohibited" in report.codes
    assert "novelty_search_boundary_missing" in report.codes


def test_windows_lite_requires_manual_bibliography_structure_check_even_when_clean() -> None:
    report = audit(
        [claim()],
        [occurrence()],
        [source("source-001")],
        profile=ExecutionProfile.WINDOWS_LITE,
    )

    assert "bibliography_and_intext_citation_structure" in report.mandatory_manual_checks
    assert report.requires_human_checkpoint is True
