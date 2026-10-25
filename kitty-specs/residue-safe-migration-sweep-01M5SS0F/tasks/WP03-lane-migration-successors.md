---
work_package_id: WP03
title: Four residue-aware successors and their registry gates
dependencies:
- WP02
- WP05
requirement_refs:
- FR-004
- FR-005
- FR-006
- FR-007
- FR-013
- NFR-001
- C-002
- C-006
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-residue-safe-migration-sweep-01M5SS0F
base_commit: 4803291702c379be22a936415a3637309f799d1e
created_at: '2026-10-25T18:28:05.079529+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Supersession
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-10-25T16:40:00Z'
  actor: claude
  action: 'Re-cut after the post-tasks adversarial review: all four successors plus every registry gate they touch, so no WP leaves the tree red'
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py
- src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
- tests/specify_cli/upgrade/test_residue_safe_successors_6669.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/supersession.py
- src/specify_cli/upgrade/migrations/order_manifest.txt
- src/specify_cli/upgrade/migrations/m_0_9_0_residue_safe_frontmatter_only_lanes.py
- src/specify_cli/upgrade/migrations/m_0_9_1_residue_safe_complete_migration.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_3_1_1_residue_safe_normalize_status_json.py
- tests/specify_cli/upgrade/test_residue_safe_successors_6669.py
- tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py
- tests/architectural/test_no_dead_modules.py
- tests/architectural/test_migration_walkers_use_mission_predicate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Four residue-aware successors and their registry gates

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

- Four shipped migrations are listed in `SUPERSEDED_MIGRATIONS` (FR-004), each with a residue-aware successor:

  | Superseded (frozen, never edited) | Successor (new) | Shape |
  |---|---|---|
  | `0.9.0_frontmatter_only_lanes` | `0.9.0_residue_safe_frontmatter_only_lanes` | subclass of the shipped class |
  | `0.9.1_complete_migration` | `0.9.1_residue_safe_complete_migration` | subclass of the shipped class |
  | `2.0.6_consistency_sweep` | `2.0.6_residue_safe_consistency_sweep` | re-walk over the frozen helpers |
  | `3.1.1_normalize_status_json` | `3.1.1_residue_safe_normalize_status_json` | re-walk over the frozen helpers |

- Each successor must:
  - repair every folder its predecessor repairs, as long as the folder is **not** residue (FR-005);
  - leave every residue folder byte-identical, under main `kitty-specs/` and under `.worktrees/*/kitty-specs/`, and add one notice per skipped folder via `_residue_successor.residue_warnings`;
  - sit immediately after its predecessor in `order_manifest.txt`, with the same `target_version` and a `# tie:` annotation (FR-006);
  - return False from `detect()` when `predecessor_settled(...)` holds (FR-007). Residue alone never makes `detect()` True;
  - keep the predecessor's `runs_on_worktrees`, `requires_git_repository` and `clone_local_effect`.
- These gates stay green **in this WP**:
  - `tests/architectural/test_migration_order_manifest.py`, `tests/upgrade/test_order_manifest.py` and `tests/upgrade/test_auto_discovery.py`, including clear plus re-discover.
  - `tests/architectural/test_no_dead_modules.py`: add the four new `m_*` successors to `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`, and remove every shipped module that gains a caller (`m_0_9_0_frontmatter_only_lanes`, `m_2_0_6_consistency_sweep` and `m_3_1_1_normalize_status_json`, plus `m_0_9_1_complete_lane_migration` if it is listed). The ratchet fails on stale entries.
  - `tests/architectural/test_migration_walkers_use_mission_predicate.py`: every new walker site is in the inventory, and the whole inventory is reclassified under the new rule (FR-013; see T014).
- `git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'` prints nothing (NFR-001).
- Requirement refs: FR-004, FR-005, FR-006, FR-007, FR-013, NFR-001, C-002, C-006.

## Context & Constraints

