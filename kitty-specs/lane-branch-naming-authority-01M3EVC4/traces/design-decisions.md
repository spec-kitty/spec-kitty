# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-09-26 — Option A (operator): extend the creation-side authority; no `lanes.json` per-lane branch field (Option B rejected: schema change + migration), no push-down into mission_runtime (Option C: layer violation).
- 2026-09-26 — FR-010 (terminus-merge-integrity WP04) absorbed but found already landed (read-back ids in `lanes/compute.py`, origin-preferring fresh parent in `worktree_allocator.py`, `tests/lanes/test_lane_identity.py`): preserve + verify only.
- 2026-09-26 — Resume with an empty persisted lane-tip record refuses fail-closed naming `merge --abort` (operator), mirroring the coord-base anchor handling.
- 2026-09-26 — Gate reach is compose + match (operator): hand-rolled lane-name matchers route through the naming module's parsers.
- 2026-09-26 — #5113 folded (operator); #5023's full dual-partition resolution stays out of scope.
- 2026-09-26 — FR-003 strict arm limited to created-branch existence; the GitProbeError tolerance on approved lanes stays (#5001 FOLD-3, pinned by test_build_claim_tolerates_unresolvable_lane_probe) — the squad caught a prompt that would have silently flipped it.
