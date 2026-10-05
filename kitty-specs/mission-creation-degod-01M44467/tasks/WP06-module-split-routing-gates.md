---
work_package_id: WP06
title: Verbatim module split, routing and gate re-pins
dependencies:
- WP04
- WP05
requirement_refs:
- FR-004
- FR-005
- FR-006
- SC-002
- SC-005
- NFR-001
- NFR-003
- C-003
- C-004
- C-006
- C-007
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
- T030
- T031
- T032
phase: Phase 2 - Decision cores and the split
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- src/specify_cli/core/mission_creation_errors.py
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/_support/mission_creation_source.py
- tests/_support/test_mission_creation_source.py
- tests/core/test_mission_creation_family.py
- docs/api/mission-creation-internals.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_errors.py
- src/specify_cli/core/mission_creation_identity.py
- src/specify_cli/core/mission_creation_roots.py
- src/specify_cli/core/mission_creation_duplicates.py
- src/specify_cli/core/mission_creation_protected_mint.py
- src/specify_cli/core/mission_creation_scaffold.py
- src/specify_cli/core/mission_creation_meta.py
- src/specify_cli/core/mission_creation_events.py
- src/specify_cli/core/mission_creation_commit.py
- src/specify_cli/core/mission_creation_rollback.py
- tests/_support/mission_creation_source.py
- tests/_support/test_mission_creation_source.py
- tests/core/test_mission_creation_family.py
- tests/architectural/test_single_mission_surface_resolver.py
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_mission_resolver_walker_gate.py
- tests/architectural/mission_type_reader_allowlist.yaml
- tests/specify_cli/cli/commands/test_commit_recipes.py
- tests/core/test_adapters.py
- docs/api/mission-creation-internals.md
- docs/changelog/CHANGELOG.md
- docs/development/docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Verbatim module split, routing and gate re-pins

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them. Load the tactics `refactoring-move-method` and `refactoring-extract-class-by-responsibility-split` (`spec-kitty charter context --include tactic:<id>`).

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback.

---

## Objectives & Success Criteria

Move each responsibility of `src/specify_cli/core/mission_creation.py` into its leaf module **verbatim** (C-003). The façade keeps `create_mission_core`, `_create_mission_core_impl`, the logger and an `x as x` re-export of every moved name (C-006). Leaves route patched and cross-family names through the façade module object (C-004, FR-005). Every architectural gate that named the file is re-pinned honestly (FR-006). This follows the PR #5679 pattern; read that PR body first (`spec-kitty` precedent, merged 2026-10-04).

Done means:

- **Exactly-once proof**: every top-level definition on the WP06 lane base's `mission_creation.py` appears exactly once across the family. After undoing `_mc.` routing, each one is AST-identical except for listed deviations. Commit the proof script output in the Activity Log, and the check itself as a test (T029).
- The façade holds only imports, the logger, re-exports, `create_mission_core`, `_create_mission_core_impl` and anything that must stay for patch interception. List what it holds in its module docstring (the module map).
- The golden matrix (WP01/WP02), the WP03 tests, the WP05 decision tests and the full 42-file covering set pass with **0 edits** to any test assertion. The golden files are byte-identical to the lane base.
- The routing check (T030) passes, and its two planted controls fail as expected.
- Every gate in T031 passes, with **0 new allowlist entries** and no baseline bumps.
- `mypy` passes on each module on its own (`follow_imports=skip`), `ruff` is clean, complexity ≤ 15.

## Context & Constraints

