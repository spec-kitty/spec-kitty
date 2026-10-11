# Mission Specification: Governed ops never destroy or mis-report user content

**Mission Branch**: `fix/5964-5434-4796-govern-user-content`
**Created**: 2026-10-11
**Status**: Draft
**Input**: Point-fix layer of the #3129 ambient-write-boundary class. Three independent P1 defects where a package-owned / governed operation destroys the only copy of operator content, or reports a false verdict, and still exits 0: #5964 (`upgrade` untracks + commits a team's own `.agents/skills/**`), #5434 (lane worktrees never get the `.spec-kitty/` exclude, so a leftover review-lock trips `DirtyWorktreeError`), #4796 (orchestrator-api `merge_mission` runs its destructive-op guard only at post-merge cleanup, reporting a completed+pushed merge as `PREFLIGHT_FAILED`).

## User Scenarios & Testing *(mandatory)*

The three stories are independent seams with independent blast radii; each is a standalone, independently testable slice. They share only the motif "a governed operation must never destroy or mis-report operator content." They do **not** share a code seam: only Story 3 touches the #6020 residue/pre-mutation-preflight family; Stories 1 and 2 are separate surfaces.

### User Story 1 - Upgrade preserves a team's own agent skills (Priority: P1)

A team keeps its own repo-scoped agent skills under `.agents/skills/<name>/SKILL.md` (committed) in a project created before 3.2.5. Running `spec-kitty upgrade --yes` must not delete those skills. Today the 3.2.5 `agents_skills_gitignore_backfill` migration untracks the *entire* `.agents/skills/` tree (consulting neither skills manifest) and the upgrade auto-commit lands the deletion, so every teammate's ordinary `git pull` removes the files from disk — exit 0, no mention of the path.

**Why this priority**: Silent, pushed loss of operator-authored content that exists nowhere else once pulled. P1 data-loss.

**Independent Test**: A pre-3.2.5 project with a committed, non-`spec-kitty.*`, non-manifest `.agents/skills/team-review/SKILL.md`; run the migration/upgrade; assert the path stays in `git ls-files`, is not staged as a deletion, and is absent from the upgrade commit's deletions, while a genuinely spec-kitty-projected `spec-kitty.<command>/SKILL.md` is still untracked.

**Acceptance Scenarios**:

1. **Given** a tracked team skill `.agents/skills/team-review/SKILL.md` owned by neither `skills-manifest.json` nor `command-skills-manifest.json`, **When** the `agents_skills_gitignore_backfill` migration applies, **Then** that path remains tracked (`git ls-files` lists it; it is not staged `D`).
2. **Given** the same repo also contains a spec-kitty-projected `.agents/skills/spec-kitty.implement/SKILL.md`, **When** the migration applies, **Then** the projected path is untracked (spec-kitty-owned machine projection) but the team path is not.
3. **Given** the migration ran, **When** the upgrade auto-commit is produced, **Then** `git log --diff-filter=D origin/main..HEAD` contains no deletion of the team path.

---

### User Story 2 - Lane worktree reuse tolerates spec-kitty's own review-lock residue (Priority: P1)

Spec-kitty's own `.spec-kitty/review-lock.json` left in a lane worktree must not block reuse or crash recovery of that worktree. The FR-016 `.spec-kitty/` exclude is written to the per-worktree `info/exclude` (`.git/worktrees/<name>/info/exclude`), which git does not read; only the common-dir `.git/info/exclude` is honoured. So the leftover lock shows as untracked and `allocate_lane_worktree` refuses with `DirtyWorktreeError`.

**Why this priority**: A governed operation (review isolation) leaves its own residue that then fails-closed and strands the operator's lane. P1 reliability; blocks resume.

**Independent Test**: Allocate a lane worktree, drop `.spec-kitty/review-lock.json` into it, assert `git -C <wt> status --porcelain` is empty, and re-allocating (reuse + crash-recovery routes) does not raise `DirtyWorktreeError`. Assertions are on real `git status --porcelain` output, never on "the exclude file was written."

**Acceptance Scenarios**:

1. **Given** a newly allocated lane worktree, **When** `.spec-kitty/review-lock.json` exists in it, **Then** `git status --porcelain` for the worktree is empty.
2. **Given** a lane worktree with that leftover lock, **When** `allocate_lane_worktree` is re-invoked (reuse route), **Then** it returns the path without raising `DirtyWorktreeError`.
3. **Given** the worktree dir was removed but the branch survives (crash-recovery route) with the lock present, **When** allocation recovers it, **Then** no `DirtyWorktreeError` is raised.
4. **Given** an existing project created before this fix, **When** the backfill migration runs, **Then** `.spec-kitty/` is present in the common-dir `.git/info/exclude` and every worktree's `git status --porcelain` ignores the lock.

