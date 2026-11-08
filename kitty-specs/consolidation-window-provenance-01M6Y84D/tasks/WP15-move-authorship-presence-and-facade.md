---
work_package_id: WP15
title: Move authorship + presence and reduce the facade
dependencies:
- WP14
requirement_refs:
- FR-019
- FR-020
- C-007
- NFR-001
- NFR-003
- NFR-008
- SC-006
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T077
- T078
- T079
- T080
- T081
- T082
phase: Phase 3 - Behaviour-preserving split
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation_verifier.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_rendering.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_module_imports.py
- tests/consolidation/test_reconciliation_seeded_mutations.py
- src/specify_cli/consolidation/reconciliation_authorship.py
- tests/consolidation/test_reconciliation_split_shape.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/reconciliation_authorship.py
- src/specify_cli/consolidation/reconciliation.py
- src/specify_cli/consolidation/reconciliation_claim.py
- src/specify_cli/consolidation/reconciliation_verifier.py
- src/specify_cli/consolidation/reconciliation_claim_types.py
- src/specify_cli/consolidation/reconciliation_closed_world.py
- src/specify_cli/consolidation/reconciliation_rendering.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_presence_lane_base.py
- tests/consolidation/test_reconciliation_split_shape.py
- tests/consolidation/test_reconciliation_module_imports.py
- tests/consolidation/test_reconciliation_seeded_mutations.py
- tests/terminus/test_resume_refuses_committed_staged_deletions.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP15 – Move authorship + presence and reduce the facade

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
- **Report progress**: `spec-kitty agent tasks add-history WP15 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This is the **last Phase 3 work package**, still a **pure move** (FR-019). Zero verdicts change. You do four things:

1. Move the **authored-content walk and the approved-content presence check as ONE slice** (C-007) into the new flat module `src/specify_cli/consolidation/reconciliation_authorship.py`. They share one first-parent history walk, `_final_authored_walk`; splitting them into two modules would let a second walk appear unnoticed. It is the most-fixed region of the file, which is why it moves last.
2. Reduce `src/specify_cli/consolidation/reconciliation.py` to **module docstring + re-exports + `__all__`** (NFR-003): zero `def`, zero `class`, no logic.
3. Retarget the two remaining test patches (`_final_authored_walk`, `commits_in_range`), and pin the single walk with a counting test.
4. Prove Phase 3 changed nothing: the corpus is byte-identical to Phase 1, the matrix and pins pass, every seeded mutation still goes red, every module is within the size limits.

Success means:

- The corpus (`verdict_corpus.json`) has had **no commit and no diff** in Phase 3 (NFR-001), the precedence matrix passes (C-006), the surface pin and family guard pass (C-005, FR-020).
- `reconciliation.py` has zero top-level `def`/`class`, and every `reconciliation*.py` file is at most **1,200 lines**; the largest is at most 30% of the original 4,096 lines (NFR-003, SC-006).
- Each moved check still has a named red cell under its seeded mutation (NFR-008, SC-005).
- No split module imports the facade, and every split module imports cleanly **alone** in a fresh interpreter.
- No new `# noqa`, `# type: ignore`, allowlist entry or registry row (NFR-005); no moved function got more complex (NFR-004); `rollback.py` stays the only rollback caller (C-009).

