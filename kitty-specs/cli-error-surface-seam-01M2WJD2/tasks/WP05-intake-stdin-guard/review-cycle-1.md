---
affected_files: []
cycle_number: 1
mission_slug: cli-error-surface-seam-01M2WJD2
reproduction_command: spec-kitty agent tasks move-task WP05 --to approved --mission cli-error-surface-seam-01M2WJD2 --agent claude
reviewed_at: '2026-09-19T12:49:07Z'
reviewer_agent: claude
wp_id: WP05
---

Approved by claude: Review passed: sys.stdin.buffer routes non-UTF-8 stdin through the already-guarded bytes branch → IntakeFileUnreadableError, clean exit 1 with parity to file-path route; scanner.py correctly untouched. Red-first confirmed: 3/6 tests (incl. stdin-vs-file parity) genuinely reproduce the UnicodeDecodeError crash on pre-fix revert, all 6 green with fix. Happy-path + cap-overflow unchanged. Scope: intake.py + new test only; ruff check clean.
