---
work_package_id: WP02
title: Two-surface workflow wiring
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-007
- FR-008
planning_base_branch: feat/ci-prose-only-downroute
merge_target_branch: feat/ci-prose-only-downroute
branch_strategy: Planning artifacts for this mission were generated on feat/ci-prose-only-downroute. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/ci-prose-only-downroute unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-prose-only-downroute-01M31T5S
base_commit: e6e3d58b0a2d6bc0a4952ca44b23d9a749c7ab39
created_at: '2026-09-21T12:10:59.312808+00:00'
subtasks:
- T006
- T007
- T008
- T008b
- T009
- T010
history:
- created by /spec-kitty.tasks 2026-09-21
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent: []
execution_mode: code_change
owned_files:
- .github/workflows/ci-modules.yml
- .github/workflows/ci-router.yml
- tests/ci/test_ci_module_wiring.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

```
/ad-hoc-profile-load python-pedro
```

Then proceed to the Objective.

## Objective

Wire the WP01 classifier into **both** content-blind routing surfaces so a proven
prose-only PR is down-routed off the module matrix, the heavy architectural
battery, and the per-group code shards, while the docs/help-drift lane is turned
**on**. Every other PR must route exactly as it does today.

Read `contracts/prose-only-classifier.md` (wiring contracts) and `research.md`
R1–R3 first. `scripts/ci/gate_selection.py` MUST remain untouched (FR-007).

## Context (why two surfaces — research R1)

- `ci-modules.yml` routes via `gate_selection.select_modules(<git diff list>)` — the
  per-module matrix. Reducible by trimming the path list.
- `ci-router.yml` routes via `dorny/paths-filter` (content-blind) — the `changes`
  job emits per-group booleans consumed by `architectural-heavy`, the
  `tests-<group>` shards, and `tests-docs`. dorny cannot be made content-aware, so a
  new `prose_only` job **output** is threaded into those `if:` conditions.

Reducing only the `ci-modules.yml` list leaves the arch battery + shards running and
the docs lane skipped — the exact inversion #4842 exists to fix.

## Subtasks

### T006 — `ci-modules.yml` path reduction

In the `changed-files` step (which already has `BASE_SHA`/`HEAD_SHA` and runs
`git diff`), after building the file list, replace it with
`prose_only.reduced_paths(files, blob_getter)` before it is handed to
`select_modules`. `blob_getter` fetches `git show <base>:<path>` and
`git show <head>:<path>`; a `git show` failure for a path means that path is **kept**
(fail-closed — never dropped on error). `select_modules`/`gate_selection.py`
unchanged.

### T007 — `ci-router.yml` `prose_only` from a SEPARATE job (squad F2 / R9)

Add a NEW job (`prose-scan`) — NOT a step in `changes` — that checks out and computes
the PR verdict, exposing `outputs.prose_only`. The verdict = every changed path is
either a `.py` proven prose-only (`prose_only.is_prose_only` over `git show` blobs)
OR a path `gate_selection` classifies as a non-code data group (docs/corpus), AND at
least one changed `.py` was prose-only; any other path (config/packaging/unmapped-src)
⇒ `prose_only=false`. Reuse `gate_selection` for the path classification (the wiring
may import it; `prose_only.py` must not). Degenerate/null base ⇒ `false`.

**Why a separate job**: `gate_selection.py`'s `_GROUP_REF = needs\.changes\.outputs\.(\w+)`
only captures references under the `changes` job. A `needs.prose-scan.outputs.prose_only`
reference is invisible to it, so `prose_only` is never parsed as a phantom routing
group and the SC-004 oracles stay green (T010). This is the fix for squad F2 — do
NOT put the output on `changes`.

### T008 — Thread the guards into the lane `if:` conditions

- `architectural-heavy`: add `prose-scan` to `needs:`; append
  `&& needs.prose-scan.outputs.prose_only != 'true'` to `if:`.
- every `tests-<code-group>` (merge/status/cli/…): same `needs:` + `if:` append.
- `tests-docs`: add `prose-scan` to `needs:`; `if:` →
  `needs.changes.outputs.docs == 'true' || needs.prose-scan.outputs.prose_only == 'true'`.
- `router-gate`: add `prose-scan` to its `needs:` (it treats an `if:`-skip as pass).
- Do NOT alter `tests-corpus`/`tests-e2e`, the always-on lanes, or the `changes`
  job / its `unmatched` step.

### T008b — Residual `__doc__` check (squad HIGH-2)

Grep the test suite for code-shard tests that assert on docstring-derived output
(`__doc__`, `inspect.getdoc`). Confirm the only asserters live in `tests/docs/`
(forced on) or are doctests (fail-closed). If any live in a code shard, record the
residual risk in the PR body — the docstring-only down-route is unsafe for that
module until its assertion moves to the docs lane.

### T009 — Wiring + golden tests (`tests/ci/test_ci_module_wiring.py`)

- `reduced_paths` drops a proven prose-only `.py`, so `select_modules` returns the
  narrowed/empty set and the matrix `has-selection=false`; a mixed diff is NOT reduced.
- **golden (hand-pinned, squad F4)**: pin the down-routed lane set for a prose-only PR
  — module matrix ✗ (`has-selection=false`), arch battery ✗, code shards ✗,
  `tests-docs` ✓, always-on ✓ (SC-001). The expected set MUST be written from first
  principles, NOT reverse-engineered from the new `if:` expressions (the same WP edits
  both the routing and this guard). Assert the non-prose PR lane set is byte-identical
  to today (SC-002).

### T010 — Path-purity guard confirmation (SC-004)

Run and keep green: `tests/architectural/test_gate_selection_authority.py`,
`test_local_gate_parity.py`, `test_ci_integrity_oracle_nonvacuous.py`, and the
workflow-coherence guard. Because `prose_only` is a separate-job output (T007), these
must pass unchanged. If any reds, the wiring referenced `prose_only` under `changes`
or edited `gate_selection.py` — fix the wiring, do NOT edit the guard or
`gate_selection.py`.

## Branch Strategy

Planning/base and local merge target: `feat/ci-prose-only-downroute` (then PR'd to
`skupstream/main` by the operator). Enter via `spec-kitty implement WP02` after WP01
is approved/done — the worktree is allocated per `lanes.json`.

## Definition of Done

- Both workflows wired; `prose_only` output computed and consumed; docs lane forced
  on for prose-only.
- Golden lane-set test passes; non-prose routing unchanged (SC-002).
- Path-purity arch guards green; `gate_selection.py` untouched (FR-007).
- ruff/format/mypy clean on the touched test file; workflow YAML valid.

## Risks / Reviewer guidance

- **YAML `if:` expressions** are easy to get subtly wrong — verify operator
  precedence (`&&`/`||`) and that a real code PR is unaffected.
- Confirm the `prose_only` guard can only ever *subtract* code lanes and *add* the
  docs lane; it must never suppress an always-on lane or fight the `unmatched`
  catch-all (research R2).
- Reviewer: trace a docstring-only PR and a mixed PR through both workflows by hand
  and confirm the lane sets match the golden.
