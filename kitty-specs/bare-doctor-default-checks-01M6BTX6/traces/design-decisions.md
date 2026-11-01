# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Default set capped at command-files, state-roots and ops. identity/topology walk every mission (~690 here) and are not cheap enough for a bare invocation; the issue says 'where cheap'.

2026-11-01 · claude · Changelog lands as docs/changelog/unreleased/6969.fixed.md (the repo's documented per-PR fragment practice) instead of editing CHANGELOG.md's Unreleased section, so two PRs never conflict on the changelog.

2026-11-01 · claude · Review round 1 (independent reviewer) found the completion manifest gate would redden on the changed doctor help; regenerated src/specify_cli/_completion_manifest.json. Also fixed: empty check set now renders as failure (exit 1); no dangling '()' when a command-file issue has no path; corrected two docs that still described the exit-2 guard.
