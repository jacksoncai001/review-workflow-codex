# Phase contracts

The harness owns ordering and persistence; Codex owns scientific judgment and prose. Never skip a phase merely because the draft already contains text.

| Phase | Required input | Durable output | Exit condition |
|---|---|---|---|
| Preflight | requested review type and workspace | runtime/profile report | writable workspace and valid profile |
| Phase 0 | draft cues, operator concern, prior scope | search lanes, 2–3 recommendation cards, automatic licensed-OA downloads, operator acquisition ledger | files resolved and operator reading notes acknowledged, or an explicit acquisition/reading wait |
| Phase 1 | inventoried PDF/DOCX sources | immutable extractions, source manifest, FTS index, quality warnings | required identities/locators usable; degraded checks recorded |
| Phase 2A | initial corpus and recommended reading | at least three reciprocal rounds and scope brief | all scope requirements resolved; evidence feasible |
| Phase 2B | scope brief | audience/decision and nearest-review comparison | differences are testable, not slogans |
| Phase 2C | positioning comparison | at least three architecture candidates | candidates materially differ |
| Phase 2D | candidates and evidence feasibility | weighted scorecards and preserved losers | one candidate meets every threshold |
| Phase 2E | winner and risks | approved outline/version | operator approves `phase_2e_outline` |
| Phase 3 | approved outline and corpus | claim-level evidence matrix | core claims pass evidence ceilings |
| Phase 4 | claims and section contracts | anchored manuscript blocks and visuals | section contracts pass |
| Phase 5 | manuscript, citations, bibliography | semantic citation audit and repairs | operator approves `phase_5_citation` |
| Phase 6 | audited manuscript | bounded reviewer findings and dispositions | no P0; operator approves `phase_6_review` |
| Phase 7 | accepted manuscript and records | reproducibility/migration bundle | operator approves `phase_7_final`; workflow completes |

## Architecture scoring

Score each candidate out of 100 with exact weights:

- target-reader need and decision usefulness: 20;
- differentiation from nearest reviews: 25;
- value of the unresolved problem: 20;
- synthesis/actionability: 15;
- evidence feasibility: 10;
- newcomer accessibility: 5;
- publication-mode fit: 5.

Eligibility requires total at least 75, reader score at least 14, differentiation at least 18, and unresolved-value score at least 14. A P0 evidence gap or unbounded novelty premise blocks the candidate regardless of total.

## Human gates

The mandatory gates are Phase 2E, Phase 5, Phase 6, and Phase 7. Show the exact artifact version, material limitations, unresolved risks, and what approval permits. Approval is never inferred from silence or from approval of an earlier version.

## Failure return object

Classify the root cause, not the page on which it was noticed. Supply failure ID, kind, reason, origin phase/step, changed artifact IDs, repair phase when causal selection is allowed, and a verifiable stop condition. Before resume, provide a resolution note and fresh, hash-valid evidence artifacts of a kind appropriate to that failure. Resume only the saved action after repair; never leap to the next phase.
