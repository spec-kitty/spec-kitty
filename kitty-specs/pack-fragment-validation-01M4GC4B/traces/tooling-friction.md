# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-09 · orchestrator · mission create scaffold commit message reads 'Add scaffold for feature <slug>' - the CLI's own commit text uses the retired 'feature' term (terminology canon). Not in scope here; noted for the CLI owners.

2026-10-09 · pi/gpt-6.1-sol · Canonical setup-plan reported phase_complete=true and auto-committed plan.md even with agents.auto_commit=false. Respected its real commit_created result; did not duplicate the commit or bulk rewrite historical CLI attribution. Skill REASONS source paths are stale; resolved current template under src/charter/offering/templates/fragments rather than inventing a template.

2026-10-09 · pi/gpt-6.1-sol · finalize-tasks validate-only preview proposed lane-a, while actual single_branch finalization correctly persisted lane-planning; consumed actual lanes.json, not preview allocation. Mutating finalizer auto-committed despite disabled auto_commit and used generic feature wording without Agent/Issue trailers. Restored agent: pi directly after finalizer normalization as canonical tasks prompt directs; no gate edit or historical bulk rewrite.

2026-10-09 · pi/gpt-6.1-sol · Strict mypy exposed baseline Any-return in touched plural helper, reproduced on planning source and reported as #5971 before continuation; fixed without suppression. Coverage driver timeouts were incomplete runs, not green evidence; final bounded coverage and required test-fast completed. No gate or timing-budget configuration was changed.
