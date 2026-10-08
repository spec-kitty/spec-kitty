---
work_package_id: "WP02"
title: "Kernel pack paths and read-side cutover"
subtasks: ["T011", "T012", "T013", "T014", "T015"]
dependencies: ["WP01"]
requirement_refs: ["FR-016", "C-007"]
task_type: "implement"
phase: "Phase 1 - Foundations (paths, package split)"
execution_mode: "code_change"
owned_files:
  - "src/kernel/charter_pack_paths.py"
  - "src/kernel/doctrine_root.py"
  - "src/kernel/README.md"
  - "tests/kernel/test_charter_pack_paths.py"
  - "tests/kernel/test_doctrine_root.py"
  - "src/charter/activation/layer_roots.py"
  - "src/specify_cli/cli/commands/charter/_layer_roots.py"
  - "tests/charter/activation/test_layer_roots.py"
  - "src/charter/activation/_drg_helpers.py"
  - "src/charter/activation/_doctrine_paths.py"
  - "src/charter/activation/kind_vocabulary.py"
  - "src/charter/activation/pack_manager.py"
  - "src/charter/activation/mission_type_profile_repository.py"
  - "src/charter/offering/drg/project_scan.py"
  - "src/charter/offering/drg/override_policy.py"
  - "src/charter/offering/service.py"
  - "src/runtime/next/runtime_bridge_composition.py"
  - "src/glossary/entity_pages.py"
  - "src/specify_cli/analysis_inputs.py"
  - "src/specify_cli/calibration/walker.py"
  - "src/specify_cli/charter_runtime/lint/_drg.py"
  - "src/specify_cli/charter_runtime/preflight/runner.py"
  - "src/specify_cli/cli/commands/_doctrine_collect.py"
  - "src/specify_cli/cli/commands/charter/_status_collectors.py"
  - "src/specify_cli/cli/commands/charter/list_cmd.py"
  - "src/specify_cli/cli/commands/profiles_cmd.py"
  - "src/specify_cli/mission_loader/command.py"
  - "src/specify_cli/mission_step_contracts/executor.py"
  - "src/specify_cli/review/gate_bindings.py"
  - "src/specify_cli/skills/catalog.py"
  - "src/specify_cli/tool_surface/providers/agent_profiles.py"
  - "tests/architectural/dead_symbol_allowlist.yaml"
authoritative_surface: "src/kernel/charter_pack_paths.py"
create_intent:
  - "src/kernel/charter_pack_paths.py"
  - "tests/kernel/test_charter_pack_paths.py"
  - "src/charter/activation/layer_roots.py"
  - "tests/charter/activation/test_layer_roots.py"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
