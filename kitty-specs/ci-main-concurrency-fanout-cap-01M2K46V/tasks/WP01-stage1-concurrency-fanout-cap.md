---
work_package_id: WP01
title: Stage-1 concurrency + fan-out cap (levers 1a + 2a)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/ci-main-concurrency-fanout-cap
merge_target_branch: fix/ci-main-concurrency-fanout-cap
branch_strategy: Planning artifacts for this mission were generated on fix/ci-main-concurrency-fanout-cap. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-main-concurrency-fanout-cap unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Stage 1 implementation
history:
- timestamp: '2026-09-15T18:45:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
mission_id: 01M2K46VR0PCTTFS5K0RTT4ZZR
owned_files:
- .github/workflows/ci-router.yml
- .github/workflows/ci-fleet-verdict.yml
- tests/architectural/test_dual_mode_contract.py
- tests/ci/test_fleet_verdict.py
role: implementer
tags: []
tracker_refs: []
wp_code: WP01
---

# Work Package Prompt: WP01 — Stage-1 concurrency + fan-out cap (levers 1a + 2a)

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile so your identity, boundaries, and directives are active:

```
/ad-hoc-profile-load implementer-ivan
```

Then run `spec-kitty charter context --action implement --json` and apply the resolved initialization, boundaries, directives, and tactics. State which you applied. You are the **implementer** for this WP.

## Objectives & Success Criteria

