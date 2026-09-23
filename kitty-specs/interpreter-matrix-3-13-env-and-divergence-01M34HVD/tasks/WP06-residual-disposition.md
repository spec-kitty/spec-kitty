---
work_package_id: WP06
title: 'Residual-red disposition + #3189 filing (FR-006)'
dependencies:
- WP05
requirement_refs:
- FR-006
planning_base_branch: issue-4866-interpreter-matrix-3-13
merge_target_branch: issue-4866-interpreter-matrix-3-13
branch_strategy: Planning artifacts for this mission were generated on issue-4866-interpreter-matrix-3-13. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4866-interpreter-matrix-3-13 unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
history: []
agent_profile: python-pedro
authoritative_surface: kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/
create_intent:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-residual-disposition.md
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-residual-disposition.md
role: implementer
tags: []
tracker_refs: []
---

# WP06 — Residual-red disposition + #3189 filing (FR-006)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select
the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

State, in writing, one of the three FR-006 dispositions for any residual
3.13 red beyond the 4 `dir_fd` failures WP02 already fixed — and, if a
residual exists, file it against #3189 (or a new cross-linked issue) with
WP05's re-measured evidence, rather than leaving it unaddressed and
unremarked.

## Context

**This WP depends on WP05** — it consumes WP05's re-measured failure set
directly (read `evidence-remeasurement-3.13.md`); do not start this WP
before WP05's completion report is available.

**This is a documentation/decision WP, not a code change** — it owns exactly
one new planning-artifact file,
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-residual-disposition.md`
(new file, `create_intent`-declared), matching WP01/WP05's shape.

**The disposition is already chosen at spec-authoring time** (spec.md Edge
Case (c), plan.md's "Residual-red disposition" section) — this WP's job is
to **apply** that pre-decided disposition to WP05's real numbers, not to
re-litigate the decision:

- **Chosen disposition**: file the residue against **#3189** (already open,
  already the workflow's own declared home for above-3.12 divergence per its
  inline comment: "Deliberately scoped to the nightly lane, NOT the full
  above-3.12 suite burn-down (#3189 is a deferred follow-up, not claimed
  here)"). Any residual divergence beyond the 4 confirmed `dir_fd` failures
  is #3189's scope, not #4866's.
- **Do not** declare the leg "green regardless" if residue exists — that
  would be the green-washing charter Standing Order 9 forbids.
- **Do not** keep fixing until green, however long that takes — that
  silently absorbs #3189's entire deferred scope into this P1 CI-hygiene
  mission, which C-002 explicitly forbids.
- An honestly red `interpreter-matrix` leg, red because of real, tracked,
  currently out-of-scope 3.13 divergence, is **acceptable, correct doctrine**
  under charter Standing Order 9 — this WP's job is to make that red
  *honest* (tracked, evidenced, disclosed), not to eliminate it.

## Subtask T001: Compare WP05's re-measurement against WP02's 4 fixed IDs

**Purpose**: Determine which of the three FR-006 dispositions applies.

**Steps**:
1. Take WP05's recorded re-measured failure/error ID set (T003 of WP05).
2. Subtract WP02's 4 `dir_fd` failures (already confirmed absent from WP05's
   set per WP05 T003 step 1b — if they're NOT absent, stop and escalate;
   that means WP02's fix didn't actually land on the branch state WP05
   measured against, and this WP cannot proceed with a contradictory input).
3. Classify the remainder:
   - **Zero residual**: WP05's failure set, minus the 4 `dir_fd` IDs, minus
     the 3.11 baseline (WP01's 21), is empty.
   - **Small-and-fixable-in-scope**: a small residual exists but is
     genuinely within this mission's C-001 blast radius to fix (this would
     be unusual given C-001's narrow scoping — treat this classification
     with skepticism; if you find yourself wanting to fix something under
     `src/` or outside the three named kernel/core files, it is NOT
     small-and-fixable-in-scope, it is large-and-out-of-scope).
   - **Large-and-out-of-scope**: any residual beyond the 4 `dir_fd` fixes
     that is not a small in-scope fix — this is the expected, and
     charter-sanctioned, outcome per spec.md's own framing (the mission does
     not claim the leg turns green).

**Files**: create
`kitty-specs/interpreter-matrix-3-13-env-and-divergence-01M34HVD/evidence-residual-disposition.md`
and write the classification with its supporting numbers into it.

**Validation**: A clear classification with the supporting numbers cited
explicitly (not asserted from confidence).

## Subtask T002: File the residue (if any) against #3189

**Purpose**: Discharge the "does not leave residue unaddressed" half of
FR-006.

**Steps**:
1. If T001 classified the residual as zero: skip filing — record explicitly
   in your completion report that no residue exists and no #3189 filing was
   needed, with the numbers that support this.
2. If a residual exists (small-in-scope or large-out-of-scope): re-verify
   `#3189` is still open (`gh issue view 3189` — do not assume it's still in
   the state the plan/spec described; state changes between planning and
   implementation time). Post a comment on `#3189` attaching the exact
   re-measured evidence (command, counts, and the specific failure-ID diff
   against the 3.11 baseline) — or, if `#3189`'s own scope doesn't cleanly
   absorb the specific findings, open a new issue cross-linked to `#3189`
   instead. Record the comment URL or new issue number for the PR body.
