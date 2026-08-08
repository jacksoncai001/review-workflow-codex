---
name: build-evidence-grounded-review
description: Build or resume a local-first narrative, critical, or technical review from operator-supplied PDF/DOCX literature and draft manuscripts. Use when Codex must inventory and extract sources, recommend complementary papers, clarify the research question through reciprocal dialogue, compare review architectures, build claim-level evidence, draft or revise sections, audit citations, or migrate a resumable review workspace.
---

# Build an Evidence-Grounded Review

Use the local Review Workflow Codex MCP as the durable control plane. Treat `state.json`, not chat history, as authoritative. Read original PDFs and drafts in place; write every generated extraction, decision, outline, manuscript, and audit only inside the configured review workspace.

This skill supports narrative, critical, and technical reviews in engineering and natural science. Do not represent its output as a systematic review or meta-analysis. If the operator needs either, explain that this workflow lacks protocol registration, dual screening, formal risk-of-bias machinery, and quantitative synthesis.

## Start or resume

1. Call `project_status` when a workspace already exists. Continue from its `phase`, `step`, status, outstanding packet, gate, and resume action.
   If the workspace was copied to a different absolute path, call `project_relocate` once and then inspect status.
2. Call `project_init` only for a new isolated workspace. Ask for review type and choose `single` or `companion`; default to `single` only when the operator has not expressed a preference.
3. Call `preflight_check`. Recommend `full` when WSL2/Docker/GROBID is healthy and `windows-lite` otherwise. WSL2 is optional, not mandatory.
4. Never copy or alter operator inputs. Call `source_inventory` with `run_extraction=true` during Phase 1 to create reusable local Markdown, structured records, and an FTS index.
5. When status is `WAITING_USER` or `WAITING_ACQUISITION`, do only the work needed to present or resolve that wait. Do not pretend background execution continues after the Codex task ends.

Read [phase contracts](references/phase-contracts.md) before advancing phases. Read [interaction policy](references/interaction-policy.md) before opening the scoping loop. Read [evidence policy](references/evidence-policy.md) before architecture scoring, claim construction, drafting, or citation audit. Read [domain profiles](references/domain-profiles.md) only when selecting or authoring a domain YAML extension.

## Execute Phase 0 through Phase 7

### Phase 0 — orient, search, and acquire

Inventory the operator's drafts and literature without changing them. Derive bounded search lanes from titles, abstracts, draft headings, and stated concerns. Call `literature_discover` and recommend two or three complementary items with distinct roles: Anchor, Contrast, and optionally Bridge. Explain why each matters, what it may change, which sections to read, and whether the recommendation is based on metadata, abstract, or full text.

`literature_discover` creates a durable acquisition route for every recommendation and automatically downloads only locations that have both a verified open PDF URL and recorded license metadata. Present every still-open acquisition request to the operator; they may place a lawful copy under the workspace `acquisitions/` directory for `acquisition_import`, or explicitly use `acquisition_request_dismiss` with a scientific rationale. Once files are resolved, ask the operator to read the recommendations and provide concise notes; call `recommended_reading_acknowledge` only after that response. Never use login automation, proxy access, CAPTCHA bypass, or paywall circumvention.

### Phase 1 — extract and build the reusable corpus

Call `source_inventory` with all input locations and `run_extraction=true`. Inspect degraded capabilities and mandatory manual checks. In `windows-lite`, require manual bibliography and in-text citation-structure inspection before approving Phase 5. For missing pages, figures, tables, equations, identity, or bibliography, call `return_route` with `extraction_or_identity` and repair Phase 1. Reuse immutable extraction IDs when hashes and parser configuration match.

### Phase 2A — reciprocal scoping loop

Conduct at least three complete reciprocal rounds. In every round Codex asks 3–5 questions and the operator asks 3–5 questions, for 6–10 questions in total. Cover target readers, the decision the review should support, scope inclusions/exclusions, nearest reviews, the sharpest distinction, unresolved value, evidence feasibility, and publication mode.

Open Codex's half with `question_packet_open`. After the operator answers and asks their questions, answer all operator questions, then call `answer_packet_record` with both sides. If answers reveal new literature lanes, return to Phase 0, resolve them, and resume the recorded Phase 2A action. Do not declare scope complete before three rounds or while a required scope field remains unresolved.

