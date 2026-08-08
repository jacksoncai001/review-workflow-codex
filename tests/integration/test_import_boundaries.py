from __future__ import annotations

import importlib
import sys


def test_state_import_does_not_import_pypdf(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pypdf", None)

    module = importlib.import_module("review_workflow.domain.state")

    assert module is not None
    assert "pypdf" not in module.__dict__
