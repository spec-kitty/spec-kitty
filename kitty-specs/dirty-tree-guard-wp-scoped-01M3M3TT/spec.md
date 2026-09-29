# Mission Specification: Dirty-Tree Guard Is WP-Scoped

**Mission Branch**: `issue-5007-dirty-tree-guard-wp-scoped`
**Created**: 2026-09-28
**Status**: Draft
**Input**: GitHub issue `spec-kitty/spec-kitty#5007`, re-scoped by maintainer `stijn-dejongh`'s
2026-09-27 triage comment to be the canonical home for the "dirty-tree guard is not WP-scoped"
defect (superseding the issue's original two-friction body and an earlier groom-sweep comment
that had proposed folding the mission-wide issue-matrix gate in here too).

## Overview

### Motivation

`spec-kitty agent tasks move-task` refuses a lane transition when the working tree is dirty.
The refusal is meant to protect against a work package (WP) leaving its own uncommitted work
behind. In practice the guard cannot tell **whose** uncommitted residue it is looking at:

- `src/specify_cli/review/dirty_classifier.py::_is_benign(path, wp_id)` accepts `wp_id` but
  never reads it — every non-benign dirty path blocks the transition regardless of which WP
  actually produced it.
- `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py::_validate_research_artifacts`
  then unconditionally narrates every blocking path as `"owned by {wp_id}"` — the WP currently
  being moved — even when that WP never touched the path.

Three independently reported, concretely reproduced occurrences share this one root cause:

1. **#5151 ask 3** — one uncommitted `kitty-specs/` path belonging to another WP's in-progress
   work (a script, not necessarily a `.md` file) blocked every *other* WP's `move-task`.
2. **#5159 item 4** — another WP's uncommitted `review-cycle` directory blocked
   `move-task --to approved` for an unrelated WP.
3. **kentonium3's corroboration** (reproduced on pinned build `spec-kitty-cli 4.0.0rc3`,
   2026-09-19/24) — a verdict via `move-task` writes an untracked `review-cycle-N.md` record
   in the primary checkout; the *next* WP's `move-task --to for_review` is then blocked by that
   record.

### What This Mission Delivers

Scopes the dirty-tree guard to the WP that actually owns a dirty path, using the existing
`kitty-specs/<mission_slug>/tasks/<WPxx>-*/` directory-naming convention as the ownership
source, and corrects the refusal message to name the real owner (or state that none could be
determined) instead of always blaming the WP being moved. A path that cannot be attributed to
any WP continues to block the transition — this mission narrows *false positives*, it does not
relax the guard's fail-closed posture.

**Out of scope** (explicitly, per the operator-ruled triage that re-scoped this issue):

- The mission-wide issue-matrix approval gate (`_issue_matrix_approval_blocker`) — this was
  friction 1 in the issue's *original* body. A groom-sweep comment proposed folding "friction 2"
  (the dirty-tree WP-scoping defect) in alongside it, but stijn-dejongh's later 2026-09-27 triage
  comment is the operative, most-recent maintainer ruling: it redefines this issue as the
  canonical home for the WP-scoping defect specifically, and does not mention the issue-matrix
  gate. The latest ruling governs; the issue-matrix gate is not this mission's concern.
- `#5159`'s items 1–3 (`auto_commit:false` leaving artifacts uncommitted, `review-cycle-N`
  overwrite, `spec-commit` refusal) — stijn's comment names only item 4 as a fold-in.
- Any change to `src/specify_cli/ownership/` (the `owned_files` frontmatter-driven ownership
  module), `.kittify/` config/metadata handling, or `lanes.json` — see Constraints below for why
  the ownership module specifically is the wrong tool here.
- `record-analysis`'s own dirty-tree preflight (SK-249) — a different command in the same guard
  family; see Related History below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Another WP's residue does not block my transition (Priority: P1)

As an agent (or the orchestrator) moving a work package through the lane state machine via
`move-task`, I want the dirty-tree guard to ignore uncommitted paths that provably belong to a
*different* WP's task directory, so that concurrent WPs in the same mission don't block each
other's legitimate transitions.

