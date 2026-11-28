---
affected_files: []
cycle_number: 10
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T20:33:33Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 10 (reviewer-renata, runner claude::reviewer-renata)

**Verdict: changes requested.** There is one fail-open leak (should fix), one gap where an operator gets a refusal with no remedy (low), and one nit.

## What holds

- **Fold claim 1.** `_build_claim` passes `pre_mission.base.sha` into both `_collect_authored` (`reconciliation_claim.py:384`) and `planning_lane_notes` (`:417`).
  - `_collect_authored` is the only caller of `_planning_walk`, so the fresh run, `--resume` and `--dry-run` all read the same Mission base. All three build their claim through `build_approved_wp_set`.
  - `mission_base` defaults to `None`, so any caller that omits it gets a lane that authors nothing.
  - `_taint_spine` fails closed in all three of its cases: no base, a base that is not below the pin, and `GitProbeError`.
  - Credit windows and `_scoped_commits` still read `pin..coord`.
  - When `_pre_mission_attribution` marks the base unavailable (range holds Mission work, or a probe failed), the lane authors nothing. That fails closed.
- **Interaction with the #7560 exemption, recorded base.** Content below a recorded Mission base that the target lacks is exempt only by exact `(path, blob)` at the base tree.
  - A credited edit of such a file lands its pre-Mission lines. #7560 already accepts those lines as inherited history: they would land exempt if left untouched. So this is not a new leak.
  - The taint walk never removes an exemption, and the exemption never credits content that the taint walk refused.
- **Fold claims 2 and 3.** The below-threshold rename is named in all three places, and the stray `.;` is gone.
- **Fold claim 4, residual (c).** The text in `adr-wording-c9.md`, the module docstring and the migration doc is accurate and complete. It names both shapes:
  - a copy whose source the same commit left unchanged, which also covers the copy-then-delete-source shape;
  - a rename below git's similarity threshold.

  It also names what the review diff shows in each case and why `--find-copies-harder` is not adopted.
- **Static checks.** ruff, `ruff format --check --force-exclude`, C901 and mypy are clean on every changed file. The diff adds no `noqa`, no `type: ignore` and no `NOSONAR`.

## Issue 1 (should fix, R2 / fail-open): a *derived* Mission base can sit above Mission-branch content, and the taint walk then never sees that content

`resolve_mission_base` falls back to a **derived** base when `meta.json` carries no valid `mission_base_sha`. The derived base is the first parent of the earliest commit that adds `kitty-specs/<slug>/`.

A commit made on the Mission branch *before* that scaffold commit therefore sits at or below the derived base. When the target lacks that commit:
- it is in the squash diff, which runs from the target tip;
- it is **not** exempt, because `_pre_mission_attribution` exempts only a **recorded** base;
- it is **not** on the taint spine, which runs `<derived base>..coord`.

So a credited edit of that file credits its final blob, and the unreviewed content lands. `_pre_mission_attribution`'s own comment (`reconciliation_closed_world.py`, "A derived base ... a non-Mission-path commit made on the Mission branch before the scaffold sits in `window_base..base` ... exempting it would pass Mission-authored content as pre-Mission (fail-open)") describes exactly this, and refuses to trust a derived base for that reason. The taint walk trusts it.

Probe (never committed): `/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/r10probe/test_r10_probe.py::test_pre_scaffold_commit_below_derived_base`. The steps:
1. On `main`: `init`.
2. On the Mission branch: a commit that writes 20 unreviewed lines to `curation/pkg/same.py`.
3. The scaffold commit (`kitty-specs/<slug>/spec.md`), then the planning pin, then WP02's claim.
4. A credited `feat(WP02)` commit appends `L = 1` to `same.py` and adds `other.py`.
5. Results:
   - base: `MissionBase(sha=<step 2 commit>, provenance=DERIVED, kind=NOT_RECORDED)`;
   - credited: `{same.py, other.py}`;
   - **squash verdict: PASS**, with `window_base` set to the `main` tip as in production.

Before WP05 the planning lane authored nothing, so this FAILed. That makes it a regression against the base, in the same class as reviews 7 to 9.

