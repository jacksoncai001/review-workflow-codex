# Public Low-Interruption Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the repository with an explicit email-only, best-effort support policy and minimal GitHub community features.

**Architecture:** Keep the source changes documentation-only and enforce the public support contract with a static release test. Apply GitHub visibility and feature settings through the browser after the tested documentation commit is pushed, then verify the browser state and GitHub metadata independently.

**Tech Stack:** Markdown, pytest, Git, GitHub web settings

## Global Constraints

- Publish only the existing 103-file source repository plus the approved support documentation.
- Never add manuscripts, PDFs, private extraction, credentials, or local workspaces.
- Public support email is exactly `1259081855@qq.com`.
- Issues, Projects, Discussions, and Wiki must be disabled.
- Pull requests remain available.
- Do not add a license without a separate owner decision.

---

### Task 1: Enforce the public support contract

**Files:**
- Modify: `tests/static/test_release_contract.py`
- Create: `.github/SUPPORT.md`
- Modify: `README.md`
- Modify: `docs/install-windows.md`

**Interfaces:**
- Consumes: the canonical URL `https://github.com/jacksoncai001/review-workflow-codex`.
- Produces: public installation wording and one recognized GitHub support document.

- [ ] **Step 1: Write the failing static test**

```python
def test_public_support_policy_is_explicit() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    support = (ROOT / ".github/SUPPORT.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{support}"
    assert "1259081855@qq.com" in combined
    assert "best effort" in combined.lower()
    assert "no response-time commitment" in combined.lower()
    assert "do not send" in combined.lower()
```

- [ ] **Step 2: Run the test and confirm the pre-change failure**

Run: `uv run pytest tests/static/test_release_contract.py::test_public_support_policy_is_explicit -q`

Expected: FAIL because `.github/SUPPORT.md` does not exist.

- [ ] **Step 3: Add the support policy and public installation wording**

Create `.github/SUPPORT.md` with the approved email, best-effort/no-SLA language,
and the sensitive-material warning. Add a concise support section to `README.md`.
Replace private-clone wording in `docs/install-windows.md` with public-clone wording.
Replace the README's pre-publication sentence with an accurate public/no-license
statement.

- [ ] **Step 4: Run targeted verification**

Run: `uv run pytest tests/static/test_release_contract.py -q`

Expected: all release-contract tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/static/test_release_contract.py .github/SUPPORT.md README.md docs/install-windows.md
git commit -m "docs: define low-interruption public support"
```

### Task 2: Verify and push the documentation change

**Files:**
- Verify: all tracked project files

**Interfaces:**
- Consumes: the Task 1 commit.
- Produces: a clean, tested `main` branch on GitHub before visibility changes.

- [ ] **Step 1: Run lint and tests**

```powershell
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Expected: lock check, lint, formatting, and the full suite pass.

- [ ] **Step 2: Confirm the staged and tracked file boundary**

Run: `git status --short`

Expected: no PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, `.env`, or review workspace is tracked.

- [ ] **Step 3: Push**

Run: `git -c http.proxy=http://127.0.0.1:7897 push origin main`

Expected: `main` advances on `jacksoncai001/review-workflow-codex`.

### Task 3: Apply public low-interruption GitHub settings

**Files:**
- External setting: `https://github.com/jacksoncai001/review-workflow-codex/settings`

**Interfaces:**
- Consumes: the tested public support commit on `main`.
- Produces: public visibility with Issues, Projects, Discussions, and Wiki disabled.

- [ ] **Step 1: Open repository Settings in the connected browser**

Verify the repository owner/name before changing any setting.

- [ ] **Step 2: Disable the four optional features**

Under General → Features, clear Issues, Projects, Discussions, and Wiki. Preserve
Pull Requests and Actions.

- [ ] **Step 3: Make the repository public**

Under Danger Zone → Change repository visibility, select Public and confirm the
repository name. This step is already authorized by the owner in the conversation.

- [ ] **Step 4: Verify the public repository page**

Open `https://github.com/jacksoncai001/review-workflow-codex` and confirm the Public
badge, README support section, and absence of Issues, Projects, Discussions, and
Wiki tabs.

- [ ] **Step 5: Verify metadata and QR target**

Confirm GitHub metadata reports `PUBLIC` plus all four feature flags disabled.
Decode `D:\review\review-workflow\share-assets\review-workflow-codex-github-qr.png`
and confirm it equals the canonical repository URL.
