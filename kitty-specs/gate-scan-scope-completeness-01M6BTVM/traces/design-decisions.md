# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Code scope is derived from the router (the architectural-heavy job's groups other than arch_scan_scope) instead of a second hardcoded src/**+tests/architectural/** list, so the completeness check follows the same authority that decides when the whole battery runs.

2026-11-01 · python-pedro · Reads whose whole path is computed at runtime (_REPO_ROOT / rel) are recorded as indirections, not failures: they name no repository path, and requiring ** for the ~100 such joins would have turned the gate into an exemption registry. A partly dynamic read is still checked at its literal parent.
