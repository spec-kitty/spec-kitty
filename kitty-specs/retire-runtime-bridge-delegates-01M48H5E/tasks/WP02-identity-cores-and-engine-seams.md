---
work_package_id: WP02
title: Identity, cores and engine seams
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-006
- FR-008
- FR-010
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Seam migration
history:
- at: '2026-10-06T12:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_identity.py
- src/runtime/next/runtime_bridge_cores.py
- src/runtime/next/runtime_bridge_engine.py
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_composition.py
- tests/runtime/test_bridge_no_compat_*.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/next/test_committed_authority.py
- tests/runtime/next/test_merged_mission_terminal.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_io.py
- tests/runtime/test_decision_git_log_write_dir.py
- tests/runtime/test_runtime_bridge_identity.py
- tests/runtime/test_runtime_identity_resolution.py
- tests/runtime/test_runtime_identity_seam_wiring.py
- tests/specify_cli/events/test_decision_log_coord.py
- tests/runtime/test_bridge_cores.py
- tests/runtime/test_requirement_grammar_parity.py
- tests/specify_cli/next/test_runtime_bridge.py
- tests/integration/test_explicit_checkout_commands.py
- tests/integration/test_owned_next_runtime.py
- tests/next/test_mission_run_back_reference.py
- tests/runtime/test_bridge_composition.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/runtime/test_bridge_engine.py
- tests/architectural/test_runtime_emitter_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Identity, cores and engine seams

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission retire-runtime-bridge-delegates-01M48H5E`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Objectives & Success Criteria

Remove the 6 delegates owned by the identity (3), cores (2) and engine (1) seams, every
`_rb.<name>` back-edge to them, and repoint the tests.

Done when the gate rows `identity`, `cores` and `engine` pass (their seams removed from
`_PENDING_SEAMS`), the WP01 characterisation file is unchanged and green, and every test file
that referenced the 6 names passes.

Requirement refs: FR-001, FR-003, FR-006, FR-008, FR-010. Depends on: WP01.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (ATDD red-first, campsite cleaning, no full heavy suites).
- Spec: `kitty-specs/retire-runtime-bridge-delegates-01M48H5E/spec.md`; plan: `plan.md`; ownership map: `data-model.md`; back-edge inventory and hazards: `research.md`; target surface: `contracts/bridge-surface.md`.
- Reference only: the grounding prototype `git show 20547b2d` on `origin/spike/runtime-bridge-grounding-2560-2562` maps the call sites. Read it for orientation; do NOT cherry-pick it (C-003).
- **Call-style rule** (decision `plan.design.internal-call-style`): inside `src/runtime/next/` call a seam-owned name on its owner (`_io_seam._build_run_ref(...)`, `runtime_bridge_retrospective._classify_exc(...)`); a seam calls its own functions directly. A deferred import of the *owning seam* is fine where a cycle forces it (io <-> composition). A lookup of a removed name on the bridge (`_rb.<name>`) is not.
- **Back-edges to names the bridge still owns stay** (FR-004): `_should_advance_wp_step`, `_is_wp_iteration_step`, `_map_runtime_decision`, `_resolve_runtime_feature_dir`, `_has_raw_dependencies_field`, `_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures`. Moving those is #2560's job (C-002).
- Stay inside `src/runtime/next/` for source edits (C-001). Test edits are limited to tests that reference the names this WP removes.
- **Repointing rule for tests**: for every test that patches, imports or reads a removed name, ask "which binding does the code under test look up?" and patch that binding. Do not mechanically rewrite strings. A patch on a removed bridge name fails loudly (`AttributeError`), which is good; a patch on a name that still exists but is no longer looked up passes silently, which is the hazard. Where a test's only purpose was to pin the compat mechanism (a forwarder exists / a live lookup goes through the bridge), delete it or rewrite it as a test of the owning seam's patch point, and list it in the Activity Log with the reason.
- Rewrite any docstring or comment in the files you touch that describes the compat-delegate / live-lookup mechanism for the names you remove, so it states what the seam owns (FR-010, campsite cleaning).

## Branch Strategy

- **Strategy**: single_branch (work packages run in sequence in the repository root checkout)
- **Planning base branch**: issue-2561-retire-runtime-bridge-delegates
- **Merge target branch**: issue-2561-retire-runtime-bridge-delegates

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implementation command: `spec-kitty agent action implement WP02 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T005 – Identity: delete 3 delegates, remove back-edges

