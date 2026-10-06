---
work_package_id: WP05
title: IO seam and the public re-exports
dependencies:
- WP04
requirement_refs:
- FR-001
- FR-003
- FR-005
- FR-006
- FR-007
- FR-008
- FR-010
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
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
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_engine.py
- tests/runtime/test_bridge_no_compat_*.py
- tests/integration/test_custom_mission_runtime_walk.py
- tests/integration/test_documentation_runtime_walk.py
- tests/integration/test_identity_coord_read.py
- tests/integration/test_mission_run_command.py
- tests/integration/test_owned_next_runtime.py
- tests/integration/test_research_runtime_walk.py
- tests/next/test_decision_unit.py
- tests/next/test_internal_runtime_coverage.py
- tests/next/test_mission_run_back_reference.py
- tests/next/test_next_advance_first_contact_5310.py
- tests/next/test_next_command_integration.py
- tests/next/test_query_mode_unit.py
- tests/next/test_runtime_bridge_blocked_paths.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/_next_mission_scaffold.py
- tests/runtime/next/test_advance_guard_coord_reachability.py
- tests/runtime/next/test_cli_guard_family.py
- tests/runtime/test_bridge_composition.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_bridge_engine.py
- tests/runtime/test_bridge_io.py
- tests/runtime/test_cli_guard_family.py
- tests/runtime/test_next_board_authority.py
- tests/runtime/test_run_index_portability_regression.py
- tests/runtime/test_run_state_hardening.py
- tests/specify_cli/cli/commands/test_implement_characterization.py
- tests/specify_cli/cli/commands/test_next_answer_effective_root.py
- tests/specify_cli/events/test_runtime_moments.py
- tests/specify_cli/missions/test_handle_equivalence_matrix.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/specify_cli/orchestrator_api/test_answer_decision.py
- tests/specify_cli/test_documentation_template_resolution.py
- tests/specify_cli/test_operational_context_wiring.py
- tests/unit/mission_loader/test_command.py
- tests/perf/test_loader_perf.py
- tests/architectural/dead_symbol_allowlist.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – IO seam and the public re-exports

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

Remove the 13 io delegates, make `get_or_start_run` / `build_operational_context_for_claim`
plain re-exports, remove io's back-edges to io names, and repoint tests, reviewing every patch
of a kept re-export by call path (GROUNDING hazard 1).

Done when the gate row `io` passes (including the re-export identity check), the WP01
characterisation file is unchanged and green, `tests/architectural/test_no_dead_symbols.py`
passes, and every io test file passes.

Requirement refs: FR-001, FR-003, FR-005, FR-006, FR-007, FR-008, FR-010. Depends on: WP04.

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