---

### User Story 3 - Orchestrator-api merge refuses unsafe worktrees before mutating (Priority: P1)

The orchestrator-api merge path must refuse an unsafe (dirty) lane worktree *before* any lane consolidation, target integration, done-stamping, or push — and never report a merge that actually completed as a failure. Today `orchestrator_api/consolidation.py::_execute_lane_merge` performs its first lane-worktree dirty check only at post-merge cleanup (`guarded_worktree_remove`), after all mutations and an optional `git push origin <target>`, then envelopes the refusal as `PREFLIGHT_FAILED` for a merge that has in fact landed.

**Why this priority**: Corrupts the verdict automation relies on — a completed, pushed merge is reported as a failed preflight, violating the path's NFR-001 ("on raise, nothing has mutated"); every retry fails identically while the mission is merged. P1 (verdict integrity on an automation contract).

**Independent Test**: Drive the real `consolidate_mission`/`_execute_lane_merge` entrypoint against a genuine repo with one untracked operator file in a lane worktree; assert exit 1 + `PREFLIGHT_FAILED`/`MERGE_UNSAFE_WORKTREE_DIRTY` AND the timing pins: target ref unchanged, WPs not stamped merged/done, no push occurred.

**Acceptance Scenarios**:

1. **Given** a lanes mission whose approved lane worktree holds one untracked non-ignored operator file, **When** `consolidate_mission` runs, **Then** it refuses with a `PREFLIGHT_FAILED` envelope carrying `MERGE_UNSAFE_WORKTREE_DIRTY`.
2. **Given** that refusal, **When** it is raised, **Then** the target branch ref is unchanged, no WP is stamped merged/done, and no `git push` occurred (NFR-001 upheld on the orchestrator path, at parity with the CLI path).
3. **Given** a clean lane worktree, **When** `consolidate_mission` runs, **Then** the pre-mutation preflight passes and the merge proceeds exactly as today.

### Edge Cases

- #5964: command skills (`.agents/skills/spec-kitty.<command>/SKILL.md`, stable prefix) vs pack/charter skills (manifest-recorded, config-variable namespace) — ownership must consult the stable command pattern **and** both manifests; a path-pattern alone cannot distinguish team from pack skills. The `.kittify/skills-manifest.json` file untrack itself is intended and stays.
- #5434: `exclude_from_git_index` early-returns if `.git/info/exclude` is absent, and no-ops if handed a worktree path (`.git` is a file) — the allocator must pass the main-repo root. The common-dir exclude is shared across all a repo's worktrees, so one migration write covers every existing worktree.
- #4796: worktree-retention in effect (`--keep-worktree`) skips the removal/dirty leg on the CLI path; the hoisted orchestrator preflight must gate on the same resolved retention so behaviour matches cleanup.

## Requirements *(mandatory)*

