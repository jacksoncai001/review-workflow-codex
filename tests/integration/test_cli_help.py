from __future__ import annotations

from typer.testing import CliRunner

from review_workflow.cli import app


def test_cli_help_succeeds_without_extraction_extras() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "evidence-grounded review workflow" in result.stdout.lower()
