# Design decisions

## 2026-10-25 — fix shape (DM 01M5T0ZHT04J7PWFV9DRCEVVGY)
- Chose the issue's first shape: do not materialise when nothing would drop. The second shape, a provenance marker, was rejected for two reasons:
  - The activation ledger's L1 validation refuses an unknown non-deny key (`activation_ledger.py:227`). A marker therefore needs a schema change, and every older rc8 CLI would fail closed reading the file.
  - A marker cannot be backfilled for a project that is already seeded, because a seeded list cannot be told apart from one an operator wrote.
- Already-seeded projects keep their list (C-004, #6499). Narrowing stays an operator action through #6408's `--narrow-activation` / `--only`. This is an open question for the operator.

## 2026-10-25 — post-spec squad folds (architect-alphonso, reviewer-renata)
- **Settle after the first run (BLOCKER).** `detect()` is True whenever the interview has selections, so the runner records `success`. A `skipped` record would re-run the migration on every upgrade, and after an operator `--only` it would append interview ids back.
- **Never materialise an absent key.** A resolved id is then either in force already or names no available artifact. This removes the fallback seed-and-append write, which could land on a legacy surface after the ledger move.
- **Compare present lists in identity space (#6423).**
- **Warning only, for already-seeded lists (FR-008).** The upgrade names the #6408 narrowing commands and makes no mutation (C-004).
- **Other folds:** `runs_on_worktrees = False`; a bundle restamp requirement; a dry-run preview requirement; NFR-002 is now a structural bound; Open Questions section added.
- **End-to-end reproduction.** It needs a version recorded below 3.2.6rc1. An rc7 stamp lets the ledger-adoption backfill settle the shipped promotion, and the reproduction then goes green on main without witnessing the bug (seen in the first run).
- **Deferred:**
  - Mission-step-contract ids do not resolve. This is pre-existing in `kind_vocabulary` and shared with the shipped migration.
  - Org-pack and project-layer resolution keeps parity with the shipped migration (built-in only).
