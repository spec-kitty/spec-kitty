---
work_package_id: WP04
title: Composition seam
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-003
- FR-006
- FR-007
- FR-010
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
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
- src/runtime/next/runtime_bridge_composition.py
- src/runtime/next/runtime_bridge_io.py
- tests/runtime/test_bridge_no_compat_*.py
- tests/integration/test_custom_mission_runtime_walk.py
- tests/integration/test_documentation_runtime_walk.py
- tests/integration/test_explicit_checkout_commands.py
- tests/integration/test_owned_next_runtime.py
- tests/integration/test_research_runtime_walk.py
- tests/next/test_composition_gate_widening.py
- tests/next/test_occurrence_gate_next_loop.py
- tests/next/test_runtime_bridge_unit.py
- tests/runtime/_next_mission_scaffold.py
- tests/runtime/next/test_advance_guard_coord_reachability.py
- tests/runtime/next/test_cli_guard_family.py
- tests/runtime/next/test_composed_guard_launder.py
- tests/runtime/next/test_pertype_presence_gate.py
- tests/runtime/test_artifact_presence_placement.py
- tests/runtime/test_bridge_composition.py
- tests/runtime/test_bridge_cores.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_bridge_io.py
- tests/runtime/test_next_board_authority.py
- tests/runtime/test_runtime_seam.py
- tests/specify_cli/missions/test_mission_template_consistency.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/specify_cli/next/test_runtime_bridge_dispatch.py
- tests/specify_cli/next/test_runtime_bridge_documentation_composition.py
- tests/specify_cli/next/test_runtime_bridge_research_composition.py
- tests/doctrine/missions/test_referential_integrity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Composition seam

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

Remove the 8 composition delegates, every back-edge to them (composition → itself, io →
composition), and repoint tests.

Done when the gate row `composition` passes and every composition test file passes.

Requirement refs: FR-001, FR-003, FR-006, FR-007, FR-010. Depends on: WP03.

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

