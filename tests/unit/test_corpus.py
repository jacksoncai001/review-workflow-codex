from __future__ import annotations

from pathlib import Path

from review_workflow.adapters.corpus import (
    CorpusChunk,
    CorpusStore,
    SourceRecord,
    compute_source_id,
)


def source(source_hash: str = "a" * 64) -> SourceRecord:
    return SourceRecord(
        source_id=compute_source_id(source_hash),
        source_hash=source_hash,
        original_path=Path("inputs/article.pdf"),
        size_bytes=2048,
        extension=".pdf",
        title="Synthetic article",
        doi="10.1000/synthetic",
    )


def chunks(source_id: str) -> list[CorpusChunk]:
    return [
        CorpusChunk(
            chunk_id="chunk-001",
            source_id=source_id,
            extraction_id="extract-001",
            page=3,
            section="Methods",
            text="External magnetic measurements require careful validation assumptions.",
        ),
        CorpusChunk(
            chunk_id="chunk-002",
            source_id=source_id,
            extraction_id="extract-001",
            page=8,
            section="Limitations",
            text="Classification accuracy does not establish current density reconstruction.",
        ),
    ]


def test_source_id_is_stable_and_ingest_does_not_double_count_exact_duplicate(
    tmp_path: Path,
) -> None:
    store = CorpusStore(tmp_path / "evidence.sqlite")
    record = source()

    store.ingest(record, chunks(record.source_id))
    store.ingest(record, chunks(record.source_id))

    assert compute_source_id("a" * 64) == record.source_id
    assert store.counts() == {"sources": 1, "chunks": 2}


def test_search_returns_page_and_section_locators(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "evidence.sqlite")
    record = source()
    store.ingest(record, chunks(record.source_id))

    hits = store.search("current density reconstruction", top_k=5)

    assert hits[0].source_id == record.source_id
    assert hits[0].page == 8
    assert hits[0].section == "Limitations"
    assert "current density reconstruction" in hits[0].text


def test_rebuild_index_preserves_search_results(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "evidence.sqlite")
    record = source()
    store.ingest(record, chunks(record.source_id))
    before = store.search("validation assumptions")

    store.rebuild_index()
    after = store.search("validation assumptions")

    assert after == before


def test_same_hash_with_second_path_remains_one_source(tmp_path: Path) -> None:
    store = CorpusStore(tmp_path / "evidence.sqlite")
    first = source()
    second = first.model_copy(update={"original_path": Path("inputs/copy.pdf")})

    store.ingest(first, chunks(first.source_id))
    store.ingest(second, chunks(second.source_id))

    assert store.counts()["sources"] == 1
