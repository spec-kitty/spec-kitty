# Approach — honest-feedback-file-drop-01M66FMD

- **[2026-10-30][plan] Per-edge remedy decided from the issue text and the surrounding contract.** Non-review edges get refusal (exit 1) inside the existing `_guard_feedback_file` (leading arm, no new `_GUARDS` slot); the arbiter-override edge keeps the #6652 stderr warning, pinned end-to-end; recording the file in the arbiter artifact is deferred (frozen `ReviewOverride` shape). Grounding: research.md D-1..D-3.
- **[2026-10-30][implement] Red-first through the real CLI.** The e2e tests (rework-loop harness) are written first and shown failing on the pre-fix tree; only then does the guard arm land.
