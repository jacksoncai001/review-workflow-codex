from __future__ import annotations

import pytest

from review_workflow.domain.scoring import (
    ArchitectureCandidate,
    ArchitectureScorer,
    ArchitectureScores,
    GateFailure,
    select_winner,
)


def candidate(
    candidate_id: str,
    *,
    scores: ArchitectureScores,
    p0_gaps: list[str] | None = None,
    novelty_search_bounded: bool = True,
) -> ArchitectureCandidate:
    return ArchitectureCandidate(
        candidate_id=candidate_id,
        title=f"Candidate {candidate_id}",
        central_question="Which evidence supports which defensible diagnostic claim?",
        target_readers=["diagnostic researchers", "new engineering readers"],
        positioning_statement="Maps measurement assumptions to claim ceilings",
        unresolved_problem="Earlier reviews do not connect validation evidence to claim limits",
        scores=scores,
        rationales={
            dimension: "Evidence-backed rationale" for dimension in type(scores).model_fields
        },
        p0_evidence_gaps=p0_gaps or [],
        novelty_search_bounded=novelty_search_bounded,
        search_boundary="OpenAlex and Crossref search through 2026-08-07",
    )


def strong_scores() -> ArchitectureScores:
    return ArchitectureScores(
        reader_need=17,
        differentiation=22,
        unresolved_value=17,
        synthesis_actionability=12,
        evidence_feasibility=8,
        newcomer_accessibility=4,
        publication_fit=4,
    )


def test_weights_sum_to_100_and_strong_candidate_passes() -> None:
    card = ArchitectureScorer.score(candidate("strong", scores=strong_scores()))

    assert ArchitectureScorer.maximum_points() == {
        "reader_need": 20,
        "differentiation": 25,
        "unresolved_value": 20,
        "synthesis_actionability": 15,
        "evidence_feasibility": 10,
        "newcomer_accessibility": 5,
        "publication_fit": 5,
    }
    assert sum(ArchitectureScorer.maximum_points().values()) == 100
    assert card.total == 84
    assert card.eligible is True


def test_total_above_75_cannot_hide_weak_differentiation() -> None:
    scores = ArchitectureScores(
        reader_need=20,
        differentiation=10,
        unresolved_value=20,
        synthesis_actionability=15,
        evidence_feasibility=10,
        newcomer_accessibility=5,
        publication_fit=5,
    )

    card = ArchitectureScorer.score(candidate("generic-polished", scores=scores))

    assert card.total == 85
    assert card.eligible is False
    assert "differentiation_below_minimum" in card.failures


def test_p0_gap_and_unbounded_novelty_each_block_candidate() -> None:
    with_gap = ArchitectureScorer.score(
        candidate("gap", scores=strong_scores(), p0_gaps=["missing nearest review full text"])
    )
    unbounded = ArchitectureScorer.score(
        candidate("unbounded", scores=strong_scores(), novelty_search_bounded=False)
    )

    assert "unresolved_p0_evidence_gap" in with_gap.failures
    assert "novelty_not_search_bounded" in unbounded.failures


def test_distinctive_evidence_feasible_candidate_beats_polished_generic_candidate() -> None:
    distinctive = ArchitectureScorer.score(candidate("distinctive", scores=strong_scores()))
    generic = ArchitectureScorer.score(
        candidate(
            "generic",
            scores=ArchitectureScores(
                reader_need=20,
                differentiation=12,
                unresolved_value=20,
                synthesis_actionability=15,
                evidence_feasibility=10,
                newcomer_accessibility=5,
                publication_fit=5,
            ),
        )
    )

    winner = select_winner([generic, distinctive])

    assert winner == "distinctive"


def test_select_winner_rejects_portfolio_with_no_eligible_candidate() -> None:
    card = ArchitectureScorer.score(
        candidate(
            "weak",
            scores=ArchitectureScores(
                reader_need=10,
                differentiation=10,
                unresolved_value=10,
                synthesis_actionability=10,
                evidence_feasibility=8,
                newcomer_accessibility=4,
                publication_fit=4,
            ),
        )
    )

    with pytest.raises(GateFailure, match="No architecture"):
        select_winner([card])
