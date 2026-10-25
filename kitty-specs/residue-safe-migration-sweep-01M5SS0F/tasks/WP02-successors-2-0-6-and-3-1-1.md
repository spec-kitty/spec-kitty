---
work_package_id: WP02
title: Successor plumbing and the 2.0.6 / 3.1.1 successors
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- C-002
- C-006
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Supersession
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/specify_cli/upgrade/migrations/_residue_successor.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
- tests/specify_cli/upgrade/test_residue_safe_successors_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/registry.py
- src/specify_cli/upgrade/supersession.py
- src/specify_cli/upgrade/migrations/_residue_successor.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- tests/specify_cli/upgrade/test_residue_safe_successors_6669.py
- tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Successor plumbing and the 2.0.6 / 3.1.1 successors

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `2.0.6_consistency_sweep` and `3.1.1_normalize_status_json` are listed in `SUPERSEDED_MIGRATIONS`. Each has a residue-aware successor registered under a new id:
  - `2.0.6_residue_safe_consistency_sweep`
  - `3.1.1_residue_safe_normalize_status_json`
- Each successor:
  - performs every repair its predecessor performs on folders that are **not** residue (FR-005);
  - never touches a residue folder, and adds one `RESIDUE_NOTICE` warning per skipped folder (FR-004, FR-008);
  - sits immediately after its predecessor in `order_manifest.txt`, with the same `target_version` and a `# tie:` annotation (FR-006);
  - returns False from `detect()` when the predecessor is settled in the **selection view** (FR-007): a ledger `success`, OR an id that a pending first-adoption backfill will settle. Live and `--dry-run` therefore agree.
- `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` prints nothing (NFR-001).
- Requirement refs: FR-004, FR-005, FR-006, FR-007, NFR-001, C-002, C-006.

## Context & Constraints

- Read the spec (US2, FR-004 to FR-007, C-002, C-006), `plan.md` (IC-02), `research.md` (R-01 to R-03, R-06) and `data-model.md` ("Successor migration", "Ledger states").
- Read ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` Amendment 2026-10-25, `src/specify_cli/upgrade/supersession.py`, `src/specify_cli/upgrade/registry.py` (`get_applicable`, `migration_settled`, `_pending_adoption_ids`), and the precedent `m_4_0_0rc6_charter_pack_cutover._is_first_application`.
- **DIRECTIVE_044**: never edit an existing `m_*.py`. Import the frozen helpers. `m_3_2_0a4_safe_globalize_commands` already imports from a shipped module.
- Residue is decided only by `specify_cli.context.mission_resolver.is_kitty_specs_residue` (WP01). Use a batched `tracked = tracked_mission_paths(project_path)` per walk.
- Keep each successor's `runs_on_worktrees`, `requires_git_repository` and `clone_local_effect` equal to its predecessor's.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

> Populated by finalize-tasks; lanes come from `lanes.json`.

```bash
spec-kitty agent action implement WP02 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T006 – Shared successor plumbing (`_residue_successor.py`, plus one public registry helper)

- **Purpose**: the four successors (two here, two in WP03) share the settled view, the residue filter and the notice. They must not each carry a copy.
- **Steps**:
  1. In `src/specify_cli/upgrade/registry.py`, add a public `settled_in_selection_view(project_path: Path, migration_id: str) -> bool`. It must use exactly the predicate `get_applicable` uses: `migration_settled(ledger, m) or m.migration_id in _pending_adoption_ids(ledger, [all declared], project_path)`. Refactor `get_applicable` to call the same internal expression, so the two cannot drift. Resolve the migration with `get_by_id`; it returns the superseded substitute, which keeps the id. If the id is unknown, return False.
  2. Create `src/specify_cli/upgrade/migrations/_residue_successor.py` with:
     - `predecessor_settled(project_path, predecessor_id) -> bool`, delegating to the registry helper;
     - `non_residue_dirs(kitty_specs_root: Path, project_path: Path) -> tuple[list[Path], list[Path]]`, which walks children once and returns `(missions, residue)` using `is_kitty_specs_residue(..., repo_root=project_path, tracked=tracked)`;
     - `residue_warnings(residue: list[Path]) -> list[str]` using `RESIDUE_NOTICE`.

     The module is private (leading underscore) and is not a migration, so auto-discovery must not import it as one. Check how `migrations/__init__.py` discovers modules (prefix `m_`?) and confirm.
- **Files**: `registry.py`, `_residue_successor.py`.
- **Notes**: watch the import direction. `registry` must not import migration modules at import time; keep lazy imports, as the module already does.

### Subtask T007 – `2.0.6_residue_safe_consistency_sweep`

- **Purpose**: the 2.0.6 repairs, minus residue.
- **Steps**:
  1. New module `m_2_0_6_residue_safe_consistency_sweep.py` with `@MigrationRegistry.register class ResidueSafeConsistencySweepMigration(BaseMigration)`:
     - `migration_id = "2.0.6_residue_safe_consistency_sweep"`, `target_version = "2.0.6"`;
     - the `description` says it supersedes 2.0.6.
  2. `detect()`: return False if `predecessor_settled(project_path, "2.0.6_consistency_sweep")`. Otherwise mirror 2.0.6's `detect` (`check_stale_legacy_assets`, `_has_legacy_worktree_assets`, `_feature_requires_repair` over **non-residue** folders only). Residue alone does not make `detect()` True.
  3. `can_apply()`: same as 2.0.6.
  4. `apply()`: mirror 2.0.6's `apply` (`_migrate_runtime_assets`, `_cleanup_legacy_worktree_assets`, then `_repair_feature` per non-residue folder), then append `residue_warnings(residue)`. Keep the "Project already consistent for 2.0.6" change line semantics.
  5. Import the private helpers from `.m_2_0_6_consistency_sweep`; it is frozen, so do not touch it.
