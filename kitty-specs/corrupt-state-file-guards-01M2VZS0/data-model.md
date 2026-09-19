# Data Model: corrupt-state fail-closed

## Corruption classes (all three must fail closed)
| Class | Trigger | Raw exception today |
|-------|---------|--------------------|
| malformed JSON | partial write / merge conflict | `json.JSONDecodeError` |
| non-UTF-8 bytes | binary garbage / wrong encoding | `UnicodeDecodeError` |
| wrong-shape (valid JSON) | schema drift | pydantic `ValidationError` |

## Domain error types
| Type | Module | Base | Carries | Status |
|------|--------|------|---------|--------|
| `MissionMetaReadError` | `specify_cli/core/paths.py` | `RuntimeError` | `meta_path`, `cause`, fail-closed message | EXISTING (reuse) |
| `DecisionIndexReadError` | `specify_cli/decisions/store.py` | `RuntimeError` | `index_path`, `cause`, fail-closed message + `run: spec-kitty doctor` hint | NEW |

- `DecisionIndexReadError` lives with its reader (mirrors where `MissionMetaReadError` sits) — NOT in `kernel`, preserving the layer chain.
- Both errors, when presented, MUST include the fail-closed framing + `run: spec-kitty doctor` hint (Q1 decision, FR-004).

## Reuse: `kernel.meta_decode.decode_meta`
Canonical `bytes|str → dict` decoder. Takes bytes (does explicit `.decode("utf-8")`), covering malformed-JSON + non-UTF-8 in one call, raising `MetaDecodeError(ValueError)`. `_decode_index` catches `MetaDecodeError`/`OSError` → wrap; then `DecisionIndex.model_validate` catches `ValidationError` → wrap. A valid-JSON array is rejected by `decode_meta` as non-object before validation (acceptable — still a clean `DecisionIndexReadError`).

## Invariants
- Missing file → empty index (unchanged); never converted to a corrupt-state error.
- Happy-path parse result byte-identical to today.
- `next` catch names `MissionMetaReadError` exactly (no broad `RuntimeError`).