- **Names**: `_primary_runtime_feature_dir`, `_resolve_coordination_branch`, `_resolve_mission_ulid`.
- **Steps**:
  1. Delete the three `def`s from `runtime_bridge.py`. Rewrite each bridge call site as `_identity_seam.<name>(...)` (the bridge already imports the seam as `_identity_seam`; confirm).
  2. In `runtime_bridge_identity.py`, the two `_rb._primary_runtime_feature_dir` lookups (:138, :165) become plain intra-module calls. Remove the deferred import if nothing else uses it.
  3. In `runtime_bridge_io.py`, `_rb._resolve_mission_ulid` (:311, :931) becomes `runtime_bridge_identity._resolve_mission_ulid`. Identity has no import of io, so a top-level `from runtime.next import runtime_bridge_identity as _identity` (or the existing alias style in io) is safe; verify with `python -c "import runtime.next.runtime_bridge"`.
  4. Rewrite the identity module docstring (it currently explains the live-lookup idiom, line ~50) to state what the seam owns.

### Subtask T006 – Cores: delete 2 delegates, keep the grammar adapter

- **Names**: `_parse_wp_sections_from_tasks_md`, `_parse_requirement_refs_from_tasks_md`.
- **Steps**: delete both; at each bridge call site of `_parse_requirement_refs_from_tasks_md(content)` call `_cores._parse_requirement_refs_from_tasks_md(content, grammar=grammar)` with `from specify_cli.requirement_mapping import grammar` kept as a **deferred** import at the call site (the existing edge; adding a top-level import may break `tests/architectural/test_layer_rules.py` or `test_bridge_cores_import_boundary.py`). If more than one call site needs it, a tiny private bridge helper is acceptable only if it is not named like the deleted delegate; prefer the inline form. Run the WP01 characterisation tests.

### Subtask T007 – Engine: delete `_advance_run_state_after_composition`

- **Steps**: delete it; callers in the bridge and in `runtime_bridge_composition.py` call `runtime_bridge_engine.advance_run_state_after_composition` (note the different name). Check whether composition reaches it through `_rb.`; if so, replace with a deferred or top-level import of the engine seam (check the import graph for a cycle first).

- **Emitter-seam guard (post-tasks squad B1, blocker):** `tests/architectural/test_runtime_emitter_seam.py:174` requires `_dn_composition_dispatch` to call `_advance_run_state_after_composition` as a bare `ast.Name`, and the mutation test at `:281` asserts the source string `"_advance_run_state_after_composition(\n"`. Your rewrite to an attribute call (e.g. `_engine_adapter.advance_run_state_after_composition(`; use whatever alias the bridge already has for the engine seam) turns both red. Update the guard to match `ast.Attribute(value=ast.Name(<engine alias>), attr="advance_run_state_after_composition")` and update the mutation pair to the new source string, keeping its "assert the needle is present before mutating" non-vacuity check. The prototype `20547b2d` missed this.

### Subtask T008 – Repoint tests for the 6 names

- **Steps**: `git grep -nE "_primary_runtime_feature_dir|_resolve_coordination_branch|_resolve_mission_ulid|_parse_wp_sections_from_tasks_md|_parse_requirement_refs_from_tasks_md|_advance_run_state_after_composition" tests/`. For each hit that targets the bridge (string `"runtime.next.runtime_bridge.<name>"`, `monkeypatch.setattr(rb, "<name>", ...)`, `patch.object(runtime_bridge, "<name>")`, `rb.<name>(...)`), patch the owning seam. `_advance_run_state_after_composition` is patched in ~8 files: patch `runtime_bridge_engine.advance_run_state_after_composition` and confirm the code under test calls it through the engine module attribute (not a `from ... import` binding).
- Tests in `test_runtime_bridge_identity.py` / `test_runtime_identity_seam_wiring.py` that assert the live lookup through the bridge are mechanism tests: rewrite them as "patching `runtime_bridge_identity._primary_runtime_feature_dir` steers `_resolve_coordination_branch`" (owner patch-point test) or delete them; log each.
- **Repointing widens interception (squad m3):** `committed_authority.py:169` imports `_primary_runtime_feature_dir` from the identity seam. Once tests patch the identity function instead of the bridge (`test_bridge_decide_next.py:425` → `None`; `test_runtime_identity_resolution.py:67-133`), the merged-mission short-circuit also sees the fake. If a test changes behaviour because of that, fix the test's fixture/expectation honestly; do not narrow the patch to hide it, and log it.

### Subtask T009 – Flip the gate rows

