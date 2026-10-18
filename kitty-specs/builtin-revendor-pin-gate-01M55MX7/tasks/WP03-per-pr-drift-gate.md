---
work_package_id: WP03
title: Per-PR drift gate
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-010
- NFR-004
- SC-001
planning_base_branch: feat/builtin-revendor-pin-gate
merge_target_branch: feat/builtin-revendor-pin-gate
branch_strategy: Planning artifacts for this mission were generated on feat/builtin-revendor-pin-gate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/builtin-revendor-pin-gate unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
phase: Phase 1 - Implementation
history:
- at: '2026-10-17T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/
create_intent:
- tests/architectural/test_built_in_drift_gate.py
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/packs.yml
- tests/architectural/test_built_in_drift_gate.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '3504'
---

# Work Package Prompt: WP03 – Per-PR drift gate

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make CI fail any PR whose committed `packs/built-in/` no longer matches the pin:

- Add a **built-in lane** job in `.github/workflows/packs.yml` that runs
  `spec-kitty charter pack vendor --check` (offline — compares the committed tree to the committed
  lockfile, no network; NFR-004) and add it to `packs-gate.needs` so a drift reds the terminal gate.
- Prove the gate with a test that drives the **SAME `spec-kitty charter pack vendor --check` command**
  on a drifting-tree fixture (NOT an assertion over the workflow YAML text) and asserts non-zero + the
  FR-010 remedy message. Red-first.

Success = FR-008, FR-010, SC-001 in [spec.md](../spec.md) hold.

## Context & Constraints

- **Plan**: [plan.md](../plan.md) IC-03. **Research**: [research.md](../research.md) D4. **Charter**: `.kittify/charter/charter.md`.
- **Depends on WP02's `--check`** — the gate is just that command wired into CI. Do not re-implement
  drift detection here.
