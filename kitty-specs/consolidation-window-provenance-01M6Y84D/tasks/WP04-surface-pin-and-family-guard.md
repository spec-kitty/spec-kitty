---
work_package_id: WP04
title: Import-surface pin, RECONCILIATION_FAMILY helper and patch-lookup guard
dependencies: []
requirement_refs:
- FR-018
- FR-020
- C-005
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
- T023
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/consolidation/
create_intent:
- tests/consolidation/reconciliation_surface.json
- tests/consolidation/test_reconciliation_surface_pin.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_family_guard.py
execution_mode: code_change
model: glm-5.3
owned_files:
- tests/consolidation/reconciliation_surface.json
- tests/consolidation/test_reconciliation_surface_pin.py
- tests/consolidation/reconciliation_family.py
- tests/consolidation/test_reconciliation_family_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Import-surface pin, RECONCILIATION_FAMILY helper and patch-lookup guard

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP04 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

You write **four test-side files** and **change no production code**. They protect a later refactor that splits `src/specify_cli/consolidation/reconciliation.py` (4,096 lines) into several modules behind a re-exporting facade.

| File | What it does |
|---|---|
| `tests/consolidation/reconciliation_surface.json` | Sorted JSON list of every name that `src/` and `tests/` reach on `specify_cli.consolidation.reconciliation`, plus its `__all__`. Generated, never hand-edited. |
| `tests/consolidation/test_reconciliation_surface_pin.py` | Fails if a pinned name stops being importable from the facade, or is not the same object as at its home. Has a control proving a removed name fails. |
| `tests/consolidation/reconciliation_family.py` | `RECONCILIATION_FAMILY` + patch helpers, a copy of the pattern in `tests/consolidation/executor_family.py`. |
| `tests/consolidation/test_reconciliation_family_guard.py` | Fails when a test patches `specify_cli.consolidation.reconciliation*.<name>` and that module does not itself **look up** `<name>`, **or** when any *other* reconciliation module also looks `<name>` up (a narrowed interception set). Has controls proving the guard fails on a stale patch and on a narrowed patch. |

**Expected test names** (use exactly these, the reviewer checks them):

- `test_reconciliation_surface_pin.py`: `test_every_pinned_name_is_importable`, `test_pinned_names_keep_object_identity`, `test_scanned_surface_is_pinned`, `test_removed_name_fails_the_pin`.
- `test_reconciliation_family_guard.py`: `test_patched_reconciliation_names_are_looked_up`, `test_stale_patch_fails_the_guard`, `test_narrowed_patch_fails_the_guard`, `test_facade_forward_reference_counts_as_a_facade_lookup`, `test_forward_reference_precedence_and_alias`, `test_family_helper_patches_every_binding_module`, `test_family_helper_patches_consumer_bindings`, `test_family_helper_refuses_unbound_name`.

All twelve must **pass** on the current, unchanged code.

## Context & Constraints

- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-04 and IC-05.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — FR-018, FR-020, C-005.
- `tests/consolidation/executor_family.py` — **read it fully**; your `reconciliation_family.py` mirrors it function by function.
- Facts you can rely on (verified when this prompt was written):
  - `reconciliation.__all__` has 10 names: `ApprovedWpCommitSet`, `MergeOutcomeVerifier`, `TERMINUS_ENTRY_POINTS`, `UnroutedTerminusPathError`, `VerifyResult`, `build_approved_wp_set`, `claim_integrity_refusal`, `detect_legacy_in_flight_state`, `route_terminus`, `write_post_fix_marker`.
  - There are 58 `from specify_cli.consolidation.reconciliation import ...` statements across `src/` and `tests/`, and 11 `src/` modules reference the module.
  - Patch forms used today (your scanner and guard MUST handle all of them):
    - plain string: `monkeypatch.setattr("specify_cli.consolidation.reconciliation.resolve_canceled_wp", fake)` (`tests/consolidation/test_reconciliation.py`).
    - f-string on a module constant: `_RECONCILIATION = "specify_cli.consolidation.reconciliation"` then `monkeypatch.setattr(f"{_RECONCILIATION}.attestation_stamps", ...)` (`tests/consolidation/test_canceled_dependency_attribution.py` line ~53 and ~198).
    - module object: `from specify_cli.consolidation import reconciliation as rec` then `monkeypatch.setattr(rec, "_final_authored_walk", ...)` (`tests/consolidation/test_presence_lane_base.py` ~161) and `monkeypatch.setattr(rec, "commits_in_range", ...)` (`tests/terminus/test_resume_refuses_committed_staged_deletions.py` ~209).
    - `mock.patch("...")` and `mock.patch.object(module, "name")` (handle them even if no current test uses them).
