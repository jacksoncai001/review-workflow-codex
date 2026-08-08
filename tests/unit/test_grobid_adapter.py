from __future__ import annotations

from pathlib import Path

from review_workflow.adapters.grobid import GrobidAdapter


class FakeResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int | None = None) -> bytes:
        return self.body if size is None else self.body[:size]


def test_process_fulltext_posts_pdf_as_multipart_and_returns_tei(tmp_path: Path) -> None:
    source = tmp_path / "article.pdf"
    source.write_bytes(b"%PDF-1.4 synthetic")
    observed = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["content_type"] = request.headers["Content-type"]
        observed["data"] = request.data
        observed["timeout"] = timeout
        return FakeResponse(b'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text/></TEI>')

    result = GrobidAdapter(opener=opener).process_fulltext(source)

    assert observed["url"].endswith("/api/processFulltextDocument")
    assert observed["content_type"].startswith("multipart/form-data; boundary=")
    assert b"%PDF-1.4 synthetic" in observed["data"]
    assert result.tei_xml.startswith("<TEI")
    assert result.endpoint.endswith("/api/processFulltextDocument")
