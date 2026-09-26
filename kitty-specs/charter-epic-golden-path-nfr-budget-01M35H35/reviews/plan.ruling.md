# Operator ruling — plan phase HALT (round 2)

Recorded 2026-09-23 by the orchestrator from the operator's answer. This ruling REPLACES the
original acceptance bar for the finding named below.

## Ruling 6 — lever C scope (PLAN-GOV-001)

Question put: profiling found that most CLI startup cost is `ensure_global_agent_commands()` /
`assess_global_agent_commands()` (`src/specify_cli/runtime/agent_commands.py`), which re-renders
every configured agent's command templates on every non-fast-pathed call. That is not the
#4417-deferred Typer command-surface construction the operator originally named for lever C.
Which should lever C cover?

Operator answer: **Both, freshness check first.** Lever C's primary mechanism is a freshness
pre-check that skips the global agent-command render when nothing has changed. The
#4417-deferred Typer command-surface trim (`register_commands()`) stays as a secondary,
complementary change. Both are in this mission and this PR.

Binding condition attached to the answer: the freshness check must be proven **red-first** not
to cause silent staleness. There must be tests that fail if the check skips a render it should
not skip: at minimum when a command template changes, when the spec-kitty version changes,
and when the rendered output on disk is missing or was altered. A missed refresh must never
pass silently.

Acceptance bar for PLAN-GOV-001: resolved when (1) spec.md's FR-003 and Clarifications record
this ruling as the authority for the expanded lever C (the original lever quote stays intact
and attributed), (2) plan.md presents the freshness check as primary and the Typer trim as
secondary, citing this ruling instead of the author's own reasoning, and (3) plan.md's test
strategy names the red-first staleness tests above explicitly.

## Closing pass authorized

One fresh fixer, then one fresh verifier on PLAN-GOV-001 and on spec/plan consistency for the
edited sections, then one fresh sweep scoped to the sections this pass edits (spec FR-003 +
Clarifications, the plan's lever C section and test strategy). Any severity ≥3 finding left
after that → HALT. No further self-extension.
