---
work_package_id: WP13
title: Move the canceled pair (mixed lane + canceled dependency)
dependencies:
- WP12
requirement_refs:
- FR-019
- FR-020
- NFR-001
- NFR-008
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T068
- T069
- T070
- T071
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
- src/specify_cli/consolidation/reconciliation_canceled.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_canceled.py
- src/specify_cli/consolidation/reconciliation.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation.py
- tests/consolidation/test_canceled_dependency_attribution.py
- tests/consolidation/test_reconciliation_module_imports.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP13 – Move the canceled pair (mixed lane + canceled dependency)

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
- **Report progress**: `spec-kitty agent tasks add-history WP13 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This is a **pure move** (FR-019). Zero verdicts change. You move the two checks that share one refusal stack, the **mixed-lane resolver** and the **canceled-dependency resolution**, as ONE slice out of `src/specify_cli/consolidation/reconciliation.py` into the new flat module `src/specify_cli/consolidation/reconciliation_canceled.py`, leave re-exports behind in the facade, retarget every test patch that pointed at the moved names, and prove nothing changed.

Success means all of these hold at the end:

1. Every symbol in the manifest below (T068) is defined in `reconciliation_canceled.py` and in **no other module** (no copies).
2. `specify_cli.consolidation.reconciliation` still exposes every name it exposed before (C-005): same object identity, no edit to any `src/` consumer's import line.
3. `tests/consolidation/characterization/verdict_corpus.json` is **byte-identical** (NFR-001): the corpus test passes without the regeneration switch and `git diff --exit-code` on the golden file is clean.
4. The refusal-precedence matrix (FR-017, C-006) and the surface pin and family guard (FR-018, FR-020) pass unchanged.
5. The seeded mutations for the moved checks (`mixed-lane`, `canceled-dependency`) still turn their named corpus cells red (NFR-008): proof that the retargeted interception still reaches the moved code.
6. No new `# noqa`, `# type: ignore`, allowlist entry or registry row (NFR-005); no moved function gets more complex (NFR-004); `rollback.py` stays the only rollback caller (C-009).

**Do not** change any behaviour, rename anything, "fix" anything you notice in a moved body, split or merge functions, reorder statements, or touch `tasks.md`/other work packages' files.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-11 (one module per check; the canceled pair is one slice), IC-12 (patch retargeting), IC-17 (mutations).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-06 (split unit), R-07 (proving a pure move), R-08 (test interception).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-019, FR-020, NFR-001, NFR-004, NFR-005, NFR-008, C-005, C-006, C-009.
- The Phase 1 pins you rely on (all merged before this phase): `tests/consolidation/test_reconciliation_characterization.py` + `characterization/verdict_corpus.json` (WP02), `tests/consolidation/test_refusal_precedence_matrix.py` (WP03), `tests/consolidation/test_reconciliation_surface_pin.py` + `reconciliation_surface.json`, `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_family_guard.py` (WP04), `tests/consolidation/test_reconciliation_seeded_mutations.py` (WP06).
- Earlier Phase 3 work packages (WP10-WP12, merged) already created `reconciliation_kernel.py`, `reconciliation_claim_types.py`, `reconciliation_rendering.py`, `reconciliation_closed_world.py`, `reconciliation_bound.py` and `reconciliation_verifier.py`. **Look at them first** (`ls src/specify_cli/consolidation/reconciliation_*.py`): they define the re-export style, the `__all__` style and the import style you must copy, and they now own the helpers this slice imports.
- **Line numbers in this prompt are the BASELINE** (the 4,096-line `reconciliation.py` before any Phase 3 move; commit `aa7f5f0794`). They have drifted. Locate every symbol **by name**: `grep -n "^def \|^class " src/specify_cli/consolidation/reconciliation.py`.
- Code today (baseline lines): mixed lane `reconciliation.py:1939-2140`; canceled dependency `:2487-2858`; both rely on the claim's one `_ClaimEventLog` (kernel since WP10).
- Cross-cutting: C-009, C-013 (targeted runs only, never `make test-full`), C-014 (ruff, ruff format, mypy: zero findings), NFR-004, NFR-005, NFR-009.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP13 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T068 – Move the mixed-lane and canceled-dependency symbols to `reconciliation_canceled.py`

