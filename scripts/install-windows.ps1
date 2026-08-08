[CmdletBinding()]
param(
    [ValidateSet("windows-lite", "full")]
    [string]$Profile = "windows-lite",
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$MarketplaceName = "review-workflow-codex"
$PluginId = "review-workflow-codex@$MarketplaceName"

if (-not (Test-Path -LiteralPath (Join-Path $RepositoryRoot "pyproject.toml") -PathType Leaf)) {
    throw "Repository root is missing pyproject.toml: $RepositoryRoot"
}

if ($WhatIf) {
    Write-Output "DRY RUN: no packages, Codex configuration, plugins, containers, or files will be changed."
    Write-Output "Would run: uv tool install --force --python 3.12 <repository-with-profile-extras>"
    Write-Output "Would run if absent: codex plugin marketplace add <repository> --json"
    Write-Output "Would run if absent: codex plugin add $PluginId --json"
    Write-Output "Would verify: review-flow, review-flow-mcp, codex plugin list, codex mcp list"
    exit 0
}

foreach ($CommandName in @("uv", "codex")) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Required command is not available on PATH: $CommandName"
    }
}

$PackageSpec = if ($Profile -eq "full") {
    "${RepositoryRoot}[full]"
} else {
    "${RepositoryRoot}[extract,discovery]"
}

# Use explicit UTF-8 so the official Skill validator works on Chinese Windows locales.
$env:PYTHONUTF8 = "1"
& uv tool install --force --python 3.12 $PackageSpec
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed with exit code $LASTEXITCODE" }

$MarketplacePayload = & codex plugin marketplace list --json | ConvertFrom-Json
$Marketplace = $MarketplacePayload.marketplaces | Where-Object { $_.name -eq $MarketplaceName }
if (-not $Marketplace) {
    & codex plugin marketplace add $RepositoryRoot --json
    if ($LASTEXITCODE -ne 0) { throw "codex plugin marketplace add failed" }
}

$PluginPayload = & codex plugin list --json | ConvertFrom-Json
$InstalledPlugin = $PluginPayload.installed | Where-Object { $_.pluginId -eq $PluginId }
if (-not $InstalledPlugin) {
    & codex plugin add $PluginId --json
    if ($LASTEXITCODE -ne 0) { throw "codex plugin add failed" }
}

foreach ($CommandName in @("review-flow", "review-flow-mcp")) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Installation finished but global command is not on PATH: $CommandName"
    }
}

& review-flow version
& codex plugin list --marketplace $MarketplaceName --json
& codex mcp list

if ($Profile -eq "full") {
    Write-Output "Python full-profile components are installed."
    Write-Output "Run scripts/check-grobid.ps1 to inspect WSL2/Docker/GROBID."
    Write-Output "Run scripts/check-grobid.ps1 -Start only when you explicitly want to create or start the container."
} else {
    Write-Output "windows-lite installed. WSL2 is optional; Phase 5 requires manual bibliography and in-text citation-structure checks."
}
