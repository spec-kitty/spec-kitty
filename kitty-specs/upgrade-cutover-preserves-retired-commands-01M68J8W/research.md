# Research — the ledger cutover preserves the retired project command files

Mission: `upgrade-cutover-preserves-retired-commands-01M68J8W`
Issue: spec-kitty/spec-kitty#6547
Grounded on: `main@35318ef51c` (2026-10-31)

## 1. What the issue reports, and what is still true

The issue (filed 2026-10-20 15:04Z) reports that a project upgraded through 3.1.2 under the version
window gains 14 project-local `spec-kitty.*` command files on its first ledger-era
`spec-kitty upgrade`, exit 0, untracked or gitignored.

Its own reproduction names the two builds it used:

| Build | Commit | Date |
|---|---|---|
| init (pre-ledger rc7) | `17f02e26` | — |
| upgrade (rc8 with the ledger) | `5068301dd` | 2026-10-20 10:06 UTC |

The adoption floor from #6431 (`49b520ce`, "settle the version floor on first ledger adoption")
landed at 2026-10-20 19:55 UTC — after both the issue and both of its builds.

## 2. Evidence gathered

- `m_4_0_0rc8_backfill_migration_ledger.py` (`_baseline_items`, #6431) stamps every migration
  whose `target_version` is below both the recorded version and `4.0.0rc8` as settled, **on first
  adoption only**, and only `if not migration_settled(ledger, self)`.
- Consequence: the issue's exact steps no longer reproduce on current `main`. A pre-ledger project
  is floor-settled at adoption, so `2.1.4_enforce_command_file_state` and
  `3.0.2_restore_prompt_commands` are stamped `success` and never re-selected. Verified by running
  the issue's shape through `MigrationRunner.upgrade` on `35318ef51c`: no command files appear.
- The surviving hole is the **already-adopted** ledger: a project cut over by an rc8 build *without*
  the floor has `4.0.0rc8_backfill_migration_ledger` recorded `success`, so the floor never runs
  again, and the writers it never recorded are re-selected forever. Reproduced on `35318ef51c`:
  `2.1.4_enforce_command_file_state` applies and writes 14 files; both retirees are settled and
  skipped.
- Additional writer found while proving the fix: `3.0.0_canonical_context` runs `rewrite_agent_shims`
  too, but only when `spec_kitty.schema_version` is absent or `< 3`. A real post-3.0.0 project
  carries `schema_version: 3`, so it is not part of this defect; a synthetic fixture that omits the
  stamp pulls it in and hides the real defect behind unrelated churn. The regression fixture
  therefore stamps `schema_version=3`.
- Only two migrations detect *absence* of a command file and write it back on a post-3.1.2 project:
  `2.1.4_enforce_command_file_state` (`detect()`: any file missing the current version marker) and
  `3.0.2_restore_prompt_commands` (`detect()`: any prompt-driven file missing).
  `2.1.3_restore_prompt_commands` needs a thin shim present; `3.1.1_direct_canonical_commands` needs
  the old shim marker present; `2.0.1_fix_generated_command_templates` needs stale content present.
  With no command files present, none of those three fires.

## 3. Decisions

1. **Fix through the registry supersession table** (`upgrade/supersession.py`, #6589): declare
   `2.1.4_enforce_command_file_state` and `3.0.2_restore_prompt_commands` superseded by
   `3.2.0a4_safe_globalize_commands`. This is the issue's suggested fix 1, and the only option that
   repairs an already-adopted ledger: options 2 (`backfill` records superseded writers `skipped`)
   and 3 (extend the adoption floor) act only at adoption time, which the defect shape has passed.
2. **No shipped module is edited** (DIRECTIVE_044). The substitute keeps `migration_id`,
   `target_version`, the defining module and `content_hash`, so recorded history never reads as
   drift; a direct import still yields the shipped class.
3. **The successor is `3.2.0a4_safe_globalize_commands`**, the last retire, in manifest order after
   both writers (79 and 82) and not itself superseded (91).
4. **No change to `get_applicable`, the runner, the backfill or the #6431 floor** (C-004). One
   declaration site; every consumer already reads it.
5. Leave `m_3_1_2_globalize_commands`'s docstring alone even though it still claims the version
   window bounds it: it is a shipped module, and the operator-facing correction belongs in
   `docs/api/upgrade-lifecycle.md`.

## 4. Open questions (resolved in plan.md / tasks.md)

- Does silencing the writers leave a pre-3.1.2 project with stale local copies forever? No: the
  retire migrations still run in their own slots and remove marked files with a global
  replacement. Pinned by WP01 T005 with a positive control.
- Does the supersession entry need a new migration id? No — #6589 substitutes under the same id.
- Is a `[Unreleased]` changelog entry wanted for a fix that only changes upgrade behaviour? Yes:
  it is user-facing (an upgrade's written file set changes), so it gets an entry and a reference
  paragraph.
