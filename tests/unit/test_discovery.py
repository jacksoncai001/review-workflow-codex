from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from review_workflow.adapters.discovery import (
    CandidateWork,
    CrossrefClient,
    DiscoveryConfigurationError,
    OpenAlexClient,
    RecommendationRole,
    UnpaywallClient,
    WorkRecord,
)
from review_workflow.application.discovery_service import DiscoveryService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "api"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_openalex_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)

    with pytest.raises(DiscoveryConfigurationError, match="OPENALEX_API_KEY"):
        OpenAlexClient(cache_dir=tmp_path)


def test_openalex_normalizes_results_and_uses_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "secret-openalex-key")
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["api_key"] == "secret-openalex-key"
        return httpx.Response(200, json=fixture("openalex-works.json"))

    client = OpenAlexClient(
        cache_dir=tmp_path,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    first = client.search("inverse diagnostics", per_page=20)
    second = client.search("inverse diagnostics", per_page=20)

    assert calls == 1
    assert first == second
    assert first[0].work_id == "https://openalex.org/W100"
    assert first[0].doi == "10.1000/anchor"
    assert first[0].authors == ["A. Author"]
    assert first[0].abstract == "Nearest review methods"
    cache_text = "".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.json"))
    assert "secret-openalex-key" not in cache_text


def test_rate_limit_retries_using_retry_after_without_logging_secret(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "secret-openalex-key")
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=fixture("openalex-works.json"))

    client = OpenAlexClient(
        cache_dir=tmp_path,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=sleeps.append,
    )

    results = client.search("inverse diagnostics")

    assert results
    assert calls == 2
    assert sleeps == [0.0]
    assert "secret-openalex-key" not in caplog.text


def test_crossref_and_unpaywall_normalize_authoritative_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CROSSREF_POLITE_EMAIL", "researcher@example.org")
    monkeypatch.setenv("UNPAYWALL_EMAIL", "researcher@example.org")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.crossref.org":
            return httpx.Response(200, json=fixture("crossref-works.json"))
        return httpx.Response(200, json=fixture("unpaywall-work.json"))

    transport = httpx.MockTransport(handler)
    crossref = CrossrefClient(
        cache_dir=tmp_path / "crossref",
        http_client=httpx.Client(transport=transport),
    )
    unpaywall = UnpaywallClient(
        cache_dir=tmp_path / "unpaywall",
        http_client=httpx.Client(transport=transport),
    )

    work = crossref.search("nearest technical review")[0]
    oa = unpaywall.lookup("10.1000/anchor")

    assert work.doi == "10.1000/anchor"
    assert work.authors == ["A. Author"]
    assert oa.pdf_url == "https://example.org/anchor.pdf"
    assert oa.license == "cc-by"
    assert oa.version == "publishedVersion"


def candidate(
    work_id: str,
    *,
    relevance: float,
    contrast: float = 0,
    bridge: float = 0,
    is_review: bool = False,
) -> CandidateWork:
    return CandidateWork(
        work_id=work_id,
        title=f"Paper {work_id}",
        authors=["Test Author"],
        year=2024,
        relevance_score=relevance,
        contrast_score=contrast,
        bridge_score=bridge,
        is_review=is_review,
        oa_status="open",
        basis="abstract",
    )


def test_recommendations_choose_anchor_contrast_bridge_not_top_three_similarity() -> None:
    candidates = [
        candidate("duplicate-high-1", relevance=0.99),
        candidate("duplicate-high-2", relevance=0.98),
        candidate("anchor-review", relevance=0.90, is_review=True),
        candidate("contrast", relevance=0.70, contrast=0.96),
        candidate("bridge", relevance=0.68, bridge=0.95),
    ]

    cards = DiscoveryService.rank_recommendations(candidates, count=3)

    assert [card.role for card in cards] == [
        RecommendationRole.ANCHOR,
        RecommendationRole.CONTRAST,
        RecommendationRole.BRIDGE,
    ]
    assert [card.work_id for card in cards] == ["anchor-review", "contrast", "bridge"]
    assert all(card.why_it_matters and card.what_it_may_change for card in cards)


def test_recommendations_allow_two_cards_when_requested() -> None:
    cards = DiscoveryService.rank_recommendations(
        [
            candidate("anchor", relevance=0.9, is_review=True),
            candidate("contrast", relevance=0.7, contrast=0.9),
        ],
        count=2,
    )

    assert len(cards) == 2


@pytest.mark.parametrize("count", [1, 4])
def test_recommendation_count_is_limited_to_two_or_three(count: int) -> None:
    with pytest.raises(ValueError, match="2 or 3"):
        DiscoveryService.rank_recommendations([], count=count)


def test_search_lanes_deduplicate_sources_and_return_role_diverse_cards() -> None:
    class Client:
        def search(self, query: str):
            return [
                WorkRecord(
                    work_id="review",
                    doi="10.1000/review",
                    title="Technical review of inverse diagnostics",
                    abstract=f"Review boundary for {query}",
                    is_review=True,
                ),
                WorkRecord(
                    work_id="contrast",
                    doi="10.1000/contrast",
                    title="Limitations and conflicting evidence in diagnostics",
                    abstract="A comparison that challenges proxy equivalence",
                ),
                WorkRecord(
                    work_id="bridge",
                    doi="10.1000/bridge",
                    title="Validation methods for external measurements",
                    abstract="Experimental methods connect measurements to diagnosis",
                ),
            ]

    cards = DiscoveryService.search_lanes(
        ["inverse diagnostics", "external measurements"],
        clients=[Client(), Client()],
        count=3,
    )

    assert [card.role for card in cards] == [
        RecommendationRole.ANCHOR,
        RecommendationRole.CONTRAST,
        RecommendationRole.BRIDGE,
    ]
    assert {card.doi for card in cards} == {
        "10.1000/review",
        "10.1000/contrast",
        "10.1000/bridge",
    }


def test_non_open_recommendation_becomes_traceable_acquisition_request() -> None:
    cards = DiscoveryService.rank_recommendations(
        [
            candidate("https://example.org/review", relevance=0.9, is_review=True),
            candidate("https://example.org/contrast", relevance=0.8, contrast=0.9),
        ],
        count=2,
    )

    requests = DiscoveryService.build_acquisition_requests(cards)

    assert len(requests) == 2
    assert requests[0].reason.startswith("Recommended as Anchor")
    assert requests[0].status == "open"


def test_verified_open_recommendation_becomes_automatic_download_request() -> None:
    card = DiscoveryService.rank_recommendations(
        [
            candidate("anchor", relevance=0.9, is_review=True),
            candidate("contrast", relevance=0.8, contrast=0.9),
        ],
        count=2,
    )[0].model_copy(
        update={
            "doi": "10.1000/open-anchor",
            "oa_url": "https://example.org/open-anchor.pdf",
            "oa_status": "gold",
            "oa_license": "cc-by",
            "oa_version": "publishedVersion",
        }
    )

    request = DiscoveryService.build_acquisition_requests([card])[0]

    assert request.route == "automatic_open"
    assert str(request.pdf_url) == "https://example.org/open-anchor.pdf"
    assert request.access_basis == "open_access"
    assert request.license_or_terms == "cc-by"
    assert request.version == "publishedVersion"
