# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · packets: `spec-commit` refused the planning artifacts twice because the mission was created on main (recorded target_branch main) and the checkout was then moved to a topic branch; the documented recovery is a creation-time --start-branch, so the recorded target_branch had to be corrected to the topic branch through write_meta before specifying could commit. Grounding cost ~15 minutes and two refusals.
