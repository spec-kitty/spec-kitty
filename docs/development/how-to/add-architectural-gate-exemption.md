---
title: Add an exemption to an architectural gate
description: How to exempt a source site from a tests/architectural gate by content, never by line number, for hand-curated allowlists and census gates.
doc_status: active
updated: '2026-09-26'
audience: docs/context/audience/internal/maintainer.md
type: how-to
related:
- docs/development/how-to/index.md
- docs/development/how-to/review-gates.md
---
# Add an exemption to an architectural gate

**Audience**: maintainers and agents whose change trips a `tests/architectural/` gate on a
site that is genuinely allowed (a sanctioned `os.path.join`, a guarded `reset --hard`, a known
OS-detection branch).

Every exemption identifies its site by **content**, never by line number. A line-pinned
entry goes red on any unrelated edit above it and, once stale, can silently bless a new
violation on its old line. The positional-anchor ban
(`tests/architectural/test_ratchet_positional_anchor_ban.py`) rejects line-pinned entries
anywhere under `tests/architectural/`, and its own exemption set is pinned empty.

## 1. Identify which kind of allowlist the gate uses

| Kind | Examples | Entry form | Stale entry |
|---|---|---|---|
| Hand-curated | join allowlist, kernel/doctrine import exemptions, os-detect / lock-ban / clock `_exemptions/*.txt` | content descriptor | **fails** the gate |
| Census | destructive-op, mutation-ownership, overwrite-ownership gates | `CensusKey(...)` | **warns** only |

## 2a. Hand-curated gate: add a content descriptor

The descriptor form is `<repo-relative path>::<qualname>::<token_substring>[::<occurrence>]`.
`qualname` is the enclosing scope and `token_substring` is a distinctive fragment of the
statement's normalised tokens. Add `occurrence` (0-based) only when the same qualname and
token appear more than once in the file.

- In an `_exemptions/*.txt` file, write one descriptor per line.
- In a Python allowlist, add a `ContentDescriptor` entry with a non-empty rationale.

Render the line rather than hand-typing it:

```python
from tests.architectural._content_identity import render_descriptor_line
```

Matching goes only through `tests/architectural/_content_identity.py`
(`resolve_allowlist` + `partition_findings`). One entry suppresses at most one finding.

## 2b. Census gate: add a `CensusKey`

The gate's failure message prints the unexpected site as
`rel::qualname::op#ordinal (line N) tokens=...`. The line is a locator only. Add a literal
to the gate's `_ALLOWLIST`:

```python
CensusKey(rel="src/...", qualname="...", token_line="...", op="...", op_ordinal=0): (
    "why this destructive operation is safe here"
),
```

`op_ordinal` counts identical `(qualname, token_line, op)` sites in source order. A second
identical operation in the same function therefore becomes a new, unexpected site and fails
the gate. If the gate is registered in `tests/architectural/_baselines.yaml` (for example the
mutation-ownership gate's `destructive_op_allowlist`), raise that ceiling in the same change and justify it in review.
Baselines are shrink-only by default.

## 3. Verify

Run the gate you touched and the positional-anchor ban:

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/<gate>.py \
  tests/architectural/test_ratchet_positional_anchor_ban.py -q
```

Do not run the full `tests/architectural/` suite locally; CI owns it.

## See also

- [Review gates: pre-PR / pre-review checklist](review-gates.md)
- Entry-format contract: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/contracts/allowlist-entry-formats.md`
