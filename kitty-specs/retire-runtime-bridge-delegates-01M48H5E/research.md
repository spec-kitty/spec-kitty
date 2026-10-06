# Research: Retire the runtime_bridge compat-delegate layer

Sources: grounding Op `01M48EGX6W10155GCSDWJCZAT1` (`GROUNDING.md` on
`origin/spike/runtime-bridge-grounding-2560-2562`), prototype commit `20547b2d` (reference
only), and a fresh read of `main` @ `1458e92e` (no change to `src/runtime` or its tests since
the grounding base `7297d8c0`).

## R1 — Still real, not superseded

- `src/runtime/next/runtime_bridge.py` is 4082 LOC with 37 "Thin compat delegate" docstrings.
- The frozen guard `tests/runtime/test_bridge_compat_surface.py` was deleted by #3285 (`177e06269`);
  nothing pins the delegates except `tests/architectural/test_no_dead_symbols.py`'s façade list.
- #2633 (sub-issue) is the same remainder; its "~14 live production callers" reach only
  `get_or_start_run`, `build_operational_context_for_claim` and names the bridge still owns
  (`query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError`).

## R2 — Delegate inventory

See [data-model.md](data-model.md): 36 delegates, 3 adapters, 1 subclass alias, 2 future re-exports.

## R3 — Back-edge inventory (`_rb.<name>` in the seams, `main` 1458e92e)

| Seam | Delegated names read back (remove) | Bridge-owned names read back (keep) |
|------|------------------------------------|-------------------------------------|
| identity | `_primary_runtime_feature_dir` ×2 (:138, :165) | — |
| retrospective | `_classify_and_emit_failure` ×5, `_build_retrospective_facilitator_callback`, `_classify_exc`, `_remediation_hint` | — |
| engine | `_resolve_retrospective_policy_for_runtime`, `_resolve_mission_id_for_terminus`, `_run_retrospective_learning_capture` ×2 | `_is_wp_iteration_step`, `_map_runtime_decision` |
| composition | `_normalize_action_for_composition` ×3, `_resolve_step_agent_profile`, `_resolve_runtime_contract_for_step`, `_check_composed_action_guard` | `_should_advance_wp_step` (`_has_generated_docs` at :462 is only a docstring mention; composition owns it) |
| io | `_load_feature_runs`, `_resolve_mission_ulid` ×2, `_build_discovery_context` ×4, `_resolve_runtime_template_in_root`, `_build_run_ref` ×2, `_runtime_template_key` ×2, `_mission_key_for_run_ref`, `_resolve_run_dir_for_mission`, `_resolve_step_agent_profile` ×2, `_resolve_tech_stack_for_profile` ×2, `_count_source_documented_events`, `_publication_approved` | `_resolve_runtime_feature_dir`, `_has_raw_dependencies_field`, `_check_requirement_mapping_ready`, `_check_bare_prose_requirements_ready`, `_occurrence_gate_failures` |

Cross-seam replacements: engine → `runtime_bridge_retrospective`; io → `runtime_bridge_identity`
(top-level import is safe, identity has no io import) and io → `runtime_bridge_composition`
(must stay a deferred import: composition imports io).

## R4 — Hazards (become acceptance criteria)

1. **Silent false-green on the kept re-exports.** Patching a deleted name raises
   `AttributeError` (loud). Patching the kept `runtime_bridge.get_or_start_run` stops
   intercepting once the bridge's internal callers use `runtime_bridge_io.get_or_start_run`
   (decision `plan.design.internal-call-style`). The grounding found 9 such tests in
   `test_bridge_decide_next`, `test_runtime_bridge_blocked_paths`, `test_query_mode_unit`,
   `test_runtime_bridge_unit`, `test_next_command_integration`. Each is reviewed by call path.
   The same applies to `runtime_bridge.MissionRunRef` patches once `_build_run_ref` stops
   threading the bridge's binding.
2. **Adapters.** `_load_feature_runs(repo_root)` is not `load_feature_runs(repo_root)`; a naive
   rename in the prototype regressed and only a patch-free test caught it.
   `_parse_requirement_refs_from_tasks_md` injects `grammar=`; `_build_run_ref` threads
   `run_ref_cls`. Each is characterised at its bridge call site before deletion (FR-008).
3. `tests/runtime/test_reassess_under_lock.py` fails on a dirty worktree ("Baseline source is
   dirty"): environmental; run on a clean tree.
4. mypy over `src/runtime/next/` reports 21 errors on `main`; the bar is "add none".

## R4b — Post-tasks adversarial squad (2026-10-06), dispositions

| Id | Finding | Disposition |
|----|---------|-------------|
| B1 | WP02 breaks `tests/architectural/test_runtime_emitter_seam.py` (bare-name AST guard + mutation pair) | Folded into WP02 T007 and owned files |
| B2 | `MissionRunRef` is bound as a default arg in io; patching io's module attribute is vacuous | Folded into WP05 T020 (pass `run_ref_cls=` explicitly) |
| M1 | Hazard 1 is 12 bridge-internal sites (+1 already-dead patch), not 9 | Folded into WP05 T021 with the classified list |
| M2 | `test_bridge_io.py:125` and `_COMPAT_GUARDED_NAMES` pin the opposite contract | Folded into WP05 T020 as mechanism-test deletions |
| M3 | Gate could pass while a delegate survives | Folded into WP01 T001 (Checks D, A′, B′, floor, call style) |
| m1 | No fourth adapter; `_load_feature_runs`/`_build_run_ref` have no bridge-internal callers | Folded into WP05 T018 |
| m2 | Import graph; io→composition must stay deferred | Every WP now imports each seam standalone |
| m3 | Repointing widens interception via `committed_authority` | Folded into WP02 T008 |
| m4 | `_has_generated_docs` is composition-owned | Fixed in data-model, R3, WP04, common rules |
| m5 | No out-of-package caller reaches a deleted name | Recorded; no action |
| m6 | `dead_symbol_allowlist.yaml:1395` note cites the bridge adapter | Folded into WP05 |
| m7, m8 | Characterisation non-vacuous; two grep false positives | Recorded; no action |

## R5 — Alternatives considered

- **Cherry-pick the prototype.** Rejected (C-003): unfinished, a few tests red, surface not re-run.
- **Keep bridge-internal calls to the re-exports as bare names** (so façade patches keep
  intercepting). Rejected: it leaves two patch points for one function and keeps the bridge as a
  lookup authority for io's function, which is the debt this mission removes.
- **Mark as bulk edit with an occurrence map.** Rejected (`plan.design.bulk-edit-classification`).
- **Repoint CLI callers and drop the re-exports.** Rejected: outside the package boundary (C-001).
