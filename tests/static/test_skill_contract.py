from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "review-workflow-codex"
SKILL = PLUGIN / "skills" / "build-evidence-grounded-review"


def skill_frontmatter_and_body() -> tuple[dict, str]:
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def test_skill_has_minimal_valid_frontmatter_and_no_scaffold_placeholders() -> None:
    frontmatter, body = skill_frontmatter_and_body()

    assert set(frontmatter) == {"name", "description"}
    assert frontmatter["name"] == "build-evidence-grounded-review"
    assert len(body.splitlines()) < 500
    assert "TODO" not in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_skill_encodes_interaction_privacy_integrity_and_return_contracts() -> None:
    _, body = skill_frontmatter_and_body()
    lower = body.lower()

    for required in (
        "phase 0",
        "phase 7",
        "at least three",
        "3–5",
        "waiting_user",
        "automatically continue",
        "full text",
        "explicit consent",
        "systematic review",
        "meta-analysis",
        "return",
        "gate_approve",
    ):
        assert required in lower


def test_direct_references_exist_and_are_linked_once_without_deep_tree() -> None:
    _, body = skill_frontmatter_and_body()
    expected = {
        "phase-contracts.md",
        "evidence-policy.md",
        "interaction-policy.md",
        "domain-profiles.md",
    }
    files = {path.name for path in (SKILL / "references").glob("*.md")}

    assert files == expected
    assert not list((SKILL / "references").glob("*/*"))
    for name in expected:
        assert f"references/{name}" in body


def test_plugin_metadata_resolves_skill_and_global_mcp_command() -> None:
    manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))

    assert manifest["version"] == "0.1.0"
    assert (PLUGIN / manifest["skills"]).is_dir()
    assert (PLUGIN / manifest["mcpServers"]).is_file()
    assert mcp["mcpServers"]["review-workflow-codex"]["command"] == "review-flow-mcp"
    assert "TODO" not in json.dumps(manifest)