- Remove `identity`, `cores`, `engine` from `_PENDING_SEAMS` in the gate. Run the gate: those rows pass, the rest still xfail.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_next_runtime.py tests/next/test_mission_run_back_reference.py tests/next/test_runtime_bridge_unit.py tests/runtime/next/test_committed_authority.py tests/runtime/next/test_merged_mission_terminal.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_cores.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_io.py tests/runtime/test_decision_git_log_write_dir.py tests/runtime/test_requirement_grammar_parity.py tests/runtime/test_runtime_bridge_identity.py tests/runtime/test_runtime_identity_resolution.py tests/runtime/test_runtime_identity_seam_wiring.py tests/specify_cli/events/test_decision_log_coord.py tests/specify_cli/next/test_runtime_bridge.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/architectural/test_runtime_emitter_seam.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **Grammar adapter**: losing `grammar=` changes parsing; the WP01 characterisation test catches it.
- **Import cycles** when replacing deferred `_rb` lookups with seam imports: keep a deferred import of the owning seam where a cycle exists; verify every seam imports on its own: `for m in runtime_bridge runtime_bridge_identity runtime_bridge_cores runtime_bridge_engine runtime_bridge_retrospective runtime_bridge_composition runtime_bridge_io; do .venv/bin/python -c "import runtime.next.$m"; done` and the architectural boundary tests.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T13:00:00Z – claude-sonnet-5-5 (python-pedro) – WP02 implemented. Base commit 32c8044c; code commit 49af2898.
  - Deleted from `runtime_bridge.py`: 6 delegates (`_primary_runtime_feature_dir`, `_resolve_coordination_branch`, `_resolve_mission_ulid`, `_parse_wp_sections_from_tasks_md`, `_parse_requirement_refs_from_tasks_md`, `_advance_run_state_after_composition`). Bridge call sites now use `_identity_seam.<name>`, `_cores._parse_requirement_refs_from_tasks_md(..., grammar=grammar)` (grammar was already imported in `_check_requirement_mapping_ready`), `_engine_adapter.advance_run_state_after_composition`.
  - Back-edges removed: 2 in `runtime_bridge_identity` (now direct intra-module calls, deferred `_rb` imports gone), 2 in `runtime_bridge_io` (`_identity._resolve_mission_ulid`, top-level import; verified no cycle). Comments/docstrings rewritten in bridge header, identity, io, composition, engine.
  - Gate: `identity`, `cores`, `engine` removed from `_PENDING_SEAMS`; `_GREEN_TODAY` left as is (it is only consulted for pending seams).
  - B1: `tests/architectural/test_runtime_emitter_seam.py` guard now matches `ast.Attribute(Name("_engine_adapter"), "advance_run_state_after_composition")`; mutation pair needle updated to `"_engine_adapter.advance_run_state_after_composition(\n"` (non-vacuity `assert before in source` kept).
  - Mechanism tests deleted (file::test, reason):
    - tests/runtime/test_bridge_composition.py::test_advance_run_state_after_composition_delegate_still_forwards_to_engine_adapter (pinned the forwarder; engine seam is now called directly)
    - tests/runtime/test_bridge_cores.py::test_bridge_parse_requirement_refs_delegate_reaches_cores_wp_sections (pinned the bridge delegate's live lookup between two delegates; both gone)
    - tests/runtime/test_runtime_identity_seam_wiring.py::test_thin_delegates_forward_to_the_seam (pinned bridge forwarder)
  - Rewritten (same count): test_runtime_identity_seam_wiring `..._uses_live_lookup_for_primary_runtime_feature_dir` x2 -> `..._reads_meta_through_the_seams_primary_dir` (owner patch point `runtime_bridge_identity._primary_runtime_feature_dir`); test_bridge_io::test_get_or_start_run_uses_live_lookup_for_resolve_mission_ulid -> `..._resolves_mission_ulid_on_the_identity_seam` (patches `io_seam._identity`).
  - Repointed by call path: test_runtime_bridge_identity (patch strings -> identity module; import `_resolve_mission_ulid` from identity), test_runtime_identity_resolution (rb -> identity), test_bridge_decide_next:425 (`rb._identity_seam`; `committed_authority` imports from identity at call time so it now also sees the fake; test still green, no expectation change), test_runtime_bridge_unit (parse tests call cores with `grammar=`; owned-coord test patches `rb._identity_seam`), specify_cli/next/test_runtime_bridge (cores + grammar), test_decision_log_coord (import from identity), test_mission_run_back_reference / specify_cli/next/test_runtime_bridge_composition (call engine function directly), test_explicit_checkout_commands / test_owned_next_runtime / test_bridge_decision_log_flush (patch `rb._engine_adapter.advance_run_state_after_composition`; bridge looks it up as that module attribute).
  - Verification: gate + characterisation + WP test list (`-n auto --dist loadfile`): 698 passed, 1 skipped, 16 xfailed. Extra: test_bridge_cores_import_boundary, test_layer_rules, test_no_dead_symbols, test_runtime_bridge_identity_git_repo: 127 passed. Seam standalone imports OK; ruff check, format --check, C901 clean; mypy src/runtime/next: 21 errors (= baseline).
