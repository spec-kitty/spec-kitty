---
work_package_id: WP14
title: Move the claim orchestration
dependencies:
- WP13
requirement_refs:
- FR-019
- C-006
- NFR-005
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T072
- T073
- T074
- T075
- T076
phase: Phase 3 - Behaviour-preserving split
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- src/specify_cli/consolidation/reconciliation_claim.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- tests/ci/test_reducer_lock_census.py
- tests/architectural/dead_symbol_allowlist.yaml
- tests/architectural/_baselines.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – Move the claim orchestration

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP14 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This is a **pure move** (FR-019). Zero verdicts change. You move the claim orchestration, the one function that decides **which refusal a claim gets first**, out of `src/specify_cli/consolidation/reconciliation.py` into the new flat module `src/specify_cli/consolidation/reconciliation_claim.py`:

- `build_approved_wp_set` **as one block** (C-006: the refusal order stays whole, in one place, unchanged);
- the compound-refusal helper `_compound_refusal` (its two text constants `_ALSO_HAS` and `_BOTH_NEEDED` already live in `reconciliation_rendering.py`, moved by WP11; import them);
- the claim-side collectors and refusal builders that only the orchestration calls;
- the terminus vocabulary: `TERMINUS_ENTRY_POINTS`, `UnroutedTerminusPathError`, `route_terminus`, `write_post_fix_marker`, `detect_legacy_in_flight_state`.

Then you update the two literal pins that name the old file (the reducer-lock census owner path and the dead-symbol allowlist keys), with **net 0 new** allowlist entries (NFR-005).

Success means:

1. The refusal order inside `build_approved_wp_set` is byte-for-byte what it was (list in T072). The refusal-precedence matrix (WP03) passes unchanged.
2. The facade `specify_cli.consolidation.reconciliation` still exposes every name it exposed (C-005), with the same object identity. No `src/` consumer (`phase_claim.py`, `forecast.py`, `phase_gate.py`, `claim_inputs.py`, `orchestrator_api/consolidation.py`, `resolve.py`) needs an import edit.
3. `tests/consolidation/characterization/verdict_corpus.json` is byte-identical (NFR-001).
4. `tests/ci/test_reducer_lock_census.py` and `tests/architectural/test_dead_symbol_allowlist_contract.py` pass; the net count of dead-symbol allowlist entries did not grow.
5. The seeded mutations for `claim-orchestration` and `rendering` still turn their named cells red (NFR-008).
6. No new `# noqa`, `# type: ignore`, allowlist entry or registry row (NFR-005). The single existing inline `# noqa: BLE001` inside `build_approved_wp_set` travels with the function (one removed from the facade, one added in the new module: net 0).

**Do not** change any behaviour, split `build_approved_wp_set` into helpers, reorder a statement, rename anything, or "fix" anything you notice in a moved body.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-11 (claim orchestration, refusal order whole), IC-12 (literal-pin housekeeping).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-06, R-07, R-08.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-019, NFR-001, NFR-004, NFR-005, NFR-008, C-005, C-006, C-009.
- Oracles from Phase 1 (merged): corpus (`tests/consolidation/test_reconciliation_characterization.py`), matrix (`tests/consolidation/test_refusal_precedence_matrix.py`), surface pin and family guard (`tests/consolidation/test_reconciliation_surface_pin.py`, `test_reconciliation_family_guard.py`), seeded mutations (`tests/consolidation/test_reconciliation_seeded_mutations.py`).
- WP10-WP13 are merged: `reconciliation_kernel.py`, `reconciliation_claim_types.py`, `reconciliation_rendering.py`, `reconciliation_closed_world.py`, `reconciliation_bound.py`, `reconciliation_verifier.py`, `reconciliation_canceled.py` exist. **Read their headers first** to copy the re-export, `__all__` and import style, and to see where each name this slice calls now lives.
- **Line numbers are the BASELINE** (4,096-line file, commit `aa7f5f0794`); they have drifted. Locate by name: `grep -n "^def \|^class " src/specify_cli/consolidation/reconciliation.py`.
- Gate selection reads the facade: `scripts/ci/gate_selection.py` (`_REDUCER_ENTRY_NAMES = {"materialize", "materialize_snapshot", "reduce"}`, `_REDUCER_MODULE`) marks a file a **reducer reader** when it imports one of those names (a function-local import counts). Today that file is `reconciliation.py` because `build_approved_wp_set` does `from specify_cli.status import materialize_snapshot` inside its body.
- Cross-cutting: C-009, C-013 (targeted runs only, never `make test-full`), C-014, NFR-004, NFR-005, NFR-009.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP14 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T072 – Move the claim orchestration symbols to `reconciliation_claim.py`

