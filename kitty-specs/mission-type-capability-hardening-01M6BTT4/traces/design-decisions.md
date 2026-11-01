# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi/deepseek-v4.1-flash-1017 · Fact port takes run_dir (authoritative) then an explicit mission_slug fallback; feature_dir.name is never consulted again. Wrappers forward both; the three live ctx call sites thread ctx.run_dir.

2026-11-01 · pi/deepseek-v4.1-flash-1017 · Review round 1 finding: the WP02 prompt said to edit docs/changelog/CHANGELOG.md, but the repository now requires docs/changelog/unreleased/<id>.<section>.md fragments (AGENTS.md:378, contributing.md:362, and PR #6893's landing commit moved an entry into 6893.fixed.md). The entry now lands as 6330.fixed.md, 895 chars, check_changelog_style clean.
