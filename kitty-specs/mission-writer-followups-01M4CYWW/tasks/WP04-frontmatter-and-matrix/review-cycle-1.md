---
affected_files: []
cycle_number: 1
mission_slug: mission-writer-followups-01M4CYWW
reproduction_command:
reviewed_at: '2026-10-08T16:02:55Z'
reviewer_agent: claude-reviewer
wp_id: WP04
---

# WP04 review cycle 1: changes requested

## Blocking

1. **FR-003 / A8: the write-scope restore still puts stale bytes back over a concurrent write.**
   `_undo_finalize_write_scope` takes its "what finalize wrote" snapshot (`written`) when the run fails,
   not when finalize writes. So any file that another writer changed while finalize ran (after its
   pre-run `before` snapshot and before the failure) looks like finalize's own output and is rewritten
   back to `before`. That includes files finalize **never wrote**. Reproduction, run directly against HEAD:
   snapshot `before`; a foreign writer appends a body note to `tasks/WP02.md`, which finalize never touches;
   `written = _snapshot_mission_write_scope(dir)`; `_restore_mission_write_scope(before, dir, written=written)`.
   Result: `kept == []` and the note is erased. FR-003 says "a history note or ref added while finalize
   ran survives" and "the restore must not put back stale bytes over a concurrent write". The data model
   says "For each file, finalize records the bytes it wrote". Both are unmet. The implementer reported
   this as a known limitation, but it is the requirement itself, not an edge case.
   Fix: record a per-write ledger `{path: bytes_written}` at each finalize write site, inside the lock
   right after the write (the frontmatter flush, the tasks.md regeneration, the lanes/wps/matrix/scaffold
   writes; `locked_update_frontmatter` / `locked_rewrite_text` can return or record the bytes). Restore
   only the paths in the ledger, and only while the current bytes equal the ledger bytes. Leave a path
   that is not in the ledger alone. For an unlink, the ledger entry is the bytes of the file finalize
   created. Add a red-first test with a foreign write *during* the run (between the flush and an injected
   later failure) to a file finalize wrote and to one it did not, and show both survive. Also, read
   `meta_written_text` under the lock that wrote it, or return it from the writer, instead of re-reading
   it afterwards outside the lock.

2. **`tests/integration/test_owned_lifecycle_acceptance_finalize.py::test_armed_get_main_repo_root_pin_owned_finalize`**
   is red. It is green at `bbbb31663`. WP01 (`121d54cbe`) introduced the red: 3 unclassified
   `get_main_repo_root` reads through
   `mission_lock_key > _lock_name_for_dir > _primary_meta > literal_primary_meta > _compose_primary_feature_dir`.
   WP04 raises the count to 7 by adding new `mission_write_lock > _primary_alias > _primary_meta` and
   `transaction_lock_key > _primary_meta` reads on the owned finalize path. Do not add owned-path R reads.
   Pass the owned checkout's own root to the lock, or fix this together with the WP01 root-cause fix the
   orchestrator routes. Re-run this pin before resubmitting.

## Non-blocking

- `scaffold_acceptance_matrix` has the same check-then-write shape and is unlocked. The acceptance-verdict
  writer cannot create a missing matrix, so only a second scaffold or a hand edit can race it. Leaving it
  outside FR-004 is acceptable. Lock it if you are already in the file (one hold, same pattern as
  `scaffold_issue_matrix`).
- `backfill_ownership` locks without `fallback_to_dir_name=True`, unlike the other migration writers. On a
  legacy coordination Mission with no mid8 it now raises `MissionLockKeyUnresolved`.

## Verified good

- `locked_update_frontmatter` preserves the body. map-requirements does the plan and the write in one
  hold. Matrix and verdict helpers are rekeyed. Guard and `record_acceptance` nest on one re-entrant key.
- Deleting `update_fields` is safe: there are no callers in src, packs, tests or docs.
- Reviewer mutation: removing the scaffold lock makes the FR-004 test fail.
- ruff, format and C901 are clean. mypy shows no new errors. There are no new suppressions. The 137
  targeted tests pass.
