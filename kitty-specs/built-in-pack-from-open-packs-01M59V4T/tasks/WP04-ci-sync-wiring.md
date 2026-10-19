---
work_package_id: WP04
title: 'CI: sync packs before tests, pin gate, regen/DRG against fetched trees'
dependencies:
- WP03
requirement_refs:
- FR-006
- FR-012
- NFR-004
planning_base_branch: feat/6451-built-in-from-open-packs
merge_target_branch: feat/6451-built-in-from-open-packs
branch_strategy: Planning artifacts for this mission were generated on feat/6451-built-in-from-open-packs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/6451-built-in-from-open-packs unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-built-in-pack-from-open-packs-01M59V4T
base_commit: e677bb23a152c3aa09866d71d0eb5ef236b1ede3
created_at: '2026-10-19T12:57:17.304169+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T046
history:
- timestamp: '2026-10-19T11:36:32Z'
  agent: planner-priti
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/actions/warmup/action.yml
create_intent:
- tests/ci/test_workflows_sync_packs.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/actions/warmup/action.yml
- .github/workflows/packs.yml
- .github/workflows/ci-windows.yml
- .github/workflows/ci-nightly.yml
- .github/workflows/ci-aggregate.yml
- .github/workflows/release.yml
- .github/workflows/ci-shard-recapture.yml
- .github/workflows/mission-status-api.yml
- .github/workflows/contracts.yml
- .github/workflows/ci-router.yml
- .github/workflows/ci-modules.yml
- .github/workflows/module-tests.yml
- .github/workflows/release-readiness.yml
- .github/workflows/contracts-release.yml
- tests/ci/test_workflows_sync_packs.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP04 – CI: sync packs before tests, pin gate, regen/DRG against fetched trees

## ⚡ Do This First: Load Agent Profile

Run `/spk-charter-profile-load python-pedro` and read `.kittify/charter/charter.md` before touching code. Load action context with `spec-kitty charter context --action implement`.

## Objective

Every CI job that reads a pack syncs it first, a pin gate fails when a pin is unresolvable or its digest does not match, and the regeneration and DRG `--check` gates run against the fetched tree.

