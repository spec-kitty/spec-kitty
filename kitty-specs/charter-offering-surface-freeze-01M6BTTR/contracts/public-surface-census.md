# Contract — `charter.offering` public surface census

This contract fixes the shape and the invariants of
`tests/architectural/charter_offering_public_surface.yaml`, the file that freezes
the charter offering public contract surface (issue #6285, P1 of epic #6099).

## C-001 — One frozen list

There is exactly one canonical list of exported offering symbols: the `surface`
section of the census. `charter.offering.api.__all__` remains the literal a
maintainer reads; the gate asserts the two are equal **in order**. Neither may be
derived from the other at import time (static gates parse the literal).

Change procedure: add/remove/reorder in both, in the same commit. A census edit
without a `__all__` edit (or the reverse) fails
`test_census_enumerates_exactly_the_live_surface`.

## C-002 — Facades are proven against the list, not against themselves

Every `surface[]` row records the `charter.*` facades that re-export that symbol
*from* `charter.offering.api`. The gate proves the record by reading the identity
table the facade gate parameterises over
(`tests.architectural.test_charter_facades_reexport_offering._FACADE_TABLE`) and
comparing sets. If the table's shape changes so the comparison cannot be made, the
gate fails — it never silently compares against an empty set.

## C-003 — Disposition is referenced, never restated

`disposition` values are compared to
`tests.architectural.test_doctrine_census.DISPOSITION` by longest prefix. The
census does not carry its own copy of the disposition rules, and the manifest
stays the single authority. A path whose disposition changes in the manifest
makes the census row stale and fails the gate.

## C-004 — Every exported symbol states its DTO direction

`dto_status` is `transitional` for every row. Today's hand-written types are
recorded in `today_type` and (for callables) `signature`, and the target direction
in `dto_target`. This consumes the direction of `spec-kitty-charter` ADR-0004
(tracked in core by #6218) without restating the ADR and without implementing any
DTO.

## C-005 — Classification covers every reached path; the delta is empty

`reached_classification[]` covers the offering paths reached from `src/` (the live
scan `reached_offering_paths()`); each row states its manifest disposition, whether
it is on the frozen surface, its reaching files, and the sanctioned route for
non-public paths. `public_contract_delta` must equal the delta the gate recomputes
and must be empty. A consumer need that is not on the surface and has no sanctioned
route is reported, never widened here.

## C-006 — Non-vacuity

Each new assertion ships with a planted-mutation self-test on an in-memory copy of
the census, in the style already used by the facade gate
(`test_planted_non_identical_offering_reexport_is_reported`). No new assertion may
pass on an empty or unparsable census.
