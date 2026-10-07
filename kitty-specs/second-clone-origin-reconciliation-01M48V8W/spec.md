# Mission Specification: Second clones reconcile with origin before every terminus gate

**Mission Branch**: `claude/happy-keller-r38xig` (lanes topology, no coordination branch)
**Created**: 2026-10-06
**Status**: Draft (post-spec squad folded 2026-10-06)
**Input**: User description: "Second clones reconcile with origin before every terminus gate (#5780, #5758, #5759). Topology: lanes (no coordination branch). Discovery is already answered by the pre-spec squad + operator rulings."

## Intent Summary

- **Primary actor**: a teammate working in their own clone of a shared project (the integrator or the reviewer), with a shared remote that both clones push to.
- **Trigger**: the teammate runs an evidence gate — `agent action review`, `accept`, `consolidate` (or their `orchestrator-api` equivalents) — or runs `init` / `upgrade` in a freshly cloned project.
- **Desired outcome**: before an evidence gate trusts the clone's local copy of a Mission's status or code, it checks what teammates pushed. A rejection or a fix that a teammate pushed is never silently ignored, and a fresh clone is set up so its first pull merges mission files with the shipped merge drivers.
- **Rule that must always hold**: an evidence gate never exits 0 while acting on a local view it knows is missing teammates' pushed status or code for this Mission, unless the operator explicitly opted out (and the output says so).
- **Boundary**: push safety for the target branch (`consolidate --push`) is unchanged; a gate never refuses because the target branch is behind for reasons unrelated to this Mission's status (#1706).
- **Decisions** (operator rulings, Decision Moments `01M48V9BXYQ1R42R071S33MCDQ` and `01M48V9K2YY2V1DH37AT8DHP2S`):
  - Origin ahead is handled by branch class: stale status evidence is refused and the gate never moves the branch that carries it; a lane at review is created from, or fast-forwarded to, the remote's lane when that is safe, and refused when diverged.
  - A configured but unreachable remote fails closed at the merge-path gates, with an explicit per-invocation opt-out and an environment-level default for it. No remote at all, or a branch never pushed, passes silently.
- **Discovery mode**: the operator asked for semi-autonomous execution; discovery was satisfied by a four-lens pre-spec squad (live reproductions, gate map, tracker sweep, brownfield cut) plus the two escalated rulings. A two-lens post-spec squad (non-vacuity; authority/terminology) was folded into this version.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The integrator's consolidate sees a teammate's pushed rejection (Priority: P1)

