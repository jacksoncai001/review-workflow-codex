from __future__ import annotations

from pathlib import Path

import pytest

from review_workflow.adapters.acquisition import (
    DownloadMetadata,
    DownloadValidationError,
    DownloadValidator,
    ExpectedIdentity,
)


def write_pdf(path: Path, *, body: bytes = b"synthetic article body") -> None:
    path.write_bytes(b"%PDF-1.7\n" + body * 100)


def metadata(**updates) -> DownloadMetadata:
    values = {
        "content_type": "application/pdf",
        "source_url": "https://repository.example/article.pdf",
        "access_basis": "repository_manuscript",
        "license_or_terms": "repository terms permit public access",
        "document_role": "full_text",
        "observed_doi": "10.1000/example",
        "observed_title": "A relevant technical article",
        "version": "acceptedVersion",
    }
    values.update(updates)
    return DownloadMetadata(**values)


def identity() -> ExpectedIdentity:
    return ExpectedIdentity(
        doi="10.1000/example",
        title="A relevant technical article",
        authors=["A. Author"],
    )


def test_valid_pdf_produces_hash_and_provenance_record(tmp_path: Path) -> None:
    path = tmp_path / "article.pdf"
    write_pdf(path)

    record = DownloadValidator().validate(path, identity(), metadata())

    assert len(record.sha256) == 64
    assert record.bytes == path.stat().st_size
    assert record.matched_by == "doi"
    assert record.source_url == "https://repository.example/article.pdf"


def test_html_error_page_named_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "article.pdf"
    path.write_text("<html>Access denied</html>", encoding="utf-8")

    with pytest.raises(DownloadValidationError, match="PDF signature"):
        DownloadValidator().validate(path, identity(), metadata(content_type="text/html"))


@pytest.mark.parametrize("document_role", ["supplement", "error_page"])
def test_supplement_or_error_page_is_rejected(tmp_path: Path, document_role: str) -> None:
    path = tmp_path / "article.pdf"
    write_pdf(path)

    with pytest.raises(DownloadValidationError, match="full article"):
        DownloadValidator().validate(path, identity(), metadata(document_role=document_role))


def test_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "article.pdf"
    write_pdf(path)

    with pytest.raises(DownloadValidationError, match="identity"):
        DownloadValidator().validate(
            path,
            identity(),
            metadata(observed_doi="10.1000/different", observed_title="Unrelated paper"),
        )


def test_truncated_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "article.pdf"
    path.write_bytes(b"%PDF-1.7\nshort")

    with pytest.raises(DownloadValidationError, match="too small"):
        DownloadValidator(minimum_bytes=1024).validate(path, identity(), metadata())


@pytest.mark.parametrize(
    "updates",
    [
        {"source_url": None},
        {"access_basis": "unknown"},
        {"license_or_terms": ""},
    ],
)
def test_unrecorded_or_unrecognized_access_provenance_is_rejected(
    tmp_path: Path,
    updates: dict,
) -> None:
    path = tmp_path / "article.pdf"
    write_pdf(path)

    with pytest.raises((DownloadValidationError, ValueError)):
        DownloadValidator().validate(path, identity(), metadata(**updates))
