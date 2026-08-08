# Reciprocal interaction policy

The Phase 2A dialogue is a mutual inquiry, not a one-sided questionnaire.

## Per-round protocol

1. Read prior round records and corpus/search changes.
2. Ask 3–5 Codex questions. Prefer questions whose answers can change scope, evidence needs, positioning, or publication mode.
3. Set `WAITING_USER` through `question_packet_open` and present the packet.
4. The operator answers each Codex question and asks 3–5 questions of Codex.
5. Answer each operator question with an evidence basis or a clearly marked inference/unknown.
6. Record both directions with `answer_packet_record`, including changed assumptions, tensions, and new search lanes.
7. If new lanes exist, follow the durable Phase 0 refresh: call `literature_discover`, let it fetch licensed open PDFs, and present unresolved acquisition requests. The last import or justified dismissal rebuilds the merged corpus and opens a recommended-reading wait. Record the operator's notes with `recommended_reading_acknowledge`; only then restore the saved Phase 2A step.
8. Otherwise, follow the returned resume action immediately in the same active task unless it reaches another wait or gate.

Minimum three complete rounds are mandatory. More rounds are allowed when requirements remain incomplete. Do not pad rounds with low-value questions.

## Coverage across rounds

- Round 1 usually tests intended readers, their prior knowledge, the decision they need to make, and why the current draft is hard to understand.
- Round 2 usually tests scope boundaries, nearest reviews, the strongest differentiator, and missing/contradictory literature.
- Round 3 usually tests the unresolved problem, evidence feasibility, newcomer explanation needs, publication mode, and what would falsify the proposed positioning.

Adapt categories to the operator's answers; this is guidance, not a fixed script.

## Completion brief

Before Phase 2B, record all of:

- allowed review type: narrative, critical, or technical;
- primary and secondary readers;
- reader decision or task;
- included and excluded boundaries;
- nearest-review identities;
- a concrete nearest-review distinction;
- unresolved problem;
- proposed contribution;
- feasible evidence judgment;
- single or companion publication mode.

## Waiting and automatic continuation

`WAITING_USER` and `WAITING_ACQUISITION` are explicit state, not failures. Once a valid answer or file resolves the wait, resume its exact stored action and automatically continue while the Codex task remains active. Never claim an unattended background process. An explicit stop, pause, or workflow adjustment from the operator takes priority.
