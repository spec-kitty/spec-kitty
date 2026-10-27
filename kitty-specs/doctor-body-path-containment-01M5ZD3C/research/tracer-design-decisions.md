# Tracer: design-decisions — doctor-body-path-containment-01M5ZD3C

- 2026-10-27 — Predicate lives in `charter.offering.drg.org_pack_loader` (beside `OrgDRGFragment`), re-exported via `charter.drg`; both doctor halves (JSON collector + human renderer) call it, so they cannot disagree.
- 2026-10-27 — Authored fragment nodes only (operator decision). Discovered artifact nodes keep their kind-owned validators.
- 2026-10-27 — New JSON key `org_drg.body_path_escapes`, always present (operator decision), plus messages on the existing `errors` channel that drives the exit code.
