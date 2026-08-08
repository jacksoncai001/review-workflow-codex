"""Phase 0 search-lane fusion, recommendation, and acquisition-request policy."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from review_workflow.adapters.discovery import (
    CandidateWork,
    RecommendationCard,
    RecommendationRole,
    WorkRecord,
)
from review_workflow.domain.models import (
    AcquisitionPriority,
    AcquisitionRequest,
    AcquisitionRoute,
)


class DiscoveryService:
    """Deterministic selection policy over semantically scored candidates."""

    @staticmethod
    def rank_recommendations(
        candidates: list[CandidateWork],
        *,
        count: int = 3,
    ) -> list[RecommendationCard]:
        if count not in {2, 3}:
            raise ValueError("Recommendation count must be 2 or 3")
        if len(candidates) < count:
            raise ValueError(f"At least {count} candidates are required")
        selected: list[tuple[RecommendationRole, CandidateWork]] = []
        remaining = list(candidates)

        review_candidates = [candidate for candidate in remaining if candidate.is_review]
        anchor_pool = review_candidates or remaining
        anchor = max(anchor_pool, key=lambda candidate: candidate.relevance_score)
        selected.append((RecommendationRole.ANCHOR, anchor))
        remaining.remove(anchor)

        contrast = max(
            remaining,
            key=lambda candidate: (candidate.contrast_score, candidate.relevance_score),
        )
        selected.append((RecommendationRole.CONTRAST, contrast))
        remaining.remove(contrast)

        if count == 3:
            bridge = max(
                remaining,
                key=lambda candidate: (candidate.bridge_score, candidate.relevance_score),
            )
            selected.append((RecommendationRole.BRIDGE, bridge))

        return [DiscoveryService._card(role, candidate) for role, candidate in selected]

    @staticmethod
    def search_lanes(
        queries: list[str],
        *,
        clients: list[Any],
        count: int = 3,
    ) -> list[RecommendationCard]:
        """Fuse multiple databases and query lanes before role-diverse selection."""
        if not queries:
            raise ValueError("At least one literature search lane is required")
        if not clients:
            raise ValueError("At least one bibliographic client is required")
        records: dict[str, WorkRecord] = {}
        matched_queries: dict[str, set[str]] = {}
        for query in queries:
            for client in clients:
                for work in client.search(query):
                    key = work.doi or _normalized_title(work.title)
                    existing = records.get(key)
                    if existing is None or _record_richness(work) > _record_richness(existing):
                        records[key] = work
                    matched_queries.setdefault(key, set()).add(query)
        candidates = [
            _candidate_from_record(record, queries, matched_queries[key])
            for key, record in records.items()
        ]
        return DiscoveryService.rank_recommendations(candidates, count=count)

    @staticmethod
    def build_acquisition_requests(
        cards: list[RecommendationCard],
    ) -> list[AcquisitionRequest]:
        """Give every recommendation a durable automatic or operator acquisition route."""
        requests: list[AcquisitionRequest] = []
        for card in cards:
            identity = card.doi or card.work_id
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
            automatic_open = bool(card.oa_url and card.oa_license)
            if automatic_open:
                landing_url = card.oa_url
            elif card.doi:
                landing_url = f"https://doi.org/{card.doi}"
            elif card.work_id.startswith(("https://", "http://")):
                landing_url = card.work_id
            else:
                landing_url = f"https://openalex.org/{card.work_id.removeprefix('W')}"
            priority = (
                AcquisitionPriority.P0
                if card.role is RecommendationRole.ANCHOR
                else AcquisitionPriority.P1
            )
            requests.append(
                AcquisitionRequest(
                    request_id=f"acq-{digest}",
                    title=card.title,
                    doi=card.doi,
                    landing_url=landing_url,
                    priority=priority,
                    reason=(
                        f"Recommended as {card.role.value}; "
                        + (
                            "a licensed open full-text location is queued for automatic download."
                            if automatic_open
                            else "no licensed open full-text PDF location was recorded, so the "
                            "operator must supply or dismiss it."
                        )
                    ),
                    evidence_type=f"{card.role.value.lower()} recommendation",
                    route=(
                        AcquisitionRoute.AUTOMATIC_OPEN
                        if automatic_open
                        else AcquisitionRoute.OPERATOR_SUPPLY
                    ),
                    pdf_url=card.oa_url if automatic_open else None,
                    access_basis="open_access" if automatic_open else None,
                    license_or_terms=card.oa_license if automatic_open else None,
                    version=card.oa_version if automatic_open else None,
                )
            )
        return requests

    @staticmethod
    def _card(role: RecommendationRole, candidate: CandidateWork) -> RecommendationCard:
        role_reason = {
            RecommendationRole.ANCHOR: (
                "It is the closest review or framing reference for the proposed scope."
            ),
            RecommendationRole.CONTRAST: (
                "It supplies a contrasting interpretation or exposes an important limitation."
            ),
            RecommendationRole.BRIDGE: (
                "It connects the review question to a necessary method, validation, or foundation."
            ),
        }[role]
        change = {
            RecommendationRole.ANCHOR: (
                "Refine the boundary and state the distinction from the nearest review."
            ),
            RecommendationRole.CONTRAST: (
                "Add counterevidence, a limitation, or an alternative organizing axis."
            ),
            RecommendationRole.BRIDGE: (
                "Strengthen the explanation linking concepts, measurements, and claims."
            ),
        }[role]
        return RecommendationCard(
            role=role,
            work_id=candidate.work_id,
            title=candidate.title,
            doi=candidate.doi,
            why_it_matters=role_reason,
            relationship_to_draft=(
                f"Candidate {candidate.work_id} has relevance score "
                f"{candidate.relevance_score:.3f}."
            ),
            what_it_may_change=change,
            sections_to_read=["abstract", "introduction", "discussion/conclusion"],
            challenges=(
                "Read for assumptions, validation limits, and claims that conflict with the draft."
            ),
            oa_status=candidate.oa_status,
            oa_url=candidate.oa_url,
            basis=candidate.basis,
        )


def _normalized_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))


def _record_richness(record: WorkRecord) -> tuple[int, int, int]:
    return (bool(record.abstract), len(record.authors), record.cited_by_count)


def _candidate_from_record(
    record: WorkRecord,
    queries: list[str],
    matched_queries: set[str],
) -> CandidateWork:
    material = " ".join([record.title, record.abstract or "", *record.topics]).lower()
    query_tokens = {
        token
        for query in queries
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2
    }
    overlap = sum(token in material for token in query_tokens)
    lexical = overlap / max(len(query_tokens), 1)
    lane_coverage = len(matched_queries) / len(queries)
    relevance = min(1.0, 0.75 * lexical + 0.25 * lane_coverage)
    contrast_terms = ("limit", "conflict", "challenge", "comparison", "bias", "failure")
    bridge_terms = ("method", "validation", "experiment", "measurement", "foundation", "mechanism")
    contrast = sum(term in material for term in contrast_terms) / len(contrast_terms)
    bridge = sum(term in material for term in bridge_terms) / len(bridge_terms)
    return CandidateWork(
        work_id=record.work_id,
        title=record.title,
        doi=record.doi,
        authors=record.authors,
        year=record.year,
        relevance_score=relevance,
        contrast_score=contrast,
        bridge_score=bridge,
        is_review=record.is_review,
        oa_status=record.oa_status or "unknown",
        oa_url=record.oa_url,
        basis="abstract" if record.abstract else "metadata",
    )
