---
work_package_id: WP06
title: 'Close-out: docstrings, last xfail, full surface'
dependencies:
- WP05
requirement_refs:
- FR-002
- FR-004
- FR-009
- FR-010
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- NFR-005
planning_base_branch: issue-2561-retire-runtime-bridge-delegates
merge_target_branch: issue-2561-retire-runtime-bridge-delegates
branch_strategy: Planning artifacts for this mission were generated on issue-2561-retire-runtime-bridge-delegates. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2561-retire-runtime-bridge-delegates unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
phase: Phase 3 - Close-out
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
- src/runtime/next/runtime_bridge_retrospective.py
- src/runtime/next/runtime_bridge_composition.py
- tests/runtime/test_bridge_no_compat_*.py
- tests/runtime/test_bridge_adapter_characterisation.py
- tests/next/test_composition_gate_widening.py
- tests/runtime/test_bridge_engine.py
- tests/runtime/test_bridge_io.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Close-out: docstrings, last xfail, full surface

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

Finish the mission: fix `_check_cli_guards`'s docstring, drop the last xfail, remove remaining
stale compat comments, and prove the whole targeted surface green.

Done when the gate file has no xfail left, `grep -c "Thin compat delegate"` on the bridge is 0,
the full runtime_bridge test surface has 0 failures, and the named architectural gates, mypy
(<= 21), ruff and format are clean.

Requirement refs: FR-002, FR-004, FR-009, FR-010, NFR-001, NFR-002, NFR-003, NFR-004, NFR-005. Depends on: WP05.

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

Implementation command: `spec-kitty agent action implement WP06 --agent claude --mission retire-runtime-bridge-delegates-01M48H5E`.

## Subtasks & Detailed Guidance

### Subtask T023 – `_check_cli_guards` docstring; last xfail

