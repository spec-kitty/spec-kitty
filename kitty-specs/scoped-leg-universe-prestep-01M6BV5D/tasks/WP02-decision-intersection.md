---
work_package_id: WP02
title: The decision answers for the leg's selected gates
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7001-universe-prestep-scope
merge_target_branch: issue-7001-universe-prestep-scope
branch_strategy: Planning artifacts for this mission were generated on issue-7001-universe-prestep-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7001-universe-prestep-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-scoped-leg-universe-prestep-01M6BV5D
base_commit: c3a5c424fb25e74e4e3b57a1c362a5b7600379db
created_at: '2026-11-01T16:41:38.113823+00:00'
subtasks:
- T004
- T005
- T006
- T007
phase: Phase 2 - Core behaviour
history:
- at: '2026-11-01T15:25:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/collect_universe_prestep.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/collect_universe_prestep.py
- .github/workflows/ci-router.yml
- tests/ci/test_collect_universe_prestep.py
- tests/ci/test_ci_workflow_prestep_shape.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The decision answers for the leg's selected gates

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) before parsing
the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: t3-code

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status` first; address every item and record each
with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

`python -m scripts.ci.collect_universe_prestep consumers --battery-part <part>` stops answering
for the leg's whole battery partition and answers for the gates the diff actually selected — so a
scope-only leg that selects no universe consumer skips the key/restore/collect/save/check chain
instead of paying a full collection (396.7 s cold, measured). CI passes the file.

Done when:

- `consumers` accepts `--gates-file <path>`; omitted means `$SK_BATTERY_GATES_FILE`; empty means
  the whole part (today's answer).
- With a readable file the answer is
  `bool(battery_part_files(part) ∩ read_selected_gates(file) ∩ universe_consumers())`.
- A named file that cannot be read exits 1 with nothing on stdout and a message on stderr.
- `ci-router.yml`'s `select` step passes `--gates-file "${{ steps.scope.outputs.gates_file }}"`,
  and `tests/ci/test_ci_workflow_prestep_shape.py` pins it with a mutation case that rejects a
  decision which keeps the argument but ignores it.

## Context & Constraints

- Spec: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/spec.md` (US1, US2, FR-001..FR-006).
- Plan IC-03/IC-04/IC-05; contract `contracts/selected-gates-file.md`; quickstart steps 1–4.
- C-002: **never narrow the collection.** A leg that collects still collects the whole tree; only
  the decision is intersected.
- C-003: the battery pytest command line, the step order and every existing guard stay as they
  are. The `select` step keeps `shell: bash`, keeps no `||`, keeps always running, keeps writing
  `universe=` to `$GITHUB_OUTPUT`.
- WP01 supplies `scripts.ci.battery_scope.read_selected_gates`; do not re-implement parsing.

## Branch Strategy

- **Strategy**: mission branch `issue-7001-universe-prestep-scope`, merge target `main`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T004 – Red-first decision tests through the real CLI entry point

- **Purpose**: The change is a behaviour change at a CLI, so the failing test must go through
  the CLI, not a helper.
