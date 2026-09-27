# Mission Specification: Lane Branch Naming Authority

**Mission Branch**: `kitty/mission-lane-branch-naming-authority-01M3EVC4` (coordination); planning on `claude/charter-load-mission-q9ajcz`
**Created**: 2026-09-26
**Status**: Draft (rev 3 — research adjudications ADJ-1..6 folded; see research.md)
**Input**: Issue #5108 — lane branch names are derived two ways during merge (with vs without the mission identity); converge on one naming authority. Folded: #5113.

## Intent Summary (confirmed 2026-09-26)

- **Primary actor**: an operator running `spec-kitty merge` (fresh or `--resume`) on a Mission whose lanes were created under one naming form while its lanes manifest carries a mission identity — a legacy `NNN-slug` Mission with a backfilled ULID, a Mission whose slug embeds a mid8 that differs from its identity, or a manifest carrying an invalid identity.
- **Trigger → outcome**: the merge runs; every merge stage (lane consolidation, the reconciliation claim, pre-interrupt lane-tip capture, the pre-mutation safety preflight, and post-merge cleanup) resolves the lane branch and worktree that were created, so a legitimate merge completes instead of being refused with "no approved lane resolved any commits".
- **Invariant**: exactly one authority names a lane's branch and worktree — the same authority that creates them. Existing branches are never renamed. No caller chooses between naming forms, and no stage probes several candidate names to see which exists.
- **Architecture decision** (operator, pre-spec checkpoint): extend the existing creation-side lane-placement authority (Option A); do not persist per-lane branch names in the lanes manifest and do not move naming into a lower layer.
- **Absorbed scope**: FR-010 of mission `terminus-merge-integrity-01M380R6` (stable, origin-aware lane identity). It has since landed on the mainline; this mission preserves and re-verifies it rather than re-implementing it.
- **Audited scope** (operator: audit in scope): mission-branch / coordination-branch naming. Post-spec audit verdict: the **mission branch** recorded in the lanes manifest drifts the same way (re-finalize recomputes it with the identity, e.g. `kitty/mission-057-foo` → `kitty/mission-foo-<mid8>`, a branch that was never created) — **in scope (FR-011)**. The **coordination branch** is minted once at create time and recorded in `meta.json`; legacy Missions have none — **audited clean**.
- **Folded scope** (operator, 2026-09-26): #5113 — recording a Decision Moment on a freshly created coordination-topology Mission partially writes the ledger and then fails because the coordination worktree is not yet materialized, and the advertised remedy cannot materialize it. Cleanly separable from the naming work; delivered as an independent slice with no dependency on it.

## Domain Language

| Term | Meaning in this mission | Avoid |
|------|------------------------|-------|
| **Lane naming authority** | The single decision that yields a lane's branch name and worktree location from the lane's **creation input** (the Mission slug recorded for the lane and the lane id). The Mission identity (ULID/mid8) is **not** an input to lane naming. | "resolver" (overloaded), "naming helper" |
| **Naming form / grammar** | One of the lane-name shapes creation produces for a slug: legacy numbered (`NNN-slug`), plain legacy (`slug`), and mid8-suffixed (`slug-<mid8>`). The form follows from the slug alone. | "mid8 form" as a caller choice |
| **Created name** | The name deterministically recomposed from the creation input — never discovered by asking git which candidate exists. | "actual name", "resolved name" |
| **Probe** (forbidden) | Choosing the name to operate on by testing several candidates for existence. | — |
| **Discover** (allowed) | Enumerating existing lane branches/worktrees for diagnosis or recovery, recognizing them only through the naming authority's parsers. | — |
| **Compose site / match site** | Code that builds a lane branch/worktree name, or recognizes/parses one, from the lane tokens (`kitty/mission-`, `-lane-`). Operator-facing prose and messages are neither. | — |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merge a divergent-shape Mission (Priority: P1)

