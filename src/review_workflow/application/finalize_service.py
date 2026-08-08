"""Phase 7 reproducibility bundle validation and manifest generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from review_workflow.adapters.filesystem import (
    atomic_write_json,
    resolve_workspace_path,
    sha256_file,
)
from review_workflow.domain.models import ArtifactStatus
from review_workflow.domain.phases import PhaseId
from review_workflow.domain.state import WorkflowEngine

REQUIRED_BUNDLE_KINDS = {
    "source_manifest",
    "extraction_record",
    "scope_brief",
    "architecture_scorecard",
    "claim_matrix",
    "manuscript",
    "citation_audit",
    "review_report",
}


class FinalizeService:
    """Build a portable manifest over verified workflow artifacts."""

    def create_bundle_manifest(self, workspace: Path) -> dict[str, Any]:
        root = workspace.resolve(strict=False)
        engine = WorkflowEngine.load(root)
        if engine.state.phase is not PhaseId.PHASE_7:
            raise ValueError("A reproducibility bundle can be created only in Phase 7")
        usable = [
            record
            for record in engine.state.artifacts.values()
            if record.status is not ArtifactStatus.STALE and record.kind != "reproducibility_bundle"
        ]
        present_kinds = {record.kind for record in usable}
        missing = sorted(REQUIRED_BUNDLE_KINDS - present_kinds)
        if missing:
            raise ValueError(
                f"Reproducibility bundle is missing artifact kinds: {', '.join(missing)}"
            )

        entries: list[dict[str, Any]] = []
        for record in usable:
            path = resolve_workspace_path(root, record.relative_path)
            if not path.is_file():
                raise FileNotFoundError(f"Registered artifact is missing: {record.artifact_id}")
            observed_hash = sha256_file(path)
            if observed_hash != record.content_hash:
                raise ValueError(f"Registered artifact hash changed: {record.artifact_id}")
            entries.append(
                {
                    "artifact_id": record.artifact_id,
                    "kind": record.kind,
                    "relative_path": str(record.relative_path).replace("\\", "/"),
                    "content_hash": record.content_hash,
                    "producer": record.producer,
                    "phase": record.phase,
                    "dependencies": record.dependencies,
                }
            )
        payload: dict[str, Any] = {
            "schema_version": 1,
            "project_id": engine.state.project_id,
            "review_type": engine.state.review_type.value,
            "execution_profile": engine.state.execution_profile.value,
            "publication_mode": engine.state.publication_mode.value,
            "state_schema_version": engine.state.schema_version,
            "state_phase": engine.state.phase.value,
            "state_step": engine.state.step,
            "event_count_before_bundle": len(engine.state.events),
            "loop_counters": engine.state.loop_counters,
            "required_kinds": sorted(REQUIRED_BUNDLE_KINDS),
            "present_kinds": sorted(present_kinds),
            "artifacts": entries,
            "migration_instruction": (
                "Install the same tagged product version, copy the whole workspace, "
                "run project_relocate, then inspect project_status."
            ),
            "limitations": (
                ["manual_bibliography_and_intext_citation_structure_check_required"]
                if engine.state.execution_profile.value == "windows-lite"
                else []
            ),
        }
        path = resolve_workspace_path(
            root,
            Path("phases/phase-7/reproducibility-bundle.json"),
        )
        atomic_write_json(path, payload)
        return {
            **payload,
            "bundle_path": str(path),
            "entry_count": len(entries),
        }
