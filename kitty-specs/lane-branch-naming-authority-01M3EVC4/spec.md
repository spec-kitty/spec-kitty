# Mission Specification: Lane Branch Naming Authority

**Mission Branch**: `kitty/mission-lane-branch-naming-authority-01M3EVC4` (coordination); planning on `claude/charter-load-mission-q9ajcz`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Issue #5108 — lane branch names are derived two ways during merge (with vs without the mission identity); converge on one naming authority.

## Intent Summary (confirmed 2026-09-26)

- **Primary actor**: an operator running `spec-kitty merge` (fresh or `--resume`) on a Mission whose lanes were created under one naming form while its lanes manifest carries a mission identity — a legacy `NNN-slug` Mission with a backfilled ULID, a Mission whose slug embeds a mid8 that differs from its identity, or a manifest carrying an invalid identity.
- **Trigger → outcome**: the merge runs; every merge stage (lane consolidation, the reconciliation claim, pre-interrupt lane-tip capture, the pre-mutation safety preflight, and post-merge cleanup) resolves the lane branch and worktree that actually exist, so a legitimate merge completes instead of being refused with "no approved lane resolved any commits".
- **Invariant**: exactly one authority names a lane's branch and worktree — the same authority that creates them. Existing branches are never renamed. No caller chooses between naming forms, and no stage probes several candidate names to see which exists.
- **Architecture decision** (operator, pre-spec checkpoint): extend the existing creation-side lane-placement authority (Option A); do not persist per-lane branch names in the lanes manifest and do not move naming into a lower layer.
- **Absorbed scope**: FR-010 of mission `terminus-merge-integrity-01M380R6` (stable, origin-aware lane identity). It has since landed on the mainline; this mission preserves and re-verifies it rather than re-implementing it.
- **Audited scope**: whether the mission-branch / coordination-branch naming drifts the same way.
- **Folded scope (operator, 2026-09-26)**: #5113 — recording a Decision Moment on a freshly created coordination-topology Mission partially writes the ledger and then fails because the coordination worktree is not yet materialized, and the advertised remedy cannot materialize it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merge a backfilled legacy Mission (Priority: P1)

An operator has a legacy Mission (slug without an embedded mid8, e.g. `057-foo`) whose identity was backfilled and whose tasks were re-finalized, so its lanes manifest now records the ULID. Its lanes were created — and still exist — under the legacy name. The operator approves every work package and runs `spec-kitty merge`.

