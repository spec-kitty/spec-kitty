# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · Chose the observed set over a hard refusal. The ADR that introduced the fallback (docs/adr/1.x/2026-01-23-6-config-driven-agent-management.md) requires legacy projects to keep working on upgrade, and the 27-migration chain calls this helper before any new migration could record a list; a raise would abort the upgrade mid-chain for exactly the affected population. Narrowing to the surfaces the project already has removes the widening while keeping stale command files repairable.

2026-10-31 · claude · Surface probe is project_path/<agent_root>/<subdir>, not the bare agent root: a CI-only .github/ must not make Copilot 'in use' (its surface is .github/prompts). Probe stays project-local so migrations never depend on $HOME or user-global command dirs.
