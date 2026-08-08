"""Frozen Phase 2 architecture rubric centered on distinctive review value."""

from __future__ import annotations

from pydantic import Field

from review_workflow.domain.models import StrictModel


class GateFailure(ValueError):
    """Raised when no architecture satisfies the scientific gate."""


class ArchitectureScores(StrictModel):
    reader_need: float = Field(ge=0, le=20)
    differentiation: float = Field(ge=0, le=25)
    unresolved_value: float = Field(ge=0, le=20)
    synthesis_actionability: float = Field(ge=0, le=15)
    evidence_feasibility: float = Field(ge=0, le=10)
    newcomer_accessibility: float = Field(ge=0, le=5)
    publication_fit: float = Field(ge=0, le=5)


class ArchitectureCandidate(StrictModel):
    schema_version: int = 1
    candidate_id: str
    title: str
    central_question: str
    target_readers: list[str] = Field(min_length=1)
    positioning_statement: str
    unresolved_problem: str
    scores: ArchitectureScores
    rationales: dict[str, str]
    p0_evidence_gaps: list[str] = Field(default_factory=list)
    novelty_search_bounded: bool
    search_boundary: str


class ScoreCard(StrictModel):
    candidate_id: str
    dimensions: ArchitectureScores
    total: float
    eligible: bool
    failures: list[str] = Field(default_factory=list)
    rationales: dict[str, str]


class ArchitectureScorer:
    """Compute the frozen 100-point rubric and non-compensable thresholds."""

    _maximum = {
        "reader_need": 20,
        "differentiation": 25,
        "unresolved_value": 20,
        "synthesis_actionability": 15,
        "evidence_feasibility": 10,
        "newcomer_accessibility": 5,
        "publication_fit": 5,
    }
    _minimum = {
        "reader_need": 14,
        "differentiation": 18,
        "unresolved_value": 14,
    }

    @classmethod
    def maximum_points(cls) -> dict[str, int]:
        return dict(cls._maximum)

    @classmethod
    def score(cls, candidate: ArchitectureCandidate) -> ScoreCard:
        values = candidate.scores.model_dump()
        total = sum(values.values())
        failures: list[str] = []
        if total < 75:
            failures.append("total_below_75")
        for dimension, threshold in cls._minimum.items():
            if values[dimension] < threshold:
                failures.append(f"{dimension}_below_minimum")
        if candidate.p0_evidence_gaps:
            failures.append("unresolved_p0_evidence_gap")
        if not candidate.novelty_search_bounded or not candidate.search_boundary.strip():
            failures.append("novelty_not_search_bounded")
        missing_rationales = set(cls._maximum) - {
            key for key, value in candidate.rationales.items() if value.strip()
        }
        if missing_rationales:
            failures.append("score_rationale_missing")
        return ScoreCard(
            candidate_id=candidate.candidate_id,
            dimensions=candidate.scores,
            total=total,
            eligible=not failures,
            failures=failures,
            rationales=candidate.rationales,
        )


def select_winner(scorecards: list[ScoreCard]) -> str:
    eligible = [card for card in scorecards if card.eligible]
    if not eligible:
        raise GateFailure("No architecture satisfies the Phase 2 scientific gate")
    eligible.sort(key=lambda card: (-card.total, card.candidate_id))
    return eligible[0].candidate_id
