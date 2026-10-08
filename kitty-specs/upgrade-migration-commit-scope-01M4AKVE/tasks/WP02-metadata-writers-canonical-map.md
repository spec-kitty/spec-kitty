---
work_package_id: WP02
title: Metadata writers keep every key and stamp the canonical capability map
dependencies:
- WP01
requirement_refs:
- FR-011
- NFR-001
- C-001
- C-004
planning_base_branch: fix/upgrade-migration-commit-scope
merge_target_branch: fix/upgrade-migration-commit-scope
branch_strategy: Planning artifacts for this mission were generated on fix/upgrade-migration-commit-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/upgrade-migration-commit-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-migration-commit-scope-01M4AKVE
base_commit: d3b1b06798a243dbd72b890fad8e9a274a63d673
created_at: '2026-10-07T14:59:20.983857+00:00'
subtasks:
- T011
- T012
- T013
- T006
- T014
phase: Phase 2 - Same rule, other writers
history:
- at: '2026-10-07T12:21:08Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/metadata.py
create_intent:
- tests/upgrade/test_metadata_writers_5229.py
- tests/upgrade/test_metadata_final_file_5229.py
- tests/specify_cli/migration/test_runner_schema_stamp_5229.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/upgrade/metadata.py
- src/specify_cli/migration/backfill_identity.py
- tests/upgrade/test_metadata_schema_roundtrip.py
- tests/upgrade/test_metadata_writers_5229.py
- tests/upgrade/test_metadata_final_file_5229.py
- tests/specify_cli/migration/test_runner_schema_stamp_5229.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5229'
---

