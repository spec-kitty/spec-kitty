# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->
- 2026-09-14 — Seeded. Tooling this mission touches: GitHub Actions workflows (`ci-quality.yml`, `ci-aggregate.yml`, `ci-modules.yml`, `module-tests.yml`, `sonar.yml`), the committed module registry, the `tests/architectural` + `tests/release` gate battery, and the SonarCloud external service.
- 2026-09-14 — `spec-kitty agent decision open/verify` failed twice with `RuntimeError: Global asset input changed: ~/.kittify/cache/slash_commands-assets.json` (#2627 family). Self-healed on retry both times; cost ~1 min. Known issue — a sibling clone running concurrently trips the global-sync startup gate. `spec-kitty next` bypasses it; other verbs need a retry loop.
- 2026-09-14 — `spec-kitty charter context --action specify --json` emits its JSON in a form that a naive `| python3 -c "json.load(sys.stdin)"` pipe could not parse, while redirecting to a file parsed fine. Cost one wasted round-trip. Low severity; noting in case it recurs.
- 2026-09-14 — `spec-kitty charter context --action plan|review|specify --json` returns **`governance unresolved`** for 30+ selected directives (`001-architectural-integrity-standard`, `030-…`, `041-…`, `043-close-defect-class-by-construction`, `044-canonical-sources-and-unification`, …) — all reported absent from `packs/built-in/directives/`. Every one of four squad delegates hit this independently and had to reconstruct its governing directives from `CLAUDE.md`/charter anchors. Pre-existing repo condition; worth its own ticket, since it silently degrades every profile-loaded delegation.
- 2026-09-14 — `spec-kitty agent profile show` resolved from a **different checkout** (`/home/stijn/Documents/SDD/fork/spec-kitty/`) than the working tree. Known global-binary resolution issue; harmless for built-in layer profiles but it means charter diagnostics may describe a sibling clone.
- 2026-09-14 — A `gh run view --log` for one job returned empty (log retention/streaming), forcing a delegate onto sibling runs for evidence. Worth knowing when CI archaeology is load-bearing.
