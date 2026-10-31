# Contracts — none for this mission

This mission changes no interface: it adds a documentation record and one additive test guard. No
CLI surface, error envelope, schema or exported symbol changes, so there is no contract to pin here.

The behaviour it does bind is a *repository* invariant, documented and enforced in-repo rather than
as a generated contract:

- the live residual record's URN set must equal the shipped graph's orphan set
  (`test_documented_residual_matches_measured_shipped_orphans`),
- `DOCUMENTED_ORPHAN_RESIDUAL` stays 25 unless the record moves with it.
