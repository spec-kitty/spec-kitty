---
work_package_id: WP04
title: Patch census tool
dependencies: []
requirement_refs:
- NFR-004
- FR-005
- FR-007
- C-002
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-creation-degod-01M44467
base_commit: 861c8b74dd9c159c4feaf31f2c70e825e8562f32
created_at: '2026-10-04T20:25:07.951048+00:00'
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 1 - Behaviour freeze
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/patch_census.py
- tests/_support/test_patch_census.py
execution_mode: code_change
model: ''
owned_files:
- tests/_support/patch_census.py
- tests/_support/test_patch_census.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Patch census tool

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback before starting a re-implementation.

---

## Objectives & Success Criteria

Commit a **reporting tool** (not a gate, spec C-002) that measures how tests patch the `mission_creation` module family. The tool gives NFR-004 a reproducible before/after number, and gives WP06's routing check the set of names tests patch on the façade (FR-005).

Done means:

- `tests/_support/patch_census.py` exposes:
  - `scan_static(tests_root: Path, *, family_prefix: str = "specify_cli.core.mission_creation", family_read_names: frozenset[str] | None = None) -> CensusReport`. It counts every static patch site whose target resolves to:
    - (a) any module named by `family_prefix*` (the façade and every future `mission_creation_*` sibling);
    - (b) when `family_read_names` is given, **any** namespace patching one of those names. This catches laundering a patch onto the source module, for example `specify_cli.core.git_ops.get_current_branch`.

    It resolves:
    - string literals and f-strings over module-level string constants (for example `f"{_CORE_MODULE}.is_git_repo"`);
    - `"a" + "b"` concatenations;
    - the object forms `monkeypatch.setattr(mod, "x", …)`, `patch.object(mod, "x")` and `patch.multiple(mod, …)`, where `mod` is bound by `import specify_cli.core.mission_creation as m` or `from specify_cli.core import mission_creation`, including imports inside functions;
    - `monkeypatch.delattr`.

    Unresolvable targets are reported as such, not dropped.
  - `patched_names_on(module: str, tests_root: Path) -> frozenset[str]`: the set of attribute names patched on exactly that module. WP06 uses it for set equality.
  - A runtime counter: an opt-in pytest plugin (`-p tests._support.patch_census`) that counts patch **applications** per test (`monkeypatch.setattr` / `mock.patch` start) against the same target rules, and writes a JSON summary to `$SPEC_KITTY_PATCH_CENSUS_OUT` at session end. This catches a fixture that applies one static patch to 70 tests (post-specify squad finding).
  - A CLI: `python -m tests._support.patch_census --report [--json]`, which prints static totals by target name, by file and by namespace, plus the unresolved count.
- `tests/_support/test_patch_census.py` self-test:
  - **Positive controls**: a synthetic test source (written to `tmp_path`) using each supported form is counted exactly once per site.
  - **Negative control**: a patch on an unrelated module is not counted, unless its name is in `family_read_names`.
  - **Repository control**: on the real `tests/` tree, the static count for the façade is ≥ 270. The grounding count is 277 on `origin/main` 9adc6880. Assert ≥ 270 and **print** the exact number rather than pinning it, because WP01–WP03 add tests in parallel. This is a sanity floor, not a ratchet, so it complies with C-002.
- The baseline report (static and runtime, on the WP04 lane base) is pasted into the Activity Log. The orchestrator copies it into `research/test-remediation.md`.
- The tool is **not** wired into any gate, collection hook or `pytest.ini`. It runs only when invoked.

## Context & Constraints

- Starting point: the grounding scanners preserved at `kitty-specs/mission-creation-degod-01M44467/research/tools/scan_patches2.py.txt` and `count_patches2.py.txt`. They are rough scratch scripts. Rewrite them cleanly, typed and mypy-clean, and keep their resolution rules.
- Prior art for the resolution rules: `tests/specify_cli/cli/commands/agent/test_tasks_patch_targets_live.py` (`_Scanner`, `_attr_chain`, f-string handling). **Read it, do not edit it** (it is owned by a different surface). Reusing its private helpers by import is acceptable only if they are stable module-level functions; otherwise reimplement the rules.
- Per the grounding, the family reads these names. WP06 will compute them for real; for the report, accept them as a parameter:
  - `is_worktree_context`
  - `locate_project_root`
  - `is_git_repo`
  - `get_current_branch`
  - `_commit_feature_file`
  - `ULID`
  - `create_mission_core`
  - `preflight_commit`
  - `safe_commit`
  - `now_utc_iso`
  - `_commit_create_scaffold`
  - `_consume_pending_origin_if_present`
  - `subprocess.run` (attribute chain)
- C-002: no count threshold, no ratchet, no baseline file. A report only.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T014 – Static scanner

