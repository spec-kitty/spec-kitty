# Discovery Research — #6234 `upgrade --dry-run` migration heading

Mission: `upgrade-dry-run-would-apply-heading-01M6BV1G`
Grounded on `main` @ `287a226cfe` (2026-11-01). Clone: `/home/exedev/work/sk-6234`.

## D1 — The issue still reproduces on current `main`, through the CLI

Not superseded. `git log -S"Migrations applied:" -- src/specify_cli/cli/commands/upgrade.py`
shows only the two commits that introduced the line (`d0ba5618dc`) and the #6552 addition of
the predicted-verdict block (`53a034ad5c`); no commit conditions the heading on `dry_run`.
The changelog fragments under `docs/changelog/unreleased/` contain nothing about this wording.

Reproduced in-process through the real `upgrade` command (the same fixture the
characterisation goldens use: a real git-backed project, one stubbed applicable migration,
`--no-worktrees`):

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│ DRY RUN - No changes were made                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
Migrations applied:
  ✓ 3.2.0a4_fake_migration
Migrations skipped (already applied or not needed):
  ○ 3.1.0_old_migration

Dry run complete — no changes applied. (1.0.0a1 -> 3.2.0a4 previewed)
```

The same fixture run for real prints the identical `Migrations applied:` / `✓` pair, which
is correct there — the two modes differ only in the panel, the closing line and the
predicted-verdict block. So the defect is exactly the missing `result.dry_run` condition on
the heading and its marker.

Evidence source: a scratch pytest module ran `_stub_applied_migration` + `_invoke(...)` from
`tests/upgrade/test_upgrade_outcome_rendering.py` for both modes and printed the captures
above; the scratch file was deleted after capture.

## D2 — The decision site is one function; nothing else chooses the words

`src/specify_cli/cli/commands/upgrade.py`:

- `_display_upgrade_results(result)` prints the `DRY RUN` panel (guarded by
  `result.dry_run`), then `_print_upgrade_section("[green]Migrations applied:[/green]", ...)`
  unconditionally, then the skipped section, then `_print_predicted_verdicts(result)`.
- `_print_upgrade_section(header, items, item_prefix)` emits nothing for an empty list.

One conditional in `_display_upgrade_results` therefore covers both modes; no second source
of truth for the heading exists.

## D3 — The words already asserted elsewhere are only these two test sites

`grep -rn "Migrations applied" --include=*.py .`:

- `src/specify_cli/cli/commands/upgrade.py:2356` — the printing site.
- `src/specify_cli/cli/commands/upgrade.py:2371` — a docstring in `_print_predicted_verdicts`
  that names the heading ("the operator cannot tell the two apart in ``Migrations applied:``").
- `src/specify_cli/upgrade/runner.py:620` — a comment referring to the heading by name.
- `tests/upgrade/test_upgrade_outcome_rendering.py:188,216` — `_GOLDEN_APPLIED` (real) and
  `_GOLDEN_APPLIED_DRY_RUN` (preview).
- `tests/upgrade/test_dry_run_sequenced_verdict_cli.py:8,80` — module docstring plus
  `assert "Migrations applied:" in result.output` on a `--dry-run --no-worktrees` run.

Only the last three are assertions about dry-run output. `_GOLDEN_APPLIED` must stay
unedited (it is the positive control that the real run did not change); the other two are
deliberate updates.

No docs page pins the dry-run applied heading: `grep -rn "Migrations skipped" docs/` returns
nothing, and `docs/api/upgrade-lifecycle.md` only describes the migration *selection* a dry
run previews (#6547). The only doc mention of the dry-run tail is ADR
`docs/adr/4.x/2026-10-04-3-upgrade-reports-one-outcome.md:72`, which pins the closing line
(`Dry run complete — no changes applied.`) — that line is not changing.

## D4 — Chosen wording and marker (decision)

Two resolutions were acceptable to the reporter: rename the section, or omit it. **Rename.**
The list carries information an operator wants (which migrations, in which order); the wrong
part is the verb tense and the success symbol.

- Heading in a dry run: `Migrations that would be applied:` in `yellow` (a preview colour,
  matching the `DRY RUN` panel border) instead of `green`.
- Entry marker in a dry run: `  [yellow]→[/yellow] ` instead of `  [green]✓[/green] `.
  `→` is already the CLI's "this will happen / this happened as a consequence" arrow (the
  auto-commit line), it is visually distinct from the neutral `○` skip marker and the `✓`
  success marker, and it is not a success tick.
- The skipped section keeps its wording and `○` marker: in a dry run it is still true that
  those migrations are already applied or not needed, and the heading already says
  "skipped", not "skipped now".

Rejected alternatives: `Would apply:` alone (loses the "Migrations" noun the golden diff and
the reader both key on); dropping the section (throws away a usable list to fix a heading);
renaming in both modes (would lie about the real run and break `_GOLDEN_APPLIED`).

## D5 — The `Migrations skipped` heading stays (scope decision)

The issue names only the applied heading. A dry run's skipped list is not a claim about
_action taken_, only about project state ("already applied or not needed"), which is accurate
on the pre-run tree. Changing it would broaden the diff without fixing a contradiction.

## D6 — No behavioural surface moves

- Selection/ordering: `MigrationRegistry.get_applicable`, the ledger and
  `order_manifest.txt` are untouched (ADR `2026-10-17-1`).
- JSON: `--json` and `--plan-json` payload keys stay (`migrations_applied`,
  `migrations_skipped`, `pending_migrations`); only the human renderer changes.
- Exit codes: derived once in the command tail from `UpgradeOutcome.exit_code`; no change.
- Writes: a dry run still writes nothing; this change adds no filesystem access.

## Open questions (resolved during plan)

1. Does the new heading wrap at the 80-column golden width? It is a plain `console.print`
   line, not a fixed-size panel — no width arithmetic is involved, so no new wrapping rule
   is needed. Verified by the golden itself after the change.
2. Should the predicted-verdict block's docstring name both headings? Yes — reword to
   "the run's applied list" so the comment cannot drift stale again.
3. Is a changelog entry warranted? Yes — user-visible output change; a
   `docs/changelog/unreleased/6234.fixed.md` fragment (the repository's current convention),
   not an edit to `docs/changelog/CHANGELOG.md`.
