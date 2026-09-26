# Tasks: Coordination branch remote-existence probe (#4979)

**Mission**: coord-branch-remote-probe-01M3F6M7
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Three work packages in a defense-in-depth chain. **WP01 is the root** — it fixes the single
canonical probe (closing the class at source) and extracts the shared remote-lookup primitive
that WP02 and WP03 consume. WP02 (doctor belt-and-suspenders) and WP03 (implement
defense-in-depth) depend on WP01 and are independent of each other. Owned-file sets are
disjoint (no-overlap finalize gate).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED-first #4979 regression: single-branch clone, remote-only coord branch → probe reports absent (RED through `status emit` refusal / doctor NEVER_CREATED); read-path fail-closed assertion | WP01 | |
| T002 | Extract shared tri-state remote-branch-lookup primitive (`git/remote_probes.py`): iterate configured remotes, bounded `timeout=`, `GIT_TERMINAL_PROMPT=0` + SSH BatchMode, memoized; returns `{HIT, CLEAN_MISS, ERROR, NO_REMOTE}` | WP01 | |
| T003 | Teach `_coord_branch_exists` to consult the primitive AFTER the local-head + `refs/remotes/` fast paths; map `HIT\|ERROR ⇒ present`, `CLEAN_MISS\|NO_REMOTE ⇒ absent`; regression pins "no ls-remote when refs/remotes hits" | WP01 | |
| T004 | Refactor the existing duplicate `_branch_resolvable` (`mission_type.py`) onto the shared primitive (fail-toward-false); add its missing `timeout=` | WP01 | |
| T005 | Fetch-first remote-only guidance on the emit-refusal path (`CoordinationBranchDeleted`/doctor hint branch on local-head vs remote-only); verify the read path raises `CoordinationWorktreeUnmaterialized` (never silent-empty) | WP01 | |
| T006 | Blast-radius verify (coordination/, missions/, migration/test_backfill_topology*, mission_runtime/test_write_target_degrade_selfmat) green; ruff/format/mypy on touched files; tracer append | WP01 | |
| T007 | RED-first #4979 regression: a `COORDINATION_WORKTREE_NEVER_CREATED` finding for a remote-present branch → `doctor coordination --fix` flattens `meta.json` (RED) | WP02 | |
| T008 | Add remote re-verify guard in `_fix_never_created_branches` (consume WP01's primitive) — skip flatten + actionable message when the branch is present on any remote; genuine-deletion path unchanged | WP02 | |
| T009 | Blast-radius verify (test_doctor_coordination, test_coordination_doctor) green; ruff/format/mypy; tracer append | WP02 | |
| T010 | RED-first #4979 regression: uncommitted `meta.json` demotion rides into `implement`'s planning-artifact auto-commit to the target branch (RED) | WP03 | |
| T011 | Add the demotion predicate + REFUSE at the staging DECISION seam (`detect_structural_planning_changes`/`resolve_planning_artifact_staging`); untracked/exit-128 ⇒ ALLOW; corrupt ⇒ REFUSE | WP03 | |
| T012 | Blast-radius verify (test_implement*, test_implement_writeside, test_implement_placement_routing) green; ruff/format/mypy; tracer append | WP03 | |

## Work Packages

### WP01 — Remote-existence probe + shared primitive (root)

**Goal**: `_coord_branch_exists` consults the remote authority via ONE shared tri-state
primitive after the local fast paths, so a coordination branch that lives only on a remote
(single-branch/shallow/CI/pruned checkout) is recognised as present — closing the flatten
defect at its source for all three probe consumers (read path, doctor, backfill). The
existing duplicate `_branch_resolvable` is refactored onto the same primitive.
**Priority**: P1 (anchor). **Execution mode**: code_change · **Rigour**: CORE (fail-closed
git-topology seam; #4959/#4970 tiered rigour).
**Independent test**: T001's regression is RED on the mission base (probe reports absent for a
remote-only branch → `status emit` refused / doctor emits NEVER_CREATED) and GREEN after; the
`refs/remotes`-hit fast path performs zero ls-remote (T003); origin-less DELETED tests and the
write-gate self-materialization tests stay green.

**Included subtasks**: T001, T002, T003, T004, T005, T006

**Dependencies**: none.
**Risks**: tri-state discrimination is the single most likely place to reintroduce the
data-loss flatten or break FR-002 — a reachable clean-miss (exit 0 empty) must NOT be
conflated with an unreachable error, and zero-remotes must keep local authority. C-002:
do NOT add remote-awareness to `_coord_branch_is_local_head` / `coord_branch_has_committed_artifact`.

**Prompt**: [tasks/WP01-remote-existence-probe.md](./tasks/WP01-remote-existence-probe.md)

### WP02 — Doctor flatten remote re-verification (belt-and-suspenders)

**Goal**: `_fix_never_created_branches` re-verifies against the remote (via WP01's primitive)
before the destructive `flatten_coordination_metadata`; a branch present on any remote is
never flattened — an independent last line of defence.
**Priority**: P1. **Execution mode**: code_change · **Rigour**: CORE.
**Independent test**: T007's regression is RED on the mission base (a NEVER_CREATED finding
for a remote-present branch flattens `meta.json`) and GREEN after (flatten skipped, `meta.json`
unchanged, message printed).

**Included subtasks**: T007, T008, T009

**Dependencies**: WP01 (consumes the shared remote-lookup primitive).
**Risks**: must not regress the genuine-deletion flatten (branch gone everywhere still flattens).

**Prompt**: [tasks/WP02-doctor-flatten-remote-reverify.md](./tasks/WP02-doctor-flatten-remote-reverify.md)

### WP03 — Implement auto-commit demotion guard (defense-in-depth)

**Goal**: `implement`'s planning-artifact staging REFUSEs (deterministically, never silently)
when the uncommitted `meta.json` is a topology demotion (`coordination_branch` non-null at
HEAD → absent/null in the working copy), so a flatten cannot propagate to the whole team
through an ordinary `implement`.
**Priority**: P2. **Execution mode**: code_change · **Rigour**: CORE.
**Independent test**: T010's regression is RED on the mission base (the demotion rides into the
`chore: planning artifacts` commit) and GREEN after (REFUSE with actionable message); an
untracked meta.json (exit-128) is ALLOWED; an ordinary non-demoting meta.json edit commits.

**Included subtasks**: T010, T011, T012

**Dependencies**: WP01 (consumes routing/primitive helpers).
**Risks**: must not false-refuse an ordinary meta.json edit or a legitimate first commit
(untracked). Hook the staging DECISION seam, not a parallel commit gate.

**Prompt**: [tasks/WP03-implement-demotion-guard.md](./tasks/WP03-implement-demotion-guard.md)

## Issue Matrix

| Issue | Verdict | Owning WP | Notes |
|-------|---------|-----------|-------|
| #4979 | in-mission | WP01 (root) + WP02 + WP03 | Three-tier fix; WP01 closes the class at source, WP02/WP03 are defense-in-depth |

See [spec.md](./spec.md) for the full requirement set and acceptance scenarios.
