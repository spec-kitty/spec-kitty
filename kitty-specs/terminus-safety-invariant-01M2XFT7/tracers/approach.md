# Tracer — Approach (terminus-safety-invariant)

Seeded at planning 2026-09-19.

- Method followed = DIRECTIVE_052 (this mission's own new directive): root-cause squad → related-ticket squad → architecture-alignment squad → structural remediation, operator-gated scope.
- Execution: WPs implemented by subagents DIRECTLY on the single mission branch `issue-4764-terminus-safety-invariant` (NOT lane worktrees — fragile allocator in a cluttered checkout, per operator directive). Governed reviews run as pre-PR adversarial passes over the integrated diff.
- Sequencing: IC-1 tidy-first enabler (shared aggregate + reroute) FIRST, then IC-2 (merge precond) → IC-5 (rollback)/IC-6 (direct-on-target); IC-3/IC-4/IC-7 parallel after IC-1.
- ATDD: each defect gets an issue-pinned @pytest.mark.regression RED test through the pre-existing CLI entry point before the fix.

## Append log (implementation)
- (WPs append here)
