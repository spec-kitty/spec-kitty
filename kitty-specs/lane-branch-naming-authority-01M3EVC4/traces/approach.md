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
- 2026-09-26 — Post-plan squad (renata/alphonso/priti) FOLD: WP02/WP06 split (9 WPs), extend the existing naming gate + def-use leg (no sibling gate), single lane-id grammar, FR-011 narrowed to preserve-only (+ typed refusal in Mission-branch fallbacks), ADR + living-docs WP, #4762 kept out (different defect class). Upstream drift check: 9 new main commits, none touch lanes/merge/decisions/coordination.
- 2026-09-26 — Post-tasks squad (renata/debbie): all 5 red-first claims confirmed red on HEAD; fold = split WP07 (→ WP07 atomic cutover + WP11 gate), numeric allow-list caps, bounded out-of-map list, per-emitter remedy round-trip, mandatory merge-base red run for SC-001.
