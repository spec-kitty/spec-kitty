# Tracer: tooling friction

One entry per friction point: `YYYY-MM-DD · actor · <text>`.

---

2026-10-19 · claude-code/opus · tests/specify_cli/cli/commands and tests/specify_cli/upgrade are out of the PR matrix, so three reds merged green and were first misread locally as environmental.
2026-10-19 · claude-code/opus · Agent containers export SPEC_KITTY_NO_NAG/NO_UPGRADE_CHECK/NON_INTERACTIVE; the root test fixture keeps pre-existing SPEC_KITTY_* values, so nag tests go red in agent sessions.
2026-10-19 · claude-code/opus · `agent mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`; the error names the flag, fine.
2026-10-19 · claude-code/opus · `move-task --to for_review` auto-commits a "Capture baseline tests" commit without a signature in this harness; every one had to be re-signed by hand.
2026-10-19 · claude-code/opus · Review verdicts are written but not committed ("--no-auto-commit") even when the flag was not passed.
2026-10-19 · claude-code/opus · The acceptance matrix is seeded once at finalize-tasks; an FR added later (FR-020) is not added to it and `acceptance-verdict --criterion FR-020` fails.
2026-10-19 · claude-code/opus · `accept` requires a contracts/ folder or a meta.json `contracts: none` waiver, and no CLI writes the waiver.
2026-10-19 · claude-code/opus · pytest-xdist hangs on the per-worker test-venv bootstrap inside lane worktrees; implementers ran -n0.
