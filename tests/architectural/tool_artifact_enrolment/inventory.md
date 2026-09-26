# Tool-artifact enrolment inventory (WP10 / owner contract C1, FR-007/FR-013)

<!-- markdownlint-disable MD037 -->

Generated input: the AST scanner in `test_enrolment_inventory.py`
(`discover_write_sinks`) walks the generated-write **surfaces** and self-asserts this
table in BOTH directions — **undercount** (every discovered generated-write sink is
enrolled here) AND **overcount / ghost** (every row still maps to a live sink). Cloned
from `tests/architectural/untrusted_path_audit` per contract C1 ("Reuse, do not
reinvent … clone that shape. Never hand-write the list").

**Row identity.** Rows are compared by the drift-proof composite `(file, qualname,
token)` from `tests.architectural._ratchet_keys.composite_key_from_file`. The `line` in
the `file:line` locator is **non-authoritative** (a jump-to aid, never compared): a
blank/comment insertion that shifts a sink's line leaves the inventory GREEN; a real
edit/rename to the sink line changes the `token` and it goes RED. Long tokens are
truncated at 60 chars with a `…` marker.

**Freshen path.** When a sink genuinely changes, re-run the tool and paste the emitted
rows — never hand-type a token:

```
uv run python -c "from tests.architectural.tool_artifact_enrolment.test_enrolment_inventory import discover_write_sinks, composite_row_key
for s in discover_write_sinks():
    rel, q, t = composite_row_key(s.rel_path, s.line)
    print(f'| {s.locator()} | {q} | {t} | {s.sink_op} | pending-owner |')"
```

**Dispositions.** `enrolled` — the write already lives inside a lifecycle transaction
(commit-or-revert, C2). `pending-owner` — a generated-write site the owner
(`coordination/transaction`) must enrol; the owner drives these to zero as it lands.

**Scope boundary.** The surfaces are the generated-write **owner** surfaces:
`coordination/transaction.py` (the transaction owner) and
`merge/bookkeeping_projection.py` (the bookkeeping projector, the mission's
duplicate-compensator crime scene). As the owner grows to enrol further sinks, add its
surface to `ENROLMENT_SURFACES` and re-freshen from the tool output.

## Generated-write sinks

| file:line | qualname | token | sink op | disposition |
|---|---|---|---|---|
| src/specify_cli/coordination/transaction.py:910 | BookkeepingTransaction._rollback | self . _snapshot_path . write_bytes ( | .write_bytes() | enrolled |
| src/specify_cli/merge/bookkeeping_projection.py:177 | _restore_optional_bytes | path . write_bytes ( original ) | .write_bytes() | pending-owner |
| src/specify_cli/merge/bookkeeping_projection.py:304 | _project_status_bookkeeping_to_target | trusted_target_events_path . write_bytes ( union_events_byte… | .write_bytes() | pending-owner |
| src/specify_cli/merge/bookkeeping_projection.py:305 | _project_status_bookkeeping_to_target | trusted_target_status_path . write_bytes ( | .write_bytes() | pending-owner |
| src/specify_cli/merge/bookkeeping_projection.py:311 | _project_status_bookkeeping_to_target | trusted_target_status_path . write_bytes ( source_status_byt… | .write_bytes() | pending-owner |
| src/specify_cli/merge/bookkeeping_projection.py:559 | project_post_checkpoint_commits_to_target | trusted . write_bytes ( content ) | .write_bytes() | pending-owner |
