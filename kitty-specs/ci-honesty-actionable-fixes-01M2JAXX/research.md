# Research: CI Pipeline Honesty — Actionable Fixes

Phase 0 consolidation. Every decision below is settled by the 4-lens adversarial research squad
staged in `work/ci-honesty-4437/` (`SYNTHESIS.md`, `lenses/A-gate-classification.md`,
`lenses/B-fanout-cluster.md` §6, `lenses/C-verdict-and-nightly.md`, `lenses/D-out-of-matrix.md`).
Citations are `file:line` at base commit `36d866d4fa` or issue#.

## Decision 1 — #4360-B: selected-shard completeness (extract reconciler)

- **Decision**: Extract the inline shard reconciler (`ci-aggregate.yml:236-383`) to
  `scripts/ci/reconcile_shards.py`; change completeness from "all registry shards (37) resolvable"
  to "all SELECTED shards fresh; UNSELECTED shards backfill-if-available, never fatal when absent".
- **Rationale**: The live repro (PR #4448, run `34950420326`) fails on the PR's own green head with
  1/1 fresh selected shard because `expected` = full registry (`ci-aggregate.yml:293-294,336`) and an
  unselected absent shard is fatal (`:340-356,375-382`). It is provably separable from the fan-out
  cluster (none of those lines read trigger source/branch/main ledger — Lens B §6). Safe against
  false-green because completeness gates ONLY diff-cover (`:412-439`), which scores only changed
  lines, which live in selected modules.
- **Alternatives considered**: (a) soften the fail-closed guard `:376-381` — REJECTED, reintroduces
  false-green and is the coupled #4360-A path. (b) fix in inline YAML without extraction — REJECTED,
  leaves the logic untestable (the reason it shipped broken).
- **Guard preserved**: `must_be_fresh` (`:347`) — a SELECTED absent shard stays fatal (NFR-001).

## Decision 2 — #4454: tests-only routing via the two-authority router (Option 1)

- **Decision**: Add `tests/<module>/**` (and `tests/ci/**`) globs to the hand-authored router filter
  groups in `.github/workflows/ci-router.yml`, mirroring each `tests/` tree into the SAME groups the
  corresponding `src/**` change already hits.
- **Rationale**: `select_modules` (`gate_selection.py:213`) intersects matched router groups with the
  registry module inventory; no group carries a `tests/<module>/**` glob, so a tests-only diff selects
  `[]` (live repro: `select_modules(['tests/status/test_store.py']) -> []`). Option 1 stays within the
  two-authority contract — the parser picks up the new globs, no code change to `select_modules`.
- **Alternatives considered**: Option 2 (derive a test-dir→module map inside `select_modules`) —
  REJECTED as the default, risks a second map (#2476 hazard) unless derived from registry; Option 1
  is the issue-author's recommendation and the single-authority move.
- **Guard**: mirror into the identical group set (not one "owning" module) and watch
  `test_no_duplicate_suite_execution` so `tests/docs`/`tests/e2e` don't double-route.

## Decision 3 — #4208: timed_out-aware router-gate classifier (Shape 1)

- **Decision**: Extract a `timed_out`-aware classification helper into `scripts/ci/router_gate.py`
  (reusing the jobs-API conclusion vocabulary already in `fleet_verdict.py:89`); the router-gate step
  populates conclusions from the Actions jobs API and reports `timed_out` distinctly. **Blocking
  policy unchanged.**
- **Rationale**: `ci-router.yml:568-572` folds `cancelled` into the blocking set with `failure`, and a
  `timeout-minutes` kill collapses to `cancelled` in the `needs` context (which cannot carry
  `timed_out`). The distinguishing signal is the jobs-API `conclusion` — API-only, already consumed by
  `fleet_verdict.py:89`.
- **Alternatives considered**: Shape 2 (per-job kill-time annotations) and Shape 3 (ceiling-proximity
  telemetry) — DEFERRED (issue names Shape 1 as the minimal sanctioned fix). Inline-heredoc-only fix —
  REJECTED (the `needs`-only test harness cannot model `timed_out`; extraction is required for a real
  RED-first pin).
- **Guard**: pass/fail blocking decision byte-identical to baseline for `{failure, cancelled}` inputs
  (NFR-001).

## Decision 4 — #4212: nightly fail-loud (capture exit codes)

- **Decision**: In `ci-nightly.yml`, capture each suite's exit code (perf `:92-98`, e2e `:100-106`,
  interpreter `:149-155`) into `$GITHUB_ENV`, keep the annotations, and add a terminal `if: always()`
  step (per job) that `exit 1`s if any captured code is non-zero.
- **Rationale**: `set +e` + trailing `echo "…exit=$?"` discards pytest's exit into a `::notice::`
  string → step exits 0; `nightly-summary` (`:256-267`) only echoes results. The run-all intent
  (`:16-24`) is legitimate; the bug is collect-all-then-never-fail.
- **Alternatives considered**: drop `set +e` — REJECTED (would abort later suites, losing the
  collect-all output the header requires).
- **Guard**: keep `if: always()` / `fail-fast: false` so every suite still runs
  (`test_performance_marker_guard.py:254-255` already requires these).

## Supply-Chain Security (051)

**N/A** — this mission adds/upgrades/removes **no dependency** in any ecosystem. Both new modules
(`reconcile_shards.py`, `router_gate.py`) use only the Python stdlib and existing repo tooling. No
registry-authenticity / lifecycle-script / freshness decision arises.

## Adversarial Evidence

The 4-lens squad IS the adversarial pass for this mission's design. Contested findings and their
disposition:

- "#4360 must ride the cluster ADR" (Lens B initial) → **changed**: §6 re-analysis proved #4360-B
  separable from #4347/#4371/#4360-A; only #4360-A stays coupled. Accepted into scope as #4360-B.
- "Just require N-not-37 / soften the guard" (naive reading of the live repro) → **rejected**: would
  false-green; the fix is completeness-scoping with `must_be_fresh` preserved.
- "#4454 Option 2 (derived map)" → **deferred**: Option 1 chosen; Option 2 recorded as the fallback
  if the two-authority globs prove insufficient.

No contested finding silently dropped (`contracts/adversarial-evidence-contract.md`).
