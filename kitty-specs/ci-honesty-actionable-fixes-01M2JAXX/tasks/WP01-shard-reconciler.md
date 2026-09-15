---
work_package_id: WP01
title: '#4360-B: diff-scoped shard reconciler (selected-shard completeness)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
planning_base_branch: fix/ci-honesty-actionable-fixes
merge_target_branch: fix/ci-honesty-actionable-fixes
branch_strategy: Planning artifacts for this mission were generated on fix/ci-honesty-actionable-fixes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-honesty-actionable-fixes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-honesty-actionable-fixes-01M2JAXX
base_commit: 2ee3919bcb2b1425cf7906c7ec055ea9f4a15fed
created_at: '2026-09-15T12:05:15.419128+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - CI honesty fixes
history:
- at: '2026-09-15T11:45:58Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- scripts/ci/reconcile_shards.py
- tests/ci/test_reconcile_shards.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-aggregate.yml
- scripts/ci/reconcile_shards.py
- tests/ci/test_reconcile_shards.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – #4360-B diff-scoped shard reconciler

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

Fix the live #4360-B false-red: a diff-scoped PR whose *selected* shards all pass must be reported
**complete**, while a *selected* shard that is genuinely absent must still be **fatal** (no
false-green). Done when:

- `tests/ci/test_reconcile_shards.py` pins contracts C-recon-1..4 and is RED on base `36d866d4fa`,
  GREEN on the fix commit.
- The inline reconciler is extracted to `scripts/ci/reconcile_shards.py` and imported by
  `.github/workflows/ci-aggregate.yml`.
- The aggregate fail-closed guard (`ci-aggregate.yml:376-381`) still fires on a non-empty `missing`.
- `ruff check`, `ruff format --check`, `mypy --strict` clean; new-code coverage ≥ 90% (NFR-002/003).

## Context & Constraints

- Design + evidence: `kitty-specs/ci-honesty-actionable-fixes-01M2JAXX/research.md` (Decision 1),
  `contracts/helper-contracts.md` (reconcile contract), `work/ci-honesty-4437/lenses/B-fanout-cluster.md` §6.
- Live repro: PR #4448 head `95d76daf`, aggregate run `34950420326` — 1/1 fresh selected shard, all
  component workflows green, yet "36 registry-expected shards missing".
- Current mechanism: `ci-aggregate.yml:293-294,336` set `expected` = all 37 registry shards
  unconditionally; `:340-356` makes an unselected absent shard fatal; `:375-382` "N registry-expected
  shards missing". `read_selected_modules` (`:297-320`), `selected` (`:324`), `must_be_fresh` (`:347`)
  already exist — extend them.
- **INVARIANT (NFR-001, C-003)**: completeness gates ONLY diff-cover, which scores only changed
  lines (always in selected modules); unselected coverage is irrelevant to the verdict. **Preserve
  `must_be_fresh`** — a SELECTED shard must be fresh in the CURRENT run; a backfill artifact does not
  satisfy it. Do NOT soften the fail-closed guard.
- **OUT OF SCOPE (C-001)**: do NOT touch the main-ledger stale-fallback source query (#4360-A,
  `ci-aggregate.yml:187-199`), the workflow_run trigger fan-out, or `ci-router.yml`.

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`
- Execution worktree is allocated per computed lane from `lanes.json`; implement in that lane.

## Subtasks & Detailed Guidance

### Subtask T001 – RED: pin reconciler contracts (commit FIRST)
- **Purpose**: Fail-first ATDD pin of the user-observable behaviour before any implementation.
- **Steps**: Create `tests/ci/test_reconcile_shards.py` asserting contracts C-recon-1..4 from
  `contracts/helper-contracts.md`: (1) `selected={"M"}`, current has M, previous empty → `complete=True, missing==[]`;
  (2) `selected={"M"}`, M absent from current (even if in previous) → M ∈ `missing`, `complete=False`;
  (3) `selected=None` → legacy all-registry behaviour; (4) unselected absent module → not in `missing`.
- **Files**: `tests/ci/test_reconcile_shards.py` (new).
- **Notes**: MUST be red on `36d866d4fa` (module doesn't exist yet / all-37 semantics). Commit as the
  first commit of the lane (ATDD-first, C-011).

### Subtask T002 – Extract reconciler (behaviour-preserving)
- **Purpose**: Move the inline Python reconciler out of YAML so it is unit-testable (the reason it
  shipped untested).
- **Steps**: Extract `ci-aggregate.yml:236-383` into `scripts/ci/reconcile_shards.py` with a
  `reconcile(registry_shards, selected, current_fresh, previous_available) -> CompletenessResult`
  signature (see contract). Keep behaviour identical in this commit (all-registry), so T001's legacy
  case (C-recon-3) passes and the current-behaviour cases stay red.
- **Files**: `scripts/ci/reconcile_shards.py` (new), `.github/workflows/ci-aggregate.yml`.
- **Notes**: Declare `__all__`; type-annotate for `mypy --strict`.

### Subtask T003 – Invert completeness (the fix)
- **Purpose**: Require only selected shards fresh; unselected backfill-if-available, never fatal.
- **Steps**: Change `expected` from the full registry to the selected set (`selected is None` ⇒ full).
  A required (selected, or all when full) shard absent from current AND fallback ⇒ `missing`. An
  unselected shard: backfill from `previous_available` if present, else ignore. Keep `must_be_fresh`
  so a selected shard needs a CURRENT-run artifact.
- **Files**: `scripts/ci/reconcile_shards.py`.
- **Notes**: This is the commit that turns C-recon-1 and C-recon-4 green while C-recon-2 stays fatal.

### Subtask T004 – Wire the aggregate step
- **Purpose**: Aggregate calls the extracted reconciler; guard preserved.
- **Steps**: Replace the inline block in `ci-aggregate.yml` with an import + call to `reconcile(...)`;
  the existing fail-closed guard (`:376-381`) fires on non-empty `missing`. Verify no other aggregate
  step (diff-cover `:412-439`) is disturbed; confirm `#4334 sonar-pr` consumes the selected-only set
  (it is `continue-on-error`, informational).
- **Files**: `.github/workflows/ci-aggregate.yml`.

### Subtask T005 – Verify red→green
- **Steps**: `pytest tests/ci/test_reconcile_shards.py -q` (green on fix, was red on base);
  `pytest tests/ci/ tests/architectural/ -q` (blast radius); `ruff check . && uv run --frozen ruff format --check . && mypy --strict scripts/ci/reconcile_shards.py`.
- **Notes**: Record the red-on-base / green-on-fix evidence in the Activity Log for the reviewer.

## Test Strategy

Mandatory. `tests/ci/test_reconcile_shards.py` is the RED-first contract pin. Also run
`tests/architectural/` (workflow-lint) and `tests/ci/` as the blast radius. Prove red on
`36d866d4fa`, green on the fix.

## Risks & Mitigations

- **False-green (the big risk)**: relaxing selected-shard freshness. Mitigation: C-recon-2 pins that a
  selected absent shard stays fatal; `must_be_fresh` preserved.
- **Disturbing diff-cover / sonar-pr consumers**: verify `:412-439` untouched; sonar-pr is informational.

## Review Guidance

- Confirm the RED-first test was red on `36d866d4fa` and green on the final commit.
- Confirm `must_be_fresh` preserved and the fail-closed guard NOT softened (NFR-001).
- Confirm no edits to #4360-A source query / fan-out / ci-router.yml (C-001).

## Activity Log

- 2026-09-15T11:45:58Z – system – Prompt created.