Clones A and B share a remote. Both work packages are approved and pushed. In clone B the reviewer rejects WP02 and pushes the status change. In clone A, which has not pulled, the integrator runs `consolidate`. Today it lands WP02 as done on the target, exit 0 (and publishes it with `--push`) (#5780). After this mission, consolidate notices that the remote carries status events for this Mission that A lacks and refuses before any branch moves, naming the remedy.

**Why this priority**: P0. Rejected work reaches the target branch silently in the ordinary two-person review flow.

**Independent Test**: two real clones of a bare remote; reject in B and push; run consolidate in A without pulling. Expect a refusal with no branch moved; after the named remedy, consolidate refuses with the ordinary "WP02 missing review approval" (the teammate's rejection is now visible). Run for both a coordination-topology Mission (evidence on the coordination branch) and a lanes Mission (evidence on the target branch).

**Acceptance Scenarios**:

1. **Given** the remote's status evidence branch carries status events for this Mission that A's local branch lacks (a teammate's rejection), **When** the integrator runs `consolidate` in A, **Then** it exits non-zero before any branch moves with `ORIGIN_STATUS_STALE`, naming the branch, the number of missing commits and the remedy command.
2. **Given** the same setup with `--push`, **When** consolidate runs, **Then** nothing is pushed.
3. **Given** A's evidence branch also has local status commits the remote lacks (diverged), **When** consolidate runs, **Then** it refuses the same way; local-only commits alone never cause a refusal.
4. **Given** a lanes Mission whose target branch is behind the remote only because of commits that do not touch this Mission's status event log (a teammate landed an unrelated Mission), **When** consolidate runs, **Then** it proceeds exactly as today (FR-015 positive control on the same fixture).
5. **Given** A is up to date with the remote, **When** consolidate runs, **Then** it behaves exactly as today.
6. **Given** a merge record exists (an interrupted run), **When** a resumed consolidate finds stale status evidence, **Then** the remedy text is "abort, update, re-run" (`consolidate --abort`, then the update command, then `consolidate`), never an update that would move a branch the record holds.

---

### User Story 2 - The reviewer's re-review sees the teammate's pushed fix (Priority: P1)

Reviewer A rejected B's WP02 (v1). B pushed fix v2 to the lane. A runs `git pull` (which updates A's remote-tracking view of the lane but not A's local lane) and `agent action review WP02` again. Today the review workspace still shows v1, A approves, and consolidate lands v1 (#5758). After this mission, the review workspace shows v2.

**Why this priority**: P0. The fix the reviewer asked for is silently dropped and the rejected code lands under a "verified" banner.

**Independent Test**: two real clones, a bare remote, the reject → fix → re-review loop. The review workspace must contain v2 and consolidate must land v2.

**Acceptance Scenarios**:

1. **Given** the reviewer's local lane is a strict ancestor of the remote's lane and every checkout of that lane is clean (review-lock residue excepted), **When** the reviewer runs `agent action review`, **Then** the lane is fast-forwarded to the remote's tip before the review lock is acquired, every checkout of it is updated, and the output says so.
2. **Given** the reviewer has a local lane but no review workspace, and the lane is behind, **When** review runs, **Then** the lane is fast-forwarded before the workspace is created.
3. **Given** the reviewer has no local lane at all, **When** review runs, **Then** the workspace is created from the remote's lane (not from the reviewer's current branch).
4. **Given** the reviewer's local lane and the remote's lane have diverged, **When** review runs, **Then** it refuses with `ORIGIN_LANE_DIVERGED` before acquiring the review lock, naming both directions and the remedy.
5. **Given** the reviewer's local lane is behind but a checkout of it has uncommitted changes (other than review-lock residue), or another agent holds a live review lock on it, **When** review runs, **Then** it refuses rather than discard, merge or race.
6. **Given** an approved lane whose remote tip is ahead of or diverged from the integrator's local lane, **When** the integrator runs `consolidate`, **Then** it refuses with `ORIGIN_LANE_STALE` before the approval-stamp check runs and before any branch moves; the remedy is to update the local lane and re-run (the approval-stamp check then decides), not to re-approve.

---

### User Story 3 - A teammate's fresh clone gets the merge-driver settings (Priority: P2)

B clones a project A already initialized and runs `spec-kitty init` (it reports "Already initialized"). Today the clone never receives the per-clone merge-driver git settings, so B's first `git pull` that brings a divergent mission file text-merges `status.events.jsonl` and `meta.json`; conflict markers then wedge every command with `MISSION_META_READ_ERROR` (#5759). After this mission, `init` on an already-initialized clone, and `upgrade`, install those settings, so the pull merges the mission files with the shipped drivers.

**Why this priority**: P1. Every second machine on a project hits this on the documented onboarding path, with no CLI remedy today.

**Independent Test**: clone, `init`, divergent status change in both clones, pull. No conflict markers in `status.events.jsonl` or `meta.json`; `agent tasks status` keeps working.

**Acceptance Scenarios**:

1. **Given** a fresh clone of an initialized project with no merge-driver settings, **When** the teammate runs `spec-kitty init`, **Then** the settings are installed and init still reports "Already initialized" with exit 0.
2. **Given** the same clone, **When** the teammate runs `spec-kitty upgrade` instead, **Then** the settings are installed even though every migration is already recorded as applied, and the install is reported in upgrade's single outcome (ADR 2026-10-04-3).
3. **Given** the settings are already present, **When** init or upgrade runs again, **Then** nothing changes (idempotent).

---

### User Story 4 - A solo or offline user is not broken (Priority: P2)

A user with no remote configured, or whose Mission branches were never pushed, runs every evidence gate exactly as today. A user who has a remote but is offline at a merge-path gate gets a clear refusal that names the opt-out; with the opt-out (per invocation, or as an environment default) the gate warns and proceeds.

**Why this priority**: the fix must not regress single-clone and offline work.

**Independent Test**: no-remote fixture (all gates pass unchanged); unreachable-remote fixture (merge-path gates refuse naming the opt-out; with the opt-out they warn and proceed; review warns and proceeds without it).

**Acceptance Scenarios**:

1. **Given** no remote resolves for the branch (FR-017), **When** review, accept or consolidate runs, **Then** no remote is contacted and behaviour is unchanged.
2. **Given** a remote resolves and answered in this invocation that the branch does not exist there, **When** a gate runs, **Then** it passes silently.
3. **Given** a remote resolves but cannot be reached, **When** accept or consolidate runs, **Then** it refuses with `ORIGIN_UNREACHABLE` before any mutation and names the opt-out — even when a stale remote-tracking ref exists locally or is absent.
4. **Given** the same unreachable remote, **When** the operator passes `--origin-check warn`, or `SPEC_KITTY_ORIGIN_CHECK=warn` is set, **Then** the gate prints a warning naming the verdict and where the opt-out came from, and continues using the last-known view.
5. **Given** an unreachable remote, **When** `agent action review` runs, **Then** it warns and continues using the last-known view.

### Edge Cases

- A pushed branch that A has never fetched, and the refresh fails: the verdict is `unreachable`, never `remote_missing` (absence is only concluded from a remote that answered in this invocation).
- The coordination branch exists only on the remote (never materialized locally): the existing `COORDINATION_WORKTREE_UNMATERIALIZED` refusal (ADR 2026-09-24-2) applies; no parallel refusal is added.
- A branch whose configured remote is not named `origin`: that remote is used (FR-017).
- Several remotes, none named `origin`, and no configured remote for the branch: treated as "no remote" (passes silently), documented as such.
- A remote that would prompt for credentials: never blocks; treated as unreachable.
- `single_branch` Missions: the evidence branch is the write branch (`kitty/mission-…` for a protected target; the target itself with `--commit-to-target`); the status-log scoping of FR-001 makes both well defined.
- `SPEC_KITTY_ORIGIN_CHECK` holds an unrecognized value: enforce, with a warning (fail closed).
- A resumed consolidate whose earlier attempt already consolidated (and possibly deleted) some lanes: those lanes are not re-checked.
- `consolidate --dry-run` is a read-only forecast and does not run the check.
- The status log of a coordination Mission may live under the slug-plus-mid8 directory on the coordination branch (ADR 2026-10-05-1); the scope covers every directory alias of the Mission.

## Domain Language

| Term | Meaning here | Avoid |
|------|--------------|-------|
| **remote (of a branch)** | The remote a branch is checked against, resolved by FR-017. Called "origin" in prose. | "upstream" (overloaded) |
| **evidence gate** | A command that turns a Mission's local status or code into a durable verdict: review workspace preparation, accept, consolidate, and their `orchestrator-api` forms. | "terminus gate" (terminus already means mission end), "merge" alone |
| **status evidence branch** | The branch whose copy of the Mission's `status.events.jsonl` a gate reads: the coordination branch, else the write branch for `single_branch`, else the target branch (lanes). | "coord" when there is no coordination topology |
| **origin freshness check** | Refreshing the remote's view of a branch in this invocation and classifying the local branch against it. | "origin reconciliation" (clashes with the consolidation reconciliation gate), "sync" (retired transport vocabulary) |
| **freshness verdict** | One of `up_to_date`, `behind`, `ahead`, `diverged`, `local_missing`, `remote_missing`, `unreachable`, `no_remote`. | "in sync" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Consolidate refuses on stale status evidence | As an integrator, I want consolidate to refuse with `ORIGIN_STATUS_STALE`, before any branch moves, when the remote's status evidence branch has commits that local lacks and that change this Mission's `status.events.jsonl`, so a teammate's pushed rejection is never landed as done (#5780). Commits that do not touch that log never cause this refusal. | High | Open | [build] | no — the red-first two-clone test lands WP02 done at exit 0 today, for both coordination and lanes topologies |
| FR-002 | Consolidate refuses on stale approved lanes | As an integrator, I want consolidate to refuse with `ORIGIN_LANE_STALE` when an approved lane's remote tip is ahead of or diverged from my local lane. It runs before the approval-stamp check and only refuses: it never adds content to the approved claim. | High | Open | [build] | no — paired with the up-to-date positive control on the same fixture |
| FR-003 | Accept refuses on stale status evidence | As an integrator, I want `accept` to apply the FR-001 check, so the gate before consolidate cannot pass on a stale view either. | High | Open | [build] | no — stale-clone fixture passes accept today |
| FR-004 | Orchestrator-api gates refuse before mutation | As an external orchestrator, I want `orchestrator-api accept-mission` and `consolidate-mission` to apply the FR-001/FR-002 checks before their first mutation, refusing with their existing envelope codes (`MISSION_NOT_READY` for accept-mission, `PREFLIGHT_FAILED` for consolidate-mission) and `data.preflight_error_code` set to the freshness code, and reporting the verdicts in the envelope (contract version bumped). | High | Open | [build] | no — same stale-clone fixture through the API entry point |
| FR-005 | Review prepares the workspace from the remote | As a reviewer, I want `agent action review` to create a missing lane from the remote's lane, fast-forward a strictly-behind lane (every checkout of it clean, review-lock residue exempt, no live foreign review lock) before the workspace is created or the lock acquired, and refuse a diverged lane (`ORIGIN_LANE_DIVERGED`) or an unsafe fast-forward, so I always review what my teammate pushed (#5758). A review that runs in the repository root checkout (planning lane, `single_branch`) is skipped: that branch is the status evidence branch, which a gate never moves (C-002). | High | Open | [build] | no — the re-review fixture shows v1 today |
| FR-006 | Gates refresh the remote themselves | As a teammate, I want each evidence gate to refresh the remote's view of the branches it is about to trust in the same invocation. `up_to_date` and `remote_missing` may only be concluded from a remote that answered in this invocation; a failed refresh yields `unreachable` even when a local remote-tracking ref exists or is absent. | High | Open | [build] | no — #5780's fixture never fetches; a fixture with a pushed-but-never-fetched branch and a failing remote must yield `unreachable` |
| FR-007 | No remote or unpublished branch passes silently | As a solo user, I want every gate to behave exactly as today when no remote resolves for the branch, or the remote answered that the branch was never pushed. | High | Open | [ratchet] | yes — paired with FR-001's red case on the same two-clone fixture minus the remote |
| FR-008 | Unreachable remote fails closed at merge-path gates | As an integrator, I want accept, consolidate and their orchestrator-api forms to refuse with `ORIGIN_UNREACHABLE` when the resolved remote cannot be reached, naming the opt-out; review only warns. | High | Open | [build] | no — unreachable-remote fixture passes today |
| FR-009 | Explicit opt-out with an environment default | As an operator, I want `--origin-check warn` on each merge-path gate, and `SPEC_KITTY_ORIGIN_CHECK=warn` as its default (default `enforce`), to turn every freshness refusal into a printed warning that names the verdict and where the opt-out came from (flag or environment). An unrecognized value enforces. The variable is documented with the other `SPEC_KITTY_*` variables. | Medium | Open | [build] | no — refusal without the opt-out, warning with it, same fixture |
| FR-010 | Actionable refusal text | As a teammate, I want every refusal to name the branch, the direction and size of the difference, the code, and the exact remedy command (abort-first when a merge record exists). | Medium | Open | [build] | no — asserted on the refusal text of FR-001/FR-005 tests |
| FR-011 | Init installs clone-local merge settings on an initialized clone | As a teammate on a fresh clone, I want `spec-kitty init` on an already-initialized project to install the per-clone merge-driver settings idempotently, so my first pull merges mission files with the shipped drivers (#5759, #4146, #4442). | High | Open | [build] | no — fresh clone has 0 settings after init today |
| FR-012 | Upgrade installs clone-local merge settings | As a teammate, I want `spec-kitty upgrade` to install the same settings even when every migration is recorded as applied, reported through upgrade's single outcome. | Medium | Open | [build] | no — clone fixture has 0 settings after upgrade today |
| FR-013 | One owner of remote contact | As a maintainer, I want every git invocation that contacts a remote (`fetch`, `ls-remote`, `remote show` without `-n`, `pull`, `clone`) to go through one owner, enforced by an architectural gate with an empty allowlist and a planted-violation self-test. `push` is excluded (FR-015). The same owner resolves remote-tracking refs, so the #4969 sites share one rule. | Medium | Open | [build] | no — the gate's planted violation must fail it |
| FR-014 | Every evidence gate runs the freshness check | As a maintainer, I want an architectural gate that fails when an evidence-gate entry point does not run the origin freshness check, with a planted omission as self-test and a non-zero floor of registered entry points. | Medium | Open | [build] | no — planted omission must fail it |
| FR-015 | Push safety for the target branch unchanged | As an integrator, I want `consolidate --push` target-branch preflight to behave as today, and local consolidate never to refuse because the target branch is behind for commits that do not touch this Mission's status log (#1706). | High | Open | [ratchet] | yes — paired with FR-001's red case on the same lanes fixture (only unrelated target commits → proceeds) |
| FR-016 | Implement's origin preference preserved | As an implementer, I want a fresh lane to keep rooting on a teammate's pushed lane (#4969), now through FR-013's owner and FR-017's rule. | Medium | Open | [ratchet] | yes — existing #4969 tests are the positive control |
| FR-017 | One remote rule | As a maintainer, I want one rule for which remote a branch is checked against: the branch's configured remote; else the sole configured remote; else the remote named `origin`; else no remote. Reachability is judged against that remote only. The all-remotes existence probe (#4979) keeps its own documented semantics inside the same owner. | Medium | Open | [build] | no — fixture with a non-`origin` configured remote must be checked against it |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded remote contact | Each remote contact completes or is classified unreachable within 15 seconds (one named timeout per contact class); a gate refreshes each remote at most once per invocation. | Performance | High | Open |
| NFR-002 | Never prompts | No remote contact can block on an interactive credential prompt (0 prompts across the test matrix). | Reliability | High | Open |
| NFR-003 | No-remote overhead | With no remote resolving, the added check costs under 200 ms per gate invocation. | Performance | Medium | Open |
| NFR-004 | Real-git regression coverage | Each of #5780, #5758 and #5759 has an issue-pinned regression test that drives the real CLI entry point with two real clones and a bare remote, red on the pre-fix base and green after; global git configuration is isolated in those tests. | Reliability | High | Open |
| NFR-005 | Quality gates | New and touched code passes ruff, ruff format and mypy with zero new findings; no touched function exceeds complexity 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Layering | The ref-level mechanics (resolve remote, refresh, classify, probe) live in the foundation layer and know nothing of Missions, lanes or status; the intent lives in the application layer. | Technical | High | Open |
| C-002 | Gates never move the status evidence branch | A gate refuses on stale status evidence; it never merges, fast-forwards or resets that branch itself. | Technical | High | Open |
| C-003 | Lane moves only by compare-and-swap | The only branch a gate may move is a reviewer's local lane, forward only, through the existing compare-and-swap ref advance (which checks and updates every checkout), recording the lane work tip. | Technical | High | Open |
| C-004 | Empty allowlists | Every architectural gate added by this mission closes with an empty allowlist (ADR 2026-09-30-1). | Technical | High | Open |
| C-005 | ADR | A new ADR amends ADR 2026-06-05-1 Decisions 1 and 2 (remote inspection only in `push_preflight`; domain preflight network-free): remote contact gets one owner, push safety stays with `push_preflight`, and evidence freshness runs as a named preflight before any mutation. It records the pre-existing drift (`remote_probes`, `protection_policy`) and cites ADRs 2026-09-24-2, 2026-10-04-5 and 2026-10-04-3. | Governance | High | Open |
| C-006 | Retired vocabulary | No new identifier, flag, environment variable or message uses the retired "sync" vocabulary. | Governance | High | Open |
| C-007 | Overlap with in-flight work | Do not edit `consolidation/rollback.py`, `git/ref_advance.py` or `coordination/status_surface_guard.py` while PR #5810 is open; rebase after it lands. | Technical | Medium | Open |

### Key Entities

- **Resolved remote**: for one branch, the remote chosen by FR-017 (or none).
- **Freshness verdict**: the relation between a local branch and the remote's tip after a refresh in this invocation, with counts.
- **Freshness policy**: per gate and branch class, what each verdict means (pass, fast-forward, warn, refuse), plus the operator opt-out and its source.

## Out of Scope (follow-ups, linked not closed)

- Origin checks at the approval transition itself (`move-task` / `agent status emit` to approved/done); covered at the terminus by FR-002.
- `implement` on an existing lane (reuse, crash recovery) and dependency-lane tips preferring the remote.
- `doctor coordination` staleness against the remote; a `doctor` finding for missing merge-driver settings.
- Renaming the pre-existing `*Sync*` identifiers in `push_preflight` (git-sense names; rename only where this mission moves the code).
- Merge-driver semantics (#5460, #5465), `status.json` conflicts (#4955), status writers that bypass the guard (#5644), doctrine-pack fetch URL changes (#5778), rebasing a mission onto a moved base (#2273).

## Assumptions

- The status-evidence verdict is computed from git history scoped to this Mission's status event log, not from an in-memory union of event logs; a union-based verdict is a possible later refinement.
- Updating the status evidence worktree from the remote (`git pull` there) is the named remedy; FR-011/FR-012 make that pull merge cleanly.
- A committed project-tier environment file could set `SPEC_KITTY_ORIGIN_CHECK=warn` for every clone; the warning names its source so that choice is visible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5780 two-clone reproduction, consolidate exits non-zero and the rejected work package does not land (0 of 2 arms land it: plain and `--push`; both coordination and lanes topologies). — [build] · no-op passable: no
- **SC-002**: In the #5758 reproduction, the re-review workspace shows the teammate's fix and the target branch receives the fix, not the rejected version. — [build] · no-op passable: no
- **SC-003**: In the #5759 reproduction, a fresh clone initialized with `spec-kitty init` pulls a divergent mission with 0 conflict markers in `status.events.jsonl` and `meta.json`. — [build] · no-op passable: no
- **SC-004**: With no remote resolving, or a remote that lacks the Mission's branches (the shape of most existing fixtures), every existing evidence-gate test passes unchanged (0 regressions in the targeted suites). — [ratchet] · no-op passable: yes — paired with SC-001 on the same fixture with the remote present
- **SC-005**: Both new architectural gates have empty allowlists and fail on their planted violation. — [build] · no-op passable: no
