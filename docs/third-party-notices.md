# Third-party boundaries and notices

Review Workflow Codex uses normal package dependencies and external scholarly services but does not vendor their source, prompts, datasets, or model weights.

## Runtime projects

- [Microsoft MarkItDown](https://github.com/microsoft/markitdown) is an optional local document-to-Markdown adapter. This project installs only its PDF and DOCX extras.
- [Docling](https://github.com/docling-project/docling) is an optional layout-aware local document adapter in the `full` profile. Its first use may obtain upstream model assets under their own terms.
- [GROBID](https://github.com/kermitt2/grobid) is an external local service. The Windows helper pins the official `grobid/grobid:0.9.0-full` image but does not redistribute it.
- [OpenAlex](https://docs.openalex.org/), [Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), and [Unpaywall](https://unpaywall.org/products/api) supply bibliographic metadata and lawful open-access locations under their respective API terms. The harness does not bypass publisher access controls.
- The Python MCP SDK, Pydantic, Typer, httpx, PyYAML, pypdf, and python-docx are installed from their normal distributions and remain governed by their upstream licenses.

Consult the locked dependency set and upstream license files before redistribution. This repository is publicly visible but currently has no project-level license; public visibility alone does not grant permission to reuse or redistribute its code beyond applicable law and GitHub's terms.

## Framework inspiration without code reuse

ARS-Codex / Academic Research Skills Codex was reviewed as design inspiration for role separation, staged integrity checks, patch-based revision, and bounded reviewer loops. The locally inspected ARS distribution declares CC BY-NC 4.0. This repository therefore does not copy its prompts, schemas, agent files, or source code. The reciprocal scoping protocol, phase/return state model, architecture score policy, domain-profile boundary, acquisition workflow, privacy guard, and artifact invalidation implementation here are independently written.

PaperQA2 and Co-STORM motivated consideration of corpus-grounded question answering and collaborative outline exploration, but neither project is embedded in v0.1. Engramory, llm-wiki, and Headcone are also not required or embedded.
