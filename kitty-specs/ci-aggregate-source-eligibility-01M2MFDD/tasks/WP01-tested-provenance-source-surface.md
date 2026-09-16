---
work_package_id: WP01
title: Tested provenance source-eligibility surface + workflow wiring
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-001
- NFR-003
- NFR-004
planning_base_branch: fix/ci-aggregate-source-eligibility
merge_target_branch: fix/ci-aggregate-source-eligibility
branch_strategy: Planning artifacts for this mission were generated on fix/ci-aggregate-source-eligibility. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-aggregate-source-eligibility unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-aggregate-source-eligibility-01M2MFDD
base_commit: dbfd5bfff1914d7dcfcbd5e5953d6bdd5ea5d60b
created_at: '2026-09-16T07:19:00.987741+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-09-16T07:11:32Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/source_eligibility.py
- tests/ci/test_source_eligibility.py
execution_mode: code_change
owned_files:
- scripts/ci/source_eligibility.py
- tests/ci/test_source_eligibility.py
- .github/workflows/ci-aggregate.yml
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ci-aggregate-source-eligibility-01M2MFDD --json`). Apply the resolved initialization, boundaries, directives, and tactics, then state which you applied. Force `PYTHONPATH=$(pwd)/src` for every pytest/validation call (global spec-kitty resolves a sibling checkout — memory).

## Objective

Replace the untested, provenance-blind inline-shell source-selection logic in `.github/workflows/ci-aggregate.yml` (the `last-success` step) with a **pure, red-first-tested** Python surface `scripts/ci/source_eligibility.py`, wired into the workflow and proven by an execution-grounded guard. This is the ADR's named "one genuine pytest red-first entry point."

Read first: `../spec.md`, `../research.md` (esp. D-02 cosmetic verdict, D-04 rule, D-05 tests), `../data-model.md` (the `SourceDecision` variants + INV-A..F), `../contracts/source-eligibility.contract.md`. Template to mirror: `scripts/ci/select_source_artifacts.py` (pure decision, `gh` at the edge, `key=value` to `GITHUB_OUTPUT`, named `ValueError`s). Wiring-guard template: `tests/ci/test_aggregate_source.py:146-153` and `:309-327`.

## ⚠️ Frozen boundaries (do NOT modify — byte-unchanged; pinned by T005)

- The fail-closed guard step in `ci-aggregate.yml` — "Fail loudly if the reconciled shard set is incomplete" (currently ~lines 292-299; re-verify, it moves). Do not touch its `run:` text.
- `scripts/ci/reconcile_shards.py` `must_be_fresh` and the whole reconciler — not in `owned_files`; do not edit.
- `.github/workflows/ci-router.yml` (#4347) and `ci-fleet-verdict.yml` (#4371) — Stage-1, out of scope.
- The PR's own diff-cover path and `collect.if` job flow — untouched (the PR's red is correct; we do not relabel or suppress it).

## Subtasks

### T001 — Red-first unit tests for the eligibility decision (write FIRST, watch them fail)
Create `tests/ci/test_source_eligibility.py`. Import `resolve_source` (to be written in T002). Cover all named branches of `SourceDecision`, **asserting the rejections, not a happy string** (reviewer's anti-laziness rule):
- `pr-head-trigger`: `event=pull_request` → `NotAMainSource`, `run-id=""`, `eligibility=pr-head-trigger`, even when a successful main candidate exists (assert it is NOT resolved).
- `failed-trigger`: `event=push, conclusion=failure` → `NotAMainSource` (`failed-trigger`), no run-id.
- `dispatch-no-fallback`: `event=workflow_dispatch` → `NoFallback`, no ledger consulted.
- `eligible push-main`: `event=push, head_branch=main, conclusion=success` + a `success` main candidate → `EligibleSource(run_id)`.
- `eligible source-branch`: eligible provenance + a `success` candidate on the source branch → `EligibleSource`.
- `no-success-source`: eligible provenance, candidates all non-success → `NoEligibleSource` (`no-success-source`), `run-id=""`.
- `unrelated-branch rejected`: a `success` candidate only on a branch ∉ {source, default} → not resolved (INV-B).
- `red source-branch run rejected`: a `conclusion!=success` candidate on the source branch → not resolved (INV-A).
- Malformed input (missing field / non-int databaseId) → raises `ValueError` (only case that raises).
Run: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/test_source_eligibility.py -q` → expect failures (module absent). That red is the point.

### T002 — Implement the pure decision `resolve_source(...)`
In `scripts/ci/source_eligibility.py`, implement `resolve_source(trigger, candidates, default_branch) -> SourceDecision` per `contracts/` + `data-model.md`. Order: dispatch → `NoFallback`; `event=pull_request` or `conclusion=failure` → `NotAMainSource`; else most-recent `conclusion=success` candidate with `headBranch==trigger.head_branch`, else `==default_branch` → `EligibleSource`; none → `NoEligibleSource`. Pure — no I/O, no subprocess, no clock. Uphold INV-A (success-only), INV-B (branch-scope), INV-C (every variant → named slug). Raise `ValueError` only on malformed input.

