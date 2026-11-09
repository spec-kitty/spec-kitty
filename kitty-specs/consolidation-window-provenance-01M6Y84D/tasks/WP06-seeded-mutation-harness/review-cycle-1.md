---
affected_files: []
cycle_number: 1
mission_slug: consolidation-window-provenance-01M6Y84D
reproduction_command:
reviewed_at: '2026-11-09T03:14:10Z'
reviewer_agent: claude:claude-opus-5-5:reviewer-renata
wp_id: WP06
---

# WP06 review, cycle 1: changes requested

Reviewer: claude:claude-opus-5-5:reviewer-renata. Reviewed commit `ea80e3e406` (lane-a), one file:
`tests/consolidation/test_reconciliation_seeded_mutations.py`.

## Verdict: changes requested

The harness is well built. The family-helper patching is correct, the control is real and the
docstring/table agreement test is good. Twelve of the 16 rows are real weakening guards.
**Four rows only show that a corpus cell reaches the check, and one more guards only in the
strengthening direction.** Together they leave the highest-risk Phase 3 slice
(`reconciliation_canceled.py`) and the Phase 4 anchor change (IC-15) with no witness.

### Why rows that only show reach do not meet the DoD

- **SC-005** says each moved check must be "guarded by at least one scenario that fails when
  the check is **broken**". **IC-17 / R-07** name the canonical mutation as "a verdict
  **forced to pass** (always passes), or a flipped predicate". The purpose is that the split
  (WP10–WP15) and Phase 4 cannot **silently weaken** a check.
- A mutation that makes a refusal check refuse every time is the mutant any corpus kills. It
  proves the check is reached, not that the corpus would notice the check losing its teeth.
- **Empirical check (reviewer probe, transient file, deleted afterwards).** I applied the
  *weakening* form of each of the four checks:
  - `_collect_excluded` returns `(frozenset(), frozenset())`;
  - `_resolve_mixed_lane` returns `(set(), [])`;
  - `_resolve_canceled_dependency_lanes` returns empty `unapproved_commits` / `content` and
    `refusal=None`;
  - `MergeOutcomeVerifier._canceled_content_divergence` returns `([], None)`.

  Then I recomputed **all 68 canceled-family corpus cells** (every key containing `canceled`,
  `mixed_lane` or `dependency_chain`). Result: **0 cells red for every one of the four.** Any
  of these checks could be deleted in the split and both the corpus and this harness would
  stay green.
- The golden file has 145 cells: 92 `pass`, 30 `refuse`, 3 `fail`. None of the three `fail`
  cells is a canceled-content FAIL, and no cell runs `--strategy merge`.

**Anti-pattern checklist:**

| # | Item | Result |
|---|---|---|
| 1 | Dead code | N/A (test only) |
| 2 | Synthetic fixture | PASS (the real in-process path) |
| 3 | Silent empty return | N/A (the fakes are deliberate) |
| 4 | Requirement coverage | **FAIL**: NFR-008 / SC-005 for 4 checks, partial for `kernel-anchors` and `external-dependency-refs` |
| 5 | Frozen surface | PASS |
| 6 | Locked decision | PASS |
| 7 | Shared-file ownership | PASS for this commit (see the rework note below) |
| 8 | Production fragility | N/A |

**Process note:** the WP prompt says that when a mutation-target cell is missing, "stop and ask
the orchestrator; do not weaken the row". The gap is documented in the docstring (line 62) but
was not escalated. The orchestrator has now sanctioned the remedy below.

---

## Who does the rework and how

**WP06 rework, with a sanctioned out-of-map addition to WP02's corpus.** WP02 is not reopened.
The added files are:

- `tests/consolidation/characterization_support.py`: new builder helpers and `Cell` entries in
  `named_cells()`, plus new `NAMED_KEYS` entries under the existing `# ---- mutation-target cells
  (WP06)` block.
- `tests/consolidation/characterization/verdict_corpus.json`: the new golden cells, recorded
  from **today's actual verdict**, not from the intended one.

**Hard constraint: the change is additive only.**

