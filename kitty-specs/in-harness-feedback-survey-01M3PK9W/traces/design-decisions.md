# Design Decisions — in-harness-feedback-survey-01M3PK9W

Decisions already made (see `research.md` R-01…R-09 and `decisions/`):

- Consent on every submission; the consent step reads only "Send feedback?" (no URL).
- Weekly throttle across all automatic triggers; "shown" is recorded at offer time under a non-blocking machine lock.
- Endpoint precedence: env var > user override > `DistributionProfile.feedback_endpoint` > none (dormant).
- Trigger commands' JSON contracts stay unchanged; agent guidance is appended via the renderer seam.
- Detached child sender with the payload on stdin (never argv or disk); 5 s cap; always silent.
- Preferences live in one hardened `feedback.json` in the user config dir (not the cache dir), built on kernel primitives rather than copies of `NagCache` internals.
- Inline terminal form's first question auto-skips after 30 s, so a pseudo-terminal agent run cannot stall.
- 2026-09-30 — Analyze (finding I1): dropped the separate "Share quick feedback?" gate; the rating question itself is timed, keeping every flow at four interactions (NFR-008).
- 2026-09-30 — Analyze (finding I2, research R-10): the agent block reaches prompt-backed commands through their pack source prompts (runtime cannot import `specify_cli`) and CLI-driven commands through the Python helper.
- 2026-09-30 — Analyze (finding U1, research R-11): unattended agent sessions are undetectable by the CLI; documented as a limitation rather than honouring `SPEC_KITTY_NON_INTERACTIVE` in `agent_check`.
# Design Decisions — in-harness-feedback-survey-01M3PK9W

Decisions already made (see `research.md` R-01…R-09 and `decisions/`):

- Consent on every submission; the consent step reads only "Send feedback?" (no URL).
- Weekly throttle across all automatic triggers; "shown" is recorded at offer time under a non-blocking machine lock.
- Endpoint precedence: env var > user override > `DistributionProfile.feedback_endpoint` > none (dormant).
- Trigger commands' JSON contracts stay unchanged; agent guidance is appended via the renderer seam.
- Detached child sender with the payload on stdin (never argv or disk); 5 s cap; always silent.
- Preferences live in one hardened `feedback.json` in the user config dir (not the cache dir), built on kernel primitives rather than copies of `NagCache` internals.
- Inline terminal form's first question auto-skips after 30 s, so a pseudo-terminal agent run cannot stall.
- 2026-09-30 — Analyze (finding I1): dropped the separate "Share quick feedback?" gate; the rating question itself is timed, keeping every flow at four interactions (NFR-008).
- 2026-09-30 — Analyze (finding I2, research R-10): the agent block reaches prompt-backed commands through their pack source prompts (runtime cannot import `specify_cli`) and CLI-driven commands through the Python helper.
- 2026-09-30 — Analyze (finding U1, research R-11): unattended agent sessions are undetectable by the CLI; documented as a limitation rather than honouring `SPEC_KITTY_NON_INTERACTIVE` in `agent_check`.
- 2026-10-01 — WP08: docs state the macOS/Linux/Windows `feedback.json` locations from the shared config-dir resolver (macOS honours `HOME`, not `XDG_CONFIG_HOME`), so the isolated quickstart profile is a temp `HOME`.
- 2026-10-01 — WP08: shipped-vs-plan notes recorded in docs: `--status` lists fields alphabetically; `mission_type` is sent as `null` outside a mission; the agent flags are hidden from `--help` by design, so the how-to documents only `--status`, `--prompts` and the bare command.
