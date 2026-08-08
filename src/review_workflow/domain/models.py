"""Canonical records shared by the workflow application and transports."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base model that rejects undeclared data."""

    model_config = ConfigDict(extra="forbid")


class ExecutionProfile(StrEnum):
    FULL = "full"
    WINDOWS_LITE = "windows-lite"


class ReviewType(StrEnum):
    NARRATIVE = "narrative"
    CRITICAL = "critical"
    TECHNICAL = "technical"


class PublicationMode(StrEnum):
    SINGLE = "single"
    COMPANION = "companion"


class ArtifactStatus(StrEnum):
    CREATED = "created"
    VERIFIED = "verified"
    STALE = "stale"
    REJECTED = "rejected"


class PayloadClass(StrEnum):
    BIBLIOGRAPHIC_METADATA = "bibliographic_metadata"
    QUERY_TEXT = "query_text"
    SHORT_SNIPPET = "short_snippet"
    FULL_TEXT = "full_text"
    DRAFT_PROSE = "draft_prose"
    CREDENTIAL = "credential"


class AcquisitionPriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class AcquisitionRoute(StrEnum):
    AUTOMATIC_OPEN = "automatic_open"
    OPERATOR_SUPPLY = "operator_supply"


class ProjectConfig(StrictModel):
    schema_version: int = 1
    project_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
    workspace_root: Path
    review_type: ReviewType
    execution_profile: ExecutionProfile = ExecutionProfile.WINDOWS_LITE
    publication_mode: PublicationMode = PublicationMode.SINGLE
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("workspace_root")
    @classmethod
    def workspace_must_be_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("workspace_root must be an absolute path")
        return value.resolve(strict=False)


class ArtifactRecord(StrictModel):
    schema_version: int = 1
    artifact_id: str = Field(min_length=3, max_length=128)
    kind: str = Field(min_length=1, max_length=80)
    relative_path: Path
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer: str = Field(min_length=1, max_length=120)
    phase: str = Field(min_length=1, max_length=16)
    dependencies: list[str] = Field(default_factory=list)
    status: ArtifactStatus = ArtifactStatus.CREATED
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("relative_path")
    @classmethod
    def artifact_path_must_be_relative(cls, value: Path) -> Path:
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("artifact relative_path must stay within the workspace")
        return value


class DisclosureRecord(StrictModel):
    schema_version: int = 1
    disclosure_id: str = Field(min_length=3, max_length=128)
    destination: str = Field(min_length=1, max_length=255)
    payload_classes: set[PayloadClass] = Field(min_length=1)
    purpose: str = Field(min_length=3, max_length=1000)
    approved_by: str = Field(min_length=1, max_length=120)
    approved_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class AcquisitionRequest(StrictModel):
    schema_version: int = 1
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
    title: str = Field(min_length=3, max_length=1000)
    doi: str | None = Field(default=None, max_length=255)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1600, le=2200)
    landing_url: HttpUrl
    priority: AcquisitionPriority
    reason: str = Field(min_length=3, max_length=2000)
    affected_claim_ids: list[str] = Field(default_factory=list)
    evidence_type: str = Field(min_length=1, max_length=255)
    route: AcquisitionRoute = AcquisitionRoute.OPERATOR_SUPPLY
    pdf_url: HttpUrl | None = None
    access_basis: str | None = Field(default=None, min_length=3, max_length=255)
    license_or_terms: str | None = Field(default=None, min_length=1, max_length=1000)
    version: str | None = Field(default=None, max_length=255)
    resolution_note: str | None = Field(default=None, min_length=3, max_length=2000)
    status: str = Field(default="open", pattern=r"^(open|fulfilled|dismissed)$")
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def automatic_open_requires_auditable_location(self) -> AcquisitionRequest:
        if self.route is AcquisitionRoute.AUTOMATIC_OPEN and not all(
            (self.pdf_url, self.access_basis, self.license_or_terms)
        ):
            raise ValueError("automatic_open requires pdf_url, access_basis, and license_or_terms")
        if self.status == "dismissed" and not self.resolution_note:
            raise ValueError("dismissed acquisition requests require a resolution_note")
        return self
