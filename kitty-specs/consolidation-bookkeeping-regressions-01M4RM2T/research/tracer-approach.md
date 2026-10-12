# Tracer: Approach (#6071, #6073)

- Reproduced all seven target tests RED on origin/main @ 8a911083 under events 10.4.4 through
  their pre-existing entry points; recorded in `red-first-reproductions.md`. No new synthetic
  reproductions written (the existing tests are the red-first pins).
- Grounded the consolidation surface with evidence-first probes (scratchpad `probe_*.py`)
  rather than assuming the brief's single-root-cause hypothesis. Result: FOUR distinct root
  causes (A done-check reducer, B composed-dir teardown, C stale skip-lanes fixtures, D
  interrupted-fold dirty detection); B and D share the #5965/#5966 composed-dir theme.
- Fixing root causes, not symptoms: for A route through the canonical reducer (single
  authority) rather than patch the wall-clock sort; for D make the interrupted-fold state
  refuse so the existing #5748 advice renders, rather than paper over the stale lock.
- Each slice kept to smallest-viable-diff and locality of change; sliced commits map 1:1 to
  the named tests.
