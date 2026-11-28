---
affected_files: []
cycle_number: 12
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T23:41:19Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 12 (claude::reviewer-renata), REJECTED (doc-truth findings only)

The cycle-11 code fold holds. `_taint_base` accepts a recorded base only when
`is_ancestor_strict(base, excluded_window_base)` holds. A missing target tip, a base off the target
and a probe error all return `None`. `_build_claim` runs that probe once and passes the result to
both `_collect_authored` and `planning_lane_notes`. Every claim route gives it the target's pre-run
tip:
- the gate rebuild: `run.target_expected_old_sha`;
- resume: `state.pre_mutation_target_sha`;
- the forecast: the live tip;
- the orchestrator API: `target_tip`.

I probed the topology by hand. With a target merge before the scaffold, the first-parent diff still
taints the file, whichever parent comes first. A rewritten or retargeted target only makes the
taint walk longer, so both fail closed. I found no fail-open path.

All 8 mutations were killed: the four fold-11 guards, plus pin ancestry, rename inheritance, the
`whole` admission and trusting a derived base. ruff, format, mypy and C901 are clean. The changelog
style check reports 0 errors and the spelling check 0 findings. No suppressions were added.

What remains is five doc and hygiene findings, all introduced in WP05 folds.

## F1 (low, changelog truth, fold 11): `docs/changelog/unreleased/7860.fixed.md` misstates the per-file rule
The sentence reads: "...and a file only when every change to it since the recorded Mission base is
credited; **otherwise the lane authors nothing, and the refusal names the lane, the reason and the
remedy**."

A reader takes "otherwise" to apply to the clause before it: one uncredited change to a file. The
code does something else:
- Only that path is attributed to nothing. `_scoped_final_walk` skips tainted paths, and the rest of
  the lane stays credited.
- No planning-lane note prints when the lane credits other work, because `planning_lane_notes`
  emits a note only when the scope is empty or `_taint_spine` is `None`. This is residual (d),
  #7891.

The cut from 3,836 characters also dropped the list of cases where the lane authors nothing, and
"Other Missions and code lanes are unchanged."

Fix: say that a file with any uncredited change is refused, then name the lane-level cases. Stay
under 1,200 characters. For example:

"...and a file only when every change to it since the recorded Mission base (a commit on the
target) is credited; another file is refused as un-attributable. The lane credits nothing when a
planning work package is not approved, an `owned_files` list is unreadable or too broad, a claim
commit cannot be proven, or no usable Mission base is recorded, and the refusal then names the lane,
the reason and the remedy."

## F2 (low, doc truth, fold 11): "a Mission retargeted onto another branch credits nothing" is too broad
This sentence appears in `docs/migrations/planning-lane-write-branch.md:70-71` and in the ADR
wording (`adr-wording-c11.md`, "So a target rewritten below the base (force-pushed) or a Mission
retargeted onto another branch credits nothing (fail closed)").

`_taint_base` refuses a retargeted Mission only when the new target does not contain the recorded
base. A Mission retargeted onto a branch that contains the base is credited as usual.

Fix: "a Mission retargeted onto a branch that does not contain its recorded base". The `_taint_base`
docstring is already accurate, because it lists retargeting as an example of a base that is not on
the target.

## F3 (nit, docstring, fold 11): `planning_lane_scope._no_taint_base_reason`
The docstring says a recorded base off the target was "checked to be at or below the scaffold's
parent, so its merge base with the target is the commit the branch was cut from too". That holds
only when the target was not rewritten and the Mission was not retargeted. Otherwise the merge base
is an older common commit. That outcome is still safe, because the longer walk taints more.

Fix: "...is a commit on the target at or below the cut (the cut itself unless the target was
rewritten or the Mission retargeted)".

## F4 (nit, module hygiene, folds 10-11): `planning_lane_walk.__all__` is missing two imported names
Commit 3c69ad71f2 set the rule "export only the planning walk names other modules import". Two
names that other modules now import are missing from `__all__`:
- `_taint_base`, which `reconciliation_claim` imports with `from ... import`;
- `_taint_spine`, which `planning_lane_scope` reads as `walk._taint_spine`.

Add both. The dead-symbols gate stays green, since both names have callers.

## F5 (nit, AGENTS.md / CLAUDE.md, fold 11): the target check is not named
`AGENTS.md` ends the default-Mission paragraph with "a Mission with no recorded base (a derived one
is not trusted, `_taint_base`) or an unusable one authors nothing too." The sentence is true, but it
hides the review-11 rule that agents most need: a hand-written `<scaffold>^` is rejected. The
implementer flagged this in the fold-11 report. AGENTS.md is in WP05's owned files, and CLAUDE.md is
a symlink to it.

Fix: "...a Mission with no recorded base, or one that is not a commit on the target (`_taint_base`:
a derived base is not trusted), or one that is otherwise unusable, authors nothing too."

No code change is needed. All five fixes are text, so no test is needed beyond re-running
`check_changelog_style`, `check_spelling` and `tests/docs`.
