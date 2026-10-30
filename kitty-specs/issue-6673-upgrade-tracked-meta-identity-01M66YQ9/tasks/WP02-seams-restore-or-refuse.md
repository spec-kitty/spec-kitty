---
work_package_id: WP02
title: Every upgrade seam restores or refuses, and none mints
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-002
- NFR-003
- C-001
- C-002
- C-005
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6673-upgrade-tracked-meta-identity
merge_target_branch: issue-6673-upgrade-tracked-meta-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6673-upgrade-tracked-meta-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6673-upgrade-tracked-meta-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-6673-upgrade-tracked-meta-identity-01M66YQ9
base_commit: b563e598e145cb047be630f42e44c9853683422e
created_at: '2026-10-30T18:22:30.475596+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - The upgrade seams stop fabricating identity
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/
create_intent:
- src/specify_cli/upgrade/tracked_meta_notice.py
- tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py
- tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py
- tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/tracked_meta_notice.py
- src/specify_cli/upgrade/migrations/m_2_0_6_residue_safe_consistency_sweep.py
- src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py
- src/specify_cli/migration/normalize_mission_lifecycle.py
- src/specify_cli/migration/backfill_identity.py
- tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py
- tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py
- tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6673'
---

# Work Package Prompt: WP02 – Every upgrade seam restores or refuses, and none mints

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: pi

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address every item and record it with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- Through the real `spec-kitty upgrade --yes` CLI, a Mission whose `meta.json` is tracked but missing from the working tree ends with a `meta.json` whose `mission_id` equals the one git holds **before the run** — never a fresh ULID.
- A Mission whose tracked `meta.json` cannot be read (corrupt committed blob) is left alone: **no** `meta.json` is written for it by **any** migration in the run — the `2.0.6` sweep, the `3.2.0a4` normalization **and** the `3.2.6rc1` runtime-state cutover's phase flip. The output names the file and `git checkout -- <path>`.
- A pre-identity Mission (tracked `spec.md`, no `meta.json` anywhere in git) is still repaired exactly as today: baseline `meta.json` plus a minted `mission_id`.
- On a project whose Missions all have their `meta.json` on disk, the upgrade's output gains no new line and `kitty-specs/` is untouched.
- `backfill_mission` returns `action="skip"` with the restore command in `reason` instead of minting, when the `meta.json` it was asked to repair is tracked but absent on disk.
- No shipped-frozen migration module is edited; `meta.json` writes still go through `mission_metadata.write_meta` under the Mission write lock.

## Context & Constraints

