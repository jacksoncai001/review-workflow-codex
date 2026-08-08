"""Local-first disclosure authorization and append-only consent records."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from review_workflow.domain.models import (
    DisclosureRecord,
    PayloadClass,
    StrictModel,
    utc_now,
)


class PrivacyDenied(PermissionError):
    """Safe denial that never includes payload or operation details."""

    def __init__(
        self,
        message: str,
        *,
        required_payload_class: PayloadClass,
        destination: str,
    ) -> None:
        super().__init__(message)
        self.required_payload_class = required_payload_class
        self.destination = destination


class PrivacyDecision(StrictModel):
    allowed: bool
    policy: str
    payload_class: PayloadClass
    destination: str
    consent_id: str | None = None


class PrivacyGuard:
    """Authorize an outbound payload class without inspecting payload content."""

    _default_external = {
        PayloadClass.BIBLIOGRAPHIC_METADATA,
        PayloadClass.QUERY_TEXT,
        PayloadClass.SHORT_SNIPPET,
    }
    _local_destinations = {"local", "localhost", "127.0.0.1", "::1"}

    def __init__(self, disclosures: list[DisclosureRecord] | None = None) -> None:
        self.disclosures = {record.disclosure_id: record for record in disclosures or []}

    def authorize(
        self,
        *,
        operation: str,
        payload_class: PayloadClass,
        destination: str,
        consent_id: str | None = None,
        now: datetime | None = None,
    ) -> PrivacyDecision:
        del operation  # Never echo potentially sensitive operation descriptions.
        current = now or utc_now()
        if payload_class is PayloadClass.CREDENTIAL:
            raise PrivacyDenied(
                "Credential transmission is prohibited by the review-workflow privacy policy.",
                required_payload_class=payload_class,
                destination=destination,
            )
        if destination.lower() in self._local_destinations:
            return PrivacyDecision(
                allowed=True,
                policy="local_processing",
                payload_class=payload_class,
                destination=destination,
            )
        if payload_class in self._default_external:
            return PrivacyDecision(
                allowed=True,
                policy="metadata_query_snippet_default",
                payload_class=payload_class,
                destination=destination,
            )
        record = self.disclosures.get(consent_id or "")
        if record is None or not self._is_active_match(record, payload_class, destination, current):
            raise PrivacyDenied(
                "Explicit active consent is required for this payload class and destination.",
                required_payload_class=payload_class,
                destination=destination,
            )
        return PrivacyDecision(
            allowed=True,
            policy="explicit_disclosure_consent",
            payload_class=payload_class,
            destination=destination,
            consent_id=record.disclosure_id,
        )

    @staticmethod
    def _is_active_match(
        record: DisclosureRecord,
        payload_class: PayloadClass,
        destination: str,
        now: datetime,
    ) -> bool:
        return (
            record.destination == destination
            and payload_class in record.payload_classes
            and record.approved_at <= now
            and (record.expires_at is None or now < record.expires_at)
            and (record.revoked_at is None or now < record.revoked_at)
        )


class DisclosureLedger:
    """Append and load explicit disclosure consent records as JSONL."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve(strict=False)

    def append(self, record: DisclosureRecord) -> None:
        existing_ids = {item.disclosure_id for item in self.load()} if self.path.exists() else set()
        if record.disclosure_id in existing_ids:
            raise ValueError(f"Disclosure record already exists: {record.disclosure_id}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())

    def load(self) -> list[DisclosureRecord]:
        if not self.path.exists():
            return []
        records: list[DisclosureRecord] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                records.append(DisclosureRecord.model_validate_json(line))
            except Exception as error:
                raise ValueError(
                    f"Invalid disclosure ledger record at line {line_number}"
                ) from error
        return records