- **Purpose**: One module holds the whole canceled stack, so a change to "what happens when a canceled work package's content is on an approved lane" is made in one place (SC-006).
- **Step 0 – baseline and snapshot (do this before editing anything)**:
  1. Run the oracle trio and confirm it is green **before** your change: the corpus, the matrix, the surface pin plus guard (commands in Definition of Done). If any is red on the untouched branch, STOP and report; do not fix it.
  2. Snapshot the facade into a scratch directory **outside the repo** (`SCRATCH=$(mktemp -d)`; `cp src/specify_cli/consolidation/reconciliation.py "$SCRATCH/reconciliation.before-WP13.py"`). You need it for the T071 pure-move proof. Never use `git stash`.
- **Symbol manifest** (move each one **verbatim**, docstring and comments included; sizes come to roughly 530 lines):

  | Group | Symbols (move all) |
  |---|---|
  | Mixed lane | `_mixed_lanes`, `_mixed_lane_recovery`, `_mixed_lane_unattributable_refusal`, `_resolve_mixed_lane_canceled_content`, `_MixedLaneScope`, `_resolve_mixed_lane` |
  | Canceled lanes (shared) | `_fully_canceled_lane_commits`, `_fully_canceled_lane_own_commits` |
  | Canceled dependency | `_CanceledLaneQuery`, `_CanceledDependencyResolution`, `_carrier_spines`, `_carried_unattributable_refusal`, `_unstamped_carried_refusal`, `_unreadable_carrier_refusal`, `_carried_dependency_content`, `_resolve_canceled_dependency_lanes` |
  | Unreadable canceled dependency lane | `_UnreadableCanceledLane`, `_missing_canceled_branch_refusal`, `_unreadable_canceled_dependency_lanes`, `_unreadable_canceled_dependency_clause`, `_unreadable_canceled_dependency_refusal_text` |

- **Shared helpers: where they live (decide by caller count, never by copying)**. Check each with `grep -nw <name> src/specify_cli/consolidation/reconciliation*.py` before you move anything:

  | Symbol | Callers at baseline | Rule |
  |---|---|---|
  | `_join_refusals` | only this slice (`_resolve_mixed_lane_canceled_content`, `_unstamped_carried_refusal`, `_unreadable_carrier_refusal`) | WP11 moved it to `reconciliation_rendering.py` (orchestrator decision, 2026-11-08). **Import it from there; do not move it.** If it is not there, stop and ask. |
  | `_attest_tail` | `_mixed_lane_recovery` (this slice) **and** `_refuse_merged_independent_change` (verifier side, baseline `:812-822`) | Two modules need it, so it sits **below both**: WP11 moved it to `reconciliation_rendering.py` and the verifier (WP12) already imports it from there. **Import it from there; do not move it.** If it is not there, stop and ask. |
  | `_RECOVERY_TAIL` (string constant) | this slice and the rendering/verifier text | Already shared: WP11 moved it to `reconciliation_rendering.py`; import it from there. **Never copy the string.** |
  | `_fully_canceled_lane_commits` | this slice **and** `_presence_scope` (authorship + presence, moves in WP15) | Defined here. WP15's module will import it from `reconciliation_canceled`. Direction is authorship → canceled; `reconciliation_canceled` must never import the authorship module. |
  | `_closed_world_anchors`, `_dependency_lane_ids`, `_lane_is_approved`, `_lane_branch_for`, `_lane_tip_commits`, `_lane_first_parent_spine`, `_is_bookkeeping`, `_ClaimEventLog` | kernel (WP10) | Import from `reconciliation_kernel`. |
  | `CanceledDependencyContent` | claim types (WP10) | Import from `reconciliation_claim_types`. |