When an answer contains new search lanes, `answer_packet_record` durably moves the workflow to Phase 0 and retains the exact Phase 2A resume action. Immediately call `literature_discover`; it downloads licensed open files and changes the state to `WAITING_ACQUISITION` when any recommendation still needs the operator. The final `acquisition_import` or justified `acquisition_request_dismiss` merges the expanded acquisition folder into the existing corpus, then enters `WAITING_USER` for recommended reading. After the operator supplies notes, `recommended_reading_acknowledge` resumes the saved Phase 2A step. Use `literature_refresh_complete` only to retry the merge after a repairable extraction failure.

After a valid answer is recorded, automatically continue within the same Codex turn from the returned action until the next genuine wait, human gate, retryable failure, operator pause, or completion. Do not stop merely because one answer arrived.

### Phase 2B–2E — compete architectures and approve one

Generate at least three materially different structures. Score them against this review's intended reader, nearest-review differentiation, unresolved problem, usable synthesis, evidence feasibility, newcomer accessibility, and publication fit. Preserve losing candidates and rationales. A polished but undifferentiated structure must not win.

At Phase 2E present the winner, alternatives, scorecards, scope brief, and unresolved risks. Wait for explicit operator approval, then call `gate_approve` with `phase_2e_outline`. A user's revision is a new version, not silent overwrite.

### Phase 3 — build claim-level evidence

Create claims before prose. For every consequential claim record the claim ceiling, evidence direction, source identity, full-text/abstract basis, page or section locator, independence count, limitations, and affected section. Search the local corpus with `evidence_search`. Return missing literature to Phase 0, extraction defects to Phase 1, weak positioning to Phase 2, and claim-support defects to Phase 3.

### Phase 4 — draft by section contracts

Draft only against the approved outline and verified claim matrix. Give newcomers enough shared concepts, measurement chains, and boundary definitions to follow the argument. Use stable block anchors and hash-guarded patches; do not regenerate an unaffected whole manuscript after a local defect. Treat figures and tables as evidence-bearing artifacts, not decoration.

### Phase 5 — semantic citation audit

Audit sentence meaning against the cited source, locator, direction, scope, strength, independence, citation distance, and bibliography existence. A plausible citation is not sufficient. Present all P0/P1 findings and the required repairs. Wait for operator review and call `gate_approve` with `phase_5_citation` only after the audit passes or limitations are explicitly accepted.

### Phase 6 — bounded critical review

Run no more than two broad review rounds. Each finding must be `addressed`, `disagreed_with_reason`, or `accepted_as_limitation`; never erase a concern silently. A remaining P0 blocks completion. Present the delta and wait for operator approval, then call `gate_approve` with `phase_6_review`.

### Phase 7 — package and hand off

Create the final manuscript plus scope brief, search lanes, source manifest, extraction provenance, architecture scorecards, claim matrix, citation audit, review dispositions, state/events, environment/profile record, and migration instructions. Record whether DOCX/PDF visual QA was performed. Wait for final operator approval, call `gate_approve` with `phase_7_final`, and then call `workflow_complete`.

## Returns, waits, and operator changes

Use `return_route` rather than inventing a separate rework phase:

- missing literature → Phase 0;
- identity, page, figure, table, or extraction defect → Phase 1;
- weak or non-distinct positioning → Phase 2;
- unsupported claim → Phase 3;
- prose or visual defect → Phase 4;
- semantic citation defect → the causal Phase 3–5;
- review failure → the causal Phase 4–6.

Register generated files and their dependencies with `artifact_register`. A repaired upstream artifact makes only its descendants stale. Preserve independent extraction and decisions. Respect an explicit operator stop or adjustment immediately; otherwise continue automatically only while the current Codex task remains active.

Before `return_resume`, replace every changed artifact, rebuild every stale descendant, and provide a substantive resolution note plus current evidence artifact IDs whose kinds match the failure's stop condition. Do not use an unrelated old artifact merely to unlock resume; the harness verifies kind, hash, freshness, and the recorded stop condition.

## Privacy and scientific integrity

Bibliographic metadata, search query text, and short snippets may use configured scholarly APIs. Keep full text and draft prose local by default. External disclosure of full text or draft prose requires destination-specific explicit consent recorded with `privacy_decision_record`; credentials are never permitted. Do not infer inaccessible full-text content from an abstract, fabricate a locator, strengthen association into causation, or claim global novelty without a bounded search basis.