- **Step 0 – baseline and snapshot (before editing)**:
  1. Run the oracle trio (corpus, matrix, surface pin plus guard) and confirm green on the untouched branch. If red, STOP and report; do not fix.
  2. Snapshot the facade outside the repo: `SCRATCH=$(mktemp -d)`; `cp src/specify_cli/consolidation/reconciliation.py "$SCRATCH/reconciliation.before-WP14.py"`. Needed for the T076 pure-move proof. Never use `git stash`.
- **Symbol manifest** (move each **verbatim**, docstrings and comments included):

  | Group | Symbols |
  |---|---|
  | Orchestration | `build_approved_wp_set` (baseline `:1655-1872`, ~220 lines, **one contiguous cut**) |
  | Compound refusal | `_compound_refusal` (import `_ALSO_HAS`, `_BOTH_NEEDED` from `reconciliation_rendering`, where WP11 put them) |
  | Claim-side builders called only by the orchestration | `_missing_branch_refusal_text`, `_refusal_claim`, `_unresolvable_approved_lane_branches`, `_collect_approved_shas` |
  | Terminus vocabulary | `TERMINUS_ENTRY_POINTS`, `UnroutedTerminusPathError`, `route_terminus`, `write_post_fix_marker`, `detect_legacy_in_flight_state`, and the `post_fix_marker_path` import they need |

  Before moving a name, `grep -nw <name> src/specify_cli/consolidation/reconciliation*.py`: if an earlier work package already moved it (for example `UnroutedTerminusPathError` sat inside the verifier region), do **not** move it twice. Make sure there is exactly one definition, and import it from where it lives. If `UnroutedTerminusPathError` is somewhere other than the claim module, move it here (it is terminus vocabulary), leave the facade re-export, and note it in the tracer.
