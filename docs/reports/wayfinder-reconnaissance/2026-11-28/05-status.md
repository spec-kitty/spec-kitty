---
doc_status: draft
updated: '2026-11-28'
---

# Status

| Stage | State | Where |
|---|---|---|
| 0. Predictions of the outside observer | Abandoned due to disclosure. The human architect reported on 2026-11-28 that the outside observer had received the consolidated findings and had given an assessment. No predictions were recorded, and none are reconstructed after the fact. | `02-prediction-packet.md` |
| 1. Investigation | Complete. 18 workstreams, 414 finding records (393 observations, 21 interpretations), 24 mutation patches. | `findings/`, `evidence/`, `workstream-reports/` |
| 2. Synthesis | Complete. Three synthesisers, evidence-first. | `synthesis/` |
| 3. Adversarial review | Complete. 162 findings sampled: 141 reproduced, 15 with a difference, 5 wider than their evidence, 1 mislabelled, 0 not reproduced. Two hypothesis verdicts overturned. | `review/` |
| 4. Post-hoc evaluation | Complete. Process and validity. | `evaluation/` |
| 5. Dialectical review | Complete. 23 points: 8 conceded, 9 narrowed, 6 open. | `dialectic/` |
| 6. Report | Complete, as a draft for the architect. Markdown source here; the PDF is handed over and not committed. | `report/` |

The verdicts of stages 2, 3 and 4 are kept side by side in `evaluation/verdict-ledger.csv`. Where they differ, the architect decides.

## Finding records per workstream

A1 38, A2 20, B1 27, B2 35, B3 13, C 33, C2 32, CX 13, D1 31, D2 22, E1 35, E2 7, E3 19, F 28, G1 12, G2 15, H06a 21, H06b 13.

## Limits, breaches and the coordinator's own failures

- Coverage limits and breaches declared by five workstreams (B3, H06a, F, C, E3): `synthesis/coordinator-procedure-notes.txt`.
- The process evaluation lists 20 deviations, most of them not declared by the coordinator, among them steering in four briefs and blind arms that were not blind: `evaluation/process-evaluation.md`, `evaluation/process-deviations.csv`.

## Changes to evidence after the review

After the review had checked all hashes, the repository's terminology gate failed on two evidence files that quote a retired term from repository text: `evidence/A2/other-glossary-index.txt` and `evidence/C2/change-chains-purposive.txt`. The coordinator inserted a `~` inside each occurrence, as the scrub tool does for other retired phrases, and replaced the two recorded SHA-256 values wherever they appear (four files). No other content changed. The reviewers' hash checks refer to the files before this change.

## Repositories attached late

`spec-kitty/spec-kitty-design` at `19fb6a224c` was cloned read-only for the report's fonts and logo only. It is not a subject of the investigation.

## Still open

- The comparison of prediction and result will not take place (stage 0 was abandoned). The report's statements that it is pending are superseded by this file.
- The decisions listed in `synthesis/open-human-decisions.md`.
- `spec-kitty-go` is not attached.
