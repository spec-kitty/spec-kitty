---
doc_status: draft
updated: '2026-11-28'
---

# Approval and dispatch record

## Approval

On 2026-11-28 the human architect approved the pre-registration (`01-pre-registration.md` at commit `ab118801fd`), including its thresholds, and gave these additional instructions.

| Subject | Instruction |
|---|---|
| Window for H01 | 2026-07-01 to 2026-09-05, provisional, with the convergence merge treated separately. The full historical series is kept. |
| Supplementary repositories | All identified repositories are cloned read-only. |
| Outside observer | The prediction packet and the pre-registration are handed to the architect for manual delivery. Predictions are returned and recorded before the observer receives findings. |
| Separation | Prospective predictions, independent findings, synthesis, adversarial review and post-hoc evaluation stay distinct. |
| Consolidation | Findings are consolidated in this folder with traceability to the evidence. |
| Dialectical review | A review that keeps substantive disagreements, counterevidence and unresolved questions, without forcing consensus. |
| Report | After review, the `comms-cleo` profile writes the consolidated report in the established executive-debrief format, exported to PDF for manual delivery. It distinguishes empirically supported conclusions, architectural interpretations, prospective design recommendations and outstanding human decisions. |
| Authority | No implementation or remediation is authorised. |

The window was given after the coordinator had proposed the same dates from grounding. The architect had not been shown any measured series. It is recorded as provisional; the H01 comparison is read at the nearest measured points on or before each boundary (end of June 2026, and the last commit of each line before the convergence), and the comparison is repeated for the periods before and after.

## Stages

Each stage writes to its own place and does not overwrite an earlier one.

| Stage | Output | Who |
|---|---|---|
| 0. Predictions | `predictions-outside-observer.md`, when returned | outside observer, via the architect |
| 1. Investigation | `findings/<workstream>/`, `evidence/<workstream>/`, `workstream-reports/` | workstreams A1, A2, B1, B2, C, C2 (blind replication), D1, D2, E1, E2, E3, F, G1, G2, H06a, H06b |
| 2. Synthesis | `synthesis/` | `synthesizer-sam` |
| 3. Adversarial review | `review/` | `reviewer-renata` and others who authored nothing |
| 4. Post-hoc evaluation | `evaluation/` | a separate squad, judging method and outcome against the pre-registration |
| 5. Dialectical review | `dialectic/` | opposing positions kept side by side |
| 6. Report | `report/` (Markdown source, HTML and PDF) | `comms-cleo` |

## Dispatch

- Every workstream receives `dispatch/COMMON.txt` and its own brief in `dispatch/`. The briefs are stored as plain text so that the instructions are part of the record. They contain measures and scope and do not contain the hypotheses.
- Sections 1 to 4 of the pre-registration are reproduced in the common brief. Workstreams are told not to read the pre-registration, the rulings, the design brief or each other's output.
- Workstream E is split: E1 inventories gates, E2 writes mutations without seeing any gate, E3 applies them and runs the gates.
- Workstream C is run twice, on different models and profiles, without sight of each other.
- The coordinator's log of what the investigation needed outside native capabilities is `operations-log.txt`. It is a single case.

## Supplementary repositories

Read-only clones, revisions as cloned on 2026-11-28. They are listed with their revisions in `dispatch/COMMON.txt`. Nothing is written to them.

## Change to an earlier file

`03-access-requirements.md` asked for access. That request is now granted in full; the file is left as submitted.
