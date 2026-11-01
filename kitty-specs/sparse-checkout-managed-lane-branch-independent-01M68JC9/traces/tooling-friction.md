# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · planner-priti · spec-kitty specify created a coord-topology mission while HEAD was main, so target_branch=main (protected): spec-commit refused and the composition Op fired 7 'refused on protected branch' records. Recreated the mission with 'agent mission create --topology single_branch' on the topic branch. The specify command has no --start-branch/--topology-only-topic path, which cost a mission recreate.

2026-10-31 · implementer-ivan · 'unregistered worktree under .worktrees/' is not constructible as an independent control: once git drops the registration, scan_path's own 'git config core.sparseCheckout' probe also fails, so the state is inactive rather than blocking. Dropped from the test matrix; the foreign-branch and drift controls carry the guard instead (both re-verified on the branch-switched fixture).