- Rewrite the docstring to describe what the function does (evaluates the CLI guards via `runtime_bridge_cores.evaluate_guards` with the bridge's facts — read it and say precisely). Remove the `xfail` on the docstring check in the gate.

### Subtask T024 – Stale compat comments sweep

- `git grep -nE "compat delegate|compat surface|FR-012|live lookup|live, deferred lookup|_rb\.<name>" src/runtime/next/`. Rewrite or delete every comment block that describes the retired mechanism (the bridge's module-level #2531 comment block included). Keep comments that describe the remaining bridge-owned back-edges, reworded to say why they are still deferred.

- WP01 review note (minor): `tests/runtime/test_bridge_adapter_characterisation.py` lines 8 and 111–138 describe `run_ref_cls` coverage; losing `run_ref_cls=` at a call site cannot be caught patch-free (same default class). Add one docstring line saying call-site coverage is WP05 T020's `run_ref_cls=FakeRunRef` test. Docstring only; no assertion changes.

- WP03 review notes (low): `src/runtime/next/runtime_bridge.py:34-42` header still claims native compat delegates for the 9 retrospective symbols; `tests/runtime/test_bridge_engine.py:484-486` docstring still says the helpers live "on `runtime_bridge`" (say `runtime_bridge_retrospective`; docstring-only, out-of-map edit with this rationale).
- Out of package (C-001), record in the spec's Deferred section instead of editing: stale prose in `src/specify_cli/post_merge/retrospective_terminus.py:216-221` (live runtime_bridge lookup) and `src/specify_cli/mission_loader/command.py` (`runtime_bridge._build_discovery_context`).

- WP04 review note (low, pre-existing, campsite in a file this mission touched): `tests/next/test_composition_gate_widening.py:96-118` `mock_resolve.assert_not_called()` can never fail because `_should_dispatch_via_composition` calls `_resolve_step_binding`, not `_resolve_step_agent_profile`. Patch `_resolve_step_binding` on the composition seam instead so the negative assertion guards the real call (out-of-map edit; record rationale).

- WP05 review note (low): `tests/runtime/test_bridge_io.py:21-22` module docstring item 4 claims mechanism tests for the re-exports and `run_ref_cls` that the file no longer has; point it at the gate (`tests/runtime/test_bridge_no_compat_delegates.py`) and `tests/next/test_runtime_bridge_unit.py` (out-of-map docstring edit; record rationale). The `mission_loader/command.py:204` docstring stays deferred (C-001).
- Known pre-existing (#5817): `Unknown mission type None` failures in `test_owned_next_runtime.py`, `test_next_advance_first_contact_5310.py`, `test_next_command_integration.py::TestNextCommandImplementState` when co-scheduled after `test_composition_success_skips_legacy_dispatch`; classify, don't fix.

### Subtask T025 – Full targeted verification

```bash
FILES=$(git grep -l runtime_bridge -- 'tests/*.py'); .venv/bin/python -m pytest $FILES tests/runtime tests/next tests/specify_cli/next -q -p no:cacheprovider -n auto --dist loadfile
make test-fast
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_bridge_cores_import_boundary.py tests/architectural/test_runtime_emitter_seam.py tests/architectural/test_no_legacy_terminology.py -q
.venv/bin/mypy src/runtime/next | tail -1
.venv/bin/ruff check src/runtime/next && .venv/bin/ruff format --check --force-exclude <changed files>
```

- Compare the pass count with the baseline (2738 passed / 4 skipped on `main` 7297d8c0, over the same command). Any drop must equal the mechanism-only tests deleted in WP02–WP05 (list them from the Activity Logs). Any failure: classify per CLAUDE.md "baseline-red gotcha" against `main` before treating it as yours.

### Subtask T026 – Final false-green sweep

- Script it: collect every string patch target `"runtime.next.runtime_bridge.<X>"` and every `setattr`/`patch.object` on the bridge module across `tests/`; assert each `<X>` is still a bridge attribute (anything else is a leftover) and flag any use of `create=True` / `raising=False` on the bridge. Record the result (expected: 0 leftovers) in the Activity Log.


## Test Strategy

Run, and record commands with pass/fail counts in the Activity Log:

```bash
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py -q
.venv/bin/python -m pytest tests/runtime/test_bridge_no_compat_delegates.py tests/runtime/test_bridge_adapter_characterisation.py -q   # no xfail left
.venv/bin/ruff check src/runtime/next <changed test files>
.venv/bin/ruff format --check --force-exclude src/runtime/next <changed test files>
.venv/bin/mypy src/runtime/next | tail -1   # must stay <= 21 errors (main baseline); none in changed lines
.venv/bin/ruff check --select C901 src/runtime/next   # complexity <= 15
```

Run on a clean tree (commit first): `tests/runtime/test_reassess_under_lock.py` reports
"Baseline source is dirty" on a dirty worktree, which is environmental.
Never run `make test-full`, the whole `tests/architectural/` directory, or any whole-repo sweep.

## Risks & Mitigations

- **A pass-count drop hiding a lost test**: reconcile against the deletion log.
- **Out-of-scope docstring** in `src/specify_cli/mission_loader/command.py` (mentions `runtime_bridge._build_discovery_context`): leave it; it is listed in the spec's Deferred section.

## Review Guidance

- Reviewer is a different agent from the implementer (charter SO#8).
- Check the gate rows for this WP's seam(s) moved from strict-xfail to passing **in this WP's diff** and nowhere else.
- For every repointed patch, open the code under test and confirm the patched binding is the one it looks up. Spot-check at least five by call path; check every one that touches a kept re-export.
- Check the adapters' characterisation tests (WP01) are untouched and green.
- Confirm no logic moved out of the bridge (C-002) and no source outside `src/runtime/next/` changed (C-001).
- Confirm mypy did not grow and ruff/format are clean.

## Activity Log

- 2026-10-06T12:10:00Z – system – Prompt created.
- 2026-10-06T18:00:00Z – claude (python-pedro, claude-sonnet-5-5) – Implemented at base 16348952, commit e952399e (spec Deferred section: 81e68f1e; trailer names Claude Sonnet 5.5, per the session attribution reminder).
  - T023: `_check_cli_guards` docstring rewritten (gathers the io snapshot, sets `wp_advance_ready` from the bridge-owned `_should_advance_wp_step` for implement/review, folds through `_cores.evaluate_guards_strict`, which raises for an unregistered family). The xfail on `test_no_thin_compat_delegate_docstring_left_on_the_bridge` is removed: the gate has no xfail left (`tests/runtime/test_bridge_no_compat_delegates.py` + characterisation: 70 passed, 0 xfailed).
  - T024 sweep: rewrote the bridge header (retrospective and io rows no longer claim native compat delegates; the `__all__` rule no longer cites a "guarded compat re-export block (FR-012)"), the WP18 self-alias comment, the `__all__` section comment, and `runtime_bridge_composition.py` comment on the deferred `_rb._should_advance_wp_step` import (bridge-owned, kept, reworded). Remaining hits of the sweep regex in `src/runtime/next/` are unrelated FR-012 requirement tags (decision.py, workflow_*, prompt_builder, bridge `#4867 FR-012`, cores). Review notes done: characterisation docstring (call-site coverage of `run_ref_cls=` is WP05 T020's `FakeRunRef` test; docstring only); `test_bridge_engine.py` docstrings (module line 41 and the terminal-branch test now say `runtime_bridge_retrospective`; out-of-map docstring edit, rationale: they described the retired live-lookup mechanism); `test_bridge_io.py` docstring item 4 now points at the gate and `tests/next/test_runtime_bridge_unit.py` (out-of-map docstring edit, same rationale); `tests/next/test_composition_gate_widening.py::test_builtin_software_dev_short_circuits_without_run_dir` now patches `runtime.next.runtime_bridge_composition._resolve_step_binding` (what `_should_dispatch_via_composition` calls), so `assert_not_called` can fail (out-of-map edit; the old patch of `_resolve_step_agent_profile` was never reached, so the assertion was vacuous). Checked by calling the function on the custom-mission path with the patch: it is invoked. Deferred (spec Out of Scope section, C-001): `src/specify_cli/mission_loader/command.py:204`, `src/specify_cli/post_merge/retrospective_terminus.py:216-221`, and #5817.
  - SC-001: `grep -c "Thin compat delegate" src/runtime/next/runtime_bridge.py` -> 0. `wc -l` bridge: 3575 vs 4082 at main 1458e92e (-507 lines, >= 500). Seam files: composition 654, cores 1073, engine 467, identity 133, io 1580, retrospective 464.
  - T025 (clean tree after commit): `FILES=$(git grep -l runtime_bridge -- 'tests/*.py'); PWHEADLESS=1 .venv/bin/python -m pytest $FILES tests/runtime tests/next tests/specify_cli/next -q -p no:cacheprovider -n auto --dist loadfile` -> 3241 passed, 4 skipped, 0 failed (293.97s). Reconciliation against base 1458e92e (3175 passed / 4 skipped): 3175 + 58 (gate file, new in WP01) + 12 (characterisation file, new in WP01) - 3 (WP02 deleted) - 0 (WP03) - 0 (WP04) - 1 (WP05 deleted) = 3241. Exact match, no unexplained difference. No #5817 failure appeared in this run.
  - `make test-fast` -> 2280 passed, 8 skipped, 0 failed (exit 0). Architectural gates `tests/architectural/test_no_dead_symbols.py test_layer_rules.py test_bridge_cores_import_boundary.py test_runtime_emitter_seam.py test_no_legacy_terminology.py` -> 247 passed. Gate + characterisation -> 70 passed. All 7 seams import standalone. `ruff check src/runtime/next` + changed tests clean; `ruff format --check --force-exclude` clean; `ruff check --select C901 src/runtime/next` clean; `mypy src/runtime/next | tail -1` -> 21 errors in 3 files (= baseline, none in changed lines).
  - T026 false-green sweep (throwaway script in the scratchpad, `false_green_sweep.py`, not in the repo): scanned 122 test files that mention `runtime_bridge`; 243 patch targets on the bridge (string `"runtime.next.runtime_bridge.<X>"` targets and `setattr`/`patch.object` on a bridge alias) checked with `hasattr(runtime_bridge, X)`: 0 leftovers; `create=True` / `raising=False` on the bridge: 0.
- 2026-10-06 rework cycle 1 (claude): addressed review-feedback-1. Fixed stale mechanism prose in `runtime_bridge_composition.py` (`_resolve_step_binding`, `_composition_dispatch_inputs`, `_has_generated_docs` docstrings now state seam ownership / the real call path). Wider sweep (`git grep -niE "residual|re-export|delegate|compat|live lookup|WP02 compat|sentinel|REACH" src/runtime/next`, every hit judged): two further stale hits fixed, both OUT of WP06's owned_files, rationale: they described the retired guard-delegate / WP02 compat-reach mechanism and are false now: `runtime_bridge_io.py` `GuardSnapshot` docstring (`wp_advance_ready` is set by `_check_cli_guards` / `_check_composed_action_guard` from the bridge-owned `_should_advance_wp_step`) and `runtime_bridge_cores.py` ~478-483 (same sentence on the cores-side snapshot protocol). Kept deliberately: `runtime_bridge_identity.py:8` history line (WP02 compat guard as past golden coverage), "residual" meaning the bridge module itself, `_internal_runtime`/`run_index`/`decision`/`schema` "delegates"/"backward-compat" prose (unrelated mechanisms), and the `runtime_bridge_engine.py` "delegates via a live module-attribute lookup" note (describes the still-current wrapper behaviour). Gate cleanup: removed `_PENDING_SEAMS`, `_MIGRATING_WP`, `_GREEN_TODAY`, the xfail branches and `_row`/`_named_row` from `tests/runtime/test_bridge_no_compat_delegates.py`; module docstring now describes a permanent guard; parametrisation ids unchanged, still 58 tests. Verification (no behaviour change, full surface not re-run): gate+characterisation+test_bridge_composition+test_bridge_io+test_composition_gate_widening -> 193 passed; gate alone 58 passed; five architectural gates -> 247 passed; ruff check, ruff format --check --force-exclude, C901 clean; mypy 21 errors (= baseline). `git grep -nE "compat guard|compat reach|residual delegate|native delegate" src/runtime/next` -> only the identity header history line.
- 2026-10-06T14:54:56Z – claude (orchestrator, rework cycle 2) – Fixed review-feedback-2: runtime_bridge_cores.py module docstring no longer claims all three guards are reachable on runtime_bridge; _check_composed_action_guard is composition-owned. ruff/format clean; gate + test_bridge_cores + cores import boundary green.
