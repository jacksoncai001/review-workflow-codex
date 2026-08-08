# Windows installation

## Choose a profile

`windows-lite` is a complete supported path for narrative, critical, and technical reviews. It uses local Python extractors and requires a manual Phase 5 check of bibliography and in-text citation structure.

`full` adds the layout-aware extraction dependencies and expects GROBID 0.9.0 at `http://127.0.0.1:8070`. WSL2 is recommended for this profile because the official GROBID image is easiest to run through Docker Engine in WSL2. WSL2 is not technically mandatory for the product.

## Install global commands and the Codex plugin

Prerequisites: Windows PowerShell, Git, `uv`, Python 3.12 (which `uv` can manage), and a current Codex CLI/Desktop installation.

Clone the private repository after GitHub access has been granted, then enter it:

```powershell
git clone https://github.com/jacksoncai001/review-workflow-codex.git
Set-Location review-workflow-codex
```

Preview without changing anything:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -WhatIf
```

Install the lighter profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -Profile windows-lite
```

Install the full Python profile:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-windows.ps1 -Profile full
```

The script installs `review-flow` and `review-flow-mcp` globally with `uv tool`, registers this repository as the `review-workflow-codex` marketplace when absent, installs the plugin when absent, and verifies the commands. It does not rewrite unrelated Codex MCP configuration.

## Optional WSL2/Docker/GROBID

The read-only check does not create or start a container:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-grobid.ps1
```

After installing Docker Engine inside the default WSL2 distribution, explicitly create or start the pinned container:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check-grobid.ps1 -Start
```

With `-Start`, the script also starts a stopped Docker service inside WSL using the WSL root account. It never removes or replaces an existing container. If a different container already owns port 8070, resolve that conflict manually.

On Windows, the Docling adapter disables only PyTorch's optional model-compilation acceleration. This avoids locale-dependent compiler output failures while retaining Docling's layout inference.

## Scholarly API settings

Set `OPENALEX_API_KEY` for OpenAlex. Set `CROSSREF_POLITE_EMAIL` for Crossref's polite pool and either that variable or `UNPAYWALL_EMAIL` for Unpaywall. Do not place credentials in project YAML, plugin manifests, prompts, or Git.

## Verify

```powershell
review-flow --help
review-flow-mcp
codex plugin list --marketplace review-workflow-codex --json
codex mcp list
```

`review-flow-mcp` is a stdio server and normally waits silently for a client; press Ctrl+C when testing it directly.
