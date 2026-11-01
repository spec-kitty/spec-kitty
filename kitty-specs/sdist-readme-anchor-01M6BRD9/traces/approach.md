# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · orchestrator agent · Grounded #6926 on main 7e2ca9fdc: hatchling compiles sdist include/exclude with pathspec.GitIgnoreSpec, so the bare `README.md` / `CHANGELOG.md` include entries match at any depth; 745 stray members ship today (698 kitty-specs, 33 docs, 11 tests, 2 scripts, packs/README.md). Approach: red-first archive test in test_packaging_safety.py (pure helper + planted self-test + archive assertion), then anchor both entries with a leading `/` and add `site/**` to exclude.
2026-11-01 · orchestrator agent · Red confirmed on the base: 732 members under docs/ + kitty-specs/ (the new Mission folder added one to the grounding's 698), config twin red on site/**. After anchoring, the before/after listing showed 0 added, 746 removed, built-in sha256-identical — but the root CHANGELOG.md is a symlink to docs/changelog/CHANGELOG.md, so the anchored sdist carried a dangling link. The first positive control (`name in rooted`) passed on it; tightened to "regular, non-empty file" and re-ran red before fixing.

## Close assessment (2026-11-01)

The approach held: red-first archive test, then anchoring. The one surprise (root CHANGELOG.md is a symlink into docs/) came from a before/after archive comparison, not from the issue's Done-when — comparing the archives, not just asserting names, is what found it. Independent review (2 cycles) added tests/ and scripts/ to the forbidden trees and named the sdist-from-sdist limitation.