**Why this priority**: this is the reported defect (#5108): the merge is refused for a reason the operator cannot fix, blocking delivery of approved work.

**Independent Test**: build that Mission through the real lane-creation path, approve its work packages, run the merge entry point; assert the merge completes and every approved lane's commits are attributed and reachable from the target.

**Acceptance Scenarios**:

1. **Given** a legacy-slug Mission with a backfilled identity and approved lanes created under the legacy name, **When** the operator runs `spec-kitty merge`, **Then** the reconciliation claim resolves each approved lane's commits and the merge completes.
2. **Given** the same Mission, **When** the merge reaches cleanup, **Then** the lane branches and worktrees that were actually created are the ones removed (or retained per the retention policy) — none is left orphaned and none is silently skipped.
3. **Given** the same Mission, **When** the pre-mutation safety preflight runs, **Then** it inspects the lane worktrees that actually exist (a dirty lane worktree is detected, not skipped).

---

### User Story 2 - Resume an interrupted merge safely (Priority: P1)

An operator's merge was interrupted. On `spec-kitty merge --resume`, the resume anchors (captured pre-interrupt lane tips) are resolved against the same lane names consolidation uses.

**Why this priority**: today the tip capture can come back empty for divergent Missions, silently disarming the resume compare-and-swap guard — an integrity risk, not only a liveness one.

**Independent Test**: interrupt a merge of a divergent-slug Mission after tip capture; resume; assert tips were captured for every non-canceled lane and the resume is anchored to them.

**Acceptance Scenarios**:

1. **Given** a divergent-slug Mission whose merge was interrupted after lane-tip capture, **When** the operator resumes, **Then** every non-canceled lane has a captured tip and the resume proceeds anchored to it.
2. **Given** a persisted merge state whose lane-tip record is empty while the Mission has non-canceled lanes (e.g. captured by an older release), **When** the operator resumes, **Then** the resume refuses fail-closed with a message naming the remedy (`spec-kitty merge --abort`, then a fresh merge) — it never proceeds unanchored.

---

### User Story 3 - The defect class cannot recur (Priority: P2)

A contributor adds new code that builds or matches a lane branch or worktree name by hand, or passes a naming-form choice.

**Why this priority**: the split existed because naming could be composed at any call site; closing it by construction prevents the next divergence.

**Independent Test**: inject a synthetic hand-rolled lane-name composition (and, separately, a hand-rolled lane-name matcher) into a scanned source file; the architectural gate goes red naming the site.

**Acceptance Scenarios**:

1. **Given** the gate and its frozen baseline, **When** a new site composes a lane branch/worktree name outside the naming authority, **Then** the gate fails naming the file and function.
2. **Given** the gate, **When** a new site matches or parses lane names with its own pattern outside the naming module, **Then** the gate fails.
3. **Given** the gate's self-test, **When** it mutates a scanned file with a synthetic offender, **Then** the gate reports red (the gate is non-vacuous).

---

### User Story 4 - Unaffected Missions behave exactly as before (Priority: P1)

Operators with modern Missions (mid8 embedded in the slug) and legacy Missions without an identity see no change in branch or worktree names, merge behavior, or lane identity across re-finalize.

**Independent Test**: existing byte-identity naming goldens, lane-identity tests (FR-010), and merge suites stay green unchanged.

**Acceptance Scenarios**:

1. **Given** a modern Mission, **When** lanes are created and merged, **Then** branch and worktree names are byte-identical to today's.
2. **Given** a Mission whose work package is removed and tasks re-finalized, **When** lanes are recomputed, **Then** surviving lanes keep their ids and a fresh lane prefers an existing `origin/<lane>` (FR-010 preserved).

### User Story 5 - Record decisions on a fresh coordination Mission (Priority: P2)

An operator runs `/spec-kitty.specify` on a Mission created with the coordination topology and opens/resolves the first Decision Moment before any coordination write has happened.

**Why this priority**: the canonical specify flow cannot be followed as written on any fresh coordination Mission; the partial write and misleading remedy push operators into improvised workarounds and split the decision ledger (#5113).

**Independent Test**: create a coordination-topology Mission; run `decision open` then `decision resolve`; assert both succeed, the decision and its events land together on the surfaces the ledger is read from, and nothing is left half-written.

**Acceptance Scenarios**:

1. **Given** a fresh coordination-topology Mission with no coordination worktree, **When** the operator opens a Decision Moment, **Then** the command succeeds and returns the `decision_id`, with the ledger entry and its event recorded consistently.
2. **Given** a condition under which recording cannot proceed, **When** the operator opens or resolves a Decision Moment, **Then** the command fails before writing anything.
3. **Given** the unmaterialized-coordination error is shown anywhere, **When** the operator follows its remedy text, **Then** that remedy actually materializes the coordination worktree.

### Edge Cases

- A lanes manifest whose identity is not a valid ULID (e.g. equal to the slug) — lane naming must not depend on it; the merge must still resolve the created lanes.
- A slug whose embedded mid8 differs from the Mission's identity mid8 — lane naming must match what creation produced.
- The planning lane (`lane-planning`) resolves to the planning base branch, not a lane branch — unchanged.
- Canceled lanes have no tip; they must not trigger the empty-tip refusal.
- Retention policy (`retain_branches` / `retain_worktrees`) must act on the resolved (actually created) names.
- Doctor, sparse-checkout, live-work and commit-guard surfaces must recognize lane worktrees/branches of every supported grammar that creation produces.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Single lane naming authority | As an operator, I want every Spec Kitty surface to obtain a lane's branch name and worktree location from the one authority that creates them, so that no stage looks up a name that was never created. | High | Open |
| FR-002 | No naming-form choice at call sites | As a maintainer, I want callers to be unable to select between naming forms (with/without Mission identity) for lane branches and worktrees, so that a divergent form cannot be requested by construction. | High | Open |
| FR-003 | Reconciliation claim uses the authority | As an operator, I want the merge reconciliation claim to attribute each approved lane's commits using the authority-resolved branch, so that a legitimate merge of a backfilled legacy Mission is not refused (#5108). | High | Open |
| FR-004 | Lane-tip capture uses the authority | As an operator, I want pre-interrupt lane-tip capture to resolve lanes through the authority, so that every non-canceled lane has a captured tip. | High | Open |
| FR-005 | Resume refuses an unanchored tip set | As an operator, I want `merge --resume` to refuse, naming `merge --abort` as the remedy, when the persisted lane-tip record is empty while non-canceled lanes exist, so that a resume never proceeds with its compare-and-swap guard silently disarmed. | High | Open |
| FR-006 | Safety preflight and cleanup use the authority | As an operator, I want the pre-mutation safety preflight and post-merge cleanup (including retention decisions and orchestrator/discard cleanup) to act on the authority-resolved worktrees and branches, so that dirty worktrees are detected and no created lane branch is orphaned. | High | Open |
| FR-007 | Retire the dual-name probe | As a maintainer, I want the lifecycle path that probes several candidate lane names and keeps whichever exists removed in favor of the authority, so that there is no third naming strategy masking the split. | Medium | Open |
| FR-008 | Lane-name matching through the naming module | As a maintainer, I want every surface that matches or parses lane branch/worktree names (doctor checks, sparse-checkout, live-work bindings, commit guard, stale-lane guidance) to use the naming module's parsers, so that recognition agrees with creation for every supported grammar. | Medium | Open |
| FR-009 | Non-vacuous architectural gate | As a maintainer, I want an architectural gate that fails when lane branch/worktree names are composed or matched outside the naming authority, with a concrete frozen baseline, a shrink-only allowlist, and a self-mutation test, so that the defect class is closed by construction. | High | Open |
| FR-010 | Preserve stable, origin-aware lane identity | As an operator, I want lane ids to stay stable across re-finalize and fresh lanes to prefer an existing `origin/<lane>`, so that the previously landed lane-identity guarantees (absorbed from `terminus-merge-integrity-01M380R6` WP04) remain intact. | High | Open |
| FR-011 | Mission/coordination branch naming audit | As a maintainer, I want the mission-branch and coordination-branch naming audited for the same identity-form split; if the same defect class is present it is converged under this mission, otherwise a follow-up is filed with evidence. | Medium | Open |
| FR-013 | Decision recording on a fresh coordination Mission | As an operator, I want `decision open` / `decision resolve` to succeed on a coordination-topology Mission whose coordination worktree is not yet materialized — or fail before any write — so that a Decision Moment is never half-recorded (#5113). | Medium | Open |
| FR-014 | Truthful unmaterialized-coordination remedy | As an operator, I want the unmaterialized-coordination error to name a remedy that actually materializes the coordination worktree, so that following the tool's own advice unblocks me (#5113). | Medium | Open |
| FR-012 | Red-first regressions for divergent Missions | As a maintainer, I want regression tests — unit and end-to-end through the merge entry point — for a legacy-slug Mission with a backfilled identity, a mismatched-mid8 slug, and an invalid manifest identity, each shown failing before the fix. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Name stability | 100% of existing byte-identity naming goldens pass unchanged; zero existing lane branches or worktrees are renamed. | Compatibility | High | Open |
| NFR-002 | Complexity ceiling | Every touched function stays at cyclomatic complexity ≤ 15 (ruff C901 / Sonar S3776). | Maintainability | High | Open |
| NFR-003 | Gate floor | The architectural gate's frozen baseline count is ≤ the offender count measured at mission start and is 0 for compose sites in the merge, lanes and workspace subsystems at mission close. | Maintainability | High | Open |
| NFR-004 | Change coverage | Diff coverage on changed lines ≥ 90% (repository diff-cover gate). | Quality | High | Open |
| NFR-005 | Static checks | Zero new ruff, ruff-format or mypy findings; no new suppressions. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Extend, don't duplicate | The authority is the existing creation-side lane-placement authority in the lanes subsystem, extended; no new competing naming authority is introduced (charter: single canonical authority). | Technical | High | Open |
| C-002 | No manifest schema change | No per-lane branch-name field is added to the lanes manifest in this mission (Option B explicitly not chosen). | Technical | High | Open |
| C-003 | Layer direction | The naming authority stays in `specify_cli`; no new upward imports and no growth of the shrink-only outbound ledgers. | Technical | High | Open |
| C-004 | No resolver fallbacks | No read-time legacy-compat fallback or multi-candidate probing is introduced (ADR `2026-07-01-1`). | Technical | High | Open |
| C-005 | Legacy retirement not decided here | The tension with dropping pre-3.2.x legacy Mission support (see #2463) is recorded, not decided; this mission keeps legacy Missions working. | Business | Medium | Open |
| C-006 | Out of scope | Merge-marker/state write-ordering (see #5111), 3-way content attribution (see #5053), tag-collision rev-parse (see #5058), and mid8 legibility (see #4681) are not addressed. | Business | Medium | Open |

### Key Entities

- **Lane**: an execution lane of a Mission; has a stable lane id, a branch, and a worktree location.
- **Lanes manifest**: the per-Mission record of lanes, their work packages, the Mission branch and the Mission identity.
- **Lane naming authority**: the single place that decides a lane's branch name and worktree location — the same decision used at lane creation.
- **Pre-interrupt lane tips**: the persisted per-lane commit anchors a resumed merge compares against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A backfilled legacy-slug Mission, a mismatched-mid8 Mission and an invalid-identity Mission each merge successfully end to end (3/3), where today all three are refused.
- **SC-002**: 0 lane branches or worktrees are left orphaned after a successful merge of each divergent Mission shape.
- **SC-003**: 0 call sites outside the naming authority compose lane branch/worktree names in the merge, lanes and workspace subsystems; the gate goes red on 100% of injected synthetic offenders.
- **SC-004**: 100% of existing naming goldens and lane-identity (FR-010) tests pass unchanged.
- **SC-006**: On a fresh coordination Mission, 100% of `decision open` / `resolve` invocations either complete fully or write nothing; 0 half-recorded decisions.
- **SC-005**: A resume with an unanchored lane-tip record refuses in 100% of cases and names the remedy.

## Assumptions

- Lane branches are only ever created through the creation-side placement authority, in the legacy/slug form; no supported path creates mid8-form lane branches (to be re-verified during planning).
- Backfill does not rewrite the lanes manifest; the identity reaches it on the next finalize.

## Traceability

- Addresses: #5108, #5113.
- Context: see #5045 (discovery), see #5023 (decision-ledger dual partition, related to #5113 — not fully resolved here), see mission `nightly-red-remediation-01M3EP85` (fixture re-pin), see mission `terminus-merge-integrity-01M380R6` (FR-010 origin).
