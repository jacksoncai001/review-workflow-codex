"""Transport-independent orchestration for the review workflow."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from review_workflow.adapters.acquisition import (
    DownloadMetadata,
    DownloadValidator,
    ExpectedIdentity,
)
from review_workflow.adapters.corpus import CorpusStore, SourceRecord, compute_source_id
from review_workflow.adapters.filesystem import (
    atomic_write_json,
    atomic_write_text,
    resolve_workspace_path,
    sha256_file,
)
from review_workflow.adapters.grobid import GrobidAdapter
from review_workflow.application.corpus_service import CorpusService
from review_workflow.application.finalize_service import FinalizeService
from review_workflow.domain.artifacts import ArtifactGraph
from review_workflow.domain.loops import (
    FailureSignal,
    MutualScopingLoop,
    QuestionPacket,
    ReturnRouter,
    ScopingRound,
)
from review_workflow.domain.models import (
    AcquisitionRequest,
    AcquisitionRoute,
    ArtifactRecord,
    DisclosureRecord,
    ProjectConfig,
)
from review_workflow.domain.phases import PhaseId, RunStatus
from review_workflow.domain.privacy import DisclosureLedger
from review_workflow.domain.state import ResumeAction, WorkflowEngine

STANDARD_DIRECTORIES = (
    "inputs",
    "corpus/extractions",
    "corpus/index",
    "phases/phase-0",
    "phases/phase-1",
    "phases/phase-2",
    "phases/phase-3",
    "phases/phase-4",
    "phases/phase-5",
    "phases/phase-6",
    "phases/phase-7",
    "manuscripts",
    "decisions",
    "acquisitions",
    "audit",
    "logs",
)

SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".doc", ".docx", ".rtf", ".odt"}

RETURN_STOP_EVIDENCE_KINDS: dict[str, set[str]] = {
    "missing_literature": {"source_manifest", "extraction_record"},
    "extraction_or_identity": {"extraction_record"},
    "positioning_or_architecture": {"scope_brief", "architecture_scorecard"},
    "claim_evidence": {"claim_matrix"},
    "prose_or_visual": {"manuscript"},
    "citation_semantic_mismatch": {"claim_matrix", "manuscript", "citation_audit"},
    "review_failure": {"manuscript", "citation_audit", "review_report"},
}


class WorkflowService:
    """Shared application boundary used by the CLI and local MCP server."""

    def project_init(
        self,
        *,
        workspace: Path,
        project_id: str,
        review_type: str,
        execution_profile: str,
        publication_mode: str = "single",
    ) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        config = ProjectConfig(
            project_id=project_id,
            workspace_root=root,
            review_type=review_type,
            execution_profile=execution_profile,
            publication_mode=publication_mode,
        )
        for relative in STANDARD_DIRECTORIES:
            resolve_workspace_path(root, Path(relative)).mkdir(parents=True, exist_ok=True)
        engine = WorkflowEngine.create(config)
        return engine.state.model_dump(mode="json")

    def project_status(self, workspace: Path) -> dict[str, Any]:
        return WorkflowEngine.load(Path(workspace)).state.model_dump(mode="json")

    def project_relocate(self, workspace: Path) -> dict[str, Any]:
        return WorkflowEngine.relocate(Path(workspace)).state.model_dump(mode="json")

    def phase_next(self, *, workspace: Path, target: str) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        engine.transition(PhaseId(target))
        return engine.state.model_dump(mode="json")

    def gate_approve(
        self,
        *,
        workspace: Path,
        gate_id: str,
        approved_by: str,
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        engine.approve_gate(gate_id, approved_by)
        return engine.state.model_dump(mode="json")

    def workflow_complete(self, workspace: Path) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        bundles = [
            record
            for record in engine.state.artifacts.values()
            if record.kind == "reproducibility_bundle" and record.status.value != "stale"
        ]
        if not bundles:
            raise ValueError("A current reproducibility bundle is required before completion")
        bundle = bundles[-1]
        if (
            sha256_file(resolve_workspace_path(engine.workspace, bundle.relative_path))
            != bundle.content_hash
        ):
            raise ValueError("The registered reproducibility bundle hash no longer matches")
        engine.complete()
        return engine.state.model_dump(mode="json")

    def question_packet_open(
        self,
        workspace: Path,
        codex_questions: list[str],
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        if engine.state.phase is not PhaseId.PHASE_2A:
            raise ValueError("Reciprocal scoping questions can be opened only in Phase 2A")
        round_number = engine.state.loop_counters.get("mutual_scoping_rounds", 0) + 1
        packet = QuestionPacket(
            round_number=round_number,
            codex_questions=codex_questions,
        )
        packet_id = f"scope-round-{round_number}"
        payload = packet.model_dump(mode="json")
        engine.wait_for_user(
            packet_id,
            {"packet_type": "mutual_scoping", **payload},
            ResumeAction(
                action="synthesize_scoping_round",
                phase=PhaseId.PHASE_2A,
                step=f"round_{round_number}_synthesize",
                parameters={"round_number": round_number},
            ),
        )
        return {"packet_id": packet_id, **payload}

    def question_packet_get(self, workspace: Path) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        outstanding = engine.state.outstanding_question
        if outstanding is None:
            raise ValueError("No question packet is currently outstanding")
        return {
            "packet_id": outstanding.packet_id,
            **outstanding.payload,
            "created_at": outstanding.created_at.isoformat(),
        }

    def answer_packet_record(
        self,
        *,
        workspace: Path,
        packet_id: str,
        answer_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        outstanding = engine.state.outstanding_question
        if outstanding is None:
            raise ValueError("No answer is currently expected")
        if outstanding.payload.get("packet_type") != "mutual_scoping":
            raise ValueError("The outstanding packet is not a mutual-scoping packet")
        record = ScopingRound(
            round_number=int(outstanding.payload["round_number"]),
            codex_questions=list(outstanding.payload["codex_questions"]),
            **dict(answer_payload),
        )
        resume = engine.record_answer(packet_id, answer_payload)
        engine.record_decision(
            f"scoping_round:{record.round_number}",
            record.model_dump(mode="json"),
            loop_counter=("mutual_scoping_rounds", record.round_number),
        )
        result: dict[str, Any] = {
            "round": record.model_dump(mode="json"),
            "resume_action": resume.model_dump(mode="json"),
        }
        if record.new_search_lanes:
            loop = MutualScopingLoop([record])
            evaluation = loop.evaluate(_empty_scope_brief())
            if evaluation.resume_action is None:
                raise ValueError("Literature refresh evaluation did not provide a resume action")
            refresh_id = f"scope-round-{record.round_number}"
            engine.begin_literature_refresh(
                refresh_id=refresh_id,
                search_lanes=record.new_search_lanes,
                resume_action=evaluation.resume_action,
            )
            result["literature_refresh"] = {
                "refresh_id": refresh_id,
                "status": "search_required",
                "return_phase": evaluation.return_phase.value
                if evaluation.return_phase is not None
                else None,
                "search_lanes": evaluation.search_lanes,
                "resume_action": evaluation.resume_action.model_dump(mode="json"),
            }
        return result

    def artifact_register(
        self,
        *,
        workspace: Path,
        artifact_id: str,
        kind: str,
        relative_path: str,
        producer: str,
        phase: str,
        dependencies: list[str],
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        path = resolve_workspace_path(root, Path(relative_path))
        if not path.is_file():
            raise FileNotFoundError(f"Artifact file does not exist: {path}")
        record = ArtifactRecord(
            artifact_id=artifact_id,
            kind=kind,
            relative_path=path.relative_to(root),
            content_hash=sha256_file(path),
            producer=producer,
            phase=phase,
            dependencies=dependencies,
        )
        graph = ArtifactGraph(engine.state.artifacts)
        if replace_existing:
            previous = graph.records.get(record.artifact_id)
            invalidated: list[str] = []
            if previous is not None and previous.content_hash != record.content_hash:
                report = graph.invalidate_descendants(
                    {record.artifact_id},
                    reason=f"Artifact content replaced: {record.artifact_id}",
                    return_phase=PhaseId(phase),
                )
                invalidated = report.invalidated_artifacts
            graph.replace(record)
            engine.replace_artifact(
                record,
                artifacts=graph.records,
                invalidated_artifacts=invalidated,
            )
        else:
            graph.register(record)
            engine.register_artifact(record)
        return record.model_dump(mode="json")

    def artifact_list(self, workspace: Path) -> list[dict[str, Any]]:
        records = WorkflowEngine.load(Path(workspace)).state.artifacts.values()
        return [record.model_dump(mode="json") for record in records]

    def return_route(
        self,
        *,
        workspace: Path,
        failure_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        signal = FailureSignal.model_validate(failure_payload)
        event = ReturnRouter.route(signal)
        graph = ArtifactGraph(engine.state.artifacts)
        report = graph.invalidate_descendants(
            set(signal.invalidated_artifacts),
            reason=signal.reason,
            return_phase=event.return_phase,
        )
        event = event.model_copy(
            update={
                "changed_artifacts": report.changed_artifacts,
                "prior_hashes": {
                    artifact_id: engine.state.artifacts[artifact_id].content_hash
                    for artifact_id in report.changed_artifacts
                },
                "invalidated_artifacts": report.invalidated_artifacts,
                "preserved_artifacts": report.preserved_artifacts,
            }
        )
        payload = event.model_dump(mode="json")
        engine.apply_return(return_payload=payload, artifacts=graph.records)
        return payload

    def return_resume(
        self,
        *,
        workspace: Path,
        failure_id: str,
        resolution_note: str | None = None,
        evidence_artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        if not engine.state.return_stack:
            raise ValueError("No return event is active")
        event = engine.state.return_stack[-1]
        if event.get("failure_id") != failure_id:
            raise ValueError(f"Active return event is not {failure_id}")
        prior_hashes = event.get("prior_hashes", {})
        for artifact_id in event.get("changed_artifacts", []):
            current = engine.state.artifacts.get(artifact_id)
            if current is None or current.content_hash == prior_hashes.get(artifact_id):
                raise ValueError(f"The changed artifact has not been replaced: {artifact_id}")
        for artifact_id in event.get("invalidated_artifacts", []):
            current = engine.state.artifacts.get(artifact_id)
            if current is None or current.status.value == "stale":
                raise ValueError(f"A downstream artifact remains stale: {artifact_id}")
        if resolution_note is None or len(resolution_note.strip()) < 12:
            raise ValueError("A substantive return resolution note is required")
        evidence_ids = list(dict.fromkeys(evidence_artifact_ids or []))
        if not evidence_ids:
            raise ValueError("At least one stop-condition evidence artifact is required")
        trigger = str(event.get("trigger_condition"))
        allowed_kinds = RETURN_STOP_EVIDENCE_KINDS.get(trigger, set())
        return_event = next(
            (
                item
                for item in reversed(engine.state.events)
                if item.event_type == "return_applied"
                and item.details.get("failure_id") == failure_id
            ),
            None,
        )
        if return_event is None:
            raise ValueError(f"Return event audit record is missing: {failure_id}")
        evidence_payload: list[dict[str, Any]] = []
        for artifact_id in evidence_ids:
            artifact = engine.state.artifacts.get(artifact_id)
            if artifact is None or artifact.status.value == "stale":
                raise ValueError(f"Stop-condition evidence is absent or stale: {artifact_id}")
            if artifact.kind not in allowed_kinds:
                raise ValueError(
                    f"Evidence artifact {artifact_id} does not match the stop condition for "
                    f"{trigger}"
                )
            artifact_path = resolve_workspace_path(engine.workspace, artifact.relative_path)
            if not artifact_path.is_file() or sha256_file(artifact_path) != artifact.content_hash:
                raise ValueError(f"Stop-condition evidence hash is invalid: {artifact_id}")
            if (
                artifact_id not in event.get("changed_artifacts", [])
                and artifact.created_at < return_event.timestamp
            ):
                raise ValueError(
                    f"Stop-condition evidence predates the active repair: {artifact_id}"
                )
            evidence_payload.append(
                {
                    "artifact_id": artifact_id,
                    "kind": artifact.kind,
                    "content_hash": artifact.content_hash,
                }
            )
        engine.record_decision(
            f"return_resolution:{failure_id}",
            {
                "failure_id": failure_id,
                "trigger_condition": trigger,
                "stop_condition": event.get("stop_condition"),
                "resolution_note": resolution_note.strip(),
                "evidence": evidence_payload,
            },
        )
        engine.resume_after_repair(failure_id)
        return engine.state.model_dump(mode="json")

    def preflight_check(self, workspace: Path) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        WorkflowEngine.load(root)
        writable = False
        logs = resolve_workspace_path(root, Path("logs"))
        logs.mkdir(parents=True, exist_ok=True)
        try:
            descriptor, probe = tempfile.mkstemp(prefix="preflight-", dir=logs)
            os.close(descriptor)
            Path(probe).unlink(missing_ok=True)
            writable = True
        except OSError:
            writable = False
        grobid = GrobidAdapter(timeout=0.5).health()
        return {
            "python_supported": sys.version_info >= (3, 12),
            "python_version": ".".join(str(part) for part in sys.version_info[:3]),
            "workspace_writable": writable,
            "tools": {
                "uv": {"available": shutil.which("uv") is not None},
                "codex": {"available": shutil.which("codex") is not None},
                "markitdown": {"available": shutil.which("markitdown") is not None},
                "docling": {"available": shutil.which("docling") is not None},
                "pypdf": {"available": importlib.util.find_spec("pypdf") is not None},
                "grobid": grobid.model_dump(mode="json"),
            },
        }

    def source_inventory(
        self,
        *,
        workspace: Path,
        input_paths: Sequence[str],
        run_extraction: bool = False,
    ) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        WorkflowEngine.load(root)
        candidates: list[Path] = []
        acquisition_root = resolve_workspace_path(root, Path("acquisitions"))
        for raw_path in input_paths:
            source_path = Path(raw_path).resolve(strict=False)
            if source_path.is_file():
                if source_path.is_relative_to(root) and not source_path.is_relative_to(
                    acquisition_root
                ):
                    raise ValueError(
                        "Workspace-internal source files are allowed only under acquisitions"
                    )
                candidates.append(source_path)
            elif source_path.is_dir():
                directory_is_internal = source_path.is_relative_to(root)
                if directory_is_internal and not source_path.is_relative_to(acquisition_root):
                    raise ValueError(
                        "Workspace-internal source directories are allowed only under acquisitions"
                    )
                candidates.extend(
                    path
                    for path in source_path.rglob("*")
                    if path.is_file()
                    and (
                        directory_is_internal or not path.resolve(strict=False).is_relative_to(root)
                    )
                )
            else:
                raise FileNotFoundError(f"Input path does not exist: {source_path}")
        records_by_hash: dict[str, SourceRecord] = {}
        manifest_path = resolve_workspace_path(root, Path("inputs/manifest.jsonl"))
        if manifest_path.exists():
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                existing = SourceRecord.model_validate_json(line)
                records_by_hash[existing.source_hash] = existing
        for path in sorted(set(candidates)):
            extension = path.suffix.lower()
            if extension not in SUPPORTED_SOURCE_EXTENSIONS:
                continue
            digest = sha256_file(path)
            records_by_hash.setdefault(
                digest,
                SourceRecord(
                    source_id=compute_source_id(digest),
                    source_hash=digest,
                    original_path=path,
                    size_bytes=path.stat().st_size,
                    extension=extension,
                ),
            )
        records = list(records_by_hash.values())
        manifest = "".join(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        )
        atomic_write_text(manifest_path, manifest)
        self.artifact_register(
            workspace=root,
            artifact_id="source-manifest",
            kind="source_manifest",
            relative_path="inputs/manifest.jsonl",
            producer="source_inventory",
            phase="1",
            dependencies=[],
            replace_existing="source-manifest" in WorkflowEngine.load(root).state.artifacts,
        )
        report: dict[str, Any] = {
            "sources": [record.model_dump(mode="json") for record in records],
            "extractions": [],
            "corpus_counts": {"sources": len(records), "chunks": 0},
        }
        if run_extraction:
            state = WorkflowEngine.load(root).state
            extraction = CorpusService().extract_and_index(
                workspace=root,
                sources=records,
                profile=state.execution_profile,
            )
            report.update(extraction)
            known = WorkflowEngine.load(root).state.artifacts
            for item in report["extractions"]:
                extraction_id = item["extraction_id"]
                artifact_id = f"extraction-record-{extraction_id.removeprefix('ext-')[:32]}"
                record_path = Path(item["record_path"]).resolve(strict=False)
                self.artifact_register(
                    workspace=root,
                    artifact_id=artifact_id,
                    kind="extraction_record",
                    relative_path=str(record_path.relative_to(root)),
                    producer=item["parser"],
                    phase="1",
                    dependencies=["source-manifest"],
                    replace_existing=artifact_id in known,
                )
        return report

    def reproducibility_bundle_create(self, workspace: Path) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        payload = FinalizeService().create_bundle_manifest(root)
        engine = WorkflowEngine.load(root)
        artifact_id = "reproducibility-bundle"
        dependencies = [
            record.artifact_id
            for record in engine.state.artifacts.values()
            if record.kind in payload["required_kinds"] and record.status.value != "stale"
        ]
        self.artifact_register(
            workspace=root,
            artifact_id=artifact_id,
            kind="reproducibility_bundle",
            relative_path=str(Path(payload["bundle_path"]).relative_to(root)),
            producer="finalize_service",
            phase="7",
            dependencies=dependencies,
            replace_existing=artifact_id in engine.state.artifacts,
        )
        return payload

    def evidence_search(
        self,
        *,
        workspace: Path,
        query: str,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        root = Path(workspace).resolve(strict=False)
        WorkflowEngine.load(root)
        database = resolve_workspace_path(root, Path("corpus/index/corpus.sqlite3"))
        store = CorpusStore(database)
        return [hit.model_dump(mode="json") for hit in store.search(query, top_k=top_k)]

    def literature_discover(
        self,
        *,
        workspace: Path,
        search_lanes: list[str],
        count: int = 3,
        clients: list[Any] | None = None,
        unpaywall_client: Any | None = None,
        auto_download_open: bool = True,
        download_http_client: Any | None = None,
    ) -> dict[str, Any]:
        """Search, route every recommendation, and fetch licensed open PDFs when possible."""
        from review_workflow.adapters.discovery import (
            CrossrefClient,
            DiscoveryConfigurationError,
            OpenAlexClient,
            UnpaywallClient,
        )
        from review_workflow.application.discovery_service import DiscoveryService

        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        cache_root = resolve_workspace_path(root, Path("phases/phase-0/api-cache"))
        digest = (
            __import__("hashlib")
            .sha256(json.dumps(search_lanes, ensure_ascii=False, sort_keys=True).encode("utf-8"))
            .hexdigest()[:16]
        )
        refresh_key, refresh = _matching_literature_refresh(engine, search_lanes)
        if (
            refresh_key is None
            and engine.state.phase is PhaseId.PHASE_0
            and engine.state.status is RunStatus.RUNNING
            and engine.state.resume_action is None
        ):
            refresh_id = f"initial-{digest}"
            engine.begin_literature_refresh(
                refresh_id=refresh_id,
                search_lanes=search_lanes,
                resume_action=ResumeAction(
                    action="continue_after_initial_recommended_reading",
                    phase=PhaseId.PHASE_0,
                    step="initial_recommendations_read",
                    parameters={"refresh_id": refresh_id},
                ),
            )
            refresh_key = f"literature_refresh:{refresh_id}"
            refresh = dict(engine.state.decisions[refresh_key])
        search_clients = clients
        if search_clients is None:
            search_clients = [CrossrefClient(cache_dir=cache_root / "crossref")]
            try:
                search_clients.insert(0, OpenAlexClient(cache_dir=cache_root / "openalex"))
            except DiscoveryConfigurationError:
                pass
        cards = DiscoveryService.search_lanes(
            search_lanes,
            clients=search_clients,
            count=count,
        )
        unpaywall = unpaywall_client
        if unpaywall is None:
            try:
                unpaywall = UnpaywallClient(cache_dir=cache_root / "unpaywall")
            except DiscoveryConfigurationError:
                unpaywall = None
        if unpaywall is not None:
            enriched = []
            for card in cards:
                if card.doi and not card.oa_url:
                    location = unpaywall.lookup(card.doi)
                    card = card.model_copy(
                        update={
                            "oa_status": location.oa_status
                            or ("open" if location.is_oa else "closed"),
                            "oa_url": location.pdf_url,
                            "oa_license": location.license,
                            "oa_version": location.version,
                        }
                    )
                enriched.append(card)
            cards = enriched
        requests = DiscoveryService.build_acquisition_requests(cards)
        for request in requests:
            if not any(
                item.request_id == request.request_id for item in engine.state.acquisition_requests
            ):
                engine.add_acquisition_request(request)
        discovery_key = f"literature_discovery:{digest}"
        payload: dict[str, Any] = {
            "search_lanes": search_lanes,
            "recommendations": [card.model_dump(mode="json") for card in cards],
            "acquisition_requests": [request.model_dump(mode="json") for request in requests],
            "automatic_downloads": [],
            "automatic_download_errors": [],
        }
        engine.record_decision(discovery_key, payload)
        if refresh_key is not None and refresh is not None:
            engine.record_decision(
                refresh_key,
                {
                    **refresh,
                    "status": "acquisition_wait",
                    "discovery_decision": discovery_key,
                    "acquisition_request_ids": [request.request_id for request in requests],
                },
            )

        if auto_download_open:
            for request in requests:
                current = next(
                    (
                        item
                        for item in WorkflowEngine.load(root).state.acquisition_requests
                        if item.request_id == request.request_id
                    ),
                    None,
                )
                if (
                    current is None
                    or current.status != "open"
                    or current.route is not AcquisitionRoute.AUTOMATIC_OPEN
                ):
                    continue
                try:
                    downloaded = self.acquisition_download_open(
                        workspace=root,
                        request_id=current.request_id,
                        http_client=download_http_client,
                        resume_refresh=False,
                    )
                    payload["automatic_downloads"].append(downloaded)
                except Exception as exc:  # preserve a traceable operator fallback
                    payload["automatic_download_errors"].append(
                        {
                            "request_id": current.request_id,
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                        }
                    )

        engine = WorkflowEngine.load(root)
        current_by_id = {
            request.request_id: request for request in engine.state.acquisition_requests
        }
        payload["acquisition_requests"] = [
            current_by_id[request.request_id].model_dump(mode="json") for request in requests
        ]
        engine.record_decision(discovery_key, payload)
        if refresh_key is not None:
            open_ids = [
                request.request_id
                for request in requests
                if current_by_id[request.request_id].status == "open"
            ]
            if open_ids:
                engine.wait_for_literature_acquisition(
                    refresh_id=str(refresh["refresh_id"]),
                    request_ids=open_ids,
                )
            else:
                payload["workflow_resume"] = self.literature_refresh_complete(
                    workspace=root,
                    refresh_id=str(refresh["refresh_id"]),
                )
        return payload

    def literature_refresh_complete(
        self,
        *,
        workspace: Path,
        refresh_id: str,
    ) -> dict[str, Any]:
        """Merge acquired files, then wait until the operator confirms recommended reading."""
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        key = f"literature_refresh:{refresh_id}"
        decision = engine.state.decisions.get(key)
        if decision is None:
            raise ValueError(f"Unknown literature refresh: {refresh_id}")
        requests_by_id = {
            request.request_id: request for request in engine.state.acquisition_requests
        }
        request_ids = list(decision.get("acquisition_request_ids", []))
        open_ids = [
            request_id
            for request_id in request_ids
            if request_id not in requests_by_id or requests_by_id[request_id].status == "open"
        ]
        if open_ids:
            raise ValueError(
                "Literature refresh still has unresolved acquisition requests: "
                + ", ".join(open_ids)
            )
        engine.record_decision(key, {**decision, "status": "corpus_refresh"})
        run_extraction = decision.get("origin_phase") != PhaseId.PHASE_0.value
        inventory = self.source_inventory(
            workspace=root,
            input_paths=[str(resolve_workspace_path(root, Path("acquisitions")))],
            run_extraction=run_extraction,
        )
        engine = WorkflowEngine.load(root)
        discovery = engine.state.decisions.get(str(decision.get("discovery_decision")), {})
        recommendation_ids = [
            str(card.get("work_id"))
            for card in discovery.get("recommendations", [])
            if card.get("work_id")
        ]
        packet_id = engine.wait_for_recommended_reading(
            refresh_id=refresh_id,
            recommendation_ids=recommendation_ids,
            corpus_counts=inventory["corpus_counts"],
        )
        return {
            **engine.state.model_dump(mode="json"),
            "refresh_id": refresh_id,
            "reading_packet_id": packet_id,
            "corpus_inventory": inventory,
        }

    def recommended_reading_acknowledge(
        self,
        *,
        workspace: Path,
        packet_id: str,
        reading_notes: list[str],
    ) -> dict[str, Any]:
        """Record operator reading notes and execute the exact saved resume action."""
        if not reading_notes or any(not note.strip() for note in reading_notes):
            raise ValueError("At least one non-empty recommended-reading note is required")
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        outstanding = engine.state.outstanding_question
        if outstanding is None or outstanding.payload.get("packet_type") != "recommended_reading":
            raise ValueError("No recommended-reading acknowledgement is currently expected")
        refresh_id = str(outstanding.payload["refresh_id"])
        resume = engine.record_answer(
            packet_id,
            {"reading_notes": reading_notes, "refresh_id": refresh_id},
        )
        key = f"literature_refresh:{refresh_id}"
        decision = engine.state.decisions.get(key)
        if decision is None:
            raise ValueError(f"Unknown literature refresh: {refresh_id}")
        engine.record_decision(
            key,
            {**decision, "status": "completed", "reading_notes": reading_notes},
        )
        return {
            **engine.state.model_dump(mode="json"),
            "resume_action_executed": resume.model_dump(mode="json"),
        }

    def acquisition_request_list(self, workspace: Path) -> list[dict[str, Any]]:
        requests = WorkflowEngine.load(Path(workspace)).state.acquisition_requests
        return [request.model_dump(mode="json") for request in requests]

    def acquisition_request_create(
        self,
        *,
        workspace: Path,
        request_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        engine = WorkflowEngine.load(Path(workspace))
        request = AcquisitionRequest.model_validate(request_payload)
        engine.add_acquisition_request(request)
        return request.model_dump(mode="json")

    def acquisition_import(
        self,
        *,
        workspace: Path,
        request_id: str,
        relative_path: str,
        expected_identity: Mapping[str, Any],
        download_metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        request = next(
            (item for item in engine.state.acquisition_requests if item.request_id == request_id),
            None,
        )
        if request is None:
            raise ValueError(f"Unknown acquisition request: {request_id}")
        path = resolve_workspace_path(root, Path(relative_path))
        acquisition_root = resolve_workspace_path(root, Path("acquisitions"))
        if not path.is_relative_to(acquisition_root):
            raise ValueError("Imported acquisition files must be placed under acquisitions")
        record = DownloadValidator().validate(
            path,
            ExpectedIdentity.model_validate(expected_identity),
            DownloadMetadata.model_validate(download_metadata),
        )
        atomic_write_json(
            path.with_suffix(".provenance.json"),
            {
                "schema_version": 1,
                "request_id": request.request_id,
                "download": record.model_dump(mode="json"),
            },
        )
        engine.replace_acquisition_request(request.model_copy(update={"status": "fulfilled"}))
        payload = record.model_dump(mode="json")
        workflow_resume = self._resume_ready_literature_refresh(root)
        if workflow_resume is not None:
            payload["workflow_resume"] = workflow_resume
        return payload

    def acquisition_request_dismiss(
        self,
        *,
        workspace: Path,
        request_id: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Dismiss an unobtainable item with an explicit scientific rationale."""
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        request = next(
            (item for item in engine.state.acquisition_requests if item.request_id == request_id),
            None,
        )
        if request is None:
            raise ValueError(f"Unknown acquisition request: {request_id}")
        if request.status != "open":
            raise ValueError(f"Acquisition request is already {request.status}: {request_id}")
        updated = request.model_copy(update={"status": "dismissed", "resolution_note": rationale})
        updated = AcquisitionRequest.model_validate(updated.model_dump(mode="json"))
        engine.replace_acquisition_request(updated)
        engine.record_decision(
            f"acquisition_resolution:{request_id}",
            {"status": "dismissed", "rationale": rationale},
        )
        payload = updated.model_dump(mode="json")
        workflow_resume = self._resume_ready_literature_refresh(root)
        if workflow_resume is not None:
            payload["workflow_resume"] = workflow_resume
        return payload

    def acquisition_download_open(
        self,
        *,
        workspace: Path,
        request_id: str,
        http_client: Any | None = None,
        resume_refresh: bool = True,
    ) -> dict[str, Any]:
        """Download from the licensed open location already stored on a request."""
        root = Path(workspace).resolve(strict=False)
        request = next(
            (
                item
                for item in WorkflowEngine.load(root).state.acquisition_requests
                if item.request_id == request_id
            ),
            None,
        )
        if request is None:
            raise ValueError(f"Unknown acquisition request: {request_id}")
        if request.route is not AcquisitionRoute.AUTOMATIC_OPEN:
            raise ValueError(f"Acquisition request is not an automatic open route: {request_id}")
        if (
            request.pdf_url is None
            or request.access_basis is None
            or request.license_or_terms is None
        ):
            raise ValueError(
                f"Automatic open request lacks auditable access metadata: {request_id}"
            )
        return self.acquisition_download(
            workspace=root,
            request_id=request_id,
            pdf_url=str(request.pdf_url),
            expected_identity={"doi": request.doi, "title": request.title},
            access_basis=request.access_basis,
            license_or_terms=request.license_or_terms,
            observed_doi=request.doi,
            observed_title=request.title,
            version=request.version,
            http_client=http_client,
            resume_refresh=resume_refresh,
        )

    def acquisition_download(
        self,
        *,
        workspace: Path,
        request_id: str,
        pdf_url: str,
        expected_identity: Mapping[str, Any],
        access_basis: str,
        license_or_terms: str,
        observed_doi: str | None = None,
        observed_title: str | None = None,
        version: str | None = None,
        http_client: Any | None = None,
        maximum_bytes: int = 50 * 1024 * 1024,
        resume_refresh: bool = True,
    ) -> dict[str, Any]:
        """Download one explicitly lawful public PDF into the isolated workspace."""
        import httpx

        from review_workflow.adapters.acquisition import DownloadMetadata

        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        request_record = next(
            (item for item in engine.state.acquisition_requests if item.request_id == request_id),
            None,
        )
        if request_record is None:
            raise ValueError(f"Unknown acquisition request: {request_id}")
        _require_public_http_url(pdf_url)
        downloads = resolve_workspace_path(root, Path("acquisitions/downloads"))
        downloads.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="download-", suffix=".pdf", dir=downloads
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        owned_client = http_client is None
        client = http_client or httpx.Client(timeout=60, follow_redirects=True)
        try:
            response = client.get(pdf_url)
            response.raise_for_status()
            _require_public_http_url(str(response.url))
            content = response.content
            if len(content) > maximum_bytes:
                raise ValueError(f"Downloaded PDF exceeds the {maximum_bytes}-byte safety ceiling")
            temporary.write_bytes(content)
            record = DownloadValidator().validate(
                temporary,
                ExpectedIdentity.model_validate(expected_identity),
                DownloadMetadata(
                    content_type=response.headers.get("Content-Type"),
                    source_url=str(response.url),
                    access_basis=access_basis,
                    license_or_terms=license_or_terms,
                    document_role="full_text",
                    observed_doi=observed_doi,
                    observed_title=observed_title,
                    version=version,
                ),
            )
            destination = resolve_workspace_path(
                root,
                Path("acquisitions/downloads", f"{request_record.request_id}.pdf"),
            )
            if destination.exists():
                if sha256_file(destination) != record.sha256:
                    raise FileExistsError(
                        "A different acquisition file already exists for "
                        f"{request_record.request_id}"
                    )
                temporary.unlink(missing_ok=True)
            else:
                os.replace(temporary, destination)
            record = record.model_copy(update={"path": destination})
            atomic_write_json(
                destination.with_suffix(".provenance.json"),
                {
                    "schema_version": 1,
                    "request_id": request_record.request_id,
                    "download": record.model_dump(mode="json"),
                },
            )
            engine.replace_acquisition_request(
                request_record.model_copy(update={"status": "fulfilled"})
            )
            payload = record.model_dump(mode="json")
            if resume_refresh:
                workflow_resume = self._resume_ready_literature_refresh(root)
                if workflow_resume is not None:
                    payload["workflow_resume"] = workflow_resume
            return payload
        finally:
            temporary.unlink(missing_ok=True)
            if owned_client:
                client.close()

    def _resume_ready_literature_refresh(
        self,
        workspace: Path,
    ) -> dict[str, Any] | None:
        engine = WorkflowEngine.load(workspace)
        pending = [
            value
            for key, value in engine.state.decisions.items()
            if key.startswith("literature_refresh:")
            and isinstance(value, dict)
            and value.get("status") in {"acquisition_wait", "corpus_refresh"}
        ]
        if len(pending) > 1:
            raise ValueError("Multiple active literature refreshes require operator repair")
        if not pending:
            return None
        decision = pending[0]
        requests_by_id = {
            request.request_id: request for request in engine.state.acquisition_requests
        }
        if any(
            request_id not in requests_by_id or requests_by_id[request_id].status == "open"
            for request_id in decision.get("acquisition_request_ids", [])
        ):
            return None
        return self.literature_refresh_complete(
            workspace=workspace,
            refresh_id=str(decision["refresh_id"]),
        )

    def privacy_decision_record(
        self,
        *,
        workspace: Path,
        record_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        root = Path(workspace).resolve(strict=False)
        engine = WorkflowEngine.load(root)
        record = DisclosureRecord.model_validate(record_payload)
        if any(
            item.disclosure_id == record.disclosure_id for item in engine.state.external_disclosures
        ):
            raise ValueError(f"Disclosure record already exists: {record.disclosure_id}")
        ledger = DisclosureLedger(resolve_workspace_path(root, Path("audit/disclosures.jsonl")))
        ledger.append(record)
        engine.add_disclosure(record)
        return record.model_dump(mode="json")


def _empty_scope_brief():
    # Import remains local to keep the common answer path small.
    from review_workflow.domain.loops import ScopeBrief

    return ScopeBrief()


def _matching_literature_refresh(
    engine: WorkflowEngine,
    search_lanes: Sequence[str],
) -> tuple[str | None, dict[str, Any] | None]:
    """Find the one pending refresh whose required lanes are covered by this search."""
    supplied = set(search_lanes)
    matches = [
        (key, dict(value))
        for key, value in engine.state.decisions.items()
        if key.startswith("literature_refresh:")
        and isinstance(value, dict)
        and value.get("status") == "search_required"
        and set(value.get("search_lanes", [])) <= supplied
    ]
    if len(matches) > 1:
        raise ValueError("Multiple pending literature refreshes match the supplied lanes")
    return matches[0] if matches else (None, None)


def _require_public_http_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Acquisition URL must use public HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Acquisition URL must not contain credentials")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Acquisition URL must not target a private or local address")
