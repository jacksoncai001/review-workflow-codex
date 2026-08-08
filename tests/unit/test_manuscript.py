from __future__ import annotations

import pytest

from review_workflow.domain.manuscript import (
    ManuscriptBlock,
    PatchConflictError,
    RevisionPatch,
    apply_revision_patch,
)


def test_hash_guarded_patch_updates_only_target_block() -> None:
    block = ManuscriptBlock.from_text(
        block_id="section-2-paragraph-3",
        heading="Measurement assumptions",
        text="Original qualified paragraph.",
    )
    patch = RevisionPatch(
        block_id=block.block_id,
        expected_hash=block.content_hash,
        replacement_text="Revised qualified paragraph with a clearer boundary.",
        rationale="Resolve reviewer concern R-01",
        finding_ids=["R-01"],
    )

    revised = apply_revision_patch(block, patch)

    assert revised.block_id == block.block_id
    assert revised.text.startswith("Revised")
    assert revised.content_hash != block.content_hash


def test_stale_block_hash_rejects_patch() -> None:
    block = ManuscriptBlock.from_text("block-001", "Heading", "Newer text")
    patch = RevisionPatch(
        block_id="block-001",
        expected_hash="a" * 64,
        replacement_text="Replacement",
        rationale="Attempt stale patch",
    )

    with pytest.raises(PatchConflictError, match="hash"):
        apply_revision_patch(block, patch)


def test_patch_cannot_target_another_block() -> None:
    block = ManuscriptBlock.from_text("block-001", "Heading", "Text")
    patch = RevisionPatch(
        block_id="block-002",
        expected_hash=block.content_hash,
        replacement_text="Replacement",
        rationale="Wrong target",
    )

    with pytest.raises(PatchConflictError, match="target"):
        apply_revision_patch(block, patch)
