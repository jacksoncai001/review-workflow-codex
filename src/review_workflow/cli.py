"""Command-line interface for Review Workflow Codex."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from review_workflow.application.service import WorkflowService

app = typer.Typer(
    help="Manage a local evidence-grounded review workflow.",
    no_args_is_help=True,
)


@app.callback()
def root() -> None:
    """Manage a local evidence-grounded review workflow."""


@app.command()
def version() -> None:
    """Print the installed package version."""
    from review_workflow import __version__

    typer.echo(__version__)


def _emit(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


@app.command("init")
def initialize(
    workspace: Path,
    project_id: Annotated[str, typer.Option("--project-id")],
    review_type: Annotated[str, typer.Option("--review-type")] = "technical",
    execution_profile: Annotated[str, typer.Option("--execution-profile")] = "windows-lite",
    publication_mode: Annotated[str, typer.Option("--publication-mode")] = "single",
) -> None:
    """Create a new isolated review workspace."""
    result = WorkflowService().project_init(
        workspace=workspace,
        project_id=project_id,
        review_type=review_type,
        execution_profile=execution_profile,
        publication_mode=publication_mode,
    )
    _emit(result)


@app.command()
def status(workspace: Path) -> None:
    """Print the complete resumable workflow state."""
    _emit(WorkflowService().project_status(workspace))


@app.command("relocate")
def relocate(workspace: Path) -> None:
    """Explicitly rebind a copied workspace to its new absolute location."""
    _emit(WorkflowService().project_relocate(workspace))


@app.command("phase-next")
def phase_next(workspace: Path, target: str) -> None:
    """Advance exactly one registered phase."""
    _emit(WorkflowService().phase_next(workspace=workspace, target=target))


@app.command("gate-approve")
def gate_approve(workspace: Path, gate_id: str, approved_by: str) -> None:
    """Record explicit operator approval for the current human checkpoint."""
    _emit(
        WorkflowService().gate_approve(
            workspace=workspace,
            gate_id=gate_id,
            approved_by=approved_by,
        )
    )


@app.command("complete")
def complete(workspace: Path) -> None:
    """Complete an operator-approved Phase 7 workflow."""
    _emit(WorkflowService().workflow_complete(workspace))


def main() -> None:
    """Run the Typer application."""
    app()