Delivery labels per tactic `acceptance-criteria-non-vacuity`: `[build]` = net-new fix behaviour pinned by a failing-first test; `no-op passable: no` = a do-nothing implementation fails the acceptance test.

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Upgrade untracks only spec-kitty-projected `.agents/skills/` paths | As a team, I want `spec-kitty upgrade` to keep our own committed `.agents/skills/**` so that an upgrade never deletes skills we authored. | High | Open | [build] | no |
| FR-002 | Team `.agents/skills` content is absent from the upgrade commit's deletions | As a teammate, I want a plain `git pull` after someone upgrades to preserve our team skills so that they are never removed from my disk. | High | Open | [build] | no |
| FR-003 | Lane worktrees honour a common-dir `.spec-kitty/` exclude on all allocation routes | As an operator resuming work, I want a leftover `.spec-kitty/review-lock.json` to be ignored so that worktree reuse and crash recovery do not refuse with `DirtyWorktreeError`. | High | Open | [build] | no |
| FR-004 | Migration backfills the `.spec-kitty/` common-dir exclude for existing projects | As an operator of a pre-existing project, I want `spec-kitty upgrade` to add the `.spec-kitty/` exclude to the shared `.git/info/exclude` so that already-created worktrees stop tripping on the lock. | High | Open | [build] | no |
| FR-005 | The dead per-worktree `.spec-kitty/` exclude writer is removed | As a maintainer, I want the writer that targets the unread `.git/worktrees/<name>/info/exclude` deleted so that the only remaining writer is the one git actually honours. | Medium | Open | [folded] | no |
| FR-006 | Orchestrator-api merge runs a pre-mutation safety preflight | As an external orchestrator, I want an unsafe lane worktree refused before any consolidation/integration/push so that a refusal truthfully means nothing mutated. | High | Open | [build] | no |
| FR-007 | A genuinely refused orchestrator merge still envelopes as `PREFLIGHT_FAILED`, now truthful | As an external orchestrator, I want the pre-mutation refusal to keep the existing `PREFLIGHT_FAILED` contract shape so that my handling is unchanged but the verdict is now honest. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No mutation on a safety refusal | On any safety refusal (upgrade untrack, lane-worktree dirty, orchestrator preflight), zero operator-authored paths are deleted/overwritten/committed-as-deleted and zero outward mutations (push) occur — asserted by pre/post `git ls-files` + ref capture, 0 differences. | Reliability | High | Open |
| NFR-002 | No completed merge reported as failure | A merge that completed is never enveloped as a failure; the orchestrator refusal occurs strictly before the first mutation (target ref, done-stamps, and origin all provably unchanged on refusal). | Correctness | High | Open |
| NFR-003 | Clean static gates | New/changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero issues; diff coverage ≥ 90%. No suppression added to pass. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical ownership authority | #5964 reuses the existing manifest-ownership authority (`skills/command_installer.py`, `skills/manifest.py`) to decide projected vs team paths. Do NOT fork a second predicate and specifically do NOT extend `coordination.coherence.is_self_bookkeeping_churn` to match `.agents/skills/**` (it feeds the consolidate/accept destructive-op guards and would widen the data-loss, not fix it). | Technical | High | Open |
| C-002 | Smallest viable diff / locality | #5434 removes only the dead per-worktree writer and its two call sites, not the larger `core/worktree.py` / `core/vcs` legacy cluster (that cleanup is a separate tracked follow-up). #4796 reuses the CLI `_pre_mutation_safety_preflight` (or extracts its lane-worktree leg) rather than writing a new check. | Technical | High | Open |
| C-003 | ATDD / red-first on observable state | Each fix lands a failing-first acceptance test (red on the WP base, green on the WP's final commit) asserting on real observable state — `git ls-files`, `git status --porcelain`, pre/post refs — never on "a file was written". No skip/xfail/quarantine; no retry-to-green. | Process | High | Open |
| C-004 | Terminology & gitignore-breadth scope | No new `feature*` identifiers (Mission canon). The separate "fresh `init` gitignores future team skills" breadth problem is OUT of scope and filed as a tracked follow-up; this mission fixes the untrack+commit data-loss only. | Technical | Medium | Open |

### Key Entities

- **Projected skill**: a `.agents/skills/` path spec-kitty itself installed — either a command skill (`spec-kitty.<command>/SKILL.md`, stable prefix) or a pack/charter skill recorded in a manifest. Machine-local; safe to untrack.
- **Team skill**: an operator-authored `.agents/skills/` path owned by no manifest and not matching the command pattern. User content; must never be untracked or deleted.
- **Common-dir git exclude**: `<git-common-dir>/.git/info/exclude` — the only `info/exclude` git honours for a worktree; shared across all of a repo's worktrees.
- **Pre-mutation safety preflight**: the CLI-path check (`consolidation/entry_preflight.py::_pre_mutation_safety_preflight`) that validates lane-worktree cleanliness and on-target predicates before any merge mutation; to be brought to parity on the orchestrator-api path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pre-3.2.5 project with a committed team `.agents/skills/team-review/SKILL.md` survives `spec-kitty upgrade --yes`: the path stays in `git ls-files`, the upgrade commit contains no deletion of it, and a simulated teammate pull keeps the file — [build] · no-op passable: no
- **SC-002**: A lane worktree carrying a leftover `.spec-kitty/review-lock.json` reports empty `git status --porcelain`, and `allocate_lane_worktree` reuse and crash-recovery routes complete without raising `DirtyWorktreeError`; the backfill migration adds `.spec-kitty/` to the common-dir exclude and is idempotent — [build] · no-op passable: no
- **SC-003**: An orchestrator-api merge with a dirty lane worktree refuses with `PREFLIGHT_FAILED` (`MERGE_UNSAFE_WORKTREE_DIRTY`) while the target ref is unchanged, no WP is stamped merged/done, and no push occurred; a clean worktree merges unchanged — [build] · no-op passable: no
- **SC-004**: All three fixes land with zero `ruff`/`mypy --strict` findings and ≥90% diff coverage, no new suppressions, and the dead per-worktree exclude writer removed from the dead-symbol allowlist — [build] · no-op passable: no
