---
work_package_id: WP01
title: Activation-store router group and charter module fan-out
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-006
- FR-007
- FR-009
- NFR-001
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- SC-001
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6336-charter-activation-shard-routing
merge_target_branch: issue-6336-charter-activation-shard-routing
branch_strategy: Planning artifacts for this mission were generated on issue-6336-charter-activation-shard-routing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6336-charter-activation-shard-routing unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Routing data plane
history:
- at: '2026-10-31T12:47:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/
create_intent:
- tests/ci/test_charter_activation_routing.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-router.yml
- scripts/ci/gate_selection.py
- tests/ci/test_charter_activation_routing.py
- tests/architectural/test_workflow_coherence.py
- tests/architectural/test_gate_selection_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Activation-store router group and charter module fan-out

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objective

Close the #6336 hole for the two non-src triggers: an edit to
`.kittify/charter/charter.yaml`, `.kittify/charter/activation.yaml` or
`packs/internal.source.yaml` must select the `charter` registry module, so
`module-tests (charter shard …)` runs on the PR and on the push to `main`.

Do it with a **new NON-src router group** `charter_activation` plus a
hand-authored fan-out row in the single gate-selection authority. Do **not**
append the paths to the existing `charter` filter group: its globs must be a
verbatim transcription of the `charter` scrub roots
(`tests/architectural/test_ci_router_transcription_guards.py::
test_router_src_filters_derive_from_scrub_verbatim`), and #6334 deliberately
refused that edit.

## Context

- Issue: spec-kitty/spec-kitty#6336 (follow-up to #6333 / PR #6334).
- Spec: `kitty-specs/charter-activation-shard-routing-01M68ZRA/spec.md` (FR-001..FR-003,
  FR-006, FR-007, FR-009; SC-001, SC-003, SC-004).
- Plan: `.../plan.md` IC-01 / IC-02. Data model: `.../data-model.md` E1, E2, E5, I1..I6, I10..I12.
- `scripts/ci/gate_selection.py` is the ONE gate-selection authority. It **parses**
  `ci-router.yml`; it never re-encodes the path→group map. The new table is a
  group→module fan-out, the same shape as `CLI_COMMAND_MODULE_FANOUT`.
- `.github/workflows/ci-modules.yml` builds the `module-tests` matrix from
  `select_modules(changed_files)`; that is the executor this WP is wiring.
- 20 registry modules, `charter` among them (`test_dirs`: `tests/charter`,
  `tests/charter_offering`, `shard_count: 7`).

## Subtasks

### T001 — Red-first routing pins

Create `tests/ci/test_charter_activation_routing.py` (module docstring naming #6336
and the class of hole) with, at minimum:

- `test_activation_store_edit_selects_the_charter_module` — parametrized over
  `.kittify/charter/charter.yaml`, `.kittify/charter/activation.yaml`,
  `packs/internal.source.yaml`: `select_gates([path]).matched_groups` contains
  `charter_activation` and `select_modules([path]) == frozenset({"charter"})`.
- `test_the_group_is_non_src_and_never_enters_the_unmatched_union` — the group is
  not in `router.src_backed_groups`, not in the parsed `unmatched` step's union, and
  an unmapped `src/**` path *plus* an activation-store path still yields
  `unmatched_src is True` and run-all (positive control on the same fixture set).
- `test_router_transcribes_the_group_verbatim` — the router filter globs equal the
  declared trigger list exactly, and `changes.outputs` has the row.
- `test_reverting_a_trigger_drops_the_selection` — per-part revert proof: strip each
  glob from a copy of the filter mapping (`Router(filters=..., job_gates=...)`) and
  assert the corresponding path no longer selects `charter`; strip the fan-out row
  and assert the path matches the group but selects no module.
- `test_unrelated_diffs_keep_their_selection` — docs-only selects zero modules;
  `packs/built-in.source.yaml` and `src/specify_cli/review/**` match the same module
  sets as the pre-change router (assert the concrete expected sets, not "unchanged").

Then run it and **record the red**:

```bash
uv run --frozen pytest -q tests/ci/test_charter_activation_routing.py 2>&1 | tail -20
```

Paste the failing summary into the WP history
(`spec-kitty agent tasks add-history WP01 --note "..."`) and into the PR body later.

### T002 — Router group + outputs row

In `.github/workflows/ci-router.yml`:

