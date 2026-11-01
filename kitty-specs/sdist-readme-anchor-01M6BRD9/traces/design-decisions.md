# Tracer: design decisions

One entry per decision: `YYYY-MM-DD · actor · <decision> — <rationale>`.

---

2026-11-01 · orchestrator agent · Anchor the include (`/README.md`, `/CHANGELOG.md`) rather than exclude the stray trees one by one — closes the leak class instead of adding a fourth tree-by-tree exclude; hatchling's own `packages` handling uses the same leading-slash anchoring (Decision Moment 01M6BRENGKBHJN1K9CMRE6AKDT).
2026-11-01 · orchestrator agent · Still add `site/**` to exclude even though the anchored include no longer matches `site/README.md` — ADR 2026-10-31-1 D-12 names the exclusion, and it keeps the docsite build output out if a later include widens.
2026-11-01 · orchestrator agent · Leave `services/**` / `contracts/**` and their comment untouched — PR #7004 (events-service cut-over) owns those lines.
2026-11-01 · orchestrator agent · Ship the root CHANGELOG.md through `[tool.hatch.build.targets.sdist.force-include] "docs/changelog/CHANGELOG.md" = "CHANGELOG.md"` and drop `/CHANGELOG.md` from include — the repository's root CHANGELOG.md is a symlink into docs/, so excluding docs/ would leave a dangling link; force-include puts the real file at the root while no docs/ member ships (both Done-when clauses hold). Residual: hatchling refuses a missing force-include source, so building an sdist from an unpacked sdist fails; wheel-from-sdist (the supported path, test_sdist_offline_wheel) does not read the sdist target.

## Close assessment (2026-11-01)

All three decisions stand. The `contracts/**` exclude is now redundant for README leakage; removing it stays with PR #7004.