- **Dependencies.** WP01 provides the rule and the notice. WP02 provides `predecessor_settled`, `partition_kitty_specs` and `residue_warnings`. WP05 makes the shared walkers residue-aware, so T014's `_FILTERS` labels for them are true when written.
- **Rediscovery trap (verified by probe).** `migrations/__init__.py:74-87` skips reloading a module whose `dir(module)` holds a class whose `migration_id` is already registered. A successor that does `from .m_0_9_0_frontmatter_only_lanes import FrontmatterOnlyLanesMigration` therefore vanishes after `MigrationRegistry.clear()` plus `auto_discover_migrations()`.
  - **Import the shipped module as an alias**: `from . import m_0_9_0_frontmatter_only_lanes as _shipped`, then subclass `_shipped.FrontmatterOnlyLanesMigration`.
  - For 2.0.6 and 3.1.1, import only module-level helper functions (safe), never the migration classes.
  - See `tests/_support/migration_registry.py:27-29`.
- **Walker gate visibility.** `_find_raw_walker_calls` sees `iterdir`, `glob` and `scandir` called on a tainted name: `kitty_specs`, `main_specs`, `wt_specs`, `specs_dir` and the like, or a name assigned from `KITTY_SPECS_DIR` or `"kitty-specs"`. It never sees `rglob`. Name every new walker variable from `_SPECS_NAME_VOCABULARY` (e.g. `kitty_specs`, `wt_specs`) so the gate sees it and its `_FILTERS` label is not vacuous.
- **0.9.0 / 0.9.1 shapes (frozen modules).**
  - `FrontmatterOnlyLanesMigration`: the per-folder predicate `_is_legacy_format` is used by `detect` and `_find_features_to_migrate`.
  - `CompleteLaneMigration` (id `0.9.1_complete_migration`):
    - `_has_remaining_lane_dirs` is used by `detect` part 1 and `_find_features_with_lanes`;
    - `_normalize_all_frontmatter` collects every `*.md` under `kitty-specs/` and the worktree specs with `rglob`, then writes through the shared `specify_cli.frontmatter.normalize_file`;
    - its worktree clean-up (agent dirs, `.kittify/scripts`) stays unchanged.
- **Cost.** In the predicate overrides, call `super()._is_legacy_format(...)` (or `_has_remaining_lane_dirs`) **first**, then `is_kitty_specs_residue`. A folder that is not legacy then costs no git call.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep
- Execution worktrees are allocated per computed lane from `lanes.json`.

