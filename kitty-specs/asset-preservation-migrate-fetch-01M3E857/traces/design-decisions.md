# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->
2026-09-26 — Decision: fold #4989 into the #4960/#4961 mission. Alternatives: two-issue mission + separate #4989 follow-up. Rationale: #4989 is the `_update` sibling of #4960 in the SAME `git_source.py`, shares the fix surface and the line-pinned arch-gate entry; a follow-up would re-touch the same file/gate days later. Operator-confirmed.
2026-09-26 — Decision: base the mission on live skupstream/main (e8054f4994), not the stale local branch. Rationale: #5036 lesson — verify premise against live upstream; all three seeds re-checked LIVE, none superseded.
2026-09-26 — Decision: two adapters over one guard call. migrate uses guard_destructive_removal + content provers; git_source uses backup + clone-to-temp-swap (no shipped manifest for a fetched pack → prover ownership proof does not apply). Rationale: reuse existing primitives, one preservation invariant, no new framework (C-003, NFR-003).
