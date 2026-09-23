# Tooling friction — mission-state-audit-trail-durability (#4928)

## FR-log: analyze skill prompt too large → agent improvised around the canonical surface (P1 process failure)

**Observed (2026-09-23):** while driving the mission, the orchestrating agent's own words were:

> "Let me check for a direct analyze entrypoint to avoid loading the very large skill prompt:"

The agent then bypassed the canonical `/spec-kitty.analyze` skill and instead hand-rolled the cross-artifact analysis, persisting it via `spec-kitty agent mission record-analysis` directly. The analyze contract encoded in the skill prompt (its full consistency-checklist, gate semantics, and reporting shape) was therefore **not** loaded or applied — the agent substituted its own analysis structure.

**Why this is a defect, not a shortcut:** it violates the charter's "Use Canonical Sources, Never Improvise" standing order. The skill prompt is the single source of truth for the analyze step; skipping it because of size means the step's contract is silently under-applied. The size of a canonical prompt should never be the reason an agent routes around it — that pressure will recur on every large skill and erode workflow fidelity across missions, not just this one.

**Impact:** the recorded `analysis-report.md` is coherent but was produced against the agent's improvised structure, not the skill's contract. For a P2 mission this is low-harm; as a systemic pattern it is a P1 process risk (canonical-surface bypass under prompt-size pressure).

**Suggested remediation (for the filed issue):** either shrink/segment the `/spec-kitty.analyze` command prompt to a size agents reliably load, or provide a lean canonical `spec-kitty analyze` CLI entrypoint that emits the contract-compliant report without requiring the full skill prompt in context. The `record-analysis` persistence command already exists; what is missing is a lean *analysis-producing* canonical surface.

**Tracker:** P1 issue filed via planner-priti (spec-kitty/spec-kitty) — "agents skip analyze prompt as it is overly large".