3. If T001's Branch A-exception or Branch B follow-up issue from WP04 exists
   (the venv-corruption follow-up), cross-link it here too if relevant — do
   not create a third, redundant issue for the same underlying finding.

**Files**: append the comment URL / new issue number to
`evidence-residual-disposition.md` (same file as T001) — the deliverable
itself is the GitHub issue comment/new issue, but this file is what PR-prep
reads.

**Validation**: If residue exists, it is filed with real evidence attached,
cross-linked appropriately, not left as a bare mention.

## Subtask T003: State the disposition plainly

**Purpose**: Produce the exact PR-body language FR-006's acceptance
criterion requires.

**Steps**:
1. Write, for inclusion in the mission's PR body (PR-prep consumes this —
   this WP does not itself have a PR to edit yet), a plain statement of
   which of the three dispositions applies: residual is zero, residual is
   small-and-fixable-in-scope (and was fixed — but see T001's skepticism
   note), or residual is large-and-out-of-scope (filed against #3189, leg
   legitimately still red).
2. **Do not write or imply "nightly turns green"** unless WP05's
   re-measurement, after WP02/WP03/WP04, in fact shows zero residual beyond
   the 4 already-fixed `dir_fd` failures. This is a hard constraint from
   spec.md's Success Criteria section (SC-005) and charter Standing Order 9
   — a false green claim here is exactly the failure mode this mission's
   own root cause (issue #4866) was about.
3. Record this disposition statement for PR-prep / WP07 to carry forward
   verbatim into the mission's PR body.

**Files**: append the final disposition statement to
`evidence-residual-disposition.md` (same file as T001/T002) — PR-prep copies
this verbatim into the PR body.

**Validation**: A plain, evidence-grounded disposition statement exists,
correctly reflecting WP05's real numbers, with no unsupported green claim.

## Definition of Done

- [ ] T001: WP05's residual classified (zero / small-fixable / large-out-of-
      scope) with numbers cited
      (`spec-kitty agent tasks mark-status T001 --status done`).
- [ ] T002: residue filed against #3189 (or a new cross-linked issue), or
      explicitly recorded as not needed if residual is zero
      (`spec-kitty agent tasks mark-status T002 --status done`).
- [ ] T003: the plain disposition statement is written for the PR body, with
      no unsupported "nightly turns green" claim
      (`spec-kitty agent tasks mark-status T003 --status done`).

## Risks

- **The main risk is a false-green claim** — the entire point of this WP is
  to state the disposition honestly, even if that means saying the leg is
  still red at mission close. Re-read spec.md's Success Criteria section
  before writing T003's statement if there is any doubt.
- Re-verify `#3189`'s live state before filing (T002 step 2) — do not trust
  the plan/spec's snapshot as still current without checking.

## Reviewer Guidance

- Recompute T001's classification yourself from WP05's raw numbers — don't
  just trust this WP's stated conclusion.
- If residue was found, confirm the #3189 comment/new issue actually
  contains the re-measured evidence (command, counts, failure-ID diff), not
  just a link back to this mission's PR.
- Scrutinize T003's disposition statement specifically for any language that
  could be read as "the nightly leg is now green" when the numbers don't
  support it.

Implementation command: `spec-kitty agent action implement WP06 --agent claude`
