---
work_package_id: WP11
title: Cutover migration I — keys, project root, path references
dependencies:
- WP03
- WP10
- WP17
requirement_refs:
- FR-012
- NFR-004
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-pack-cutover-01M491G6
base_commit: bc4e33ec0b74419a9129be196ffdb9af73319574
created_at: '2026-10-07T10:25:00.782203+00:00'
subtasks:
- T055
- T056
- T057
- T058
- T059
- T060
phase: Phase 3 - Upgrade migration
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py
- src/specify_cli/upgrade/migrations/_charter_pack_cutover_report.py
- src/specify_cli/migration/legacy_charter_layout.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py
- tests/specify_cli/migration/test_legacy_charter_layout.py
- .kittify/charter-packs/**
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py
- src/specify_cli/upgrade/migrations/_charter_pack_cutover_report.py
- src/specify_cli/migration/legacy_charter_layout.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py
- tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py
- tests/specify_cli/migration/test_legacy_charter_layout.py
- .kittify/doctrine/**
- .kittify/charter-packs/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP11 – Cutover migration I — keys, project root, path references

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

After WP18 lands, the `/ad-hoc-profile-load` skill is deleted: load profiles with `spk-charter-profile-load` instead (use whichever exists in your checkout).

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and pick the best match for `task_type: implement` on `src/specify_cli/upgrade/migrations/`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress** in the Activity Log as you address each item.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Build the first half of the one FR-012 upgrade migration: the module, its `detect()`, the shared legacy predicate the CLI-root gate (WP14) will reuse, the result/summary plumbing, and every **key, project-root and path-reference** row of the FR-012 inventory. Then run it on this repository so the tracked `.kittify/doctrine/` tree becomes `.kittify/charter-packs/`.

Done means:

- `m_4_0_0rc6_charter_pack_cutover.py` is registered with `migration_id = "charter_pack_cutover"`, `runs_first = True` (WP10's flag), and selected first by `MigrationRegistry.get_applicable` on a legacy fixture.
- These inventory rows are rewritten, idempotently, with a report line each: org packs list; single-pack legacy form; `organisation_packs`; `governance.doctrine` (config.yaml, charter.yaml, standalone `governance.yaml`); tracker `doctrine` key; interview answers top-level `doctrine:`; `doctrine_pack_id` in activation entries; `.kittify/doctrine/**` move (with collision preflight); synthesis manifest paths; provenance sidecar paths; skills-manifest `source_ref`; `.gitignore` rules.
- A second `apply()` on every WP11 fixture changes 0 bytes and `detect()` is False (NFR-004 for these rows).
- `detect()` evaluates the reset predicates (stale lists, kind gates, `[]`) only while the migration is not recorded as applied; once applied, only the structural predicate (legacy root, legacy keys, `doctrine_pack_id`) can re-select it, so an operator restoring a deliberate `[]` never re-triggers it (analysis U1).
- This repository has `.kittify/charter-packs/` holding the 14 formerly tracked files, no `.kittify/doctrine/`, and a `.gitignore` with no `.kittify/doctrine` rule.
- Every WP01 acceptance test marked `pending_until("WP11")` is green.

## Context & Constraints

Read before starting:

- `kitty-specs/charter-pack-cutover-01M491G6/spec.md`: FR-012 and its **migration inventory** table, Edge Cases (both roots present, canonical+legacy keys both present, uncommitted edits, Windows, user-chosen path values never rewritten), NFR-004, C-001, C-008.
- `contracts/upgrade-migration.md` (identity, `detect()`, the 8-step `apply()` order, `MigrationResult` fields).
- `research/runtime-seams.md` §1 (selection/ordering, runner behaviour), §2 (worktrees), §3 (detection seam; the predicate function and its cost budget), the §3 table "Where the legacy shapes are read today".
- `research/package-split-and-paths.md` Part B (B.1 persisted contract and ignore rules, B.3 kernel module API).
- `data-model.md` "Legacy project state → canonical".
- `.kittify/charter/charter.md` (project charter) — load it; `spec-kitty charter context --action implement`.

Upstream state you can rely on (verify each by grep before using):

- **WP02/WP03**: `src/kernel/charter_pack_paths.py` exists with `PROJECT_PACK_ROOT`, `PROJECT_PACK_ROOT_POSIX`, `project_pack_root()`, `PROJECT_GRAPH_FILENAME` (names per research B.3; use whatever WP02 actually shipped). Every reader and writer targets `.kittify/charter-packs/`. The FR-016 path-authority gate (`tests/architectural/test_charter_pack_path_authority.py` per research B.4, confirm the real filename) forbids a `"doctrine"` path segment in `src/` except by a closed **by-file** exemption list.
- **WP10**: `BaseMigration.runs_first`, applied in `get_applicable`; rc35 / normalizer / glossary-context migrations neutralised; finalize migration no longer calls the governance compat helper.
- Read-side legacy fallbacks (`doctrine.org.*`, `organisation_packs`, `governance.doctrine`, tracker `doctrine`) **still exist** until WP14. Do not remove them here; the migration must not depend on them either (it reads raw YAML).

Constraints:

- **C-001**: no aliases or shims. The migration is the only place allowed to spell legacy keys and paths; it reads raw files, never through the legacy-aware readers.
- **Layering (C-007)**: the predicate module `specify_cli/migration/legacy_charter_layout.py` imports nothing from `charter.*` (it runs on every CLI invocation from WP14 on). Migration modules import `charter.*` lazily inside functions so discovery stays cheap (precedent: `m_3_2_x_normalize_activation_absence.py` docstring).
- **Exemptions**: the main module matches the occurrence-map exemption `m_*charter_pack_cutover*.py`. The two helper modules you create (`_charter_pack_cutover_report.py` if it spells legacy literals, and `specify_cli/migration/legacy_charter_layout.py`) are **not** covered by that glob. Add them to the FR-016 gate's by-file exemption list (WP03-owned gate, completed upstream: a logged follow-up edit) and record in the Activity Log that WP25's FR-018 gate must exempt them too. Keep legacy literals in as few files as possible.
- Code style: ruff + mypy clean, complexity ≤ 15 per function (split `apply()` into one function per step), no `# noqa`/`# type: ignore` without an inline rationale, repeated literals (≥ 3) hoisted to module constants.
- Commit discipline: small commits, conventional subjects referencing #3732 (for example `feat(upgrade): charter-pack cutover config-key rewrites (#3732)`). Never push to `main`.

## Branch Strategy

- **Strategy**: lane-based; the lane is assigned in `lanes.json` by `spec-kitty agent mission finalize-tasks`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do not change them manually.

## Red-first (C-006 / C-011)

Your **first commit** removes the `pending_until("WP11")` strict-xfail markers from the WP01 acceptance tests in `tests/acceptance/charter_pack_cutover/` that cover the FR-012 rows listed above (find them with `grep -rn 'pending_until("WP11")' tests/acceptance/charter_pack_cutover/`; WP01's plan lists them in `test_upgrade_migration.py`: `test_fr012_cutover_runs_first`, `test_fr012_legacy_keys_rewritten[*]`, `test_fr012_doctrine_pack_id_renamed`, `test_fr012_project_root_moved`, `test_fr012_collision_refuses_and_moves_nothing`, `test_fr012_path_references_rewritten`, `test_fr012_windows_locked_file_refuses`; in `test_rename_skills_glossary.py`: `test_fr010_charter_pack_id_in_project_state`), and nothing else. Run them and paste the red result into the Activity Log. Two exceptions to red-first evidence: `test_fr012_user_path_values_untouched` is unmarked (it passes at base; a regression guard), and `test_fr012_windows_locked_file_refuses` (`windows_ci`) is auto-skipped off win32, so it is exempt from red-first evidence: record that in the Activity Log and rely on the POSIX simulation in T058. Do not edit their assertions (C-006: WP01 owns the acceptance criteria; the acceptance files are WP01's, edited here as a logged follow-up). If a test tagged WP11 needs behaviour from WP12 (a stale-list reset), stop and record it; do not re-tag silently. WP17 is upstream, so the model already accepts `charter_pack_id`. Implementation commits then turn them green.

## Subtasks & Detailed Guidance

### Subtask T055 – Cutover migration skeleton: `detect()`, shared legacy predicate, result/summary plumbing

- **Purpose**: one migration module and one cheap predicate that the CLI-root gate (WP14) and `detect()` share, so the gate and the migration cannot disagree (research §3 decision).
- **Steps**:
  1. Create `src/specify_cli/migration/legacy_charter_layout.py` with `detect_legacy_charter_layout(root: Path) -> tuple[str, ...]`. It returns stable finding names (module constants, for example `LEGACY_PROJECT_ROOT = "legacy_project_root"`, `LEGACY_GOVERNANCE_FILE`, `LEGACY_ORG_PACKS_KEY`, `LEGACY_ORGANISATION_PACKS_KEY`, `LEGACY_GOVERNANCE_SELECTION_KEY`) cheapest first, exactly as research §3 lists:
     1. `stat(<root>/.kittify/doctrine)` (directory exists);
     2. `stat(<root>/.kittify/charter/governance.yaml)` **only when it carries a legacy key**: this file is also a legitimate pre-fold file, so read it only if it exists (rare) and test for a top-level `doctrine:` mapping key;
     3. read the bytes of `<root>/.kittify/config.yaml`; substring prefilter for `doctrine` / `organisation_packs`; only on a hit `yaml.safe_load` and test the top-level `doctrine.org`, `organisation_packs`, `governance.doctrine` keys, and `tracker.doctrine`.
     Never read `charter.yaml` here (155 KB in this repo; research §3). No `charter.*` import. Unparseable YAML: return a finding (`unreadable_config`) rather than raising, so the gate can name it.
  2. Also expose `LEGACY_PROJECT_DIRNAME` (the `"doctrine"` literal) and `LEGACY_PROJECT_ROOT_RELPATH` here so the migration does not re-spell them.
  3. Create `src/specify_cli/upgrade/migrations/_charter_pack_cutover_report.py`: a frozen-ish dataclass `CutoverReport` with ordered lists `moved`, `rewritten`, `reset`, `kept_for_review`, `matches_minimal`, `skills_removed`, `skills_kept`, `errors`, and `to_migration_result(dry_run: bool) -> MigrationResult`. Mapping (contract): `changes_made[0]` = `json.dumps(report_dict, sort_keys=True)` (the CLI already decodes `changes_made[0]` into `migration_reports` for `--json`, see `cli/commands/upgrade.py:834-848`), followed by one human line per moved/rewritten/reset item; `warnings` = kept-for-review, minimal-equal, edited skill copies and every `[]` reset line (WP12 fills the last ones); `manual_review_required = bool(warnings)`; `preserved_paths` = edited skill copies; `success = not errors`. Dry run: same lines prefixed `Would ` and nothing written. WP12 renders this in the human upgrade summary (T064); keep the dict shape documented in the module docstring so WP12 can rely on it.
  4. Create `src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py`:
     - `@MigrationRegistry.register`, class `CharterPackCutoverMigration(BaseMigration)`, `migration_id = "charter_pack_cutover"`, `runs_first = True`, `runs_on_worktrees = False` (contract; research §1.3 said True: the contract wins, record why in the docstring: integrating worktrees are skipped by the runner anyway, #5457), `target_version` = the `pyproject.toml` version at implementation time (`4.0.0rc6` today, matching the filename; if the version was bumped before you start, rename the file and both frontmatter paths and log it).
     - `detect()` = `bool(detect_legacy_charter_layout(project_path))` **or** the content checks that only the migration runs (charter.yaml `governance.doctrine` and `governance.activations[].doctrine_pack_id`, answers.yaml top-level `doctrine:`, path references with the old prefix, `.gitignore` legacy rules). WP12 extends `detect()` with stale lists and skills. Content-driven only, never version-driven (research §1.2).
     - **Split predicate** (orchestrator decision, AR-B4): implement WP10's hook `structural_detect()` as the **structural** part only: legacy project root present, legacy config keys present, or an activation entry carrying `doctrine_pack_id`. WP10's selection re-runs the migration whenever it is true, even when `metadata.yaml` records the cutover as applied (a pulled teammate checkout with untracked legacy files, or a merge that brings legacy state back). The `[]`, stale-list and kind-gate resets (WP12) run only on the **first** application: record that the resets ran (for example a marker in the migration's recorded result) and skip them on a structural re-run, so a deliberate post-cutover `activated_<kind>: []` is never reset again. Add a test: cutover recorded as success, `.kittify/doctrine/x.md` planted, `spec-kitty upgrade` moves it and the FR-011 predicate is then empty.
     - `can_apply()` returns `(True, "")`. The collision preflight (T058) runs inside `apply()`, as the contract says (`success=False`, every colliding path in `errors`, nothing written), so a dry run reports it too. The runner records that as a failed migration and stops (`runner.py:225-246`), which is the intended outcome.
     - `apply()` runs the steps in the contract order (preflight → move → path references → config keys → `doctrine_pack_id` → [WP12: resets] → [WP12: skills] → record), each step a separate function returning report entries, so complexity stays ≤ 15 and WP12 adds its steps with a two-line wiring edit.
  5. Verify selection ordering against WP10: in a fixture stamped `3.1.0`, `MigrationRegistry.get_applicable("3.1.0", <pyproject version>, path)[0].migration_id == "charter_pack_cutover"`. WP10 already selects a `runs_first` migration independently of the version window and re-selects it on `structural_detect()`; add a test that a project **stamped above** the cutover `target_version` with a legacy root selects the cutover. Do not patch `registry.py` or `runner.py` (WP10 owns them); if the test fails, raise it with the orchestrator.
- **Files**: the three new modules above.
- **Parallel?**: no; T056–T058 build on it.
- **Notes**: the CLI root never imports the migration module; it imports only the predicate module. Keep the predicate under 1 ms on a project with no legacy state (two `stat`s + one ~1 KB read).

### Subtask T056 – Config-key rewrites (org packs incl. single-pack and `organisation_packs`, governance, tracker, answers)

- **Purpose**: the persisted config keys FR-011 stops reading (WP14).
- **Steps**:
  1. Load YAML with ruamel round-trip (preserve comments and order); precedent helpers: `_round_trip_yaml`, `_load_mapping`, `_write` in `src/specify_cli/upgrade/migrations/_retired_activation.py:198-240`. Write atomically; a malformed file raises `MigrationStateUnreadableError` (`migrations/base.py`), never a silent skip.
  2. `.kittify/config.yaml`:
     - `doctrine.org.packs[]` → `charter_packs.org.packs[]`.
     - Single-pack legacy form `doctrine.org.{local_path,subdir,source_type,url,ref}` → one `charter_packs.org.packs[]` entry with the same fields and an **explicit name that is not `default`** (spec inventory row; `default` collides with the preset and is special-cased in `ensure_pack_identity`, `org_pack_config.py:764`). Derive the name from the basename of `local_path` slugified to the pack-name grammar (verify the constraint on `OrgPackConfig.name`); fall back to `org`; de-duplicate against existing names. Report the chosen name.
     - `organisation_packs[]` (`name`, `path`, optional `source`) → `charter_packs.org.packs[]` entries `{name, local_path: <path>}` (reader today: `_registry_from_legacy_organisation_packs`, `org_pack_config.py:695-721`). An entry whose `source` is not `local_path` cannot be expressed: keep that entry, add a `kept_for_review` line, and leave `organisation_packs` holding only the unconvertible entries.
     - When the canonical `charter_packs.org` block already exists, the canonical value wins: drop the legacy key and name it in the report (Edge Cases).
     - Remove the top-level `doctrine:` mapping once `org` is moved; if it holds other keys, keep them and report `kept_for_review`.
     - `governance.doctrine` → `governance.charter` (canonical wins when both exist).
     - `tracker.doctrine` → `tracker.ownership` (canonical wins; same block shape, `tracker/config.py:236-291`).
  3. `.kittify/charter/charter.yaml` (resolve the path through the `charter:` pointer in config.yaml; do not hard-code): `governance.doctrine` → `governance.charter`. Use a byte-minimal edit: ruamel round-trip of a 155 KB file can reflow; assert in a test that only the renamed key line changes (compare all other lines).
  4. Standalone `.kittify/charter/governance.yaml` (legacy, folded by `m_unify_charter_activation_finalize`): rename its legacy selection key. Check the file's shape in the finalize migration (`m_unify_charter_activation_finalize.py` around `:231-247`): if the file's top level *is* the governance mapping, the key is top-level `doctrine:`. Do not fold the file; that stays the finalize migration's job, which now runs after this one.
  5. `.kittify/charter/interview/answers.yaml` top-level `doctrine:` → `charter:`. Reuse the byte-preserving anchored-regex approach of `scripts/migrate_charter_interview_answers.py` (`_LEGACY_KEY_LINE`, both-keys guard at `_substitute_governance_key`): copy the logic, do not import from `scripts/`. Prose and comments that merely contain the word stay untouched.
  6. Never touch user-chosen values: `local_path: packs/doctrine-foo` is kept verbatim (spec Edge Cases). Only keys move.
- **Files**: the migration module (step functions), `tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py`.
- **Parallel?**: yes, with T057 after T055.
- **Notes**: `tracker.doctrine` is a CR-03 shim key (`tracker/config.py:31-39`). Research §3 suggested keeping it as unrelated vocabulary, but spec FR-011/FR-012 rule it in scope; the spec wins.

### Subtask T057 – `doctrine_pack_id` → `charter_pack_id` in project activation entries

- **Purpose**: OD-1 rename of persisted project state.
- **Steps**:
  1. In the resolved `charter.yaml`, rewrite `governance.activations[].doctrine_pack_id` → `charter_pack_id` (model today: `ActivationEntry`, `charter/activation/activations.py:193-219`, `extra="forbid"`). Also rewrite the same key in a standalone `governance.yaml` if present.
  2. An entry carrying both keys: canonical wins, legacy dropped, reported.
  3. Line-level edit, same byte-minimal rule as T056 step 3.
- **Files**: migration module; tests in `test_charter_pack_cutover_keys.py`.
- **Parallel?**: yes.
- **Notes**: the model rename that makes a migrated file **load** is WP17 (T085), which runs **before** this WP (WP11 depends on WP17), so a migrated fixture with activations loads through `ActivationEntry`. `test_fr010_charter_pack_id_in_project_state` (WP01) flips here. Do not change the model here.

### Subtask T058 – Project-root move with collision preflight; path-reference rewrites; `.gitignore`

- **Purpose**: the project layer moves to `.kittify/charter-packs/`, and every persisted string that points at the old root follows it.
- **Steps**:
  1. **Preflight** (contract step 1): walk `.kittify/doctrine/**` (files and symlinks, including dot-directories such as `<kind>/.provenance/`). For each relative path, if the target exists under `.kittify/charter-packs/` with different bytes, collect it. Any collision → `errors` lists every colliding path, `success=False`, **nothing written** (Edge Cases). Same bytes → not a collision (the source is deleted after the move step).
  2. **Move** (contract step 2). **Ownership gate first**: `tests/architectural/test_mutation_ownership_routing.py` and `test_overwrite_ownership_routing.py` census every raw destructive call (`rmtree`/`unlink`/`rmdir`/rename-like ops) in migration modules against a **shrink-only** allowlist; a new raw literal fails the gate by construction. Route through `specify_cli.asset_preservation` instead, for example copy each file with `backup.write_file_verbatim(src, dst)` and then remove the source with `guard_destructive_removal(src, project_path, prover=CanonicalContentProver(canonical=dst.read_bytes(), check_marker=False))` (`asset_preservation/provers.py:174`, `guard.py:148`), so a source is deleted only once a byte-identical copy exists. Check how the gate classifies empty-directory removal and whether a new routed module must be added to its pinned routed-module set (a test edit there is a logged follow-up); never add an allowlist entry: if the routing seems impossible, stop and escalate. Move file by file into the target (create parent dirs; a target that does not yet exist is fine on Windows). Call `autocommit.record_upgrade_mutation(src, dst, is_move=True)` (`upgrade/autocommit.py:94`) for each file so a finalizer commit owns the move. Then remove empty directories bottom-up, then `.kittify/doctrine` itself. A `PermissionError`/`OSError` on one file (Windows lock): stop, put the path in `errors`, list already-moved files in the report; a re-run finishes the job (idempotent). Do not use `git mv` (spec Assumptions). Uncommitted edits are carried over because the working-tree file is what moves.
  3. **Path references** (contract step 3), rewriting only values that start with the old prefix `.kittify/doctrine/` (POSIX form; also accept a backslash form written on Windows and normalise it):
     - `.kittify/charter/synthesis-manifest.yaml` `artifacts[].path` (prefix constant today `_ARTIFACT_PATH_PREFIX`, `charter/activation/synthesizer/manifest.py:38`; WP03 repointed it to the kernel constant). After rewriting, recompute `manifest_hash` with the canonical function (`compute_manifest_hash` / `finalize_manifest`, `manifest.py:237-271`, or wherever WP04 moved the hash helpers) and assert `verify_manifest_hash` passes in a test. Lazy import.
     - Provenance sidecars: `.kittify/charter/provenance/*.yaml` and the moved tree's `<kind>/.provenance/*.yaml`. Grep the `ProvenanceEntry` model (`charter/activation/synthesizer/synthesize_pipeline.py:~100-130`) for fields that carry a repository path; rewrite only those field values. If no field carries the old root (this repo's sidecars carry none), the step is a recorded no-op; write a fixture that does carry one only if the model allows it.
     - `.kittify/skills-manifest.json` `source_ref` (`skills/manifest.py:43`), JSON, preserve key order and indentation.
     - `.gitignore` at the project root: through `gitignore_manager.read_gitignore_text` / `write_gitignore_text` (symlink-safe; `GitignorePathError` propagates as a failure). Rewrite each **rule line** (not comment lines) that contains `.kittify/doctrine`, replacing the prefix with `.kittify/charter-packs`; if the rewritten rule already exists, drop the legacy line instead. Keep negation order. Comments are prose and stay.
  4. Never rewrite a path value that does not start with the old root, and never touch `.kittify/charter/.staging/` (transient; if a legacy staging subtree is present, add a `kept_for_review` line).
- **Files**: migration module; `tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py`.
- **Parallel?**: no (depends on T055).
- **Notes**: Windows case: add a test marked `windows_ci` (check the marker name in `pytest.ini`) that locks a file and asserts the named-path refusal; on POSIX simulate with a monkeypatched `os.replace` raising `PermissionError`.

### Subtask T059 – Run the migration on this repository

- **Purpose**: dogfood the migration on a real project; this repository still tracks `.kittify/doctrine/` (14 files: `directive/`, `procedure/`, `tactic/` with `.provenance/` sidecars, `overlays/calibration-*.yaml`; `git ls-files .kittify/doctrine`).
- **Steps**:
  1. In your lane worktree (the checkout whose files are committed on the lane branch), run the migration directly, not a whole `spec-kitty upgrade` (that would run unrelated migrations and restamp `metadata.yaml`):
     ```bash
     uv run --frozen python -c "from pathlib import Path; from specify_cli.upgrade.migrations.m_4_0_0rc6_charter_pack_cutover import CharterPackCutoverMigration as M; r=M().apply(Path('.'), dry_run=True); print(r)"
     ```
     Record the dry-run report in the Activity Log, then run with `dry_run=False`.
  2. Check: `.kittify/doctrine` absent; `git status` shows 14 renames into `.kittify/charter-packs/`; `.kittify/charter/synthesis-manifest.yaml` unchanged (its `artifacts: []` is empty); `.gitignore` has no `.kittify/doctrine` rule (WP03/T018 may already have added the `.kittify/charter-packs` rules: then the step only drops leftovers; WP03 owns `.gitignore`, so this edit is a logged follow-up); config.yaml unchanged (it already uses `charter_packs.org.packs`); charter.yaml governance already uses `charter:`.
  3. Run `detect()` again → False. Run `apply()` again → 0 bytes changed (`git diff --stat` empty after the commit).
  4. Run the readers against the moved tree: `spec-kitty charter list --json` and `spec-kitty charter synthesize --dry-run` (or the WP03 CLI test) must still see the four project artifacts and overlays. Paste the counts.
  5. Commit: `git add -A .kittify/doctrine .kittify/charter-packs .gitignore` then `chore(repo): move project charter components to .kittify/charter-packs (#3732)`. `.kittify/` paths are bookkeeping for `approved_bound` (research §2); `.gitignore` is not, so commit it before requesting review.
  6. Drop the `'.kittify/doctrine/**'` path filter from `.github/workflows/ci-router.yml` (WP03 kept it until this move; WP03 owns the file, completed upstream: a logged follow-up edit) and run the router self-tests (`pytest tests/ci -q -k router`).
- **Files**: `.kittify/doctrine/**` (deleted), `.kittify/charter-packs/**` (created), `.gitignore` and `.github/workflows/ci-router.yml` (follow-ups).
- **Parallel?**: last implementation step, after T055–T058.
- **Notes**: the stale-list and `[]` resets on this repo's `charter.yaml` (it holds `activated_mission_step_contracts: []` and `activated_glossary_packs: []`) are **WP12**'s; do not touch activation lists here.

### Subtask T060 – Tests per inventory row; flip FR-012 xfails for these rows

- **Purpose**: one focused test per inventory row, plus idempotence, so Sonar new-code coverage and NFR-004 hold for these rows.
- **Steps**:
  1. `tests/specify_cli/migration/test_legacy_charter_layout.py`: one test per finding name, a clean-project test returning `()`, an unreadable-config test, a test that `charter.yaml` is never opened (monkeypatch `Path.read_bytes`/`open` to fail on that path), and a planted positive control (a project with `charter_packs.org` and the word "doctrine" in a comment returns `()`).
  2. `test_charter_pack_cutover_keys.py`: per row (org packs, single-pack with derived name and with `default` basename, `organisation_packs` incl. non-`local_path` source, both-keys-present for each key, governance in config/charter.yaml/governance.yaml, tracker, answers incl. both-keys guard, `doctrine_pack_id`, user path value containing `doctrine` kept). Each asserts the rewrite, the report line, and that a second `apply()` is byte-identical with `detect()` False.
  3. `test_charter_pack_cutover_paths.py`: move with nested dot-dirs; collision refuses with every path named and writes nothing (tree hash before == after); identical-content overlap moves cleanly; synthesis manifest rewrite + hash verifies; skills manifest `source_ref`; `.gitignore` rule rewrite with negations and the already-canonical case; locked file; dry-run writes nothing and reports the same lines; registry ordering (T055 step 5).
  4. Run the WP01 tests you un-marked; all green.
- **Files**: the three test files.
- **Parallel?**: write alongside each subtask (ATDD), finish here.

## Test Strategy

Run and record exact commands and pass/fail counts in the Activity Log and the PR's *Tests run*:

```bash
make test-fast
uv run --frozen pytest tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_keys.py tests/specify_cli/upgrade/migrations/test_charter_pack_cutover_paths.py tests/specify_cli/migration/test_legacy_charter_layout.py -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/ -q          # the flipped WP11 tests green; others still xfail
uv run --frozen pytest tests/specify_cli/upgrade/ tests/upgrade/ tests/specify_cli/migration/ -q
uv run --frozen pytest tests/compat/test_dry_run_parity.py tests/upgrade/test_auto_discovery.py -q
uv run --frozen pytest tests/architectural/test_migration_chain_integrity.py tests/architectural/test_no_dead_modules.py tests/architectural/test_charter_pack_path_authority.py tests/architectural/test_charter_path_literal_authority.py tests/architectural/test_ruff_format_enforcement.py tests/architectural/test_mutation_ownership_routing.py tests/architectural/test_overwrite_ownership_routing.py -q
uv run --frozen pytest tests/specify_cli/asset_preservation/ -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen mypy src/specify_cli/upgrade/migrations/m_4_0_0rc6_charter_pack_cutover.py src/specify_cli/upgrade/migrations/_charter_pack_cutover_report.py src/specify_cli/migration/legacy_charter_layout.py
uv run --frozen ruff check src/specify_cli/upgrade/migrations/ src/specify_cli/migration/ tests/specify_cli/upgrade/migrations/ tests/specify_cli/migration/
uv run --frozen ruff format --check --force-exclude <every file you touched>
```

Confirm the FR-016 gate's real filename before running it (WP03 created it). Never run bare `tests/architectural/` or `make test-full`. Classify any unrelated red per the CLAUDE.md baseline-red gotcha.

## Risks & Mitigations

- **Selection for projects stamped above the target, or with the cutover already recorded** (T055 steps 4–5): a wedge between the WP14 gate and `upgrade`. Mitigation: WP10's version-independent selection and `structural_detect()` re-selection; test both here.
- **Byte churn in a 155 KB `charter.yaml`**: ruamel reflow breaks NFR-004 and reviewers' diffs. Mitigation: line-level edits + a test that compares untouched lines.
- **Partial move on Windows**: idempotent re-run; report moved paths; never delete a source before its target exists.
- **Legacy literals leaking into `src/`**: confined to the three modules; gate exemptions by file, logged for WP25.

## Definition of Done

- [ ] `detect()` and `structural_detect()` are total: they never raise. They run on every `spec-kitty upgrade` of every project (WP10 review), so an unreadable or malformed file makes them return True (select) and `apply()` reports the problem with its remedy; a test plants a malformed `config.yaml` and asserts `detect()` returns True and `apply()` fails with a named error instead of the selector raising.

- [ ] First commit removed only the WP11 `pending_until` markers and showed them red (output in the Activity Log).
- [ ] Every WP11 inventory row is rewritten with a report line; second `apply()` changes 0 bytes; `detect()` False after.
- [ ] Collision preflight refuses with every path named and writes nothing.
- [ ] `detect_legacy_charter_layout` exists, imports no `charter.*`, never reads `charter.yaml`.
- [ ] This repository's tree moved, `.gitignore` clean, the `ci-router.yml` legacy filter dropped, readers still see the project artifacts.
- [ ] `structural_detect()` implemented (structural findings only); resets recorded as first-application-only; the recorded-then-replanted test passes.
- [ ] Ordering verified (cutover first); the stamped-above-target case tested and its outcome recorded.
- [ ] All commands in Test Strategy pass; mypy and ruff (check + format with `--force-exclude`) clean; complexity ≤ 15.
- [ ] Follow-up edits outside owned files (acceptance markers, `.gitignore`, FR-016 gate exemption list) each logged with a one-line rationale.

## Review Guidance

- Verify red-on-base → green-on-final for every test that carried `pending_until("WP11")`: check out the first commit and see them fail, then the final commit and see them pass. The Windows case is exempt (recorded); `test_fr012_user_path_values_untouched` is an unmarked regression guard.
- Check the report dict shape and the `MigrationResult` mapping against `contracts/upgrade-migration.md`.
- Check that no step writes in dry-run (tree hash compare in tests).
- Check no legacy-aware reader (`load_pack_registry`, `load_governance_config`, `TrackerProjectConfig.from_dict`) is used by the migration.
- Check the repo move commit: renames only, 14 files, no content change.
- Confirm mypy/ruff were run on the touched sources, not just pytest.

## Activity Log

> Entries in chronological order (oldest first). Format: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>`.

- 2026-10-06T19:30:00Z – system – Prompt created.
- 2026-10-07T11:27:06Z – claude – shell_pid=5893 – Red-first (beb12b26): removed the 9 WP11 pending_until markers (test_upgrade_migration.py x8 incl. US2-7 lane test, test_package_split.py::test_fr010_charter_pack_id_in_project_state); run: 16 failed, 1 passed (user-path regression guard), 1 skipped (windows_ci, win32-only: exempt from red-first; POSIX lock simulated in test_charter_pack_cutover_paths.py). Implementation c3533915/cf6a5065/dd524ba4: predicate specify_cli/migration/legacy_charter_layout.py (no charter.* import, never reads charter.yaml, 25us on this repo), report module, m_4_0_0rc6_charter_pack_cutover.py (runs_first, runs_on_worktrees=False, detect/structural_detect total, is_first_application hook for WP12). Dry-run on this repo: 14 moves, nothing else. Real run (51b8de99): 14 renames, 0 content change; detect/structural False after; second apply 0 lines. Readers: charter list --json identical before/after; calibration overlays resolve under .kittify/charter-packs with no legacy warning. Follow-ups outside owned files (logged): runner.py does not record a failed runs_first result (collision test requires 0 bytes changed, incl. metadata.yaml); FR-016 gate exemption for legacy_charter_layout.py + missing-file tolerance removed (WP25 FR-018 must exempt legacy_charter_layout.py and _charter_pack_cutover_report.py-style helpers); routed-module pin + no-dead-modules allowlist; ci-router.yml/ci_retirement_scrub.json/VESTIGIAL row/tests/ci corpus paths; 9 NFR-004 params unmarked from WP12 (strict XPASS, no reset rows). Pre-existing reds not mine: FR-016 gate on charter/offering/packs/retired_fields.py 'org-charter.yaml' (WP17xWP03), pinning_rule_inventory stale (test_pyproject_shape.py lines), corpus snapshot parity (live mission), test_mission_corpus_recovery (shallow history).
- 2026-10-07T12:56:07Z – python-pedro – Cycle 2 fixes: (1) callerless names private, no allowlist entry; (2) cutover tests import datetime via kernel.clock; (3) unreadable .gitignore (symlink/non-UTF-8/dir/EACCES) is kept_for_review, never actionable, write failure a named error; (4) predicate total under EACCES via os.lstat + new unreadable_project_root finding, apply() names it; (5) kept config key (charter_packs not a mapping) no longer re-selects a recorded cutover (CONFIG_KEY_FINDINGS confirmed by dry run). Commits 1c1f640f b191c5a1 228405cc 0c8d5785 afd02da2.
