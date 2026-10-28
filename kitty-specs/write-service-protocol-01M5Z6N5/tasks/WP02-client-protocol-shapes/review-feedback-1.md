# WP02 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The structure is sound: RED-first holds (6706ed15 fails collection
before 8cea0847), the 208 targeted tests pass, ruff/format/mypy are clean, the binder is all or
nothing on the conflict paths, and the allowlist growth (+11 / -1, cap 229 -> 239, category 7
1 -> 2) is priced against #6195 with `requires_issue: true`. The items below are defects against
the WP prompt, the data model or NFR-003 and must be fixed. Each needs a red-first test.

## Must fix

1. **`from_wire` leaks `AttributeError` instead of `ProtocolShapeError`**
   (`src/specify_cli/status/write_service_protocol.py:306-311, 338, 361-365`).
   `DurabilityAck.from_wire([])` and `BatchDurabilityAck.from_wire({"units": ["x"], "fsyncs": 1})`
   both raise `AttributeError: ... has no attribute 'get'`. The prompt (T005) requires
   `ProtocolShapeError` on a missing or mistyped field, and a client adapter will catch only that.
   Fix: reject a non-`Mapping` wire at the top of every `from_wire` (one shared helper), and check
   each batch unit is a mapping. Tests: one non-mapping case per shape, plus a non-object batch unit.

2. **The endpoint reader accepts `schema_version: true` and `1.0`** (`:515`).
   `document.get("schema_version") != 1` is false for `True` and `1.0`, so both read as valid.
   `port` and `pid` already exclude `bool`; `schema_version` must match: an `int` that is not a
   `bool` and equals 1. Add both values to `test_a_malformed_endpoint_file_is_refused`.

3. **The token travels in the exception chain of a MALFORMED refusal** (`:501-504`).
   `raise EndpointFileError(...) from exc` keeps the `json.JSONDecodeError` as `__cause__`, and its
   `.doc` attribute is the whole file text, token included (verified: a file
   `{"token":"SSS...", bad` gives `"SSS..." in error.__cause__.doc`). `UnicodeDecodeError.object`
   holds the raw bytes in the same way. The `str()` is clean, but any logger or traceback renderer
   that walks the cause can print it. That breaks NFR-003 and the "no token leak path" rule.
   Fix: `raise ... from None` on both decode paths. Test: assert `error.__cause__ is None`, or that
   the token appears nowhere in `traceback.format_exception(error)`.

4. **OS errors escape as raw `OSError`, not as the named refusal** (`:545-550`, `:484-497`).
   `read_endpoint_file` runs `exists()`, then `lstat()`, then `open()`. When the service shuts down
   and removes the file between those calls, the reader raises a bare `FileNotFoundError`. A
   `PermissionError` on the file or on its directory is also raised bare. User Story 3 requires
   refusing "with a named error". Fix: map `FileNotFoundError` to `MISSING` and any other `OSError`
   to `EXPOSED` or `MALFORMED`, with a fixed message and `from None`. Better: open once with
   `os.open(path, O_RDONLY | O_NOFOLLOW)` and run the mode, owner and regular-file checks on
   `os.fstat(fd)`. That also closes the lstat-then-open TOCTOU window. The parent-directory mode
   check stays as is. Test: monkeypatch `Path.open` or `os.open` to raise `FileNotFoundError` and
   `PermissionError`.

## Should fix (same cycle if cheap)

5. **`protocol_versions` and `protocolVersions` must be ascending** (data model: "non-empty,
   ascending"). `_versions` (`:321-324`) accepts `[2, 1, 1]`. Require strictly ascending, which
   also rules out duplicates.
6. **Silent empty defaults in `transition_unit_from`** (`:295`, `:300`). When the first row has no
   `actor` or `wp_id`, the request goes out with `""` and is refused later as
   `REQUEST_MALFORMED`. Raise `ProtocolShapeError` here instead (anti-pattern item 3).
7. **`DurabilityAck` accepts a negative `appendedLines`, and `BatchDurabilityAck` accepts empty
   `units`.** The contract says one ack per unit of a batch that holds 1..64 units. Require
   `appendedLines >= 1` (or `== len(eventIds)` if WP03's contract states that) and non-empty `units`.
8. **Windows skips the symlink and regular-file checks too** (`:485`). Only the mode-bit check is
   POSIX-only. `lstat`, `S_ISLNK` and `S_ISREG` work on Windows, and the data model says "the
   reader checks what the platform exposes". Move the `os.name == "nt"` early return to just
   before the mode and owner checks.

## Nits (non-blocking)

- `bind_event_bridge` (`src/runtime/next/_internal_runtime/events.py:305-324`) copies the two
  conflict predicates instead of reusing their authorities. The transition half compares
  `type(bound) is not type(port)`, but `bind_work_package_transition_port` compares `_port_key`
  (module plus qualname). After a module reload the pre-check therefore refuses a port that the
  real binder accepts. That fails closed, so it does not break all or nothing, but the two
  definitions of "conflict" have drifted apart. Consider a small public predicate per half.
- `events.py:325-327` leaves three blank lines after `bind_event_bridge`. The file is on the
  formatter ratchet, so no gate catches it. Campsite rule: make it two.
- The operator ruling for the new category (`category_c_write_service_client_6675`)
  appears only in the WP history note. DM-01M5Z6TDWPD1RGWDNXQGQW27C9 records the earlier ruling
  (binder into the existing category). Cite the superseding ruling in WP04's ADR or changelog so
  the allowlist rationale points at a recorded decision.

## Anti-pattern checklist

1 Dead code: PASS (priced allowlist entries with #6195 exit, operator-approved) ·
2 Synthetic fixture: PASS · 3 Silent empty return: FAIL (item 6) · 4 FR coverage: PASS ·
5 Frozen surface: PASS · 6 Locked decision: PASS (no transport, C-001) ·
7 Shared-file ownership: PASS (out-of-map seam test edit recorded in history) ·
8 Production fragility: FAIL (items 1 and 4: untyped errors escape the typed surface)
