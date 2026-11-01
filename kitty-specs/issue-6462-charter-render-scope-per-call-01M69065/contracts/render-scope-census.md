# Contract — render-scope census (deterministic guards)

Owner: `tests/charter/test_charter_render_scope_6462.py`. Purpose: make "the CLI parses
only the doctrine it reads" a checked invariant instead of a hope, without asserting
wall clock on a shared host (#6858's rule: count the work, not the seconds).

## What is counted

| Counter key | Production seam | Meaning |
|---|---|---|
| `graph` | `parse_shipped_yaml` on `*.graph.yaml` | one built-in DRG fragment actually parsed |
| `profile` | `parse_shipped_yaml` on `*.agent.yaml` | one agent-profile document actually parsed |
| `paradigm` / `directive` / `tactic` / `styleguide` / `toolguide` / `procedure` / `mission_step` / `mission_type` | `parse_shipped_yaml` on the matching suffix | one catalog document actually parsed |
| `catalog_scan` | `catalog._collect_ids_from_roots` | one domain scan started |

Memo hits are not counted: the guard charges what a fresh process pays, which is what a
CLI invocation is.

## Clauses

- **C-1 (render ceiling).** A persona render for any action parses at most 60 catalog
  documents and **zero** documents from the tactic, styleguide, toolguide, procedure and
  agent-profile domains.
- **C-2 (board ceiling).** `agent tasks status` parses **zero** graph fragments and at
  most 70 catalog documents.
- **C-3 (positive control).** The same fixture, unscoped, parses strictly more documents
  than the scoped render — proving the guard can observe a difference rather than
  passing because the counter never counts.
- **C-4 (parity).** The rendered charter text and the resolved governance selections are
  byte-identical with and without the scope. A guard that passes by changing output is
  a failure.
- **C-5 (no clock).** No assertion reads a wall clock or a duration. Durations may be
  printed for the report (`-s`), never asserted.
- **C-6 (ratchet direction).** The ceilings move down only. Lowering them is always
  allowed; raising one requires the PR that raises it to explain the new legitimate
  read.
