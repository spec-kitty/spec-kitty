# Mission Specification: Squash Merge Target Safety

**Issue:** [#4892](https://github.com/spec-kitty/spec-kitty/issues/4892)  
**Mission type:** software-dev

## Problem

The default `spec-kitty merge` strategy integrates a mission branch with
`git merge --squash -X theirs`. When the target branch and mission branch both
modify an ordinary source file, this global preference silently selects mission
content. The command then reports success, marks work packages done, writes the
retrospective, and removes lane resources. A legitimate target-branch change can
therefore disappear from the resulting tree without any warning.

## Outcome

Default squash branch integration must be lossless when changes are disjoint and
must fail closed when ordinary content genuinely conflicts. The dry-run forecast
must predict the same blocker. Existing path-scoped merge drivers and the
target-newer planning-artifact policy remain authoritative.

## Users and stories

### US-001 — Protect target changes during default integration

As an operator merging a completed mission, I need a conflict with newer target
source content to stop before the target ref changes so I can resolve it
deliberately.

### US-002 — Trust dry-run as a readiness forecast

As an operator preparing a merge, I need `spec-kitty merge --dry-run` to report
a conflict that the real default squash integration would reject.

### US-003 — Preserve established artifact reconciliation

As a maintainer, I need governed bookkeeping and target-newer planning artifacts
to retain their path-specific reconciliation behavior while ordinary source
content stops using a global conflict preference.

## Functional requirements

- **FR-001:** Default mission-to-target squash integration MUST NOT invoke Git
  with a blanket `-X theirs` or equivalent mission-wide conflict preference.
- **FR-002:** When the mission and target modify the same ordinary content hunk,
  integration MUST return a non-success result and MUST leave the target ref and
  target checkout bytes unchanged.
- **FR-003:** A failed conflict MUST occur before work-package completion,
  retrospective finalization, branch deletion, or worktree removal.
- **FR-004:** Non-overlapping changes to the same ordinary file MUST merge
  losslessly under the default squash strategy.
- **FR-005:** Existing registered custom merge drivers MUST remain the authority
  for their governed artifact paths.
- **FR-006:** Target-newer PRIMARY planning artifacts MUST retain the current
  history-aware target-preservation behavior; the fix MUST NOT turn those paths
  into unconditional blockers or mission-preferred content.
- **FR-007:** For an existing mission and target ref, squash dry-run MUST exercise
  the same conflict-detection primitive used by execution.
- **FR-008:** A predicted ordinary content conflict MUST make dry-run exit
  non-zero and emit a stable diagnostic containing the mission branch, target
  branch, deterministic repo-relative conflict paths, and remediation.
- **FR-009:** A clean dry-run MUST preserve the existing successful JSON payload
  key set and exit behavior.
- **FR-010:** Dry-run conflict detection MUST NOT advance or rewrite either ref,
  change tracked checkout bytes, emit lifecycle completion, or perform cleanup.
- **FR-011:** The explicit `merge` and `rebase` strategy behavior MUST remain
  unchanged.

## Non-functional requirements

- **NFR-001 — Atomicity:** target-ref advancement occurs only after the isolated
  integration has no unresolved conflict.
- **NFR-002 — Determinism:** conflict paths and diagnostics are sorted and stable.
- **NFR-003 — Locality:** implementation stays within the existing lane merge and
  dry-run forecast seams; no second merge policy authority is introduced.
- **NFR-004 — Auditability:** tests demonstrate red-first failure for execution
  and dry-run, target preservation, disjoint merging, and governed artifacts.
- **NFR-005 — Compatibility:** clean forecast schema and non-squash strategies
  remain backward compatible.

## Acceptance scenarios

### AC-001 — Same-hunk source divergence fails closed

Given a shared source file at the branch merge base, and the mission and target
branches commit different values to the same line, when default squash branch
integration runs, then it reports failure, names the conflict path, and the
target SHA and bytes equal their pre-integration values.

### AC-002 — Disjoint changes remain lossless

Given the mission changes one line and the target changes a different line in
the same source file, when default squash integration runs, then it succeeds and
the target tree contains both edits.

### AC-003 — Dry-run predicts the blocker

Given AC-001's graph and a valid merge-ready mission, when
`spec-kitty merge --dry-run --json` runs, then it exits non-zero with the stable
conflict diagnostic and does not change refs, tracked files, WP states, lane
branches, or worktrees.

### AC-004 — Clean dry-run contract stays frozen

Given a conflict-free merge-ready mission, when dry-run runs, then it exits zero
and the successful JSON object has exactly the existing contract keys.

### AC-005 — Governed artifacts retain path-specific behavior

Given a divergence handled by a registered Spec Kitty merge driver or by the
target-newer planning artifact authority, when default squash integration runs,
then that authority resolves the path and no global mission preference is used.

## Negative invariants

- **NI-001:** No ordinary source conflict may be converted to success by choosing
  the mission side globally.
- **NI-002:** A conflict may not advance the target ref, mark WPs done, finalize a
  retrospective, delete a branch, or remove a worktree.
- **NI-003:** Dry-run may not report ready for a graph execution would reject.
- **NI-004:** Dry-run may not change the clean-success payload schema.
- **NI-005:** The fix may not disable or supersede registered artifact merge
  drivers.
- **NI-006:** The fix may not broaden target-preference from the established
  planning-artifact policy to ordinary source paths.

## Out of scope

- Changing the default strategy away from squash.
- Redesigning lane-to-mission consolidation.
- Automatic semantic resolution of ordinary source conflicts.
- Remote push or hosting behavior.
- Reworking the merge retention policy.
