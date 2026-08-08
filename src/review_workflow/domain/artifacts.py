"""Artifact dependency graph with recursive downstream invalidation."""

from __future__ import annotations

from collections import defaultdict

from pydantic import Field

from review_workflow.domain.models import ArtifactRecord, ArtifactStatus, StrictModel
from review_workflow.domain.phases import PhaseId


class ArtifactCycleError(ValueError):
    """Raised when artifact dependencies contain a cycle."""


class UnknownArtifactError(ValueError):
    """Raised when a dependency or changed artifact is not registered."""


class InvalidationReport(StrictModel):
    changed_artifacts: list[str]
    invalidated_artifacts: list[str]
    preserved_artifacts: list[str]
    reason: str = Field(min_length=1)
    return_phase: PhaseId


class ArtifactGraph:
    """Mutable graph over canonical ``ArtifactRecord`` objects."""

    def __init__(self, records: dict[str, ArtifactRecord] | None = None) -> None:
        self.records: dict[str, ArtifactRecord] = dict(records or {})
        self._assert_acyclic()

    def register(self, record: ArtifactRecord) -> None:
        if record.artifact_id in self.records:
            raise ValueError(f"Artifact already exists: {record.artifact_id}")
        self._assert_dependencies_exist(record)
        self.records[record.artifact_id] = record
        try:
            self._assert_acyclic()
        except Exception:
            del self.records[record.artifact_id]
            raise

    def replace(self, record: ArtifactRecord) -> None:
        if record.artifact_id not in self.records:
            raise UnknownArtifactError(record.artifact_id)
        self._assert_dependencies_exist(record, allow_self=True)
        previous = self.records[record.artifact_id]
        self.records[record.artifact_id] = record
        try:
            self._assert_acyclic()
        except Exception:
            self.records[record.artifact_id] = previous
            raise

    def invalidate_descendants(
        self,
        changed_ids: set[str],
        reason: str,
        return_phase: PhaseId,
    ) -> InvalidationReport:
        unknown = changed_ids - self.records.keys()
        if unknown:
            raise UnknownArtifactError(", ".join(sorted(unknown)))
        dependents: dict[str, set[str]] = defaultdict(set)
        for artifact_id, record in self.records.items():
            for dependency in record.dependencies:
                dependents[dependency].add(artifact_id)

        descendants: set[str] = set()
        queue = list(changed_ids)
        while queue:
            current = queue.pop(0)
            for dependent in dependents.get(current, set()):
                if dependent not in descendants and dependent not in changed_ids:
                    descendants.add(dependent)
                    queue.append(dependent)

        ordered_invalidated = [
            artifact_id for artifact_id in self.records if artifact_id in descendants
        ]
        for artifact_id in ordered_invalidated:
            self.records[artifact_id] = self.records[artifact_id].model_copy(
                update={"status": ArtifactStatus.STALE}
            )
        preserved = [artifact_id for artifact_id in self.records if artifact_id not in descendants]
        return InvalidationReport(
            changed_artifacts=[
                artifact_id for artifact_id in self.records if artifact_id in changed_ids
            ],
            invalidated_artifacts=ordered_invalidated,
            preserved_artifacts=preserved,
            reason=reason,
            return_phase=return_phase,
        )

    def _assert_dependencies_exist(self, record: ArtifactRecord, allow_self: bool = False) -> None:
        missing = set(record.dependencies) - self.records.keys()
        if allow_self:
            missing.discard(record.artifact_id)
        if missing:
            raise UnknownArtifactError(", ".join(sorted(missing)))

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(artifact_id: str) -> None:
            if artifact_id in visiting:
                raise ArtifactCycleError(f"Artifact dependency cycle includes {artifact_id}")
            if artifact_id in visited:
                return
            visiting.add(artifact_id)
            record = self.records[artifact_id]
            for dependency in record.dependencies:
                if dependency not in self.records:
                    raise UnknownArtifactError(dependency)
                visit(dependency)
            visiting.remove(artifact_id)
            visited.add(artifact_id)

        for artifact_id in self.records:
            visit(artifact_id)
