from __future__ import annotations

from review_workflow.domain.claims import (
    ClaimGate,
    ClaimRecord,
    ClaimStrength,
    ClaimType,
    EvidenceBasis,
    EvidenceLink,
    StudyDesign,
    SupportDirection,
)


def evidence(
    source_id: str,
    *,
    basis: EvidenceBasis = EvidenceBasis.FULL_TEXT,
    locator: str | None = "p. 3, Methods",
    design: StudyDesign = StudyDesign.EXPERIMENTAL,
    group: str | None = None,
) -> EvidenceLink:
    return EvidenceLink(
        source_id=source_id,
        basis=basis,
        locator=locator,
        support_direction=SupportDirection.SUPPORTS,
        study_design=design,
        independence_group=group or source_id,
    )


def claim(**updates) -> ClaimRecord:
    values = {
        "claim_id": "claim-001",
        "text": "The method showed a qualified improvement in the reported experiment.",
        "claim_type": ClaimType.OBSERVATION,
        "strength": ClaimStrength.QUALIFIED,
        "is_core": False,
        "evidence": [evidence("source-001")],
        "claim_ceiling": "single-study observation",
        "uncertainty": "Generalisability has not been established.",
        "counterevidence": [],
        "prohibited_extrapolations": ["Do not call this a field-wide consensus."],
    }
    values.update(updates)
    return ClaimRecord(**values)


def test_core_claim_supported_only_by_abstract_is_rejected() -> None:
    result = ClaimGate.evaluate(
        claim(is_core=True, evidence=[evidence("source-001", basis=EvidenceBasis.ABSTRACT)])
    )

    assert result.eligible is False
    assert "core_claim_requires_full_text" in result.codes


def test_trend_claim_with_one_source_and_unqualified_strength_is_rejected() -> None:
    result = ClaimGate.evaluate(
        claim(
            claim_type=ClaimType.TREND,
            strength=ClaimStrength.STRONG,
            evidence=[evidence("source-001")],
        )
    )

    assert "multi_source_claim_requires_independent_sources" in result.codes


def test_locator_less_full_text_evidence_is_rejected() -> None:
    result = ClaimGate.evaluate(claim(evidence=[evidence("source-001", locator=None)]))

    assert "full_text_locator_missing" in result.codes


def test_causal_claim_requires_experimental_or_mechanistic_evidence() -> None:
    result = ClaimGate.evaluate(
        claim(
            claim_type=ClaimType.CAUSAL,
            strength=ClaimStrength.STRONG,
            evidence=[evidence("source-001", design=StudyDesign.OBSERVATIONAL)],
        )
    )

    assert "causal_claim_lacks_causal_design" in result.codes


def test_absolute_or_search_unbounded_novelty_claim_is_rejected() -> None:
    absolute = ClaimGate.evaluate(
        claim(claim_type=ClaimType.NOVELTY, strength=ClaimStrength.ABSOLUTE)
    )
    unbounded = ClaimGate.evaluate(claim(claim_type=ClaimType.NOVELTY, search_boundary=None))

    assert "absolute_novelty_prohibited" in absolute.codes
    assert "novelty_search_boundary_missing" in unbounded.codes


def test_qualified_single_study_observation_is_accepted() -> None:
    result = ClaimGate.evaluate(claim())

    assert result.eligible is True
    assert result.codes == []


def test_consensus_with_two_independent_full_text_sources_is_accepted() -> None:
    result = ClaimGate.evaluate(
        claim(
            claim_type=ClaimType.CONSENSUS,
            strength=ClaimStrength.STRONG,
            evidence=[
                evidence("source-001", group="lab-a"),
                evidence("source-002", group="lab-b"),
            ],
            counterevidence=["A minority study reports a boundary-condition exception."],
        )
    )

    assert result.eligible is True
