from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ci_runs_locked_lint_and_tests_on_windows_and_ubuntu() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]["os"]
    assert "windows-latest" in matrix
    assert "ubuntu-latest" in matrix
    assert "uv sync --locked" in text
    assert "ruff check" in text
    assert "pytest" in text


def test_public_docs_cover_core_boundary_profiles_privacy_and_migration() -> None:
    combined = "\n".join(
        (ROOT / name).read_text(encoding="utf-8").lower()
        for name in (
            "README.md",
            "docs/architecture.md",
            "docs/privacy.md",
            "docs/migration.md",
            "docs/third-party-notices.md",
            "docs/release-checklist.md",
        )
    )
    for required in (
        "narrative",
        "critical",
        "technical",
        "systematic review",
        "three reciprocal",
        "windows-lite",
        "full",
        "grobid",
        "local-first",
        "explicit consent",
        "project_relocate",
        "ars-codex",
    ):
        assert required in combined


def test_repository_defaults_exclude_real_research_documents_and_secrets() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").lower()

    assert "*.pdf" in ignore
    assert "*.docx" in ignore
    assert ".env" in ignore
    assert "review-workspace" in ignore


def test_release_metadata_and_install_docs_point_to_the_canonical_repository() -> None:
    canonical = "https://github.com/jacksoncai001/review-workflow-codex"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = (ROOT / "docs/install-windows.md").read_text(encoding="utf-8")

    assert f'Homepage = "{canonical}"' in pyproject
    assert f'Repository = "{canonical}.git"' in pyproject
    assert f"git clone {canonical}.git" in readme
    assert f"git clone {canonical}.git" in install


def test_public_support_policy_is_explicit() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    support = (ROOT / ".github/SUPPORT.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{support}"

    assert "1259081855@qq.com" in combined
    assert "best effort" in combined.lower()
    assert "no response-time commitment" in combined.lower()
    assert "do not send" in combined.lower()
