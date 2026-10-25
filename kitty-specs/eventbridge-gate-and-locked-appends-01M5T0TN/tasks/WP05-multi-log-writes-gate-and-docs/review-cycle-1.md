---
affected_files: []
cycle_number: 1
mission_slug: eventbridge-gate-and-locked-appends-01M5T0TN
reproduction_command:
reviewed_at: '2026-10-25T21:15:18Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review, cycle 1: changes requested

Verified and passing: the scanner extraction is behaviour-preserving (the removed block and `_write_site_scan.py` differ only in the `_classify_call` -> `classify_call` rename); 107 gate tests pass; the docs tests pass (357); ruff and format pass; mypy reports only the 3 moved and 2 conftest errors. The red-first claim also holds: over `origin/main`'s `src` the raw census reports exactly the eight G-5 appends. T018's AST pins are fine.

## Blocking

**Issue 1: the raw census misses the `kitty-ops/<op>.jsonl` family (FR-005, FR-006).**
The gate resolves paths with its own resolver (`_path_families` / `_helper_families`), not the shared `_Resolver`. That resolver does not follow a helper that returns a local, and it does not follow `self.<method>()` helpers. As a result:
- On `origin/main`, none of the three raw Op-record writes in `invocation/writer.py` was reported, by the raw census or as an unresolved pin: the `os.open(... O_APPEND ...)` at :160 and :199, and the exclusive create at :249.
- In today's tree, `InvocationWriter.write_started` (`path = self.invocation_path(...)`, `path.open("x")`) is not seen. The WP expected this exclusive Op create in the raw ledger with a reason, and the empty `EXPECTED_RAW_LOG_WRITERS` is a symptom of the miss. The `m_3_3_0_op_record_schema_v2` rewrite (`os.replace(tmp_path, path)` over Op records) is a migration the WP also expected ledgered, and it is not seen either.
- Mutation run against the scanners: adding a method `rogue_append` to `writer.py` that does `path = self.invocation_path(i); path.open("a").write(line)` gives `raw=set()` and `unres=set()`, so the gate passes. A module helper `def journal_path(d): p = d / "run.events.jsonl"; return p`, used as `journal_path(d).open("a")`, is also not reported.

Fix:
- Resolve through the shared `_Resolver`, which already follows a local returned from a function, or reach the same strength. Also resolve `self.<helper>()` / `cls.<helper>()` method returns.
- Ledger `write_started` (exclusive create, collision detection) and the migration rewrite with reasons.
- Add synthetic floors for the helper-returning-a-local shape and the method-helper shape. Add one floor that writes a per-Op trail through `invocation_path`.

**Issue 2: NFR-004 (the gate runs under 5 s) is not met and not measured.**
Timed on this box (1370 files; a CPython 10^7-iteration loop takes 0.59 s, so the machine is normal speed):

| Step | Time |
|---|---|
| `scan_door_calls` | 4.1 s |
| `scan_raw_log_writers` | 4.5 s |
| `scan_unresolved_log_writes` | 4.5 s |
| Gate's own scans, total | about 13 s |
| Shared parse, on top of that | about 6.6 s |
| Status gate's `scan_write_sites`, for comparison | 4.8 s |

The profile shows that nearly all of the time goes to repeated `ast.walk`. `_write_paths` runs twice per module (once for raw, once for unresolved). `_docstring_ids`, `_module_constants` and `_helper_families` each walk the whole module. `scan_door_calls` walks every function twice, then the tree again.

Fix: compute `_write_paths` once per module, shared by both censuses, and build the per-module indexes in a single walk. Then record the measured time, or add a coarse timing assertion.

**Issue 3: `persistence.append_event` in attribute form is not a door (WP: "any alias").**
`_door_of` deliberately skips the `append_event` attribute form. So `import spec_kitty_events.persistence as p; p.append_event(...)` and `from spec_kitty_events import persistence; persistence.append_event(...)` are both not reported (confirmed with synthetic source).

Fix: track names bound to the `spec_kitty_events.persistence` module (`import ... as`, `from spec_kitty_events import persistence [as x]`) and match `<bound>.append_event(...)`. That avoids false positives on unrelated `.append_event` methods. Add a floor for each form.

## Non-blocking

- **Ledger key.** The WP says `(module, path expression)`; the code uses `(module, function, door)` plus a count. I accept this as meeting FR-005/FR-006: a caller in a new function fails, and an extra call in a ledgered function fails on the count. Path expressions here are mostly parameter names, so they would add little. One known weakness: a ledgered function redirected to a different log still passes. Say so in the module docstring as a deliberate deviation from the WP text.
- **`docs/architecture/event-ledger-writers-and-readers.md`:**
  - The "What does not hold" bullet still says "No `EventBridge` module exists in `src/`".
  - The G-1 Evidence column still says "no `EventBridge` in `src/`".
  - The G-2 row keeps the stale sentence "No writes gate for event logs other than `status.events.jsonl`" after "Partly closed".
  - G-1's remedy still says "two existing doors".
  - The writer rows you rewrote keep stale line numbers. Current lines: `writer.py` `write_started` :223, `write_completed` :250, `_append_line_no_follow` :188; `lifecycle.py` :58; `engine.py` :108/:110; `decision_log.py` :249; `mission_v1/events.py` :62.
  - "contract below" points to a bullet that sits above it. Consider citing the contract itself as well: ADR 2026-10-22-1 D-4, or `kernel/event_log_append.py`'s module docstring.
- **`docs/development/reference/events-in-core.md`** says the gate "fails any raw write to a named log or any other `.jsonl`". State the residuals: a path that arrives only as a parameter, an imported constant whose name does not read like a log, and module-level writes, which `_write_paths` only scans inside functions.
- **`CHANGELOG.md`:** both new entries add a blank line before the next bullet. The neighbouring entries are contiguous, so this makes a loose list. Drop the blank lines.
