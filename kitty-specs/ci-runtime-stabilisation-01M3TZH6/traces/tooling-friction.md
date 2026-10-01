# Tooling friction — ci-runtime-stabilisation-01M3TZH6

Seeded at specify (2026-10-01). Append friction as it happens: command, symptom, workaround, follow-up.

## Context
The mission edits CI workflows (`ci-router.yml`, `ci-modules.yml`, `module-tests.yml`, `packs.yml`, `ci-nightly.yml`), `scripts/ci/gate_selection.py`, `.github/ci-module-registry.yml`, shard timings and `tests/architectural/` gate files. Its own workflow edits cannot be exercised by local runs; validation depends on PR CI and a full-mode router run.

## Log
- 2026-10-01 — `mission create` on a non-primary topic branch resolved topology `coord` (CLAUDE.md suggests `lanes` is the non-primary default). Proceeding with coord; watch for coordination-worktree materialisation and status-byte merge gotchas.
- 2026-10-01 — Decision-ledger split (known #5519, related #5023): the four specify-time Decision Moments (DMs 01M3TZHM…, 01M3TZHQ…, 01M3TZHT…, 01M3TZHX…) were written to the PRIMARY `decisions/` + `status.events.jsonl` while the coord worktree was empty; later DMs landed on coord. Left the primary residue uncommitted (CLI classifies it as coordination residue); did NOT run `doctor decisions --repair` (it drops the earlier decisions per #5519).
- 2026-10-01 — `spec-commit` routed the seeded tracer files to the coordination branch and left identical untracked copies on primary; removed the primary copies after a byte-diff.
- 2026-10-01 — `finalize-tasks --validate-only` rejected WP02 owning a file that WP01 creates (literal-path zero-match) until WP02 also declared it in `create_intent`.
- 2026-10-01 — Pre-existing red on main: `test_pinning_inventory_fresh.py` (#5523, inventory stale after #3143); folded by WP06's regeneration.
- 2026-10-01 — Issue-matrix approval gate scans spec/plan/research/tasks/contracts for every `#NNNN`: 22 context citations had no row → pre-recorded 42 verdicts before the first approval.
