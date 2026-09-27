# Approach Evolution

> Track how your approach changed as the mission progressed.

**Prompting questions**
- What approach did you start with (as stated in the spec or plan)?
- What changed during implementation, and why?
- What would you try differently on a similar mission?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what approach was tried and what shifted. -->

## Seed (2026-09-27)
Adopt the existing placement-seam partition-resolution authority at the two straggler consumers (mission-review Gate 4, merge issue-matrix gate) using the existing healthy two-partition split (discovery from primary, verdicts from coordination) as the reference shape. Extend it with a coordination-branch-ref read for the post-consolidation unmaterialized-worktree case. Add merge-side terminal-verdict enforcement mirroring the move-task `done` blocker. ATDD red-first with coord-vs-flat same-fixture controls.
