"""Phase 1 extraction persistence and local evidence indexing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from review_workflow.adapters.corpus import CorpusChunk, CorpusStore, SourceRecord
from review_workflow.adapters.extraction import (
    ExtractionResult,
    ExtractionRouter,
    ExtractionTool,
    ToolAvailability,
    compute_extraction_id,
    extractor_for,
)
from review_workflow.adapters.filesystem import (
    atomic_write_json,
    atomic_write_text,
    resolve_workspace_path,
    sha256_file,
)
from review_workflow.adapters.grobid import GrobidAdapter
from review_workflow.domain.models import ExecutionProfile


class CorpusService:
    """Execute selected local parsers and retain immutable, reusable outputs."""

    def __init__(
        self,
        *,
        availability: ToolAvailability | None = None,
        grobid_adapter: Any | None = None,
        grobid_version: str = "0.9.0",
    ) -> None:
        self.availability = availability
        self.grobid_adapter = grobid_adapter or GrobidAdapter()
        self.grobid_version = grobid_version

    def extract_and_index(
        self,
        *,
        workspace: Path,
        sources: list[SourceRecord],
        profile: ExecutionProfile,
    ) -> dict[str, Any]:
        root = workspace.resolve(strict=False)
        availability = self.availability or self.detect_tools()
        router = ExtractionRouter(profile, availability)
        store = CorpusStore(resolve_workspace_path(root, Path("corpus/index/corpus.sqlite3")))
        extraction_reports: list[dict[str, Any]] = []
        for source in sources:
            source_path = source.original_path.resolve(strict=False)
            if sha256_file(source_path) != source.source_hash:
                raise ValueError(f"Source changed after inventory: {source.source_id}")
            plan = router.route(source_path)
            runnable = [tool for tool in plan.parsers if tool is not ExtractionTool.GROBID]
            if not runnable:
                raise RuntimeError(
                    f"No installed extractor can process {source_path.suffix.lower()}; "
                    f"degraded={plan.degraded_capabilities}"
                )
            result = extractor_for(runnable[0]).extract(
                source_path,
                source_id=source.source_id,
                source_hash=source.source_hash,
            )
            report = self._persist_result(root, result)
            report["degraded_capabilities"] = plan.degraded_capabilities
            report["mandatory_manual_checks"] = plan.mandatory_manual_checks
            if ExtractionTool.GROBID in plan.parsers:
                report.update(self._persist_grobid(root, source_path, source))
            chunks = _chunks_from_result(result)
            store.ingest(source, chunks)
            extraction_reports.append(report)
        return {"extractions": extraction_reports, "corpus_counts": store.counts()}

    def _persist_grobid(
        self,
        root: Path,
        source_path: Path,
        source: SourceRecord,
    ) -> dict[str, Any]:
        extraction_id = compute_extraction_id(
            source_hash=source.source_hash,
            parser="grobid",
            parser_version=self.grobid_version,
            parser_config={"endpoint": "processFulltextDocument"},
            schema_version=1,
        )
        directory = resolve_workspace_path(
            root,
            Path(
                "corpus/extractions",
                _storage_key(source.source_id),
                _storage_key(extraction_id),
            ),
        )
        tei_path = directory / "fulltext.tei.xml"
        document = self.grobid_adapter.process_fulltext(source_path)
        normalized = document.tei_xml.rstrip() + "\n"
        reused = tei_path.exists()
        if reused:
            if tei_path.read_text(encoding="utf-8") != normalized:
                raise ValueError(f"Immutable GROBID extraction drift: {extraction_id}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            atomic_write_text(tei_path, normalized)
            atomic_write_json(
                directory / "provenance.json",
                {
                    "schema_version": 1,
                    "source_id": source.source_id,
                    "source_hash": source.source_hash,
                    "extraction_id": extraction_id,
                    "parser": "grobid",
                    "parser_version": self.grobid_version,
                },
            )
        return {
            "tei_path": str(tei_path.resolve(strict=False)),
            "tei_extraction_id": extraction_id,
            "tei_reused": reused,
        }

    @staticmethod
    def detect_tools() -> ToolAvailability:
        return ToolAvailability(
            markitdown=importlib.util.find_spec("markitdown") is not None,
            docling=importlib.util.find_spec("docling") is not None,
            grobid=GrobidAdapter(timeout=0.25).health().healthy,
            pypdf=importlib.util.find_spec("pypdf") is not None,
            python_docx=importlib.util.find_spec("docx") is not None,
        )

    @staticmethod
    def _persist_result(root: Path, result: ExtractionResult) -> dict[str, Any]:
        # Keep physical keys short enough for legacy Windows MAX_PATH while retaining
        # the complete collision-resistant identities inside extraction.json.
        relative_directory = Path(
            "corpus/extractions",
            _storage_key(result.source_id),
            _storage_key(result.extraction_id),
        )
        directory = resolve_workspace_path(root, relative_directory)
        json_path = directory / "extraction.json"
        markdown_path = directory / "document.md"
        reused = json_path.exists() and markdown_path.exists()
        if reused:
            existing = ExtractionResult.model_validate_json(json_path.read_text(encoding="utf-8"))
            if existing != result:
                raise ValueError(
                    f"Immutable extraction ID collision or parser drift: {result.extraction_id}"
                )
        else:
            directory.mkdir(parents=True, exist_ok=True)
            atomic_write_json(json_path, result.model_dump(mode="json"))
            atomic_write_text(markdown_path, result.markdown)
        return {
            "source_id": result.source_id,
            "extraction_id": result.extraction_id,
            "parser": result.parser,
            "parser_version": result.parser_version,
            "page_count": result.page_count,
            "figure_count": result.figure_count,
            "table_count": len(result.tables),
            "warning_count": len(result.warnings),
            "markdown_path": str(markdown_path.resolve(strict=False)),
            "record_path": str(json_path.resolve(strict=False)),
            "reused": reused,
        }


def _chunks_from_result(
    result: ExtractionResult, maximum_characters: int = 2400
) -> list[CorpusChunk]:
    chunks: list[CorpusChunk] = []
    for unit in result.units:
        text = unit.text.strip()
        if not text:
            continue
        pieces = [
            text[index : index + maximum_characters]
            for index in range(0, len(text), maximum_characters)
        ]
        for piece_number, piece in enumerate(pieces, start=1):
            chunk_id = f"{result.extraction_id}:{unit.unit_id}:{piece_number}"
            chunks.append(
                CorpusChunk(
                    chunk_id=chunk_id,
                    source_id=result.source_id,
                    extraction_id=result.extraction_id,
                    page=unit.page,
                    section=unit.section,
                    text=piece,
                )
            )
    return chunks


def _storage_key(identifier: str) -> str:
    prefix, _, digest = identifier.partition("-")
    return f"{prefix}-{digest[:20]}"
