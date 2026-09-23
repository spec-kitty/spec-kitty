# Tracer: Approach — reconcile-flake-family-01M34HR7

Seeded at plan phase (2026-09-22). Append entries during implementation; assess at mission close.

## Plan phase

- Read the spec, the charter, `AGENTS.md`, `CONTRIBUTING.md`, and the actual code for all three
  surfaces (`fleet_verdict.py`, `fleet_main.py`, `reconcile_shards.py`) plus both CI workflow
  YAML files (`ci-aggregate.yml`, `ci-fleet-verdict.yml`) before drafting the plan, per
  `AGENTS.md`'s "never improvise" standing order.
- Grounded the FR-005 artefact-visibility polling design in the ACTUAL artifact-name convention
  already enforced by `scripts/ci/select_source_artifacts.py`'s `ARTIFACT` regex
  (`module-tests-{module}-shard-{n}-of-{count}-attempt-{attempt}-reports`), rather than inventing
  a parallel naming scheme — the new polling step reuses that regex and reuses
  `reconcile_shards.py`'s own exported `parse_registry`/`read_selected_modules` helpers
  (already in its `__all__`) to compute the must-be-fresh target set, instead of re-deriving
  shard expansion or selection logic a second time (single-canonical-authority governing
  principle).
- Verified the FR-008 shared-helper decision against the codebase's own existing precedent:
  `fleet_main.py` already imports five symbols directly from `fleet_verdict.py`
  (`AGGREGATE, PR_WORKFLOWS, GitHub, automatic_aggregate, classify, comment_body`) — so adding one
  more shared symbol for the retry primitive follows an established reuse path rather than
  introducing a new one.
- Verified gate facts first-hand rather than trusting the dispatch's summary at face value:
  confirmed `ruff check .` / `ruff format --check .` are hard-enforced (`ci-quality.yml:29-32`,
  no `continue-on-error`); confirmed `mypy` has zero references anywhere under
  `.github/workflows/`; confirmed `sonar-pr` in `ci-aggregate.yml` is `continue-on-error: true`
  and excluded from `aggregate-gate`'s `needs: [collect, diff-cover]`; confirmed
  `.github/ci-module-registry.yml`'s `ci` module row's `cov_targets` are `kernel` /
  `specify_cli.core`, not `scripts/ci`, so the diff-cover ≥90% floor structurally does not apply.
  Also found (not asserted by the dispatch, discovered independently): `ci-router.yml`'s
  `commit-msg` job is currently vacuous as written (`git log ... || true` — cannot fail), and no
  standalone Bandit/pip-audit CI *job* exists in `.github/workflows/`; both are dev dependencies
  and Bandit's ruleset is already folded into `ruff check .`'s `S` rule family. Recorded in
  plan.md's gate statement rather than silently assumed.

## Close-out (WP04, 2026-09-22)

**As-implemented shape, confirmed against the merged code rather than assumed from
plan.md:** WP01 (`scripts/ci/reconcile_retry.py`) provides one generic, stdlib-only bounded
retry primitive (`retry_with_backoff`); WP02 wires it into `fleet_verdict.py::report()` and
`fleet_main.py::report()` as a retry-then-skip-silently-and-defer strategy so a genuinely
racy snapshot disagreement gets a bounded second look before the fleet reporter defers
rather than publishing a stale verdict; WP03 adds a new `scripts/ci/wait_for_artifacts.py`
poller wired into a new step in `.github/workflows/ci-aggregate.yml`'s `collect` job, polling
only the SELECTED (must-be-fresh) shard set for late-arriving artifacts before
`reconcile_shards.py` runs; WP04 (this WP) is the integration/verification close-out —
confirming the three compose as a whole and appending the mission tracer files, carrying no
functional code of its own.

**T016 verification — exact commands and results:**

- `.venv/bin/python -m pytest tests/ci/ -q` → **412 passed, 0 failed** in ~44s. This matches
  the mission's own expected arithmetic exactly (baseline 392 on `main`, +4 WP01, +5 WP02, +1
  WP02 follow-on, +10 WP03 = 412) — no discrepancy to explain.
- SC-003 baseline scope, `.venv/bin/python -m pytest tests/ci/test_fleet_verdict.py
  tests/ci/test_fleet_main.py tests/ci/test_reconcile_shards.py -q` → **104 passed, 0
  failed** (at/above the recorded 98-passed baseline plus WP01–WP03's additions to these
  files).
- Combined new-surface suite, `.venv/bin/python -m pytest tests/ci/test_fleet_verdict.py
  tests/ci/test_fleet_main.py tests/ci/test_reconcile_shards.py tests/ci/test_reconcile_retry.py
  tests/ci/test_wait_for_artifacts.py -q` → **118 passed, 0 failed**, no cross-file
  interaction failures — the direct proof that WP01/WP02/WP03 compose when run together, not
  merely individually per-WP.
