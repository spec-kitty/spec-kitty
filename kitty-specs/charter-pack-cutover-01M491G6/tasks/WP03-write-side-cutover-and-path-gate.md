---
work_package_id: WP03
title: Write-side cutover and path-authority gate
dependencies:
- WP02
requirement_refs:
- FR-016
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: b87ca5df36e0736b2524562c996980cdc8d9f813
created_at: '2026-10-07T02:14:41.132014+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
phase: Phase 1 - Foundations (paths, package split)
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/
create_intent:
- tests/architectural/test_charter_pack_path_authority.py
- tests/architectural/charter_pack_path_allowlist.yaml
execution_mode: code_change
owned_files:
- src/charter/activation/synthesizer/write_pipeline.py
- src/charter/activation/synthesizer/path_guard.py
- src/charter/activation/synthesizer/manifest.py
- src/charter/activation/synthesizer/reconcile.py
- src/charter/activation/synthesizer/staging.py
- src/charter/activation/synthesizer/validation_gate.py
- src/charter/activation/synthesizer/project_drg.py
- src/charter/activation/synthesizer/resynthesize_pipeline.py
- src/charter/activation/synthesizer/graph_residue.py
- src/charter/activation/synthesizer/errors.py
- src/charter/activation/synthesizer/__init__.py
- src/charter/activation/project_registration.py
- src/charter/bundle.py
- src/specify_cli/charter_runtime/freshness/computer.py
- src/specify_cli/cli/commands/charter/_fresh_doctrine.py
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/doctrine_synthesizer/apply.py
- src/specify_cli/cli/commands/doctrine.py
- src/specify_cli/state/contract.py
- .gitignore
- .github/workflows/ci-router.yml
- tests/architectural/test_charter_pack_path_authority.py
- tests/architectural/charter_pack_path_allowlist.yaml
- tests/charter/synthesizer/**
- tests/charter/test_project_registration.py
- tests/charter/test_synthesis_provenance_paths.py
- tests/charter/test_bundle_validate_cli.py
- tests/agent/cli/commands/test_charter_synthesize_cli.py
- tests/agent/cli/commands/test_charter_resynthesize_cli.py
- tests/cli/test_agent_status_validate_retrospective.py
- tests/doctrine_synthesizer/test_apply.py
- tests/doctrine_synthesizer/test_path_traversal_rejection.py
- tests/integration/test_charter_status_freshness.py
- tests/integration/test_charter_synthesize_built_in_only.py
- tests/integration/test_charter_synthesize_fresh.py
- tests/specify_cli/charter/test_bundle_validate_fresh_seed.py
- tests/specify_cli/charter_freshness/test_computer.py
- tests/specify_cli/charter_runtime/test_freshness_activation_visibility.py
- tests/specify_cli/charter_runtime/test_freshness_cache.py
- tests/specify_cli/charter_runtime/test_freshness_residue.py
- tests/specify_cli/cli/commands/charter/test_resynthesize_and_hotpath.py
- tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py
- tests/specify_cli/cli/commands/charter/test_synthesize_freshgate_4785.py
- tests/specify_cli/cli/commands/test_doctrine_new.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Write-side cutover and path-authority gate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/charter/activation/synthesizer/`.

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

1. Every **writer** of the project layer targets `.kittify/charter-packs/` through `kernel.charter_pack_paths` (WP02): the synthesizer, project registration, fresh-project seeding, the scaffolder, the retrospective-proposal applier, the synthesis commit recipe, and the state contract.
2. `charter synthesize` on a migrated project writes under `.kittify/charter-packs/` and creates no `.kittify/doctrine/` (testability squad A1).
3. A new architectural gate, `tests/architectural/test_charter_pack_path_authority.py`, forbids a `"doctrine"` path segment in path-construction contexts under `src/` and re-spellings of the pack-path literals outside the kernel authority, with planted self-tests and a scanned-file floor.
4. This repository's `.gitignore` and `.github/workflows/ci-router.yml` follow the new root.
5. WP01's FR-016 tests pending on WP03 are green.

## Context & Constraints

- Read: `spec.md` FR-016, NFR-002, C-001, C-008; `research/package-split-and-paths.md` B.1 (WRITE/BOTH table), B.2, B.4 (gate shape), "Not the project root" list; `research/postspec-squad-testability.md` A1; `contracts/upgrade-migration.md` (the migration, not this WP, rewrites persisted paths of existing projects).
- **Persisted paths.** `synthesis-manifest.yaml` `artifacts[].path` (`synthesizer/manifest.py:38`), provenance sidecars and `skills-manifest.json` `source_ref` carry the old prefix in existing projects. This WP changes what is **written** and validated for new writes; WP11 rewrites existing files. Until WP11, a manifest validator that rejects the legacy prefix would break legacy projects: accept both prefixes on read in `manifest.py` and write only the new one, with the legacy acceptance in one named predicate that WP14 deletes (record it in the Activity Log).
- **Do not move this repository's `.kittify/doctrine/` tree** (WP11 T059 does it with the migration). Do not run `charter synthesize --apply` on this repository.
- **No aliases (C-001)**: no constant kept under its old name, no `DOCTRINE_DIR` re-export from `charter.bundle`.
- Ownership: `src/charter/activation/synthesizer/manifest.py`, `project_registration.py` and `cli/commands/doctrine.py` are also edited by WP04 (hash-helper move, imports). WP04 must start after this WP is approved; if your lane finds WP04 already running, stop and tell the orchestrator.
- Code style: ruff, `ruff format`, mypy clean; complexity ≤ 15; no new suppressions.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- Lane: from `lanes.json` (filled by `spec-kitty agent mission finalize-tasks`).

## Red-first (C-006 / C-011)

First commit: delete the `pending_until("WP03", …)` markers in `tests/acceptance/charter_pack_cutover/test_project_pack_root.py` (`test_fr016_synthesize_writes_new_root_only`, `test_fr016_path_authority_gate_detects_planted_literal`, `test_fr016_state_contract_and_gitignore_use_new_root`). Run them, record the red output, commit. Implementation commits turn them green. Do not change their assertions.

## Subtasks & Detailed Guidance

### Subtask T016 – Repoint synthesizer WRITE sites

- **Purpose**: the synthesizer is the main writer; leaving it on the legacy root recreates `.kittify/doctrine/` after the migration (A1).
- **Steps** (`src/charter/activation/synthesizer/`):
  1. `write_pipeline.py:40,62,68-70,184,520,560,600,604`: drop `_DOCTRINE_DIRNAME = LEGACY_PROJECT_PACK_DIRNAME`; build live paths with `project_pack_path(repo_root, kind_subdir, filename)` and `project_pack_path(repo_root, PROJECT_GRAPH_FILENAME)`. `_rel_path` docstring (`:119`) shows the new prefix.
  2. `path_guard.py:37`: `_DEFAULT_ALLOWLIST = (PROJECT_PACK_ROOT_POSIX, ".kittify/charter")` built from the constant; module docstring `:8`. `errors.py:89`: message names `.kittify/charter-packs/`.
  3. `manifest.py:38` `_ARTIFACT_PATH_PREFIX = PROJECT_PACK_ROOT`; the read-side validator accepts the legacy prefix through one predicate `_is_legacy_artifact_prefix` (docstring: "removed by FR-011, WP14"); new entries are always written with the new prefix. Docstrings `:58`, `:120`.
  4. `reconcile.py:79` (the CR-07 split-literal trap `_DOCTRINE_DIRNAME = ".kittify"`): delete it; `:315` f-string becomes `(PROJECT_PACK_ROOT / doctrine_kind_subdir(kind) / filename).as_posix()`; `:316` provenance path composes `.kittify/charter/provenance` without a misnamed constant; `:612` keeps `resolve_project_pack_read_root` (the one warning site).
  5. **Staging subtree** (B.1 "Not the project root", recommendation adopted): `staging.py:112,145`, `validation_gate.py:184`, `project_drg.py:549`, `write_pipeline.py:600` use `<staging>/doctrine/...`. Rename the segment to `PROJECT_PACK_DIRNAME` so promotion stays 1:1 and the gate can stay strict. A staging directory is transient (`.kittify/charter/.staging/`); no migration needed, but confirm nothing persists staging paths (grep `staging` in `manifest.py` and provenance writers) and record the result.
  6. Reads inside the synthesizer: `project_drg.py:460` and `resynthesize_pipeline.py:370,453,482` resolve through `resolve_project_pack_read_root(repo_root, quiet=True)`; docstrings `project_drg.py:160,228,420-426`, `resynthesize_pipeline.py:234`, `graph_residue.py:41`, `__init__.py:5`, `staging.py:17`.
- **Files**: the synthesizer files above.
- **Parallel?**: no; T019's gate is calibrated on the result.
- **Validation**:
  - [ ] `grep -n '"doctrine"\|\.kittify/doctrine\|LEGACY_PROJECT_PACK' src/charter/activation/synthesizer/*.py` shows only `reconcile.py`'s read call and the `manifest.py` legacy-prefix predicate.
  - [ ] `pytest tests/charter/synthesizer -q` green after fixtures are moved to the canonical root.

### Subtask T017 – Registration, seeding, scaffold and applier WRITE sites

- **Steps**:
  1. `src/charter/activation/project_registration.py:119` (read existing graph → read root) and `:297` (write `graph.yaml` → `project_pack_path(root, PROJECT_GRAPH_FILENAME)`).
  2. `src/specify_cli/cli/commands/charter/_fresh_doctrine.py:108,147,157,200`: plan, write, delete and `PROVENANCE.md` under the pack root. Do not rename the module (WP21 R3).
  3. `src/specify_cli/cli/commands/charter/_synthesis.py:305,334` (JSON `"path"` values) and `:750` (`_SYNTHESIS_ARTIFACT_PATHS`, fed to `safe_commit_recipe`): use `PROJECT_PACK_ROOT_POSIX`. The commit recipe must still pick up a legacy-root project's changes until WP11: keep only the new root (a legacy project gets migrated before it synthesizes again; WP14 gates it) and record that decision.
  4. `src/specify_cli/cli/commands/charter/synthesize.py:136,149,152,316,324,358,369`: user-facing strings name `.kittify/charter-packs/`.
  5. `src/specify_cli/doctrine_synthesizer/apply.py:185-195` (`_DOCTRINE_BASE`): `PROJECT_PACK_ROOT`; drop the `LEGACY_PROJECT_PACK_DIRNAME` import WP02 repointed.
  6. `src/specify_cli/cli/commands/doctrine.py:640-650` (`_resolve_scaffold_root`, default target of `new`) → `project_pack_root(repo_root)`; `:1028-1035` (`org init` scaffold writes `org-charter.yaml`, `drg/fragment.yaml`) → `pack_org_charter(pack_path)`, `pack_drg_fragment(pack_path)`; printed names from the constants. The command module itself moves in WP15; do not move it here.
  7. `src/charter/bundle.py:66` `DOCTRINE_DIR`: delete the constant; `:309` and `src/specify_cli/charter_runtime/freshness/computer.py:337-349` use `kernel.charter_pack_paths` (read root for the graph check at `:342`). Docstrings `bundle.py:274,396`, `computer.py:55,85`.
- **Files**: as listed. **Parallel?**: yes with T018.
- **Validation**:
  - [ ] `charter synthesize --dry-run --json` on a migrated fixture reports paths under `.kittify/charter-packs/`.
  - [ ] `spec-kitty charter new directive …` in a tmp project scaffolds under `.kittify/charter-packs/`.

### Subtask T018 – State contract, `.gitignore`, `ci-router.yml`

- **Steps**:
  1. `src/specify_cli/state/contract.py:592-603`: `StateSurface(name="project_pack_graph", path_pattern=<from PROJECT_PACK_ROOT_POSIX and PROJECT_GRAPH_FILENAME>, ...)`, notes in charter vocabulary. Search for consumers of the surface name (`grep -rn "project_doctrine_graph" src tests docs`); at planning time only the contract module names it.
  2. `.gitignore:97-114`: replace the `.kittify/doctrine/**` block with the same rules for `.kittify/charter-packs/**`. Decide whether the new rule tracks everything (simpler: no `/**` ignore at all) or keeps the narrow re-includes; the consumer squad noted `mission_types/`, `agent_profiles/`, `mission_step_contracts/`, `skills/` are not re-included today. Required (WP01 review, spec FR-012 inventory row "Ignore rules"): carry the existing rules over to `.kittify/charter-packs/**` (same ignores, same re-includes, rewritten prefix); `test_fr016_state_contract_and_gitignore_use_new_root` asserts `.gitignore` names `.kittify/charter-packs`. Do not switch to "ignore nothing": changing what is tracked is out of scope. Record it in the comment above the rule. The tracked legacy files stay tracked (git ignores rules for tracked files) until WP11 moves them.
  3. `.github/workflows/ci-router.yml:233`: path filter `'.kittify/charter-packs/**'`. Keep `'.kittify/doctrine/**'` too until WP11 T059 moves this repository's tree, then WP11 drops it; note this in the Activity Log for WP11.
- **Files**: `state/contract.py`, `.gitignore`, `ci-router.yml`. **Parallel?**: yes.
- **Validation**:
  - [ ] `pytest tests/architectural/test_lifted_root_gitignore_contract.py -q` (if it pins these lines) and the state-contract tests (`grep -rl "state.contract\|StateSurface" tests`).
  - [ ] Router self-tests: `pytest tests/ci -q -k router` (or the files `grep -rl ci-router tests` returns).

### Subtask T019 – FR-016 path-authority gate with planted self-tests

- **Purpose**: make the cutover permanent (FR-016 "no `"doctrine"` path segment is joined to `.kittify` in `src/`"; NFR-002 closes it empty).
- **Steps**: create `tests/architectural/test_charter_pack_path_authority.py`, modelled on `tests/architectural/test_charter_path_literal_authority.py` (743 lines: AST contexts, composite-key allowlist, shrink-only baseline, FLOOR/margin at `:575-576`, staleness twin, planted self-tests at `:591-740`). Expose a public `scan(paths: Iterable[Path]) -> list[Finding]` (WP01's acceptance test imports it by file path).
  - **Authority**: `src/kernel/charter_pack_paths.py`, the only file allowed to spell the clause (b) literals and the legacy segment (the latter until WP14; say so in the gate's docstring and in a test that fails once WP14 deletes `LEGACY_PROJECT_PACK_DIRNAME`, telling WP14 to drop the exemption).
  - **Contexts**: `/` `BinOp` operands; `Path(...)`/`PurePath(...)`/`joinpath(...)` arguments; constant-assignment right-hand sides that are path-like (`".kittify/…"` strings, `Path` calls); `JoinedStr` constant parts split on `/`; tuple/list literals **only** when they are path parts (passed to `Path(*x)`/`joinpath(*x)` directly, or assigned to a module-level name that is later splatted into one; resolve that alias in-module). Resolve module-level `str` constant aliases (as `_module_level_charter_filename_aliases` does in the model gate) so `X = ".kittify"` / `Y = LEGACY…` cannot hide a site.
  - **Clause (a)**: a `"doctrine"` segment in any of those contexts.
  - **Clause (b)**: `.kittify/charter-packs`, a `"charter-packs"` segment, `"org-charter.yaml"`, `"fragment.yaml"`, or a `"presets"` segment outside the authority.
  - **Clause (c)**: `.gitignore` has no `.kittify/doctrine` rule and has the new rule; the `StateSurface` pattern equals the kernel-built value (import and compare).
  - **Exemptions** (closed, by file, each with a reason in the module): the cutover migration module (created by WP11; add its expected path now, the staleness twin tolerates a missing file only for this entry and says so), and the frozen migrations whose dead `parents[3]/"doctrine"/"skills"` fallbacks B.1 lists (at planning time: `src/specify_cli/upgrade/migrations/m_2_1_2_fix_glossary_context_skill.py`, `m_2_1_2_fix_orchestrator_api_skill.py`, `m_2_1_2_fix_runtime_next_skill.py`, `m_2_1_2_install_git_workflow_skill.py`, `m_2_1_2_install_mission_system_skill.py`, `m_3_2_0rc30_fix_runtime_next_result_default.py`, `m_3_2_0rc35_fix_prompt_file_workaround.py`; re-run `grep -ln '"doctrine"' src/specify_cli/upgrade/migrations/*.py` and list each real file, no glob). WP10 runs in parallel and may stub some of these, so the staleness check for **file exemptions** asserts only that the file exists (WP10 keeps every migration module); WP25 shrinks the list to the files that still contain the literal.
  - **Allowlist** `tests/architectural/charter_pack_path_allowlist.yaml`, shrink-only, composite key `(file, qualname, literal)`, each entry naming the WP that removes it. Expected entries: the pack-relative literals still spelled inside `src/specify_cli/doctrine/*` (B.2: `pack_validator.py:584,1422,1546,1678`, `pack_assembler.py:467,481,672,685,695`, `org_charter.py:426`, `org_charter_loader.py:68`, `snapshot.py:357,468,582`, `builtin_manifest.py:43`; owner WP04/WP05, which repoint them while moving the modules), the remaining B.2 sites outside the package (`charter/activation/drg_activation.py:163`, `_drg_helpers.py:177`, `offering/drg/org_pack_loader.py:536`, `org_pack_discovery.py:158,269`, `mission_step_contracts/executor.py:583`, `_doctrine_collect.py:94,141,173`; owner WP25 unless a WP touching the file removes them first), the nested org layout (`kind_vocabulary.py:297`) and the built-in flat fallback (`_doctrine_paths.py:32`) with owner WP14. Repoint any of these yourself when it is a one-line change in a file you own.
  - **Non-vacuity**: scanned-file floor (≥ 1,000 `src` files, recorded with a margin, like the model's FLOOR); a planted-literal `tmp_path` test per clause and per shape (BinOp, `Path()` arg, f-string, tuple splat, alias constant); "allowlisting one literal does not waive the module"; the staleness twin (an allowlist entry whose site disappeared fails).
- **Files**: the gate and its allowlist. **Parallel?**: after T016–T018.
- **Notes**: prose (docstrings, messages) is out of the gate by construction; the FR-018 vocabulary gate (WP25) owns `.kittify/doctrine` in prose. `template_resolver.py:173`, `retrospective/schema.py:490`, `retrospective/reader.py:112` are not path contexts; confirm the scan ignores them and add one planted test for a non-path tuple.
- **Validation**:
  - [ ] Gate green on the tree; each planted test red without the fix and green with it.
  - [ ] Allowlist entries all name an owner WP; count recorded in the Activity Log.

### Subtask T020 – CLI synthesize test; flip WP01 FR-016 xfails

- **Steps**:
  1. Update the owned tests listed in the frontmatter so their fixtures and assertions use the canonical root (tests follow the code). Keep one test per writer that **seeds a legacy-root project** and proves the read fallback still serves it until WP14 (that test is deleted by WP14 with the shim; name it `test_*_legacy_root_read_fallback` so WP14 finds it).
  2. Add a CLI regression in `tests/agent/cli/commands/test_charter_synthesize_cli.py`: migrated fixture, `charter synthesize` (apply), artifact under `.kittify/charter-packs/`, `.kittify/doctrine` absent, `charter list --json` shows it (positive control).
  3. Run the WP01 acceptance file; the three WP03 tests go green.
- **Parallel?**: no; last.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest tests/acceptance/charter_pack_cutover/test_project_pack_root.py -q -rxX
uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -rxX
uv run --frozen pytest tests/charter tests/doctrine tests/doctrine_synthesizer -q
uv run --frozen pytest tests/agent/cli/commands/test_charter_synthesize_cli.py tests/agent/cli/commands/test_charter_resynthesize_cli.py \
  tests/integration/test_charter_synthesize_fresh.py tests/integration/test_charter_synthesize_built_in_only.py \
  tests/integration/test_charter_status_freshness.py tests/specify_cli/charter_freshness tests/specify_cli/charter_runtime \
  tests/specify_cli/cli/commands/charter tests/specify_cli/cli/commands/test_doctrine_new.py tests/cli/test_agent_status_validate_retrospective.py -q
uv run --frozen pytest tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_charter_path_literal_authority.py \
  tests/architectural/test_no_stale_charter_path_literals.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_lifted_root_gitignore_contract.py -q
uv run --frozen mypy <every touched src file>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Never bare `tests/architectural/` or `make test-full`. Record commands and counts in the Activity Log.

## Commit discipline

Per subtask, conventional subjects naming #3732 (`fix(charter): synthesizer writes the charter-packs root (#3732)`, `test(architectural): FR-016 path-authority gate (#3732)`). Never push to `main`.

## Risks & Mitigations

- **Legacy projects break before the migration exists**: read fallback (WP02) plus the manifest's legacy-prefix predicate keep them readable; writes go to the new root. Documented split-brain is resolved by WP11.
- **Gate too broad** (flags non-path strings): restrict contexts as specified; planted non-path test.
- **Gate too narrow** (misses f-strings or aliases, the CR-07 trap): planted tests per shape.

## Definition of Done

- [ ] No writer targets `.kittify/doctrine/`; `charter synthesize` on a migrated fixture creates no legacy directory.
- [ ] Gate lands green with a scanned-file floor, planted tests, and an allowlist whose every entry names its removing WP.
- [ ] `.gitignore`, `ci-router.yml`, state contract updated; decisions logged.
- [ ] WP03 acceptance tests red on the first commit, green at the end; the rest of the suite unchanged.

## Review Guidance

- First commit: three WP03 tests red; last: green.
- Read the gate's planted tests: each shape (BinOp, `Path()`, f-string, tuple splat, alias) has one.
- Verify `reconcile.py` no longer has a constant named for one thing and holding another.
- Verify the allowlist is not a path glob and every entry has an owner WP.

## Activity Log

- 2026-10-06T19:30:00Z – system – Prompt created.
- 2026-10-07T03:45:26Z – claude – shell_pid=27413 – Red-first (e92ccab9): 3 failed/3 passed - synthesize recreated .kittify/doctrine; gate module missing; project_doctrine_graph in STATE_SURFACES.
- 2026-10-07T03:45:44Z – claude – shell_pid=27413 – Decisions: manifest legacy prefix accepted on read only via _is_legacy_artifact_prefix (removed by WP14); _SYNTHESIS_ARTIFACT_PATHS commit recipe keeps only the new root (legacy project migrates before re-synthesizing; WP14 gates); staging subtree renamed to <staging>/charter-packs (transient, nothing persists staging paths - grep of manifest/provenance writers clean); .gitignore rules carried over 1:1 to .kittify/charter-packs/** (no tracking change); charter.bundle.DOCTRINE_DIR deleted (no alias).
- 2026-10-07T03:45:46Z – claude – shell_pid=27413 – WP11 note: ci-router.yml corpus filter now lists '.kittify/charter-packs/**' AND keeps '.kittify/doctrine/**' (also mirrored in tests/release/ci_retirement_scrub.json); WP11 drops the legacy line in both after T059 moves this repo's tree. FR-016 gate exemption for m_4_0_0rc6_charter_pack_cutover.py tolerates a missing file until WP11 creates it (EXEMPTIONS_TOLERATED_MISSING).
- 2026-10-07T03:45:49Z – claude – shell_pid=27413 – Allowlist tests/architectural/charter_pack_path_allowlist.yaml: 25 entries, baseline 25 - WP04 6 (specify_cli/doctrine pack_validator, pack_assembler, org_charter), WP05 1 (org_charter_loader), WP14 11 (B.2 sites drg_activation, _drg_helpers, org_pack_loader, org_pack_discovery x2, executor, _doctrine_collect; nested org layout kind_vocabulary + pack_manager; manifest legacy predicate; preflight runner legacy dirty-scope prefix), WP25 7 (missions/repository.py origin labels 'doctrine/...'). WP14 test_authority_legacy_segment_exemption_is_temporary fails when LEGACY_PROJECT_PACK_DIRNAME is deleted.
- 2026-10-07T03:45:51Z – claude – shell_pid=27413 – Mechanical edits outside owned_files: src/charter/activation/synthesizer/_constants.py (docstring, synthesizer surface); tests/release/ci_retirement_scrub.json (WP21, transitive dependent: router corpus copy); tests/specify_cli/charter_runtime/test_boundary_heal.py (WP20, dependent); unowned tests repointed to the write root: tests/charter/test_symlink_loop_guards.py, test_project_default_context.py, test_project_profile_cascade_reach.py, tests/specify_cli/cli/commands/charter/test_activate_preserve.py, tests/specify_cli/cli/commands/test_charter_authoring.py, test_charter_project_ingestion.py, tests/agent/cli/commands/test_charter_status_cli.py, tests/e2e/test_charter_epic_golden_path.py. Not changed: shared seed_graph fixture (tests/specify_cli/charter_preflight/_fixtures.py, ~15 suites) still seeds the retired root and is read via the fallback - must be repointed before WP14 removes the shim.
- 2026-10-07T03:45:54Z – claude – shell_pid=27413 – Tests: make test-fast 2281 passed/8 skipped; owned list + tests/charter/synthesizer 755 passed/12 skipped; tests/charter + tests/doctrine_synthesizer 3444 passed + 3 fixed (re-run 7 passed); acceptance + FR-016 gate + charter_path_literal + no_stale_charter_path_literals + layer_rules + lifted_root_gitignore + no_legacy_terminology: 320 passed, 265 xfailed, 0 failed, 0 xpassed; gate: 36 passed; tests/ci + router gates 2127 passed + scrub fix; legacy-root-seeding tests (73 files) 1193 passed after 2 fixes; writer-exercising tests (118 files) 2295 passed, 1 env failure (test_corpus_wp_snapshot_parity: live coordination surface of this mission). Pre-existing on lane base 3ee1c97a: tests/ci/test_corpus_blocking_home.py::test_every_corpus_test_has_a_blocking_per_pr_home. mypy: same 4 pre-existing errors as base, none new; ruff check + format --force-exclude clean.
- 2026-10-07T04:34:46Z – claude – Cycle 2 (python-pedro): (1) 814f4ad8 dropped unused pending_until import; whole-repo ruff check clean. (2) cb697aee kept owner WP14 for the 7 clause-(b) sites + pack_manager nested layout, rationale cites WP14 T070 (path-allowlist sites handed over by WP03); WP25 repository.py origin-label entries note template_resolver._tier_to_origin must be renamed with them. (3) 7a0894c1 FR-016 gate learns loop-then-join (tuple/list literal or module sequence alias iterated by for/comprehension whose variable is a / operand or Path()/joinpath() arg); planted inline + module-alias tests, loop-without-join negative; allowlisted _doctrine_paths.py:_project_root_candidates and agent_profiles.py:_profile_input_roots (owner WP14); baseline 25 -> 27 (WP04 6, WP05 1, WP14 13, WP25 7); docstring lists known limits. (4) 0114957b ci-router tests-corpus-blocking lists the 7 charter_pack_cutover corpus modules (25 node-ids), packs.yml deselects each (logged out-of-ownership, WP15); no filter-group change needed; tests/ci 1914 passed. (5) 1b745fc5 VESTIGIAL_FILTER_GLOBS row for the forward '.kittify/charter-packs/**' corpus glob (WP03 regression, test_every_restored_filter_glob_is_live was red); expires when WP11 moves the tree (logged out-of-ownership edit to tests/architectural/test_workflow_coherence.py). Verified: acceptance 87 passed/1 skipped/265 xfailed/0 failed/0 xpassed; gate+path-literal+layer_rules+workflow_coherence+retirement_scrub 148 passed; mypy clean on changed tests (no src changes).
- 2026-10-07T04:48:47Z – claude – Cycle 3 (python-pedro): 4bd28458 fixes the seven doubled continuations in ci-router.yml tests-corpus-blocking (stubbed bash -eo pipefail run: all 13 selections reach pytest argv, exit 0); 7ee6b5be adds tests/ci/test_workflow_run_shell_syntax.py (bash -n + doubled-continuation guard over every bash run: step, planted-bad self-tests; red on pre-fix file). tests/ci 1919 passed; workflow coherence 17 passed; ruff check clean; format+mypy clean on new file.
