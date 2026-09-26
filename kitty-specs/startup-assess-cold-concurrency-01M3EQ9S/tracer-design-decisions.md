# Tracer: Design Decisions

Mission: `startup-assess-cold-concurrency-01M3EQ9S`, which fixes P1 #3998.

See `research.md` D-1..D-8 for the full rationale. The headline decisions:

- **DD-1.** Escalate an unlocked torn read to the *same* serialization point `recheck_assets` uses. It is extracted, not re-derived (single authority).
- **DD-2.** The typed `TornReadError(ValueError)` carries the lock identity, which `incomplete()` would otherwise drop. String-prefix routing is retired.
- **DD-3.** The unlocked retry loop is removed. An unlocked retry can only re-race a writer that runs under a lock.
- **DD-4.** The point is released after the locked build rather than held through apply. `apply_with_reassess` already re-locks and re-checks.
- **DD-5.** FR-005 reuses the `GuardedReadError` presentation hook through `StartupAssetError(GuardedReadError, RuntimeError)`.

(append during implement/review)

## Closing: WP decomposition (3 → 2 WPs)

- **DD-6 (WP merge, `finalize-tasks` no-overlap gate).** `plan.md` sketched three sequential WPs: WP01 (red-first + tidy-first), WP02 (the fix), WP03 (closeout, small). WP01 and the planned WP02 would both own `src/specify_cli/runtime/asset_preparation.py` — `finalize-tasks` forbids overlapping `owned_files` across WPs, so the two code WPs were merged into one (`WP01-torn-read-escalation`), recorded in `tasks.md`. Inside that single WP, the red-first discipline is preserved as **separate, ordered commits** rather than collapsed into one diff: red regression test (`a20797b6da`) → tidy-first `_serialize_owner` extraction (`96eb2a01b2`) → `TornReadError` (`44845a1260`) → `build_serialized` + owner swaps + `incomplete()` codes (`cf6abb2306`) → `StartupAssetError` (`250adb2afe`) → primitive tests (`8cee323e66`) → flip regression→functional + terminal/source-drift CLI tests (`469db75571`) → CLI-hook test isolation (`5f4fa69ac1`). This keeps ADR `2026-07-17-1`'s red→green provability intact even though it is one WP, not two. The planned WP03 (closeout) survives unmerged as WP02 (this WP) because it owns disjoint files (`docs/changelog/CHANGELOG.md`, the mission's own evidence/tracer files) with no overlap against WP01's `src`/`tests` set.
- **DD-7 (review remediation, cycle 1).** The reviewer's cycle-1 rejection (`f196a3237d`) asked for: a US3.3 test; two inventory observations before the first lock plus a sentinel-first assertion (turning a mutation probe with an extra unlocked retry RED, `4 == 2`); concrete C-008 lock-path lists for both the cold and warm cases (replacing a looser existing-elements assertion); a concrete T007.2 list; a T007.13 skills-path test asserting the escalation actually fires; and removal of all 8 suppressions the first pass had accumulated. All were folded as blocking items 1–6 in the remediation commits (`81542ec482`, `38b90b7597`, `8a3f2f7fee`, `6b005a1c71`), with three non-blocking folds (INFO line asserted on the owner logger; the hint text keyed off the error code; stderr empty under `--json`). This is a design-decision entry, not just an activity note, because "concrete list" vs "existing elements" is a reusable assertion-strength pattern for any future lock-set identity test in this codebase.