# Work Package Prompt: WP02 – Metadata writers keep every key and stamp the canonical capability map

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission upgrade-migration-commit-scope-01M4AKVE`). Address every feedback item before completing.

---

## Objectives & Success Criteria

- **FR-011** (#5229): after `spec-kitty upgrade` on a legacy (pre-schema-3) project, the FINAL `.kittify/metadata.yaml` carries `spec_kitty.schema_version == CURRENT_SCHEMA_VERSION`, `spec_kitty.schema_capabilities` as the canonical `dict[str, bool]` map (a legacy list converted, operator values kept), `spec_kitty.project_uuid`, and every operator key the file had before the run (top level and inside `spec_kitty`).
- Every writer this WP changes is **merge-preserving and atomic**: `ProjectMetadata.save()`, `MigrationRunner._stamp_schema_version()`, `backfill_project_uuid()`, and (T006, moved here from WP01) the schema-3 migration's `_update_schema_version` in `migration/runner.py`.
- US6 scenario 1 holds; a fresh-`init` project (which already carries the canonical map) keeps it across its first upgrade (today the upgrade strips it).
- C-004: a `regression` test is red on the planning base before the fix commit, through the pre-existing entry point (`spec-kitty upgrade`), and green at the end.
- NFR-001: the existing metadata, version-stamp and schema-recovery suites stay green with no assertion weakened.

## Context & Constraints

- Spec: `kitty-specs/upgrade-migration-commit-scope-01M4AKVE/spec.md` (US6, FR-011); plan IC-02; lens A M4 in `<operator-local squad notes>` ("keys lost ... #5229-class, not P0. Fix: merge-preserving atomic ProjectMetadata.save(); reuse init's _stamp_schema_metadata rule; test the final file after `spec-kitty upgrade`").
- **`src/specify_cli/migration/runner.py` — one recorded out-of-map edit (T006)**: WP01 owns the file and ships it in PR 1; Decision `01M4B6G3J0YNZ57WSHJXDMJS6N` (do not reopen) moved the runner-side #5229 write (`_update_schema_version` + `_TARGET_SCHEMA_VERSION`/`_TARGET_SCHEMA_CAPABILITIES`) from WP01 to this WP, in PR 2, **after** WP01 — hence `dependencies: [WP01]`. Touch nothing else in that file (WP01's step-10 removal, rollback hygiene and shim ordering are WP01's); line numbers below are `origin/main` and have moved after WP01 — locate by symbol. Record the out-of-map edit and its rationale in the Activity Log. Do not edit `src/specify_cli/cli/commands/upgrade.py` (WP01) nor `init.py` (not in scope).
- **`src/specify_cli/upgrade/runner.py` — second recorded out-of-map edit (T013)**: WP01 owns this file (it gives the upgraded-worktree commit block, `_upgrade_worktrees`, the main-checkout rules in PR 1); this WP edits only `MigrationRunner._stamp_schema_version` (`origin/main` `:752-817`), **after** WP01 (already a dependency). It is deliberately NOT in this WP's `owned_files`. Touch nothing else in that file (the worktree commit block is WP01's); locate by symbol, since WP01 moves lines. Record the out-of-map edit and its rationale in the Activity Log.
- Do not edit any #5856 file: `upgrade/finalize.py`, `upgrade/outcome.py`, `tests/upgrade/test_finalizer.py`, `test_upgrade_auto_commit_unit.py`, `test_upgrade_outcome_kind.py`, `test_upgrade_outcome_rendering.py`.

### Writer order during `spec-kitty upgrade` on a legacy project (grounded on origin/main 5ee323802)

1. `MigrationRunner.upgrade` loads the legacy file into memory **before** any migration runs: `ProjectMetadata.load(self.kittify_dir)` at `src/specify_cli/upgrade/runner.py:203` (legacy file has no `schema_version` → `metadata.schema_version is None`).
2. `normalize_and_save_legacy_ids` (`upgrade/metadata.py:154-165`) may `save()` (rewrite from the fixed dict).
3. Migration `3.0.0_canonical_context` → `migration/runner.py::run_migration`: `backfill_project_uuid` (`src/specify_cli/migration/backfill_identity.py:252-290`, ruamel round-trip, plain `open(..., "w")` — **non-atomic**) adds `spec_kitty.project_uuid`; then `_update_schema_version` (`migration/runner.py:194-220`; rewritten by this WP's T006) adds `schema_version: 3` and the capability **list**.
4. After every applied migration `_record_migration_result` (`upgrade/runner.py:703-721`) calls `metadata.save()` → `ProjectMetadata.save` (`upgrade/metadata.py:180-256`) **rebuilds the whole file from a fixed dict** (`spec_kitty` = version/initialized_at/last_upgraded_at[/schema_version], `environment`, `migrations.applied`). This erases `project_uuid`, `schema_capabilities`, the freshly written `schema_version` (the in-memory model still says `None`) and every operator key.
5. `_finalize_main_metadata` (`upgrade/runner.py:723-749`): on success `save()` again, then `_stamp_schema_version(kittify_dir, REQUIRED_SCHEMA_VERSION)` (`upgrade/runner.py:752-817`) which only sets `spec_kitty.schema_version` (raw PyYAML round-trip, atomic, compare-before-write). On failure `VersionStamp.restore` (`metadata.py:365-416`).
6. Worktrees: same pair at `upgrade/runner.py:595` (`wt_metadata.save`) and `:603` (`_stamp_schema_version`). No-migrations path: `upgrade/runner.py:177-189` and `cli/commands/upgrade.py:712-729` (`_stamp_no_migrations_metadata`, WP01's file; it calls the same two methods, so it is fixed transitively).
7. `init` does the same pair: `cli/commands/init.py:1447` `metadata.save(...)` then `:1456` `_stamp_schema_metadata(...)` (`init.py:489-588`, ruamel, inserts the canonical map only when the key is absent, never merges into an existing map).

**Conclusion:** the last writers of the final file are `ProjectMetadata.save()` + `_stamp_schema_version()`, both changed by this WP (`save()` owned; `_stamp_schema_version()` a recorded out-of-map edit after WP01), so this WP's `regression` test on the final file goes green through T012/T013. T006 makes the intermediate runner write canonical too (the file a crash between step 3 and step 4 leaves behind, and the shape `run_migration` callers outside `spec-kitty upgrade` see). The dependency on WP01 exists only because T006 edits WP01's file (Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`); base this lane on WP01's merged commits.

- Constants: `src/specify_cli/migration/schema_version.py:30-57` — `SCHEMA_CAPABILITIES`, `CURRENT_SCHEMA_VERSION`, `CURRENT_SCHEMA_CAPABILITIES: dict[str, bool]` (the map init stamps). `REQUIRED_SCHEMA_VERSION` (`:27`) is what the runner stamps today; it equals `CURRENT_SCHEMA_VERSION` today — derive, never write a literal `3` in code or tests.
- Atomic write seam: `specify_cli.core.atomic.atomic_write(path, content, *, mkdir=False)` (`src/specify_cli/core/atomic.py:30`), already used by `save()` (`metadata.py:255`) and `_stamp_schema_version` (`runner.py:817`).
- Readers: nothing in `src/` reads `schema_capabilities` (lens A: identity is read from `config.yaml project.uuid`), so the map shape change has no runtime consumer to break; tests pin it (`tests/integration/test_init_fresh_project_chain.py:116`, `tests/specify_cli/cli/commands/test_init_schema_stamp.py:53`).
- Charter: ATDD-first — the red test commit lands before the fix commit; complexity ≤ 15 per function; ruff-format touched files; no full suites locally.