- **The defect (#6673).** With `meta.json` tracked but absent from the working tree: (a) `2.0.6_residue_safe_consistency_sweep` calls `build_baseline_feature_meta`, which now (WP01) seeds from the tracked copy, rebuilds the file and thereby restores it; (b) `3.2.0a4_normalize_mission_lifecycle` then calls `backfill_mission`, which mints a fresh ULID when `meta.json` exists without one. When the tracked content is unreadable, (a) writes nothing — which is only honest if no other seam writes for that folder either.
- **Third writer, proven on `main`.** `RuntimeStateBackfillMigration.apply` (`m_zz_runtime_state_backfill.py`) walks **every** `kitty-specs/` child unconditionally (`_cutover_corpus` → `cutover_mission` → `_flip_phase`), and `_flip_phase` (`migration/runtime_state_cutover.py:332-341`) documents and does write a one-key stub `{"status_phase": "1"}` when `meta.json` is missing. `detect()` is a whole-project OR, so on any real project that still needs the cutover, the corrupt/refused Mission gets a `meta.json` git never had, which a later `migrate backfill-identity` will mint into. Reproduce it before fixing:
  ```bash
  # scratch repo: mission with spec.md + corrupt meta.json committed, meta.json deleted, tasks/doing/WP01-x.md
  python - <<'PY'
  from pathlib import Path
  from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import RuntimeStateBackfillMigration
  RuntimeStateBackfillMigration().apply(Path("<scratch>"))
  PY
  ```
  (The reviewer's probe on `main` produced `{"status_phase": "1"}` for exactly this fixture.) Guard it **before** `_cutover_corpus`, not inside `_flip_phase`: `_flip_phase`'s stub contract belongs to `cutover_mission`'s other callers; the upgrade seam is where the skip belongs.
- **Frozen module (C-001).** `src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py` is a shipped migration: its bytes are its `content_hash`. **Do not edit it.** Its live helpers are imported by the residue-safe successor, so the successor's `apply()` is where the per-Mission decision goes. Its `_feature_requires_repair` already returns `True` when `meta.json` is missing on disk, so `detect()` needs no change. `m_zz_runtime_state_backfill.py` and `normalize_mission_lifecycle.py` and `backfill_identity.py` are live code and may change.
- **Residue behaviour is out of scope to change (#6627/#6669).** `partition_kitty_specs` already keeps residue folders out of `missions`; keep the existing `residue_warnings` output byte-identical and add the new notice only for real Missions.
- **One message authority.** Put the operator text in a new module `src/specify_cli/upgrade/tracked_meta_notice.py` so the sweep, the normalization and the cutover cannot drift into three different messages:

  ```python
  @dataclass(frozen=True)
  class MissingTrackedMeta:
      notice: str   # one line, names the Mission's meta.json and the restore command
      refuse: bool  # True: git knows the path but its content cannot be used

  def classify_missing_tracked_meta(feature_dir: Path, repo_root: Path) -> MissingTrackedMeta | None:
      """Notice for a Mission whose working-tree meta.json is absent, or None when there is nothing to say."""
  ```

  `None` when the file is on disk or git holds nothing for it. `refuse` is `read_tracked_meta(...).unavailable`. Compute the project-relative path with `feature_dir.relative_to(repo_root).as_posix()` and fall back to the absolute path on `ValueError` (the pattern in `normalize_mission_lifecycle._repo_relative`). It calls `read_tracked_meta` **once** and must not write anything. Resolve mutable state per call — no module-level cache (a later seam may have restored the file).
- **Three notice variants** (keep them close, the restore command identical):
  - restore (readable copy in `HEAD`): `` kitty-specs/<slug>/meta.json: tracked meta.json is missing from the working tree; rebuilt it from the copy git holds (restore yours with `git checkout -- kitty-specs/<slug>/meta.json`) ``
  - refuse, corrupt committed copy: `` kitty-specs/<slug>/meta.json: tracked meta.json is missing from the working tree and git holds no readable copy; no identity was minted — restore it with `git checkout -- kitty-specs/<slug>/meta.json` and re-run the upgrade ``
  - refuse, index-only copy: `` kitty-specs/<slug>/meta.json: meta.json is missing from the working tree and git holds it only in the index (not committed); no identity was minted — restore it with `git checkout -- kitty-specs/<slug>/meta.json` and commit it ``
  Keep the lines free of "feature", "spec folder" or other retired terminology (`tests/architectural/test_no_legacy_terminology.py`).
- **Write ordering (C-005).** A path whose git read can fail must be read once per run for every affected Mission *before* the first repair write, so a mid-walk timeout cannot abort after earlier Missions were repaired (the #6669 successors' priming rule). In the sweep that means one pre-pass over `missions` building `{mission_dir: MissingTrackedMeta}` before the runtime-asset repairs, not a per-folder call inside the write loop.
- **Resolve the project root canonically.** `backfill_mission` takes no `repo_root`; use `specify_cli.core.paths.locate_project_root(feature_dir)` for the notice's display path and fall back to the absolute path when it returns `None`. Do **not** pass `feature_dir.parent.parent`.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `main`; completed changes must merge back into `main` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`
- Depends on WP01 (the reader and the builder seeding). A WP whose dependency is not `approved`/`done` refuses to be claimed; that is a claim gate, not a different command.

```bash
spec-kitty agent action implement WP02 --agent python-pedro --mission issue-6673-upgrade-tracked-meta-identity-01M66YQ9
```

## Subtasks

### T004 — Red-first reproduction of the defect through the real `upgrade --yes` CLI

Write `tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py` **first** and run it before touching `src/`. Module docstring: what #6673 is, who reported it, and that this file is the acceptance test for it. `pytestmark = [pytest.mark.integration, pytest.mark.git_repo]`.

Fixture helpers (local, small; follow `tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py`, which runs the real CLI in-process with `CliRunner` and `contextlib.chdir`):

- `_git(root, *args)` running real git; `git init -q -b main`, local `user.name`/`user.email`.
- `_commit_mission(root, slug, meta: dict | bytes)` writing `spec.md` plus the `meta.json` bytes and committing everything.
- `_head_sha(root)` → `git rev-parse HEAD`, captured **before** the upgrade run.
- `_upgrade(project)` → `(exit_code, output)` through `app` + `CliRunner`.

**The auto-commit trap.** `upgrade --yes` commits what it writes, so after the run `HEAD` already holds the post-upgrade file. Compare the surviving `mission_id` against `git show <pre-run-sha>:kitty-specs/<slug>/meta.json`. A comparison against post-run `HEAD` would compare a minted id with itself and pass vacuously.

Fixture shapes in one repository (one run proves them together):

1. `sparse-...`: committed `meta.json` with a **literal** known `mission_id` (the `_REAL_ID` style of the #6669 test), then `(meta_path).unlink()` (the accidental `rm` / sparse-checkout shape).
2. `legacy-...`: tracked `spec.md` only, no `meta.json` anywhere in git (the pre-identity control, FR-004).
3. `corrupt-...`: committed `meta.json` whose bytes are not JSON (for example `{not json\n`), **plus a `status.json` and a `status.events.jsonl`** (or a `tasks/` tree) so that a later step would rewrite state in that folder if the refusal did not skip it, then unlink `meta.json`.

Assertions (red on `main` for the `sparse` case; all green after T005–T008):

- `exit_code == 0` and the output names each affected path at least once (collapse whitespace as the #6669 test does).
- `sparse`: `meta.json` exists again and `json.loads(...)["mission_id"]` equals the literal committed id **and** the id at `<pre-run-sha>`; also assert it differs from any id the run could mint by asserting equality, never by a "looks like a ULID" heuristic.
- `legacy`: a `meta.json` now exists and carries a non-empty `mission_id` (positive control: the repair is still a repair).
- `corrupt`: `meta.json` does not exist after the run — this is the assertion the runtime-state cutover breaks today — the folder's other files are byte-identical to their pre-run snapshot, and the output contains `git checkout -- kitty-specs/<slug>/meta.json`.

Confirm the red state now (`uv run pytest tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py -q` fails on the `sparse` — and, with the extra state present, likely the `corrupt` — assertions) and record the exact failure in the WP history note.

### T005 — One notice authority; refuse an unreadable tracked `meta.json` in the 2.0.6 successor

- Add `src/specify_cli/upgrade/tracked_meta_notice.py` with `MissingTrackedMeta` and `classify_missing_tracked_meta` as described above.
- In `m_2_0_6_residue_safe_consistency_sweep.py::apply`, **prime** the classification before any write:
  ```python
  missing = {m: classify_missing_tracked_meta(m, project_path) for m in missions}
  ```
  then, after the runtime/worktree repairs and before the repair loop, append each `MissingTrackedMeta.notice` to `warnings` in mission order, and inside `for mission_dir in missions:` skip a refused folder **entirely**:
  ```python
  refusal = missing.get(mission_dir)
  if refusal is not None and refusal.refuse:
      continue
  ```
  (`_repair_feature` must not run for it: its later steps would write status/lane state for a Mission we could not identify.)
- Do not change `detect()`.
- Extend the class docstring and the module docstring's summary with one sentence: a Mission whose tracked `meta.json` is missing from the working tree is rebuilt from git, or refused with the restore command; the folder is never given a second identity (#6673).
- `--dry-run` still emits the notice (it is a report, not a write) but writes nothing — verify on the fixture.

### T006 — Replace the weak notice in the 3.2.0a4 normalization

- In `src/specify_cli/migration/normalize_mission_lifecycle.py::_load_meta_for_normalization`, replace the `result.warnings.append("meta.json missing; mission skipped")` branch:
  - it needs `repo_root` to build the notice; thread it through (the function is module-private; `normalize_repo` already has `repo_root`);
  - when `classify_missing_tracked_meta` returns a notice, append it; otherwise keep a short "no meta.json on disk; mission skipped".
- Add one sentence to `normalize_repo`'s docstring: an identity is never derived for a Mission whose tracked `meta.json` is absent — the folder is reported (FR-003).
- Do not add a second `backfill_mission` call site; the refusal lives in that function (T007) so every caller is covered.

### T007 — Make `backfill_mission` skip instead of minting, with its own test

- In `src/specify_cli/migration/backfill_identity.py::backfill_mission`, in the `if not meta_path.exists():` branch:
  ```python
  missing = classify_missing_tracked_meta(feature_dir, locate_project_root(feature_dir) or feature_dir)
  if missing is not None:
      return BackfillResult(feature_dir=..., slug=slug, action="skip", reason=missing.notice)
  ```
  Keep the existing `"meta.json not found"` skip for a folder git holds nothing for. A readable tracked copy still reaches the normal path — the 2.0.6 sweep restores the file first and the `3.2.0a4` normalization reads it from disk, so nothing here needs a second identity read.
- Docstring: state that a tracked-but-absent `meta.json` is a refusal, not an identity source, so no caller can fork an identity through this function (FR-006).
- Check the import graph: `specify_cli.migration` importing `specify_cli.upgrade.tracked_meta_notice` (which imports only `mission_metadata`, `core.paths` and `mission_resolver`) is acceptable; confirm with `tests/architectural/` green. Import lazily inside the function if the module-load order complains.
- **Own test** (`tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py`), because no `upgrade` path reaches this branch (`normalize_repo` returns before the call when the file is missing) — the caller that does is `migrate backfill-identity`:
  1. tracked `meta.json` (HEAD), deleted from disk → `backfill_mission` returns `action="skip"` with the restore command in `reason`, writes no file, and the on-disk id never changes (assert the file is still absent).
  2. control on the same fixture: a `meta.json` present on disk without an id → `action="wrote"` and an id is minted (today's behaviour, unchanged).
  3. nothing tracked, no file → `action="skip"`, reason `"meta.json not found"` (unchanged string).

### T008 — Stop the runtime-state cutover writing a stub `meta.json` for such a Mission

- Reproduce first with the probe in the Context section (a one-off script or a test that fails today), and record the observed stub.
- In `m_zz_runtime_state_backfill.py::apply`, partition `missions` **before** `_cutover_corpus`: a Mission whose tracked `meta.json` is absent from disk (`classify_missing_tracked_meta(...) is not None`) is skipped, its notice appended to `MigrationResult.warnings`, and it is not passed to `_cutover_corpus` — so neither the seed phase nor the flip phase reaches it. When every Mission is skipped, return `success=True` with the notices and no changes.
- Keep `_flip_phase`'s stub contract untouched (its other callers, `cutover_mission`/`cutover_repo`, keep it).
- Add the unit test `tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py`:
  1. a corrupt-tracked-absent Mission beside a Mission that genuinely needs the cutover (legacy `tasks/doing/WP01-x.md`) → after `apply()`, the refused folder has **no** `meta.json` and no event log, while the other Mission is cut over (positive control on the same fixture: the probe can observe a cutover happening).
  2. nothing tracked and no file → the cutover is unchanged (no new skip path).

### T009 — Green the reproduction, add the healthy/idempotent cases, prove the fix half by half

- Re-run the T004 test until green. Add:
  - `test_upgrade_leaves_a_healthy_project_unchanged`: all Missions have their `meta.json` on disk; run `upgrade --yes`; assert no `tracked meta.json`/`only in the index` text in the output and that every Mission's `meta.json` bytes are unchanged and ids are unchanged (NFR-003).
  - `test_upgrade_is_idempotent_for_a_restored_mission`: run the upgrade twice on the mixed fixture; the second run changes nothing under the `sparse` Mission (byte snapshot) and its id is still the tracked one.
- Half-by-half (tactic `acceptance-criteria-non-vacuity`): revert each part in turn and record which assertion goes red — T005 (the sweep's refusal `continue` and its notice), T006 (the normalization's notice text), T008 (the cutover skip). T007 is covered by its own test, not by the upgrade run; say so rather than claiming a red you cannot produce.
- `uv run pytest tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py -q` must stay green (residue untouched) — run it, do not edit it.

## Test Strategy

```bash
uv run pytest tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py -q
uv run pytest tests/specify_cli/upgrade/test_runtime_state_cutover_skips_absent_meta_6673.py tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py -q
uv run pytest tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py tests/integration/migration/test_upgrade_residue_identity_6627.py -q
uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/specify_cli/migration tests/specify_cli/upgrade/test_residue_safe_successors_6669.py -q
uv run pytest tests/architectural/test_migration_walkers_use_mission_predicate.py tests/architectural/test_git_path_listing_owner.py -q
```

No full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- Every command above is green; the new integration module was red before T005–T008.
- The reproduction test asserts against the literal id **and** the pre-run commit SHA, never against post-run `HEAD`.
- `git diff --stat src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py` is empty.
- All notices name the project-relative path and the exact `git checkout --` command, come from one module, and contain no retired terminology.
- No `except Exception` and no suppression; no test marked `xfail` or `skip`.

## Risks & Reviewer Guidance

- **Skip the folder, not just the write.** If `refuse` only suppresses `_repair_feature_meta`'s write, later steps of `_repair_feature` (status regeneration, lane moves) still write state for an unidentified Mission. Reviewers: confirm the `continue`.
- **A fourth writer.** Grep the upgrade chain for `write_meta(` and `_STATUS_PHASE_KEY` before declaring the invariant held: the cutover's stub is the one a reviewer already found on `main`, and there may be another behind a `detect()` that this fixture does not trip.
- **Notice duplication.** Four seams, one text. If the command string appears in two modules, the authority is wrong.
- **Minting after the refusal.** `3.2.0a4` and `3.2.6rc1` run after `2.0.6` in the same upgrade. Confirm on the `corrupt` fixture that no `meta.json` appears after the whole run, not just after the sweep.
- **Flat-out regression risk.** The `legacy` control is the guard: if the tracked-copy test is too broad, legacy Missions stop being repaired.
