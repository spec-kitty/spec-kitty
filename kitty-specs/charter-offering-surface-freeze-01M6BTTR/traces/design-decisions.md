# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Census lives at tests/architectural/charter_offering_public_surface.yaml (gate asset, never wheel data); api.__all__ stays a literal so static parsers keep working; facade provenance is read from the existing _FACADE_TABLE rather than duplicated; classification is compared to test_doctrine_census.DISPOSITION by longest prefix.

2026-11-01 · reviewer-renata · Aggregate review found one defect: the offering README's census link used ../../ instead of ../../../, so it resolved to src/tests/. Fixed in its own commit. Everything else in the aggregate diff held: C-003 no longer asserts the pre-ADR-0004 position, the census gates pass on the integrated tree, no machine-local paths or non-operator authors in history.
