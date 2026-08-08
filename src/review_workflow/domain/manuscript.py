"""Section contracts, stable manuscript blocks, and hash-guarded local revision."""

from __future__ import annotations

import hashlib

from pydantic import Field

from review_workflow.domain.models import StrictModel


class PatchConflictError(ValueError):
    """Raised when a revision patch targets stale or different content."""


class SectionContract(StrictModel):
    schema_version: int = 1
    section_id: str
    heading: str
    question: str
    central_argument: str
    comparison_axis: str
    required_claim_ids: list[str] = Field(default_factory=list)
    counterevidence: list[str] = Field(default_factory=list)
    figure_table_plan: list[str] = Field(default_factory=list)
    transition_out: str
    exclusions: list[str] = Field(default_factory=list)
    newcomer_concepts: list[str] = Field(default_factory=list)
    target_words: int = Field(gt=0)


class ManuscriptBlock(StrictModel):
    schema_version: int = 1
    block_id: str
    heading: str
    text: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_text(cls, block_id: str, heading: str, text: str) -> ManuscriptBlock:
        return cls(
            block_id=block_id,
            heading=heading,
            text=text,
            content_hash=_block_hash(heading, text),
        )


class RevisionPatch(StrictModel):
    schema_version: int = 1
    block_id: str
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacement_text: str = Field(min_length=1)
    rationale: str = Field(min_length=3)
    finding_ids: list[str] = Field(default_factory=list)


def apply_revision_patch(block: ManuscriptBlock, patch: RevisionPatch) -> ManuscriptBlock:
    if patch.block_id != block.block_id:
        raise PatchConflictError(
            f"Patch target {patch.block_id!r} does not match block {block.block_id!r}"
        )
    if patch.expected_hash != block.content_hash:
        raise PatchConflictError("Patch expected hash does not match the current block hash")
    return ManuscriptBlock.from_text(
        block_id=block.block_id,
        heading=block.heading,
        text=patch.replacement_text,
    )


def _block_hash(heading: str, text: str) -> str:
    material = f"{heading}\n\n{text}".encode()
    return hashlib.sha256(material).hexdigest()
