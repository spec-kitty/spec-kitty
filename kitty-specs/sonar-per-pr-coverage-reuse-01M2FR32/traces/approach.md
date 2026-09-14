# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->
- 2026-09-14 — Starting approach (from spec): move the per-PR Sonar scan onto the existing `workflow_run:[CI Modules]` chain as a new job in `ci-aggregate.yml`, consuming the already-published reconciled-coverage + source artefacts, and delete the duplicate `make test-fast` step. Two scope additions beyond the source issue: declare the orphaned test dirs in the module registry, and relocate (never delete) every gate pinning the current shape.
- 2026-09-14 — Deliberately NOT taking the issue's framing at face value. Research falsified its "the fast tier is one of the matrixed tiers" premise (every registry row is `tier: standard`), which is what surfaced the orphaned-directory gap. Lesson so far: verify the premise of a well-written issue, not just its conclusion.
- 2026-09-14 — Post-spec adversarial squad (4 lenses, brownfield point-cut) refuted **five** factual claims in my own research: the cost figure was the population minimum not the median (22m32s, n=12); the "waste went live today" story was wrong (the evidence runs were fork PRs; live since ≥09-10); "every scan fails exit 3" was wrong (≥3 causes, one clean pass); "the only CI execution of those dirs" was wrong (the nightly sweeps them by marker); and SC-001's "today: two" was never derived. Root causes: single-sample sourcing, and grepping for directory paths while missing marker-based selection with `testpaths`.
- 2026-09-14 — Approach shift: scope GREW on operator ruling. Now includes fixing coverage-measurement breadth and the full four-file inventory cascade. The mission is no longer "move a job"; it is "make one measurement trustworthy enough to be the single source, then move the job onto it".
- 2026-09-14 — Lesson for the next point-cut: the squad's value was overwhelmingly in the lenses tasked to *falsify* rather than review. Briefs that said "assume the research author was overconfident" and "assume this inventory is incomplete and prove it" produced every one of the load-bearing findings. A review-shaped brief would have produced agreement.
