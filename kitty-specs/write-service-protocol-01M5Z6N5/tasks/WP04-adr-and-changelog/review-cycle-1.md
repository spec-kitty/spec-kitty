---
affected_files: []
cycle_number: 1
mission_slug: write-service-protocol-01M5Z6N5
reproduction_command:
reviewed_at: '2026-10-27T21:15:10Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The ADR is well built: it covers every operator ruling and every
provisional default, uses derived markers, and has a Pros and Cons section. The index row and the
amendment section are in place. The squad fold delta on the WP02 and WP03 files is sound:
- RED first: at 7ab7466f, 23 tests fail and 89 pass.
- At HEAD every contract tool exits 0, both bundles are byte-identical, vacuum reports 0
  violations, and ruff, format and mypy are clean.

Two statements are wrong, and implementers will build against them; one docs gate is red.

## Must fix

1. **The canonical row encoding drops the CLI's PII sanitization.** Affected:
   - ADR 2026-10-27-1 D-5, "Encoding": "the CLI's canonical encoding
     (`json.dumps(row, sort_keys=True)`)".
   - `contracts/mission-write/schemas/TransitionUnit.yaml`, description: "the CLI's canonical
     encoding (ADR 2026-10-22-1 D-7: keys sorted)".

   The CLI's one encoding authority is `specify_cli.status.store.serialize_event_line`, which is
   `json.dumps(sanitize_event_for_log(event_dict), sort_keys=True)`.
   `sanitize_event_for_log` (`src/specify_cli/events/sanitizer.py`) strips `machine_name`,
   `hostname`, `workspace_path`, `developer_name` and `developer_email` at every nesting level, and
   replaces the session timestamps. ADR 2026-10-22-1 D-7, the record this ADR cites, names that
   function too (line 149).

   The client sends `row.to_dict()` unsanitized (`transition_unit_from`). A Java service built from
   this ADR and contract would therefore write PII into the committed event log, and its bytes
   would drift from the CLI's.

   Fix: in D-5 and in the `TransitionUnit` description, state that the encoding is
   `store.serialize_event_line`: `sanitize_event_for_log`, then `json.dumps(..., sort_keys=True)`.
   State that a retry is compared on the sanitized rows. If the operator would rather have the
   client sanitize before sending, say so instead and make `transition_unit_from` do it, with a
   test. Either way, one side must own the sanitization, and the documents must say which.

2. **The changelog miscounts the protocol-only codes** (`docs/changelog/CHANGELOG.md`, the
   #6675 bullet). It says "20 verbatim plus 8 protocol-only ones", but since the squad fold added
   `SERVICE_DRAINING` there are 9. The ADR and the module CHANGELOG already say 9.

3. **The new ADR fails the docs description gate.**
   `tests/docs/test_description_length_gate.py::test_live_tree_is_clean` reports
   `TOO_LONG docs/adr/4.x/2026-10-27-1-...md (length 208)`; the limit is
   `MAX_DESCRIPTION_LENGTH = 180`. Shorten the frontmatter `description` to 180 characters or
   fewer. This is the one failure in the ADR gate set that this mission causes.
   - The other failures in that set are environmental. `test_upgrade_recovery_preservation.py`
     has 117 errors and 1 failure because this checkout is shallow
     (`git show 6e60f8b4…` exits 128), so those are not yours.

## Should fix

4. **The ADR Confirmation section is stale.** It says "the protocol header on all but the
   handshake", but `/health` is now exempt too: see D-4 and
   `test_every_operation_but_handshake_and_health_requires_the_protocol_header`.
5. **ADR 2026-10-22-1 has no header pointer.** T018 asked for an "Amended by ADR 2026-10-27-1
   (open question 3, D-7)" line in its header block. The amendment exists only as a section at
   the end, so someone reading the header cannot see that this ADR is amended. Add the line; it
   should also name D-3, which the squad fold amends as well.

## Nits on the fold delta (non-blocking)

- `transition_unit_from`: `_SURFACE_BY_TARGET[target.value]` raises a bare `KeyError` for a write
  target it does not know. A `ProtocolShapeError` would keep the typed surface.
- `WriteRefusal.from_wire` does not check that a reason travels under the code it is bound to.
  The contract now pins that pairing. A lenient reader is acceptable, but say so in the docstring.

## Anti-pattern checklist

1 N/A (docs) · 2 PASS · 3 PASS · 4 PASS (FR-019) · 5 PASS (ADR 2026-10-22-1 decisions not
rewritten; amendment section only) · 6 FAIL (item 1 contradicts ADR 2026-10-22-1 D-7's encoder
clause) · 7 PASS (squad dispositions recorded) · 8 N/A
