# Tracer: Tooling Friction — nightly-suites-green-rework

Seeded at planning; append during implement.

- 2026-10-10 (planning): `spec-kitty charter context`/`doctor charter-packs` refused with LEGACY_CHARTER_STATE on this checkout — the dogfooded `.kittify/doctrine/` was stale on-disk (untracked). `spec-kitty upgrade --project` regenerated it to the already-committed `charter-packs` layout; zero tracked diff. Operator-authorized. Net: a local working-copy regen, not a migration.
- 2026-10-10 (planning): background `pytest` over integration + contract corpus took ~200s setup (corpus scan). Keep repros targeted.