- **`claim_integrity_refusal` is not yours to move.** WP12 moved it into `reconciliation_verifier.py` together with `MergeOutcomeVerifier` (orchestrator decision, 2026-11-08: the two call each other, so they share a module and no cycle exists). The facade already re-exports it from there. Do not move it, do not import it into the claim module (`build_approved_wp_set` does not call it), and do not edit `reconciliation_verifier.py`. Direction stays fixed: `reconciliation_claim` may import `reconciliation_verifier`; the verifier never imports the claim module.
- **Refusal order of `build_approved_wp_set` (C-006, do not touch)**: external dependency refs resolved first, then in this order, each returning `_refusal_claim(...)` (or an `ApprovedWpCommitSet(...)` with `surface_resolved=False`) at the first hit: unreadable recorded lane heads → external dependency refusal → snapshot unmaterializable → unresolvable approved lane branches → unreadable canceled dependency lanes → canceled dependency refusal (compound with the bound) → mixed lane refusal (compound with the bound) → approved bound refusal → evidence refusal (`evaluate_evidence`) → presence range unreadable → collectors (`_collect_authored`, `_collect_excluded`) → the final `ApprovedWpCommitSet(...)`. The function body moves **as one block** and keeps that exact statement order and keyword arguments.
- **Steps**:
  1. Create `reconciliation_claim.py`: docstring (the claim orchestration: one place for the refusal order; say that no verdict changed in the move), `from __future__ import annotations`, imports.
  2. Imports: take each collaborator **by its own name at module level** from its current home so tests can patch where it is looked up: from the kernel (`_ClaimEventLog`, `_planning_prefix`, `_lane_is_approved`, `_lane_branch_for`, `_lane_tip_commits`, `_APPROVED_MEMBERSHIP_LANES`, plus any other kernel name the moved bodies use), claim types (`ApprovedWpCommitSet`), bound (`_approved_bound_verdict`, `_bound_claim_base`, `_BoundVerdict`), closed world (`resolve_external_dependency_refs`, `_recorded_lane_heads`, `_collect_excluded`), canceled (`_CanceledLaneQuery`, `_resolve_canceled_dependency_lanes`, `_resolve_mixed_lane_canceled_content`, `_unreadable_canceled_dependency_lanes`, `_unreadable_canceled_dependency_refusal_text`), rendering (`_ALSO_HAS`, `_BOTH_NEEDED`), `evaluate_evidence` (`specify_cli.consolidation.wp_evidence`), `post_fix_marker_path` (`specify_cli.consolidation.workspace`), `branch_exists`, `is_planning_lane`, `lane_fully_canceled`, `LanesManifest`, `GitProbeError`, `functools`, typing names. The **authorship + presence** names the orchestration calls (`_collect_authored`, `_presence_scope`, `_presence_range_unreadable_refusal`) are still defined in the facade until WP15, and the same holds for any other name `grep -n "^def \|^class " src/specify_cli/consolidation/reconciliation.py` still lists that `build_approved_wp_set` calls. (`_collect_excluded` is not one of them: WP11 moved it to `reconciliation_closed_world.py`; import it from there at module level. If it is still in the facade, stop and ask.) A module-level `from specify_cli.consolidation.reconciliation import ...` in the claim module is **circular** (the facade imports the claim module), so use the **function-local** form: ONE `from specify_cli.consolidation.reconciliation import (...)` statement as the first statement after the docstring of `build_approved_wp_set`, preceded by the comment `# TEMPORARY FORWARD REFERENCE (moves in WP15): the authorship + presence names stay in reconciliation.py until WP15.` This is the same convention WP11 and WP12 use (one function-local import from the facade, marked with the work package that removes it). It is the **only** body difference the move may introduce and the only facade back-reference this work package adds; the two earlier ones (WP11's in the closed-world module, WP12's in the verifier module) stay until WP15, which deletes all three, imports from `reconciliation_authorship` at module level and adds a durable test that no split module imports the facade. List the names in the tracer. (Ruff does not enable the import-outside-toplevel rule here; the existing function-local imports in this function carry no suppression either, so this needs none.)
  2b. `_compound_refusal` logs through the module `logger` (`logger.debug("the approved bound could not be evaluated for the compound refusal", exc_info=True)`, baseline `:1899`). Define `logger = logging.getLogger(__name__)` at the top of `reconciliation_claim.py` (add `import logging`). That is the only use of `logger` in the facade, so the facade's own `logger` line becomes dead; leave deleting it to WP15 (T078) unless ruff flags it now. The logger name changes from `…reconciliation` to `…reconciliation_claim`; no test asserts on it (checked with `grep -rn "caplog" tests/consolidation | grep -i reconciliation`).
  3. Keep the two existing function-local imports of `build_approved_wp_set` **function-local**: `from specify_cli.status import materialize_snapshot` and `from specify_cli.lanes.single_branch_landing import authorship_window`. They protect the status cold-import boundary; the census and gate selection read them. Do not hoist.
  4. Keep the inline `except Exception as exc:  # noqa: BLE001 — any unmaterializable surface fails closed` exactly as written.
  5. Declare `__all__` per the convention of `reconciliation_kernel.py`.
  6. Delete the moved definitions from the facade after the new module imports (`uv run --frozen python -c "import specify_cli.consolidation.reconciliation_claim"`); then drop now-unused facade imports (`ruff --select F401`) **except** pinned names: the surface pin decides, restore any it names as explicit re-exports (T073).
