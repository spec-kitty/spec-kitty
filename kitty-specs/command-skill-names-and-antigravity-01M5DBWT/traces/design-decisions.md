# Design decisions

- **[2026-10-20][specify] Name `spec-kitty-<cmd>`, clean break.** Operator ruling; the dotted names become retired, no alias folder (C-005).
- **[2026-10-20][plan] Render-time invocation rewrite.** Pack sources keep `/spec-kitty.<cmd>` (correct for the 13 slash agents, C-001); the command-skill renderer rewrites known invocation tokens to the skill name (operator planning answer A).
- **[2026-10-20][plan] `builtin:` alias.** `builtin:spec-kitty.<cmd>` stays accepted as input, rendered as `spec-kitty-<cmd>` (operator planning answer B).
- **[2026-10-20][plan] Ownership never by prefix.** `spec-kitty-` is shared with nine shipped charter skills, so orphan/stale detection uses the explicit command set and the manifest.
- **[2026-10-20][plan] Home writer scoped to configured agents.** Startup passes the project's configured slash agents; outside a project nothing is written (operator ruling 3). Amends ADR 2026-04-07-1's "all agents at every startup".