- **Steps**:
  1. Create `reconciliation_canceled.py`: module docstring (what the slice is: mixed-lane canceled content resolution #5046 and fully-canceled dependency lane resolution #5569/#5613/#6313, one refusal stack; name that no verdict changed in the move), `from __future__ import annotations`, then imports.
  2. Imports the moved code needs (take exactly these names from where they live today; do not add others): `functools`; `dataclass`; `NamedTuple`; `Callable`, `Mapping`, `Sequence`; `Path`; `Any`; `branch_exists` (`specify_cli.lanes._git`); `is_planning_lane`, `lane_fully_canceled`; `ExecutionLane`, `LanesManifest`; `GitProbeError`, `commits_in_range` (`specify_cli.consolidation.git_probes`); `ATTEST_FLAG`, `ATTEST_REASON_FLAG`, `OVERRIDABLE_REASONS`, `attestation_stamps` (`specify_cli.consolidation.canceled_attestation`); from `specify_cli.consolidation.wp_attribution`: `Attributed`, `AttributionOutcome`, `CanceledPathState`, `Unattributable`, `UnattributableReason`, `canceled_spine_content`, `lacks_lane_head_stamps`, `lane_never_started`, `lane_own_commits`, `resolve_canceled_wp`; plus the kernel, claim-type and rendering names from the table. **Import each collaborator by its own name at module level** (`from ...git_probes import commits_in_range`), because the tests patch a name where it is *looked up* (T070).
  3. Keep function-local imports function-local. `_missing_canceled_branch_refusal` has `from specify_cli.lanes.lane_tip import read_tip` inside its body (baseline `:2769`, with the comment "Lazy import, as phase_teardown does"). It moves **with the function, unchanged**. Do not hoist it.
  4. Declare `__all__` the way `reconciliation_kernel.py` does (follow that file's convention exactly: the names the facade re-exports, sorted).
  5. Delete the moved definitions from `reconciliation.py` only after the new module imports cleanly (`uv run --frozen python -c "import specify_cli.consolidation.reconciliation_canceled"`).
  6. Remove from the facade only the imports that became **unused** (`uv run --frozen ruff check --select F401 src/specify_cli/consolidation/reconciliation.py`). Then run the surface pin. If it names a missing pinned name (the pin includes `attestation_stamps`, `OVERRIDABLE_REASONS`, `canceled_spine_content`, `resolve_canceled_wp`, `commits_in_range`, `path_state_at` and `merge_tree_write_tree_available`), put that import back as an explicit re-export in the style the facade already uses (T069). The pin, not ruff, decides what stays.
- **Files**: `src/specify_cli/consolidation/reconciliation_canceled.py` (new) and `src/specify_cli/consolidation/reconciliation.py`. `reconciliation_rendering.py` is read, not edited: every shared helper this slice needs is already there.
- **Do not**: change any string, f-string, regex, default argument, `sorted(...)` key or `frozenset` literal; add logging; add a helper to shorten a body; alter a `try/except` shape; merge `_fully_canceled_lane_commits` into its `_own_commits` sibling.

### Subtask T069 – Update facade re-exports and the family tuple

- **Purpose**: Old import paths keep working (C-005) and `RECONCILIATION_FAMILY` knows where the moved names are now looked up (FR-020).
- **Steps**:
  1. In `reconciliation.py`, add the re-export block for **every moved name, private ones included**, using the style WP10 established (`grep -n "reconciliation_kernel" src/specify_cli/consolidation/reconciliation.py`). If WP10 used the redundant-alias form, write `from specify_cli.consolidation.reconciliation_canceled import _mixed_lanes as _mixed_lanes`. The alias form is what keeps ruff F401 and mypy `no_implicit_reexport` quiet **without** a suppression. Do not add `# noqa` or `__all__` names (the facade `__all__` stays the same 10 names).
  2. In `tests/consolidation/reconciliation_family.py`, import `reconciliation_canceled` next to the other family modules and append it to `RECONCILIATION_FAMILY`. The facade stays in the tuple, first. Update the comment that lists the modules.
  3. In the WP10 fresh-interpreter smoke test (`grep -rln "reconciliation_kernel" tests/consolidation/ | head`; expected `tests/consolidation/test_reconciliation_module_imports.py`), add `reconciliation_canceled` to its module list.
  4. Run: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py`. The guard is **expected to fail now** on the six patch lines of T070 (the facade no longer looks up the moved names). That is the guard working; do not weaken it.
- **Files**: `reconciliation.py`, `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_module_imports.py`.
- **Check**: `grep -n "^def \|^class " src/specify_cli/consolidation/reconciliation.py` lists none of the manifest names.

### Subtask T070 – Retarget the patches in `test_reconciliation.py` and `test_canceled_dependency_attribution.py`

- **Purpose**: A patch on the facade now replaces a name no code looks up, so the test would still pass while intercepting nothing (FR-020). Retarget each one to where the name is **looked up**.
- **Patch inventory (verified at baseline; re-confirm with the guard output)**:

  | File : line (baseline) | Patched name | Looked up in | New target |
  |---|---|---|---|
  | `tests/consolidation/test_reconciliation.py:2686`, `:2719`, `:2749` | `resolve_canceled_wp` | only `_resolve_mixed_lane` | `"specify_cli.consolidation.reconciliation_canceled.resolve_canceled_wp"` |
  | `tests/consolidation/test_canceled_dependency_attribution.py:198`, `:231`, `:378` | `attestation_stamps` | `_resolve_mixed_lane_canceled_content` **and** `_unstamped_carried_refusal` (both in the new module) | `reconciliation_canceled` |
  | same file `:199` | `OVERRIDABLE_REASONS` | `_resolve_mixed_lane` and `_unstamped_carried_refusal` (both new module) | `reconciliation_canceled` |
  | same file `:377`, `:409` | `canceled_spine_content` | only `_carried_dependency_content` | `reconciliation_canceled` |

  Other patches on the facade (`merge_tree_write_tree_available`, `path_state_at` at `:433` of `test_canceled_dependency_attribution.py`) belong to the verifier and were retargeted by WP12. If the guard still flags one of them, retarget it to `reconciliation_verifier` and say so in the tracer; do not leave it.
- **Steps**:
  1. `test_reconciliation.py`: change the three string targets to the `reconciliation_canceled` dotted path. Keep the surrounding code as it is.
  2. `test_canceled_dependency_attribution.py` builds targets as `f"{_RECONCILIATION}.name"` with `_RECONCILIATION = "specify_cli.consolidation.reconciliation"` (line ~53). Add a second constant next to it, `_CANCELED = "specify_cli.consolidation.reconciliation_canceled"`, and switch exactly the six `f"{_RECONCILIATION}..."` lines in the table to `f"{_CANCELED}..."`. Leave the constants that other tests still use.
  3. If a patched name is looked up in **two** family modules (it is not, for this slice, but check), use `setattr_reconciliation_family` / `patch_reconciliation_family` from `tests/consolidation/reconciliation_family.py` instead of a single string. A single module-string patch must never narrow the old interception set.
  4. **Prove each retargeted patch is live (not vacuous).** Back the test file up with `cp` into your scratch directory. For one patch per distinct name, temporarily make the fake raise `AssertionError("patch reached")` and run just that test: it must go red. Restore the file with `cp`. Never use `git stash` or `git checkout --` for this.
  5. Run the guard and the patch-target validator: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_family_guard.py` and `uv run --frozen python scripts/check_patch_targets.py tests/consolidation/`. Both must be clean.
- **Files**: `tests/consolidation/test_reconciliation.py`, `tests/consolidation/test_canceled_dependency_attribution.py`.
- **Do not** edit any assertion, fixture or test name; do not touch `tests/consolidation/reconciliation_surface.json` (it is shrink-tolerant: the scan may only shrink).

### Subtask T071 – Run the oracle gates and record the module size

- **Steps**:
  1. Run every command in Definition of Done. Paste the final summary lines into the WP history note.
  2. **Pure-move proof (AST equality)**: every moved function/class body must be identical to its baseline body. From the repo root, with `$SCRATCH` from Step 0:

     ```bash
     uv run --frozen python - "$SCRATCH/reconciliation.before-WP13.py" <<'EOF'
     import ast, sys
     def defs(path):
         return {n.name: ast.dump(n) for n in ast.parse(open(path).read()).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
     before = defs(sys.argv[1])
     after = defs("src/specify_cli/consolidation/reconciliation_canceled.py")
     changed = sorted(n for n in after if before.get(n) != after[n])
     print("moved", len(after), "changed", changed)
     sys.exit(1 if changed else 0)
     EOF
     ```
     Expected: `moved 21 changed []` (exactly the 21 manifest symbols; `_join_refusals`, `_attest_tail` and `_RECOVERY_TAIL` were moved by WP11 and are only imported here). A name in `changed` means you edited a body: undo it. Any count other than 21 means a symbol was missed or an extra one came along: stop and ask.
  3. Record `wc -l` of `reconciliation_canceled.py` and of the facade (expected: the new module roughly 560-600 lines, well under 1,200, NFR-003).
  4. Back-reference check (informational at this stage, a hard test in WP15): `grep -n "consolidation.reconciliation import\|consolidation import reconciliation" src/specify_cli/consolidation/reconciliation_*.py`. Any hit is a module importing the facade. List each hit and the name it pulls in the tracer. Your new module must have **none**.
  5. Seeded mutations: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py -k "mixed or canceled"`. Both rows must pass (they assert the cell goes red under the mutation). If a row stops going red, the mutation no longer reaches the moved function: diagnose by lookup site (which module's namespace the fake must replace), fix the **retarget**, not the corpus.
- **Files**: none beyond the above; tracer appends.

## Test Strategy

No new behaviour, so no new tests except the one-line additions to existing modules (family tuple, smoke-test module list). The deliverable is that the **existing oracles stay byte-identical**: the corpus (NFR-001), the precedence matrix (C-006), the surface pin with identity, the guard, and the seeded mutations. Run them first (red/green baseline), after the move, and after the retarget.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
git diff --exit-code -- tests/consolidation/characterization/verdict_corpus.json
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_module_imports.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_canceled_dependency_lane.py tests/consolidation/test_canceled_attestation.py tests/consolidation/test_canceled_content_residuals.py tests/consolidation/test_canceled_content_benchmark.py tests/consolidation/test_canceled_line_attribution_6309.py tests/consolidation/test_merge_canceled_wp.py tests/consolidation/test_rewritten_dependency_attribution.py tests/consolidation/test_dependency_merge_attribution_7307.py
uv run --frozen pytest -q tests/consolidation/ tests/specify_cli/consolidation/
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_modules.py
uv run --frozen python scripts/check_patch_targets.py tests/consolidation/
uv run --frozen ruff check src/specify_cli/consolidation/ tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py
uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation_canceled.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation_canceled.py src/specify_cli/consolidation/reconciliation.py tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py
uv run --frozen mypy src/specify_cli/consolidation/ src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/coordination/coherence.py src/specify_cli/lanes/for_review_gate.py
make test-fast
```

- [ ] Corpus golden file unchanged: the corpus test passed **without** `SPEC_KITTY_REGEN_VERDICT_CORPUS` set, and `git diff --exit-code` on `verdict_corpus.json` is clean. (Never set the regeneration variable in Phase 3.)
- [ ] The AST pure-move proof of T071 step 2 prints `changed []`.
- [ ] Every manifest symbol is defined in `reconciliation_canceled.py` only: `grep -n "^def _mixed_lanes\|^def _resolve_canceled_dependency_lanes" src/specify_cli/consolidation/reconciliation*.py` shows one hit each.
- [ ] No `# noqa`, `# type: ignore` or allowlist/registry edit appears in `git diff`.
- [ ] Module size recorded; `reconciliation_canceled.py` is at most 1,200 lines.
- [ ] **Base-relative zero-diff check** (NFR-001; post-tasks squad R-01): `WP_BASE` is the lane commit this WP started from. Record it in your first history note (`git rev-parse HEAD` before your first commit); the reviewer confirms `git log --oneline "$WP_BASE"..HEAD` lists only this WP's commits. Both must hold on the final commit: `git diff --exit-code "$WP_BASE" HEAD -- tests/consolidation/characterization/verdict_corpus.json` exits 0, and `uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('$WP_BASE'))"` prints `[]`. (A plain `git diff --exit-code` compares only the working tree with the index and misses a committed regeneration.)
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP13" --entry "<summary>. <detail>"` for confirmation that `_attest_tail` / `_join_refusals` / `_RECOVERY_TAIL` were imported from `reconciliation_rendering.py`, not moved; the new module's line count; any facade back-reference found; `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`. Never claim a test passed that you did not run.

## Risks & Mitigations

- **Import cycle through a shared text helper** (`_attest_tail`, `_join_refusals`): decide placement by caller count (T068 table); the fresh-interpreter smoke test fails at import time if you get it wrong.
- **A silently vacuous patch** (still green, intercepts nothing): the family guard plus the T070 step 4 "make the fake raise" proof.
- **Hoisted lazy import** (`read_tip`) changes import-time behaviour: keep it function-local.
- **Facade lost a pinned name**: the surface pin names it; restore it as an explicit re-export.
- **Accidental body edit during cut-and-paste**: the AST equality proof.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (judgment on shared-helper placement; the oracle is the corpus plus the matrix plus the pins).
- Rerun the whole Definition of Done yourself. Re-run the AST proof against `git show <WP12-approved-commit>:src/specify_cli/consolidation/reconciliation.py`.
- Confirm `git diff` on `verdict_corpus.json` is empty and that the regeneration variable was not used.
- For two retargeted patches (one per file), copy the file aside, make the fake raise, confirm red, restore.
- Confirm `reconciliation_canceled.py` does not import the facade or `reconciliation_authorship`, and that no helper text is duplicated across modules.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP13 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP13 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
