# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · Scoping is structural (which Mission directory a path sits under), never a filename list: test_exemption_registry_ratchet treats module-level filename sets in churn modules as exemptions, and the #5669 ruling keeps mission-events.jsonl real dirt. So #5938 is fixed by next committing its row, not by exempting it.

2026-11-11 · claude-orchestrator · Assessment: one structural Mission-scoped dirt rule (coordination/mission_dirt.py) served both gates without filename lists. Commits reuse existing committers: upgrade.autocommit's baseline diff for init (no new capability holder), the status door's coordination shape for next's row (now shared by answer-decision). Open for the operator: the init reversal of mission 079 FR-002/FR-007; the content-blind lane-guard tolerance of the inherited event log; what auto_commit: false should mean for status writes (#3933 residual).
