# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-25 — `.venv/bin/python -m pip install -e .` fails against the local artifactory mirror (`No matching distribution for packaging>=24.2`); the editable install was already current so `src/` changes are picked up live regardless (known local artifactory-pollution gotcha).
- 2026-09-25 — This is a dogfooding mission on the very `implement`/coord seam it fixes; the mission itself runs on `coord` topology, so the #4905 defect it targets is live in its own workflow — implement/review of later WPs may hit the very add/add conflict being fixed. Noting so the implement loop uses the low-level `spec-kitty implement` (lane cut only) where the agent-verb claim would trip #4905 before WP02's fix lands.
- 2026-09-25 — `spec-kitty merge` landed the full aggregate correctly (all 3 lanes squashed into the feature branch, all source+test changes present, WPs done, 33 regression tests green) but the SQUASH terminus reconciliation gate REFUSED with "projected coordination bookkeeping content did not land on the target" (the coord-owned `status.json` legitimately does not commit to the target), and `merge --resume` then dead-ended on `TARGET_BRANCH_CONTENT_CONFLICT` (status.json) because the squash had already landed. Net: the deliverable merged cleanly but the gate false-FAILs on coord-bookkeeping projection — the #5018/#5022 terminus-reconciliation-false-FAIL class, hit live on this mission. Verified the merge outcome directly rather than trusting the refusal. Candidate new dogfooding issue. (Also: mission-command reruns rewrite the primary-checkout mission dir from the coord surface, silently reverting un-committed working-tree edits to traces/ — commit tracer appends immediately.)