An operator has a Mission whose lanes were created under the slug-determined name while its lanes manifest records a Mission identity that yields a different name: (a) a legacy `057-foo` Mission with a backfilled ULID and re-finalized tasks; (b) a slug embedding a mid8 that differs from the identity's; (c) a manifest identity that is not a valid ULID — both ≥ 8 characters (yields a bogus name today) and < 8 characters (crashes today). The operator approves every work package and runs `spec-kitty merge`.

**Why this priority**: this is the reported defect (#5108): the merge is refused (or crashes) for a reason the operator cannot fix.

**Independent Test**: build each shape **through the real lane-creation path** (never by composing branch names in the fixture with the code under test), approve, run the merge entry point; assert the merge completes and every approved lane's commits are attributed and reachable from the target.

**Acceptance Scenarios**:

1. **Given** each divergent shape with approved lanes created by the creation authority, **When** the operator runs `spec-kitty merge`, **Then** the reconciliation claim attributes each approved lane's commits and the merge completes — no refusal, no traceback.
2. **Given** a divergent shape with one canceled lane and one surviving approved lane, **When** the merge runs, **Then** the canceled lane is excluded and the survivor is attributed.
3. **Given** an approved, non-canceled lane whose created branch does not exist in git, **When** the merge runs, **Then** it refuses with a message naming that branch — never an empty commit set that is reported generically.
4. **Given** a divergent shape with a dirty lane worktree, **When** the pre-mutation safety preflight runs, **Then** the dirty worktree is detected and the merge refuses.
5. **Given** a successful merge of a divergent shape, **When** cleanup runs, **Then** every created lane branch and worktree is removed (or retained per the retention policy) — none is orphaned.

---

### User Story 2 - Resume an interrupted merge safely (Priority: P1)

An operator's merge was interrupted. On `spec-kitty merge --resume`, the resume anchors (captured pre-interrupt lane tips) are keyed by the same created names consolidation uses.

**Why this priority**: today the tip capture silently returns nothing for divergent Missions, disarming the resume compare-and-swap guard — an integrity risk.

**Independent Test**: capture tips for a divergent-shape Mission; resume with persisted records of different shapes; assert anchoring or refusal as below.

**Acceptance Scenarios**:

1. **Given** a divergent-shape Mission, **When** lane tips are captured, **Then** every non-canceled, non-planning lane has a tip keyed by its created branch name.
2. **Given** a persisted lane-tip record in which any non-canceled, non-planning lane has no tip under its created branch name (empty, partial, or keyed under another form by an older release), **When** the operator resumes, **Then** the resume refuses fail-closed naming the remedy (`spec-kitty merge --abort`, then a fresh merge).
3. **Given** a Mission whose only lanes are canceled or the planning lane, **When** the operator resumes, **Then** the refusal in scenario 2 does not trigger.

---

### User Story 3 - Re-finalize keeps the recorded Mission branch (Priority: P1)

An operator backfills a legacy Mission's identity and re-runs `finalize-tasks`.

**Why this priority**: re-finalize today rewrites the manifest's Mission branch to a name that was never created, so later implement/merge steps target a phantom branch.

**Independent Test**: finalize a legacy Mission, backfill its identity, re-finalize; assert the manifest's Mission branch is unchanged and implement/merge use it.

**Acceptance Scenarios**:

1. **Given** a finalized legacy Mission whose identity is then backfilled, **When** tasks are re-finalized, **Then** the lanes manifest's Mission branch is byte-identical to before.
2. **Given** a first-time finalize of any Mission, **When** lanes are computed, **Then** the Mission branch name is unchanged from today's behaviour, and lane creation creates exactly that recorded branch.

---

### User Story 4 - The defect class cannot recur (Priority: P2)

A contributor adds code that composes or matches lane names by hand, or passes a naming-form choice.

**Independent Test**: inject a synthetic offender of each idiom into a scanned file; the gate goes red naming the site.

**Acceptance Scenarios**:

1. **Given** the gate and its recorded baseline, **When** a new compose site appears outside the naming authority anywhere under `src/specify_cli/`, **Then** the gate fails naming the file and function.
2. **Given** the gate, **When** a new match site appears outside the naming authority, **Then** the gate fails.
3. **Given** the public lane-naming surface, **When** inspected, **Then** it offers no way to request a naming form (no identity parameter for lanes).
4. **Given** the gate's self-test, **When** it injects a synthetic offender, **Then** the gate reports red.

---

### User Story 5 - Unaffected Missions behave exactly as before (Priority: P1)

**Independent Test**: existing byte-identity naming goldens, lane-identity tests (FR-010), and merge/lanes suites stay green unchanged.

**Acceptance Scenarios**:

1. **Given** a modern Mission, **When** lanes are created and merged, **Then** branch and worktree names are byte-identical to today's.
2. **Given** a Mission whose work package is removed and tasks re-finalized, **When** lanes are recomputed, **Then** surviving lanes keep their ids and a fresh lane prefers an existing `origin/<lane>` (FR-010 preserved).

---

### User Story 6 - Record decisions on a fresh coordination Mission (Priority: P2)

An operator runs `/spec-kitty.specify` on a Mission created with the coordination topology (coordination branch present, coordination worktree absent) and opens/resolves the first Decision Moment.

**Why this priority**: the canonical specify flow cannot be followed as written on any fresh coordination Mission (#5113).

**Independent Test**: create a Mission through the real `mission create` (coordination branch present, worktree absent); run `decision open` then `decision resolve`.

**Acceptance Scenarios**:

1. **Given** a fresh coordination Mission with no coordination worktree, **When** the operator opens a Decision Moment, **Then** the coordination worktree is materialized first, the command returns the `decision_id`, and `decision list` shows the entry.
2. **Given** materialization itself fails, **When** the operator opens or resolves a Decision Moment, **Then** the command fails and the decision index, decision artifact and status-events files are byte-identical to before.
3. **Given** the unmaterialized-coordination error is shown, **When** the operator runs the remedy command it names, **Then** the coordination worktree exists afterwards.

### Edge Cases

- Manifest identity not a valid ULID: ≥ 8 characters and < 8 characters — neither may affect lane naming, and neither may raise.
- Slug embedding a mid8 that differs from the identity's mid8.
- The planning lane (`lane-planning`) resolves to the planning base branch — unchanged, and exempt from tip-anchoring refusal.
- Canceled lanes have no tip and are exempt from the refusal.
- Retention policy (`retain_branches` / `retain_worktrees`) acts on created names.
- Discovery surfaces (doctor, sparse-checkout, live-work, commit guard) recognize every grammar creation produces.
- `kitty/mission-{slug}*` recovery enumeration over-matches prefix slugs (`057-foo` vs `057-foobar`) — a separate defect, filed as a follow-up, not fixed here.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Single lane naming authority | As an operator, I want every Spec Kitty surface to obtain a lane's branch name and worktree location from the lane naming authority, keyed only on the creation input (slug + lane id), so that no stage looks up a name that was never created. | High | Open |
| FR-002 | No naming-form choice | As a maintainer, I want the public lane-naming surface to offer no way to request a naming form (no Mission-identity parameter for lane branch or worktree names), so that a divergent form cannot be requested; verified by signature and by the gate. | High | Open |
| FR-003 | Reconciliation claim uses the authority | As an operator, I want every reconciliation-claim consumer (approved-commit attribution, canceled-lane exclusion, authored-blob spine) to use the created lane branch, and an approved non-canceled lane whose created branch does not resolve to produce a refusal naming that branch rather than an empty commit set, so that a legitimate merge is not refused and a real miss is legible (#5108). | High | Open |
| FR-004 | Lane-tip capture uses the authority | As an operator, I want pre-interrupt lane-tip capture to key every non-canceled, non-planning lane's tip by its created branch name, so that the resume guard is armed. | High | Open |
| FR-005 | Resume refuses an unanchored tip record | As an operator, I want `merge --resume` to refuse, naming `merge --abort` as the remedy, when any non-canceled, non-planning lane has no tip under its created branch name, so that a resume never proceeds with its guard disarmed; applies where lane tips are captured and persisted (coordination topology with a persisted pre-mutation coordination anchor); canceled-only and planning-only manifests are exempt. | High | Open |
| FR-006 | Remaining lane consumers routed through the authority | As a maintainer, I want the remaining lane-name consumers that already compose the created form (consolidation, already-integrated skip, cleanup, retention, orchestrator/discard cleanup, workspace/context/topology resolution, dependency bases, backfill-ownership migration, acceptance lane source roots) routed through the authority with behavior preserved, and the pre-mutation safety preflight corrected to inspect created worktrees, so that no consumer can diverge again. | High | Open |
| FR-007 | Retire the dual-name probe | As a maintainer, I want the lifecycle path that probes several candidate lane names removed in favor of the authority, so that there is no third naming strategy. | Medium | Open |
| FR-008 | Match sites through the authority's parsers | As a maintainer, I want these match sites to recognize lane names only through the naming authority's parsers, covering every grammar creation produces: sparse-checkout lane matching, the coordination doctor's sparse-checkout drift check, the status doctor's orphan-workspace scan, live-work worktree bindings, the commit guard's lane-branch pattern, merge-resolution branch parsing, and VCS worktree detection. Operator remediation text (stale-lane guidance) and recovery-time branch enumeration are excluded. | Medium | Open |
| FR-009 | Non-vacuous architectural gate | As a maintainer, I want the existing worktree-naming gate extended (one gate, one allow-list) over `src/specify_cli/` and `src/runtime/` that fails on any compose or match site outside the naming authority, with a baseline count recorded in the plan that can only shrink and reaches 0 compose sites outside the authority by mission close, and a self-test proving it goes red on an injected offender. | High | Open |
| FR-010 | Preserve stable, origin-aware lane identity | As an operator, I want lane ids to stay stable across re-finalize and fresh lanes to prefer an existing `origin/<lane>`, so that the previously landed guarantees (absorbed from `terminus-merge-integrity-01M380R6` WP04) remain intact. | High | Open |
| FR-011 | Re-finalize preserves the recorded Mission branch | As an operator, I want re-finalizing tasks to keep the lanes manifest's recorded Mission branch (first-time finalize is unchanged and defines it), and every other Mission-branch consumer to prefer the recorded value, refusing with a typed error rather than crashing when it must recompose from an invalid identity, so that a backfilled legacy Mission never targets a Mission branch that was never created. | High | Open |
| FR-012 | Red-first regressions for divergent shapes | As a maintainer, I want red-first regressions for the sites that diverge today (reconciliation claim consumers, lane-tip capture, resume anchoring, safety preflight, the dual-name probe, Mission-branch re-finalize) over the divergent shapes in User Story 1, with fixtures that create lanes through the creation authority; the existing red `TestPlanningArtifactReachesTarget` cases go green without editing their fixture. Behavior-preserving re-routes (FR-006) are guarded by the gate and existing tests. | High | Open |
| FR-013 | Decision recording on a fresh coordination Mission | As an operator, I want `decision open` / `decision resolve` to resolve every write target before writing — materializing the coordination worktree through the existing materialization path when it is absent — and to fail with nothing written only when materialization itself fails, so that a Decision Moment is never half-recorded (#5113). Which partition each ledger file lives on is unchanged. | Medium | Open |
| FR-014 | Truthful unmaterialized-coordination remedy | As an operator, I want the unmaterialized-coordination error wherever it is raised, to name a command that, when run, leaves the coordination worktree materialized, so that following the tool's advice unblocks me (#5113). | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Name stability | 100% of byte-identity goldens that describe a created name (every Mission-branch, coordination and Mission-dir golden, and every lane/worktree golden composed without an injected identity) pass unchanged; lane/worktree goldens that encode identity-injected names creation never produces are re-pinned to the created name; zero existing lane or Mission branches or worktrees are renamed. | Compatibility | High | Open |
| NFR-002 | Complexity ceiling | Every touched function stays at cyclomatic complexity ≤ 15 (ruff C901 / Sonar S3776). | Maintainability | High | Open |
| NFR-003 | Gate floor | The gate's compose-site baseline is recorded as a number in the plan, never grows, and is 0 outside the naming authority at mission close; the match-site baseline is recorded and never grows. | Maintainability | High | Open |
| NFR-004 | Change coverage | Diff coverage on changed lines ≥ 90%. | Quality | High | Open |
| NFR-005 | Static checks | Zero new ruff, ruff-format or mypy findings; no new suppressions. | Quality | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Extend, don't duplicate | The authority is the existing creation-side lane-placement authority in the lanes subsystem, extended; no competing naming authority is introduced. | Technical | High | Open |
| C-002 | No manifest schema change | No per-lane branch-name field is added to the lanes manifest. | Technical | High | Open |
| C-003 | Layer direction | The naming authority stays in `specify_cli`; no new upward imports and no growth of the shrink-only outbound ledgers. | Technical | High | Open |
| C-004 | No probing | No read-time legacy-compat fallback or multi-candidate probing (ADR `2026-07-01-1`); discovery is allowed only through the authority's parsers. | Technical | High | Open |
| C-005 | Creation-path verification | Planning must verify, by enumerating every lane-branch creation site, that lanes are created only through the creation-side placement authority; any other creation site is folded into FR-006. | Technical | High | Open |
| C-006 | Decision-ledger partitions unchanged | The partition assignment of decision artifacts and events is not changed (see #5023, out of scope). | Technical | High | Open |
| C-007 | Legacy retirement not decided here | The tension with dropping pre-3.2.x legacy Mission support (see #2463) is recorded, not decided; legacy Missions keep working. | Business | Medium | Open |
| C-008 | Out of scope | Merge-marker/state write-ordering (see #5111), 3-way content attribution (see #5053), tag-collision rev-parse (see #5058), mid8 legibility (see #4681). | Business | Medium | Open |

### Key Entities

- **Lane**: an execution lane of a Mission; has a stable lane id, a created branch, and a created worktree location.
- **Lanes manifest**: the per-Mission record of lanes, their work packages, the Mission branch and the Mission identity.
- **Lane naming authority**: see Domain Language.
- **Pre-interrupt lane tips**: persisted per-lane commit anchors, keyed by created branch name, that a resumed merge compares against.
- **Decision ledger**: the per-Mission decision index, decision artifacts, and their status events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four divergent shapes (backfilled legacy, mismatched mid8, invalid identity ≥ 8 chars, invalid identity < 8 chars) merge successfully end to end (4/4) with no traceback, where today all are refused or crash.
- **SC-002**: 0 lane branches or worktrees are orphaned after a successful merge of each divergent shape.
- **SC-003**: 0 compose sites outside the naming authority under `src/specify_cli/`; the gate goes red on 100% of injected synthetic offenders (compose and match).
- **SC-004**: 100% of created-name goldens (per NFR-001) and lane-identity (FR-010) tests pass unchanged.
- **SC-005**: A resume with an unanchored lane-tip record refuses in 100% of cases and names the remedy; canceled-only/planning-only Missions never trigger it.
- **SC-006**: On a fresh coordination Mission, 100% of `decision open` / `resolve` invocations complete (worktree materialized) or, if materialization fails, leave the ledger byte-identical; following the error's remedy materializes the worktree in 100% of cases.
- **SC-007**: Re-finalizing a backfilled legacy Mission leaves its recorded Mission branch unchanged in 100% of cases.

## Assumptions

- Backfill does not rewrite the lanes manifest; the identity reaches it on the next finalize.
- The Mission slug recorded for a Mission is stable across backfill (only the identity changes).

## Traceability

- Addresses: #5108, #5113.
- Context: see #5045 (discovery), see #5023 (decision-ledger dual partition; related to #5113, out of scope), see mission `nightly-red-remediation-01M3EP85` (fixture re-pin; not present in this checkout's history — unverified), see mission `terminus-merge-integrity-01M380R6` (FR-010 origin).
