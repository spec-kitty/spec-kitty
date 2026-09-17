# Contract — `_bound_wire_review_ref(value)` (wire-projection bound)

Pure function in `src/specify_cli/status/zeitgeist_bridge.py`, applied in
`_broadcast_status_transition` before the payload reaches `to_zeitgeist_attrs`.
Deterministic (same input → byte-identical output). Touches **only** `review_ref`.

## Signature
```python
def _bound_wire_review_ref(value: str | None) -> str | None: ...
```

## Classification (pointer-biased, structural — KISS, no sentence detection)
`value` is a **POINTER** (⇒ returned verbatim) iff any of:
- it is whitespace-free AND contains `:` in `<verb>:<id>` / URI-scheme shape (e.g. `review:WP04`,
  `approval:WP04`, `auto-approval:WP04:2026-09-17`, `https://…`); or
- it contains a path separator (`/`) and **no line break** (covers filesystem paths, incl. paths
  containing spaces).

Otherwise it is **PROSE**.

## Input → output table
| Input `review_ref` | Classified | Output | Notes |
|--------------------|-----------|--------|-------|
| `None` / `""` | — | unchanged | no-op |
| `review:WP04` | pointer | `review:WP04` | verbatim |
| `auto-approval:WP04:2026-09-17` | pointer | verbatim | verbatim |
| `/var/reviews/wp 04 note.md` (>240B) | pointer (path w/ space, no newline) | verbatim | **T5** — never truncated; codec fails closed loudly if it still rejects |
| `"Looks good.\nShip it."` (≤240B after collapse) | prose | `"Looks good. Ship it."` | one-line collapse, no `…` |
| 300-byte multi-line prose note | prose | 237-byte codepoint-safe prefix + `…` (≤240B) | **T1/T6** — byte-identical to codec `_truncate_utf8`; INFO log |
| prose ending mid-multibyte-char at the 240B cut | prose | cut never splits a codepoint | **T6** |

## Invariants
- **Byte bound**: `len(output.encode("utf-8")) <= 240` for every prose output (bytes, not chars).
- **Ellipsis budget**: truncated output = ≤237-byte prefix + `…` (the `…` is 3 UTF-8 bytes).
- **Whitespace-collapse precedes** the byte check AND the codec's `_first_non_printable_attr` guard
  (order-sensitive: a raw newline would otherwise drop the moment independently).
- **Scope**: only `review_ref` is transformed; any other over-bound attr still reaches the codec
  unbounded → existing fail-closed behavior (T8) is unchanged.
- **Offer count**: the transform converts a raise→drop (0 offers) into a valid broadcast (1 offer);
  it never adds a second offer (FR-006/NFR-003).
- **Logging**: a truncation emits one INFO-level log naming that `review_ref` was bounded.

## SUNSET
Marked `# SUNSET: remove when #4327 lands` / `refs #3954`. The structural replacement (dedicated
`summary` attr + `review_ref` pointer-only) is #4327/#4336; when it lands, this helper is deleted.
