# Discovery — ledger ADR visibility wording (#6362)

Mission: `ledger-adr-visibility-wording-01M68ZKY`. Grounded on `origin/main` at
`dfe9efb0e8` (2026-10-31), in the repository root checkout.

## Decisions

### D1 — The shipped read surface is `spec-kitty migrate ledger [--json]`, and only that

**Evidence.** `src/specify_cli/cli/commands/migrate_cmd.py` registers
`@app.command(name="ledger")` under the `migrate` group; the docstring says "A **read-only**
view of the two-partition migration ledger … This command never commits and never writes a
file", and `--json` "emits the one structured shape the human summary renders from". The report
is assembled by `assemble_report` (WP01) and its pending set comes from
`VersionDetector(repo_root).applicable_migrations(__version__)` — i.e. the single pending source
the ADR's §5 named. `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py` pins the JSON shape and
the states.

**Decision.** The ADR's current visibility decision (§5) and the #E deliverable are reworded to
name `spec-kitty migrate ledger [--json]` and that single pending source. The rejected proposal
(the `doctor migrations` sub-surface plus `upgrade --list-applied`) stays in the ADR, explicitly
labelled historical, with the reason it was not built (one read surface beats two consumers that
could drift).

### D2 — Nothing is implemented; the ADR is what changes

The issue is explicit: "No new command aliases, ledger implementation, or migration semantics
changes." `spec-kitty doctor migrations` and `upgrade --list-applied` do not exist and must not be
added: the closes-out note already records that one surface shipped, and a second surface would
contradict §5's own no-divergence argument. C-001/C-002 in the spec pin this.

### D3 — The state/token vocabulary the ADR already uses matches the shipped command

**Evidence.** `_ledger_step_state` / `_STATE_*` and the `--json` `summary` keys give: `in-place`
("already in place"), `recorded-elsewhere` ("recorded elsewhere but not here"), `pending` ("not
yet applied"), `drift` ("content changed since it ran"). Drift is reported, never re-applied
(`_DRIFT_HUMAN`, module docstring). The two-partition split is the `partition` field on each row
(`tracked` / `clone-local`).

**Decision.** The ADR's partition/pending/drift prose needs no semantic change; only the command
identity in §5 and #E is wrong. The closeout note at ~391-395 (which already explains the
divergence) is kept and re-framed so it records why one surface shipped, rather than reading as a
live disagreement between two current statements.

### D4 — A narrow docs guard, not a broad ADR-prose gate

**Decision.** Add one test under `tests/docs/` that extracts `spec-kitty …` command snippets from
the ADR's §5 visibility section and the #E bullet and asserts each resolves to a registered Typer
path (reusing `scripts.docs._typer_walker.walk`). Red on the current ADR (`doctor migrations` is
not registered), green after the wording fix. It is scoped to this ADR's current visibility
decision on purpose: many ADRs legitimately record proposals that never shipped, so a
tree-wide "every command in every ADR exists" gate would be wrong.

## Evidence gathered

- `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` — stale spellings at lines 221/223
  (§5) and 314 (#E); closeout note at ~391-395 already names `spec-kitty migrate ledger`.
- `src/specify_cli/cli/commands/migrate_cmd.py:1694-1830` — the shipped command, its JSON shape,
  its states, and the single pending source.
- `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py` and
  `tests/scenarios/upgrade/migration-ledger.feature` — existing coverage of the surface.
- Issue #6362 body and both triage comments: original docs deliverable already delivered by PR
  #6387; the residual is this ADR wording only.
- `docs/adr/4.x/index.md:78`, `docs/development/page-inventory.yaml:1349`,
  `docs/development/docs-retrieval-index.yaml:3836` — inventory entries for the edited page; the
  regenerators must stay diff-free after the edit.

## Open questions

None blocking. Residual judgement call recorded for the reviewer: whether the historical
paragraph should keep the file paths of the never-created module
(`cli/commands/_migration_ledger_doctor.py`). Decision: keep the names as prose of the rejected
proposal but drop nothing else, so the trail of what was proposed stays readable; the guard only
scans `spec-kitty …` snippets, so a historical mention without the `spec-kitty` prefix cannot
re-introduce a phantom command path.
