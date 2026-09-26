# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

- 2026-09-26 — Pre-spec squad (architect, debugger, patterns, planner) converged: creation-side placement is the de facto authority; claim/tip-capture/preflight diverge to the mid8 form. Approach: extend the creation authority, thread it through every merge stage, close the class with a compose+match arch gate. Red-first entry: `TestPlanningArtifactReachesTarget` (case e) + a unit claim test with a legacy slug and real ULID.
- 2026-09-26 — Post-spec squad (renata/paula/debbie) FOLD: 6+5+3 majors folded into spec rev 2 — mission-branch re-finalize drift pulled into scope (coord branch audited clean), #5113 as independent slice with #5023 non-goal, FR-013 mandates materialize-before-write, probe vs discover defined, <8-char identity crash added, fixtures must create lanes via the creation authority.
