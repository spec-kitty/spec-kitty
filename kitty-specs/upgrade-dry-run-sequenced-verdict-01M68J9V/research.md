# Discovery — upgrade dry-run sequenced verdict (#6552)

## Question

Does `spec-kitty upgrade --project --dry-run` still report a migration as
`not needed (project already in target state)` when an earlier migration in the same run
would have made it needed, on `origin/main` `35318ef51c`? And what is the smallest honest
way to make the preview agree with the real run?

## Evidence gathered

### The defect reproduces on current `main`

A freshly initialised project (`spec-kitty init --ai claude --non-interactive`, isolated
`HOME`, `CI=1`) seeds both merge-driver `.gitattributes` lines and the *row-aware*
`merge.spec-kitty-issue-matrix.name`. The 3.2.6 gate-artifact migration declares the same
key with the *filled-side* name, so its `detect()` is True on that project while
`3.2.6_issue_matrix_driver_repoint`'s `detect()` is False (the configured name already
equals the row-aware name it wants). Removing the repoint's clone-local ledger record — the
state of any project upgraded from a build that predates the repoint — recreates the
reported pair, and the two modes disagree:

```text
dry:  ○ 3.2.6_issue_matrix_driver_repoint
      ! Migration 3.2.6_issue_matrix_driver_repoint not needed (project already in target state)
real: ✓ 3.2.6_issue_matrix_driver_repoint
```

`Migrations applied:` differs by exactly that one entry, which is the reported symptom.
The dry run wrote nothing (`git status --porcelain` empty in the fixture).

Note: on a project whose ledger already records the repoint, `init`'s ledger seed makes the
pair moot, which is why a bare "fresh `init` then upgrade" no longer shows it. The generic
mechanism (a `detect()` that reads state an earlier migration writes) is unaffected by that.

### Where the divergence lives

- `src/specify_cli/upgrade/runner.py:347` — the run loop applies migrations in manifest
  order; the verdict comes from `_apply_migration` one at a time.
- `runner.py:477` — `migration_needed = migration.detect(self.project_path)`; under
  `dry_run` nothing before it has written, so this reads the pre-run tree.
- `runner.py:509-521` — `not migration_needed` returns status `skipped` with the
  `not needed (project already in target state)` warning.
- `src/specify_cli/upgrade/migrations/_merge_driver_seeding.py:112-115` — the seeding
  `apply()` returns early under `dry_run`, so a predecessor's writes never land.
- `src/specify_cli/upgrade/migrations/m_3_2_6_issue_matrix_driver_repoint.py:30-37` —
  the module docstring already records the dependency ("must run AFTER
  `m_3_2_6_gate_artifact_merge_drivers`"), and `order_manifest.txt:120-121` orders them.
- `tests/compat/test_dry_run_parity.py:1-4` — the standing requirement: the dry run must
  report the same pending work a real run applies. #3336 pinned the *selection* set, not the
  per-migration `detect()` verdict, which is where this divergence lives.

### Prior art read

- `1b5bae2742` (#6629) — the closest precedent: the dry run's *promotion preview* was made
  to agree with the real run by asking the selection rule what a pending adoption will
  settle, instead of copying a second source of truth. Small, targeted, no writes.
- `tests/upgrade/preview_support/` — the repo's *test-only* exact-preview technique is
  "copy the project including `.git` and run the real upgrade on the copy". It confirms the
  copy is the only exact simulation, and that it belongs in tests, not in the product path.
- `src/specify_cli/upgrade/migrations/order_manifest.txt` — the single execution-order
  authority (ADR 2026-10-17-1 §2). Its comments already record ordering *reasons*
  (`runs last so every earlier gitignore backfill has written the whole-folder lines it
  narrows`), so declared order dependencies are an established concept here.

## Decisions

### D-001 — Simulate the sequenced verdict; do not copy the project

Three shapes were considered:

1. **Throwaway copy + real `apply()`** (the issue's most exact option). Rejected: it
   multiplies the product surface (`worktrees/`, git worktree pointers, global `$HOME`
   surfaces several migrations write) and turns "a dry run writes nothing anywhere" into a
   promise about a copy. Its justified home is `tests/upgrade/preview_support/`, where it
   already lives.
2. **Declared detect-input predecessors, consumed by one sequencing decision in the
   runner** (the issue's middle option). Chosen. Exact where the relationship is declared,
   O(1), no writes, no copy, and the real run's code path is untouched.
3. **Wording only.** Adopted as the fallback half: an undeclared dry-run skip stops
   claiming target state and claims only the current tree.

### D-002 — Declare detect inputs, not execution order

The new declaration is `BaseMigration.sequenced_after`: the ids whose application, earlier
in the same run, changes what this migration's `detect()` reads. It never reorders
anything; `order_manifest.txt` stays the order authority (C-001), and a declaration that
contradicts the manifest changes no sequence.

### D-003 — Prediction is an `applied` verdict, not a new status

A declared dependent whose predecessor this run reports applied is reported **applied** in
the dry run, with a change line naming the predecessor (`dry-run: would apply after <id>`).
That makes `Migrations applied:` (and the `--json` `migrations_applied`) agree with the real
run instead of introducing a third verdict that every consumer would have to learn. The
prediction still honours `can_apply` and is only taken when the predecessor is in this
run's selection.

### D-004 — Real runs are untouched

The prediction branch is reachable only under `dry_run`: in a real run the predecessor has
already written, so `detect()` answers for itself. Real-run warnings, records and writes
stay byte-identical (C-002); the `not needed (project already in target state)` wording is
kept for real runs and replaced by `not needed on the current tree` for dry runs.

## Open questions (for specify/plan)

- Should the worktree pass get the same prediction? Scoped out (C-004): worktree verdicts are
  per-worktree, are not reported in `Migrations applied:`, and carry no skip message to
  correct. Revisit only if a worktree-local report is ever added.
- Should undeclared dependencies be *detected* rather than declared (e.g. by probing
  `detect()` on a copy)? Rejected for this mission: it is the copy approach of D-001 on a
  smaller scale, and its cost is unbounded per migration.
