---
affected_files: []
cycle_number: 11
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-27T22:11:02Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 11 (claude::reviewer-renata) — REJECTED

The cycle-10 folds hold as claimed: `_taint_base` gates on `RECORDED`, the one call site in
`reconciliation_claim._build_claim` threads it, the note names a derived base apart, the new e2e
test drives the remedy, residual (d) is documented with #7891, and the docstring nit is fixed.
Static checks and the blast run are clean (see the report). What follows are new findings,
each probed.

## Issue 1 (high, fail-open): the `_BASE_NOT_RECORDED` remedy reopens the exact cycle-10 leak

`planning_lane_scope.py:106-112` (`_BASE_NOT_RECORDED`), mirrored in
`docs/migrations/planning-lane-write-branch.md:127-129` and the ADR wording (c10, remedy bullet),
tells the operator to hand-write `mission_base_sha` into meta.json. The recorded-base validation
in `mission_base._recorded_base` only requires the value to be a full commit id in the clone, an
ancestor-or-equal of the Mission's *origin* (the scaffold commit's first parent) and below the
Mission directory. The pre-scaffold commit X of the cycle-10 shape **is** the origin, so writing X
passes every check and becomes a RECORDED base.

Probe (scratch, never committed:
`/tmp/claude-0/-home-user-spec-kitty/241acd7b-8c3e-5505-b70e-8c22ad244fdf/scratchpad/r11probe/test_r11_handedit.py`),
cycle-10 shape (20 unreviewed lines in `same.py` committed on the Mission branch before the
scaffold, then a credited WP02 edit):

| `mission_base_sha` written | provenance | credited | squash verdict |
|---|---|---|---|
| the scaffold's first parent X (pre-scaffold commit) | recorded | `other.py`, **`same.py`** | **PASS** (the 20 lines land unreviewed) |
| the `main` cut | recorded | `other.py` | FAIL on `same.py` (correct) |

The refusal text itself steers to the wrong value: the same sentence names "the one derived from
its first commit (the scaffold commit's first parent)", and an agent asked to find "the commit
the Mission branch was cut from" will most naturally compute `git rev-parse <scaffold>^`, which
is X in exactly the shape the gate exists for (and harmless in every other shape, so a test
would never show it). There is no CLI that records `mission_base_sha` (`record_mission_base_sha`
is write-once, create-only; nothing under `cli/` or `upgrade/` writes it), so the remedy is a
hand-rolled edit, which CLAUDE.md's canonical-sources rule asks us not to prescribe. It is a
recorded act (a commit of meta.json on the Mission branch), but nothing validates it against the
property the taint walk relies on, and the ADR sentence "Below a recorded base the content is on
the target already or is pre-Mission history" is then false.

Fix (pick one; I recommend **a**, it is small and keeps the remedy honest):
- **a. Validate.** In `planning_lane_walk._taint_base` (or a helper it calls with the claim's
  target pre-run tip / claim base), accept a recorded base only when it is an ancestor-or-equal of
  the target's pre-run tip (`is_ancestor_strict(base, target_base)`). The commit a Mission branch
  was cut from was a target tip; a Mission-branch-only commit (X) is not on the target. Otherwise
  the lane authors nothing, with a note reason "the recorded Mission base is not on <target>".
  Add the probe above as a regression test (the pre-scaffold value must not credit `same.py`),
  and make the remedy text say "a commit on `<target>` (the target commit the branch started at,
  for example `git merge-base <target> <scaffold>^`)" rather than naming the scaffold's parent.
  The target's pre-run tip is already in `_build_claim` as `excluded_window_base`
  (`reconciliation_claim.py:150,199`), so no new input is needed; `None` there must also author
  nothing. Fail-closed side effects to document: a rewritten (force-pushed) target or a retargeted Mission
  then credits nothing.
- **b. Drop the remedy.** Print "there is no verified remedy today" (as residual (d) does) and
  file a follow-up for a validating CLI (e.g. a `migrate`/`doctor` subcommand that records a
  base after checking it is on the target). Then the e2e test drives the refusal only.

Either way, keep the e2e test's restore value as the `main` cut and add a sibling case that
writes the scaffold's first parent.

## Issue 2 (medium, release note): every in-flight default Mission created on a released build is un-creditable

`mission_base_sha` is written only since 0b7b3e9e92 (#7560, 2026-11-13), which is **not** in
`v4.0.0rc8` (2026-11-09) and ships first with rc9; the create-time default topology
(ADR 2026-11-06-3, `lanes/topology_settlement.py`) **is** in rc8. So every default Mission
created on rc8 that settled `lanes_with_coord` has no recorded base, resolves a DERIVED base, and
after this change its planning lane authors nothing: `consolidate` FAILs on every owned,
non-bookkeeping planning path, exactly as before the fix. (No regression against rc8, but the
fix does not reach them.) The fragments do not say so:
- `docs/changelog/unreleased/7860.upgrade-notes.md` covers only the evidence-window side of
  in-flight Missions.
- `7860.fixed.md` and the migration doc say "created before #7560", an issue number operators
  cannot map to a version.

Fix: add an upgrade-notes bullet: a default Mission created on 4.0.0rc8 or earlier records no
`mission_base_sha`; its planning lane's work is refused at `consolidate` until <the remedy from
Issue 1, or "no remedy today, land it ... / re-create">. Say "created before 4.0.0rc9" in the
migration doc instead of (or beside) "before #7560".

## Issue 3 (low, doc truth): ADR/doc claim about content below a recorded base

ADR wording c10 ("Below a recorded base the content is on the target already or is pre-Mission
history the squash axes exempt") and the `_taint_spine` docstring
(`planning_lane_walk.py:335-341`) state as fact what holds only when the recorded base is the
true cut. After Issue 1(a) it becomes true by validation; with 1(b), qualify it ("a recorded base
is trusted as tool-written; a hand-written value is not validated against the target").

## Residual (d) assessment (no change requested beyond the above)

The wording is accurate for merge, rebase, cherry-pick before finalize and merge after it (the
probe set in fold 10 matches). In practice it bites only when a target change touches a file a
planning work package owns and then edits; planning work packages usually own docs or curation
paths, so syncing the Mission branch with the target is not a blocker in general, but it is one
for long-lived Missions whose planning WPs own shared docs. The advice "keep target changes to
the owned files out of the Mission branch until it lands" is the right interim guidance.
