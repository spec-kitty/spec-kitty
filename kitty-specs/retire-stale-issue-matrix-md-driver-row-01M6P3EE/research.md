# Research: Retiring the stale `issue-matrix.md` merge-driver row (#7217)

## Grounding on current `main`

`origin/main` at `b4d1e918e2` ("chore(landing): preserve incoming lifecycle rows through their
native owner"). No change in `git log -S "issue-matrix.md merge"` since 3.2.6/4.0.0rc7 shipped
the repoint, and no open PR references #7217 (`gh pr list --search "7217 in:body"` → empty;
issue unassigned before this claim).

**Reproduction** (clean throwaway clone, so this repository's own tree was not touched):

```
git clone --shared . /tmp/repro7217
cd /tmp/repro7217 && spec-kitty upgrade --yes
#   ✓ 3.2.6_gate_artifact_merge_drivers
#   ✓ 3.2.6_issue_matrix_driver_repoint
git status --porcelain
#  M .gitattributes
git diff -- .gitattributes
# +kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix
```

The row is appended **after** the file's last line (`kitty-ops/lifecycle.jsonl merge=union`),
confirming `ensure_line()`'s append-only write.

The same run also removed `.opencode/command/spec-kitty.*` from `.gitignore`. That is a
different defect (`4.0.0rc8_narrow_agent_gitignore`'s narrow block vs. its legacy list), not
caused by this change and not in this mission's scope; it is recorded in the PR's
`## Deferred` section.

## Which side is wrong

1. **No canonical writer.** `tests/architectural/test_issue_matrix_json_migration_completeness.py`
   (T027b) asserts that no code path creates a fresh `issue-matrix.md`; `src/mission_runtime/
   artifacts.py` maps the `.md` name to the legacy `ISSUE_MATRIX` kind for reading only.
2. **No declared driver for the pattern.** `_MERGE_DRIVERS` declares
   `kitty-specs/**/issue-matrix.json` for `spec-kitty-issue-matrix`; the `.md` row has no
   matching declaration, so `test_declared_merge_drivers_are_registered_in_gitattributes`
   reports it as `orphaned` drift.
3. **The driver is format-specific.** `merge-driver-issue-matrix` runs
   `run_issue_matrix_driver`, a 3-way merge over the JSON `rows` array keyed by
   `issue_ref`. It cannot merge a Markdown table, so "re-add the driver correctly" for `.md`
   would need a different driver that nothing needs.

Conclusion: **retire the row; keep the driver pointed at `issue-matrix.json`.** What has to be
"re-added correctly" is the *acceptance-matrix* half of the same superseded migration, which
is still the #2804 fix and must survive the retirement (D-002 in plan.md).

## Why it keeps coming back

`MergeDriverSeedingMigration.clone_local_effect = True`: the effect is split between a tracked
`.gitattributes` line and a clone-local `git config --local` entry. A pulled clone carries the
tracked half but not the local half, so `detect()` is True, the migration is re-selected, and
`apply()` re-appends every line in its `drivers` tuple — including the retired one. The ledger
cannot settle it (`clone_local_effect` routes the skip decision to per-clone `detect()`, #6233).

Superseding the module is the only fix that does not edit a shipped migration: the registry
replaces it with a `SupersededMigration` (`detect()` always False), so nothing re-appends the
row, and the successor carries the live halves plus the removal.

## Blast radius survey

| Surface | Why it is touched |
|---|---|
| `src/specify_cli/upgrade/supersession.py` | The retirement entry |
| `src/specify_cli/upgrade/migrations/m_4_0_0rc8_retire_issue_matrix_md_row.py` | New successor |
| `src/specify_cli/upgrade/migrations/order_manifest.txt` | The successor's slot (build-time gate requires one line per registered id) |
| `src/specify_cli/upgrade/init_seed.py` | Docstring only: the workaround it documents (writes the inert line) is now vacuous |
| `src/specify_cli/upgrade/runner.py` | `SEQUENCED_AFTER` loses its only entry; its predecessor is a recorded no-op now |
| `src/specify_cli/upgrade/migrations/README.md` | The `sequenced_after` example names the retired id |
| `tests/init/test_init_then_upgrade_is_noop.py` | Encodes the #6416 workaround (asserts `init` writes the inert line) → inverted |
| `tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py` | `SHIPPED_SUPERSEDED` must cover every `SUPERSEDED_MIGRATIONS` key (equality assertion) |
| `tests/upgrade/test_dry_run_sequenced_verdict.py`, `..._cli.py` | Their "reported pair" is the retired one; re-anchored on a same-shaped synthetic pair |
| `tests/upgrade/test_issue_matrix_md_row_retirement_7217.py` | New red-first proof |

Not affected (verified by reading, to be confirmed by running): `test_clone_local_migration_idempotent.py`
(imports the shipped class directly; its flag is unchanged), `test_backfill_ledger.py` (passes
the id as a string to a stub), `test_row_aware_merge_driver.py` (imports the shipped module and
calls `apply()` directly), `tests/architectural/test_no_dead_modules.py` (the module still
exists), `tests/release/coverage_breadth_baseline.json` (the module still exists).

## Measured behaviour to preserve

- `init` seeds the ledger so the first `upgrade` selects nothing (#6416); the seed's
  `.gitattributes` union (`merge_attribute_seed_lines()`) must still cover every *live* seeding
  migration's lines, otherwise the first upgrade commits them.
- A skip record does not settle a migration; a superseded one is re-skipped every run,
  idempotently (#6589).
- `4.0.0rc8_narrow_agent_gitignore` shows the house pattern for a retire migration: frozen
  legacy list, `detect()` computed from `_plan()`, `apply()` reporting each removal, and
  `can_apply` carrying the reason.
