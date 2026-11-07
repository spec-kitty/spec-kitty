# Design decisions tracer

- 2026-11-07 — Repository-local fixture identity is preferred over production identity synthesis or global CI configuration because it repairs the missing test prerequisite while preserving `safe_commit` and the existing assertions.
- 2026-11-07 — Scope tension resolution: smallest viable diff selects the one test file plus required governance/changelog artifacts; no campsite refactor is justified inside this four-command fixture repair.