```bash
spec-kitty agent action implement WP03 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T009 – `2.0.6_residue_safe_consistency_sweep`

- Create a new module with `@MigrationRegistry.register class ResidueSafeConsistencySweepMigration(BaseMigration)`, `migration_id = "2.0.6_residue_safe_consistency_sweep"` and `target_version = "2.0.6"`.
- From `.m_2_0_6_consistency_sweep`, import the frozen helpers `_migrate_runtime_assets`, `_cleanup_legacy_worktree_assets`, `_has_legacy_worktree_assets`, `_feature_requires_repair` and `_repair_feature`. Import `check_stale_legacy_assets` from the module that defines it.
- `detect()` returns False if `predecessor_settled(p, "2.0.6_consistency_sweep")`. Otherwise it mirrors 2.0.6's `detect` over **non-residue** folders, using `partition_kitty_specs(p / KITTY_SPECS_DIR, p)` with the local name `kitty_specs`.
- `can_apply()` is the same as 2.0.6's.
- `apply()` mirrors 2.0.6 over the Mission folders, then appends `residue_warnings(residue, p)`. The "Project already consistent for 2.0.6" line keeps its meaning.

### Subtask T010 – `3.1.1_residue_safe_normalize_status_json`

- Use `_needs_normalisation` from the frozen module, and replicate the inline `status.json` write exactly: `json.dumps(current, sort_keys=True, indent=2, ensure_ascii=False) + "\n"`.
- Run the write-site gates now:
  - `tests/architectural/test_status_events_writes_gate.py`
  - `tests/architectural/test_mutation_ownership_routing.py`
  - `tests/architectural/test_generated_writer.py`
  - `tests/architectural/test_byte_identity_mapping.py`
  - any file listed by `git grep -ln "SNAPSHOT_FILENAME" tests/architectural`
- If a gate fires, add the narrowest entry with a one-line rationale ("residue-safe successor of the frozen 3.1.1 writer; same bytes"), and record that gate file in this WP's history as an out-of-map edit.

### Subtask T011 – `0.9.0_residue_safe_frontmatter_only_lanes` and `0.9.1_residue_safe_complete_migration`

- Subclass through the module alias (see the rediscovery trap).
- **0.9.0** overrides:
  - `_is_legacy_format`: super first, then the residue check;
  - `detect`: the settled gate, then `super().detect`;
  - `apply`: `super().apply()` plus residue warnings, from a walk over the main and worktree specs that uses tainted names.
- **0.9.1** overrides:
  - `_has_remaining_lane_dirs`: super first, then the residue check;
  - `detect`: the settled gate;
  - `_normalize_all_frontmatter`: re-implement only the file collection so that `*.md` under a residue folder is excluded. Normalise through `normalize_file` with the same dry-run comparison and the same change and warning strings.
  - `apply`: adds the residue warnings.
- Keep complexity ≤ 15 by extracting helpers. Do not copy the frozen `noqa: C901`.

### Subtask T012 – Supersession table and order-manifest ties

- Add the four entries to `SUPERSEDED_MIGRATIONS`, each commented `# #6669: residue-aware successor`.
- In `order_manifest.txt`, place each successor immediately after its predecessor: 0.9.0 and 0.9.1 at lines 30–31, 2.0.6 at line 61, 3.1.1 after line 84. Use the form `<id>  # tie: residue-safe successor of <predecessor> (#6669); same slot so later steps see its output`.

### Subtask T013 – `test_no_dead_modules` ratchet

- Add the four new modules to `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`, and remove the shipped modules that now have a caller. Run the gate to see exactly which entries are stale.

### Subtask T014 – Walker inventory (FR-013)

- Add every new walker site: the successors' `detect` and `apply`, and the residue-warning walks.
- Label the four superseded walkers with a new `_SUPERSEDED` label: "shipped migration registered as a no-op; its residue-aware successor walks instead". Add a test asserting that each `_SUPERSEDED` module's migration id is a key of `SUPERSEDED_MIGRATIONS`.
- Label the successors' walkers and WP05's two shared walkers `_FILTERS`; `test_filters_classification_is_true` must pass. Add `is_kitty_specs_residue` to `_PREDICATES` and the new seams to `_GUARDED_SEAMS`.
- Re-derive every `_REQUIRES_STATE` / `_REQUIRES_META` label under the new rule: a folder with `meta.json` is never residue, while one with only `status.json` or `tasks/` is. Where a label changed, write the reason as a comment. Remove `_GUARDED_IDENTITY_ONLY`.
- Document the detector's blind spots in the module docstring: `rglob`, untainted names, and constants such as `_KITTY_SPECS_DIRNAME`. The detector misses the `m_zz_runtime_state_backfill._iter_mission_dirs` walker, so list it by hand with a comment (it walks through `cutover_mission`, which is guarded).

### Subtask T015 – Successor tests (registry- and runner-driven)

