---
work_package_id: WP02
title: Ledger floor joins the charter group; changelog
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-008
- NFR-002
- C-004
- C-006
- SC-002
- SC-003
- SC-005
planning_base_branch: issue-6336-charter-activation-shard-routing
merge_target_branch: issue-6336-charter-activation-shard-routing
branch_strategy: Planning artifacts for this mission were generated on issue-6336-charter-activation-shard-routing. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6336-charter-activation-shard-routing unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 2 - Cross-subsystem ownership and docs
history:
- at: '2026-10-31T12:47:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/release/
create_intent:
- docs/changelog/CHANGELOG.md
- tests/ci/test_charter_activation_routing.py
execution_mode: code_change
model: ''
owned_files:
- tests/release/ci_retirement_scrub.json
- .github/ci-module-registry.yml
- .github/workflows/ci-router.yml
- tests/ci/test_charter_activation_routing.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Ledger floor joins the charter group; changelog

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

#6336's 2026-10-20 follow-up comment asks for
`src/kernel/activation_ledger_store.py` (the activation ledger's kernel floor,
read through by `tests/charter/activation/**` and
`tests/charter/conformance/test_activation_ledger_conformance.py`) to reach the
charter shard. Today it selects `{core_misc, kernel, unit}` only.

Reach it by adding the file **verbatim to the `charter` scrub group's roots**, and
transcribe that into the registry row and the router filter in the same change.
A `src/` file may not live in WP01's non-src `charter_activation` group: that would
make the group src-backed and drag it into the FR-004 `unmatched` union plus the
"every src-backed group is job-gated" guard.

Also add the `[Unreleased]` changelog entry and run the mission's final targeted
verification sweep.

## Context

- Spec FR-004, FR-005, FR-008, C-006; SC-002, SC-003, SC-005.
- Plan IC-03, IC-05. Data model E3, E4, I1, I7, I8.
- Overlapping src ownership is already the scrub's documented shape: `core_misc`,
  `unit` and `execution_context` each own `src/specify_cli/status/**`.
- `src/charter/activation/activation_ledger.py` already selects `charter` (it is
  under `src/charter/**`); pin it, do not re-route it.

## Subtasks

### T007 — Red-first pins for the ledger floor and the reader

Extend `tests/ci/test_charter_activation_routing.py` (created by WP01) with:

- `test_kernel_ledger_floor_selects_the_charter_module` — `select_modules(["src/kernel/activation_ledger_store.py"])`
  is exactly `{"charter", "core_misc", "kernel", "unit"}`; assert `charter` is
  present *and* the pre-existing three are still present (no narrowing).
- `test_activation_ledger_reader_stays_selected` — `select_modules(["src/charter/activation/activation_ledger.py"]) == {"charter"}`.
- `test_reverting_the_charter_root_drops_the_floor_selection` — per-part revert:
  build a `Router` whose `charter` globs are the registry's pre-change list and
  assert the floor path no longer selects `charter` (proving the root, not something
  else, carries the selection).

Record the pre-fix red run in the WP history.

### T008 — Scrub root

`tests/release/ci_retirement_scrub.json`: append
`"src/kernel/activation_ledger_store.py"` to the `charter` group's `roots` (last
position) and extend that group's `note` with one sentence naming #6336 and why the
ledger floor is owned by the charter group (its readers are `tests/charter/activation/**`).

### T009 — Registry row (verbatim)

`.github/ci-module-registry.yml`: append the same path to the `charter` row's
`roots` in the same position, with a one-line comment naming #6336. Do not touch
`test_dirs`, `cov_targets`, `tier` or `shard_count`.

### T010 — Router filter (verbatim)

`.github/workflows/ci-router.yml`: append the same glob
(`'src/kernel/activation_ledger_store.py'`) to the `charter` filter group, so the
transcription guard's ordered comparison still holds.

### T011 — Changelog

`docs/changelog/CHANGELOG.md`, under `[Unreleased]`: a bold impact-first lead ending
in `(#6336)`, then before/after, under 1,200 characters. Content: an activation-store
(`.kittify/charter/*.yaml`) or internal-pack-pin (`packs/internal.source.yaml`) edit
now runs the charter module shard, and the activation ledger's kernel floor now runs
the charter tests that read it — before, such an edit selected no module at all, so
a parity-breaking activation could reach `main` green (how #6333 did). Mention
#6333/#6334 as the parent references.

### T012 — Final verification sweep

```bash
uv run --frozen pytest -q \
  tests/ci/test_charter_activation_routing.py \
  tests/architectural/test_ci_router_transcription_guards.py \
  tests/architectural/test_gate_selection_authority.py \
  tests/architectural/test_workflow_coherence.py \
  tests/architectural/test_module_shard_registry.py \
  tests/architectural/test_same_tier_uniqueness.py \
  tests/architectural/test_retirement_scrub.py \
  tests/architectural/test_ci_integrity_oracle_nonvacuous.py \
  tests/architectural/test_ci_quality_path_filters.py \
  tests/architectural/test_consumer_census_routing.py \
  tests/ci/test_fanout_derivation.py \
  tests/ci/test_consumer_census.py
```

Record the results in the WP history. Do not run a full heavy suite locally
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Branch Strategy

- Planning/base branch: `issue-6336-charter-activation-shard-routing`
- Final merge target: the mission branch; the operator merges the PR into `main`.
- Execution worktrees come from the computed lanes; never hand-build one.

## Definition of Done

- [ ] The ledger floor selects `charter` **and** keeps `kernel`/`core_misc`/`unit`.
- [ ] The reader pin exists and is green.
- [ ] Scrub root, registry root and router glob are edited together and verbatim.
- [ ] Registry module set (20), `charter` `shard_count: 7` and `test_dirs` unchanged.
- [ ] Changelog entry present under `[Unreleased]`, with `(#6336)`.
- [ ] T012 passes; results recorded.

## Risks & Reviewer Guidance

- Editing only two of the three transcription sites reds
  `test_registry_consumes_scrub_verbatim_no_divergent_rescrub` or
  `test_router_src_filters_derive_from_scrub_verbatim`. All three move together.
- A reviewer should confirm the file is a *floor* module owned by the charter
  group's readers (not a broadening of the charter module's test dirs), that no
  shard count changed, and that the changelog does not over-claim (the heavy
  architectural battery is explicitly out of scope).