**Do not** change any behaviour, split the authorship + presence slice across two modules, add a second `_final_authored_walk` call, "fix" a moved body (the #5048(b) deletion inference at the `except GitProbeError: deletions.add(path)` site is a **Phase 4** change, WP16), or touch other work packages' files.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-11 (authorship + presence one slice, one spine walk; "move last: it is the most-fixed region, and `test_presence_lane_base.py` pins its single walk"), IC-12, IC-17.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-019, FR-020, NFR-001, NFR-003, NFR-004, NFR-005, NFR-008, SC-005, SC-006, C-005, C-006, C-007, C-009.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-06, R-07, R-08.
- Oracles (Phase 1, merged): corpus `tests/consolidation/test_reconciliation_characterization.py` + `characterization/verdict_corpus.json`; matrix `tests/consolidation/test_refusal_precedence_matrix.py`; pins `test_reconciliation_surface_pin.py`, `test_reconciliation_family_guard.py`; mutations `test_reconciliation_seeded_mutations.py`.
- WP10-WP14 are merged: the kernel, claim types, rendering, closed world, bound, verifier, canceled and claim modules exist. **Read their headers first** for the re-export, `__all__` and import conventions you copy. List them: `ls src/specify_cli/consolidation/reconciliation_*.py`.
- **Line numbers are the BASELINE** (4,096-line file at commit `aa7f5f0794`); they have drifted. Locate by name: `grep -n "^def \|^class \|^[A-Za-z_]* *[:=]" src/specify_cli/consolidation/reconciliation.py`.
- Code today (baseline): presence verdict `:3076-3234`; lane content `:3237-3297`; reviewed-merge helpers `:3306-3357`; authored walk and presence scope `:3675-3933`; `_collect_authored` `:3936-4082`.
- Real-git fixture for the single-walk tests: `tests/consolidation/test_presence_lane_base.py` (fixture `repo`: `c0` base, mission branch `m1`, lane-a `a1`, `m2`).
- Cross-cutting: C-009, C-013 (targeted runs only, never `make test-full`), C-014, NFR-004, NFR-005, NFR-009 (checked by CI diff-cover; moved lines are exercised by the corpus, add no exemption).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP15 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T077 – Move the authorship and presence symbols to `reconciliation_authorship.py`

- **Step 0 – baseline, snapshot, and write the single-walk tests FIRST** (before moving anything):
  1. Run the oracle trio (corpus, matrix, surface pin plus guard) on the untouched branch: green, or STOP and report.
  2. Snapshot the facade outside the repo: `SCRATCH=$(mktemp -d)`; `cp src/specify_cli/consolidation/reconciliation.py "$SCRATCH/reconciliation.before-WP15.py"`. Never use `git stash`.
  3. Add the single-walk tests of T079 step 3 to `tests/consolidation/test_presence_lane_base.py` and run them against the **unmoved** code. They must pass now. A pin written after the move proves nothing about the move.
- **Symbol manifest** (move each **verbatim**, docstrings and comments included; about 620 lines):

  | Group | Symbols |
  |---|---|
  | Authored walk (the shared spine walk) | `_final_authored_walk`, `_final_authored_blobs`, `_final_authored_deletions`, `_record_lane_path_contribution`, `_AuthoredClaim`, `_collect_authored` |
  | Presence scope and lane content | `_PresenceScope`, `_presence_scope`, `_presence_range_unreadable_refusal`, `_commits_before`, `_presence_spine`, `_presence_lane_content` |
  | Presence verdict | `_unsuperseded_holders`, `_presence_gap`, `_started_from`, `StateAt`, `_owns_change`, `_dropped_own_change`, `_missing_entries`, `_path_gap`, `unmet_approved_content` |
  | Lane content assembly | `_order_lane_content`, `_dependency_forks`, `_lane_content` |
  | Reviewed-merge helpers used by `_collect_authored` | `_approved_stamps`, `_drop_unreviewed_merges`, `_own_dependency_merges` |

  Keep their relative order in the file (for example `StateAt = Callable[...]` stays after `_started_from`; the annotations rely on `from __future__ import annotations`).
- **Why one module (C-007)**: `_final_authored_walk` is looked up from five places: `_final_authored_blobs`, `_final_authored_deletions`, `_presence_lane_content` and **three** sites inside `_collect_authored` (the full walk, the reviewed-merges walk, the own-base-bounded walk). A test or mutation that replaces that one name must reach every one of them through a single module namespace. Do not leave any of these in another module.
- **Names that must NOT be moved here (import them from where they live)**:

  | Name | Home | Note |
  |---|---|---|
  | `_LaneWalk`, `_lane_is_approved`, `_lane_branch_for`, `_lane_first_parent_spine`, `_APPROVED_MEMBERSHIP_LANES`, `_dependency_lane_ids` | kernel (WP10) | If `_LaneWalk` is still in the facade, move it to `reconciliation_kernel.py` (it is shared with the claim types and the tests). |
  | `ApprovedLaneContent`, `LaneContribution`, `MissingApprovedContent`, `PresenceGap` | claim types | `PresenceGap`, `_GAP_ABSENT` and `_GAP_UNCHANGED` are shared with the claim types and the rendering of `MissingApprovedContent`. If they are still in the facade, move them to `reconciliation_claim_types.py` (the lowest module their callers share), never here. |
  | `_fully_canceled_lane_commits` | `reconciliation_canceled` (WP13) | Import it. Direction is authorship → canceled, never the reverse. |
  | `approval_stamp`, `lane_own_commits`, `lane_dependency_merges`, `first_governed_open_stamp` | `approved_bound` / `wp_attribution` | Import each by its own name at module level so tests can patch where it is looked up. |

- **Steps**:
  1. Create `reconciliation_authorship.py`: docstring (the authorship + presence slice, one spine walk; no verdict changed in the move; name issues #5013, #5022, #5571, #5788, #5968, #7307), `from __future__ import annotations`, imports.
  2. Imports the moved code needs, by their own names: `functools`; `dataclass`, `field`; `NamedTuple`; `Callable`, `Iterable`, `Mapping`, `Sequence`; `Path`; `Any`; `is_planning_lane`; `ExecutionLane`, `LanesManifest`; `GitProbeError`, `blob_id_at`, `changed_paths_of`, `commits_in_range`, `is_merge_commit`, `patch_id_of`, `sha_reachable_from` (`specify_cli.consolidation.git_probes`); `approval_stamp`; `first_governed_open_stamp`, `lane_dependency_merges`, `lane_own_commits`; plus the kernel, claim-type and canceled names from the table above. Add no other imports.
  3. Declare `__all__` per the convention of `reconciliation_kernel.py`.
  4. Delete the moved definitions from the facade after the new module imports (`uv run --frozen python -c "import specify_cli.consolidation.reconciliation_authorship"`).
  5. **Remove every temporary back-reference to the facade** (this is the point where the split becomes acyclic). There are exactly three, each a function-local `from specify_cli.consolidation.reconciliation import ...` under a `# TEMPORARY FORWARD REFERENCE (moves in WP15)` comment (the one convention WP11, WP12 and WP14 share). Delete each comment together with its import:
     - `reconciliation_closed_world.py`: WP11 added one in `_verify_declared_ref` for `_final_authored_walk`. Replace it with a module-level `from specify_cli.consolidation.reconciliation_authorship import _final_authored_walk` (direction closed world → authorship; authorship must not import the closed-world module). After this, a test that patches `_final_authored_walk` must reach `reconciliation_closed_world` through `setattr_reconciliation_family` (T079).
     - `reconciliation_claim.py`: WP14 added ONE function-local `from specify_cli.consolidation.reconciliation import (...)` as the first statement of `build_approved_wp_set`. Delete that statement and import the same names at **module level** from `reconciliation_authorship` (and from wherever any other still-facade-resident name has moved). After your edit, `git diff -- src/specify_cli/consolidation/reconciliation_claim.py` must show only that removed statement and the added module-level import line(s).
     - `reconciliation_verifier.py`: WP12 added one in `_approved_content_divergence` for `unmet_approved_content` (baseline `:1034`, `:1048`). Replace it with a module-level `from specify_cli.consolidation.reconciliation_authorship import unmet_approved_content` (direction verifier → authorship; authorship must not import the verifier). `claim_integrity_refusal` already lives in the verifier module (WP12) and needs nothing.
     - Confirm with `grep -rn "consolidation.reconciliation import\|consolidation import reconciliation\|TEMPORARY FORWARD REFERENCE" src/specify_cli/consolidation/reconciliation_*.py`. **Expected after this step: no hit at all.** The durable guard is `test_split_modules_never_import_the_facade` (T081). If a fourth back-reference exists, stop and ask.
  6. Drop facade imports that became unused (`ruff --select F401`), except pinned names: the surface pin decides, and anything it names stays as an explicit re-export (T078).
- **Files**: `reconciliation_authorship.py` (new), `reconciliation.py`, and `reconciliation_closed_world.py` / `reconciliation_claim.py` / `reconciliation_verifier.py` / `reconciliation_claim_types.py` **only** for the back-reference removal and the shared-constant placement above.
- **Do not**: split the slice; create `reconciliation_presence.py`; change `_final_authored_walk`'s `try/except GitProbeError: deletions.add(path)`; add a second walk; touch the line `if spine == walk.spine and authored == [...]` in `_presence_lane_content` (that equality is the L2 reuse).

### Subtask T078 – Reduce the facade to docstring + re-exports + `__all__`

- **Purpose**: NFR-003: "the reconciliation facade defines no verification logic (re-exports and the module docstring only)".
- **Steps**:
  1. List what is left in the facade:

     ```bash
     uv run --frozen python - <<'EOF'
     import ast
     tree = ast.parse(open("src/specify_cli/consolidation/reconciliation.py").read())
     for node in tree.body:
         if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
             print("DEF   ", node.name, node.lineno)
         elif isinstance(node, (ast.Assign, ast.AnnAssign)):
             targets = node.targets if isinstance(node, ast.Assign) else [node.target]
             print("ASSIGN", [getattr(t, "id", "?") for t in targets], node.lineno)
         elif not isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr)):
             print("OTHER ", type(node).__name__, node.lineno)
     EOF
     ```
  2. Every line it prints other than the single `ASSIGN ['__all__']` is a leftover to place. Likely leftovers: `logger = logging.getLogger(__name__)` (its only user, `_compound_refusal`, moved with its own `logger` in WP14, so just delete the facade's), and any module constant no earlier work package moved (for example `_KITTY_OPS_ROOT_RECORD`; `APPROVED_CONTENT_MISSING` and `CANCELED_REACHABLE_VIA_DEPENDENCY` went to rendering in WP11, the `_REFUSE_DEPENDENCY_*` texts to the closed world in WP11 and the three verifier `_REFUSE_*` texts to the verifier in WP12, so they should not appear). Helper homes are fixed (orchestrator decision, 2026-11-08): `_collect_excluded` and `_refused` belong in `reconciliation_closed_world.py` (WP11); `_attest_tail`, `_RECOVERY_TAIL` and `_join_refusals` in `reconciliation_rendering.py` (WP11); `_collect_approved_shas`, `_unresolvable_approved_lane_branches` and `_refusal_claim` in `reconciliation_claim.py` (WP14). If one of them is still in the facade, this sweep moves it to that home. For each: `grep -nw <name> src/specify_cli/consolidation/reconciliation*.py`, then put it in the **lowest module all its callers may import without a cycle**: one caller module → that module; several → the lowest (kernel for lane/git helpers, claim types for types and status codes, rendering for text). Move **verbatim**; never copy; the facade keeps a re-export of any name the surface pin lists.
  3. Final shape of `reconciliation.py`:
     - the **original module docstring, unchanged**, plus a short closing "Layout" paragraph (at most 15 lines, docs only) naming each `reconciliation_<unit>.py` and what it holds;
     - `from __future__ import annotations`;
     - the re-export imports, grouped by module, in the style WP10 set (redundant-alias form `name as name` if that is what WP10 used; no `# noqa`);
     - `__all__` with the **same 10 names**: `ApprovedWpCommitSet`, `MergeOutcomeVerifier`, `TERMINUS_ENTRY_POINTS`, `UnroutedTerminusPathError`, `VerifyResult`, `build_approved_wp_set`, `claim_integrity_refusal`, `detect_legacy_in_flight_state`, `route_terminus`, `write_post_fix_marker`.
  4. The facade must re-export **every name in `tests/consolidation/reconciliation_surface.json`**, including the third-party names the tests patch through it today (`attestation_stamps`, `OVERRIDABLE_REASONS`, `canceled_spine_content`, `resolve_canceled_wp`, `commits_in_range`, `path_state_at`, `merge_tree_write_tree_available`, …). Run the surface pin after every deletion; the facade keeps the name even though nothing in it looks the name up any more. That is the intended end state (C-005).
  5. The facade must not import `materialize_snapshot` (the census owner is the claim module, WP14) and must hold no function-local import.
  6. Run `uv run --frozen mypy src/specify_cli/consolidation/reconciliation.py` and ruff: both clean with **no suppression**.
- **Files**: `src/specify_cli/consolidation/reconciliation.py`, plus the destination module of any leftover.

### Subtask T079 – Retarget the `_final_authored_walk` and `commits_in_range` patches, and pin the single walk

- **Purpose**: after the move the facade looks nothing up, so a patch on it intercepts nothing (FR-020). Retarget each to where the name is **looked up**, and keep the old interception set.
- **Patch inventory (verified at baseline; re-confirm with the guard output)**:

  | File : line (baseline) | Patched name | Looked up in | New target |
  |---|---|---|---|
  | `tests/consolidation/test_presence_lane_base.py:161` (`monkeypatch.setattr(rec, "_final_authored_walk", _no_second_walk)` in `test_lane_content_reuses_the_authorship_walk_when_the_spines_agree`) | `_final_authored_walk` | `reconciliation_authorship` (five lookup sites) **and** `reconciliation_closed_world` (`_verify_declared_ref`, through the module-level import that replaces WP11's forward reference in T077 step 5) | `setattr_reconciliation_family(monkeypatch, "_final_authored_walk", _no_second_walk)` from `tests.consolidation.reconciliation_family` (before the split the facade patch also reached `_verify_declared_ref` through the forward reference, so a single-module patch would narrow the interception set) |
  | `tests/terminus/test_resume_refuses_committed_staged_deletions.py:209` (`monkeypatch.setattr(rec, "commits_in_range", _unreadable_mission_range)`) | `commits_in_range` | **several** family modules: kernel (`_lane_tip_commits`), canceled (`_unreadable_canceled_dependency_lanes`), closed world, verifier, authorship (`_presence_scope`, `_commits_before`, `_dependency_forks`) | `setattr_reconciliation_family(monkeypatch, "commits_in_range", _unreadable_mission_range)` from `tests.consolidation.reconciliation_family` |

  The second one **must** use the family helper: before the split every one of those lookups saw the fake because they shared one namespace, so a single-module patch would narrow the interception set. The wrapper only fakes the one read where `base == run.pre_target and "-lane-" not in head`; every other read passes through to the real function, exactly as before.
- **Steps**:
  1. Make the two edits above. Remove the now-unused local `rec` import in each patched test only if nothing else in that test uses it (the terminus test imports `rec` locally just for the patch).
  2. Add `reconciliation_authorship` to `RECONCILIATION_FAMILY` in `tests/consolidation/reconciliation_family.py` (facade stays first; the tuple now holds the facade and all nine split modules; update the comment). Add it to the module list of the fresh-interpreter smoke test `tests/consolidation/test_reconciliation_module_imports.py` (`grep -rln "reconciliation_kernel" tests/consolidation/` if the name differs).
  3. **Single-walk tests** (add to `tests/consolidation/test_presence_lane_base.py`; they patch through `setattr_reconciliation_family`, so the same text works before and after the move):
     - `test_collect_authored_walks_each_approved_lane_spine_once`: wrap the real walk in a counter (`real = rec._final_authored_walk`; the wrapper appends its `first_parent_shas` argument to a list and returns `real(repo_root, first_parent_shas)`), patch it with `setattr_reconciliation_family(monkeypatch, "_final_authored_walk", wrapper)`, then call
       `rec._collect_authored(root, _MANIFEST, _APPROVED, str(repo["m1"]), canceled_lane_commits=frozenset(), presence=rec._PresenceScope(base=str(repo["m1"]), carried=frozenset(), lane_bases={}, canceled=frozenset()))`.
       Assert `len(calls) == 1`: the authorship walk is the only walk; the presence content reuses it (L2).
     - `test_second_walk_only_when_the_presence_spine_differs` (the control that proves the counter counts): same call but with `canceled=frozenset({str(repo["a1"])})` in the `_PresenceScope`; assert `len(calls) == 2` (the presence spine drops the canceled commit, so a second walk over `[]` is legitimate).
     - Run both on the **unmoved** code first (Step 0). If a count differs from 1 and 2, your fixture arguments are wrong. Do **not** change production code to make a count match; adjust the arguments, and record what you found in the tracer.
  4. **Prove each retargeted patch is live.** Copy the two test files aside with `cp` into your scratch directory. For each patch, temporarily make the fake raise `AssertionError("patch reached")` and run just that test: it must go red. Restore with `cp`. Never `git stash` / `git checkout --`.
  5. Run the guard and the validator: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_family_guard.py` and `uv run --frozen python scripts/check_patch_targets.py tests/consolidation/ tests/terminus/`. After this step **no test in the repository patches a name on the facade that the facade does not look up** (the facade looks up nothing).
- **Files**: `tests/consolidation/test_presence_lane_base.py`, `tests/terminus/test_resume_refuses_committed_staged_deletions.py`, `tests/consolidation/reconciliation_family.py`, `tests/consolidation/test_reconciliation_module_imports.py`.
- **Do not** edit any other assertion or test name; do not add a retry or sleep; do not touch `reconciliation_surface.json`.

### Subtask T080 – Re-run and, where needed, retarget the seeded mutations; every moved check keeps a red cell

- **Purpose**: NFR-008 / SC-005. A mutation that no longer reaches the moved code would go quietly green and prove nothing.
- **Steps**:
  1. Run the whole file: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py`. Every row passes (each asserts its named cells differ from the golden values), the unmutated control is green, and the coverage test (`test_every_moved_check_has_a_mutation`, all 16 check ids) passes.
  2. If a row went green, the fake no longer replaces the name where the moved code looks it up. Retarget **only through the family helper** (`setattr_reconciliation_family`; for methods, patch the class attribute), or patch the exact caller module that binds the name (`phase_claim`, `forecast`, … bind `build_approved_wp_set` themselves). Never edit the corpus or production code to make a row red. Edit only the failing row's `apply` function.
  3. Add to `tests/consolidation/test_reconciliation_split_shape.py` (T081) a test that ties each mutation row to its real home, so a future move cannot orphan a row:
     `test_every_mutation_target_is_defined_in_exactly_one_split_module`: import `MUTATIONS` from `tests.consolidation.test_reconciliation_seeded_mutations`; for each row take the first dotted segment of `row.target` (`MergeOutcomeVerifier` from `MergeOutcomeVerifier._canceled_content_divergence`), AST-parse every non-facade `src/specify_cli/consolidation/reconciliation*.py` and assert exactly one defines a top-level `def`/`class` of that name. Expected homes (record them in the tracer): `kernel-*` → `reconciliation_kernel`; `closed-world`, `external-dependency-refs` → `reconciliation_closed_world`; `approved-bound`, `write-branch`, `lane-tip-recheck` → `reconciliation_bound`; `mixed-lane`, `canceled-dependency` → `reconciliation_canceled`; `authorship`, `presence` → `reconciliation_authorship`; `verifier-*` → `reconciliation_verifier`; `rendering` → `reconciliation_rendering`; `claim-orchestration` → `reconciliation_claim`.
  4. Re-run the authorship and presence rows on their own: `uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py -k "authorship or presence"`.
- **Files**: `tests/consolidation/test_reconciliation_seeded_mutations.py` (only a failing row's `apply`), `tests/consolidation/test_reconciliation_split_shape.py`.

### Subtask T081 – Verify NFR-003 sizes and that the facade has no logic

- **Steps**: create `tests/consolidation/test_reconciliation_split_shape.py` (new). Plain `ast`, `pathlib` and `subprocess`; fully typed (mypy strict); no suppressions. `repo_root = Path(__file__).resolve().parents[2]`; `modules = sorted((repo_root / "src/specify_cli/consolidation").glob("reconciliation*.py"))`. Tests (use exactly these names):
  - `test_facade_defines_nothing`: every top-level statement of `reconciliation.py` is the docstring `Expr`, an `Import`/`ImportFrom`, or the one `Assign` to `__all__`. No `FunctionDef`, `ClassDef`, `If`, `Try`, other `Assign`/`AnnAssign`.
  - `test_facade_all_is_the_original_ten_names`: `sorted(reconciliation.__all__)` equals the ten names listed in T078.
  - `test_every_reconciliation_module_is_at_most_1200_lines`: `len(path.read_text().splitlines()) <= 1200` for every file in `modules`; the failure message names the file and its length.
  - `test_largest_reconciliation_module_is_at_most_30_percent_of_the_original`: the maximum length is at most `int(0.30 * 4096)`.
  - `test_split_modules_never_import_the_facade`: for every non-facade module, no `ast.ImportFrom` (anywhere in the tree, function-local included) has `module == "specify_cli.consolidation.reconciliation"`, and none imports the name `reconciliation` from `specify_cli.consolidation`.
  - `test_no_top_level_name_is_defined_in_two_split_modules`: collect top-level `def`/`class` names per non-facade module; no name appears twice (no copies of a moved body).
  - `test_every_split_module_imports_alone_in_a_fresh_interpreter`: parametrize over the non-facade modules; run `[sys.executable, "-I", "-c", f"import specify_cli.consolidation.{stem}"]` with `check=True`. An import-order-dependent cycle fails here.
  - `test_every_mutation_target_is_defined_in_exactly_one_split_module` (T080 step 3).
- Record sizes: `wc -l src/specify_cli/consolidation/reconciliation*.py`. Expected ballpark: facade under 120; authorship 650-720; claim 450-520; canceled 560-600; verifier at most about 1,000; **every file at most 1,200** (if one is not, STOP and report: it is a decomposition problem for the planner, not something to fix by editing bodies).
- **Files**: `tests/consolidation/test_reconciliation_split_shape.py` (new).

### Subtask T082 – Run the full Phase 3 verification set

- **Steps**:
  1. Run every command in Definition of Done; paste the final summary lines into the WP history note.
  2. **Zero corpus diff, Phase 3 as a whole**: `git log --oneline -- tests/consolidation/characterization/verdict_corpus.json` shows that its newest commit is from **Phase 1** (WP02, WP05 or WP06; Phase 2 must not commit the golden file either, post-tasks squad R-01), and `changed_cells(<that Phase 1 commit>)` prints `[]`, and `git diff --exit-code -- tests/consolidation/characterization/verdict_corpus.json` is clean. The regeneration variable `SPEC_KITTY_REGEN_VERDICT_CORPUS` was never set.
  3. **Pure-move proof for the new module** (AST equality against the pre-WP15 facade snapshot):

     ```bash
     uv run --frozen python - "$SCRATCH/reconciliation.before-WP15.py" <<'EOF'
     import ast, sys
     def defs(path):
         return {n.name: ast.dump(n) for n in ast.parse(open(path).read()).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
     before = defs(sys.argv[1])
     after = defs("src/specify_cli/consolidation/reconciliation_authorship.py")
     changed = sorted(n for n in after if before.get(n) != after[n])
     print("moved", len(after), "changed", changed)
     sys.exit(1 if changed else 0)
     EOF
     ```
     Expected: `changed []`. (`_PresenceScope` and `_AuthoredClaim` are classes; they count too.)
  4. Record in the tracer: the final line counts of every `reconciliation*.py`, the check → module table of T080, and the list of back-references removed.
- **Files**: none beyond the above; tracer appends.

## Test Strategy

No behaviour change. New tests are limited to (a) the two single-walk tests, written first against the unmoved code and green before and after, and (b) the split-shape file, which turns NFR-003 and "facade has no logic" and "no cycles" into durable gates. Everything else is the existing oracle set, byte-identical: corpus, precedence matrix, surface pin with identity, family guard, seeded mutations.

## Definition of Done

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_characterization.py
git diff --exit-code -- tests/consolidation/characterization/verdict_corpus.json
uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_seeded_mutations.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation_split_shape.py tests/consolidation/test_reconciliation_module_imports.py tests/consolidation/test_presence_lane_base.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_approved_content_presence.py tests/consolidation/test_rewritten_dependency_attribution.py tests/consolidation/test_dependency_merge_attribution_7307.py tests/consolidation/test_reconciliation_divergent.py tests/consolidation/test_merge_divergent_end_to_end.py tests/consolidation/test_forecast_squash_parity.py tests/consolidation/test_approved_bound.py
uv run --frozen pytest -q tests/consolidation/ tests/specify_cli/consolidation/
uv run --frozen pytest -q tests/terminus/test_resume_refuses_committed_staged_deletions.py tests/terminus/test_repro_4997.py tests/terminus/test_repro_4982.py tests/terminus/test_repro_4985.py tests/terminus/test_repro_4991.py tests/terminus/test_repro_5021.py tests/terminus/test_rollback_door.py tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_resume_refreshes_lagging_coord_worktree.py
uv run --frozen pytest -q tests/coordination/test_projection_teardown.py tests/integration/test_merge_resume.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen pytest -q tests/ci/test_reducer_lock_census.py
uv run --frozen pytest -q tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_dead_symbol_allowlist_loader.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_modules.py tests/architectural/test_exemption_registry_ratchet.py tests/architectural/test_cold_import_status_boundary.py
uv run --frozen python scripts/check_patch_targets.py tests/consolidation/ tests/terminus/
wc -l src/specify_cli/consolidation/reconciliation*.py
uv run --frozen ruff check src/specify_cli/consolidation/ tests/consolidation/reconciliation_family.py tests/consolidation/test_presence_lane_base.py tests/consolidation/test_reconciliation_split_shape.py tests/terminus/test_resume_refuses_committed_staged_deletions.py
uv run --frozen ruff check --select C901 src/specify_cli/consolidation/reconciliation_authorship.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/reconciliation.py src/specify_cli/consolidation/reconciliation_authorship.py src/specify_cli/consolidation/reconciliation_claim.py src/specify_cli/consolidation/reconciliation_verifier.py src/specify_cli/consolidation/reconciliation_claim_types.py tests/consolidation/reconciliation_family.py tests/consolidation/test_presence_lane_base.py tests/consolidation/test_reconciliation_split_shape.py tests/terminus/test_resume_refuses_committed_staged_deletions.py
uv run --frozen mypy src/specify_cli/consolidation/ src/specify_cli/orchestrator_api/consolidation.py src/specify_cli/coordination/coherence.py src/specify_cli/lanes/for_review_gate.py tests/consolidation/test_reconciliation_split_shape.py
make test-fast
```

- [ ] Corpus golden file byte-identical to Phase 1: no Phase 3 commit touches it (T082 step 2), `git diff --exit-code` clean, regeneration variable never set.
- [ ] The T082 step 3 AST proof prints `changed []`; `git diff -- src/specify_cli/consolidation/reconciliation_claim.py` shows only the removed temporary back-import and the added module-level import.
- [ ] Facade: zero `def`/`class`, `__all__` unchanged (10 names), `test_facade_defines_nothing` passes.
- [ ] Sizes recorded; every `reconciliation*.py` at most 1,200 lines; the largest at most 1,228 lines (30% of 4,096).
- [ ] The single-walk tests were green **before** the move and are green after it; the control test (count 2) passes.
- [ ] `grep -rn "consolidation.reconciliation import\|consolidation import reconciliation" src/specify_cli/consolidation/reconciliation_*.py` prints nothing.
- [ ] Every seeded mutation row is red under its mutation; the unmutated control is green; each check's real home matches the T080 table.
- [ ] No new `# noqa`, `# type: ignore`, allowlist/registry entry; the dead-symbol allowlist count did not grow (compare `grep -c '^- module:' tests/architectural/dead_symbol_allowlist.yaml` with the WP14 value).
- [ ] **Base-relative zero-diff check** (NFR-001; post-tasks squad R-01): `WP_BASE` is the lane commit this WP started from. Record it in your first history note (`git rev-parse HEAD` before your first commit); the reviewer confirms `git log --oneline "$WP_BASE"..HEAD` lists only this WP's commits. Both must hold on the final commit: `git diff --exit-code "$WP_BASE" HEAD -- tests/consolidation/characterization/verdict_corpus.json` exits 0, and `uv run --frozen python -c "from tests.consolidation.characterization_support import changed_cells; print(changed_cells('$WP_BASE'))"` prints `[]`. (A plain `git diff --exit-code` compares only the working tree with the index and misses a committed regeneration.)
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback; post-tasks squad R-02): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP15" --entry "<summary>. <detail>"` for final module sizes; where each leftover constant landed; the check → module table; the back-references removed; the single-walk counts; and one entry `Phase 3 tip = <sha>` (the lane commit WP15 ends on; WP21 diffs the golden file from it, post-tasks squad R-11); `--category tooling-friction` for any friction. The command works from any checkout (lane worktree included) and commits to the coordination surface itself.
- [ ] Never run `make test-full`. Never claim a test passed that you did not run.

## Risks & Mitigations

- **A second spine walk slips in during the move**: the counting tests (1 call, control 2) written first against unmoved code.
- **A copy of a body left behind in the facade or another module**: `test_no_top_level_name_is_defined_in_two_split_modules` and the AST proof.
- **Import cycle** (claim → authorship → canceled → kernel is the allowed direction; verifier → authorship): `test_split_modules_never_import_the_facade` and the fresh-interpreter test fail on any back-edge.
- **A pinned name dropped when emptying the facade**: the surface pin names it; keep it as an explicit re-export.
- **A silently vacuous patch** (`_final_authored_walk`, `commits_in_range`): the family guard plus the make-the-fake-raise proof of T079 step 4.
- **A module over 1,200 lines**: report it (planner decision), do not trim bodies.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: mid** (judgment on the authorship + presence slice boundary, the leftover placements and the patch retargets; the oracle is the corpus plus the matrix plus the pins plus the shape tests).
- Rerun the whole Definition of Done yourself, including the AST proof against `git show <WP14-approved-commit>:src/specify_cli/consolidation/reconciliation.py`.
- Open the facade: it must read as docstring, imports, `__all__`. Nothing else.
- Check that `_final_authored_walk` has exactly one definition, that its five lookups are in `reconciliation_authorship.py` and that the only other module binding it is `reconciliation_closed_world.py` through a module-level import (`grep -n "_final_authored_walk" src/specify_cli/consolidation/reconciliation*.py`).
- Check that no `TEMPORARY FORWARD REFERENCE` comment and no facade import is left in any split module (three were removed: closed world, verifier, claim).
- For both retargeted patches, copy the file aside, make the fake raise, confirm red, restore.
- Confirm the diff of `verdict_corpus.json` is empty and the regeneration variable was not used.
- Confirm Phase 4 prerequisites are intact: the `_final_authored_walk` `except GitProbeError: deletions.add(path)` site is unchanged (WP16 changes it red-first).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP15 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP15 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
