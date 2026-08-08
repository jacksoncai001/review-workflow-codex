from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "scripts" / "install-windows.ps1"
GROBID = ROOT / "scripts" / "check-grobid.ps1"


def test_windows_installer_is_dry_run_capable_and_uses_declared_global_commands() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "[switch]$WhatIf" in text
    assert "uv tool install" in text
    assert "--force" in text
    assert "review-flow-mcp" in text
    assert "codex plugin marketplace add" in text
    assert "codex plugin add" in text
    assert "PYTHONUTF8" in text
    assert "$HOME" not in text
    assert "Remove-Item -Recurse" not in text


def test_grobid_script_never_starts_container_without_explicit_start_switch() -> None:
    text = GROBID.read_text(encoding="utf-8")
    start_block = text.index("if ($Start)")
    docker_run = text.index("docker run")
    docker_service_start = text.index("service docker start")

    assert "[switch]$Start" in text
    assert "grobid/grobid:0.9.0-full" in text
    assert docker_run > start_block
    assert docker_service_start > start_block
    assert "docker rm" not in text
    assert "$HOME" not in text
    assert "Remove-Item" not in text


def test_windows_scripts_parse_and_installer_whatif_is_non_mutating() -> None:
    parse_command = (
        "$errors=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        f"'{INSTALLER}', [ref]$null, [ref]$errors) | Out-Null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{GROBID}', "
        "[ref]$null, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
    )
    parsed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", parse_command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    dry_run = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-WhatIf",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert parsed.returncode == 0, parsed.stderr
    assert dry_run.returncode == 0, dry_run.stderr
    assert "DRY RUN" in dry_run.stdout
