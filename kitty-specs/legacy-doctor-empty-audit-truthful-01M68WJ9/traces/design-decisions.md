# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude-s1 · Chose the issue's first option (truthful summary naming the absent agent list) over widening the audit to the every-agent fallback (#6501): widening a legacy project that uses one tool into 20 tools' worth of missing-surface findings is a false red, and per-harness ownership is #6472's decision.

2026-10-31 · claude-s1 · Overlap recorded: PR #6894 (#6493, still OPEN) touches the same three report functions in _command_surface_doctor.py for the stated-empty shape and adds no_cli_managed_agents(config) in core/agent_config.py. This Mission changes the legacy shape only, reuses a single config load, and keeps --json key sets identical, so the second of the two PRs to merge resolves a small textual conflict rather than a semantic one.

2026-10-31 · claude-s1 · Exit codes stay 0 for a nothing-examined report: doctor's documented contract is 0 ok / 1 issues / 2 not-in-project or bad config, and 'nothing to check' is not an issue. Honesty is carried by the summary line plus the zero counts the JSON already exposes; turning it into exit 1 would fail legacy projects' CI for a state they cannot fix without stating an agent list.
