---
affected_files: []
cycle_number: 1
mission_slug: upgrade-dry-run-sequenced-verdict-01M68J9V
reproduction_command:
reviewed_at: '2026-10-31T09:30:57Z'
reviewer_agent: user
wp_id: WP01
---

# Review feedback — WP01 (dry-run sequenced verdict, #6552)

Reviewed commit `dd47c8bfc9` (plus an independent second review). The core mechanism is
sound and red-first: the prediction is unreachable on a real run, writes nothing, changes
no real-run text, reorders nothing, and the new test module fails on the pre-fix tree and
fails half-by-half (declaration removed vs wording removed).

## Anti-pattern checklist

1. Dead code — PASS (`sequenced_after` has one production reader; both helpers are called).
2. Synthetic-fixture test — PASS (tests drive the real `MigrationRunner` loop).
3. Silent empty return — PASS (`sequenced_predecessors = []` default is documented).
4. FR coverage — PASS (FR-001..FR-005, NFR-001..NFR-003 have assertions).
5. Frozen surface — PASS (`order_manifest.txt` untouched).
6. Locked decision — PASS (C-001..C-003 honoured: order authority, real-run parity, ledger authority).
7. Shared-file ownership — PASS (no overlap with WP02 at this commit).
8. Production fragility — PASS (no new `raise`, no new I/O).

## Must fix before approval

**M1 — the predicted verdict is invisible to the operator.** The change line
`dry-run: would apply after <id>` is rendered by no surface: text mode prints
`changes_made` only when `changes_made[0]` is a JSON dict (`_print_migration_summaries`),
and the `--json` payload never carries raw `changes_made`. An operator sees an unqualified
`✓ 3.2.6_issue_matrix_driver_repoint` and cannot tell a prediction from a direct detection —
exactly what the spec's prediction entity promises. Fix: carry the predecessors on
`MigrationResult` (e.g. `predicted_after: tuple[str, ...]`), print a dim prediction line in
`_display_upgrade_results` for a dry run, and add the field to the per-migration `--json`
detail. Assert the RENDERED text in the tests, not only the data model.

**M2 — `--dry-run --verbose` contradicts the run summary.** The "Detection results" preview
calls `detect()` on the pre-run tree and prints the repoint as `skipped`, while the same
invocation's summary now prints it `applied`. Fix: the preview must apply the same
sequencing, and it must do so through the SAME function the runner uses (no second
authority): lift the declaration read into one module-level
`sequenced_predecessors(migration, applied)` in `runner.py`, use it in both places, and show
`ready (after <dep>)` for a dependency the preview itself reports ready.

**M3 — nothing validates a declaration.** A typo'd/unregistered id, or one naming a
migration ordered LATER in the manifest, silently disables the prediction forever. Add a
test that every `sequenced_after` id in the discovered registry is registered and appears
earlier in `order_manifest.txt` than its declarer. That is the gate this repo already uses
for `requires_git_repository` and for manifest rules.

## Nits (fix in the same round)

**N1** — `BaseMigration.sequenced_after` must state its assumption: the declaration asserts
the predecessor's write lands in every project where both apply. Outside a git repository
`MergeDriverSeedingMigration.apply` skips the config half while this pair's dependent also
stops reading config there, so a tampered non-git tree can be predicted `applied` and then
skipped for real. Document the assumption on the attribute (and in the migration comment).

**N2** — the worktree pass is not sequenced-view aware (C-004 scopes it out) but its
docstring does not say so; add one line. Also reset `_sequenced_applied` in
`upgrade_worktrees_only` next to `_seen_residue` so the state cannot leak into a later read.

**N3** — `getattr(migration, "sequenced_after", ())` is dead defensiveness (`ClassVar` on
`BaseMigration`); use the attribute, or justify the getattr in a comment.

**N4** — `m_3_2_6_issue_matrix_driver_repoint.py`'s docstring still explains same-version
ordering via "`get_all()` sorts by `Version` … alphabetical `pkgutil` discovery order" while
the manifest is the ordering authority, and the new class comment says so. Refresh that
paragraph so one module does not carry two contradictory explanations.

## Verification for the next round

- `uv run pytest tests/upgrade/test_dry_run_sequenced_verdict.py -q` (plus the existing
  suites listed in the WP prompt), ruff check/format, and a rendered-output assertion for
  the prediction line.
