# Code-Grounding Report — Issue #4868 (P1)

**Baseline:** `fix/verdict-matrix-rmw-preservation` @ scaffold `ac85d2574572e...` off `skupstream/main == 45df0b61d5`.
**Verdict on triage: CONFIRMED and precise.** Serial wrong-source-directory migration bug (not concurrency).

## Mechanism (file:line)
- Entrypoint: `issue_verdict_command` `src/specify_cli/cli/commands/agent/issue_verdict.py:290`; pure core `do_issue_verdict` `:211`.
- `_migrate_if_needed` `issue_verdict.py:138-176`:
  - `read_dir = _resolve_read_dir(...)` (coord-aware) available at `:161` (`coord_read_dir_for(...) or feature_dir`, `_resolve_read_dir` `:110-118`).
  - Coord-aware JSON existence check CORRECT at `:162`.
  - **BUG at `:166`**: `migrate_issue_matrix_to_json(feature_dir, ...)` passes PRIMARY `feature_dir`, not `read_dir`.
- `migrate_issue_matrix_to_json` `src/specify_cli/tasks/issue_matrix_migration.py:219-271` reads legacy from its `feature_dir` arg (`:240` existence, `:242` md_path, `:248` `validate_issue_matrix`). On coord the `.md` is on the coord worktree → not found → returns `None` → `migrated=False` (`issue_verdict.py:173`).
- Then `do_issue_verdict:256` `rows = _load_raw_rows(read_dir / ISSUE_MATRIX_JSON_FILENAME)` → `{}` (never reads `.md`); `_upsert_row` adds only #B (`:257`); `write_issue_matrix` (`:260`) writes JSON with only #B. Existing #A gone.
- Docstring nuance: `_migrate_if_needed` docstring (`:145-153`) claims read-surface awareness, true only for the existence check, not the migration read.

## Writer is full-object overwrite
- `write_issue_matrix` `src/specify_cli/tasks/issue_matrix.py:327-378` → `build_issue_matrix_document(rows)` (`:311`) serializes ONLY passed rows; `_stage` `path.write_text(json.dumps(...))` (`:364`), no read-merge. Analogous to `acceptance/matrix.py:389-405`. Correctness depends on the read side supplying all prior rows.
- Round-trip parse used by command: `parse_issue_matrix_document` `issue_matrix.py:319` (preserves placeholder rows); canonical filtered reader `load_issue_matrix` `issue_matrix_migration.py:168-197` (JSON-first, failover to `.md`; does NO topology resolution — uses the dir the caller resolved).

## Coord read-dir resolution
- `coord_read_dir_for(repo_root, mission_slug, kind)` `src/mission_runtime/resolution.py:2131-2181` — returns coord worktree dir only for COORD/LANES_WITH_COORD topologies with a materialized worktree, else `None` (caller falls back to primary). Thin projection of `resolve_artifact_surface`.
- Write routing: `write_issue_matrix` stages into primary `feature_dir`, commit routes through `write_artifact` `coordination/write_seam.py:418` → materializes coord copy + cleans primary residue. So the WRITE is coord-correct; only the READ/migration source is wrong.

## Minimal fix seam (2 changes)
1. `migrate_issue_matrix_to_json` (`issue_matrix_migration.py:219`): add optional `read_dir: Path | None = None`; `source_dir = read_dir or feature_dir` for legacy existence/read (`:240`, `:242`, `:248`). Keep `write_issue_matrix(feature_dir=feature_dir)` (`:263`) unchanged so write stays primary + routes through seam. Default None preserves bulk caller `_migrate_one_mission` (`:295`).
2. `_migrate_if_needed` (`issue_verdict.py:166`): pass `read_dir=read_dir`.
- DO NOT pass `read_dir` as the write `feature_dir` — that breaks the write-seam residue-cleanup contract the tests pin.

## Tests / fixtures
- Command tests: `tests/specify_cli/cli/commands/agent/test_issue_verdict_command.py` (flat fixture `_make_mission:33`; autouse `_no_coord_surface:104-113` monkeypatches `coord_read_dir_for`→None).
  - Flat legacy-`.md` control (already GREEN): `TestMigrateOnWrite.test_legacy_markdown_mission_migrates_on_first_write:312` (preserves #1298 + #1726).
  - `TestCoordAwareReadSurface...:380` seeds coord `.json` (not `.md`) — NOT the bug path.
- Migration units: `tests/specify_cli/tasks/test_issue_matrix_structured.py:341-410` (flat only).
- Arch: `tests/architectural/test_issue_matrix_json_migration_completeness.py`.
- **No existing regression covers coord + legacy `.md` + preserve prior verdicts.** Gap is real/untested.

## Red-first regression (deterministic, serial — MUST be integration)
- Must use the REAL write-seam (a fake write_artifact writes only primary and won't materialize coord JSON → post-migration coord re-read empty even with fix).
- New file: `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py` (integration, `git_repo`).
- Reuse `_build_coord_mission_for_matrix` (`tests/integration/test_accept_matrix_coord_partition.py:115`) → `(result, coord_root, coord_feature_dir)`.
- Steps: build coord mission → seed legacy `issue-matrix.md` on coord surface (mkdir coord_feature_dir, commit on coord branch) with #A `fixed`+evidence → assert `coord_read_dir_for(...)` reader sees #A before → run `do_issue_verdict(issue="#B", ..., repo_root=tmp_path)` (chdir repo root) → assert `ok`, `migrated is True`, committed coord `issue-matrix.json` (resolved via `coord_read_dir_for`) has BOTH #A and #B, and `load_issue_matrix(coord_read_dir)` returns both. RED on base (only #B); green after fix.
- Flat control already green (cite, don't rewrite): `test_issue_verdict_command.py:312`.

## Blast radius
`tests/specify_cli/cli/commands/agent/test_issue_verdict_command.py`; `tests/specify_cli/tasks/` (full — issue_matrix_structured, issue_matrix_scaffold, issue_ref_url_provenance); new integration test + neighbors (`test_accept_matrix_coord_partition.py`, `test_placement_partition_golden_path.py`, `test_issue_2404_acceptance_matrix_write_surface.py`); `tests/architectural/test_issue_matrix_json_migration_completeness.py`; baseline `make test-fast`. Signature add is backward-compatible.