- Cross-cutting: no production change, ruff + ruff format + mypy clean, no `# noqa` / `# type: ignore`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> Populated by `finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP04 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T018 – Write the surface scanner

- **Purpose**: Generate the name list from code, never by hand (IC-04 risk).
- **Steps**:
  1. In `tests/consolidation/test_reconciliation_surface_pin.py`, write `scan_reconciliation_surface(repo_root: Path) -> set[str]`. It parses (with `ast`) every `*.py` under `repo_root / "src"` and `repo_root / "tests"`, skipping `src/specify_cli/consolidation/reconciliation*.py` themselves and `__pycache__`.
  2. Collect names from:
     - `ast.ImportFrom` with `module == "specify_cli.consolidation.reconciliation"`: every `alias.name`.
     - aliases bound to the module: `from specify_cli.consolidation import reconciliation` (alias name `reconciliation` or its `asname`, e.g. `rec`), and `import specify_cli.consolidation.reconciliation as X`. Then every `ast.Attribute` whose `value` is `ast.Name(id=<alias>)` contributes `attr`.
     - string constants: any `ast.Constant` string matching `^specify_cli\.consolidation\.reconciliation\.([A-Za-z_][A-Za-z0-9_]*)$` contributes group 1.
     - f-strings: an `ast.JoinedStr` whose first part is a `FormattedValue` of `ast.Name(id=C)` where module-level `C = "specify_cli.consolidation.reconciliation"`, followed by a constant `".<name>"`, contributes `<name>`.
     - `setattr`/`monkeypatch.setattr`/`mock.patch.object` calls whose first argument is a module alias (see above) and whose second argument is a string constant: contribute that string.
  3. Return the set. Keep each helper function small (complexity <= 15; split into `_names_from_import`, `_names_from_attributes`, `_names_from_strings`, ...).
- **Files**: `tests/consolidation/test_reconciliation_surface_pin.py`.

### Subtask T019 – Generate `reconciliation_surface.json`

- **Steps**:
  1. Add a regeneration path: when the environment variable `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE=1` is set, `test_scanned_surface_is_pinned` writes `sorted(scan | set(reconciliation.__all__))` to `tests/consolidation/reconciliation_surface.json` (`json.dumps(names, indent=2) + "\n"`) and passes.
  2. Run it once:
     ```bash
     SPEC_KITTY_REGEN_RECONCILIATION_SURFACE=1 uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py::test_scanned_surface_is_pinned
     ```
  3. Open the JSON and confirm it contains at least the 10 `__all__` names and the patched names `resolve_canceled_wp`, `merge_tree_write_tree_available`, `attestation_stamps`, `OVERRIDABLE_REASONS`, `canceled_spine_content`, `path_state_at`, `_final_authored_walk`, `commits_in_range`. Paste the total count into the WP history note.
- **Files**: `tests/consolidation/reconciliation_surface.json`.

### Subtask T020 – Surface pin tests and the removed-name control

- **Steps**:
  1. `test_every_pinned_name_is_importable`: load the JSON; for each name assert `hasattr(reconciliation, name)`; collect all missing names and fail once listing them.
  2. `test_pinned_names_keep_object_identity`: for each name, `obj = getattr(reconciliation, name)`. Identity rule (it must hold before **and** after the split):
     - if `obj` is a function or class (`inspect.isfunction(obj) or inspect.isclass(obj)`): `home = sys.modules[obj.__module__]`; assert `getattr(home, obj.__name__) is obj`.
     - otherwise: for every module in `RECONCILIATION_FAMILY` (import it from `tests.consolidation.reconciliation_family`) whose `vars()` binds `name`, assert `vars(module)[name] is obj`.
  3. `test_scanned_surface_is_pinned`: without the regen variable, assert `scan_reconciliation_surface(repo_root) <= pinned` (subset, **not** equality: later work packages retarget patches to new homes, which shrinks the scan, and that must stay green). On failure, print the unpinned names and the regeneration command.
  4. `test_removed_name_fails_the_pin`: the control. Use `monkeypatch.delattr(reconciliation, "build_approved_wp_set")`, then call the same checking helper that `test_every_pinned_name_is_importable` uses and assert it raises `AssertionError` mentioning `build_approved_wp_set`. Factor the check into `_assert_pinned_names_importable(module, names)` so the control calls the real check.
- **Notes**: `repo_root = Path(__file__).resolve().parents[2]`.

### Subtask T021 – `reconciliation_family.py` [P]

- **Steps**: Copy the structure of `tests/consolidation/executor_family.py` exactly, renaming:
  - `EXECUTOR_FAMILY` -> `RECONCILIATION_FAMILY: tuple[ModuleType, ...] = (reconciliation,)` — today only the facade exists; later work packages append `reconciliation_kernel`, `reconciliation_bound`, ... as they create them. Add a comment saying so.
  - **New, no executor counterpart** (post-tasks squad pedro #1): `RECONCILIATION_CONSUMERS: tuple[ModuleType, ...] = (phase_claim, phase_gate, forecast)` from `specify_cli.consolidation`. These modules sit **outside** the family but bind reconciliation names **by name** at import time (verified: `phase_claim.py:46-51` binds `build_approved_wp_set`, `claim_integrity_refusal`, `detect_legacy_in_flight_state`, `write_post_fix_marker`; `phase_gate.py:29-37` binds `ApprovedWpCommitSet`, `MergeOutcomeVerifier`, `VerifyResult`, `build_approved_wp_set`, `dependency_refs_moved_refusal`, `lane_tips_moved_refusal`, `route_terminus`; `forecast.py:30-36` binds `MergeOutcomeVerifier`, `VerifyStatus`, `_lane_branch_for`, `build_approved_wp_set`, `claim_integrity_refusal`). A patch of the family alone does not reach those bindings. This tuple is the **one explicit list**; a comment says so and says that a new by-name consumer must be added here.
  - `family_modules_binding(name)` -> same body over `RECONCILIATION_FAMILY`, error text `no consolidation reconciliation-family module binds {name!r}`, then **append** every module of `RECONCILIATION_CONSUMERS` whose `vars()` binds `name` **to the same object** as the family binding (`vars(consumer)[name] is vars(family_module)[name]`; a consumer binding a different object is left alone). The refusal still fires when no **family** module binds the name: consumers only extend a family patch, they never stand in for one.
  - `setattr_executor_family` -> `setattr_reconciliation_family(monkeypatch, name, value)`.
  - `patch_executor_family` -> `patch_reconciliation_family(name, new=mock.DEFAULT, **kwargs)`.
  - Module docstring: explain that the split of `reconciliation.py` (Mission consolidation-window-provenance-01M6Y84D) spreads lookups over flat `reconciliation_<unit>.py` modules, and these helpers patch every binding module.
- **Files**: `tests/consolidation/reconciliation_family.py`.
- **Notes**: Say in the module docstring that the guard (T022) covers only `reconciliation*` modules; the by-name consumers are covered by the helper, not by the guard, and a direct string patch on `specify_cli.consolidation.phase_claim.<name>` (as WP02 T007 step 4 uses) is outside the guard's scope.

### Subtask T022 – Patch-lookup guard

- **Purpose**: After a name moves, a patch on the facade replaces the facade's binding but the moved code looks the name up in its new module, so the patch intercepts nothing and the test goes vacuously green (FR-020). The guard makes that a failure.
- **Steps**:
  1. Pure core function in `test_reconciliation_family_guard.py`:
     `unlooked_up_patches(test_sources: Mapping[Path, str], module_sources: Mapping[str, str]) -> list[str]`.
     - `module_sources` maps a dotted module name (`specify_cli.consolidation.reconciliation`, later also `specify_cli.consolidation.reconciliation_kernel` ...) to its source text.
     - For each test source, find patch targets with the same forms as T018 step 2, but for any module whose dotted name starts with `specify_cli.consolidation.reconciliation` (facade or a future `reconciliation_<unit>`), producing `(test_path, line, module, name)`.
     - A module **looks up** `name` when its AST contains an `ast.Name(id=name, ctx=ast.Load())` anywhere inside a function or method body, or an `ast.Attribute` load chain rooted at `name`, **excluding** the module-level `__all__` list and pure re-export import statements.
     - Return one message per patch target whose module does not look the name up: `"{test_path}:{line}: patches {module}.{name}, but {module} never looks {name} up; patch it where it is looked up (see tests/consolidation/reconciliation_family.py)"`.
     - **Also** return one message per patch target where the name is looked up in **any reconciliation module other than the one patched** (orchestrator decision 2026-11-08, issue 8: a single-module patch on a name two modules look up narrows what the patch intercepted before the split, and the test can stay green while the other lookup goes unpatched): `"{test_path}:{line}: patches {module}.{name}, but {name} is also looked up in {others}; patch every binding module with setattr_reconciliation_family (see tests/consolidation/reconciliation_family.py)"`. `{others}` is the sorted, comma-joined list of the other modules.
     - **Forward-reference rule.** A lookup in module M of a name that M binds only through a function-local `from specify_cli.consolidation.reconciliation import <name>` (the Phase 3 `TEMPORARY FORWARD REFERENCE` convention) reads the **facade's** attribute at call time, so it counts as a lookup in the facade, not in M. Without this rule a facade patch on `_final_authored_walk` would be flagged during WP11 to WP14 although it still intercepts every call.
     - **Precedence of the forward-reference rule** (post-tasks squad pedro MEDIUM; apply these exactly, in this order):
       1. **Module-level binding wins.** If M binds `<name>` at module level (a `def`, `class`, assignment or module-level import) **and** also imports it function-locally, every lookup of `<name>` in M counts as a lookup in **M**.
       2. **Alias resolves to the imported name.** A function-local `from specify_cli.consolidation.reconciliation<_unit> import Y as Z`: a load of `Z` in that function counts as a lookup of **`Y`** (not `Z`) in the source module.
       3. **Source module decides.** A function-local import from a reconciliation module R (facade or a `reconciliation_<unit>`) counts as a lookup in **R**, not in M, and not in the facade unless R is the facade.
       4. Function-local imports from any module outside `specify_cli.consolidation.reconciliation*` are ignored by this rule (the name then counts as a lookup in M as usual).
     - Patches made through `setattr_reconciliation_family` / `patch_reconciliation_family` are not string or module-object patches and are not scanned: they patch every binding module by construction.
     - Before the split there is one reconciliation module, so the second rule cannot fire on today's code.
  2. `test_patched_reconciliation_names_are_looked_up`: build `module_sources` from every `src/specify_cli/consolidation/reconciliation*.py` file (dotted name from the file stem), `test_sources` from every `tests/**/*.py`, call the core, assert the result is empty (print all messages).
  3. **If this test fails on today's unchanged code**, an existing patch is already vacuous. Do **not** change production code and do **not** change the existing test. Stop, record each message in the WP history note (`spec-kitty agent tasks add-history WP04 --note "..."`), and ask the orchestrator. Do not weaken the guard to make it pass.
- **Files**: `tests/consolidation/test_reconciliation_family_guard.py`.

### Subtask T023 – Controls

- **Steps**:
  1. `test_stale_patch_fails_the_guard`: call `unlooked_up_patches` with a synthetic module source `{"specify_cli.consolidation.reconciliation": "Y = 2\n\ndef f():\n    return 1\n"}` and a synthetic test source `{Path("t.py"): 'def test(monkeypatch):\n    monkeypatch.setattr("specify_cli.consolidation.reconciliation.Y", 3)\n'}`; assert exactly one message, mentioning `Y`. Add a second case using the f-string constant form and a third using the module-object form (`from specify_cli.consolidation import reconciliation as rec` + `monkeypatch.setattr(rec, "Y", 3)`).
  2. `test_narrowed_patch_fails_the_guard`: two synthetic modules, `{"specify_cli.consolidation.reconciliation": "def f():\n    return Y\n", "specify_cli.consolidation.reconciliation_kernel": "def g():\n    return Y\n"}`, and a test source that string-patches only `specify_cli.consolidation.reconciliation.Y`; assert exactly one message, naming `reconciliation_kernel`. Then patch both modules (two `setattr` lines) and assert no message.
  3. `test_facade_forward_reference_counts_as_a_facade_lookup`: modules `{"specify_cli.consolidation.reconciliation": "def h():\n    return Y\n", "specify_cli.consolidation.reconciliation_kernel": "def g():\n    from specify_cli.consolidation.reconciliation import Y\n    return Y\n"}` and a facade-only patch of `Y`; assert no message. Control: the same kernel source with a **module-level** `from x import Y` instead yields one message.
  3a. `test_forward_reference_precedence_and_alias`: one case per precedence rule of T022:
     - rule 1: kernel source `"Y = 1\n\ndef g():\n    from specify_cli.consolidation.reconciliation import Y\n    return Y\n"` plus facade `"def h():\n    return Y\n"`, facade-only patch of `Y` -> exactly one message naming `reconciliation_kernel` (narrowed patch);
     - rule 2: kernel source `"def g():\n    from specify_cli.consolidation.reconciliation import Y as Z\n    return Z\n"`, facade `"def h():\n    return Y\n"`, facade-only patch of `Y` -> no message; and a facade-only patch of `Z` -> one message (the facade never looks `Z` up);
     - rule 3: kernel source `"def g():\n    from specify_cli.consolidation.reconciliation_bound import Y\n    return Y\n"`, bound `"def b():\n    return Y\n"`, facade `"X = 0\n"`, a patch of only `specify_cli.consolidation.reconciliation_bound.Y` -> no message.
  4. `test_family_helper_patches_every_binding_module`: with a fake module object created by `types.ModuleType("fake")` appended through `monkeypatch.setattr(reconciliation_family, "RECONCILIATION_FAMILY", (reconciliation, fake))`, bind the same name in both, call `setattr_reconciliation_family`, assert both now hold the new value.
  4a. `test_family_helper_patches_consumer_bindings`: on the **real** modules, `setattr_reconciliation_family(monkeypatch, "build_approved_wp_set", sentinel)`; assert `reconciliation.build_approved_wp_set`, `phase_claim.build_approved_wp_set`, `phase_gate.build_approved_wp_set` and `forecast.build_approved_wp_set` are all `sentinel`. Then, with a fake consumer module bound to a **different** object of the same name appended to `RECONCILIATION_CONSUMERS`, assert that consumer is left unchanged.
  5. `test_family_helper_refuses_unbound_name`: `family_modules_binding("definitely_not_bound")` raises `AttributeError`.

## Test Strategy

Tests are the deliverable. Every test must pass on unchanged production code; the controls prove the pins can fail (stale patch, narrowed patch, removed name).

## Definition of Done

Run **exactly** these commands and paste their final summary lines (e.g. `8 passed in 3.21s`) into the WP history note. Do not paraphrase the output; reviewers rerun them.

```bash
uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_presence_lane_base.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py
uv run --frozen ruff check tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen ruff format --check --force-exclude tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
uv run --frozen mypy tests/consolidation/reconciliation_family.py tests/consolidation/test_reconciliation_surface_pin.py tests/consolidation/test_reconciliation_family_guard.py
make test-fast
```

Expected: the first command reports `12 passed` (the twelve named tests; parametrized cases may add more). Every command exits 0.

- [ ] The twelve test names above exist exactly.
- [ ] `reconciliation_surface.json` was produced by the regeneration command, not typed.
- [ ] `git diff --stat` shows only the four owned files (plus tracer appends). No file under `src/` changed.
- [ ] **Tracer files** (canonical writer only, no hand edits of `traces/*.md`, no `add-history` fallback): `spec-kitty agent tracer-append --mission consolidation-window-provenance-01M6Y84D --category design-decisions --actor "implement WP04" --entry "<summary>. <detail>"` for the identity rule you used and the pinned-name count; `--category tooling-friction` for any friction.
- [ ] Never run `make test-full`. Never claim a test passed that you did not run.

## Risks & Mitigations

- **Guard too lax** (treats a definition or `__all__` entry as a lookup): the T023 controls catch it.
- **Scanner misses a patch form**: the T019 step 3 checklist names the patched names that must appear.
- **Equality instead of subset** in `test_scanned_surface_is_pinned`: would break every later retarget; use `<=`.

## Review Guidance

- Reviewer profile: `reviewer-renata` (Claude reviewer for a cheap-tier implementer).
- **Model tier: cheap** (implementer: TokenFactory glm-5.3; reviewer: Claude). Rerun every Definition-of-Done command yourself; do not trust pasted output.
- Verify the identity rule holds for both functions and constants.
- Temporarily add a stale patch to a scratch test locally and confirm the guard fails (then discard it).
- Rerun `SPEC_KITTY_REGEN_RECONCILIATION_SURFACE=1 uv run --frozen pytest -q tests/consolidation/test_reconciliation_surface_pin.py::test_scanned_surface_is_pinned` and confirm `git diff --exit-code tests/consolidation/reconciliation_surface.json` is clean (the file came from the generator, not from typing).
- Check `RECONCILIATION_CONSUMERS` against a fresh `grep -n "from specify_cli.consolidation.reconciliation import" src/specify_cli/consolidation/*.py` outside `reconciliation*.py`: every module that binds a reconciliation name by name and is reached by the corpus is listed.
- **Record** in the review note each spot-check command you ran and its outcome (which test failed on the stale patch), so the check is verifiable afterwards (post-tasks squad R-15).

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP04 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP04 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
