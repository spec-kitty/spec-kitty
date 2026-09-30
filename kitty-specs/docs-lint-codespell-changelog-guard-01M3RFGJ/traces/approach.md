# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-30 · claude-orchestrator · Seed (plan): add codespell as a pinned dev dependency with [tool.codespell] as the only dictionary config. Two stdlib-only entry points under scripts/docs/: check_spelling.py (a typo pass over docs/**, README.md and packs/built-in/**/*.md; a US pass over docs/guides and docs/context; a US pass over the extracted Unreleased section with line offsets) and check_changelog_style.py (heading, shape, banned-token and length rules). They share one unreleased_section() extractor added to scripts/release/validate_release.py. An always-on, unmasked docs-lint CI job runs both via python -m; make docs-lint runs the same. Planted-violation tests live in tests/docs/. Stacked on PR #5420.

2026-09-30 · claude-orchestrator · WP01 approved (reviewer-renata, cycle 1). Queued for the pre-PR fold: _SectionParser._attach drops prose directly under a ###/#### heading before its first bullet, so banned tokens there escape the guard (a bypass; no live line affected). Fold with a planted red test. Also carry to the PR body: the three edited entries, the 991-char warning entry, and the R-5 locality note.

2026-09-30 · claude-orchestrator · WP04 approved (reviewer-renata, cycle 1; 555 passed across 22 CI-shape files; 4 real-file mutants red). Queued pre-PR fold: harden the docs-lint masking check beyond the literal '|| true' (||true, '|| :', 'set +e', 'exit 0'). PR carry-over: docs-lint is green only with WP03 consolidated; actionlint was not run locally.

2026-09-30 · claude-orchestrator · WP03 approved (reviewer-renata, cycle 1). Queued pre-PR fold: respell 'materialised' at docs/context/charter.md:28 by hand (not in codespell's en-GB_to_en-US dictionary; a dictionary gap, also worth one line in the WP05 docs).

2026-09-30 · claude-orchestrator · WP05 implemented. Queued pre-PR folds: (a) the two scripts resolve a relative --changelog differently (spelling against --repo-root, guard against cwd); unify on the repo root and update the contract; (b) ci-gate-mechanics.md claims inventory_lockfile.py --write refuses a path under docs/, but it wrote docs/development/3-2-page-inventory.yaml fine; verify and correct (campsite, same file).