**Why this priority**: This is the root cause behind all three reported occurrences (#5151 ask
3, #5159 item 4, kentonium3's Friction 2). Every other story depends on this scoping existing.

**Independent Test**: With a dirty tree containing only a path under
`kitty-specs/<slug>/tasks/WP02-*/` (any file, any extension, or — with the mission's
`kitty-specs/<slug>/tasks/` parent directory already tracked, per Edge Cases' "Wholly untracked
WP directories" note — the bare directory itself when wholly untracked), invoke `move-task` for
`WP01` in the same mission and observe the transition proceed without refusal.

**Acceptance Scenarios**:

1. **Given** a dirty path `kitty-specs/<slug>/tasks/WP02-foo/notes.py` and WP01 is being moved,
   **When** `move-task WP01 --to for_review` runs, **Then** the transition succeeds and the path
   does not appear in any blocking guidance.
2. **Given** a dirty path that is a *wholly untracked* directory
   `kitty-specs/<slug>/tasks/WP02-foo/` (git reports the directory path itself, no filename,
   because nothing inside it is tracked yet, and the mission's `kitty-specs/<slug>/tasks/` parent
   directory is already tracked — see Edge Cases, "Wholly untracked WP directories"; a fixture
   where `kitty-specs/` itself is still untracked exercises the FR-004 fallback instead, not this
   scenario) and WP01 is being moved, **When** `move-task WP01 --to for_review` runs, **Then** the
   transition succeeds.
3. **Given** a dirty path `kitty-specs/<slug>/tasks/WP01-foo/scratch.md` under the *moving* WP's
   own directory, **When** `move-task WP01 --to for_review` runs, **Then** the transition still
   blocks on that path (a WP's own uncommitted work is not exempted by this mission).

---

### User Story 2 - The refusal tells the truth about who owns the path (Priority: P1)

As the agent receiving a blocked-transition refusal, I want the guidance message to name the
path's real determined owner — the moving WP itself, when the residue genuinely is its own, or an
explicit "not attributable" statement, when it is not — instead of unconditionally claiming the
WP I am moving owns it regardless of which case actually applies, so I don't waste time trying to
reconcile a change I never made.

**Why this priority**: Even where the current fail-closed block is correct (an unattributable
path), the *message* is actively misleading today — it always says "owned by {wp_id}" for the WP
being moved. This is the second half of the root cause stijn's triage comment names explicitly:
*"the refusal message names the real owning WP (or none), not the WP being moved."*

**Independent Test**: Trigger a blocking refusal with an unattributable dirty path and inspect
the guidance text for an honest ownership statement instead of a hardcoded `{wp_id}` claim.

**Acceptance Scenarios**:

1. **Given** a dirty path that matches no WP's task directory and no existing benign category,
   **When** the transition is refused, **Then** the guidance states the path is not attributable
   to a specific work package (not "owned by {wp_id}" naming the WP being moved).
2. **Given** a dirty path under `kitty-specs/<slug>/tasks/WP01-*/` and WP01 itself is being
   moved, **When** the transition is refused, **Then** the guidance correctly attributes the path
   to WP01 (this is the one case where "owned by {wp_id}" is actually true).
3. **Given** a single refusal's blocking list contains more than one path with *different*
   determined owners (e.g. one path under the moving WP's own directory per FR-007, plus one
   path that is not attributable to any WP per FR-004, in the same `move-task` call), **When**
   the transition is refused, **Then** each blocking line in the guidance is annotated with its
   own determined owner (the moving WP itself, or "not attributable") — not one shared header
   applied to the whole blocking list. (A blocking path can never be determined to belong to a
   *different* specific WP: FR-001/FR-002/FR-003 route any path attributable to another WP's task
   directory into `benign`, so the only two outcomes reachable for a line that is actually
   blocking are the moving WP's own residue (FR-007) or "not attributable" (FR-004).)

---

### User Story 3 - Unowned dirty state still fails closed (Priority: P2)

As a maintainer relying on this guard family's long-standing fail-closed design precedent
(SK-114/SK-115), I want a dirty path this mission cannot attribute to any WP to keep blocking
the transition, so the fix narrows false positives without opening a silent-pass hole.

**Why this priority**: This is the guard's core safety property and the explicit operator
decision recorded in Clarifications Q2. It is P2 relative to Story 1 only because it is a
*preservation* of existing behavior rather than new behavior, but it is exercised by the same
test suite and is equally required for acceptance.

**Independent Test**: Construct a dirty path with no relationship to any WP's task directory
(e.g., a stray file directly under `kitty-specs/<slug>/`) and confirm `move-task` still refuses
for every WP in the mission.

**Acceptance Scenarios**:

1. **Given** a dirty path `kitty-specs/<slug>/some-stray-file.txt` that matches no WP directory
   and no existing benign category, **When** any WP's transition is attempted, **Then** the
   transition refuses.

---

### Edge Cases

- **Non-`.md` files inside a WP's task directory** (e.g., #5151 ask 3's "in-progress script")
  must be attributable to that WP the same as a `.md` file — ownership by directory convention is
  not restricted to a file extension.
- **Wholly untracked WP directories.** When a WP's task subdirectory has never been committed
  (e.g., the first `review-cycle-1.md` a verdict writes), *and its parent
  `kitty-specs/<slug>/tasks/` directory is already tracked* (the normal case once any WP's task
  file has been committed for the mission), `git status --porcelain` reports the *directory*
  itself (trailing slash, no filename) rather than the file inside it. Ownership determination
  must recognise this directory-only form, not only fully-qualified file paths — verified
  directly: a fresh untracked `kitty-specs/<slug>/tasks/WP01-foo/` with one new file inside,
  under an already-tracked `kitty-specs/<slug>/tasks/` directory, reports as
  `?? kitty-specs/<slug>/tasks/WP01-foo/` in porcelain output. (If no ancestor directory is
  tracked yet, git's porcelain output collapses further up the tree instead — e.g. to
  `?? kitty-specs/` — a degenerate bootstrap case already covered by the fail-closed fallback,
  not by this directory-only-form recognition.) This is the concrete mechanism behind
  kentonium3's Friction 2 report.
- **The moving WP's own directory** stays governed by existing behavior: its own task `.md` file
  is already benign (pre-existing `test_own_task_file_is_benign`); other uncommitted paths under
  its own directory are NOT exempted by this mission — a WP's own unstaged work must still be
  committed before it can move.
- **A dirty path matching no mission's WP-directory pattern at all** (a stray file directly
  under `kitty-specs/<slug>/`, or a path outside `kitty-specs/` entirely) is never attributable
  and always blocks — see Story 3.
- **A dirty path under a different mission's `kitty-specs/<other-slug>/tasks/WPxx-*/`** is not
  "this mission's WP business" — the ownership check is scoped to the *current* mission's
  `mission_slug` (already a parameter of `classify_dirty_paths`); a same-numbered WP in an
  unrelated mission must not be treated as an owner match.
- **Existing benign categories are unaffected.** Toolchain-generated churn (`meta.json`,
  encoding-provenance JSONL, `status.events.jsonl`/`status.json`), `.kittify/` paths, and
  `lanes.json` keep passing through their existing, wp_id-independent checks; this mission adds a
  new WP-scoped category, it does not touch those.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Cross-WP paths under another WP's task directory are benign | As an agent moving a WP, I want a dirty path under a different WP's `kitty-specs/<slug>/tasks/<WPxx>-*/` directory to not block my transition, so unrelated concurrent work doesn't false-block me. | High | Open | [build] | no — paired with the same-fixture positive control that the identical path blocks when WPxx *is* the WP being moved |
| FR-002 | Ownership is not restricted by file extension | As an agent, I want a non-`.md` file (e.g. a script) inside another WP's task directory to be recognised as that WP's residue, so the scoping isn't accidentally narrower than the reported #5151 ask-3 case. | High | Open | [build] | no |
| FR-003 | Wholly-untracked WP directories are attributable | As an agent, I want a WP task directory reported by git as a single untracked directory path (no filename) to still resolve to its owning WP, so a first-write review-cycle artifact (kentonium3's Friction 2) is correctly scoped. | High | Open | [build] | no |
| FR-004 | Unattributable dirty paths still block (fail-closed) | As a maintainer, I want a dirty path that cannot be attributed to any WP's task directory, and does not already match an existing benign category, to continue blocking the transition, so the guard never silently passes unrecognised dirty state. | High | Open | [ratchet] | no — paired with FR-001's positive control (same test module, opposite outcome) |
| FR-005 | Refusal message names the real owner or states none | As an agent reading a blocked-transition refusal, I want the guidance text to name the path's actual determined owner (the WP being moved, when its own residue is what blocks it) or explicitly state it is not attributable to a specific work package, instead of unconditionally asserting the WP being moved owns it regardless of which case applies. A blocking line is never attributed to a *different* WP — FR-001/FR-002/FR-003 already route any path owned by another WP into `benign`, so the only two reachable outcomes for a blocking line are "the moving WP itself" (FR-007) or "not attributable" (FR-004). When a single refusal's blocking list spans both outcomes (e.g. one path under the moving WP's own directory plus one unattributable path in the same `move-task` call), each blocking line in the guidance must carry its own owner attribution, not one shared header applied to the whole list. See User Story 2, Acceptance Scenario 3. | High | Open | [build] | no |
| FR-006 | Existing wp_id-blind `.md` task-file benign behavior is preserved | As a maintainer, I want the pre-existing tests `test_other_wp_task_files_are_benign` and `test_wp_task_file_other_double_digit_is_benign` (any WP's flat `tasks/WPxx-*.md` file is benign regardless of the moving WP) to keep passing unmodified in substance — this sub-behaviour was already correct, it simply becomes a special case of the new WP-scoped ownership check rather than a separate wp_id-blind rule. | Medium | Open | [folded] | yes — behavior is unchanged, only its underlying justification generalizes |
| FR-007 | Own-directory residue is not exempted | As a maintainer, I want a WP's own uncommitted, non-task-file residue under its own `kitty-specs/<slug>/tasks/<own-WPxx>-*/` directory to keep blocking that same WP's transition, so this mission narrows only cross-WP false positives, not a WP's own commit discipline. | Medium | Open | [ratchet] | no |
| FR-008 | Ownership check is scoped to the current mission | As an agent, I want the WP-directory ownership match to apply only within the mission currently being transitioned (`mission_slug`), so a same-numbered WP in an unrelated mission's `kitty-specs/` tree is never mistaken for an owner. | Medium | Open | [build] | no |
| FR-009 | Red-first regression coverage exists before the fix | Per charter ATDD-First discipline (C-011), a failing test reproducing each of the three reported occurrences (#5151 ask 3, #5159 item 4, kentonium3's Friction 2) exists and is committed before any implementation commit, and is shown RED on `main` and GREEN on the fix. This mission also adds NEW coverage for the pre-existing blocking-lines truncation ("... and N more") branch in `_validate_research_artifacts`'s guidance construction, since no test in `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` currently exercises it (verified: none of the three existing `_validate_research_artifacts` tests constructs more than one blocking path) — this is new coverage this mission adds, not pre-existing coverage being preserved (see SC-002). | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Guard stays fast | `classify_dirty_paths` / `_is_benign` ownership resolution adds no measurable per-call overhead beyond existing regex/string checks; `move-task` as a whole stays within the charter's <2s CLI operation budget for typical mission sizes. | Performance | Medium | Open |
| NFR-002 | No new leak surface | The corrected refusal message must not introduce an absolute-checkout-path leak (SK-223 precedent) — any path named in the message stays repo-relative, matching the existing "(not owned by {wp_id})" note's format. | Security/Hygiene | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Ownership module is out of bounds | The fix must NOT use or extend `src/specify_cli/ownership/` (`owned_files` frontmatter-driven ownership). `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md:223`'s "kitty-specs ownership ban" forbids a `code_change` WP from listing any `kitty-specs/` path in `owned_files` (enforced by `finalize-tasks --validate-only` as `INVALID_WP_OWNED_FILES_KITTY_SPECS`); since nearly every WP is `code_change`, that module structurally cannot answer "which WP owns this `kitty-specs/` bookkeeping path." The mechanism is the pre-existing, topology-independent directory-naming convention (`kitty-specs/<slug>/tasks/<WPxx>-*/` → owned by `WPxx`) already partially implemented in `_is_review_handoff_survivor_path`'s `wp_task_pattern`. | Technical | High | Open |
| C-002 | Implement phase is sequenced behind #5151 WP02 (hold LIFTED, operator ruling 2026-09-28) | **Superseding update (operator ruling 2026-09-28):** the operator lifted this constraint's implement-phase hold outright. Implementation on this mission proceeds now, off `main`, without waiting for sibling mission `lane-history-safe-handoff-5151-01M3JR6R`'s WP02 to land or be reviewed/approved first. The two missions' PRs are independent; whichever of the two merges second rebases onto the first (the shared file's edits land in different functions, so the residual conflict is small and localized). This replaces the prior sequencing bar below, which is retained as history, not as a current gate. — **Prior wording (history, superseded):** Design (spec/plan/tasks/analyze) may proceed now — it is file-agnostic — but the *implement* phase must not start until sibling mission `lane-history-safe-handoff-5151-01M3JR6R`'s WP02 ("Preserve refused edits with exact-path guidance") has landed or been reviewed/approved on its own branch. WP02's `owned_files` lists the same file and the same two test files this mission's blast radius touches (`tasks_parsing_validation.py` and its two test files), targeting a different function (`_check_kitty_specs_contamination` and neighbours, not `_validate_research_artifacts`). spec-kitty has no cross-mission dependency gate — the CLI will not block `implement`/`move-task` on another mission_id's WP status; this sequencing is a self-enforced orchestrator/operator discipline, not a CLI-level gate, and the orchestrator must manually verify WP02's lane state before starting this mission's implement phase, since nothing in the tooling enforces it automatically. Message-style harmonization between this mission's FR-005 refusal wording and whatever exact-path guidance convention WP02 introduces alongside it in the same file is a plan-level decision, deferred to plan.md — not ruled on here. See Clarifications Q1. | Process | High | Lifted (operator ruling 2026-09-28) |
| C-003 | Blast radius stays within the named surfaces | This mission touches only `src/specify_cli/review/dirty_classifier.py` (`_is_benign`, `_is_review_handoff_survivor_path`, `classify_dirty_paths`), `src/specify_cli/cli/commands/agent/tasks_parsing_validation.py` (`_validate_research_artifacts` and its message construction), and their test files (`tests/review/test_dirty_classifier.py`, `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py`, and `tests/specify_cli/cli/commands/agent/test_tasks.py` for the public route, per smallest-viable-diff and locality-of-change). No `.kittify/`, `lanes.json`, or ownership-module changes. | Technical | High | Open |

### Key Entities

- **WP Task Directory**: the path `kitty-specs/<mission_slug>/tasks/<WPxx>-<slug>/` (or the flat
  `tasks/<WPxx>-<slug>.md` file for missions that haven't materialized a directory yet). The
  pre-existing, topology-independent ownership source for this mission — a pure path-string
  convention, not read from `lanes.json` or any coordination structure.
- **Dirty Path Classification**: the existing `(blocking, benign)` partition
  `classify_dirty_paths` produces. This mission adds one new way a path can land in `benign`
  (attributable to a different WP) without changing the shape of the return value. Per-path
  ownership for a mixed-ownership blocking list (FR-005, User Story 2 Acceptance Scenario 3) must
  be resolved for each blocking path without diverging from `classify_dirty_paths`'s own
  blocking/benign partition, and without changing `classify_dirty_paths`'s return shape (its
  existing 2-tuple `(blocking, benign)` unpack is relied on at three call sites:
  `tasks_parsing_validation.py`, the `dirty_classifier.py` module docstring example, and
  `tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py`). The exact mechanism — a new
  sibling per-path ownership-lookup helper in `dirty_classifier.py`, or reusing the existing
  `_is_benign` predicate — is a plan-level implementation decision, deferred to plan.md
  (mirroring C-002/Clarifications Q1's treatment of message-style harmonization) — not ruled on
  here.
- **Ownership Attribution**: the determined owner of a *blocking* dirty path — either the `WPxx`
  being moved (its own residue, per FR-007) or "none determined" (not attributable to any WP, per
  FR-004) — now threaded into the refusal guidance instead of being hardcoded to the WP being
  moved regardless of which case applies. A blocking path's owner is never a *different* specific
  WP: FR-001/FR-002/FR-003 already route any path attributable to another WP's task directory
  into `benign`, so that outcome cannot reach this attribution step.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A red-first regression test exists for each of the three concretely reported
  occurrences (#5151 ask 3's non-`.md` cross-WP file, #5159 item 4's cross-WP review-cycle
  directory, kentonium3's Friction 2 wholly-untracked review-cycle-N.md), each shown RED against
  current `main` behavior and GREEN after the fix — [build] · no-op passable: no.
- **SC-002**: Every pre-existing test in `tests/review/test_dirty_classifier.py` and
  `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` (including
  `test_other_wp_task_files_are_benign`, `test_wp_task_file_other_double_digit_is_benign`, and
  `test_own_task_file_is_benign`) continues to pass unmodified in substance — [ratchet] · no-op
  passable: yes. (The blocking-lines truncation ("... and N more") branch has no pre-existing
  test coverage — see FR-009, which adds it as new coverage this mission contributes.)
- **SC-003**: A dirty path attributable to no WP still produces a blocking refusal in 100% of
  cases exercised by the test suite (fail-closed non-regression), paired in the same test module
  with the positive control that a same-mission other-WP path passes — [build] · no-op passable:
  no.
- **SC-004**: The refusal guidance text for a blocking path never hardcodes "owned by {wp_id}"
  when `{wp_id}` (the WP being moved) is not the determined owner — verified by a test asserting
  the guidance string content, not just the blocking/benign boolean — [build] · no-op passable:
  no.

## Compatibility & Reflexivity

This mission changes the guard that `move-task`'s lane-transition path depends on — including for
missions that are *currently* mid-flight, such as the live `lane-history-safe-handoff-5151-01M3JR6R`
mission itself (see Constraint C-002 on sequencing).

- **The guard becomes more precise, never less strict**, with one narrowly-scoped exception. A
  path that blocks today and is *provably* another WP's residue under
  `kitty-specs/<slug>/tasks/<WPxx>-*/` (per FR-001/FR-002/FR-003) is the only category that moves
  from blocking to benign. Every other path that blocks today keeps blocking after this fix —
  including a WP's own residue (FR-007) and any unattributable path (FR-004).
- **No mid-flight mission should observe a *new* block it did not see before this fix.** The
  change only removes false positives in the narrowly-scoped case above; it introduces no new
  classification of a previously-benign path as blocking.
- **Any WP that was wrongly blocked by another WP's residue before this fix should now proceed**
  once the fix lands, without any change to that WP's own behavior.
- Because `move-task`'s guard is shared infrastructure, this is a compatibility-relevant change
  for every in-flight mission using it, not only the missions that reported the defect — hence
  the sequencing decision in C-002/Clarifications Q1, and the requirement (SC-002) that no
  existing pinned test regresses.

## Related History (Ledger Context)

`SPEC-KITTY-LEDGER.md` records prior real-mission friction with this guard family. Each entry's
relationship to this mission's scope:

- **SK-114** (`record-analysis`'s dirty-tree guard blocks on its own side effects) — **precedent
  for a design choice**. Establishes that this guard family is deliberately fail-closed by
  design; the historical fix direction has always been "teach the guard to recognise a specific
  known-safe residue as benign," never "make unrecognised dirty state pass silently." FR-004 /
  Clarifications Q2's unowned-path behavior in this mission follows that same precedent
  directly.
- **SK-115** (`move-task --to approved` unreachable: the tool dirties the lane branch it then
  rejects) — **precedent for a design choice, and same failure family**. A different manifestation
  of the same class of bug (a guard reacting to residue it or another part of the tool produced,
  without the context to classify it correctly) — not this mission's blast radius (it concerns
  lane-branch `kitty-specs/` commits and sparse-checkout interactions, not WP-scoped attribution
  on the primary/root checkout), but confirms the family-wide pattern this mission's fix belongs
  to.
- **SK-223** (`feedback_path` persisted as an absolute checkout path, leaking the OS username) —
  **out of scope as a defect, but binding as a hygiene precedent**. Not a defect this mission
  fixes; NFR-002 exists specifically so this mission's corrected refusal message does not
  introduce a new instance of the same class of leak (any path named in the new guidance stays
  repo-relative).
- **SK-249** (`record-analysis`'s dirty-tree preflight makes the documented analyze fix-loop
  uncompletable by a fixer seat) — **explicitly out of scope**. Same guard *family* (a dirty-tree
  preflight blocking a legitimate transition) but a distinct command (`record-analysis`, not
  `move-task`) and a distinct root cause (the fix-loop's role assignment forces the fixer seat to
  either commit mid-loop or self-verify; not a WP-attribution defect). Not conflated with this
  mission's `dirty_classifier.py` / `tasks_parsing_validation.py` fix.

## Clarifications

### Session 2026-09-28

- Q: Given the same-file, same-test-files overlap with #5151's WP02 (currently in the tasks
  phase, not yet implementing), how should #5007 be sequenced relative to it? → A: **Design now,
  hold implement.** Run #5007's spec/plan/tasks now, but hold its implement phase until #5151's
  WP02 is approved, so #5007 goes second and rebases onto one known diff. Recorded as a binding
  sequencing constraint (C-002) that gates the *implement* phase only, not design. This
  sequencing is enforced by the orchestrator's own discipline only: spec-kitty's tooling has no
  cross-mission dependency gate that would block `implement`/`move-task` automatically on
  WP02's status — the orchestrator must check WP02's lane state itself.
  - **2026-09-28 (later same day) — operator ruling, hold LIFTED:** the operator lifted this
    implement-phase hold outright. Implementation proceeds now, off `main`, without waiting for
    #5151's WP02 to land or be reviewed/approved. The two missions' PRs are independent;
    whichever merges second rebases onto the first — the shared file's edits are in different
    functions, so the residual conflict is small and localized. See C-002's superseding update.
- Q: Should a dirty path that cannot be attributed to any specific WP be allowed to pass (silent
  success), or should it continue to block? → A: **Yes, unowned still blocks (fail-closed).**
  Only paths that provably belong to a different WP pass; everything else still refuses, now with
  correct attribution. Concretely: a dirty path under `kitty-specs/<slug>/tasks/<WPxx>-*/` for
  some WPxx other than the WP being moved → passes as benign; if the same `move-task` call's
  guidance also surfaces an informational note about that path, the note may mention WPxx, but
  this is never a *blocking* refusal line. A dirty path that does not match any WP's task
  directory (or matches the WP being moved itself, or an existing benign category) → still
  blocks, but the refusal message must state the path's ownership honestly (e.g. "not
  attributable to a specific work package") instead of falsely claiming the moving WP owns it. A
  blocking line's owner is thus always either the moving WP itself or "not attributable" — never
  a different, specific WP — see FR-005. Never a silent pass for an undetermined path.

## Assumptions

- The `kitty-specs/<mission_slug>/tasks/<WPxx>-*/` directory-naming convention is stable and
  already relied upon elsewhere in the codebase (`_is_review_handoff_survivor_path`'s
  `wp_task_pattern`); this mission generalizes an existing convention rather than introducing a
  new one.
- `mission_slug` is already threaded into `classify_dirty_paths`'s signature, so scoping the
  ownership check to the current mission (FR-008) does not require a new parameter.
- No topology-specific handling is required: because the ownership mechanism is a pure
  path-string convention, it is identical across `single_branch`, `lanes`, `coord`, and
  `lanes_with_coord` topologies.
