from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-grobid",
        action="store_true",
        default=False,
        help="run integration tests against a local GROBID service",
    )
