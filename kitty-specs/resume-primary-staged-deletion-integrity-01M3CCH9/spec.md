# Mission Specification: Merge resume primary-site staged-deletion integrity

**Mission Branch**: `kitty/mission-resume-primary-staged-deletion-integrity-01M3CCH9`
**Created**: 2026-09-25
**Status**: Draft
**Input**: GitHub issue [#4997](https://github.com/spec-kitty/spec-kitty/issues/4997) (P0, milestone #11 MVP launch) — primary-checkout sibling of the closed #4982.

## Context

`spec-kitty merge --strategy merge` (lanes topology) advances the target branch with
`git update-ref` and then runs `git reset --hard <target>` in the primary checkout to
resync it. Those two steps are **unlinked** (#1826). If the `reset --hard` fails (an
`index.lock` held by another git process / IDE) or the process is killed between them,
the primary checkout's index and working tree lag their own (already-advanced) HEAD:
the mission's own files read as **staged deletions**.

`merge --resume` then hits the pre-mutation primary dirty guard
(`_pre_mutation_safety_preflight` → `assert_worktree_clean(main_repo,
error_code=MERGE_UNSAFE_PRIMARY_DIRTY)`), which refuses `rc=1` and advises "Commit,
stash, or revert". Two failure modes follow:

1. **Resume cannot recover.** Even though the state is a pure behind-own-HEAD lag that a
   `git reset --hard HEAD` would fully repair, the resume aborts instead of recovering,
   so approved WP content never lands (the interrupted merge is stuck).
2. **The "Commit" remedy is catastrophic.** An operator (or an agent following the literal
   remedy) commits the staged deletions, recording a commit on the target that deletes
   every mission file. The re-run `git merge <mission>` is then "Already up to date" (the
   mission branch is already an ancestor), but under the **merge** strategy the FR-037
   zero-diff adjudication never fires (the merge no-op wrongly reports `already_applied=False`),
   so every WP is stamped `done`, lanes and the mission branch are deleted, `exit 0` — and
   **the target ends with none of the mission's code.**

#4982 (closed 2026-09-24) fixed the *clean-primary* behind-own-HEAD window at the
lane-consolidation site. #4997 is the **primary-checkout sibling**: the same window but
with the primary carrying staged deletions, plus the merge-strategy no-op adjudication
gap. A red-first repro already exists at `tests/terminus/test_repro_4997.py`
(`xfail(strict)`), named by the #4982 fix commit as the tracked follow-up.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A resume over a behind-own-HEAD primary recovers and lands all approved code (Priority: P1)

An operator ran `spec-kitty merge --strategy merge`; the target ref advanced but the
primary checkout's `reset --hard` failed (index.lock) or the process was killed, leaving
the primary's tree/index lagging its own HEAD with the mission's files shown as staged
deletions. The operator runs `spec-kitty merge --resume`.

**Why this priority**: This is the P0 data-integrity path. A resume that cannot recover a
pure lag either strands the merge or (via the "Commit" remedy) destroys the whole
mission's code from the target while reporting success.

**Independent Test**: `tests/terminus/test_repro_4997.py`, driven through the real
`spec-kitty merge --resume` CLI: after an interrupted terminus that advanced the target
and left the primary lagging with staged deletions of the mission's own files, a single
`--resume` recovers and every approved WP's commit SHA is reachable from the target.

**Acceptance Scenarios**:

1. **Given** the target ref was advanced to include the mission (mission branch is an
   ancestor of the primary HEAD) and the primary's tree/index are byte-identical to the
   persisted pre-mutation target tip (a pure lag, phantom staged deletions only),
   **When** `spec-kitty merge --resume` runs, **Then** it recovers the primary
   (`git reset --hard HEAD`), continues the merge, and every approved WP commit is
   reachable from the target (`exit 0`).
2. **Given** the same behind-own-HEAD window but the primary ALSO carries a genuine
   tracked edit or an intentional deletion of a non-mission file (the working tree/index
   differ from the persisted pre-mutation target tip), **When** `spec-kitty merge --resume`
   runs, **Then** it REFUSES (`rc != 0`) and never runs `reset --hard` — the genuine local
   change is preserved, not discarded.

---

### User Story 2 - A no-op merge that would leave the target missing approved content refuses (Priority: P1)

After the "Commit" mis-remedy (or any state where the mission branch is already an ancestor
of the target but the target tree no longer carries the mission's content), the resumed
`git merge <mission>` is "Already up to date".

**Why this priority**: Without adjudication, the merge no-op stamps every WP `done`, deletes
lanes and the mission branch, and exits 0 with the target missing the code — silent,
unrecoverable-except-by-reflog whole-mission loss.

**Independent Test**: a red-first regression test: with the mission branch an ancestor of
the target but the target tree diverging from the mission tree, `spec-kitty merge --resume
--strategy merge` refuses (`rc != 0`) instead of marking WPs done / exit 0.

**Acceptance Scenarios**:

1. **Given** the merge strategy and a mission branch already an ancestor of the target whose
   tree diverges from the mission tree, **When** the mission→target integration runs, **Then**
   `_merge_branch_into` reports the no-op (`changed=False` → `already_applied=True`) and the
   strategy-agnostic zero-diff adjudication refuses the merge (`exit 1`) before any WP is
   stamped `done` or any lane/branch is torn down.

### Edge Cases

- **Genuine local edit coexisting with the lag** → the phantom-only proof fails → refuse (US1 AC2).
- **Intentional deletion of a non-mission file (e.g. `README.md`) in the window** → tree differs
  from the pre-mutation base → refuse (never resurrected).
- **`pre_mutation_target_sha` not persisted** (a resume before the target advanced) → cannot prove
  a pure lag → refuse (fail-closed; the state is not a behind-own-HEAD recovery).
- **`index.lock` still present** → `BLOCKED_INDEX_LOCK` remedy path (unchanged): surface the lock,
  do not reset over an interrupted transaction.
- **Squash strategy** → existing behaviour unchanged; the no-op adjudication already fires for squash.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Phantom-only recovery on resume | As an operator resuming an interrupted `--strategy merge`, I want a pure behind-own-HEAD primary (index/tree byte-identical to the persisted pre-mutation target tip, HEAD its descendant) to be recovered with `git reset --hard HEAD` and the merge continued, so approved code lands instead of the resume aborting. | High | Open |
| FR-002 | Fail-closed on any non-phantom dirt | As an operator, I want the resume to REFUSE (never `reset --hard`) the moment the primary carries any change not explained by the pure lag (genuine edit, intentional non-mission deletion, missing pre-mutation base), so no genuine local work is destroyed. | High | Open |
| FR-003 | Merge-strategy no-op adjudication | As an operator, I want a "Already up to date" mission→target merge that would leave the target tree missing approved content to be reported as a no-op (`already_applied=True`) and refused by the zero-diff adjudication, so the merge cannot exit 0 with WPs `done` and the target missing the code. | High | Open |
| FR-004 | Faithful red-first repro | As a maintainer, I want `tests/terminus/test_repro_4997.py` corrected to model the real behind-own-HEAD window (target advanced, primary lagging with phantom staged deletions of the mission's own files) and to PASS with the xfail removed. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new dirty-guard authority | The recovery reuses the single `classify_resume_dirty_remedy` classifier and the persisted `pre_mutation_target_sha`; it introduces no parallel dirty predicate (INV-3). | Maintainability | High | Open |
| NFR-002 | Atomic refusal | On any refusal path the repository is byte-identical to pre-invocation; recovery mutates only via `reset --hard HEAD` after the phantom-only proof passes. | Reliability | High | Open |
| NFR-003 | Zero ruff/mypy issues; complexity ≤15 | New/changed functions pass `ruff` + `mypy` clean, no new suppressions, McCabe ≤15; new branches/helpers carry focused tests in the same PR (Sonar new-code gate). | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not weaken the discriminator | The fix must NOT loosen the primary dirty guard to reset away arbitrary staged deletions; recovery is gated on ancestry AND the phantom-only proof. | Technical | High | Open |
| C-002 | Reconciliation-gate merge blind spot is a documented residual | The reconciliation gate's merge/rebase axis is pure ancestry and blind to a merged-then-content-reverted lane; FR-003's tree-equality adjudication is the primary guard. Extending the #5013 blob-attribution axis to the merge strategy is out of scope and recorded as a follow-up. | Technical | Medium | Open |
| C-003 | Canonical merge module only | All changes land in `src/specify_cli/merge/` + `src/specify_cli/lanes/merge.py` + `src/specify_cli/git/`; no new authority outside the merge seam. | Technical | High | Open |

### Key Entities

- **`pre_mutation_target_sha`** (`MergeState`): transaction-start target tip, persisted read-first — the lagged base against which the phantom-only proof is computed.
- **`ResumeRemedyKind.BEHIND_OWN_HEAD`** (`merge/preflight.py`): ancestry classification of a dirty resume checkout.
- **Phantom-only proof**: the primary's working tree AND index are byte-identical to `pre_mutation_target_sha` and HEAD is its descendant → `reset --hard HEAD` is provably non-destructive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `tests/terminus/test_repro_4997.py` passes with the `xfail` removed, modelling the real behind-own-HEAD window.
- **SC-002**: A new safety test proves a resume over a behind-own-HEAD window with a coexisting genuine edit REFUSES and preserves the edit (no `reset --hard`).
- **SC-003**: A new red-first test proves a merge-strategy "Already up to date" no-op that would leave the target missing approved content refuses (`rc != 0`), never stamping WPs `done` / exit 0.
- **SC-004**: `tests/terminus/` and the merge subsystem test directories are green locally before push; `ruff`/`mypy`/format clean.
- **SC-005**: `test_repro_4982.py` (clean-primary sibling) remains green — no regression to the closed sibling.
