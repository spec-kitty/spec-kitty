# Contract — CLI error-presentation hook & envelope

**Home**: global Typer error handler registered on the top-level `spec-kitty` app
(`src/specify_cli/cli/…`). Single authority (C-002).

## Behavior

| Condition | stdout | stderr | exit |
|-----------|--------|--------|------|
| `GuardedReadError` (or subclass), no `--json` | — | `Error: <reason>` (one line, names file/handle) | **1** |
| `GuardedReadError` (or subclass), `--json` | one JSON object (below) | — | **1** |
| Typer usage error (missing arg, bad option) | — | Typer's usage text | **2** (unchanged) |
| Any other exception | — | Python traceback | (propagates) |

## JSON envelope (`--json`)

Exactly one object on stdout, nothing else on stdout:

```json
{
  "error": "workflow file 'bad.yaml' is not valid: while parsing a block mapping ...",
  "kind": "WorkflowFileError",
  "path": "bad.yaml"
}
```

- `error`: the actionable human reason (same text as the non-JSON line).
- `kind`: the concrete `GuardedReadError` subclass name.
- `path`: the offending file/handle, or `null` when not path-scoped (e.g.
  `NonAsciiNameError` carries the offending name as `path` or a dedicated field —
  finalized in WP06, but always a stable machine field).

## Invariants

- **INV-1**: no in-scope error path emits non-JSON prose on stdout under `--json`
  (NFR-002).
- **INV-2**: the hook catches only the `GuardedReadError` base family; it never
  converts a Typer usage error (exit 2) to exit 1 (D4).
- **INV-3**: a non-domain exception is re-raised so genuine bugs remain visible as
  tracebacks (D2).
- **INV-4**: the hook is registered on the top-level app (asserted by the FR-011
  gate); no command relies on its own bespoke emitter for the domain base.