history:
  - at: "2026-10-06T19:30:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP02 – Kernel pack paths and read-side cutover

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/kernel/charter_pack_paths.py`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check `review_ref` in the event log (`spec-kitty agent tasks status`) or the Activity Log below.
- Address every feedback item before you finish; log each fix in the Activity Log.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers on code blocks.

## Objectives & Success Criteria

1. `src/kernel/charter_pack_paths.py` is the one module that names the project pack root (`.kittify/charter-packs/`) and the pack-relative paths (`drg/fragment.yaml`, `org-charter.yaml`, `presets/`, `graph.yaml`). `src/kernel/doctrine_root.py` is deleted (C-001: no re-export module left behind).
2. Layer-root resolution lives in `charter` as `charter.activation.layer_roots`; `resolve_layer_roots(repo)["project"]` is the **project pack root**, not `.kittify`.
3. Every READ site of the project layer listed below resolves through the kernel module, with the existing canonical-first, legacy-fallback read (the fallback is removed by WP14, FR-011).
4. Writers are untouched (WP03). Behaviour on a legacy project is unchanged; a migrated project (`.kittify/charter-packs/`) is now read.
5. The WP01 acceptance tests pending on WP02 are green (see Red-first).

## Context & Constraints

- Read: `spec.md` FR-016, C-007, C-008; `plan.md` decision list; `research/package-split-and-paths.md` Part B (B.1 READ table, B.2, B.3 kernel API, layer-root contract change); `research/runtime-seams.md` §3 table row `.kittify/doctrine/ (read fallback)`.
- Layering (`tests/architectural/test_layer_rules.py`): `kernel` imports nothing from `charter`/`specify_cli`; `charter` may import `kernel`; `charter.offering` may not import `charter.activation` (`test_charter_offering_does_not_import_activation.py`).
- **No aliases (C-001)**: no `doctrine_root` re-export, no forwarding `_layer_roots.py` stub, no old-name constant kept "for compatibility". The read fallback is **not** an alias: it is the FR-011 shim that WP14 deletes; keep it in exactly one function.
- **Writers stay on the legacy root in this WP.** WP03 flips them. Between WP02 and WP03 a migrated project is read correctly; a legacy project still reads and writes `.kittify/doctrine/`. Do not run `charter synthesize --apply` on this repository during the mission until WP11 T059 moves the tree.
- Code style: ruff, `ruff format`, mypy clean; complexity ≤ 15; no new suppressions.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- Lane: from `lanes.json` (filled by `spec-kitty agent mission finalize-tasks`).

## Red-first (C-006 / C-011)

Your **first commit** deletes the `pending_until("WP02", …)` markers in `tests/acceptance/charter_pack_cutover/test_project_pack_root.py` (`test_fr016_kernel_module_is_single_authority`, `test_fr016_layer_roots_project_is_pack_root`, `test_fr016_migrated_fixture_project_artifact_is_listed`) and nothing else. Run them; record the red output in the Activity Log. Your implementation commits turn them green. Do not edit the tests' assertions (C-006); if one is wrong, stop and raise it with the orchestrator.

## Mechanical edits outside owned_files (log each in the Activity Log)

Deleting `kernel/doctrine_root.py` and `_layer_roots.py` breaks imports in files other WPs own. Change **only the import line and the renamed symbol** there, keep behaviour identical, and log each file with a one-line rationale:

- `src/charter/activation/synthesizer/write_pipeline.py:40,70` and `src/charter/activation/synthesizer/reconcile.py:47,612`, `src/specify_cli/doctrine_synthesizer/apply.py` (`LEGACY_DOCTRINE_DIRNAME` / `resolve_doctrine_read_root` imports; WP03 then rewrites these sites).
- `_layer_roots` importers: `src/specify_cli/cli/commands/charter/{_cascade_shared,_resynthesis_preflight,activate,deactivate,interview}.py`, `src/specify_cli/doctrine/org_charter.py:386,918` (lazy), and docstring references in `src/charter/activation/pack_manager.py:337,349,422,465`, `src/charter/offering/missions/mission_type_repository.py:383`.
- Tests importing `_layer_roots`: `tests/charter/test_kind_vocabulary_scan_roots.py`, `test_mission_type_path_layout_ssot.py`, `test_pack_manager.py`, `test_pack_manager_catalog.py`; `tests/specify_cli/cli/commands/charter/test_activation_layout.py`, `test_org_cascade_chain.py`.

tasks.md's rule covers edits in files owned by a completed upstream WP; these files belong to WPs that run after this one in the same chain (WP03, WP04/WP05, WP06, WP08), so no lane runs them in parallel. The orchestrator has been told.

## Subtasks & Detailed Guidance

### Subtask T011 – `kernel/charter_pack_paths.py` replaces `kernel/doctrine_root.py`

- **Purpose**: one constant module (C-007) for the project pack root and pack-relative paths (FR-016).
- **Steps**:
  1. Create `src/kernel/charter_pack_paths.py` with the B.3 API (names are binding for later WPs and for WP01's tests):
     ```python
     KITTIFY_DIRNAME = ".kittify"
     PROJECT_PACK_DIRNAME = "charter-packs"
     PROJECT_PACK_ROOT = Path(KITTIFY_DIRNAME, PROJECT_PACK_DIRNAME)
     PROJECT_PACK_ROOT_POSIX = PROJECT_PACK_ROOT.as_posix()
     DRG_DIRNAME = "drg"
     DRG_FRAGMENT = Path(DRG_DIRNAME, "fragment.yaml")
     ORG_CHARTER_FILENAME = "org-charter.yaml"
     PRESETS_DIRNAME = "presets"
     PROJECT_GRAPH_FILENAME = "graph.yaml"
     def project_pack_root(repo_root: Path) -> Path: ...
     def project_pack_path(repo_root: Path, *parts: str) -> Path: ...
     def pack_drg_fragment(pack_root: Path) -> Path: ...
     def pack_org_charter(pack_root: Path) -> Path: ...
     def pack_presets_dir(pack_root: Path) -> Path: ...
     ```
     Root layout is **one flat pack** at `.kittify/charter-packs/` (data-model "Project layer"; B.3 open point settled by the spec).
  2. Move the read fallback into the same module, renamed for the new vocabulary and marked for deletion by WP14 in its docstring: `LEGACY_PROJECT_PACK_DIRNAME = "doctrine"`, `resolve_project_pack_read_root(repo_root, *, quiet=False) -> Path` (the body of `doctrine_root.resolve_doctrine_read_root`, `doctrine_root.py:76-104`, unchanged semantics: canonical if it is a directory, else legacy if it is a directory with a warn-once unless `quiet`, else canonical), and `LegacyDoctrineRootWarning` with its `lru_cache` warn-once gate. Keep the class name: FR-011 names it for deletion, and renaming it now would create a name no requirement tracks.
  3. Export via `__all__`; module docstring states the layer rule ("kernel imports nothing upward") and that the legacy names exist only until FR-011 (WP14).
  4. Delete `src/kernel/doctrine_root.py`. Repoint the three importers (mechanical list above): `LEGACY_DOCTRINE_DIRNAME` → `LEGACY_PROJECT_PACK_DIRNAME`, `resolve_doctrine_read_root` → `resolve_project_pack_read_root`.
  5. `src/kernel/README.md`: add a `kernel.charter_pack_paths` bullet (one line, charter vocabulary).
  6. `tests/architectural/dead_symbol_allowlist.yaml:316-322,1236-1239`: re-key the `kernel.doctrine_root` entries to `kernel.charter_pack_paths` with the new symbol names, or delete an entry whose symbol now has a live caller (the dead-symbol gate tells you which).
- **Files**: `src/kernel/charter_pack_paths.py` (new), `src/kernel/doctrine_root.py` (deleted), `src/kernel/README.md`, `tests/architectural/dead_symbol_allowlist.yaml`.
- **Parallel?**: no; T012–T014 import it.
- **Notes**: the constant module is the FR-016 *authority* that WP03's gate whitelists for clause (b) literals; keep every literal in it. The legacy `"doctrine"` literal also lives only here until WP14.
- **Validation**:
  - [ ] `uv run --frozen python -c "import kernel.doctrine_root"` fails; `import kernel.charter_pack_paths` works.
  - [ ] `pytest tests/architectural/test_layer_rules.py tests/architectural/test_kernel_no_doctrine_import.py tests/architectural/test_no_dead_symbols.py -q` green.

### Subtask T012 – `charter.activation.layer_roots`; project root = pack root

- **Purpose**: layer-root discovery belongs in `charter` (C-007, research A.3 #5) and must hand out the pack root so consumers stop joining a `"doctrine"` segment (B.3 "Layer-root contract change").
- **Steps**:
  1. Create `src/charter/activation/layer_roots.py` from `src/specify_cli/cli/commands/charter/_layer_roots.py` (85 lines). Inside `charter`, import `resolve_org_roots` / `resolve_existing_org_roots` from `charter.offering.drg.org_pack_config` directly (the `charter.drg` proxy comment applies only to `specify_cli` and runtime). Keep `__all__ = ["resolve_layer_roots", "resolve_org_root_chain"]` and the docstrings (reword the tier sense to "charter pack").
  2. Change `resolve_layer_roots`: `project = resolve_project_pack_read_root(repo_root, quiet=True)`; set `roots["project"] = project` when `project.is_dir()`. Today it sets `.kittify` when `.kittify/doctrine` is a dir (`_layer_roots.py:20-22`).
  3. Update the three consumers that joined `"doctrine"` to the `.kittify` value:
     - `src/charter/activation/pack_manager.py:286-288` → `root / kind_dir`;
     - `src/charter/activation/kind_vocabulary.py:294-296` (`_layer_candidate_dir`, project branch) → `root / PROJECT_KIND_DIRS.get(kind, kind.plural)`; leave the non-project nested-org branch at `:297` alone (WP03 decides it for the gate);
     - `src/specify_cli/cli/commands/charter/list_cmd.py:72-74` → `project_root / "missions"`.
  4. **Do not break project mission types.** `pack_manager.py:345-358` joins `PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT` to the project root, assuming it is `.kittify` (`mission_type_repository.py:375-389`). After the change it would look under `.kittify/charter-packs/missions/mission_types`. Resolve `.kittify/missions/mission_types` from the repository root instead (thread `repo_root`, or join `PROJECT_MISSION_TYPES_RELATIVE` onto `project_root.parent.parent` only via a named helper with a test). Pick one, write a test that a project mission type under `.kittify/missions/mission_types/` is still listed with a migrated layout, and record the decision in the Activity Log. Update the `PROJECT_MISSION_TYPES_RELATIVE_TO_KITTYFY_ROOT` docstring so it no longer claims the layer root is `.kittify`.
  5. Delete `src/specify_cli/cli/commands/charter/_layer_roots.py`; repoint every importer (mechanical list). `grep -rn "_layer_roots" src tests` must return nothing.
- **Files**: `src/charter/activation/layer_roots.py` (new), `_layer_roots.py` (deleted), `pack_manager.py`, `kind_vocabulary.py`, `list_cmd.py`.
- **Parallel?**: after T011.
- **Notes**: `resolve_org_root_chain` is unchanged in behaviour. `roots["org"]` stays a single `Path` (back-compat contract documented in the moved docstring).
- **Validation**:
  - [ ] `pytest tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_runtime_charter_doctrine_boundary.py -q` green (the module now lives in `charter`).
  - [ ] `pytest tests/charter/test_kind_vocabulary_scan_roots.py tests/charter/test_pack_manager.py tests/charter/test_pack_manager_catalog.py tests/charter/test_mission_type_path_layout_ssot.py tests/specify_cli/cli/commands/charter -q` green after the mechanical repoint.

### Subtask T013 – READ sites in `kernel`, `charter`, `runtime`, `glossary`

- **Purpose**: every reader of the project layer resolves the root through the kernel module (FR-016).
- **Steps**: replace each hard-coded `.kittify/doctrine` join with `resolve_project_pack_read_root(repo_root, quiet=True)` (or `project_pack_root` where the code only names the canonical location, for example a display string). Use `quiet=True` everywhere: today these sites read the legacy root silently, and only `reconcile.py:612` warns; keep that behaviour.
  - `src/charter/activation/_drg_helpers.py:196` (project DRG load).
  - `src/charter/activation/_doctrine_paths.py:30` (`_PROJECT_ROOT_CANDIDATES`, first entry). The candidate list is a tuple of repo-relative strings: replace the first entry by a call (turn the tuple into a function returning the resolved candidates) so the resolver, not a string, decides. Leave the `"doctrine"` flat built-in fallback at `:32` (not the project root; WP03's gate decides).
  - `src/charter/activation/mission_type_profile_repository.py:52` (`_PROJECT_OVERRIDE_PARTS`).
  - `src/charter/offering/drg/project_scan.py:73,200,205` (offering may import `kernel`).
  - `src/charter/offering/drg/override_policy.py:70` (`POLICY_RELPATH`): becomes `PROJECT_PACK_ROOT / "replaceable-builtins.yaml"` for display, and the reader at `:251` resolves through the read root.
  - `src/charter/offering/service.py:48`: the project-root detection `name == "doctrine" and parent.name == ".kittify"` must accept the pack root: compare against `PROJECT_PACK_DIRNAME` and `LEGACY_PROJECT_PACK_DIRNAME` (the legacy half dies in WP14).
  - `src/runtime/next/runtime_bridge_composition.py:286`; `src/glossary/entity_pages.py:72`.
- **Files**: as listed.
- **Parallel?**: yes with T014.
- **Notes**: docstrings that only describe the path (for example `_drg_helpers.py:91-122`, `project_scan.py:4,123`) are updated to `.kittify/charter-packs/` in the same edit; broader prose is WP22.
- **Validation**:
  - [ ] `pytest tests/charter tests/doctrine -q` (both owning trees, because `src/charter/offering/**` changed).
  - [ ] `pytest tests/glossary tests/runtime -q -k "entity_pages or bridge"` plus the test files that `grep -rl "runtime_bridge_composition\|entity_pages" tests` returns.

### Subtask T014 – READ sites in `specify_cli`

- **Steps**: same rule as T013.
  - `analysis_inputs.py:200` (the `"doctrine"` entry of the declarative-subtree loop): include the resolved read root instead of `root/".kittify"/"doctrine"`.
  - `calibration/walker.py:347,395` (overlays).
  - `charter_runtime/lint/_drg.py:51`.
  - `charter_runtime/preflight/runner.py:129,787` (`_DIRTY_SCOPE_PATHS` and the dirty filter): include **both** `PROJECT_PACK_ROOT_POSIX + "/"` and the legacy prefix until WP14, built from the kernel constants, so a dirty file in either tree blocks auto-refresh.
  - `cli/commands/_doctrine_collect.py:244,352,616,1175` and the `POLICY_RELPATH` display at `:928-931`.
  - `cli/commands/charter/_status_collectors.py:211`; `cli/commands/profiles_cmd.py:105`; `mission_loader/command.py:274`; `mission_step_contracts/executor.py:176`; `review/gate_bindings.py:74` (`_PROJECT_CONTRACTS_SUBPATH`); `skills/catalog.py:60` (`_PROJECT_SKILLS_DIR`).
  - `tool_surface/providers/agent_profiles.py:578` (fingerprint inputs): replace `".kittify/doctrine"` with the resolved read root; leave the bare `"doctrine"` entry and record why (it is a repository-root directory, not the project layer) or drop it if no such directory exists anywhere (check with `git ls-files doctrine | head`).
- **Files**: as listed.
- **Parallel?**: yes with T013.
- **Notes**: `_doctrine_collect.py:1088` (`governance_block.get("doctrine")`) is a legacy **config key**, not a path: leave it for WP14. `tracker/config.py:39` is out of scope (tracker ownership key, CR-03 is WP14).
- **Validation**:
  - [ ] `grep -rn '"\.kittify/doctrine\|"\.kittify" / "doctrine"\|/ "doctrine" /' src --include=*.py` lists only WP03's write files, `kernel/charter_pack_paths.py` and the frozen migrations.
  - [ ] Each touched module's tests pass (find them with `grep -rl "<module_name>" tests --include=*.py`).

### Subtask T015 – Tests for the kernel module and the moved layer roots

- **Steps**:
  1. Move `tests/kernel/test_doctrine_root.py` to `tests/kernel/test_charter_pack_paths.py` (git mv, then adapt): keep every behavioural case of the fallback (canonical wins, legacy warns once, neither → canonical, `quiet` suppresses), add cases for every public constant/function in B.3 (`project_pack_root`, `project_pack_path`, `pack_drg_fragment`, `pack_org_charter`, `pack_presets_dir`).
  2. `tests/charter/activation/test_layer_roots.py`: migrated layout → `roots["project"] == repo/.kittify/charter-packs`; legacy layout → `repo/.kittify/doctrine`; neither → no `"project"` key; org chain unchanged. Include the project mission-types regression from T012 step 4.
  3. A read-site regression: a migrated fixture with a project directive under `.kittify/charter-packs/directive/` is visible to `charter list --all --json` (this is also WP01's acceptance test; add a unit-level twin at `PackManager` level in `tests/charter/test_pack_manager.py` only if the acceptance test does not localise failures well; log the choice).
- **Files**: `tests/kernel/test_charter_pack_paths.py` (new), `tests/kernel/test_doctrine_root.py` (deleted), `tests/charter/activation/test_layer_roots.py` (new).
- **Parallel?**: no; last.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/test_project_pack_root.py -q -rxX
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -rxX        # nothing else may change state
uv run --frozen pytest tests/kernel tests/charter tests/doctrine -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter tests/glossary tests/runtime -q
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_kernel_no_doctrine_import.py \
  tests/architectural/test_charter_no_specify_cli_import.py tests/architectural/test_charter_offering_does_not_import_activation.py \
  tests/architectural/test_runtime_charter_doctrine_boundary.py tests/architectural/test_no_dead_symbols.py \
  tests/architectural/test_dead_symbol_allowlist_contract.py tests/architectural/test_charter_path_literal_authority.py -q
uv run --frozen mypy src/kernel/charter_pack_paths.py src/charter/activation/layer_roots.py <every touched src file>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Plus the tests of every touched module (`grep -rl "<module>" tests --include=*.py`). Never bare `tests/architectural/` or `make test-full`. Record commands and pass/fail counts in the Activity Log.

## Commit discipline

Commit per subtask, conventional subjects naming #3732, for example `test(acceptance): unmark WP02 FR-016 tests (red) (#3732)`, `refactor(kernel): charter_pack_paths replaces doctrine_root (#3732)`, `refactor(charter): layer_roots moves to charter.activation (#3732)`. Never push to `main`.

## Risks & Mitigations

- **Project mission types silently lost** after the layer-root contract change: T012 step 4 test.
- **Split-brain** once WP03 writes the canonical root on a legacy project: the canonical tree wins reads. Documented; resolved by the migration (WP11). Do not run synthesis on this repository mid-mission.
- **Warning noise** if a read site forgets `quiet=True`: CLI output on this repository would gain a warning line; tests that snapshot stderr would catch it.

## Definition of Done

- [ ] `kernel/doctrine_root.py` and `_layer_roots.py` deleted; no import of either remains.
- [ ] Every B.1 READ site in owned files resolves through `kernel.charter_pack_paths`.
- [ ] WP02 acceptance tests: red on base (first commit) → green; the rest of the acceptance suite unchanged (still `xfailed`/`passed`).
- [ ] Gates, mypy, ruff, format, terminology guard green; mechanical edits logged.

## Review Guidance

- Check out the first commit: the three WP02 acceptance tests are red. Final commit: green.
- Grep for `kernel.doctrine_root`, `_layer_roots`, `"doctrine"` path joins: only allowed leftovers (WP03 write files, nested-org branch, frozen migrations).
- Confirm no alias module or forwarding stub exists, and the fallback lives in exactly one function.
- Confirm project mission types still resolve on a migrated layout.

## Activity Log

- 2026-10-06T19:30:00Z – system – Prompt created.