Land both coupled ADR levers (governing authority: ADR `2026-09-15-1`, PR #4534; ratified content at `work/ci-honesty-4437/DRAFT-ADR-ci-main-verdict-topology.md`) in one lane:

- **1a (#4347)** — per-SHA concurrency on push→main so no landed main tip cancels another (FR-001); PR/dispatch behavior unchanged (FR-002).
- **2a (#4371)** — `ci-fleet-verdict.yml`: trim `workflow_run` `types:` to `[completed]` (FR-004); add a **top-level per-SHA** `concurrency:` block that coalesces the fan-out to one surviving verdict per tip (FR-003); **leave `report-main` UNCHANGED** (the fan-out cap already drains its queue — FR-005; see Context).
- Golden-YAML pins are **exact-equality** (fakeable substring pins were rejected by the post-plan squad); a **non-tautological** dedup survivor test pins the coalesce-relies-on-this invariant (FR-006).
- Green path never widened: aggregate fail-closed guard untouched, `test_fleet_main.py` untouched (NFR-001); no dropped last-writer verdict (NFR-002); `actionlint`+`shellcheck` clean (NFR-003).

## Context & Constraints

Read before editing: `plan.md` (Implementation Approach + Test strategy + risk table), `research.md` (D1–D8 + the post-plan squad adjudication table), `contracts/ci-yaml-shape.md` (C-YAML-1..6 — the exact shapes), `contracts/verdict-invariants.md` (VI-1..6), `data-model.md` (CK-1, VS-1/2).

**Load-bearing constraints (do not violate):**
- **`report-main` stays exactly as-is** (`ci-fleet-verdict.yml:71-73`: `group: ci-fleet-verdict-main`, `cancel-in-progress: false`). Moving it to per-SHA opens an incident create-create race (research D4). `tests/ci/test_fleet_main.py:166` must stay green **untouched** — you do not own that file.
- **Every `cancel-in-progress: true` group keyed on main content must embed a per-SHA discriminator** (CK-1). Never collapse tips into a shared `cancel:true` group.
- **Do not touch** `ci-aggregate.yml`, `scripts/ci/reconcile_shards.py`, `scripts/ci/aggregate_source.py`, `scripts/ci/router_gate.py`, or `scripts/ci/fleet_main.py` (Stage 2/3 / consumed-not-modified). The dedup survivor guarantee in `fleet_verdict.py`/`fleet_main.py` is already correct — **pin it, do not change it** (research D5).
- **`/attempts/` is plural** in any jobs-API reference.
- Note PyYAML parses bare `on:` as boolean `True` — golden-YAML tests read `doc[True]` for the trigger block (existing pattern in `test_dual_mode_contract.py` / `test_fleet_verdict.py`).

## Subtasks & Detailed Guidance

### Subtask T001 — Lever 1a: `ci-router.yml` per-SHA main concurrency
- **Purpose**: each landed main tip gets its own terminal evaluation; a merge burst no longer cancel-cascades (FR-001), PR self-coalescing preserved (FR-002).
- **Edit** `.github/workflows/ci-router.yml:35-37` from:
  ```yaml
  concurrency:
    group: ci-router-${{ github.ref }}
    cancel-in-progress: true
  ```
  to exactly (C-YAML-1):
  ```yaml
  concurrency:
    group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}
    cancel-in-progress: ${{ github.event_name != 'push' }}
  ```
- **Why**: push→ `ci-router-<sha>` singleton, `cancel:false` (no sibling to cancel); pull_request→ `ci-router-<ref>`, `cancel:true` (unchanged self-coalesce); workflow_dispatch→ `ci-router-<ref>`, `cancel:true` (unchanged).
- **Validation**: `actionlint .github/workflows/ci-router.yml` clean; the T002 pin passes.

### Subtask T002 — Lever 1a exact-equality golden-YAML pin
- **Purpose**: prevent a silently-broken concurrency expression from re-enabling the cancel-cascade (a substring pin passes for `... || true`; Renata HIGH).
- **Add** a test in `tests/architectural/test_dual_mode_contract.py` mirroring its `_load_workflow` pattern, asserting **exact equality** (C-YAML-1):
  ```python
  wf = _load_workflow(CI_ROUTER)  # existing helper
  assert wf["concurrency"] == {
      "group": "ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}",
      "cancel-in-progress": "${{ github.event_name != 'push' }}",
  }
  ```
  (Confirm the exact helper/const names in the file; reuse them. Also keep any existing `on:`-block assertions passing — the `push.branches == ['main']`, pull_request, workflow_dispatch triggers are unchanged.)
- **Validation**: the new test is RED before T001, GREEN after.

### Subtask T003 — Lever 2a: `ci-fleet-verdict.yml` fan-out cap
- **Purpose**: collapse the ~60-runs/tip fan-out to ≈1 coalesced verdict per tip (FR-003/004), without touching `report-main` (FR-005).
- **Edits** to `.github/workflows/ci-fleet-verdict.yml`:
  1. Line `:6` `types: [requested, in_progress, completed]` → `types: [completed]` (C-YAML-2).
  2. Add a **top-level** `concurrency:` block (after `on:`, before `jobs:`) exactly (C-YAML-3):
     ```yaml
     concurrency:
       group: ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}
       cancel-in-progress: true
     ```
  3. Refresh the now-stale comment on the `report`(PR) job's `cancel-in-progress: false` (around `:40-44`, C-YAML-6): note that same-head coalescing is now owned by the top-level per-SHA key + the double-snapshot head-drift guard. **Do not change the `report` job's concurrency values**, only the comment.
  4. **`report-main` (`:71-73`): DO NOT CHANGE.** Leave `group: ci-fleet-verdict-main`, `cancel-in-progress: false`.
- **Validation**: `actionlint .github/workflows/ci-fleet-verdict.yml` clean; T004 pins pass.

### Subtask T004 — Lever 2a exact-equality golden-YAML pins
- **Purpose**: pin the trigger + top-level concurrency exactly (a `head_sha in group` substring passes for a broken expr that collapses all tips into one shared `cancel:true` group — the cross-tip cancel NFR-002 forbids).
- **Edits** to `tests/ci/test_fleet_verdict.py`:
  1. Update the existing assertion near `:125` (`test_reporter_trigger_covers_every_registered_workflow_and_reruns`): `set(trigger["types"]) == {"completed"}` (was `{"requested","in_progress","completed"}`). Keep the `workflows` set assertion unchanged.
  2. Add an **exact-equality** top-level-concurrency assertion (C-YAML-3):
     ```python
     reporter = yaml.safe_load(FLEET_VERDICT.read_text())
     assert reporter["concurrency"] == {
         "group": "ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}",
         "cancel-in-progress": True,
     }
     ```
  3. Keep the existing `report`(PR) job assertion (`matrix.pr` group, `cancel-in-progress is False`) GREEN — do not change it.
- **DO NOT** edit `tests/ci/test_fleet_main.py` — `report-main` is unchanged, its `:166` exact assertion must stay green as-is.

### Subtask T005 — dedup survivor test (non-tautological)
- **Purpose**: pin the invariant the coalesce-with-survivor relies on (VI-1/VI-2): the survivor re-reads live evidence (double-snapshot) and a newer terminal verdict is never suppressed.
- **Add** to `tests/ci/test_fleet_verdict.py` using the existing in-memory `API()` port:
  - `test_terminal_survivor_rereads_and_is_not_suppressed`: drive evidence drift **through the `API()` stub's mutating state** so `report()` actually calls `snapshot()` twice and compares — assert it raises `"changed before publication; later event will reconcile"` on drift, and that a `running`→`green`/`red` sequence for the same head **does** publish (extends the existing `:209` duplicate-suppression test). **Never patch `snapshot` itself** (that asserts the mock, not the behavior — Renata non-tautology guard).
- **Validation**: the test exercises the real double-read path in `fleet_verdict.report()` (`:317`, `:332-334`).

### Subtask T006 — verify (levers + invariants + coupling)
- **Purpose**: prove the WP pre-merge (the merged-main-tip proof is the operator's landing step per quickstart.md).
- **Steps** (capture raw output for the PR body):
  1. `actionlint .github/workflows/ci-router.yml .github/workflows/ci-fleet-verdict.yml` → 0 findings (paste raw).
  2. `shellcheck` any changed inline shell (there is none unless you added some) → 0 findings.
  3. `PWHEADLESS=1 .venv/bin/python -m pytest tests/ci/test_fleet_verdict.py tests/ci/test_fleet_main.py tests/ci/test_reconcile_shards.py tests/architectural/test_dual_mode_contract.py -q` → all green (never-green + aggregate guard + router-gate byte-identical policy tests included).
  4. Diff-scope check (NFR-001): `git diff --name-only <base>...HEAD | grep -E 'ci-aggregate|reconcile_shards|aggregate_source|router_gate|fleet_main'` → **empty** (you touched none of them).
  5. Confirm `ruff check` / `ruff format --check` clean on any Python you edited (the test file).
- **Definition of Done gate**: all of T001–T005 landed, all four exact contracts (C-YAML-1/2/3 + the report(PR) comment) applied, `report-main` + `test_fleet_main.py` untouched, all checks in this subtask green with raw output captured.

## Branch Strategy

- **Planning/base branch**: `fix/ci-main-concurrency-fanout-cap` (cut clean from `upstream/main`).
- **Final merge target**: upstream `main`, via an operator-merged PR — never push `main`, never `spec-kitty merge --push`.
- Execution worktree is allocated per computed lane from `lanes.json` (this mission is single-lane). Enter the worktree the resolver gives you; do not reconstruct paths.

## Test Strategy

Honest per C-002: the YAML concurrency/fan-out changes are **not** unit-testable at runtime in pytest — they are pinned by **exact-equality golden-YAML shape assertions** (T002, T004) + the dedup survivor unit test (T005). The real gate is the **merged-main-tip** runbook (quickstart.md SC-001..006). `actionlint`/`shellcheck` are run manually (no CI gate exists). Do not fabricate a test that pretends to exercise the runner.

## Definition of Done

- [ ] T001–T006 complete; `mark-status` recorded for each.
- [ ] C-YAML-1/2/3 applied verbatim; report(PR) comment refreshed (C-YAML-6).
- [ ] `report-main` (`ci-fleet-verdict.yml:71-73`) and `tests/ci/test_fleet_main.py` UNCHANGED.
- [ ] Exact-equality pins present (not substring); dedup survivor test non-tautological.
- [ ] `actionlint`+`shellcheck` = 0 (raw output captured); ci pins + never-green + reconcile + router-gate policy tests green; diff-scope check empty; ruff clean.

## Risks & Reviewer Guidance

- **Fakeable pins** → assert exact equality; reviewer greps the test for `== {` on the concurrency blocks, not `in`.
- **Accidental report-main change** → reviewer diffs `ci-fleet-verdict.yml:71-73` and confirms `test_fleet_main.py` is not in the diff.
- **Green-path widening** → reviewer confirms the diff-scope check is empty (no aggregate/source-eligibility files).
- **Tautological dedup test** → reviewer confirms drift is driven through `API()`, not by patching `snapshot`.
- **Residual survivor wedge** (Debbie MED) is knowingly out of Stage-1 scope (detected by SC-006, self-heal → Stage 3/4b) — do not build a sweep here.
