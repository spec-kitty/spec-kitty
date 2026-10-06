---
work_package_id: WP03
title: Retrospective seam
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-003
- FR-006
- FR-009
- FR-010
- NFR-005
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
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
- src/runtime/next/runtime_bridge_retrospective.py
- src/runtime/next/runtime_bridge_engine.py
- tests/runtime/test_bridge_no_compat_*.py
- tests/integration/retrospective/test_default_flow_generator_failure.py
- tests/integration/retrospective/test_default_flow_healthy.py
- tests/integration/retrospective/test_opt_out.py
- tests/integration/retrospective/test_policy_source_attribution.py
- tests/integration/retrospective/test_strict_flow_block.py
- tests/integration/retrospective/test_wp04_coverage_branches.py
- tests/next/test_mission_run_back_reference.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_bridge_engine.py
- tests/runtime/test_bridge_retrospective.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/specify_cli/post_merge/test_retrospective_triggering.py
- tests/architectural/test_runtime_emitter_seam.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Retrospective seam

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

Remove the 9 retrospective delegates (including the `_BufferingRuntimeEmitter` subclass alias),
every back-edge to them (retrospective → itself, engine → retrospective), and repoint tests.

Done when the gate row `retrospective` passes, `tests/architectural/test_runtime_emitter_seam.py`
passes, and the integration retrospective tests pass.

Requirement refs: FR-001, FR-003, FR-006, FR-009, FR-010, NFR-005. Depends on: WP02.

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