Requirements: FR-006, FR-012, NFR-004 (folds #6166).

## Context

- `module-tests.yml:139` uses `./.github/actions/warmup` (the shared install step for the module matrix); add the sync there once.
- `packs.yml` jobs at ~L196-270 run `uv sync` then regen `--check`, DRG `regenerate-graph --check`, `vendor --check` (pin drift gate, L245-251) and the manifest freshness guard. Insert `python scripts/sync_packs.py --pack all` after `uv sync`, and replace the `vendor --check` job with `python scripts/sync_packs.py --check` after a sync (name it `pin gate`).
- `ci-windows.yml:92-102` installs via pipx; add a sync step with the host python before tests (NFR-004).
- `ci-nightly.yml` has many `uv sync` steps (L131…L1480); `ci-aggregate.yml:368`; `release.yml:128`; `ci-shard-recapture.yml:177,258`. Add the sync after each `uv sync` that precedes pytest or a build. `contracts.yml` and `mission-status-api.yml` use `--no-install-project`; check whether their tests read packs, and only add the step where they do.
- Cache: use `actions/cache` keyed on `hashFiles('packs/*.source.yaml')` for `~/.cache/spec-kitty/open-packs` to keep cold syncs off the hot path (NFR-001/002). Pin the action by SHA like the rest of the repo (DIR-051).
- open-packs must be readable from CI. WP01 changes the built-in pin repository to `https://github.com/spec-kitty/spec-kitty-open-packs.git`; confirm it clones without credentials in CI.
- Pack-manifest regen and DRG `--check` gates run against the FETCHED trees (sync precedes them). `ci-router.yml` path filters currently key on `packs/built-in/missions/**`; rewrite them to also key on `packs/*.source.yaml` (folds #6166 FOLD-POST).

Dependencies: Depends on WP03.

## Subtasks

### T016: Red guard test

- **Purpose**: Red guard test.
- **Steps**: `tests/ci/test_workflows_sync_packs.py`: parse each workflow YAML; for every job that runs `pytest`, `uv build` or a `charter pack` command, assert a `sync_packs.py` step appears before it (or the job uses the warmup action).
- **Edge cases / notes**: Allowlist jobs that genuinely read no pack, with a reason string.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T017: Warmup action + module matrix

- **Purpose**: Warmup action + module matrix.
- **Steps**: Add the cache restore and `python scripts/sync_packs.py --pack all` to `.github/actions/warmup/action.yml`.
- **Edge cases / notes**: Must work on both Linux and Windows runners.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T018: packs.yml

- **Purpose**: packs.yml.
- **Steps**: Sync before regen/DRG/manifest jobs; replace the vendor drift gate with the pin gate `sync_packs.py --check` and update its `::error::` remedy text.
- **Edge cases / notes**: The drift-gate test file itself is retired in WP07.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T019: Remaining workflows

- **Purpose**: Remaining workflows.
- **Steps**: Windows, nightly, aggregate, release, shard-recapture; contracts / mission-status-api only if they read packs.
- **Edge cases / notes**: Release must sync before `uv build` (the hook in WP05 also verifies).
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T020: Cache step

- **Purpose**: Cache step.
- **Steps**: Add `actions/cache` for the open-packs cache keyed on the pin files.
- **Edge cases / notes**: SHA-pin the action.
- **Validation**: the tests named under Test strategy pass, file-scoped.

### T046: Router filters and remaining workflow files

- **Purpose**: Route pack-pin changes to the right lanes and sync in the rest of the workflows (B1).
- **Steps**: Rewrite `ci-router.yml` pack path filters (`packs/built-in/missions/**` -> also `packs/*.source.yaml`); add the sync step (or warmup action) to `ci-modules.yml`, `module-tests.yml`, `release-readiness.yml`, `contracts-release.yml` wherever pytest, `uv build` or `charter pack` runs.
- **Edge cases / notes**: The guard test (T016) must cover these files too.
- **Validation**: the tests named under Test strategy pass, file-scoped.

## Owned files

- `.github/actions/warmup/action.yml`
- `.github/workflows/packs.yml`
- `.github/workflows/ci-windows.yml`
- `.github/workflows/ci-nightly.yml`
- `.github/workflows/ci-aggregate.yml`
- `.github/workflows/release.yml`
- `.github/workflows/ci-shard-recapture.yml`
- `.github/workflows/mission-status-api.yml`
- `.github/workflows/contracts.yml`
- `.github/workflows/ci-router.yml`
- `.github/workflows/ci-modules.yml`
- `.github/workflows/module-tests.yml`
- `.github/workflows/release-readiness.yml`
- `.github/workflows/contracts-release.yml`
- `tests/ci/test_workflows_sync_packs.py`

Do not edit files outside this list. If you need to, stop and raise it with the orchestrator.

## Branch Strategy

Planning base and merge target: `feat/6451-built-in-from-open-packs`. Mission topology is `coord`; the lane for this WP is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`. Work in the workspace that `spec-kitty implement` resolves; never reconstruct the path.

## Test strategy

ATDD red-first: write or update the failing test, show it red, then implement. Run narrow, file-scoped pytest only (never a whole directory):

```bash
uv run --no-sync pytest tests/ci/test_workflows_sync_packs.py -q
```

Also run `ruff check` and `ruff format --check --force-exclude` on changed files, and `mypy` on changed source modules. Record commands and pass/fail counts in the WP notes.

## Definition of Done

- All subtasks done; tests above green; ruff, format and mypy clean with no new suppressions.
- Complexity ≤ 15 per function; repeated literals hoisted.
- Only owned files changed.
- A test parses every workflow job running pytest or `uv build` and asserts a sync step (or warmup action) precedes it; this covers `ci-router.yml`, `ci-modules.yml`, `module-tests.yml`, `release-readiness.yml` and `contracts-release.yml`.
- `ci-router.yml` pack path filters also key on `packs/*.source.yaml` (folds #6166 FOLD-POST).
- The PR links a green CI run where the Windows job and at least one `ci-modules` shard log the pin digest check.
- Pin URL is HTTPS (WP01); regen and DRG `--check` gates run against fetched trees.
- Requirements FR-006, FR-012, NFR-004 demonstrably covered by a test or gate.

## Risks

A missed job goes red only after cutover (WP09). The guard test catches that before the cutover lands.

## Reviewer guidance

Walk every workflow job that runs tests and confirm a sync precedes it; check the pin gate exits 1 on a stale tree. Reviewer profile: reviewer-renata.

## Implement command

```bash
spec-kitty agent action implement WP04 --agent claude --mission built-in-pack-from-open-packs-01M59V4T
```
