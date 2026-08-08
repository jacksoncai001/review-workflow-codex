"""Privacy-aware bibliographic discovery clients with deterministic caching."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx
from pydantic import Field

from review_workflow.adapters.filesystem import atomic_write_json
from review_workflow.domain.models import StrictModel


class DiscoveryConfigurationError(RuntimeError):
    """Raised when a required official API setting is absent."""


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized or None


class WorkRecord(StrictModel):
    work_id: str
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    work_type: str | None = None
    cited_by_count: int = 0
    abstract: str | None = None
    topics: list[str] = Field(default_factory=list)
    is_review: bool = False
    oa_status: str | None = None
    oa_url: str | None = None


class OaLocation(StrictModel):
    doi: str
    is_oa: bool
    oa_status: str | None = None
    landing_url: str | None = None
    pdf_url: str | None = None
    host_type: str | None = None
    version: str | None = None
    license: str | None = None


class RecommendationRole(StrEnum):
    ANCHOR = "Anchor"
    CONTRAST = "Contrast"
    BRIDGE = "Bridge"


class CandidateWork(StrictModel):
    work_id: str
    title: str
    doi: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    relevance_score: float = Field(ge=0)
    contrast_score: float = Field(default=0, ge=0)
    bridge_score: float = Field(default=0, ge=0)
    is_review: bool = False
    oa_status: str = "unknown"
    oa_url: str | None = None
    basis: Literal["abstract", "full_text", "metadata"] = "metadata"


class RecommendationCard(StrictModel):
    role: RecommendationRole
    work_id: str
    title: str
    doi: str | None = None
    why_it_matters: str
    relationship_to_draft: str
    what_it_may_change: str
    sections_to_read: list[str]
    challenges: str
    oa_status: str
    oa_url: str | None = None
    oa_license: str | None = None
    oa_version: str | None = None
    basis: Literal["abstract", "full_text", "metadata"]


class _CachedJsonClient:
    _secret_keys = {"api_key", "email", "mailto"}

    def __init__(
        self,
        *,
        base_url: str,
        cache_dir: Path,
        http_client: httpx.Client | None = None,
        sleeper: Callable[[float], Any] = time.sleep,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir.resolve(strict=False)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.http_client = http_client or httpx.Client(timeout=30)
        self.sleeper = sleeper
        self.max_retries = max_retries

    def _get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        cache_params = {key: value for key, value in params.items() if key not in self._secret_keys}
        cache_material = json.dumps(
            {"base_url": self.base_url, "path": path, "params": cache_params},
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_id = hashlib.sha256(cache_material.encode("utf-8")).hexdigest()
        cache_path = self.cache_dir / f"{cache_id}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            response = self.http_client.get(url, params=params)
            if response.status_code != 429:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Bibliographic API response must be a JSON object")
                atomic_write_json(cache_path, payload)
                return payload
            if attempt >= self.max_retries:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After", "1")
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 1.0
            self.sleeper(max(delay, 0.0))
        raise RuntimeError("unreachable")


class OpenAlexClient(_CachedJsonClient):
    def __init__(
        self,
        *,
        cache_dir: Path,
        api_key: str | None = None,
        http_client: httpx.Client | None = None,
        sleeper: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY")
        if not self.api_key:
            raise DiscoveryConfigurationError("OPENALEX_API_KEY is required for OpenAlex search")
        super().__init__(
            base_url="https://api.openalex.org",
            cache_dir=cache_dir,
            http_client=http_client,
            sleeper=sleeper,
        )

    def search(self, query: str, per_page: int = 50) -> list[WorkRecord]:
        payload = self._get_json(
            "/works",
            {"search": query, "per-page": per_page, "api_key": self.api_key},
        )
        return [self._normalize(item) for item in payload.get("results", [])]

    @staticmethod
    def _normalize(item: dict[str, Any]) -> WorkRecord:
        work_type = item.get("type")
        oa = item.get("open_access") or {}
        return WorkRecord(
            work_id=item.get("id")
            or normalize_doi(item.get("doi"))
            or item.get("title", "unknown"),
            doi=normalize_doi(item.get("doi")),
            title=item.get("title") or "Untitled work",
            authors=[
                authorship.get("author", {}).get("display_name")
                for authorship in item.get("authorships", [])
                if authorship.get("author", {}).get("display_name")
            ],
            year=item.get("publication_year"),
            work_type=work_type,
            cited_by_count=item.get("cited_by_count") or 0,
            abstract=_decode_inverted_abstract(item.get("abstract_inverted_index")),
            topics=[
                topic.get("display_name")
                for topic in item.get("topics", [])
                if topic.get("display_name")
            ],
            is_review=work_type == "review",
            oa_status=oa.get("oa_status"),
            oa_url=oa.get("oa_url"),
        )


class CrossrefClient(_CachedJsonClient):
    def __init__(
        self,
        *,
        cache_dir: Path,
        polite_email: str | None = None,
        http_client: httpx.Client | None = None,
        sleeper: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.polite_email = polite_email or os.environ.get("CROSSREF_POLITE_EMAIL")
        super().__init__(
            base_url="https://api.crossref.org",
            cache_dir=cache_dir,
            http_client=http_client,
            sleeper=sleeper,
        )

    def search(self, query: str, rows: int = 20) -> list[WorkRecord]:
        params: dict[str, Any] = {"query.bibliographic": query, "rows": rows}
        if self.polite_email:
            params["mailto"] = self.polite_email
        payload = self._get_json("/works", params)
        items = payload.get("message", {}).get("items", [])
        return [self._normalize(item) for item in items]

    @staticmethod
    def _normalize(item: dict[str, Any]) -> WorkRecord:
        doi = normalize_doi(item.get("DOI"))
        title_values = item.get("title") or []
        title = title_values[0] if title_values else "Untitled work"
        date_parts = (item.get("published") or {}).get("date-parts") or []
        year = date_parts[0][0] if date_parts and date_parts[0] else None
        authors = []
        for author in item.get("author", []):
            name = " ".join(part for part in (author.get("given"), author.get("family")) if part)
            if name:
                authors.append(name)
        return WorkRecord(
            work_id=doi or item.get("URL") or title,
            doi=doi,
            title=title,
            authors=authors,
            year=year,
            work_type=item.get("type"),
        )


class UnpaywallClient(_CachedJsonClient):
    def __init__(
        self,
        *,
        cache_dir: Path,
        email: str | None = None,
        http_client: httpx.Client | None = None,
        sleeper: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.email = (
            email or os.environ.get("UNPAYWALL_EMAIL") or os.environ.get("CROSSREF_POLITE_EMAIL")
        )
        if not self.email:
            raise DiscoveryConfigurationError(
                "UNPAYWALL_EMAIL or CROSSREF_POLITE_EMAIL is required for Unpaywall lookup"
            )
        super().__init__(
            base_url="https://api.unpaywall.org/v2",
            cache_dir=cache_dir,
            http_client=http_client,
            sleeper=sleeper,
        )

    def lookup(self, doi: str) -> OaLocation:
        normalized = normalize_doi(doi)
        if not normalized:
            raise ValueError("A DOI is required for Unpaywall lookup")
        payload = self._get_json(f"/{quote(normalized, safe='')}", {"email": self.email})
        location = payload.get("best_oa_location") or {}
        return OaLocation(
            doi=normalized,
            is_oa=bool(payload.get("is_oa")),
            oa_status=payload.get("oa_status"),
            landing_url=location.get("url"),
            pdf_url=location.get("url_for_pdf"),
            host_type=location.get("host_type"),
            version=location.get("version"),
            license=location.get("license"),
        )


def _decode_inverted_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    maximum = max(position for positions in index.values() for position in positions)
    words = [""] * (maximum + 1)
    for word, positions in index.items():
        for position in positions:
            words[position] = word
    return " ".join(words).strip() or None