- **Files**: `src/specify_cli/consolidation/reconciliation_claim.py` (new) and `reconciliation.py`. `reconciliation_verifier.py` is not edited.
- **Do not**: wrap `build_approved_wp_set` in a helper; move the `ApprovedWpCommitSet(...)` construction; change keyword order; touch `_join_refusals` (WP13's) or `_ClaimEventLog` (kernel).

### Subtask T073 – Update facade re-exports and the family tuple

- **Steps**:
  1. Add a re-export block in the facade for every moved name, private ones included, in the style WP10 set (`grep -n "reconciliation_kernel" src/specify_cli/consolidation/reconciliation.py`; if it is the redundant-alias form: `from specify_cli.consolidation.reconciliation_claim import build_approved_wp_set as build_approved_wp_set`). No `# noqa`; the facade `__all__` keeps its **same 10 names** (`ApprovedWpCommitSet`, `MergeOutcomeVerifier`, `TERMINUS_ENTRY_POINTS`, `UnroutedTerminusPathError`, `VerifyResult`, `build_approved_wp_set`, `claim_integrity_refusal`, `detect_legacy_in_flight_state`, `route_terminus`, `write_post_fix_marker`).
  2. The facade must **not** import `materialize_snapshot` (T074 depends on it). Its re-export of `build_approved_wp_set` is a name from the claim module, nothing else.
  3. Append `reconciliation_claim` to `RECONCILIATION_FAMILY` in `tests/consolidation/reconciliation_family.py` (facade stays first), and add it to the fresh-interpreter smoke test module list (`grep -rln "reconciliation_kernel" tests/consolidation/`; expected `test_reconciliation_module_imports.py`).
  4. Callers keep importing from the facade: `forecast.py`, `phase_claim.py`, `phase_gate.py`, `claim_inputs.py`, `run_state.py`, `orchestrator_api/consolidation.py`, `resolve.py`. **Do not edit any of them** (C-005). `git diff --stat` must show no `src/` file other than the three above.
  5. Run `uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py`. No patch in the test tree points at a name moved by this WP (the earlier retargets covered the others), so both must pass. If the guard flags a patch on a name you moved, retarget it to `reconciliation_claim` (or `setattr_reconciliation_family` when two family modules look it up), prove it live by making the fake raise in a scratch copy, and record it.
- **Files**: `reconciliation.py`, `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_module_imports.py`.

### Subtask T074 – Update the census owner path in `tests/ci/test_reducer_lock_census.py`

- **Why it changes**: the only reducer reader in the consolidation split is the module that now holds `build_approved_wp_set`. `_ClaimEventLog.read` imports `read_events`, which is **not** in `_REDUCER_ENTRY_NAMES`, so the kernel is not an owner.
- **Steps**:
  1. In `test_reducer_readers_route_the_indirect_consumers` (baseline `:103`), change
     `assert "src/specify_cli/consolidation/reconciliation.py" in census.reducer_owners`
     to
     `assert "src/specify_cli/consolidation/reconciliation_claim.py" in census.reducer_owners`.
     Change nothing else in that file. The first assertions in that test (`"consolidation" in via_reducer`) stay as they are.
  2. Run `uv run --frozen pytest -q tests/ci/test_reducer_lock_census.py`. Expected: green. If it is red because the new path is missing from `census.reducer_owners`, the function-local `materialize_snapshot` import did not move with `build_approved_wp_set` (or was hoisted/renamed): fix the move, **not** the test.
  3. Confirm the facade is no longer an owner: `grep -n "materialize_snapshot" src/specify_cli/consolidation/reconciliation.py` returns nothing.
- **Files**: `tests/ci/test_reducer_lock_census.py`.

### Subtask T075 – Re-key or keep in place `TERMINUS_ENTRY_POINTS` / `UnroutedTerminusPathError` in `dead_symbol_allowlist.yaml` (net 0)

- **Background**: `tests/architectural/dead_symbol_allowlist.yaml` has two entries keyed `module: specify_cli.consolidation.reconciliation`, names `TERMINUS_ENTRY_POINTS` and `UnroutedTerminusPathError` (category `category_c_terminus_reconciliation_5001`; baseline `:1174-1183`). The gate keys on the dotted module whose `__all__` declares the name; a caller is any `from <module> import <name>` in `src/`, including a facade re-export (`tests/architectural/test_no_dead_symbols.py`, `_symbol_has_caller`, `_is_reexport_shim_symbol`). The facade can no longer *define* them (NFR-003), so the old keys may go stale or become auto-exempt. **Do not guess: run the gate and read its verdicts.**
- **Steps**:
  1. Count entries before: `grep -c '^- module:' tests/architectural/dead_symbol_allowlist.yaml` (record N).
  2. Run: `uv run --frozen pytest -q tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_ratchet_baselines.py`.
  3. Act on exactly what the failure says, in this order of preference:

     | Gate says | Do |
     |---|---|
     | An allowlist entry is `SUPERSEDED` (the facade re-export of a name whose origin has a real caller is now auto-exempt) | **Delete that entry** (the file shrinks). This is the expected outcome for both names, because the facade's own `from ...reconciliation_claim import ...` is a caller of the origin. |
     | An entry is `GONE` or `INVALID` and the gate prints a "probably moved to" hint, **and** an offender at the new module remains | **Re-key** that entry (change only its `module:` line to `specify_cli.consolidation.reconciliation_claim`; keep category and rationale). Replace, never add. |
     | An offender appears at `reconciliation_claim` for a name | First try to **drop the name from `reconciliation_claim.__all__`** when it is only used inside that module (the gate rescues a non-`__all__` name that its own module uses). Only if that is impossible, re-key as in the previous row. |
     | Shrink-only ratchet warns or fails because the count fell (`test_ratchet_baselines.py`) | Lower the recorded baseline in `tests/architectural/_baselines.yaml` by exactly the number of entries you removed, with a one-line justification comment. A shrink is allowed. |
  4. Count after. The count must be **less than or equal to** N: `git diff -U0 -- tests/architectural/dead_symbol_allowlist.yaml | grep -c '^+- module:'` must not exceed `grep -c '^-- module:'` on the same diff.
  5. Do not add a category, a rationale, a widened (`module::name`) entry or any new `(module, name)` pair.
- **Files**: `tests/architectural/dead_symbol_allowlist.yaml`, and `tests/architectural/_baselines.yaml` only if a ratchet demands the lower number.

### Subtask T076 – Run the oracle gates and the literal-pin gates

- **Steps**:
  1. Run every command in Definition of Done and paste the final summary lines into the WP history note.
  2. **Pure-move proof (AST equality)**, with `$SCRATCH` from Step 0:

     ```bash
     uv run --frozen python - "$SCRATCH/reconciliation.before-WP14.py" <<'EOF'
     import ast, sys
     FACADE = "specify_cli.consolidation.reconciliation"
     def strip_temp(node):
         # the one allowed difference: the temporary function-local facade back-import of T072 step 2
         if isinstance(node, ast.FunctionDef):
             node.body = [s for s in node.body if not (isinstance(s, ast.ImportFrom) and s.module == FACADE)]
         return node
     def defs(path):
         return {n.name: ast.dump(strip_temp(n)) for n in ast.parse(open(path).read()).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
     before = defs(sys.argv[1])
     after = defs("src/specify_cli/consolidation/reconciliation_claim.py")
     changed = sorted(n for n in after if before.get(n) != after[n])
     print("moved", len(after), "changed", changed)
     sys.exit(1 if changed else 0)
     EOF
     ```
     Expected `moved 10 changed []` (the ten functions and classes of the manifest: `build_approved_wp_set`, `_compound_refusal`, `_missing_branch_refusal_text`, `_refusal_claim`, `_unresolvable_approved_lane_branches`, `_collect_approved_shas`, `UnroutedTerminusPathError`, `route_terminus`, `write_post_fix_marker`, `detect_legacy_in_flight_state`; `TERMINUS_ENTRY_POINTS` is an assignment the snippet does not count). A name under `changed` means a body was edited beyond the one allowed back-import: undo it. A different count: stop and ask.
  3. Record `wc -l` of `reconciliation_claim.py` and of the facade in the tracer (new module expected 450-520 lines, under 1,200).
  4. Back-reference check (informational): `grep -n "consolidation.reconciliation import\|consolidation import reconciliation" src/specify_cli/consolidation/reconciliation_*.py`. Expected exactly three hits, each a function-local import marked `TEMPORARY FORWARD REFERENCE (moves in WP15)`: `_final_authored_walk` in `reconciliation_closed_world.py` (WP11), `unmet_approved_content` in `reconciliation_verifier.py` (WP12) and the authorship/presence names in `reconciliation_claim.py` (T072 step 2). List them. Any other hit is a bug.
  5. Seeded mutations: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py -k "claim-orchestration or rendering"`. Both rows must pass. If the `claim-orchestration` row stops going red, the fake must replace `build_approved_wp_set` **where the caller looks it up**: callers such as `phase_claim` bind the name themselves, so diagnose which module namespace the fake reaches and fix the **retarget** in the mutation row's `apply`, never the corpus or production code.
  6. Precedence: `uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py` must pass **and** `test_swapped_order_control` must still pass (its control proves the order assertion can fail).
- **Files**: none beyond the above; tracer appends.

## Test Strategy

No new behaviour, so no new tests beyond one-line additions (family tuple, smoke-test module list, the census path). The deliverable is that the **existing oracles stay byte-identical**: corpus, precedence matrix, surface pin with identity, family guard, seeded mutations, and the two literal-pin gates. Run them before the move (baseline), after the move, and after the pin updates.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
git diff --exit-code -- tests/consolidation/characterization/verdict_corpus.json
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_claim_integrity_refusal.py tests/consolidation/test_dependency_ref_claim.py tests/consolidation/test_lane_evidence_axis.py tests/consolidation/test_approved_bound.py tests/consolidation/test_forecast_squash_parity.py tests/consolidation/test_executor_phase_boundary.py tests/consolidation/test_executor_terminus_integrity.py
uv run --frozen pytest -q tests/consolidation/ tests/specify_cli/consolidation/ tests/integration/test_merge_resume.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q tests/ci/test_reducer_lock_census.py
uv run --frozen pytest -q tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_ratchet_baselines.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_modules.py tests/architectural/test_cold_import_status_boundary.py
uv run --frozen python scripts/check_patch_targets.py tests/consolidation/
uv run --frozen ruff check src/specify_cli/consolidation/ tests/consolidation/reconciliation_family.py tests/ci/test_reducer_lock_census.py
uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation_claim.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_claim.py src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/reconciliation_verifier.py tests/consolidation/reconciliation_family.py tests/ci/test_reducer_lock_census.py
uv run --frozen mypy src/specify_cli/consolidation/ src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/coordination/coherence.py src/specify_cli/lanes/for_review_gate.py
make test-fast
```

- [ ] Corpus golden file unchanged: the corpus test passed **without** `SPEC_KITTY_REGEN_VERDICT_CORPUS`, `git diff --exit-code` on `verdict_corpus.json` is clean.
- [ ] The AST pure-move proof of T076 step 2 prints `changed []`.
- [ ] `build_approved_wp_set` is defined once (`grep -n "^def build_approved_wp_set" src/specify_cli/consolidation/reconciliation*.py` shows one hit, in `reconciliation_claim.py`), and `grep -n "materialize_snapshot" src/specify_cli/consolidation/reconciliation.py` shows none.
- [ ] Allowlist entry count after is `<=` count before (record both numbers); no new `(module, name)` pair, no category, no widened entry.
- [ ] No new `# noqa`, `# type: ignore`; the only `noqa` in the diff is the moved `BLE001` line (one `-`, one `+`).
- [ ] No `src/` file other than `reconciliation.py` and `reconciliation_claim.py` changed.
- [ ] **Tracer files**: dated entries in `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (where `UnroutedTerminusPathError` landed; the allowlist outcome per name; module sizes; the temporary back-reference names WP15 must remove) and `traces/tooling-friction.md` (friction). Format `- **[YYYY-MM-DD][implement WP14] <summary>.** <detail>`. No `kitty-specs/` in your checkout: `spec-kitty agent tasks add-history WP14 --note "..."`.
- [ ] Never run `make test-full`. Never claim a test passed that you did not run.

## Risks & Mitigations

- **Reordering a refusal while moving**: the function moves as one cut; the matrix plus its swapped-order control fail on any reorder.
- **Import cycle verifier ↔ claim**: resolved in WP12 (`claim_integrity_refusal` lives in the verifier module); the claim module may import the verifier, never the reverse. The fresh-interpreter smoke test fails at import time if a cycle appears.
- **Hoisted lazy imports** change import-time behaviour and silently move the census owner: keep `materialize_snapshot` and `authorship_window` function-local.
- **Allowlist growth by accident**: follow the verdict table; the count check in the DoD catches a net increase.
- **Patch vacuity**: the family guard; make a fake raise to prove any patch you retarget is live.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (judgment on the allowlist verdicts and the temporary forward reference; the oracle is the corpus, the matrix and the pins).
- Rerun the whole Definition of Done yourself. Re-run the AST proof against the pre-move facade (`git show <WP13-approved-commit>:src/specify_cli/consolidation/reconciliation.py`).
- Read the moved `build_approved_wp_set` side by side with the baseline: the sequence of `return _refusal_claim(...)` points must be identical.
- Check the allowlist diff by eye: only deletions or one-line `module:` re-keys, no additions.
- Confirm `git diff` on `verdict_corpus.json` is empty and the regeneration variable was not used.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP14 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP14 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