- `.venv/bin/python -m pytest tests/ci/test_aggregate_source.py -q` → **54 passed, 0
  failed**. `spec.md`'s SC-003 parenthetical describing 34 pre-existing failures here
  (`ModuleNotFoundError: coverage`) did NOT reproduce against this WP's synced `.venv` — see
  `tracer-tooling-friction.md`'s "Implement phase" item 7 for the full correction; this is a
  stale-venv false red, not a real pre-existing gap.
- SC-002 safety-invariant spot-check: `test_recovery_within_budget_publishes_stabilized_evidence_not_stale`
  and `test_attempt_change_during_publication_refuses_stale_verdict` in
  `test_fleet_verdict.py`/`test_fleet_main.py` prove "never publish from a stale/first
  snapshot when the two disagree" under retry; `test_composing_reconcile_shards_still_fails_closed_when_poller_exhausts`
  in `test_wait_for_artifacts.py` proves `reconcile_shards.py::main()` still fails closed
  when the poller's budget is exhausted. Both invariants present and convincing — no gap to
  record.
- `.venv/bin/ruff check .` → **All checks passed!** (whole repo).
- `.venv/bin/ruff format --check .` → **2202 files already formatted** (whole repo, zero
  reformats needed).
- `.venv/bin/ruff check --select TID251 .` → **All checks passed!** (import-linter gate,
  whole repo).
- `.github/workflows/ci-aggregate.yml` YAML parse (`python3 -c "import yaml;
  yaml.safe_load(open(...))"`) → parses cleanly with all three lanes' changes merged.
- Composition sanity check: `scripts/ci/fleet_verdict.py`, `scripts/ci/fleet_main.py`, and
  `scripts/ci/wait_for_artifacts.py` all import `retry_with_backoff` from the single
  `scripts/ci/reconcile_retry` module (`from scripts.ci.reconcile_retry import
  retry_with_backoff`, confirmed by direct grep across all four files) — nothing shadows or
  duplicates the primitive; WP02 and WP03 genuinely share it rather than merely coexisting.

**Pre-merge verification scope note — restated, per this WP prompt's own instruction to
state it explicitly rather than merely imply it:** this mission's own PR cannot exercise its
own fix through the real trigger path. `ci-fleet-verdict.yml` and `ci-aggregate.yml` both
fire on `workflow_run`, which always executes the copy of the workflow file — and every
script it references — that lives on the repository's default branch (`main`) at trigger
time, never the triggering PR's own branch copy (spec.md Decision 2 / C-001). A green PR for
this mission is therefore NOT evidence that the race is closed. The only pre-merge
verification available is the unit tests WP01/WP02/WP03 added, run directly against mocked
racy evidence sequences — exactly what the T016 re-run above confirms. Confirmation that the
real race is closed is a POST-MERGE observation (spec.md SC-004: 20 consecutive `main`-head
CI cycles or 5 calendar days, whichever comes first, zero same-SHA reconcile flaps across all
three job shapes) — explicitly NOT a condition this WP or this mission's PR must satisfy.
Confirmed by direct code/grep inspection: no rehearsal/replay path and no split-off
observability mission were added anywhere in WP01–WP03's diffs. (`fleet_verdict.py` does
contain pre-existing `replay`/`verify_replay_checkout` code — an operator-facing manual
`workflow_dispatch` replay feature that predates this mission and is unrelated to SC-004
verification; confirmed unchanged by diffing against `main`.) Both alternatives were
explicitly rejected in spec.md Decision 2 and neither crept in.

**PR-shape recommendation — revised from plan.md's estimate, not merely repeated.**
plan.md's PR Shape (§2a.6) estimated ~250–350 lines for one reviewable PR. The actual merged
diff across `scripts/ci/**`, `tests/ci/**`, and `.github/workflows/ci-aggregate.yml` is
**1,041 insertions / 74 deletions across 9 files** (433 insertions / 52 deletions in the
functional surfaces — `reconcile_retry.py`, `wait_for_artifacts.py`, `fleet_verdict.py`,
`fleet_main.py`, `ci-aggregate.yml` — plus 608 insertions / 22 deletions in tests). This is
roughly 3x plan.md's estimate. Per this WP's explicit instruction not to decide a split
unilaterally: **flagging this for the orchestrator/operator to decide.** WP04's own read is
that the diff, while larger than estimated, is still a single coherent change (one shared
primitive plus its three call sites plus tests) that does not have a natural seam to split
along without breaking the "prove WP01/WP02/WP03 compose" story this same PR needs to tell —
but that is a recommendation, not a decision made here.