- One AST pass per file. Collect module-level string constants. Track import aliases at module and function scope. Visit `Call` nodes whose callee chain ends with:
  - `setattr` or `delattr` (receiver `monkeypatch` or any name: match on the method name and the argument shapes);
  - `patch`;
  - `patch.object`;
  - `patch.multiple`;
  - `mocker.patch` and `mocker.patch.object`, if pytest-mock is in use (grep the repository first).
- For the string form, split the dotted target as module + attribute, preferring the longest prefix that is an importable module path under `specify_cli.`, so that `specify_cli.core.mission_creation.subprocess.run` maps to module `specify_cli.core.mission_creation`, attribute chain `subprocess.run`.
- `CensusReport` is a frozen dataclass: `sites: tuple[PatchSite, ...]` (file, line, module, attr, form) and `unresolved: tuple[...]`, with `by_name()`, `by_file()` and `by_namespace()` helpers.

### Subtask T015 – Runtime counter plugin

- Implement `pytest_configure` (register), `pytest_runtest_setup`/`teardown` hooks or a wrapper around `MonkeyPatch.setattr` and `unittest.mock._patch.__enter__`/`start`.
- Wrap only while the plugin is active (installed at configure, restored at unconfigure), and count only targets that match the family rules.
- Output JSON: `{"applications_total": int, "by_name": {...}, "tests_with_patches": int}`.
- The plugin must not change test outcomes. Prove it by running a small file with and without `-p` and getting identical pass counts.

### Subtask T016 – `patched_names_on()`

- A thin wrapper over `scan_static`, filtered to an exact module, returning attribute names (first segment of the chain, so `subprocess.run` becomes `subprocess`). Document that WP06 uses it.

### Subtask T017 – Self-test and baseline report

- Write the controls described in the objectives.
- Run the baseline:

```bash
.venv/bin/python -m tests._support.patch_census --report
SPEC_KITTY_PATCH_CENSUS_OUT=/tmp/census-runtime.json PWHEADLESS=1 .venv/bin/python -m pytest -p tests._support.patch_census \
  $(cat <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md | grep '^tests/')) -n 4 --dist loadfile -q
```

- Paste both outputs, condensed, into the Activity Log. If xdist workers each write their own file, aggregate them (make the plugin write per-worker files `…<worker>.json` and have `--report` merge them).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/_support/test_patch_census.py -q
uv run --frozen ruff check tests/_support/patch_census.py tests/_support/test_patch_census.py
uv run --frozen ruff format --check --force-exclude tests/_support/patch_census.py tests/_support/test_patch_census.py
.venv/bin/mypy tests/_support/patch_census.py
make test-fast
```

## Risks & Mitigations

- **Over-counting** (patches on unrelated modules) or **under-counting** (aliases, f-strings): the positive and negative controls cover both.
- **Runtime plugin interfering with tests**: install wrappers only when explicitly loaded; restore them exactly; record identical outcomes.
- **Treated as a gate by later readers**: the module docstring states "Reporting tool. Not a gate (C-002). Never add a threshold."

## Review Guidance

- The report on the real tree gives ≈ 277 façade sites, consistent with the grounding. Explain any difference: added WP01–WP03 tests are expected.
- Run the plugin on/off comparison yourself on one file.
- Check that nothing imports the plugin outside opt-in use: `rg -n "patch_census" --glob '!tests/_support/*'`.

## Post-tasks squad folds (binding)

1. **Laundering forms**, each with a positive control:
   - `patch.dict(<module>.__dict__, …)`
   - `monkeypatch.setitem(vars(<module>), …)` / `monkeypatch.setitem(<module>.__dict__, …)`
   - `patch.dict(sys.modules, …)` when it replaces a family module
   - plain attribute assignment `<module_alias>.<name> = …` in test code
   - `importlib.import_module("specify_cli.core.mission_creation…")` aliases
2. **`family_read_names` is derived, not hand-listed.** An AST scan of every `src/specify_cli/core/mission_creation*.py` collects every imported name (module-level and function-local `ImportFrom`/`Import`). The census then counts patches of those names **in their source modules too**, for example `specify_cli.core.git_ops.resolve_primary_branch`, `specify_cli.git.protection_policy.ProtectionPolicy` and `subprocess.run` patched through `git_ops`. Report family-namespace and source-namespace counts separately. Accept an explicit `--files` list for the source-namespace (b) count, so WP09 can measure baseline and final over the same fixed file set. Report stdlib process-global names (`subprocess`, `os`, `shutil`) in their own bucket; they are outside the NFR-004 budget.
3. Report `unresolved` sites that may target the family. WP06 requires this to be 0.
4. Run the runtime counter over the covering set **plus every test file touched by this mission**, and report the collected test count next to the census, so deletions and skips are visible.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
