"""Validation for lawfully acquired PDF candidates."""

from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl

from review_workflow.adapters.discovery import normalize_doi
from review_workflow.adapters.filesystem import sha256_file
from review_workflow.domain.models import StrictModel


class DownloadValidationError(ValueError):
    """Raised when a downloaded file is not a verified lawful full-text article."""


class ExpectedIdentity(StrictModel):
    doi: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)


class DownloadMetadata(StrictModel):
    content_type: str | None = None
    source_url: HttpUrl | None
    access_basis: Literal[
        "open_access",
        "publisher_permitted",
        "repository_manuscript",
        "preprint",
    ]
    license_or_terms: str = Field(min_length=1, max_length=1000)
    document_role: Literal["full_text", "supplement", "error_page"]
    observed_doi: str | None = None
    observed_title: str | None = None
    version: str | None = None


class DownloadRecord(StrictModel):
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0)
    source_url: str
    access_basis: str
    license_or_terms: str
    version: str | None = None
    matched_by: Literal["doi", "title"]


class DownloadValidator:
    def __init__(self, minimum_bytes: int = 1024, title_threshold: float = 0.85) -> None:
        self.minimum_bytes = minimum_bytes
        self.title_threshold = title_threshold

    def validate(
        self,
        path: Path,
        expected: ExpectedIdentity,
        metadata: DownloadMetadata,
    ) -> DownloadRecord:
        if not path.is_file():
            raise DownloadValidationError(f"Downloaded file does not exist: {path}")
        with path.open("rb") as stream:
            signature = stream.read(5)
        if signature != b"%PDF-":
            raise DownloadValidationError("Downloaded file does not have a PDF signature")
        if path.stat().st_size < self.minimum_bytes:
            raise DownloadValidationError("Downloaded PDF is too small to be a full article")
        if metadata.content_type and "pdf" not in metadata.content_type.lower():
            raise DownloadValidationError("Response content type is not PDF")
        if metadata.document_role != "full_text":
            raise DownloadValidationError("Downloaded document is not classified as a full article")
        if metadata.source_url is None:
            raise DownloadValidationError("A lawful source URL must be recorded")

        expected_doi = normalize_doi(expected.doi)
        observed_doi = normalize_doi(metadata.observed_doi)
        if expected_doi and observed_doi:
            if expected_doi != observed_doi:
                raise DownloadValidationError(
                    "Downloaded document identity does not match expected DOI"
                )
            matched_by: Literal["doi", "title"] = "doi"
        else:
            expected_title = _normalize_title(expected.title)
            observed_title = _normalize_title(metadata.observed_title or "")
            similarity = SequenceMatcher(None, expected_title, observed_title).ratio()
            if similarity < self.title_threshold:
                raise DownloadValidationError(
                    "Downloaded document identity does not match expected title"
                )
            matched_by = "title"

        return DownloadRecord(
            path=path.resolve(strict=False),
            sha256=sha256_file(path),
            bytes=path.stat().st_size,
            source_url=str(metadata.source_url),
            access_basis=metadata.access_basis,
            license_or_terms=metadata.license_or_terms,
            version=metadata.version,
            matched_by=matched_by,
        )


def _normalize_title(title: str) -> str:
    return " ".join(
        "".join(character.lower() if character.isalnum() else " " for character in title).split()
    )
