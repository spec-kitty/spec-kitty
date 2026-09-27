# Contract: merge-driver body (`specify_cli.merge.drivers`)

Owner: merge domain. Consumers: `cli/commands/merge_driver.py` (subprocess entrypoint shell) and `merge/git_probes.py` (in-process driver replay). Both MUST call the same body.

## Types

```python
class MergeDriverError(Exception):
    """Unresolvable merge-driver conflict or invalid input. str(exc) is the exact stderr text."""

@dataclass(frozen=True)
class MergeDriverOutcome:
    notice: str | None = None   # stdout notice (review-cycle only today)

MergeDriverBody = Callable[[str, str, str], MergeDriverOutcome]   # (base, ours, theirs)

MERGE_DRIVER_BODIES: Mapping[str, MergeDriverBody]   # key = registered command name
```

## Registered bodies (6)

| Key | Body | Writes | Errors raised as MergeDriverError |
|---|---|---|---|
| `merge-driver-event-log` | `run_event_log_driver` | `ours` via `status.merge_event_log_files` | `EventLogMergeError`, path hardening |
| `merge-driver-meta` | `run_meta_driver` | `ours`, `_META_JSON_KWARGS` + `"\n"` | `JSONDecodeError`, `EventLogMergeError`, path hardening |
| `merge-driver-traces` | `run_traces_driver` | `ours`, union text as returned | path hardening (UnicodeDecodeError propagates, as today) |
| `merge-driver-issue-matrix` | `run_issue_matrix_driver` | `ours`, `indent=2, sort_keys=True` + `"\n"` | `RowMatrixMergeError`, `AcceptanceMatrixParseError`, path hardening |
| `merge-driver-acceptance-matrix` | `run_acceptance_matrix_driver` | `ours`, `indent=2` + `"\n"` (no sort_keys) | same as issue-matrix |
| `merge-driver-review-cycle` | `run_review_cycle_driver` | `ours` (identical → ours; else conflict markers) | path hardening; returns `notice` on collision |

(Body names are indicative; the table keys are binding and must equal the command names derived from `lanes/merge.py::_MERGE_DRIVERS` and the `merge-driver-*` keys of `cli/commands/__init__.py::_COMMAND_REGISTRARS`.)

## Invariants

1. A body never calls `sys.exit` / raises `typer.Exit` and never imports `specify_cli.cli.*`.
2. Every body runs the path hardening first (replay is hardened like the subprocess path).
3. Foreign errors are wrapped `MergeDriverError(str(exc)) from exc` — stderr stays byte-identical.
4. Shell: `MergeDriverError` → `typer.echo(str(e), err=True)` + `typer.Exit(1)`; `outcome.notice` → stdout; otherwise exit 0. Command names, argument order and exit codes are unchanged (C-001).
5. Resolver: `MERGE_DRIVER_BODIES.get(command_name)` via a function-local import; unresolvable → existing fail-closed `GitProbeError` path.
