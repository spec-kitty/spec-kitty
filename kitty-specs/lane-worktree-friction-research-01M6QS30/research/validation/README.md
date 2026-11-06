# Validation artifacts

## What is here

- **`issue-holdout-numbers.json`**: the 45 issue numbers used as a fresh holdout for the issue heuristic. Their hand labels are in `../issue-hand-labels.csv`, and `../scripts/issue_agreement.py` computes the agreement:

  | Measure | Agreement |
  |---|---|
  | Lane vs not lane | 42/45 |
  | Cause code | 40/45 |
  | Severity | 23/45 |

- **Independent re-check (pre-PR adversarial squad, evidence lens, 2026-11-06).** The reviewer re-labelled 16 random rows of each source:

  | Source | Lane vs not | Cause code |
  |---|---|---|
  | Issues | 16/16 | about 12/16 (75%) |
  | Tracers | 14/16 | not reported |

  Both tracer disagreements counted an entry as lane-related when it was not. The 32% tracer share is therefore an upper estimate.

## What is missing

- **Tracer hand check.** The 50-entry hand check of the tracer rules is not recorded as an artifact. Its 85-90% figure is unverified; rely on the 14/16 re-check above.
- **Subject-bias split.** The split of Missions whose subject is lanes or coordination is not recorded either. The original analyst counted 42 Missions and 112 entries, leaving a 28.5% share outside them. The reviewer's regex proxy counted 29 Missions and 29.5%. Report the share as about 28-30%.
