from __future__ import annotations

import pytest

from review_workflow.adapters.grobid import GrobidAdapter


def test_local_grobid_090_full_is_healthy(request) -> None:
    if not request.config.getoption("--run-grobid"):
        pytest.skip("pass --run-grobid to test the local service")

    health = GrobidAdapter("http://127.0.0.1:8070").health()

    assert health.healthy is True
    assert health.endpoint.endswith("/api/isalive")
