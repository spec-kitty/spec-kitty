# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over that one?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-10-31 — Decision: treat `agents.available: []` (stated, #6494) as the plugin/outside-CLI ownership shape; a config with no list stays the legacy all-agents fallback (#6501). Alternatives: detect the harness plugin on disk (`.claude/plugins`, `enabledPlugins`). Rationale: #6472 owns how ownership is recorded; inventing a probe here would create a second authority for it.
- 2026-10-31 — Decision: `init --ai claude` on a stated-empty project exits 0 and explains that the stated list wins, instead of exiting 1 with `agent config add`. Alternatives: follow the flag and hand the surface to the CLI (writes a duplicate). Rationale: the issue's Expected is that such a project is *recognised as set up*; the config is the single canonical authority for which agents the CLI manages.
- 2026-10-31 — Review round 1 (independent review by a different model) requested changes: the agent guide still taught "No agents configured." and `doctor command-files` had no positive control. Both folded (`docs/guides/how-to/collaboration/manage-agents.md`, a healthy-fixture control), plus three nits (defensive-only docstring, narrowed "one reader" claim, deliberate `explicit_agent_list` in a mock). Rationale for not widening: the legacy shape's own doctor lines are a pre-existing residual, filed as a follow-up rather than folded into a P2 reporting fix.
