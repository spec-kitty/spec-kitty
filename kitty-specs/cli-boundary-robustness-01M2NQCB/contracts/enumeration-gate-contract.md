# Contract — `--json` enumeration gate + OptionInfo guard (WP06)

Two durable (non-transitional) class guards. They may extend
`tests/architectural/test_cli_console_single_seam.py` or live in a new
`tests/architectural/test_json_contract_enumeration.py`.

## G0 — Discovery / triage (WP06 first step)
- Walk the Typer app tree; select every command declaring a bool option whose flag
  string is `--json` (param names `json_output`, `output_json`, bare `json`).
  Introspect the declared option — name-string matching alone is insufficient.
- Classify each into: **adopted-shape** (this mission's owned commands),
  **already-parseable** (parses on the error arm today), **non-parseable-deferred**
  (does not parse — e.g. `events.py` → stderr/empty-stdout). Record the classification.
- The **parse allow-list** = adopted-shape ∪ already-parseable. Non-parseable-deferred
  commands are filed as a follow-up and EXCLUDED from the gate (so it cannot red on
  an unowned command).

## G1 — `--json` enumeration gate
- **Drive (error arm, allow-list)**: invoke each allow-list command outside a project
  (or with an equivalent generic error input); assert C1 parseability; for adopted
  commands assert C2 shape + C4 exit code.
- **Drive (empty arm, explicit list)**: for each command in an extensible
  empty-case fixture list (e.g. `agent tasks status` on a zero-WP mission),
  assert C1 + C3.
- **Failure conditions**: a newly added `--json` command that is non-parseable on
  the error arm; an adopted command that regresses its envelope shape or exit code.
- **Boundary**: cannot cover the import-time #4600 crash (pre-flag-parse) — that is
  NFR-003's red-first test, not this gate.

## G2 — OptionInfo negative-assertion guard
- Parameterized over every `invoke_without_command=True` callback
  (`__init__.py`, `migrate_cmd.py` ×2, `context.py`, `charter/list_cmd.py`).
- Invoke each app with no subcommand; assert combined stdout+stderr contains no
  `OptionInfo` / `ArgumentInfo` / `typer.models.OptionInfo` repr.
- Behavioral/output-based only — no AST or binding-style inspection (cannot
  mislabel the safe `Annotated[...] = <real>` form).
