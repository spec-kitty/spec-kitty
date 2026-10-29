# Tracer: approach

- 2026-10-27 (plan): grounded both defects red on `581b5c46` before specifying; inventoried every owned refusal site with an independent read-only pass. Shape decided by the operator (C2 strict + `context`), then sliced: migration fix independent; renderer + callers in one WP so no intermediate state breaks imports.
- 2026-10-29 (closeout): consolidation's stale-assertion analyzer and a post-rebase pre-merge squad each found a cross-WP gap (an unrun architectural test; the orchestrator-api delegate classifier) that per-WP reviews could not see. Both were folded red-first.
