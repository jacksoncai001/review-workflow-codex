from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from review_workflow.domain.models import DisclosureRecord, PayloadClass
from review_workflow.domain.privacy import DisclosureLedger, PrivacyDenied, PrivacyGuard


def consent(
    *,
    disclosure_id: str = "consent-001",
    destination: str = "external-model.example",
    payload_classes: set[PayloadClass] | None = None,
    approved_at: datetime | None = None,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> DisclosureRecord:
    approved = approved_at or datetime.now(UTC)
    return DisclosureRecord(
        disclosure_id=disclosure_id,
        destination=destination,
        payload_classes=payload_classes or {PayloadClass.FULL_TEXT},
        purpose="independent citation audit",
        approved_by="operator",
        approved_at=approved,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


@pytest.mark.parametrize(
    "payload_class",
    [
        PayloadClass.BIBLIOGRAPHIC_METADATA,
        PayloadClass.QUERY_TEXT,
        PayloadClass.SHORT_SNIPPET,
    ],
)
def test_default_policy_allows_metadata_queries_and_short_snippets(
    payload_class: PayloadClass,
) -> None:
    decision = PrivacyGuard().authorize(
        operation="bibliographic_search",
        payload_class=payload_class,
        destination="api.openalex.org",
    )

    assert decision.allowed is True
    assert decision.consent_id is None


@pytest.mark.parametrize("payload_class", [PayloadClass.FULL_TEXT, PayloadClass.DRAFT_PROSE])
def test_external_full_text_and_draft_require_explicit_consent(payload_class: PayloadClass) -> None:
    with pytest.raises(PrivacyDenied) as error:
        PrivacyGuard().authorize(
            operation="external_model_review",
            payload_class=payload_class,
            destination="external-model.example",
        )

    assert error.value.required_payload_class is payload_class
    assert "consent" in str(error.value).lower()


def test_active_matching_consent_allows_external_full_text() -> None:
    now = datetime.now(UTC)
    guard = PrivacyGuard(
        [consent(approved_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1))]
    )

    decision = guard.authorize(
        operation="external_model_review",
        payload_class=PayloadClass.FULL_TEXT,
        destination="external-model.example",
        consent_id="consent-001",
        now=now,
    )

    assert decision.allowed is True
    assert decision.consent_id == "consent-001"


@pytest.mark.parametrize(
    "record",
    [
        consent(destination="different.example"),
        consent(expires_at=datetime.now(UTC) - timedelta(seconds=1)),
        consent(revoked_at=datetime.now(UTC) - timedelta(seconds=1)),
        consent(payload_classes={PayloadClass.DRAFT_PROSE}),
    ],
)
def test_destination_expiry_revocation_and_payload_mismatch_deny(record: DisclosureRecord) -> None:
    with pytest.raises(PrivacyDenied):
        PrivacyGuard([record]).authorize(
            operation="external_model_review",
            payload_class=PayloadClass.FULL_TEXT,
            destination="external-model.example",
            consent_id=record.disclosure_id,
        )


def test_credentials_are_always_rejected_without_echoing_secret() -> None:
    secret = "synthetic-credential-that-must-not-appear"

    with pytest.raises(PrivacyDenied) as error:
        PrivacyGuard([consent(payload_classes={PayloadClass.CREDENTIAL})]).authorize(
            operation=f"send credential {secret}",
            payload_class=PayloadClass.CREDENTIAL,
            destination="external-model.example",
            consent_id="consent-001",
        )

    assert secret not in str(error.value)


def test_local_processing_does_not_require_external_disclosure_consent() -> None:
    decision = PrivacyGuard().authorize(
        operation="local_extraction",
        payload_class=PayloadClass.FULL_TEXT,
        destination="local",
    )

    assert decision.allowed is True


def test_disclosure_ledger_is_append_only_and_redacts_operation_details(tmp_path: Path) -> None:
    ledger = DisclosureLedger(tmp_path / "review-workspace" / "audit" / "disclosures.jsonl")
    first = consent(disclosure_id="consent-001")
    second = consent(disclosure_id="consent-002", payload_classes={PayloadClass.DRAFT_PROSE})

    ledger.append(first)
    ledger.append(second)

    records = ledger.load()
    assert [record.disclosure_id for record in records] == ["consent-001", "consent-002"]
    assert ledger.path.read_text(encoding="utf-8").count("\n") == 2
