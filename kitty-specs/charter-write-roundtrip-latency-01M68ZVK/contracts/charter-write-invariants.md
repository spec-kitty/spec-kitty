# Preserved contracts: the governed charter write path

This mission adds no new external contract. It changes how the compiled charter is written, and
the whole point is that **nothing observable moves** apart from speed. These are the contracts the
change had to preserve, and where each one is pinned.

## C1 — One write authority (INV-9)

Every writer of the governed `.kittify/charter/charter.yaml` goes through
`charter.activation.charter_yaml_io`: one observe → load → mutate-owned-section → round-trip-save
helper. This mission removes a redundant *pass*, not an authority: `prepare_charter_yaml_sections`
is the same helper carrying more than one owned section per cycle, and
`prepare_charter_yaml_section` delegates to it so its eight existing call sites are unchanged.

- Pinned by: `tests/charter/test_charter_yaml_io.py`, `tests/charter/activation/test_charter_yaml_io_sections.py`
- Boundary gate: `tests/architectural/test_activation_boundary.py`, `tests/architectural/charter_activation_boundary_baseline.yaml`

## C2 — Byte preservation of everything the caller does not own

A write replaces only the named owned sections. Authored `governance`, `directives`, `overrides`,
the flat activation keys, comments, key order, document framing and line endings survive byte for
byte. `charter.md` is never written (the `#2772` Landmine-3 clobber).

- Pinned by: `tests/charter/activation/test_charter_yaml_io_sections.py` (merged write must equal
  the sequential writes it replaced, byte for byte, across a document and section matrix),
  `tests/charter/test_compiler_charter_yaml.py::TestPartialMergeRefresh`

## C3 — A no-op write writes nothing

A write whose content is unchanged returns the original bytes, `PreparedYamlWrite.changed` is
`False`, and the file's mtime does not move. A recompile that produces an identical catalog does
not restamp `metadata.generated_at`.

- Pinned by: `tests/specify_cli/cli/commands/charter/test_compiled_charter_single_cycle.py`
  (`test_second_refresh_is_a_no_op_and_keeps_generated_at`,
  `test_unchanged_catalog_preserves_the_authored_timestamp`)

## C4 — Equality verdicts are unchanged

`yaml_documents_equal` decides exactly what it decided before, including for opaque constructed
nodes: tagged scalars, tagged keys, anchors, aliases, and a `.nan` key that is never equal to
itself. The serialise-and-reparse comparison is still the fallback; it now applies to the values
that differ rather than to the whole document.

- Pinned by: `tests/charter/activation/test_charter_yaml_io_equality.py` (freezes the pre-change
  rule and asserts verdict identity over a corpus, with per-category non-vacuity)

## C5 — Fail-closed writes

A write whose inputs changed between preparation and application is refused
(`precondition_changed`), never retried. An unsafe output directory is refused before any write. A
document that cannot round-trip raises rather than silently losing aliases or section boundaries.

- Pinned by: `tests/charter/test_charter_yaml_write_refusal.py`,
  `tests/charter/activation/test_activation_write_target_ledger.py`

## C6 — Layer rule (INV-7)

`charter/activation/charter_yaml_io.py` does not import `specify_cli`.

- Pinned by: `tests/architectural/test_charter_activation_boundary.py` and the baseline file above.

## Performance contract

The write path's cost is pinned structurally, not by a clock: at most 6 whole-document round trips
per recompile (`tests/charter/activation/test_charter_write_roundtrips.py`, with a same-fixture
control at 18), plus a coarser runaway bound on command latency over a read floor
(`tests/performance/test_charter_write_repo_scale_timing.py`). The budgets and the measurements
behind them are recorded in
[ADR `2026-10-31-1`](../../../docs/adr/4.x/2026-10-31-1-charter-write-budget-for-repository-scale-projects.md).