### T003 — Implement the edge `main()`
Arg-parse injected JSON (mirror `select_source_artifacts.py`'s file-argument style — e.g. `--trigger <path>` + candidate run-list path/stdin); the `gh run list --json databaseId,conclusion,headBranch,event ...` call stays in the workflow, NOT the module. Emit exactly two keys to stdout/`$GITHUB_OUTPUT`: `run-id=<id|"">` and `eligibility=<slug>`. Never emit `complete`/`missing`/`coverage` (C-003 / INV-D). Exit 0 for every `SourceDecision` variant incl. empty ones; non-zero only on malformed input (INV-E — reconcile stays the fail-closed terminus).

### T004 — Wire the `last-success` step to call the helper
In `ci-aggregate.yml`, rewrite the `last-success` step's `run:` block: replace the inline `gh run list ... || true` decision with `gh run list --json databaseId,conclusion,headBranch,event ... | python3 scripts/ci/source_eligibility.py ...` (pass the trigger JSON via env, e.g. `TRIGGER_JSON: ${{ toJSON(github.event.workflow_run) }}`). Keep emitting `run-id` to `$GITHUB_OUTPUT` under the SAME output name (`steps.last-success.outputs.run-id`) so `download-previous` (`if: ...run-id != ''`) and `reconcile` are unchanged. Preserve the `if: github.event_name != 'workflow_dispatch'` gate.

### T005 — Non-fakeable wiring guard + guard-byte-unchanged pin (in the same test file)
Add to `tests/ci/test_source_eligibility.py` (mirror `test_aggregate_source.py:146-153,309-327`): (a) load `ci-aggregate.yml`, select the `last-success` step, assert its `run:` invokes `scripts/ci/source_eligibility.py` and that no inline `gh run list` decision remains; (b) EXECUTE the extracted `run:` block against a stubbed `gh` returning a no-eligible-source inventory, assert stdout has `run-id=` (empty) + a named `eligibility` slug; (c) assert the fail-closed guard step's `run:` text is byte-identical to a pinned copy (fetch the current text and pin it — this is INV-6/C-001).

### T006 — Local gates green (record commands + counts)
Run and record: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/test_source_eligibility.py -q`; `uv run --frozen ruff check .`; `uv run --frozen ruff format --check .` (SEPARATE gate); `uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q`; download the `actionlint` release binary and run it on `.github/workflows/ci-aggregate.yml`, paste RAW output (do NOT self-report "0"). Also run the wider CI-script blast radius: `PYTHONPATH=$(pwd)/src uv run --frozen python -m pytest tests/ci/ -q`.

## Branch Strategy

Planning/base branch: `fix/ci-aggregate-source-eligibility`. Final merge target: `fix/ci-aggregate-source-eligibility` (consolidated to local `main`, then a PR to `upstream/main`; the operator merges). Execution worktrees are allocated per computed lane from `lanes.json` — enter the resolved workspace via `spec-kitty implement WP01`; do not reconstruct the path.

## Definition of Done (non-fakeable)

- `resolve_source` covers all 6 named branches + the two rejection cases + malformed→raise, all red-first then green. No live API call in any test (NFR-003).
- The wiring guard EXECUTES the real extracted `last-success` step (not a grep) and asserts `run-id=""` + named slug on a stubbed no-source inventory; the guard step's `run:` is pinned byte-identical (C-001).
- The helper writes only `run-id` + `eligibility` (never completeness — C-003); exits 0 on every decision variant, non-zero only on malformed input (NFR-004).
- `ruff check` AND `ruff format --check` clean; terminology guard green; `actionlint` raw output pasted (clean); `tests/ci/` green.
- Frozen boundaries untouched (guard, reconciler, ci-router, ci-fleet-verdict, PR diff-cover path).

## Risks / reviewer guidance

- **Green-path leak (highest):** confirm no change relaxes `--status success` (LEAK-A) or widens the eligible branch set beyond `{source ∪ default}` (LEAK-B); confirm the helper never writes `complete`/`missing`/`coverage` (LEAK-C/D). Reviewer: check the `NotAMainSource`/`NoEligibleSource` paths cannot ever return a run-id.
- **Fakeable test:** reject any unit test that asserts a named-error string for a trivial no-input case without exercising success+branch REJECTIONS; reject a grep-only wiring guard.
- **Hard-exit regression:** the helper must NOT hard-exit on no-source (would make the reconcile guard's shard-list message unreachable — NFR-004).
- `toJSON(github.event.workflow_run)` is `null` on `workflow_dispatch`; ensure the dispatch path is handled before any JSON parse assumes fields.