- No existing builder, cell, key or golden value changes.
- `git diff kitty/mission-consolidation-window-provenance-01M6Y84D -- tests/consolidation/characterization/verdict_corpus.json`
  must show only added keys.
- The characterization test's `changed_cells` against base must list exactly the new cells.
- Existing builders may only gain **new optional parameters with defaults that keep today's
  behaviour**, or be called with parameters they already accept. Prefer reusing those: for
  example, `build_canceled_dependency_mission(..., wp02_overwrites_wp01=False)` and
  `build_coord_mission_mixed_lane_canceled(..., survivor_after=())`.
- Record the out-of-map files in the WP history (`add-history`) and in the move-task note, so
  the shared-file ownership item stays PASS.
- Add a tracer entry (`--category design-decisions`) for the sanctioned out-of-map addition.

---

## Required changes

Key names below are suggestions; keep the `mut_` `NAMED_KEYS` convention. For each row, pin
the cell **only after running the weakening mutation and seeing it flip**. A cell whose status
or code does not change under the weakening does not count, and neither does a cell whose
only change is in its pinned text.

### Issue 1 [HIGH]: `verifier-canceled-axis` and `mixed-lane` need a cell where canceled content leaks

- **New cell:** `fresh|mixed_lane_canceled_wp|canceled_content_leaks` (`mut_canceled_content_leaks`).
  - Build: the mixed-lane builder with the canceled WP's change **surviving** on the lane, so
    there is no `survivor_after` deletion of the canceled path. Use the default squash strategy.
  - Expected golden (verify): `fail`, divergence field `canceled_content`.
- **`verifier-canceled-axis` mutation** (replaces "always refuses", line 237):
  `_canceled_content_divergence` returns `([], None)`. Expected: the new cell FAIL → PASS (or
  at least loses the `canceled_content` divergence).
- **`mixed-lane` mutation** (replaces "always refuses", line 194): `_resolve_mixed_lane`
  returns `(set(), [])`, so the lane resolves clean and carries no canceled content. Expected:
  the same new cell flips.
- If one cell cannot serve both rows, because one check masks the other, add a second leak
  variant and pin each row to the cell its own weakening flips.

### Issue 2 [HIGH]: `canceled-dependency` needs a cell where a fully-canceled dependency's content is live on the target

- **New cell:** `fresh|fully_canceled_dependency|canceled_content_reachable`
  (`mut_canceled_dependency_reachable`).
  - Build: `build_canceled_dependency_mission(tmp, wp01_final="canceled", depends=True, wp02_overwrites_wp01=False, mid8=<new unique mid8>)`.
  - Expected golden (verify): `fail` with `canceled_reachable_via_dependency` /
    `CANCELED_REACHABLE_VIA_DEPENDENCY`, or a claim-time REFUSE. Pin whichever today
    produces.
- **Mutation** (replaces "always refuses", line 201): wrap the real
  `_resolve_canceled_dependency_lanes` and return
  `dataclasses.replace(r, unapproved_commits=frozenset(), content=frozenset(), refusal=None)`.

### Issue 3 [HIGH]: `closed-world` (`_collect_excluded`) needs a `--strategy merge` cell

- Under the default squash strategy no verdict reads the excluded sets, which is why the row
  raises today. Add **`fresh|mixed_lane_canceled_wp|stamp=present|window=recorded|strategy=merge`**
  (`mut_mixed_lane_strategy_merge`).
  - Use the existing mixed-lane shape with `--strategy merge`, passed through
    `_run_cell(mission, "fresh", "--strategy", "merge")`.
  - In that shape the approved survivor deletes the canceled path, so the content axis sees no
    surviving canceled content. The SHA-granular excluded check is then the deciding evidence.
  - Expected golden (verify): `fail` / `refuse` on the excluded canceled commit reachable from
    the target.
- **Mutation** (replaces the raise at line 160): `_collect_excluded` returns
  `(frozenset(), frozenset())`. Expected: the merge cell flips.
- If the canceled axis masks the excluded check in this shape, pick a variant in which only
  `_collect_excluded` decides (for example a canceled commit whose content an approved commit
  later reverts). Check it by running the weakening.
- Delete `_SeededMutationReached` once no row needs it.