- **Steps**:
  1. In `tests/ci/test_collect_universe_prestep.py`, add tests that call `main(["consumers",
     "--battery-part", ..., "--gates-file", ...])` (or the subprocess form the file already uses)
     and assert stdout/exit:
     - non-consumer gates only → `false`, exit 0 (this fails on `main`: it prints `true`);
     - a real consumer gate for that part (`test_fast_tier_marker_completeness.py` for `1/2`,
       `test_same_tier_uniqueness.py` for `2/2` — or a fixture-driven consumer if the file
       prefers fixtures) → `true`, exit 0;
     - no gates file → today's whole-part answer, asserted **against the computed partition**
       (`bool(battery_part_files(part) & universe_consumers())`) rather than a hard-coded `true`:
       the partition moves with the timings, and a hard-coded answer breaks on a recapture that
       has nothing to do with this change (the reference page's stale "leg 2/2 holds no
       collecting test" sentence is the proof that this assumption rots);
     - an empty gates file → `false`, exit 0;
     - a missing gates file → exit 1, empty stdout, stderr names the path;
     - the environment form: `SK_BATTERY_GATES_FILE` set and no `--gates-file` behaves like the
       option;
     - a gates file naming gates of the other leg only → `false`.
  2. Pair every refusal (the missing-file case) with a same-fixture positive control (the same
     path, file present) so the probe is not vacuous.
- **Files**: `tests/ci/test_collect_universe_prestep.py`
- **Notes**: The existing file pins `consumers`' current answers; keep those cases meaningful —
  a whole-part answer with no file must stay `true` for both parts.

### Subtask T005 – Implement `--gates-file` and the intersection, fail closed

- **Purpose**: Deliver the behaviour T004 pins.
- **Steps**:
  1. Add `--gates-file` to the parser (`consumers` only, like `--battery-part`); default
     `None`, resolved to `os.environ.get("SK_BATTERY_GATES_FILE", "")` inside `cmd_consumers`
     when the option is omitted.
  2. Implement `leg_files(part, gates_file)` (or an equivalent named helper) returning
     `battery_part_files(part)` when no file is named, else the intersection with
     `read_selected_gates(...)`; an unreadable file raises and `cmd_consumers` prints
     `consumers failed: <error>` to stderr and returns 1 (no stdout answer).
  3. Print one stderr line naming how many of the part's files the leg selected, so a CI reader
     sees why the pre-step declined (e.g. `scoped leg: 3 of 125 files selected`).
  4. Update the module docstring's `consumers` paragraph and the command help text.
  5. Update `__all__` if a new public name is added.
- **Files**: `scripts/ci/collect_universe_prestep.py`
- **Notes**: Keep the answer on stdout exactly `true`/`false` — the workflow matches it with a
  `case`. Do not read the gates file when no answer needs it (no file named → no read).

### Subtask T006 – Wire the leg's gates file into the `select` step of `ci-router.yml`

- **Purpose**: Make the intersection reach CI.
- **Steps**:
  1. In the `select` step's `consumers` invocation, append
     `--gates-file "${{ steps.scope.outputs.gates_file }}"`.
  2. Extend the step's comment block: a scoped leg asks only about the gates the diff selected,
     so a scope-only leg with no consumer skips every universe step; a whole-leg run passes an
     empty path and keeps the whole-part answer.
  3. Change nothing else in the step (no `||`, keep `shell: bash`, keep it unguarded).
- **Files**: `.github/workflows/ci-router.yml`
- **Notes**: `steps.scope.outputs.gates_file` is the path `battery_scope select --out` wrote; the
  `scope` step already runs before `select`.

### Subtask T007 – Extend the workflow-shape test and its mutation cases

- **Purpose**: The pinned shape must cover the new argument, and a decision that ignores it must
  be rejected.
- **Steps**:
  1. Update `_CONSUMERS_RE` (or add a second pattern) so it requires the `--gates-file` argument
     bound to `${{ steps.scope.outputs.gates_file }}`; a decision without it fails
     `_heavy_decision_problems`.
  2. Add mutation cases: the argument stripped; the argument present but the run text not passing
     it to `consumers`; the argument hard-coded to a path (not the step output); and the decision
     and the pytest step naming **different** expressions, so `consumers` asks about a file the
     leg does not read (both steps must resolve the same
     `${{ steps.scope.outputs.gates_file }}`).
  3. Keep every existing mutation case passing — the control (`_prestep_problems(...) == []`) must
     hold for the real job.
- **Files**: `tests/ci/test_ci_workflow_prestep_shape.py`
- **Notes**: The file's philosophy is "a pure function of one parsed job"; keep the new checks in
  `_heavy_decision_problems` rather than a new ad-hoc assertion.

## Test Strategy

```bash
uv run --frozen pytest -q tests/ci/test_collect_universe_prestep.py tests/ci/test_ci_workflow_prestep_shape.py tests/ci/test_battery_scope.py
uv run --frozen pytest -q tests/architectural/test_battery_partition_plugin.py
uv run --frozen ruff check scripts/ci/collect_universe_prestep.py tests/ci/test_collect_universe_prestep.py tests/ci/test_ci_workflow_prestep_shape.py
uv run --frozen mypy scripts/ci/collect_universe_prestep.py
```

Also run the quickstart's steps 2–4 by hand and paste the observed output into the WP history.

## Risks & Mitigations

- A narrowed leg that needed the universe: covered by the consumer-gate case (FR-002) and by
  `check`, which reds a job whose test collected for itself.
- The workflow rendering the empty output as `''`: the `scope` step writes `gates_file=` for a
  full run, which reaches `consumers` as an empty string → whole part (FR-003, tested).
- A test that only exercises a helper: every acceptance case goes through `main([...])`.

## Review Guidance

- Confirm the decision reads no file when none is named, and that the file is read exactly once.
- Confirm stdout stays `true`/`false` only, and the fail-closed path prints nothing there.
- Confirm the workflow diff is one argument plus comments — nothing else moved.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change status**: `spec-kitty agent tasks move-task WP02 --to <status>`
