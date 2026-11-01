# Change 3 research: GitHub merge queue

Op `01M6B0W9FBEM0YFWSWXYFVC477`. Read against `origin/main` at `bf8d27ce`. Items marked
(inference) are not verified against a live queue run.

## Required checks and their workflows

| Check | Workflow | Job |
|---|---|---|
| `router gate` | `ci-router.yml` | `router-gate` (1465) |
| `CI Modules gate` | `ci-modules.yml` | `modules-gate` (419) |
| `Clean install verification` | `ci-quality.yml` | `clean-install-verification` (63) |

Only these three workflows need `merge_group:`. `packs`, `ci-windows`, `contracts`, `release-readiness`,
`check-spec-kitty-events-alignment` and `mission-status-api` are not required. `merge_group` takes no
`paths` filter (inference), so adding it to the path-filtered ones would run them on every group, and
`tests/release/test_release_ci_ownership.py:136`, `test_contracts_workflows.py:192` and
`test_mission_status_api_build.py` pin their exact triggers.

## Pull-request-only expressions under `merge_group`

- **Label guards** (`pr:pause-ci`, `pr:skip-ci`, `pr:deferred`): the label list is absent, so the jobs
  run and the gates' refusal steps stay off. A paused PR cannot enter the queue because its required
  checks are red. No fix.
- **Diff base, must fix.** `ci-modules.yml` changed-files (188-198) has no `merge_group` case: `base`
  is empty, the step fails and the build step (291-293) forces full module selection on every queue run.
  `ci-router.yml` prose-scan (708-716) loses the prose-only downroute the same way (safe, but costly).
  Fix: `MERGE_GROUP_BASE: ${{ github.event.merge_group.base_sha }}` and a `merge_group)` case, mirroring the
  existing `push)` case. `github.sha` is the group head.
- **Path router.** `scripts/ci/gate_selection.py` is pure (paths in, gates out). `dorny/paths-filter`
  v4.0.3 already handles `merge_group` (base `merge_group.base_sha`). No change.
- **Skip-if-green** steps are `pull_request`-only. No change.
- **Concurrency** keys on `github.ref`; each `gh-readonly-queue/main/pr-N-<sha>` ref is unique. No change.

## Downstream workflow_run consumers

- **`ci-aggregate.yml`** (`workflow_run` on CI Modules): `aggregate_source.py:84-88` raises
  "unsupported source event" for anything but `pull_request`, `push` and `workflow_dispatch`, so a queue
  run would post a red (non-required) `CI Aggregate gate`. Diff-cover already ran on the PR. Skip
  `merge_group` sources there.
- **`ci-fleet-verdict.yml:24`** keys concurrency on `workflow_run.head_sha` with cancel-in-progress. With a
  rebase queue `main` is fast-forwarded to the group's head (inference), so a late queue completion can
  cancel the push run's verdict for the same commit. Add the source event to the key.

## Tests that parse workflow triggers

`_gate_coverage.py` models push-to-main only and understands a `merge_group` `event_name` atom;
`test_fork_guard.py`, `test_ci_module_wiring.py` (exact `if:` pins: do not change the fork guard),
`test_pause_ci_label.py`, `test_battery_partition_proof.py` and `test_module_shard_registry.py` are
unaffected if the `if:` texts stay. `tests/ci/test_skip_if_green_wiring.py:175`
(`NON_PULL_REQUEST_EVENTS`) should gain `merge_group`. New pins: the `merge_group` diff case in
ci-modules and ci-router.

## Settings (recommendation, inference)

Rebase merge; only merge non-failing PRs; build concurrency 3; group size min 1 / max 3; wait 5 min;
status-check timeout 90 min. A push to a queued PR evicts it and rebuilds later groups, so the external
fleet must stop re-pushing queued PRs.

## Docs to update

ADR `docs/adr/3.x/2026-09-23-1-auto-merge-required-checks-gate.md` (amend), `pr-landing.md`
(`gh pr merge --rebase --auto`, pausing CI), `unclog-ci.md`, `docs/development/reference/ci-gate-mechanics.md`.
