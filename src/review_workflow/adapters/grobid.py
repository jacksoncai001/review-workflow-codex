"""Optional local GROBID service health adapter."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from review_workflow.domain.models import StrictModel


class GrobidHealth(StrictModel):
    healthy: bool
    endpoint: str
    response: str | None = None
    error: str | None = None


class GrobidDocument(StrictModel):
    tei_xml: str
    endpoint: str


class GrobidAdapter:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8070",
        timeout: float = 5.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = opener

    def health(self) -> GrobidHealth:
        endpoint = f"{self.base_url}/api/isalive"
        try:
            with self.opener(endpoint, timeout=self.timeout) as response:  # noqa: S310
                body = response.read(256).decode("utf-8", errors="replace").strip()
            return GrobidHealth(
                healthy=body.lower() in {"true", "ok", "1"},
                endpoint=endpoint,
                response=body,
            )
        except (OSError, URLError) as error:
            return GrobidHealth(healthy=False, endpoint=endpoint, error=type(error).__name__)

    def process_fulltext(self, source_path: Path) -> GrobidDocument:
        """Submit one local PDF to GROBID and return its TEI XML."""
        path = source_path.resolve(strict=True)
        if path.suffix.lower() != ".pdf":
            raise ValueError("GROBID full-text processing requires a PDF")
        boundary = f"review-workflow-{uuid.uuid4().hex}"
        body = _multipart_pdf(path, boundary)
        endpoint = f"{self.base_url}/api/processFulltextDocument"
        request = Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Accept": "application/xml",
            },
            method="POST",
        )
        with self.opener(request, timeout=self.timeout) as response:  # noqa: S310
            tei_xml = response.read().decode("utf-8", errors="strict").strip()
        if not tei_xml.startswith("<") or "TEI" not in tei_xml[:500]:
            raise ValueError("GROBID response is not recognizable TEI XML")
        return GrobidDocument(tei_xml=tei_xml, endpoint=endpoint)


def _multipart_pdf(path: Path, boundary: str) -> bytes:
    header = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="input"; '
        f'filename="{path.name}"\r\nContent-Type: application/pdf\r\n\r\n'
    ).encode()
    footer = f"\r\n--{boundary}--\r\n".encode("ascii")
    return header + path.read_bytes() + footer