### Issue 4 [MEDIUM]: `kernel-anchors` guards only the strengthening direction

- Today's mutation, "no anchors" (line 153), *adds* refusals, and the two cells change only in
  pinned text.
- That text pin catches a pure move. It does not catch the dangerous direction, an anchor set
  that is **too wide**. Phase 4 **IC-15** changes exactly this function (A-03: anchors read
  live dependency-lane names on resume), so this row must be a weakening guard.
- **Mutation:** wrap the real `_closed_world_anchors` and return `real + [the lane's own branch]`
  (`_lane_branch_for(lanes_manifest, lane.lane_id)`). That anchor exempts every post-approval
  commit on the lane.
  - Expected: a `LANE_MOVED_AFTER_APPROVAL` cell flips refuse → pass, for example
    `resume|mixed_lane_canceled_wp|...|dependency_lane_advanced` or the R-09 forecast cell.
  - Alternative: drop the fully-canceled / planning-lane filters, which makes those
    dependencies anchors. That flips the Issue 2 cell.
- The flip must be a **status or code change**, not text only. You may keep the current
  "no anchors" mutation as an extra row (`kernel-anchors-strict`); the uniqueness test allows
  extra ids.

### Issue 5 [MEDIUM]: `external-dependency-refs` guards only the strengthening direction

- "A declared ref is honoured but exempts no commit" (line 167) is a strengthening: it causes
  false refusals. The safety-relevant weakening is the one the WP prompt named, "accept every
  declared ref", which means a ref naming Mission work stops being refused.
- On the existing `dependency_ref` cell, where the ref is legitimate, that weakening changes
  nothing. So it needs its own cell.
- **New cell:** `fresh|single_lane|dependency_ref_names_mission_work`
  (`mut_dependency_ref_mission_work`).
  - Build: single_lane with `--dependency-ref <a Mission lane branch, e.g. kitty/mission-…-lane-a>`.
  - Expected golden (verify): `refuse`, with the namespace refusal code (the
    `_REFUSE_DEPENDENCY_MISSION_NAMESPACE` text) or `DEPENDENCY_REF_COVERS_MISSION_WORK`.
- **Mutation:** wrap the real `resolve_external_dependency_refs` and drop the refusal
  (`dataclasses.replace(result, refusal=None)`). Expected: REFUSE → a different verdict.
- You may keep "exempt nothing" as an extra row (`external-dependency-refs-exemption`)
  pinned to the existing `dependency_ref` cell.

### Issue 6 [LOW]: docstring and table cleanup

- Remove the "Rows that are reach or polarity mutations…" paragraph (line 62 onwards).
- Update the docstring table, the expected-cell block and `MUTATIONS` together.
  `test_docstring_table_matches_mutations` enforces this.
- Update the mutation descriptions that say "polarity flip".

## Judged acceptable as they stand (no change required)

- **`claim-orchestration`, refuse → a different refusal.** Removing the claim's own refusal
  is a real weakening. The cell changes because a later phase now decides, so the corpus
  witnesses the claim refusal. It overlaps `approved-bound` (same cells), which is acceptable;
  the corpus has no compound-refusal cell for an orchestration-only mutation. Not blocking.
- **Patching discipline.** Every function row goes through `setattr_reconciliation_family`,
  and `_real` reads from `family_modules_binding`, never from the facade. Methods patch the
  `MergeOutcomeVerifier` class attribute. There are no string targets, and
  `test_no_row_patches_a_facade_string_target` enforces this. PASS.
- **Control.** `test_unmutated_cells_match_golden` recomputes the union of the cells and
  equals the golden file. PASS.

## Acceptance for the next cycle

- Every row in `PHASE3_CHECKS` uses a **weakening** mutation (forced to pass, a lost refusal,
  dropped evidence, or an over-wide exemption). Each one turns at least one cell red in **status,
  code or divergence fields**. Text-only flips are allowed only as extra rows.
- The new cells are additive (the corpus diff adds keys only), and the
  characterization test passes with `changed_cells` equal to the new keys.
- The control includes the new cells and stays green.
- Notify the WP07 / WP09 agents (they depend on WP06).