Implementation command: `spec-kitty agent action implement WP05 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T018 – Delete the 13 delegates; add the two re-exports

- **Names**: `_load_feature_runs`, `_mission_key_for_run_ref`, `_build_run_ref`, `_build_discovery_context`, `_resolve_runtime_template_in_root`, `_runtime_template_key`, `_existing_run_ref`, `_start_ephemeral_query_run`, `get_or_start_run`, `_resolve_run_dir_for_mission`, `_resolve_tech_stack_for_profile`, `build_operational_context_for_claim`, `_build_operational_context_for_decision`.
- **Steps**:
  1. Delete the 13 definitions. Add `from runtime.next.runtime_bridge_io import build_operational_context_for_claim, get_or_start_run` with a one-line comment that they are kept for callers outside the package. Keep both in `__all__`.
  2. Every bridge-internal call site uses `_io_seam.<name>`, **including** `get_or_start_run` and `build_operational_context_for_claim` (decision `plan.design.internal-call-style`).
  3. Adapters (squad m1: `_load_feature_runs` and `_build_run_ref` have **no bridge-internal call sites**; their only callers are io:264, :754, :814, handled in T019): `_load_feature_runs(repo_root)` call sites become `_io_seam.load_feature_runs(_io_seam._feature_runs_path(repo_root))` (or an existing io helper that does exactly this, if one exists — check first). `_build_run_ref(...)` call sites call `_io_seam._build_run_ref(...)` without `run_ref_cls`, so io's own `MissionRunRef` binding is used; confirm both bindings are the same class.

### Subtask T019 – Remove io back-edges to io names

- `runtime_bridge_io.py`: `_rb._load_feature_runs` (:264), `_rb._build_discovery_context` ×4, `_rb._resolve_runtime_template_in_root`, `_rb._build_run_ref` ×2, `_rb._runtime_template_key` ×2, `_rb._mission_key_for_run_ref`, `_rb._resolve_run_dir_for_mission`, `_rb._resolve_tech_stack_for_profile` ×2 become intra-module calls (with the `_load_feature_runs` adapter expanded as above). Keep `_rb._resolve_runtime_feature_dir` and the guard-fact names (bridge-owned).
- `runtime_bridge_engine.py` and `src/runtime/next/_internal_runtime/__init__.py` / `run_index.py`: check for io names reached through the bridge and repoint them.
- Rewrite the io module docstring (:64) that describes the live lookup.

### Subtask T020 – Repoint tests for the 11 private names and `MissionRunRef`

- `git grep -nE "<the 11 private names>|runtime_bridge\.MissionRunRef|\"MissionRunRef\"" tests/`. Patch `runtime_bridge_io.<name>`. Tests that patched `runtime_bridge.MissionRunRef` to observe `_build_run_ref`'s substitution now need `runtime_bridge_io.MissionRunRef` (or are mechanism tests: delete/rewrite and log).
- **`MissionRunRef` (squad B2, blocker):** `runtime_bridge_io._build_run_ref` (io:394-399) takes `run_ref_cls=MissionRunRef` as a **default argument**, bound at definition time, so patching `runtime_bridge_io.MissionRunRef` is never seen. Do NOT repoint `tests/next/test_runtime_bridge_unit.py:440` (the `FakeRunRef` `TypeError`-fallback test) to `runtime_bridge_io.MissionRunRef`; rewrite it to call `runtime_bridge_io._build_run_ref(..., run_ref_cls=FakeRunRef)` and assert the fallback branch ran. Rewrite io's docstring at :401-410 accordingly.
- **Mechanism tests that contradict the contract (squad M2):** `tests/runtime/test_bridge_io.py:125` asserts `get_or_start_run.__module__ == "runtime.next.runtime_bridge"` (native delegate), and its `_COMPAT_GUARDED_NAMES` tests (~:60-120) pin the 11 private delegates. Delete them (the gate's Check C/D now pin the opposite contract) and log each deletion for WP06's pass-count reconciliation.
- **Dead-symbol allowlist (squad m6):** `tests/architectural/dead_symbol_allowlist.yaml:1395` cites `runtime_bridge._load_feature_runs` as `load_feature_runs`'s live caller. Update the note to the io-internal caller and confirm `tests/architectural/test_no_dead_symbols.py` still counts it.

### Subtask T021 – Hazard 1: review every patch of a kept re-export by call path

- List every test that patches `runtime_bridge.get_or_start_run` or `runtime_bridge.build_operational_context_for_claim` (string targets, `setattr`, `patch.object`). Re-derive the list yourself; the post-tasks squad's classification (against `main` 1458e92e) is the starting point:
  - **Bridge-internal path → repoint to `runtime_bridge_io.<name>` (12 sites):** `tests/runtime/test_bridge_decide_next.py:256, 291, 369, 429, 478` (via `_dn_bootstrap`; `:291` is a "must NOT be called" negative patch, which would silently lose its guard: make sure it patches the binding the bridge now calls); `tests/next/test_runtime_bridge_blocked_paths.py:206, 261, 312, 363` (`decide_next_via_runtime`); `tests/next/test_next_command_integration.py:550`; `tests/next/test_runtime_bridge_unit.py:613` (`answer_decision_via_runtime`).
  - **Already dead today:** `tests/next/test_query_mode_unit.py:469` — `query_current_state` uses `_existing_run_ref` (bridge:3102) and never calls `get_or_start_run`. Repoint to `runtime_bridge_io._existing_run_ref` if the test needs it, else delete the patch; log it.
  - **CLI lookup on the bridge → patch stays:** `tests/integration/test_mission_run_command.py:132, 184, 216, 261`; `tests/unit/mission_loader/test_command.py:173, 221, 257, 297, 340, 402, 529, 571, 668, 736`; `tests/integration/test_custom_mission_runtime_walk.py:518`; `tests/perf/test_loader_perf.py:164`; `tests/specify_cli/cli/commands/test_implement_characterization.py:832` (valid because `implement_phases.py:361` imports the name inside the function).
- For each, find which caller the test drives:
  - a CLI module (`next_cmd`, `implement_phases`, `workflow_executor`, `mission_loader.command`, `orchestrator_api.decision_verbs`) that looks the name up on the bridge → the patch stays.
  - the bridge's own internal path (`decide_next_via_runtime`, `query_current_state`, `answer_decision_via_runtime`, …) → it now calls `_io_seam.get_or_start_run`, so patch `runtime_bridge_io.get_or_start_run`.
- Make each reviewed test prove its fake ran (assert called, or assert an effect only the fake produces). Record the classification table (test → caller → binding) in the Activity Log.

### Subtask T022 – Flip the gate row

- Remove `io` from `_PENDING_SEAMS`; run the gate, the characterisation file and `tests/architectural/test_no_dead_symbols.py`.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/integration/test_custom_mission_runtime_walk.py tests/integration/test_documentation_runtime_walk.py tests/integration/test_identity_coord_read.py tests/integration/test_mission_run_command.py tests/integration/test_owned_next_runtime.py tests/integration/test_research_runtime_walk.py tests/next/test_decision_unit.py tests/next/test_internal_runtime_coverage.py tests/next/test_mission_run_back_reference.py tests/next/test_next_advance_first_contact_5310.py tests/next/test_next_command_integration.py tests/next/test_query_mode_unit.py tests/next/test_runtime_bridge_blocked_paths.py tests/next/test_runtime_bridge_unit.py tests/runtime/_next_mission_scaffold.py tests/runtime/next/test_advance_guard_coord_reachability.py tests/runtime/next/test_cli_guard_family.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_io.py tests/runtime/test_cli_guard_family.py tests/runtime/test_next_board_authority.py tests/runtime/test_run_index_portability_regression.py tests/runtime/test_run_state_hardening.py tests/specify_cli/cli/commands/test_implement_characterization.py tests/specify_cli/cli/commands/test_next_answer_effective_root.py tests/specify_cli/events/test_runtime_moments.py tests/specify_cli/missions/test_handle_equivalence_matrix.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/orchestrator_api/test_answer_decision.py tests/specify_cli/test_documentation_template_resolution.py tests/specify_cli/test_operational_context_wiring.py tests/unit/mission_loader/test_command.py tests/perf/test_loader_perf.py tests/runtime/test_bridge_adapter_characterisation.py tests/architectural/test_no_dead_symbols.py -q -n auto --dist loadfile
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **Hazard 1 (silent false-green)**: the biggest risk of the mission; T021 is mandatory, not a spot check.
- **Hazard 2 (adapters)**: the characterisation file must stay unchanged and green.
- **`test_no_dead_symbols` pins façade names**: if it lists a deleted private name, update the pin only if the gate's own rules say it should be removed; never weaken the gate.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T17:00:00Z – claude (python-pedro, claude-sonnet-5-5) – Implemented at base 79d2d4f5, commit 50ef6605 (trailer names Claude Sonnet 5.5, per the session attribution reminder). Red-first: gate showed the `io` rows XFAIL (50 passed / 8 xfailed); after the change `io` is out of `_PENDING_SEAMS` (no `_GREEN_TODAY` change) and all rows pass.
  - Source: deleted the 13 delegates from `runtime_bridge.py`; added `from runtime.next.runtime_bridge_io import build_operational_context_for_claim, get_or_start_run` (kept in `__all__`, same objects). Bridge-internal call sites now read `_io_seam.<name>`: `get_or_start_run` x2 (`_dn_bootstrap`, `answer_decision_via_runtime`), `_build_operational_context_for_decision`, `_existing_run_ref`, `_start_ephemeral_query_run`. Unused imports (`DiscoveryContext`, `OperationalContextT`, the empty `TYPE_CHECKING` block) removed. io: 16 `_rb.<name>` reads (7 names) became intra-module calls; `_rb._load_feature_runs(repo_root)` became `load_feature_runs(_feature_runs_path(repo_root))` (no existing io helper did exactly this); `_build_run_ref` is called without `run_ref_cls`, so io's own `MissionRunRef` is used (same class as the bridge's: both import it from `runtime.next._internal_runtime`). 9 deferred `_rb` imports removed; the two that remain are for the bridge-owned `_resolve_runtime_feature_dir` and the guard-fact names. Engine, `_internal_runtime/__init__.py` and `run_index.py` reach no io name through the bridge (only prose). io module docstring and the `load_feature_runs` / `_build_run_ref` docstrings rewritten to state what the seam owns and why `run_ref_cls` must be passed explicitly (B2). `dead_symbol_allowlist.yaml` note for `save_feature_runs` now cites `runtime_bridge_io._load_run_index` (m6); `test_no_dead_symbols` passes.
  - Mechanism tests deleted (1): `tests/runtime/test_bridge_io.py::test_runtime_bridge_keeps_native_thin_delegates_for_public_relocated_names` (asserted `get_or_start_run.__module__ == runtime.next.runtime_bridge`, the opposite of the contract; gate Check C now pins identity). The `_COMPAT_GUARDED_NAMES` set was replaced by `_SEAM_OWNED_NAMES` and `test_seam_defines_every_relocated_symbol` became `test_seam_defines_every_owned_symbol` (same coverage, kept). Rewritten and kept (each still asserts its fake ran), renamed `*_uses_live_lookup_*` -> `*_observes_a_patch_on_*`, patch target `runtime_bridge_io`: `test_runtime_template_key_*build_discovery_context`, `test_runtime_template_key_*resolve_runtime_template_in_root`, `test_existing_run_ref_*load_feature_runs_and_build_run_ref`, `test_build_operational_context_for_claim_*resolve_tech_stack`. Net pass-count effect of WP05: -1 test.
  - B2 (`MissionRunRef`): `tests/next/test_runtime_bridge_unit.py::TestRuntimeBridgeCompatibilityHelpers::test_build_run_ref_falls_back_when_runtime_uses_mission_type` now calls `runtime_bridge_io._build_run_ref(..., run_ref_cls=FakeRunRef)` and asserts the fallback ran (`attempts == ["mission_key", "mission_type"]`, instance is `FakeRunRef`). No patch of `runtime_bridge.MissionRunRef` remains in tests.
  - Other repoints (private names, imports moved to `runtime_bridge_io`): test_runtime_bridge_unit (`_runtime_template_key` x5 incl. 2 patched-context tests, `_load_feature_runs` -> `load_feature_runs(_feature_runs_path(...))` x2, `_mission_key_for_run_ref` x2), test_query_mode_unit (`_existing_run_ref`, `_start_ephemeral_query_run` imports), test_owned_next_runtime (`_existing_run_ref`), test_documentation_runtime_walk, test_documentation_template_resolution, test_answer_decision (`_resolve_run_dir_for_mission`), test_operational_context_wiring (imports; the two "delegate hop" assertions became `_dn_bootstrap -> helper` and an identity assert for the claim re-export), test_run_state_hardening (`rb._runtime_template_key` patch -> `io_seam`), test_bridge_io (8 `rb._load_feature_runs` patches -> `io_seam.load_feature_runs(path)`, 6 `rb._resolve_*` patches -> `io_seam`).
  - T021 classification (re-derived with `grep -rn get_or_start_run|build_operational_context_for_claim tests/`; the squad list holds, 11 bridge-internal `get_or_start_run` sites plus the already-dead one = 12 sites; no test patches the claim builder on the bridge on a bridge-internal path):
    | test file:line (before) | caller driven | binding patched | disposition |
    |---|---|---|---|
    | runtime/test_bridge_decide_next.py:256 | `_dn_bootstrap` (raises -> blocked decision) | `rb.get_or_start_run` -> `_io_seam.get_or_start_run` | repointed; asserts reason carries the fake's "cannot start run" |
    | runtime/test_bridge_decide_next.py:291 | `_dn_bootstrap` merged-mission, "must NOT be called" (`_raising`) | now `_io_seam.get_or_start_run` (the binding the bridge calls at runtime_bridge.py:1379) | repointed; negative guard now live |
    | runtime/test_bridge_decide_next.py:369, 429, 478 | `_dn_bootstrap` | `_io_seam.get_or_start_run` | repointed; added `ctx.run_ref is run_ref` (369 already `==`) to prove the fake ran |
    | next/test_runtime_bridge_blocked_paths.py:206, 261, 312, 363 | `decide_next_via_runtime` | `patch("runtime.next.runtime_bridge_io.get_or_start_run") as get_run` | repointed; `get_run.assert_called_once()` |
    | next/test_next_command_integration.py:550 | `decide_next_via_runtime` | `runtime_bridge_io.get_or_start_run` | repointed; `assert_called_once()` |
    | next/test_runtime_bridge_unit.py:614 | `answer_decision_via_runtime` | `runtime_bridge_io.get_or_start_run` | repointed; asserts `provide` received `fake_run_ref` |
    | next/test_query_mode_unit.py:469 | `query_current_state` (uses `_existing_run_ref`, never `get_or_start_run`) | patch was dead; now `runtime_bridge_io._existing_run_ref` | repointed (not deleted: before, the test passed because the unpatched real lookup found no run and the bootstrap failure produced the same error text); now asserts `_read_snapshot` was called |
    | integration/test_mission_run_command.py:132, 184, 216, 261; unit/mission_loader/test_command.py:173, 221, 257, 297, 340, 402, 529, 571, 668, 736; integration/test_custom_mission_runtime_walk.py:518; perf/test_loader_perf.py:164 | `mission_loader.command` (`runtime_bridge.get_or_start_run`, src/specify_cli/mission_loader/command.py:161) | `runtime_bridge.get_or_start_run` | kept (CLI looks the name up on the bridge) |
    | specify_cli/cli/commands/test_implement_characterization.py:832 | `implement_phases` (imports the name inside the function, :361) | `runtime_bridge.build_operational_context_for_claim` | kept |
    | specify_cli/cli/commands/test_next_answer_effective_root.py, integration/test_identity_coord_read.py:309 | `next_cmd` / fake bridge object | fake `runtime_bridge` stand-ins | kept (do not patch the real module) |
    | decide_next tests at test_bridge_decide_next.py:371, 437, 484 | `_dn_bootstrap` | `_io_seam._build_operational_context_for_decision` | already on the seam; unchanged |
  - Verification (all `-p no:cacheprovider`): gate + `test_bridge_adapter_characterisation.py` (unchanged, no diff): green. WP list + characterisation + `test_no_dead_symbols` + gate, 39 files `-n auto --dist loadfile`: 977 passed, 1 skipped, 1 xfailed (characterisation's), 5 failed. The 5 failures are the known "Unknown mission type None" pollution, not WP05: `test_next_advance_first_contact_5310.py` x3 and `test_next_command_integration.py::TestNextCommandImplementState` x2 (it hit different victims than the three `test_owned_next_runtime` tests, same mechanism and same polluter). Confirmed: running `test_runtime_bridge_composition.py::test_composition_success_skips_legacy_dispatch` followed by the 5310 file and `TestNextCommandImplementState` with `-n0` in a scratch worktree at base 79d2d4f5 gives the same 5 failures; both victim files pass alone on this tree (44 passed). Worktree removed. All 7 seams import standalone. ruff check clean, `ruff format --check --force-exclude` clean, `ruff --select C901 src/runtime/next` clean, mypy 21 errors (baseline 21; all in `_internal_runtime/engine.py`, `prompt_builder.py`, `runtime_bridge_engine.py`, none in changed lines).