Implementation command: `spec-kitty agent action implement WP03 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T010 – Delete the 9 delegates

- **Names**: `_BufferingRuntimeEmitter`, `_rich_hic_prompt`, `_resolve_mission_id_for_terminus`, `_build_retrospective_facilitator_callback`, `_resolve_retrospective_policy_for_runtime`, `_run_retrospective_learning_capture`, `_classify_exc`, `_remediation_hint`, `_classify_and_emit_failure`.
- **Steps**: delete them from the bridge; bridge call sites use `_retrospective_seam.<name>`. `_BufferingRuntimeEmitter` is a subclass that keeps `__module__ == "runtime.next.runtime_bridge"`; check every `isinstance`/construction site and `test_runtime_emitter_seam.py` (it may pin the class's home or module) before replacing with the seam's class.

### Subtask T011 – Remove back-edges

- `runtime_bridge_retrospective.py`: `_rb._classify_and_emit_failure` ×5, `_rb._build_retrospective_facilitator_callback`, `_rb._classify_exc`, `_rb._remediation_hint` become intra-module calls.
- `runtime_bridge_engine.py`: `_rb._resolve_retrospective_policy_for_runtime`, `_rb._resolve_mission_id_for_terminus`, `_rb._run_retrospective_learning_capture` ×2 become `runtime_bridge_retrospective.<name>` (check the import graph; engine → retrospective should be acyclic). Keep `_rb._is_wp_iteration_step` and `_rb._map_runtime_decision` (bridge-owned, FR-004).
- Rewrite the retrospective module docstring (:44–:50) and engine comments that describe the live lookup.

### Subtask T012 – Repoint tests

- `git grep -nE "<the 9 names>" tests/`. The integration retrospective tests patch e.g. `runtime_bridge._run_retrospective_learning_capture`; after T011 the engine looks it up on `runtime_bridge_retrospective`, so patch there. For `_classify_and_emit_failure`, the retrospective seam now calls it intra-module, so patch `runtime_bridge_retrospective._classify_and_emit_failure`.
- `src/specify_cli/post_merge/retrospective_terminus.py` and its test reference retrospective names: confirm they import from the seam, not the bridge; if one imports a removed name from the bridge, that is out of package (C-001): stop and record it, do not edit `src/specify_cli/` without an explicit rationale line in the Activity Log.

### Subtask T013 – Flip the gate row

- Remove `retrospective` from `_PENDING_SEAMS`; run the gate and `tests/architectural/test_runtime_emitter_seam.py`.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/architectural/test_runtime_emitter_seam.py tests/integration/retrospective/test_default_flow_generator_failure.py tests/integration/retrospective/test_default_flow_healthy.py tests/integration/retrospective/test_opt_out.py tests/integration/retrospective/test_policy_source_attribution.py tests/integration/retrospective/test_strict_flow_block.py tests/integration/retrospective/test_wp04_coverage_branches.py tests/next/test_mission_run_back_reference.py tests/next/test_runtime_bridge_unit.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_engine.py tests/runtime/test_bridge_retrospective.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/post_merge/test_retrospective_triggering.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **Emitter identity**: tests or production code may compare `type(emitter).__module__` or use `isinstance` against the bridge's subclass; check before deleting.
- **Silent false-green**: integration tests that patch the bridge's capture function to force a failure path would pass vacuously if they only assert "no exception"; check each asserts the fake was called or its effect is visible.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T14:00:00Z – claude (python-pedro, claude-sonnet-5-5) – Implemented at base f0673fb8, commit 7a0f56f1. Red-first: gate showed `retrospective` rows (A, A', B, D) XFAIL (42 passed / 16 xfailed); after the change 46 passed / 12 xfailed, `retrospective` removed from `_PENDING_SEAMS` (no `_GREEN_TODAY` change needed).
  - Source: deleted the 9 delegates from `runtime_bridge.py` (incl. the `_BufferingRuntimeEmitter` subclass, so the emitter's `__module__` is now the seam's; no `isinstance`/`__module__` pin existed); bridge sites call `_retrospective_seam.<name>`; the two bridge annotations/constructions of `buffer: _BufferingRuntimeEmitter` retyped to `_retrospective_seam._BufferingRuntimeEmitter`. Seam: 7 `_rb.` back-edges (5x `_classify_and_emit_failure`, `_build_retrospective_facilitator_callback`, `_classify_exc`, `_remediation_hint` = 8 call sites) became intra-module calls, 3 deferred `runtime_bridge` imports removed. Engine: 4 `_rb.<retro name>` calls became `_retrospective.<name>`; `_rb._is_wp_iteration_step` / `_map_runtime_decision` kept (bridge-owned, FR-004). Docstrings rewritten: retrospective module docstring, engine module docstring (lines 30-38, "thin compat delegate for advance_run_state_after_composition" is now stated as engine-owned), the `# T012` section comment, and `_emit_terminal`'s docstring.
  - Tests repointed by call path: `test_bridge_decision_log_flush.py` (4 patches + `_SpyBuffer` base/patch -> `_retrospective_seam`, which the bridge now reads), `test_bridge_engine.py` (3+1 patches -> retrospective module, which the engine reads), `test_runtime_bridge_composition.py` (3 string patches -> `runtime.next.runtime_bridge_retrospective.*`), `test_runtime_bridge_unit.py` (emitter from the seam), 6 integration retrospective files (imports from the seam, 15 import lines). `test_bridge_decide_next.py`, `test_mission_run_back_reference.py`, `test_retrospective_triggering.py`, `test_runtime_emitter_seam.py` already targeted the seam: unchanged.
  - Mechanism tests deleted: none. Rewritten (kept, same assertions, patch target now the seam, which is the binding the code under test looks up): `tests/runtime/test_bridge_retrospective.py::test_classify_and_emit_failure_uses_live_lookup_for_classify_and_hint` -> `..._observes_patch_on_seam_for_classify_and_hint`; `::test_run_retrospective_learning_capture_uses_live_lookup_for_facilitator_builder` -> `..._observes_patch_on_seam_for_facilitator_builder`; `::test_facilitator_uses_live_lookup_for_classify_and_emit_failure` -> `..._observes_patch_on_seam_for_classify_and_emit_failure`. Two further tests in that file (`..._swallows_failure_by_default`, `..._reraises_when_blocking`) had only their patch target repointed. Also removed 3 unused module constants and the stale docstring in that file. Pass-count effect: 0 tests removed.
  - Out of package (C-001), not edited: `src/specify_cli/post_merge/retrospective_terminus.py` already imports from the seam; its docstring (~:210-219) still says "runtime_bridge compat delegate" / "live runtime_bridge lookup" (stale prose, no behaviour).
  - Verification: gate + characterisation + WP list (`-n auto --dist loadfile -p no:cacheprovider`, 16 files): 364 passed, 1 skipped, 12 xfailed. All 7 seams import standalone. ruff check clean, `ruff format --check --force-exclude` clean, C901 clean, mypy 21 errors (baseline 21; all in pre-existing lines, payload constructors in the engine).
