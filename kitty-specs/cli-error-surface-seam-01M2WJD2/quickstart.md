# Quickstart — adopting the guarded-read + presentation seam

**Mission**: cli-error-surface-seam-01M2WJD2

This is the pattern every in-scope command/reader adopts, and the pattern the FR-011
construction gate enforces for future code.

## Reading a state/config/input file in a command

**Before (crashes on bad input):**
```python
raw = yaml.safe_load(path.read_text(encoding="utf-8"))
workflow = WorkflowSequence.model_validate(raw)
```

**After (typed domain error → hook presents it):**
```python
from kernel.guarded_read import read_guarded
from specify_cli...errors import WorkflowFileError   # subclass of GuardedReadError

def _parse(text: str) -> WorkflowSequence:
    return WorkflowSequence.model_validate(yaml.safe_load(text))

workflow = read_guarded(
    path, _parse,
    errors=(yaml.YAMLError, pydantic.ValidationError),
    error_cls=WorkflowFileError,
)
```
The command does **not** try/except for presentation — the global hook renders
`WorkflowFileError` (human line or JSON envelope, exit 1). A genuine bug in `_parse`
that isn't in the declared tuple still surfaces as a traceback.

## Validating operator input (not a file read)

`specify` name validation is *not* a read — raise a domain error directly:
```python
if not slug:                       # no usable ASCII characters
    raise NonAsciiNameError(path=value, reason=f"name {value!r} has no usable ASCII characters")
# NOT: raise typer.BadParameter(...)  # bypasses the hook, forces exit 2/stderr
```

## Hardening a reader while preserving its contract (D5)

```python
# absent input keeps its existing None/empty return:
if not path.exists():
    return None
# only corrupt/malformed input routes to the typed error:
return read_guarded(path, _parse, errors=(json.JSONDecodeError,), error_cls=MissionMetaReadError)
```

## Verifying (per WP)

1. **Red-first**: add an issue-pinned `@pytest.mark.regression` test that runs the
   real command with bad input and asserts a traceback today (RED on the base).
2. **Green**: adopt the seam; the test now asserts exit 1 + actionable message (and a
   JSON object under `--json`).
3. **Back-compat (NFR-006)**: if the WP touches a consolidated error type, assert its
   existing `except` sites still catch it.
4. **Through the entry point**: audit-tail readers are tested via their reachable
   command (e.g. `finalize-tasks` for `wps_manifest`), not reader-level only.

## The gate (WP08)

`tests/architectural/test_cli_error_surface_seam.py` asserts: (a) the global hook is
registered on the top-level app; (b) no in-scope command reaches a read/decode/
resolver outside `read_guarded` (call-graph/AST scan of the named helpers), against a
concrete shrink-only floor; (c) a self-mutation test proves (a) and (b) fail when the
hook is removed or an unguarded read is introduced.