- **Target layout**: `plan.md` "Source Code" tree (module → definitions). The final assignment is yours where the plan is ambiguous, with two rules: (1) a constant or class moves **with its reader**, because the dead-symbol gate flags a public name left without a reader; (2) only break the layout to avoid a real import cycle, and record that as a deviation.
- `mission_creation_decisions.py` already exists (WP05). Do not move pure logic again; the leaves import it directly. It is not a leaf that needs routing.
- **Routing rule** (C-004, copied from PR #5679): a leaf calls
  - (1) any function another `mission_creation*` module owns, and
  - (2) any name tests patch on the façade

  through a lazy in-function `from specify_cli.core import mission_creation as _mc`, then `_mc.<name>(...)`. Every other call inside a leaf is direct. **No leaf imports the façade at module scope.** The façade imports leaves at module scope (for the re-exports). Leaves must therefore never import the façade at import time.
- **The patched-name set** comes from WP04: `tests._support.patch_census.patched_names_on("specify_cli.core.mission_creation", Path("tests"))`. That includes names WP03 patches (see its `Patched façade names:` docstring).
- **Logger**: every leaf that logs uses `logging.getLogger("specify_cli.core.mission_creation")` (a literal), so caplog filters keep matching. Leaves that do not log get no logger (the dead-symbol gate).
- **Function-local imports stay function-local** (C-007): they avoid cycles and preserve tracker adapter registration order (`_consume_pending_origin_if_present` imports `specify_cli.core.adapters` lazily). T029 pins them.
- Gate facts come from `research/code-grounding.md` Appendix C (gates lens), §A/§B; a trial move in a scratch clone confirmed them.
- **Rebase first**: `mission_creation.py` changed 6 times in the 4 days before this mission. Before starting, check whether the planning base moved (`git fetch origin main`). If `origin/main` changed `mission_creation.py` since the mission base, **stop and tell the orchestrator**; the orchestrator rebases the mission branch before this WP proceeds.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T026 – Scripted verbatim move + façade re-exports + exactly-once proof

- Write a throwaway script (in `/tmp`, not committed) that uses `ast` + `ast.get_source_segment` to cut each top-level definition, **including its decorators and the comments directly above it**, into its target module.
- Each leaf gets:
  - the `from __future__ import annotations` header;
  - only the imports it uses (start from the façade's import block and prune with `ruff check --select F401 --fix` on that leaf only);
  - a module docstring naming its responsibility and "moved verbatim from mission_creation.py (#5634)".
- The façade gets one import block per leaf, `from specify_cli.core.mission_creation_roots import _CreateRoots as _CreateRoots, _resolve_create_roots as _resolve_create_roots`, and so on, in the `x as x` style so mypy and ruff treat them as re-exports.
- Keep `__all__` consistent if the façade has one (check first).
- The proof: for each name in the base file's top-level definitions, assert it is defined in exactly one family file. Compare `ast.dump(node)` of the base definition with the moved one, after textually stripping `_mc.` prefixes in the moved source. Before comparing, strip both the `_mc.` qualifier **and** the exact lazy-import statement `from specify_cli.core import mission_creation as _mc`, so routing alone never shows up as a deviation. Record the count (expected 46 plus WP05's additions) and the list of non-identical definitions (deviations) with reasons.

### Subtask T027 – Patch-interception routing in leaves

- For every leaf function body that references a routed name (the T030 set) or a cross-family function, rewrite the reference to `_mc.<name>` and add the lazy import at the top of that function.
- Do not route names that are not patched and not cross-family. The check enforces exactly this set (no over-routing in the stale direction).
- The façade's own functions (`create_mission_core`, `_create_mission_core_impl`) resolve names through façade globals, so they need no routing.

### Subtask T028 – Family source helper + self-test

- `tests/_support/mission_creation_source.py`:
  - `MISSION_CREATION_MODULE_PATHS`, derived from disk: `sorted((SRC/"specify_cli/core").glob("mission_creation*.py"))`;
  - `FACADE`;
  - `LEAVES` (family minus façade minus decisions);
  - `family_source()`, the concatenated source with the `_mc.` qualifier stripped (`re.compile(r"\b_mc\.")`).
- `tests/_support/test_mission_creation_source.py`: the module list equals the glob, and `"_mc." not in family_source()`. This mirrors `tests/_support/finalize_source.py` and its test; read both.

### Subtask T029 – Family checks

In `tests/core/test_mission_creation_family.py`, parametrised over `LEAVES` (and decisions where relevant):

1. **Re-export identity**: every top-level def, class or assignment of a leaf is reachable on the façade, and `getattr(facade, n) is getattr(leaf, n)`.
2. **No module-scope façade import** in any leaf, and no façade import of any kind in `mission_creation_decisions.py`.
3. **Logger pin**: any module-level `logger` in a leaf has `.name == "specify_cli.core.mission_creation"`.
4. **Local-import pin** (C-007): the lazy imports of `specify_cli.core.adapters`, `specify_cli.coordination.teardown`, `specify_cli.missions._read_path_resolver`, `specify_cli.status`, `specify_cli.core.git_ops.resolve_primary_branch` and `specify_cli.git.protection_policy` remain function-local wherever they live. Collect the set of function-local imports in the base file with a one-off scan and pin the same set across the family.
5. **Exactly-once**: the T026 proof as a test. It compares against a frozen list of the base file's top-level names, embedded in the test as a tuple literal, with a comment saying where the list came from.
6. **Behavioural intercept tests** (as in #5679): for three representative routed names (`is_worktree_context`, `_commit_feature_file`, `get_current_branch`), patch the name on the façade, call a façade entry that reaches the leaf, and assert the patch fired.

### Subtask T030 – Routing set-equality check + planted controls

- Compute `ROUTED = patched_names_on(façade) ∩ names read by any leaf` (an AST name-load scan of leaves, counting both `Name` loads and `_mc.<attr>` loads). Exclude `subprocess`: patching `mission_creation.subprocess.run` patches the global module and is out of routing scope by design; WP09 removes that patch.
- **Rule A**: inside a leaf function body, a name in `ROUTED` is never a bare `Name` load. It must be `_mc.<name>`.
- **Rule B**: a function another family module defines is never a bare `Name` load in a leaf. It must be `_mc.<name>`, unless it is imported from the decisions module, which is pure and never patched.
- **Rule C (stale)**: every `_mc.<name>` used in a leaf is either in `ROUTED` or defined by another family module. Otherwise it is over-routing, which hides drift.
- **Planted controls**, run in-memory on modified source text:
  1. strip `_mc.` from one routed reference and expect exactly one Rule A violation;
  2. add a synthetic patched name to the patched set that a leaf reads bare and expect a violation.
- Allowlist: **none**.

### Subtask T031 – Re-pin the architectural gates

Each fix is a re-point, never a loosening (see Appendix C of `research/code-grounding.md`):

1. `tests/architectural/test_single_mission_surface_resolver.py` (~:297-322): change the `_scaffold_mission_dir` `ContentDescriptor.rel_path` to the new module, and append "re-pinned (#5634): moved verbatim to <file>" to its rationale. Leave the bite-battery test (~:704) targeting the façade. This descriptor fails at collection time, so fix it first.
2. `tests/architectural/test_no_write_side_rederivation.py`:
   - re-point the `_COORD_WRITER_CENSUS` pair `(…/mission_creation.py, "_emit_create_events")` (~:1381) to `mission_creation_events.py`;
   - add every leaf that holds moved write-side code to `_WRITE_DIR_CONSUMER_MODULES`. Do **not** add to `_PRE_WRITE_DIR_ADOPTED_MODULES`; its derived allowlist count is pinned at 17. Precedent: commit f89218441.
3. `tests/architectural/test_mission_resolver_walker_gate.py` (~:21): `_SCAFFOLD_SNAPSHOT_MODULE` becomes the module that now holds `_list_mission_scaffolds`. Do not add it to `_LEGACY_WALKER_ALLOWLIST`.
4. `tests/specify_cli/cli/commands/test_commit_recipes.py` (~:82-90): the `("core/mission_creation.py", "has no commits yet")` key becomes the module that holds `_resolve_create_roots`. Its sibling test `test_no_unallowed_git_commit_recipe_strings_in_src` is **baseline-red #5705** for an unrelated file; that is expected.
5. `tests/core/test_adapters.py` (~:296-337): read the family via `family_source()` instead of one file.
6. `tests/architectural/mission_type_reader_allowlist.yaml` (~:87-98): re-point `path` if the `"software-dev"` defaults moved, and replace stale line numbers with function names.

Then run the dead-symbol and dead-module gates and fix findings by moving names with their readers. Never add an allowlist entry.

### Subtask T032 – Module map, docs and changelog

- The façade module docstring gets a module map table (module → responsibility → key names) and the routing rule in three lines.
- `docs/api/mission-creation-internals.md` (new): frontmatter `title`, `description`, `doc_status: active`, `updated: '<today>'`, as in `docs/api/finalize-tasks-internals.md`. It contains the module map, the routing rule and "where to add a create-time decision" (decisions module → unit test → adapter). Audience: a maintainer persona.
- `docs/changelog/CHANGELOG.md`: one Internal entry, styled like the neighbouring entries. Check with `uv run --frozen python -m scripts.docs.check_changelog_style`.
- Regenerate the docs index: `uv run --frozen python -m scripts.docs.docs_index --write`, then `uv run --frozen python -m scripts.docs.check_docs_freshness --ci`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/core/test_mission_creation_family.py tests/_support/test_mission_creation_source.py tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
PWHEADLESS=1 .venv/bin/python -m pytest $(grep '^tests/' <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md)) -n 4 --dist loadfile -q
.venv/bin/python -m pytest -p no:cacheprovider \
  tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_single_mission_surface_resolver.py \
  tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_mission_type_reader_invariants.py \
  tests/specify_cli/test_mission_type_write_boundaries.py tests/architectural/test_integration_boundary.py \
  tests/architectural/test_mission_runtime_surface.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_no_dead_symbols.py tests/architectural/test_no_dead_modules.py \
  tests/architectural/test_destructive_op_routing.py tests/architectural/test_egress_consent_boundary.py \
  tests/architectural/test_unregistered_shim_scanner.py tests/architectural/test_ratchet_baselines.py \
  tests/architectural/test_no_legacy_terminology.py \
  tests/specify_cli/cli/commands/test_commit_recipes.py tests/core/test_adapters.py \
  tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py tests/release/test_pinning_inventory_fresh.py -q
git diff <lane-base> -- tests/core/golden tests/core/test_mission_creation_golden_* tests/core/_mission_create_golden.py tests/specify_cli/cli/commands/agent/golden   # must be empty
for f in src/specify_cli/core/mission_creation*.py; do .venv/bin/mypy "$f" || exit 1; done
uv run --frozen ruff check src/specify_cli/core/ tests/core tests/_support && uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen ruff check --select C901 src/specify_cli/core/mission_creation*.py
make test-fast
```

Baseline reds to classify, not chase: baseline-red #5705, #5706.

## Risks & Mitigations

- **Silent loss of patch interception**: T030, plus the behavioural intercept tests.
- **Collection-time gate failure**: re-pin the surface-resolver descriptor first.
- **Import cycles**: leaves never import the façade at module scope; errors live in `mission_creation_errors.py` so leaves can import them directly.
- **Dead symbols**: move constants with their readers.
- **Rebase churn**: see "Rebase first".

## Review Guidance

- Re-run the exactly-once proof, and read every listed deviation.
- Plant one de-routing yourself and see T030 fail.
- `git diff <base> --stat -- tests/` touches only the owned gate files and the new family tests: no other test file changed.
- Each gate diff is a re-point (path or qualname), never a new entry. Count entries before and after.

## Post-tasks squad folds (binding; they supersede conflicting text above)

1. **Rebase protocol (NFR-001 vs a moving main).** Before T026, `git fetch origin main`. If `origin/main` changed `src/specify_cli/core/mission_creation.py` (or any module it imports) since the mission base, **stop and report** to the orchestrator. The orchestrator then:
   - rebases the mission branch;
   - re-captures the golden files on the rebased, still unsplit code, in a separate commit `test(golden): re-capture on rebased base <sha>`, attaching `git diff <old_base> <new_base> -- src/specify_cli/core/mission_creation.py` to that commit's message;
   - updates `base_commit`.

   No WP edits golden files by any other route.
2. **Routing check hardening (T030)**:
   - (a) Resolve every `ImportFrom` in a leaf by its **original** name. A leaf that imports a ROUTED name under any alias fails.
   - (b) Scan the **whole leaf module**, not only function bodies: module-scope assignments, default arguments, class bodies and dict or tuple literals that reference a ROUTED name fail Rule A.
   - (c) The façade alias is exactly `_mc`, imported only as `from specify_cli.core import mission_creation as _mc` inside a function. Any other alias, `import specify_cli.core.mission_creation`, `importlib.import_module(...)` or `getattr(<façade>, "...")` in a leaf fails.
   - (d) The WP04 census `unresolved` count for family-targeting sites is 0.
   - (e) Add a planted control for (a) and for (b).
3. **Frozen façade attribute list (C-006).** Pin, in `tests/core/test_mission_creation_family.py`, the full set of names importable from the façade on the lane base (`dir(module)` minus dunders, captured once). This includes imported names such as `subprocess`, `ULID`, `get_current_branch`, `is_git_repo`, `locate_project_root`, `is_worktree_context`, `now_utc_iso`, `preflight_commit` and `safe_commit`. Every one must still resolve on the façade. Removals happen only in WP08/WP09, as part of de-routing, and update this list in the same commit with a reason.
4. **Per-gate planted removal (FR-006/SC-005).** For each of the six re-pinned gates, in your worktree, remove the guarded call or pattern from its **new** module, run the gate, see it go red, and revert. Record each as a `git diff` patch block plus the failing test id in the Activity Log.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
