# Data Model — CLI Boundary Robustness (Phase 1)

This mission has no persistent datastore. The "entities" are the machine-contract
shapes and the boundary state machines the CLI must honor.

## Entity: JSON error envelope (canonical)
- **Shape**: `{"ok": false, "error": {"code": <string slug>, "message": <human string>}}`
- **Invariants**: `error` is always an object (never a bare string); `code` is a stable, machine-branchable slug; `ok` is literal `false`.
- **Home**: `cli/json_contract.py` (single authority, NFR-004); `_doctor_shared.py` re-exports.
- **Emitted on**: every error path of an adopted `--json` command; via the `CliConsole.emit_json`/`print_json` transport seam (stdout only).
- **Example codes**: `not_in_project`, `repo_root_unresolved`, `no_worktree`, `workspace_not_found`, `unknown_mission_type`, `git_resolution_failed`.

## Entity: JSON empty-success payload
- **Shape**: the command's normal success payload with empty collections — e.g. `{"work_packages": []}`, `{"tasks": [], "count": 0}`, or a bare `[]` (glossary). **No `error` key.**
- **Invariants**: exit code 0; parseable JSON; distinguishable from an error only by the absence of the error envelope (SC-005 is 2-state: error vs success, empty = success sub-case).
- **Note**: success payload shapes remain per-command (NFR-004 governs the error envelope only).

## Entity: Config read site
- **States**: `import-time-pointer-read` (fail-soft → returns no value, CLI continues) | `content-load-read` (fail-loud → named message, non-zero exit, no traceback) | `parseable-but-invalid` (degrade like `charter status` → named domain error).
- **Transitions**: unreadable/non-UTF-8 bytes at import-time → soft skip; at content-load → loud named error; malformed-but-parseable at content-load → domain error (#4600 Instance 2).
- **Invariant**: no state emits a raw Python traceback; import-time site stays stdlib+kernel pure.

## Entity: Typer option binding
- **States**: `bound` (normal Typer dispatch → declared default resolved) | `off-binding` (command body reached bare → OLD-style `= typer.Option(...)` params hold the `OptionInfo` sentinel).
- **Invariant**: no `OptionInfo`/`ArgumentInfo` repr reaches user output or participates in logic; off-binding callbacks resolve real defaults (pass explicit values or use resolved defaults).
- **Note**: `Annotated[T, typer.Option(...)] = <real>` params never enter the leaking state (real Python default).

## Entity: `--json`-capable command (for the enumeration gate)
- **Discovery**: structural Typer introspection — any command whose signature declares a bool option flagged `--json` (vocabularies: `json_output`, `--json`, `json: bool`, `output_json`).
- **Attributes**: `is_adopted` (subject to shape assertion) vs `parse-only` (parseability only); `error_driver` (run outside a project) and `empty_driver` (explicit fixture case, extensible list).
- **Aliases**: multi-registration paths (`mission list` / `mission-type list` / `charter mission-type list` / `doctrine mission-type list`) must all resolve through the corrected callee.