The texts are untrue for a derived base:
- the `_taint_spine` docstring ("Below the Mission base the content is either on the target already or pre-Mission history the squash axes exempt");
- the c9 ADR wording (same sentence);
- the migration doc ("the Mission base (the commit the Mission branch was cut from)");
- `_NO_MISSION_BASE`'s parenthesis "(the commit the Mission branch was cut from)", which is accurate only for a recorded base.

The fold report says "When the target has not merged anything in, the two are the same commit", meaning the Mission base and the merge-base. That is false for a derived base. In the probe, merge-base(main, coord) is `init`, while the derived base is the step 2 commit.

**Fix (fail closed; pick one):**
- **(a) Trust only a recorded base, mirroring `_pre_mission_attribution`.** Pass `pre_mission.base.sha` only when `pre_mission.base.provenance is MissionBaseProvenance.RECORDED`, and `None` otherwise, so the lane authors nothing.
  - The note's remedy already tells the operator to record `mission_base_sha`.
  - Default Missions record it at mint (`mission_creation_protected_mint.py:247`, `mission_creation_meta.py:207`), so a normal Mission is unaffected.
  - The note text then needs a "not recorded" reason.
- **(b) Start the taint walk at the lower of the two commits.** For a derived base, use `git merge-base <window base> <coordination base>`, where the window base is the target's pre-run tip and the claim already holds it as `excluded_window_base`. That bounds the squash diff from below regardless of where the scaffold sits.
  - This needs the window base threaded into `_collect_authored`.

Add a red-first test of the probe shape at claim level and at the squash verifier, plus a recorded-base control that still PASSes. Then correct the four texts.

## Issue 2 (low, report as requested): a Mission branch that merged the target before `finalize-tasks` cannot consolidate a later edit of a file the target changed, and nothing tells the operator why

Probe `test_merge_of_target_before_pin_then_owned_edit`:
1. The Mission is scaffolded.
2. `main` commits `curation/pkg/same.py` (`M = 1`).
3. The Mission branch runs `git merge --no-ff main` before the pin.
4. After the claim, a credited `feat(WP02)` appends `L = 1` to `same.py`.
5. Result: **FAIL**, unattributable `same.py`.

The only content that is not on the target is the reviewed `L = 1`.

Before cycle 9 the merge sat below the pin and was not walked, so this shape PASSed. Now the merge's first-parent diff taints `same.py`. This fails closed and is consistent with the review-6 rule that a merge is never credited. The post-pin merge case was already like this.

Keeping a Mission branch current by merging the target is a common habit, though, and the FAIL prints no planning-lane note:
- `planning_lane_notes` is computed only for a lane that credits nothing;
- this lane credits `other.py`.

So the operator gets a bare un-attributable path with no remedy. Two changes are needed:
- **Docs.** Name this shape in the migration doc's merge sentence, and give the remedy that works through the CLI, or say there is none, then file a follow-up.
- **Code, or a recorded residual.** Either have the FAIL text name a planning-owned path that a merge tainted, or record that as a residual.

I do not ask for the merge rule itself to change.

## Issue 3 (nit): the module docstring says "this repository"

`planning_lane_walk.py`, residual paragraph: "about 170 ms a commit on this repository's 41,000 files". This is shipped code, and "this repository" reads as the consumer's repository. Use the ADR's wording instead: "on a 41,000-file repository".

## Tests, mutations

See the report: `/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/wp05-review-10-report.md`.

### Test and mutation summary

- **Blast run.** It covered all the requested paths and the architectural and kernel gates, run at `-n 4 --dist loadfile`. Result: **19146 passed, 40 skipped, 11 xfailed, 0 failed** in 31m27s (`wp05-r10-blast.log`).
- **Mutations.** Each was applied in place, then restored and checked with `cmp` and `git diff --quiet`. None was committed. Every one was killed:

| Mutation | Result |
|---|---|
| M1: the taint walk starts from the pin | 6 failed |
| M2: the ancestor check is removed | 1 failed |
| M3: no Mission base falls back to the pin range | 2 failed |
| M5: a probe error falls back to the pin range | 1 failed |
| M4: the note ignores the taint spine | 1 failed |
