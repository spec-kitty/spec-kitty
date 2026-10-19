# Tracer: tooling friction

One entry per friction point: `YYYY-MM-DD · actor · <text>`.

---

2026-10-19 · claude-code/opus · tests/specify_cli/cli/commands and tests/specify_cli/upgrade are out of the PR matrix, so three reds merged green and were first misread locally as environmental.
2026-10-19 · claude-code/opus · Agent containers export SPEC_KITTY_NO_NAG/NO_UPGRADE_CHECK/NON_INTERACTIVE; the root test fixture keeps pre-existing SPEC_KITTY_* values, so nag tests go red in agent sessions.
2026-10-19 · claude-code/opus · `agent mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`; the error names the flag, fine.
