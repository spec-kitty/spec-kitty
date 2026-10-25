# Approach

## 2026-10-25 — seed
- Supersede the shipped `unify_charter_activation_promote_answers` migration through `SUPERSEDED_MIGRATIONS`, with no edit to it.
- Add a 4.0.0rc8 successor, ordered after `4.0.0rc8_activation_ledger`. It promotes answers-only ids through `resolve_activation_write_target` and `promote_activations`.
- An absent key stays absent when every answers id is already in its in-force set.
- Red-first: an issue-pinned regression test drives the registered migration through the runner on the #6629 project shape, then calls the synthesis request builder and the establishment probe.

## 2026-10-25 — implement
- The first reproduction (an rc7 stamp) was green on main: the ledger-adoption backfill settles the shipped promotion. Moving the stamp to 3.2.0rc30 made it red. Lesson: a runner-driven repro of an old migration must stamp a version below it.
- Post-tasks folds were applied in WP01: seam re-exports, the dead-module entry, the deny-gate move, deny filtering before the write, and the audit fixture.
