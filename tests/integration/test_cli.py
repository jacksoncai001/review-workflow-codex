from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from review_workflow.application.service import WorkflowService
from review_workflow.cli import app


def test_cli_init_and_status_match_application_service(tmp_path: Path) -> None:
    workspace = (tmp_path / "review-workspace").resolve()
    runner = CliRunner()

    initialized = runner.invoke(
        app,
        [
            "init",
            str(workspace),
            "--project-id",
            "synthetic-review",
            "--review-type",
            "technical",
            "--execution-profile",
            "windows-lite",
        ],
    )
    status_result = runner.invoke(app, ["status", str(workspace)])

    assert initialized.exit_code == 0, initialized.stdout
    assert status_result.exit_code == 0, status_result.stdout
    cli_status = json.loads(status_result.stdout)
    service_status = WorkflowService().project_status(workspace)
    assert cli_status == service_status


def test_cli_status_failure_is_structured_and_nonzero(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["status", str(tmp_path / "missing")])

    assert result.exit_code != 0
    assert "state.json" in (result.stdout + str(result.exception))