- **Non-vacuity (DIRECTIVE_043 / the mission's own rule)**: the acceptance test MUST invoke the real
  `vendor --check` command (via `CliRunner` or a subprocess) on a fixture whose `packs/built-in/` has
  a one-byte edit and assert exit non-zero + the remedy substring. A test that only greps `packs.yml`
  for the command string is vacuous and is explicitly forbidden by the spec (US3-S2).
- **Offline (NFR-004)**: `--check` must not reach the network; the CI job needs no `GIT_TOKEN` and no
  open-packs fetch. (Only an actual pin bump via `vendor` — not this gate — reaches open-packs.)
- **Workflow placement**: mirror the existing built-in-lane jobs (`built-in-regen-check`,
  `built-in-drg-check`): `needs: [changes]`, `if: ${{ needs.changes.outputs.built_in == 'true' }}`,
  `uv sync --frozen --all-extras` then `uv run --frozen spec-kitty charter pack vendor --check`, with
  a `failure()` step echoing the remediation (`::error::`). The built-in filter already covers
  `packs/built-in/**`; the lockfile `packs/built-in.source.yaml` is a sibling — **add it to the
  `built_in` dorny filter paths** so a lockfile-only change also runs the lane.
- **Wire into the gate**: add the new job name to `packs-gate.needs` (the terminal aggregator), so a
  real failure blocks `packs gate`. Keep it BLOCKING (not `continue-on-error`) — this is the #3504
  regression guard, not advisory.
- The test home is `tests/architectural/` (a tree-wide invariant about the committed tree vs the pin).
  Per `NO_FULL_HEAVY_SUITES_IN_MISSION`, during this mission run only THIS gate file, never the bare
  `tests/architectural/` directory.

## Branch Strategy

- **Strategy**: single_branch (direct in the write checkout; no lane worktree)
- **Planning base branch**: feat/builtin-revendor-pin-gate
- **Merge target branch**: feat/builtin-revendor-pin-gate (PR → main)

## Subtasks & Detailed Guidance

### Subtask T009 – Red-first drift-gate test (drives the real command)

- **Purpose**: ADR `2026-07-17-1` + non-vacuity (FR-008, FR-010, SC-001).
- **Steps**:
  1. In `tests/architectural/test_built_in_drift_gate.py`, build a fixture repo-root copy
     (committed `packs/built-in/` + `packs/built-in.source.yaml`), introduce a one-byte edit under
     `packs/built-in/`, and invoke the REAL `spec-kitty charter pack vendor --check` against it (same
     command CI runs — via `CliRunner().invoke(app, ["charter","pack","vendor","--check"])` with the
     fixture as repo root, or a subprocess with `$PWD/src:$PWD` on PYTHONPATH).
  2. Assert exit non-zero AND the FR-010 remedy substring (names `vendor`, says bump the pin / do not
     hand-edit). Add the in-sync positive control: an unedited fixture exits 0.
  3. The red-first evidence for this WP **is the drifting-fixture case itself** (single_branch runs
     sequentially, so WP02's `vendor --check` is already present when this WP starts — a "command
     absent" red is not reproducible and is not the point). The always-reproducible, non-vacuous
     red/green pair is: drifted fixture → non-zero + remedy (RED before the gate wiring/detection is
     correct), in-sync fixture → 0 (positive control). Record both.
- **Files**: `tests/architectural/test_built_in_drift_gate.py`
- **Parallel?**: No.
- **Notes**: Do NOT assert on `packs.yml` text. The whole point is to exercise the command the gate
  invokes.

### Subtask T010 – Wire the gate into packs.yml

- **Purpose**: FR-008 — CI reds a drifting PR.
- **Steps**:
  1. Add a `built-in-vendor-check` job (name it clearly) to the built-in lane of `.github/workflows/packs.yml`,
     mirroring `built-in-drg-check`: `needs: [changes]`, gated on `needs.changes.outputs.built_in == 'true'`,
     `uv sync --frozen --all-extras` + `uv run --frozen spec-kitty charter pack vendor --check`, plus a
     `failure()` step echoing `::error::packs/built-in drifted from the pin. Run: spec-kitty charter pack vendor (then commit).`.
  2. Add `packs/built-in.source.yaml` to the `built_in:` dorny filter paths (so a lockfile-only edit
     runs the lane).
  3. Add `built-in-vendor-check` to `packs-gate.needs`.
  4. Run the repo's workflow-YAML linters if any are wired (`actionlint` is not required locally); at
     minimum validate the YAML parses.
- **Files**: `.github/workflows/packs.yml`
- **Parallel?**: No (depends on T009's expectations).

## Test Strategy

- Red-first drift test driving the real `vendor --check` on a drifting fixture; in-sync positive
  control.
- Targeted surface: `tests/architectural/test_built_in_drift_gate.py` (the specific gate file only) +
  `tests/charter_offering/test_pack_vendor.py` (confirm the command still behaves). Record commands +
  counts in the PR. NO bare `tests/architectural/` run (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Risks & Mitigations

- **Vacuous YAML-text test**: the test drives the real command on a fixture — never greps the workflow.
- **Gate not reaching the terminal aggregator**: add the job to `packs-gate.needs`; a job absent from
  `needs` cannot block (memory: "needs:-gate masks hidden reds").
- **Lockfile change not triggering the lane**: add `packs/built-in.source.yaml` to the `built_in`
  filter.
- **Network creep**: `--check` is offline; the job must not depend on `GIT_TOKEN`.

## Review Guidance

- Confirm the test exercises the real command (non-vacuous) and asserts the remedy message.
- Confirm the new job is blocking, in the built-in lane, and in `packs-gate.needs`.
- Confirm the `built_in` dorny filter includes the lockfile path.
- Confirm no network dependency in the `--check` job.

## Progress & Status

Progress/history/status live in the status event log — do not hand-edit here.
- Record a note: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- Change status: `spec-kitty agent tasks move-task WP03 --to <status>`
- View: `spec-kitty agent tasks status`