- **File**: `tests/specify_cli/upgrade/test_residue_safe_successors_6669.py` (uses `git_repo`). **Never construct a shipped class directly**, except as a parity oracle on a twin fixture.
- **Cases**:
  1. **Substitution.** For each superseded id, `get_by_id(...)` is a `SupersededMigration` whose `detect()` is False, and each successor id resolves. After `MigrationRegistry.clear()` plus `auto_discover_migrations()`, all four successors resolve again.
  2. **Repair parity.** Port every scenario of `tests/upgrade/migrations/test_m_2_0_6_consistency_sweep.py` and of the 0.9.0, 0.9.1 and 3.1.1 tests (`git grep -l "0_9_0\|0_9_1\|3_1_1_normalize" tests`). Run each through the successor via the registry and assert the same result. For 0.9.x, compare trees against the shipped class run on a twin fixture.
  3. **Residue untouched.** In a tracked project, five residue shapes stay byte-identical under main `kitty-specs/` and under `.worktrees/wt1/kitty-specs/`: a tasks WP, an event log, a `status.json`, a `tasks/doing/WP01-x.md` and a `decisions/` folder. The warnings name each one by project-relative path.
  4. **Fallback-mode repair (US2 scenario 3).** The 2.0.6 and 0.9.x successors repair a tasks-only pre-identity Mission in three projects: a non-git project, one with a gitignored `kitty-specs/`, and an untracked project nested in a parent repo.
  5. **Settled gate (US2 scenario 4).** With a ledger `success` for the predecessor, `detect()` is False. Through `MigrationRunner`, a live run changes nothing for that successor and `upgrade --dry-run` previews nothing.
  6. **Dry-run parity on adoption.** Use a pre-ledger project stamped at **exactly 2.0.6**, with `2.0.6_consistency_sweep` in `applied_migrations`. Assert that `get_applicable` **selects** the successor and that its `detect()` is False in both the dry run and the live run. A version above 2.0.6 would make the test vacuous, because adoption would settle the successor itself.
  7. **Worktree ledger.** In a non-integrating `.worktrees/wt1` whose own ledger records the predecessor as `success`, the successor does nothing there.
  8. **Superseded record (US2 scenario 5).** In a run where the successor applies, the runner records the shipped entry as `skipped`, with the "Superseded by …" note from `superseded_note`, in the same ledger.
  9. **C-006 (accepted residual).** A pre-ledger project with 2.0.6 `failed` at a version above it has its successor settled by adoption. Assert the current behaviour with a comment citing C-006; no xfail.
  10. **Order.** Each successor's index equals its predecessor's index + 1.
- Extend `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py`: parametrize its generic pins (carried attributes, byte-identical `content_hash`, successor after superseded, successor not itself superseded) over `SUPERSEDED_MIGRATIONS.items()`.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py tests/architectural/test_migration_order_manifest.py tests/upgrade/test_order_manifest.py tests/upgrade/test_auto_discovery.py tests/architectural/test_no_dead_modules.py tests/architectural/test_migration_walkers_use_mission_predicate.py tests/architectural/test_mission_resolver_walker_gate.py tests/specify_cli/upgrade/test_requires_git_repository_audit.py tests/specify_cli/test_locked_frontmatter_writers.py -q
uv run --frozen pytest tests/specify_cli/upgrade tests/upgrade -n 8 --dist loadfile -q   # classify reds per CLAUDE.md; commit before running (dirty-tree refusals)
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'   # must print nothing
uv run --frozen mypy --strict src/specify_cli/upgrade/supersession.py src/specify_cli/upgrade/migrations/m_*_residue_safe_*.py
```

Known environmental red: `tests/upgrade/test_mission_corpus_recovery.py`, because the shallow clone lacks `c0054153`.

## Risks & Mitigations

- **Rediscovery trap**: mitigated by the alias import and checked by T015 case 1.
- **A missed 0.9.1 walker**: mitigated by the T014 inventory, plus an AST test that lists every method of `CompleteLaneMigration` that walks `kitty-specs` and asserts it is overridden or reached only through an overridden predicate.
- **Write-site gates**: covered by T010.

## Review Guidance

- Confirm the NFR-001 command prints nothing, the tests go through the registry or the runner, and clear plus re-discover works.
- Confirm no `noqa` was copied, the walker variables use tainted names, and the gate labels are true.

## Progress & Status

- `spec-kitty agent tasks add-history WP03 --note "..."`, `spec-kitty agent tasks move-task WP03 --to <status>`, `spec-kitty agent tasks status`.