1. Add the dorny filter group next to `mission_pack_content` / `charter`, with a
   comment that names #6336, says why it is non-src (never in the `unmatched` union,
   never job-gated; the module matrix is its executor), and why the internal trigger
   is the pin lockfile (`packs/internal/**` is untracked since #6451):

   ```yaml
   charter_activation:
     - '.kittify/charter/charter.yaml'
     - '.kittify/charter/activation.yaml'
     - 'packs/internal.source.yaml'
   ```

2. Add the matching `changes.outputs.charter_activation` row in the standard fold
   shape used by the other non-src fan-out groups.

### T003 — Fan-out in the single selection authority

In `scripts/ci/gate_selection.py`:

1. Add `ACTIVATION_STORE_MODULE_FANOUT: dict[str, frozenset[str]] = {"charter_activation": frozenset({"charter"})}`
   directly after `CLI_COMMAND_MODULE_FANOUT`, with a comment that records: the
   hole (#6333 landed green because the charter shard never ran), why the store and
   the pin are the triggers, and **why it cannot be a `GROUP_MODULE_FANOUT` member**
   (the consumer census records only resolved `src/**` imports and
   `packs/built-in/missions/**` runtime reads, so a `.kittify`/pin group derives an
   empty set and `tests/ci/test_fanout_derivation.py::test_derivation_is_non_vacuous`
   would red).
2. Export it in `__all__` (alphabetical position).
3. Union it in the `select_modules` fan-out loop, alongside
   `GROUP_MODULE_FANOUT` / `dependency` / `CLI_COMMAND_MODULE_FANOUT`.

### T004 — Register the deliberately-ungated group

`tests/architectural/test_workflow_coherence.py`:
`_DELIBERATELY_UNGATED_FILTER_GROUPS` gains `"charter_activation"`, and the
docstring that lists the members' reasons gains one line naming #6336 and the
module-matrix executor. This is registration, not a waiver: the group is
non-src and gates no job by design, exactly like `mission_manifest`.

### T005 — Extend the fan-out wiring pin

`tests/architectural/test_gate_selection_authority.py::test_group_module_fanout_is_wired`:
add `ACTIVATION_STORE_MODULE_FANOUT` to the iteration over the three tables (so its
group must be a filter group and its targets real registry modules) and pin the
target set explicitly:

```python
assert ACTIVATION_STORE_MODULE_FANOUT == {"charter_activation": frozenset({"charter"})}
```

Do not relax the existing assertions for the other tables.

### T006 — Verify

```bash
uv run --frozen pytest -q \
  tests/ci/test_charter_activation_routing.py \
  tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_workflow_coherence.py \
  tests/architectural/test_ci_quality_path_filters.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py \
  tests/architectural/test_consumer_census_routing.py \
  tests/ci/test_fanout_derivation.py \
  tests/ci/test_consumer_census.py
uv run --frozen ruff check scripts/ci/gate_selection.py tests/ci/test_charter_activation_routing.py
uv run --frozen ruff format --check scripts/ci/gate_selection.py tests/ci/test_charter_activation_routing.py
```

Record the results in the WP history. If a gate reds for a reason outside this
diff, reproduce it on pristine `origin/main` before attributing it.

## Branch Strategy

- Planning/base branch: `issue-6336-charter-activation-shard-routing`
- Final merge target: `issue-6336-charter-activation-shard-routing` (the mission
  branch; the operator merges the PR into `main`)
- Execution worktrees are allocated per computed lane from `lanes.json`; do not
  hand-build a workspace path.

## Definition of Done

- [ ] The new test module exists and its pre-fix red run is recorded.
- [ ] `charter_activation` is in the router filter block and `changes.outputs`.
- [ ] `ACTIVATION_STORE_MODULE_FANOUT` exists, is exported and is consulted by
      `select_modules`.
- [ ] The two guard registries are extended (no assertion removed or weakened).
- [ ] The verification commands in T006 pass; results recorded.
- [ ] `ruff check` and `ruff format --check` clean on the touched Python files.
- [ ] No `src/` glob was added to the new group; no new registry row, shard or
      test-dir claim was introduced.

## Risks & Reviewer Guidance

- The tempting shortcut — adding the activation-store paths to the `charter`
  filter group — reds the transcription guard and contradicts #6334. Reject it.
- A reviewer should confirm: the group has no `src/` glob; the group is in
  `changes.outputs` but in no job `if:`; `_DELIBERATELY_UNGATED_FILTER_GROUPS` names
  it; the fan-out table's comment records the census reason; the revert rows in the
  new test module genuinely fail when the corresponding part is reverted.