- **Notes**: every writer stays inside the frozen module, so the write-site gates should see no new site. Verify T010's gate runs.

### Subtask T008 – `3.1.1_residue_safe_normalize_status_json`

- **Purpose**: 3.1.1's `materialized_at` normalisation, minus residue.
- **Steps**:
  1. New module, `migration_id = "3.1.1_residue_safe_normalize_status_json"`, `target_version = "3.1.1"`.
  2. `detect()`: False if the predecessor is settled; otherwise `any(_needs_normalisation(d) for d in missions)`, importing `_needs_normalisation` from the frozen module.
  3. `apply()`: the same loop as the frozen `apply()` over non-residue folders, plus residue warnings. The write is inline in the frozen module, so the successor writes `status.json` itself; replicate it exactly (`sort_keys=True, indent=2, ensure_ascii=False` plus a trailing newline).
  4. Run the write-site gates now: `tests/architectural/test_status_events_writes_gate.py`, `tests/architectural/test_mutation_ownership_routing.py`, `test_generated_writer.py`, `test_byte_identity_mapping.py`, and any gate that enumerates `status.json` writers (`git grep -ln "SNAPSHOT_FILENAME\|status.json" tests/architectural`). If one fires, add the narrowest entry with a one-line rationale ("residue-safe successor of the frozen 3.1.1 writer; same bytes"). Otherwise add nothing.
- **Notes**: `3.1.1_normalize_status_json` is the 4th of four tied 3.1.1 entries in the manifest; insert the successor right after it.

### Subtask T009 – Supersession entries and manifest ties

- **Steps**:
  1. In `supersession.py` `SUPERSEDED_MIGRATIONS`, add `"2.0.6_consistency_sweep": "2.0.6_residue_safe_consistency_sweep"` and `"3.1.1_normalize_status_json": "3.1.1_residue_safe_normalize_status_json"`, each with a comment citing #6669.
  2. In `order_manifest.txt`, insert each successor immediately after its predecessor: `2.0.6_residue_safe_consistency_sweep  # tie: residue-safe successor of 2.0.6_consistency_sweep (#6669); same slot so 3.0.0/3.2.0a4 see its baseline meta.json`. Add the analogous line for 3.1.1.
  3. Run `tests/architectural/test_migration_order_manifest.py`.

### Subtask T010 – Registry- and runner-driven tests

- **File**: `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py` (`git_repo` marker). **Never construct a shipped class directly**: use `MigrationRegistry.get_by_id(...)` or `MigrationRunner(project).upgrade(...)`.
- **Cases**:
  1. `get_by_id("2.0.6_consistency_sweep")` and `get_by_id("3.1.1_normalize_status_json")` are `SupersededMigration` substitutes whose `detect()` is False.
  2. **2.0.6 repair parity**: port every scenario of `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` to run through the successor (resolved via the registry), and assert the same repairs.
  3. **Residue untouched**: a tracked project with a residue folder for each of the five shapes keeps every byte after the successor's `apply()`. The warnings name each folder once.
  4. **Settled gate**: with a ledger `success` record for `2.0.6_consistency_sweep`, the successor's `detect()` is False and a full `MigrationRunner.upgrade` changes no Mission file. Without the record, it repairs.
  5. **Dry-run parity**: a pre-ledger project stamped at a version above 2.0.6, with 2.0.6 in `applied_migrations` (`metadata.yaml`), gives a dry-run `upgrade` that previews no successor work. The live run does no successor work either.
  6. **3.1.1**: a real Mission with a stale `materialized_at` is normalised; a residue `status.json` is not.
  7. **Order**: the successor index is predecessor index + 1 in `order_manifest.txt`.
- Use `tmp_path` git repos; reuse helpers from `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` where possible.

### Subtask T011 – Extend the #6589 supersession pins

- Extend the parametrization in `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` (carried attributes, byte-identical `content_hash`, successor after superseded, successor not itself superseded) with the two new ids. If the test is too gitignore-specific, factor the generic pins into a parametrized test over `SUPERSEDED_MIGRATIONS.items()`, so WP03 inherits them for free.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py tests/architectural/test_migration_order_manifest.py tests/specify_cli/upgrade/test_requires_git_repository_audit.py -q
uv run --frozen pytest tests/specify_cli/upgrade tests/upgrade -n 8 --dist loadfile -q   # blast radius; classify reds per AGENTS.md before acting
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'   # must be empty
uv run --frozen mypy --strict src/specify_cli/upgrade/registry.py src/specify_cli/upgrade/supersession.py src/specify_cli/upgrade/migrations/_residue_successor.py src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
```

Known environmental reds: `tests/upgrade/test_mission_corpus_recovery.py` needs historical commit `c0054153` (shallow clone). Some upgrade CLI tests refuse while the source tree is dirty, so commit first.

## Risks & Mitigations

- **Selection-view drift**: `get_applicable` and the helper must share one expression (T006).
- **Write-site gates**: run them in T008.
- **C-006** (accepted residual): a pre-ledger project with 2.0.6 `failed` is adoption-settled. Write a test that **documents** this (xfail is not allowed; assert the current behaviour with a comment citing C-006).

## Review Guidance

- Confirm that no shipped module changed (NFR-001 command).
- Confirm that the tests resolve classes via the registry or runner only.
- Confirm that `settled_in_selection_view` and `get_applicable` share the predicate.
- Confirm that mypy strict and ruff ran clean.

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "..."`, `spec-kitty agent tasks move-task WP02 --to <status>`, `spec-kitty agent tasks status`.