Implementation command: `spec-kitty agent action implement WP04 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T014 – Delete the 8 delegates

- **Names**: `_normalize_action_for_composition`, `_should_dispatch_via_composition`, `_resolve_step_agent_profile`, `_resolve_runtime_contract_for_step`, `_count_source_documented_events`, `_publication_approved`, `_check_composed_action_guard`, `_dispatch_via_composition`.
- **Steps**: delete them from the bridge; bridge call sites use the composition seam alias already imported in the bridge (confirm the alias name). Keep `_check_cli_guards` (real logic) untouched apart from what WP06 does.

### Subtask T015 – Remove back-edges

- `runtime_bridge_composition.py`: `_rb._normalize_action_for_composition` ×3, `_rb._resolve_step_agent_profile`, `_rb._resolve_runtime_contract_for_step`, `_rb._check_composed_action_guard` become intra-module calls. Keep `_rb._should_advance_wp_step` (bridge-owned). `_has_generated_docs` is composition-owned (composition:455); the `_rb._has_generated_docs` text at :462 is only a docstring mention, so just fix the docstring.
- `runtime_bridge_io.py`: `_rb._count_source_documented_events`, `_rb._publication_approved` (:1539–:1540), `_rb._resolve_step_agent_profile` (:1033, :1070) become `runtime_bridge_composition.<name>` via a **deferred** import of the composition seam (composition imports io at top level; a top-level io → composition import would cycle). Keep the bridge-owned names at :1526–:1538.
- Rewrite the composition module docstring (:50–:64) that describes the live-lookup idiom.

### Subtask T016 – Repoint tests (call-path review)

- `git grep -nE "<the 8 names>" tests/`. In particular `tests/specify_cli/next/test_runtime_bridge_composition.py`, `tests/runtime/test_bridge_composition.py`, `tests/next/test_composition_gate_widening.py`, `tests/next/test_occurrence_gate_next_loop.py`, the integration runtime walks and `tests/runtime/_next_mission_scaffold.py`.
- For each patch decide: does the code under test reach the name from the bridge (now `_composition_seam.<name>`), from composition (intra-module, so patch `runtime_bridge_composition.<name>`), or from io (deferred `runtime_bridge_composition.<name>`, same binding)? All three now resolve to the composition module attribute, so one patch on the composition module intercepts all of them. Confirm each test still asserts its fake was hit.

### Subtask T017 – Flip the gate row

- Remove `composition` from `_PENDING_SEAMS`; run the gate.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/doctrine/missions/test_referential_integrity.py tests/integration/test_custom_mission_runtime_walk.py tests/integration/test_documentation_runtime_walk.py tests/integration/test_explicit_checkout_commands.py tests/integration/test_owned_next_runtime.py tests/integration/test_research_runtime_walk.py tests/next/test_composition_gate_widening.py tests/next/test_occurrence_gate_next_loop.py tests/next/test_runtime_bridge_unit.py tests/runtime/_next_mission_scaffold.py tests/runtime/next/test_advance_guard_coord_reachability.py tests/runtime/next/test_cli_guard_family.py tests/runtime/next/test_composed_guard_launder.py tests/runtime/next/test_pertype_presence_gate.py tests/runtime/test_artifact_presence_placement.py tests/runtime/test_bridge_composition.py tests/runtime/test_bridge_cores.py tests/runtime/test_bridge_decide_next.py tests/runtime/test_bridge_decision_log_flush.py tests/runtime/test_bridge_io.py tests/runtime/test_next_board_authority.py tests/runtime/test_runtime_seam.py tests/specify_cli/missions/test_mission_template_consistency.py tests/specify_cli/next/test_runtime_bridge_composition.py tests/specify_cli/next/test_runtime_bridge_dispatch.py tests/specify_cli/next/test_runtime_bridge_documentation_composition.py tests/specify_cli/next/test_runtime_bridge_research_composition.py tests/runtime/test_bridge_adapter_characterisation.py -q -n auto --dist loadfile
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **io ↔ composition cycle**: a top-level import from io to composition will fail at import time; keep it deferred and say why in a short comment.
- **`_resolve_step_agent_profile` is read by both io and the bridge**: after this WP both look it up on composition, so a test patching it once covers both.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T15:00:00Z – claude (python-pedro, claude-sonnet-5-5) – Implemented at base c6241a7b, commit 90663c7c. Red-first: gate showed `composition` rows (A, A', B, D) XFAIL (46 passed / 12 xfailed); after the change 50 passed / 8 xfailed, `composition` removed from `_PENDING_SEAMS` (no `_GREEN_TODAY` change).
  - Source: deleted the 8 delegates from `runtime_bridge.py`; the 3 bridge call sites (`_should_dispatch_via_composition`, `_normalize_action_for_composition`, `_dispatch_via_composition`) now read `_composition.<name>`. Composition: 5 deferred `_rb` imports removed (3x `_normalize_action_for_composition`, `_resolve_step_agent_profile`, `_resolve_runtime_contract_for_step`, `_check_composed_action_guard` became plain intra-module calls); the one remaining deferred `_rb` import is `_should_advance_wp_step` (bridge-owned). IO: 4 `_rb.<name>` reads (`_resolve_step_agent_profile` x2, `_count_source_documented_events`, `_publication_approved`) now go through a deferred `runtime_bridge_composition` import (gather_artifact_presence already had one as `_composition`). Docstrings rewritten: composition module docstring (compat-delegate and live-lookup paragraphs), the `_has_generated_docs` docstring, the bridge section comment and header table row, three io docstrings.
  - Tests repointed by call path: import-only moves to `runtime_bridge_composition` (test_custom/documentation/research runtime walks, test_composition_gate_widening, test_runtime_bridge_dispatch, test_runtime_bridge_documentation_composition, test_runtime_bridge_research_composition, test_runtime_bridge_composition [its import block only], test_mission_template_consistency, test_occurrence_gate_next_loop, test_runtime_bridge_unit, test_next_board_authority). Patches: `test_bridge_decision_log_flush.py` (2x4 patches -> `rb._composition`, which the bridge reads), `test_bridge_io.py` (3 patches -> composition module, which io reads), `test_explicit_checkout_commands.py` (1 patch + 2 direct calls -> `rb._composition`), `test_owned_next_runtime.py` (spy patch+read -> composition module). `test_bridge_decide_next.py`, `test_runtime_seam.py`, `test_cli_guard_family.py` already targeted the seam: unchanged. Gate file: only `_PENDING_SEAMS`.
  - Mechanism tests deleted: none. Rewritten (kept; patch target now the seam, which is the binding the code under test looks up; each still asserts its fake ran): `tests/runtime/test_bridge_composition.py::test_should_dispatch_via_composition_uses_live_lookup_for_normalize` -> `..._calls_normalize_on_the_seam`; `::test_resolve_step_binding_uses_live_lookup_for_normalize` -> `..._calls_normalize_on_the_seam`; `::test_resolve_runtime_contract_for_step_uses_live_lookup_for_normalize` -> `..._calls_normalize_on_the_seam`; `::test_composition_dispatch_inputs_uses_live_lookup_for_resolution_helpers` -> `..._calls_resolution_helpers_on_the_seam`; `::test_dispatch_via_composition_uses_live_lookup_for_check_composed_action_guard` -> `..._calls_check_composed_action_guard_on_the_seam`. Patch-only repoint of 2 more in that file (`test_dispatch_via_composition_success_returns_none_when_guard_passes`, `..._returns_guard_failures`) and the delegate-oriented module docstring/comments. `test_check_composed_action_guard_uses_live_lookup_for_should_advance_wp_step` kept as is (bridge still owns the name). Pass-count effect: 0 tests removed.
  - Out of package (C-001), not edited: `tests/unit/mission_loader/test_command.py`, `tests/e2e/test_charter_epic_golden_path.py`, `test_research_composition.py` only mention names in prose. Stale prose in `runtime_bridge_cores.py` (~:21, :820) mentions `_check_composed_action_guard` generically (still accurate).
  - Verification (all `-p no:cacheprovider`): gate + characterisation: 62 passed, 8 xfailed. WP list + `test_bridge_adapter_characterisation.py` + 3 prose-only files (31 files, `-n auto --dist loadfile`): 817 passed, 2 skipped, 3 failed. The 3 failures (`test_owned_next_runtime.py::TestFr007StaleRootCopyBoard::test_stale_root_copy_never_consulted`, `TestFr008RuntimeWalk::test_decide_next_from_tasks_issues_implement_wp01_in_p`, `::test_non_owned_control_walks_from_tasks_to_implement`; "Unknown mission type None") are an xdist ordering flake: identical 3 failures / 817 passed at base c6241a7b in a scratch worktree, and the file is 25/25 green run alone on this tree. All 7 seams import standalone. ruff check clean, `ruff format --check --force-exclude` clean, C901 clean, mypy 21 errors (baseline 21; none in changed files).
