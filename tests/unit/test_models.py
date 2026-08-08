from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from review_workflow.domain.models import (
    AcquisitionPriority,
    AcquisitionRequest,
    ArtifactRecord,
    ArtifactStatus,
    DisclosureRecord,
    ExecutionProfile,
    PayloadClass,
    ProjectConfig,
    PublicationMode,
    ReviewType,
)


def test_project_config_accepts_supported_review_types_and_profiles(tmp_path: Path) -> None:
    config = ProjectConfig(
        project_id="fuel-cell-diagnostics",
        workspace_root=(tmp_path / "review-workspace").resolve(),
        review_type=ReviewType.TECHNICAL,
        execution_profile=ExecutionProfile.WINDOWS_LITE,
        publication_mode=PublicationMode.COMPANION,
    )

    assert config.schema_version == 1
    assert config.review_type is ReviewType.TECHNICAL
    assert config.execution_profile is ExecutionProfile.WINDOWS_LITE


def test_project_config_rejects_relative_workspace(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        ProjectConfig(
            project_id="example",
            workspace_root=Path("review-workspace"),
            review_type=ReviewType.NARRATIVE,
        )


def test_artifact_record_requires_sha256_and_relative_path() -> None:
    artifact = ArtifactRecord(
        artifact_id="artifact-001",
        kind="scope_brief",
        relative_path=Path("phases/phase-2/scope-brief.json"),
        content_hash="a" * 64,
        producer="mutual-scoping-loop",
        phase="2A",
        status=ArtifactStatus.VERIFIED,
    )

    assert artifact.content_hash == "a" * 64

    with pytest.raises(ValidationError):
        ArtifactRecord(
            artifact_id="artifact-002",
            kind="scope_brief",
            relative_path=Path("C:/outside.json"),
            content_hash="bad-hash",
            producer="test",
            phase="2A",
        )


def test_disclosure_record_captures_destination_and_expiry() -> None:
    approved_at = datetime.now(UTC)
    record = DisclosureRecord(
        disclosure_id="consent-001",
        destination="external-model.example",
        payload_classes={PayloadClass.FULL_TEXT},
        purpose="independent citation audit",
        approved_by="operator",
        approved_at=approved_at,
        expires_at=approved_at + timedelta(hours=2),
    )

    assert record.payload_classes == {PayloadClass.FULL_TEXT}
    assert record.revoked_at is None


def test_acquisition_request_preserves_actionable_metadata() -> None:
    request = AcquisitionRequest(
        request_id="acq-001",
        title="A relevant inaccessible paper",
        doi="10.1000/example",
        authors=["A. Author"],
        year=2024,
        landing_url="https://doi.org/10.1000/example",
        priority=AcquisitionPriority.P0,
        reason="Required to verify the central comparison",
        affected_claim_ids=["claim-001"],
        evidence_type="full_text_method_details",
    )

    assert request.priority is AcquisitionPriority.P0
    assert request.status == "open"
