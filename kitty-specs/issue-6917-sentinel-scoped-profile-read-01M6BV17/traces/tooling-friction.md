# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi:deepseek-v4.1-flash-1017:python-pedro · spec-kitty next generated a review prompt only for WP01 (spec-kitty-next-...-review-WP01.md); the WP02 reviewer had to work from the WP prompt because ...-review-WP02.md did not exist. Recording so the prompt-file naming gap is visible.

2026-11-01 · pi:deepseek-v4.1-flash-1017:python-pedro · WP03's owned_files named docs/changelog/CHANGELOG.md (as the batch brief does), but the repo's PR-body contract and tests/release/test_changelog_fragments.py now require a per-PR fragment docs/changelog/unreleased/<pr>.<section>.md and forbid editing the shared changelog. Landed with 6917.fixed.md instead; the WP file keeps the old path.
