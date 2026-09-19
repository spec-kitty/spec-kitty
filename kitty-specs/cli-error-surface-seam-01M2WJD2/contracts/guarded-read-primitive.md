# Contract — `kernel.read_guarded`

**Home**: `src/kernel/guarded_read.py` · **Layer**: kernel (no schema/validation libs)

## Signature (indicative)

```python
T = TypeVar("T")

def read_guarded(
    path: Path,
    parse: Callable[[bytes | str], T],
    *,
    errors: tuple[type[BaseException], ...] = (),
    error_cls: type[GuardedReadError] = GuardedReadError,
    mode: Literal["bytes", "text"] = "text",
) -> T:
    ...
```

## Guarantees

1. Reads `path` once (`mode="text"` → utf-8 decode; `mode="bytes"` → raw). No second
   read, no extra `open` beyond the single read (NFR-003).
2. Applies `parse` to the read content and returns its result unchanged on success.
3. On any of `(OSError, UnicodeDecodeError, *errors)` raised by the read or by
   `parse`, raises `error_cls(path=str(path), reason=<actionable message>)` — a
   `GuardedReadError` subclass. The original is chained (`raise … from exc`) for logs,
   but the message the hook prints carries no stack.
4. Any exception **not** in the declared set propagates unchanged (a real bug stays a
   traceback).
5. Never partially writes or mutates state (read-only).

## Caller responsibility

- The caller supplies the format decoder (`json.loads`, `yaml.safe_load` +
  `WorkflowFile.model_validate`, `tomllib.load`, `str`) and the format-specific
  exception tuple (`json.JSONDecodeError`, `yaml.YAMLError`, `pydantic.ValidationError`,
  `tomllib.TOMLDecodeError`, `KeyError`/`TypeError` for missing keys).
- The caller chooses the `error_cls` subclass appropriate to its domain
  (`WorkflowFileError`, `ReleasePyprojectError`, `MissionMetaReadError`, …).

## Non-goals

- No schema knowledge in the primitive (kernel imports no pydantic/tomllib/yaml).
- Not a validator for operator *input strings* (e.g. name slugs) — that is
  presentation-seam territory (a domain error raised directly), not a read.