## Branch Strategy

- **Strategy**: (populated by finalize-tasks)
- **Planning base branch**: `fix/upgrade-migration-commit-scope`
- **Merge target branch**: `fix/upgrade-migration-commit-scope`

Execution worktrees are allocated per computed lane from `lanes.json`; use `spec-kitty agent action implement WP02 --agent claude`. This WP lands in PR 2 (Decision `01M4AYQTE5WGNXKW7411AVYP79`) and is based on WP01 (T006 edits `migration/runner.py` after WP01; Decision `01M4B6G3J0YNZ57WSHJXDMJS6N`).

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first `regression` tests: the final file after `spec-kitty upgrade`, plus writer units

- **Purpose**: pin #5229 through the pre-existing entry point so the fix is proven on the file an operator actually ends up with (lens A: "test the final file after `spec-kitty upgrade`").
- **Commit boundary**: T011 is committed ALONE first (`test(5229): red-first final metadata.yaml after upgrade`); record the red output in the Activity Log. The fix commits (T012, T013) follow.
- **Steps (real-git module `tests/upgrade/test_metadata_final_file_5229.py`)**:
  1. Module markers: `pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]`. Never `p0_repro` (this is not #5443).
  2. Fixture `legacy_project(tmp_path)`: model it on `tests/specify_cli/migration/test_runner.py:47-157` (`_make_legacy_project`): `.kittify/metadata.yaml` with `spec_kitty: {version: "2.1.0", initialized_at: ...}` and NO `schema_version`; add operator keys you will assert on: top-level `operator_note: keep-me` and `spec_kitty.custom_flag: true`; `.kittify/config.yaml` with a pinned agent config (`agents: {available: [claude]}`); one mission under `kitty-specs/` with a `meta.json` and one WP file; `.gitignore`. `git init -b work` (a non-protected branch name — never `main`/`master`), local `user.email`/`user.name`, `commit.gpgsign=false`, one commit.
  3. Environment: build an allowlisted env exactly like `tests/upgrade/preview_support/process.py::child_environment` (`:17-58`; import it rather than re-implementing, it isolates HOME, all XDG dirs, `SPEC_KITTY_HOME`, `GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL`), then add `SPEC_KITTY_NO_UPGRADE_CHECK=1` and `PYTHONPATH=<checkout>/src` where `<checkout> = Path(__file__).resolve().parents[2]`, and `PATH` that includes the directory of the `git` binary (`shutil.which("git")`). `PYTHONPATH=<checkout>/src` needs `<checkout>/packs/` beside `src/` (a lane worktree has it) — assert `(<checkout>/"packs").is_dir()`. Nothing from the parent `GIT_*` / `SPEC_KITTY_*` namespace may leak in — assert it in a one-line guard (`assert not [k for k in env if k.startswith("GIT_DIR")]`).
  4. Run `subprocess.run([sys.executable, "-m", "specify_cli", "upgrade", "--yes"], cwd=project, env=env, capture_output=True, text=True, timeout=300)`. Check `--yes` is the right confirm flag with `--help` on the planning base; do not use `--json` here (the text path is the operator path).
  5. Assertions, in this order (the first two make "red for the right reason" provable):
     - `result.returncode == 0`, message includes stdout+stderr. If the minimal fixture cannot upgrade cleanly, fix the fixture, not the assertion.
     - `"3.0.0_canonical_context"` appears in the final file's `migrations.applied[*].id` with `result == "success"` (proves the legacy migration really ran).
     - `spec_kitty.schema_version == CURRENT_SCHEMA_VERSION` (import the constant).
     - `isinstance(spec_kitty["schema_capabilities"], dict)` and `dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES`.
     - `spec_kitty["project_uuid"]` is a non-empty string (the value is generated during the run; also assert it equals the `project_uuid` the run printed or, simpler, that a second `spec-kitty upgrade --yes` leaves it byte-identical — a writer that regenerates it every run is a churn bug).
     - `data["operator_note"] == "keep-me"` and `spec_kitty["custom_flag"] is True`.
  6. Second test: a "fresh-init" shaped project (metadata already at `CURRENT_SCHEMA_VERSION` with the canonical map, where the operator flipped one capability to `false` and added `my_cap: true`) plus one applicable later migration (pick any always-applicable recent one by setting `spec_kitty.version` a few releases back, e.g. `"3.2.0"`; verify on the base that `upgrade` applies ≥ 1 migration so `_record_migration_result` → `save()` runs). Assert the map after upgrade still has the operator's `false` and `my_cap: True`. Red today (save strips the whole map).
- **Expected RED on the planning base**: returncode 0 and the migration recorded (assertions 1-2 pass), then `KeyError`/assertion on `schema_capabilities` and on `project_uuid` and `operator_note`. A failure in assertion 1 or 2 is a broken fixture, not a red.
- **Steps (unit module `tests/upgrade/test_metadata_writers_5229.py`, `pytestmark = [pytest.mark.unit, pytest.mark.fast]`, no subprocess, only `tmp_path`)** — each case names the mutant it kills:
  - `save()` keeps unknown keys: write a file with top-level `operator_note`, `spec_kitty.project_uuid`, `spec_kitty.custom_flag`, `spec_kitty.schema_capabilities` map; `load()`, `record_migration(...)`, `save()`; assert all four survive. Kills "save rebuilds from the fixed dict" (today's behaviour).
  - `save()` with model `schema_version is None` while the disk has a value (load a legacy file, then write `schema_version: <CURRENT>` to disk out-of-band, then `save()` the stale model): the disk value survives. Kills a mutant that pops `schema_version` whenever the model says `None` (that mutant re-creates #5229's "upgrade erased the stamp" mid-run).
  - `save()` with model `None` and no key on disk still writes no key (mirror of `tests/upgrade/test_metadata_schema_roundtrip.py:113-129`; keep that test as is). Kills a mutant that forges a stamp.
  - `save()` overwrites the fields the model owns: on-disk `spec_kitty.version: "old"`, model `version = "new"` → `"new"`; `migrations.applied` equals the model's list exactly (a removed record does not resurrect from disk). Kills a "disk wins" merge.
  - `save()` on an unparseable or non-mapping existing file falls back to writing the model (no exception, file parses afterwards).
  - Compare-before-write still skips a timestamp-only change (`_mask_volatile_metadata`, `metadata.py:23-45`): call `save()` twice with only `last_upgraded_at` advanced → second returns `False` and bytes unchanged. Kills a merge that always rewrites.
  - `_stamp_schema_version` (call `MigrationRunner._stamp_schema_version(kittify, CURRENT_SCHEMA_VERSION)`): (a) absent capabilities → map equal to `CURRENT_SCHEMA_CAPABILITIES`; (b) legacy list `["canonical_context", "event_log_authority", "ownership_manifest", "thin_shims", "custom_cap"]` → map with all listed names `True` (including `custom_cap`) — kills a converter that filters to known names; (c) existing map with `canonical_context: false` and `my_cap: true` → unchanged (operator owns an existing map, same as `init.py:572-580`) — kills a converter that overwrites values; (d) idempotent: second call leaves bytes and mtime unchanged — kills an always-write mutant.
  - Derivation, not literal: `monkeypatch.setattr(schema_version_module, "CURRENT_SCHEMA_CAPABILITIES", {**CURRENT_SCHEMA_CAPABILITIES, "probe_cap": True})` then stamp a file with no capabilities → `probe_cap` present. Kills a hard-coded list/map copy (the very drift #840 warned about, `schema_version.py:35-44`). This requires the helper to read the module attribute at call time (`from specify_cli.migration import schema_version as _sv; _sv.CURRENT_SCHEMA_CAPABILITIES`), not a module-level `from ... import` binding.
  - Parity with init: on an absent-capabilities file, the stamp's resulting `schema_capabilities` equals what `init._stamp_schema_metadata` produces on an identical copy (import `from specify_cli.cli.commands.init import _stamp_schema_metadata`). Kills divergence between the two stamp rules.
  - `backfill_project_uuid` writes atomically: `monkeypatch.setattr(backfill_identity, "atomic_write", spy)` → spy called exactly once with the metadata path, and the file is not opened for writing directly (patch `builtins.open` is too broad; the spy count plus content assertion suffices). Kills the plain `open(..., "w")` write.
- **Files**: two new test modules (~120 + ~200 lines).
- **Validation**: unit cases red on the base for: unknown keys, `None`-vs-disk, list conversion, derivation probe, parity, atomic spy; the "None writes no key" and compare-before-write cases are green on the base (they guard against over-correction — say so in their docstrings).

### Subtask T012 – Merge-preserving atomic `ProjectMetadata.save()` and atomic `backfill_project_uuid`

- **Purpose**: the writer that runs after every applied migration stops erasing keys it does not own (FR-011).
- **Steps**:
  1. In `src/specify_cli/upgrade/metadata.py:180-256`, split rendering from persistence: add `_model_owned_mapping(self) -> dict` returning exactly today's dict (`metadata.py:209-238`), and `_merge_onto_disk(existing: dict | None, owned: dict) -> dict`:
     - start from a deep copy of the existing on-disk mapping (parse with `yaml.safe_load(read_text("utf-8-sig"))`; `None`, unreadable or non-mapping → `{}`);
     - `spec_kitty` block: keep every existing key, overwrite `version`, `initialized_at`, `last_upgraded_at` from the model; `schema_version` only when the model's value is not `None` (when `None`, leave whatever the disk has — see T011 cases);
     - `environment`: overwrite the three model keys, keep any other key in the block;
     - `migrations.applied`: replace with the model's list (the model is the authority for the applied record — keep any other key under `migrations`);
     - every other top-level key: untouched;
     - preserve the existing key order (dict insertion order) and append new keys at the end of their block, so a no-op save renders byte-identically to a previous save.
  2. Keep the header (`metadata.py:240-242`), PyYAML `default_flow_style=False, sort_keys=False`, the masked compare-before-write (`:247-253`), and `atomic_write(..., mkdir=True)` (`:255`). Reuse the module-level `_METADATA_HEADER` (`:307`) instead of the inline copy in `save()` (campsite: one header constant).
  3. Update the `save()` docstring: merge-preserving; which keys the model owns; `schema_version=None` neither forges nor erases.
  4. `VersionStamp._patch_trio`/`restore` (`metadata.py:365-416`) already patch only the trio into the current content — leave them; run `tests/upgrade/test_metadata_version_stamp.py` to prove it.
  5. `src/specify_cli/migration/backfill_identity.py:282-288`: replace `open(metadata_path, "w") ... y.dump(data, fh)` with dumping into a `io.StringIO` and `atomic_write(metadata_path, buf.getvalue())` (import `atomic_write` at module level from `specify_cli.core.atomic` so the T011 spy can patch it). Behaviour otherwise unchanged (ruamel round-trip keeps comments).
  6. `tests/upgrade/test_metadata_schema_roundtrip.py`: keep every existing test; if one pinned the lossy shape (none expected — `:80-129` assert preservation), adjust only that assertion and say why in the Activity Log.
- **Files**: `upgrade/metadata.py`, `migration/backfill_identity.py`.
- **Validation**: T011 unit `save()` cases green; `pytest tests/upgrade/test_metadata_schema_roundtrip.py tests/upgrade/test_metadata_version_stamp.py tests/upgrade/test_schema_version_recovery.py tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py -q` green. `test_schema_version_recovery.py:179-213` monkeypatches `save` with an erasing double — it must stay green (the restore authority is `VersionStamp`, untouched).
- **Edge cases**: a file whose `spec_kitty` is not a mapping (e.g. a string) → replace the block with the model's; `migrations` not a mapping → replace; keep `utf-8-sig` read.

### Subtask T013 – `_stamp_schema_version` stamps the canonical capability map

- **Purpose**: every upgrade path (main, no-migrations, worktree) ends with `schema_version` and the canonical map (US6 scenario 1), derived from `CURRENT_SCHEMA_CAPABILITIES`.
- **Steps**:
  1. In `upgrade/metadata.py` add a pure helper `canonical_schema_capabilities(existing: object) -> dict[str, bool]` (export it in the module's public names if the module declares `__all__`; it does not today — do not add one only for this):
     - `existing` absent/`None` → `dict(_sv.CURRENT_SCHEMA_CAPABILITIES)` (read at call time, see T011 derivation case);
     - a list/tuple of names → `{str(name): True for name in existing}` plus any missing `CURRENT_SCHEMA_CAPABILITIES` key set to its canonical value (a legacy list is spec-kitty-written, so completing it is safe);
     - a mapping → returned unchanged (operator owns it; same rule as `init.py:572-580` "insert the canonical map only if entirely missing ... do NOT merge into it");
     - anything else (string, int) → the canonical map (a malformed value is not operator intent; note it with `logger.warning` in the caller).
  2. In `upgrade/runner.py:752-817` (`_stamp_schema_version`), after `data["spec_kitty"]["schema_version"] = schema_version` (`:800`), set `data["spec_kitty"]["schema_capabilities"] = canonical_schema_capabilities(data["spec_kitty"].get("schema_capabilities"))`. Keep the compare-before-write (`:808-815`) so an already-canonical file is not rewritten. Update the docstring ("Write `schema_version` and the canonical `schema_capabilities` map ...") and the stale comments that say the stamp must follow `save()` "because save() does not preserve unknown keys" (`runner.py:181-188`, `:596-597`, `:733-735`) — after T012 the ordering still matters for `schema_version` on a legacy in-memory model, so reword, do not delete the ordering.
  3. Do NOT touch `cli/commands/init.py`; the T011 parity test keeps the two rules aligned. `migration/runner.py` is T006's (below), not this subtask's.
  4. Keep `_stamp_schema_version` a `@staticmethod` with the same signature: `cli/commands/upgrade.py:728` calls `MigrationRunner._stamp_schema_version(kittify_dir, REQUIRED_SCHEMA_VERSION)`.
- **Files**: `upgrade/metadata.py`, `upgrade/runner.py` (recorded out-of-map edit after WP01, `_stamp_schema_version` only).
- **Validation**: T011 stamp cases + both real-git final-file tests green; `pytest tests/upgrade/test_schema_version_recovery.py tests/upgrade/test_runner_status_classification.py tests/specify_cli/cli/commands/test_init_schema_stamp.py tests/integration/test_init_fresh_project_chain.py -q` green.
- **Mutants to reason about in review**: stamping the map only on the main path (worktree `:603` and no-migrations `:189` share the method, so a per-call-site fix would leave them red — the T011 unit tests call the method directly, and add one worktree-path assertion if `tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py` gives you a cheap fixture).

### Subtask T006 – Runner-side schema stamp: canonical map, merge-preserving, atomic (moved from WP01)

- **Purpose**: FR-011 (runner half; #5229) — the schema-3 migration must stamp the same shape `init` stamps, without losing keys, atomically. Moved here from WP01 by Decision `01M4B6G3J0YNZ57WSHJXDMJS6N` (do not reopen): a recorded out-of-map edit of `src/specify_cli/migration/runner.py`, made after WP01 lands. Keep the id T006 (it was WP01's; ids are not renumbered).
- **Steps**:
  1. `_update_schema_version` (`origin/main` `runner.py:194-220`): stamp `CURRENT_SCHEMA_VERSION` from `specify_cli.migration.schema_version` (`schema_version.py:46`, `:55-57`). Delete `_TARGET_SCHEMA_VERSION`/`_TARGET_SCHEMA_CAPABILITIES` (`runner.py:35-41`) — `git grep -n "_TARGET_SCHEMA_" -- src tests` first (on `origin/main` only `runner.py:35`, `:36`, `:213`, `:214`, `:220` reference them); update every reference.
  2. Write rule — identical to T013's `canonical_schema_capabilities` (and init's rule, `init.py:572-580`): `schema_version = CURRENT_SCHEMA_VERSION`; `schema_capabilities` absent → the canonical map; a legacy list → `{name: True for name in list}` plus missing canonical keys; an existing map → untouched. Reuse T013's helper with a **function-local** import inside `_update_schema_version` (`from specify_cli.upgrade.metadata import canonical_schema_capabilities`): `specify_cli/upgrade/__init__.py:5-8` imports `runner` and `registry`, which import the migrations, which import `migration.runner` — a module-top import risks a cycle. Verify with `.venv/bin/python -c "import specify_cli.migration.runner"` and `-c "import specify_cli.upgrade"`. Keep `last_upgraded_at`. Keep every other key (top-level and under `spec_kitty`), ruamel round-trip as today (`:202-207`).
  3. Atomic write: dump to a string (`io.StringIO`) and write with `specify_cli.core.atomic.atomic_write(metadata_path, text)` (`src/specify_cli/core/atomic.py:30` — the same seam as T012) instead of the in-place `open("w")` at `:217-218` — a crash mid-write today truncates the file.
  4. Tests — a NEW module `tests/specify_cli/migration/test_runner_schema_stamp_5229.py` (`unit`, `fast`, `tmp_path` only), so WP01's `tests/specify_cli/migration/test_runner.py` stays untouched (its `TestSchemaVersionUpdate`, `:519-552`, asserts `== 3` and `"canonical_context" in caps`, both still true for the map — run it, do not edit it): `schema_version == CURRENT_SCHEMA_VERSION`; `schema_capabilities == CURRENT_SCHEMA_CAPABILITIES` for a file without the key; legacy list `["canonical_context"]` → map containing all canonical keys `True`; operator map `{"canonical_context": True, "my_flag": False}` → `my_flag` kept `False`; operator top-level key `project: {uuid: x}` and `spec_kitty.project_uuid` preserved; `monkeypatch` the module's `atomic_write` with a spy → called once with the metadata path. Mutant "write the list" → equality with the dict kills it; mutant "replace the map" → `my_flag` lost kills it; mutant "plain open" → spy count 0 kills it.
- **Files**: `src/specify_cli/migration/runner.py` (out-of-map, `_update_schema_version` + the two constants only), `tests/specify_cli/migration/test_runner_schema_stamp_5229.py` (new).
- **Validation**: `pytest tests/specify_cli/migration/test_runner_schema_stamp_5229.py tests/specify_cli/migration/test_runner.py -q` green; `git grep -n "_TARGET_SCHEMA_" -- src tests` empty; `git diff <WP01 base> -- src/specify_cli/migration/runner.py` touches only the constants, the import(s) and `_update_schema_version`.

### Subtask T014 – Verification and closeout

- **Steps**:
  1. Targeted runs (no full suites):
     ```bash
     .venv/bin/python -m pytest tests/upgrade/test_metadata_writers_5229.py tests/upgrade/test_metadata_final_file_5229.py -q
     .venv/bin/python -m pytest tests/specify_cli/migration/test_runner_schema_stamp_5229.py tests/specify_cli/migration/test_runner.py -q
     .venv/bin/python -m pytest tests/upgrade/test_metadata_schema_roundtrip.py tests/upgrade/test_metadata_version_stamp.py \
       tests/upgrade/test_schema_version_recovery.py tests/upgrade/test_issue_4972_idempotent_worktree_metadata.py \
       tests/upgrade/test_runner_status_classification.py tests/upgrade/test_failed_upgrade_recoverable.py \
       tests/specify_cli/cli/commands/test_init_schema_stamp.py tests/integration/test_init_fresh_project_chain.py \
       tests/cross_cutting/versioning/test_upgrade_version_update.py -q
     ```
  2. `ruff check` + `ruff format --check --force-exclude` on the touched files; `mypy src/specify_cli/upgrade/metadata.py src/specify_cli/upgrade/runner.py src/specify_cli/migration/backfill_identity.py src/specify_cli/migration/runner.py`.
  3. `git diff --stat <WP01 base> -- src/specify_cli/cli/commands/upgrade.py src/specify_cli/upgrade/finalize.py src/specify_cli/upgrade/outcome.py tests/specify_cli/migration/test_runner.py` must be empty; `git diff <WP01 base> -- src/specify_cli/migration/runner.py` touches only T006's region and `git diff <WP01 base> -- src/specify_cli/upgrade/runner.py` touches only `_stamp_schema_version` (T013) — the two recorded out-of-map edits.
  4. Record RED (T011 commit) and GREEN output lines in the Activity Log; draft the changelog bullet text for WP08 in the Activity Log (impact first: "`spec-kitty upgrade` no longer drops `project_uuid`, the schema capability map and your own keys from `.kittify/metadata.yaml` (#5229)").
  5. `spec-kitty agent tasks mark-status T011 T012 T013 T006 T014 --status done --mission upgrade-migration-commit-scope-01M4AKVE`.

## Test Strategy

```bash
# red on the planning base (T011 commit), green at the end
.venv/bin/python -m pytest tests/upgrade/test_metadata_final_file_5229.py tests/upgrade/test_metadata_writers_5229.py -q
# neighbours that must not move
.venv/bin/python -m pytest tests/upgrade/test_metadata_schema_roundtrip.py tests/upgrade/test_metadata_version_stamp.py tests/upgrade/test_schema_version_recovery.py -q
```

Marker vocabulary: `unit`+`fast` only for the no-subprocess module; `git_repo`+`non_sandbox`+`regression` on the `spec-kitty upgrade` module. No `p0_repro`.

## Risks & Mitigations

- **Over-correction forges a stamp** (merge keeps a stale disk `schema_version` on a failed run): the failure path restores the trio through `VersionStamp.restore` (`metadata.py:365-393`), which runs after the last save; `test_schema_version_recovery.py` guards it.
- **Byte churn on no-op upgrades** (#1871/#1838): keep insertion order and the masked compare-before-write; T011 idempotency cases.
- **Operator capability map silently "fixed"**: never merge into an existing map (init's rule).
- **Fixture environment leak** (real HOME, global git hooks): use `child_environment`; non-protected branch; `GIT_CONFIG_NOSYSTEM`.
- **WP01 overlap**: `migration/runner.py` and `upgrade/runner.py` are WP01's files; this WP edits only `_update_schema_version` and the two `_TARGET_SCHEMA_*` constants (T006) and `_stamp_schema_version` (T013), after WP01 has landed (dependency), and adds its tests in new modules rather than WP01's `test_runner.py`.
- **Import cycle** (`migration.runner` → `upgrade.metadata` → `specify_cli.upgrade/__init__` → registry → migrations → `migration.runner`): function-local import in T006; verified by bare imports.

## Review Guidance

- Confirm the T011 commit precedes the fix commits and its recorded RED is a content assertion on the final file (after returncode 0 and the applied-migration assertion), not a fixture failure.
- Confirm no literal schema version/capability list in code or tests (grep the diff for `"canonical_context"` outside fixture data that models a legacy list, and for a bare `3`).
- Confirm `save()` still writes no `schema_version` key for a genuinely unmigrated project and still skips timestamp-only writes.
- Confirm `cli/commands/upgrade.py`, `init.py`, `tests/specify_cli/migration/test_runner.py` and the #5856 files are untouched, and that the `migration/runner.py` diff is limited to T006's region and the `upgrade/runner.py` diff to `_stamp_schema_version` (recorded out-of-map edits, Activity Log rationale present).
- Run the two real-git tests once yourself.

## Activity Log

- 2026-10-07T12:21:08Z – system – Prompt created.
- 2026-10-07 – planner-priti – Decision `01M4B6G3J0YNZ57WSHJXDMJS6N` (not reopened): WP01's T006 (runner-side `_update_schema_version` canonical-map, merge-preserving, atomic write, #5229) moved here for PR 2 as a recorded out-of-map edit of `src/specify_cli/migration/runner.py` after WP01; `dependencies: [WP01]`; T006 keeps its id; its tests go in the new `tests/specify_cli/migration/test_runner_schema_stamp_5229.py` so WP01's `test_runner.py` is not touched; `requirement_refs` unchanged (FR-011 already here). Post-tasks review NOTE 6 folded (T011: `packs/` must sit beside `<checkout>/src`).
- 2026-10-07 – planner-priti – Analysis fold (AN-UND-001, orchestrator resolution): `src/specify_cli/upgrade/runner.py` moved to WP01's `owned_files` (WP01 gives the upgraded-worktree commit path the main-checkout rules in PR 1); T013's `_stamp_schema_version` change is now a recorded out-of-map edit after WP01 (existing dependency), not an owned file. AN-COV-002: C-004 added to `requirement_refs`.
- 2026-10-07 – orchestrator (recording implementer evidence) – Lane-b commits: be3384dd6 test (red), 4456420db fix, 89b0adce4 fix (failed upgrade restores the map with the version trio). RED at be3384dd6: final-file module 4 failed (KeyError schema_capabilities / project_uuid / dirty_operator_key); writers 13 failed / 9 passed; runner stamp 6 failed / 2 passed. GREEN: WP list 115 passed, 1 skipped; tests/upgrade + migration + init + architectural suites 1673 passed, 4 skipped, 15 failed (all `<checkout>/.venv` preview tests, red on base too). 13/13 mutants killed. Out-of-map edits: migration/runner.py (T006, DM 01M4B6G3J0YNZ57WSHJXDMJS6N), upgrade/runner.py (T013), and fixture-only edits to test_issue_4972_idempotent_worktree_metadata.py and test_upgrade_worktree_commit.py (main fixture gains the canonical map a real upgrade now stamps). Dirty metadata.yaml e2e: the operator key survives; the YAML comment does not (FR-011 promises keys only).
- 2026-10-07 – orchestrator – Changelog draft for WP08 (#5229): "`spec-kitty upgrade` no longer drops `project_uuid`, the schema capability map or your own keys from `.kittify/metadata.yaml`. Every metadata writer now keeps the keys it does not own, the schema-3 migration stamps the same capability map `init` does, and `backfill_project_uuid` and the schema stamp write atomically. A failed upgrade restores the map along with the version stamp. (#5229)"
