# Tracer: design decisions

One entry per decision: `YYYY-MM-DD · actor · <decision> — <why>`.

---

2026-10-19 · operator · Styleguides reach-only when sourced; table DIRECTIVE_034/030/037, always emitted — same defect class as #6404.
2026-10-19 · operator · PROJECT_001 is project-wide intent; rename slug, retire dead requires->mission_type edge — it is built from project_intent.
2026-10-19 · operator · One language authority, multi-language evidence, hash changes only for >1 language.
2026-10-19 · operator · jvm family tag; java and kotlin imply jvm; retag shared JVM toolguides in core + open-packs re-seed + pin bump in this Mission — avoids a Kotlin+Gradle regression.
2026-10-19 · operator · Styleguide sources travel as source_urns (request hash changes, ADR 2026-04-17-1 amended).
2026-10-19 · claude-code/opus · Upgrade-outside-git guard lives in the runner, not the shipped rc35 migration — DIRECTIVE_044 forbids editing a shipped migration.
2026-10-19 · claude-code/opus · Language catalog in charter.offering.shared, authority in charter.activation — offering cannot import activation.
