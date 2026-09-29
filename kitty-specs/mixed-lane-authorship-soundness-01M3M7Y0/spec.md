# Mission Specification: Mixed-lane authorship soundness

**Mission Branch**: `issue-5046-mixed-lane-authorship` (target branch from `mission create`; topology `lanes`, no coordination branch)
**Created**: 2026-09-28
**Status**: Draft
**Input**: Slice 6 toward the 4.0.0rc5 cut — issues #5047 then #5046 (parent epic: #5001). Post-spec, post-plan and post-tasks squad findings folded 2026-09-28. Operator decisions recorded as Decision Moments `01M3M7ZQG4F3M4YCY9NJCEEBQ8`, `01M3M8022ZA99EVP88Y861DFAH`, `01M3M84XQM14N7Q6ZG1QWFDYZT`, `01M3MAB8FTDKKVVTXPREK75AEP`, `01M3NR7QRXJBZXQR1B91XKY3JQ`, `01M3NR7XAJGSJCK5YP937KT91H`.

## Intent Summary (confirmed by the operator, 2026-09-28)

- **Primary actor:** an operator running `spec-kitty consolidate` (default squash strategy, or merge) on a mission.
- **Trigger:** one work package (WP) was canceled *after* it committed content to an execution lane it shares with a WP that is approved (a *mixed lane*).
- **Desired outcome:** the reconciliation gate — the last line of defence before the target branch advances — decides per WP, not per lane, whose content is on the target. Canceled content that no surviving WP superseded is caught (FAIL) and the target is restored; superseded canceled content passes; when the gate cannot tell which commits the canceled WP made, it refuses (REFUSE) rather than guessing.
- **Invariant:** *no canceled WP's content reaches the target while consolidation exits 0.*
- **Boundary:** the canonical terms are **Mission**, **work package (WP)**, **execution lane**, **mixed lane**, **reconciliation gate**, and **WP commit attribution**, and the gate verdicts **PASS / FAIL / REFUSE** (see Domain Language).

### Why this mission exists (grounded on `origin/main` `dccf6aa7`)

Today the gate treats a lane as approved if *any* of its WPs is approved, and then trusts the lane's entire first-parent history as approved authorship. Cancellation is a status change, not a revert, and a lane is consolidated whole, so a canceled sibling's commits are physically on the target and are also counted as approved. The result is a silent PASS of canceled work under **both** the squash and the merge strategy (the issue text says squash; grounding showed merge leaks through the same exclusion subtraction). The existing regression pin for the opposite failure (a false FAIL on a mixed lane, listed under Dependencies and References) cancels its WP before that WP commits anything, so no test exercises committed-then-canceled work. No test fixture plants a committed-then-canceled WP or records per-WP attribution (#5047); grounding on 2026-09-28 also showed the fixture limitation recorded in that issue (default strategy unreachable, post-build lane mutation breaks consolidation) does not reproduce — the only real trigger is a missing coordination worktree directory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Canceled work cannot ship silently (Priority: P1)

An operator consolidates a mission in which WP02 committed changes to lane A and was then canceled, while WP01 in the same lane A was approved. WP01 never touched WP02's files afterwards. Consolidation must not exit 0 with WP02's content on the target branch.

**Why this priority**: This is a data-loss-class defect (canceled work silently shipped) in the release-blocking epic; it is the reason the mission exists.

**Independent Test**: Build a mixed-lane mission where the canceled WP adds a file, modifies a file, and deletes a file; consolidate with the default strategy and with the merge strategy; observe a FAIL verdict (not a refusal), a non-zero exit, a message naming the lane, the canceled WP and the offending paths, and a target branch restored to its pre-consolidation position.

**Acceptance Scenarios**:

1. **Given** a mixed lane where the canceled WP added a file no surviving WP touched, **When** the operator consolidates with the default strategy, **Then** the gate returns a FAIL verdict (not a refusal), consolidation exits non-zero, reports the canceled WP and the path, and the target branch is back at its pre-consolidation commit.
2. **Given** the same mission, **When** the operator consolidates with the merge strategy, **Then** the outcome is the same as scenario 1.
3. **Given** a mixed lane where the canceled WP deleted a file that exists at the base, **When** the operator consolidates, **Then** consolidation does not exit 0 with that file missing from the target.
4. **Given** a mixed lane where the canceled WP modified an existing file and no survivor rewrote it, **When** the operator consolidates, **Then** consolidation does not exit 0 with the canceled modification on the target.

---

### User Story 2 - Superseded canceled work does not block a good consolidation (Priority: P1)

An operator consolidates a mission in which WP02 committed a change to `a.py` and was then canceled, and the approved WP03 in the same lane later rewrote `a.py` in full. The target should carry WP03's approved version; consolidation must succeed.

**Why this priority**: The previous fix in this area was about exactly this availability failure; a guard that reintroduces a false FAIL here would trade one release blocker for another.

**Independent Test**: Build a mixed lane where every path the canceled WP touched is later rewritten (or restored) by a surviving WP; consolidate under both strategies; observe exit 0 and the survivor's content on the target.

**Acceptance Scenarios**:

1. **Given** a mixed lane where every path touched by the canceled WP was later rewritten by an approved WP, **When** the operator consolidates with either strategy, **Then** consolidation exits 0 and the target carries the approved WP's content.
2. **Given** a mixed lane where the canceled WP added a file that a surviving WP later deleted, **When** the operator consolidates with either strategy, **Then** consolidation exits 0 and the file is absent from the target.
3. **Given** a mixed lane where the canceled WP changed a file and then itself reverted it to its base content before being canceled, **When** the operator consolidates, **Then** consolidation exits 0.
4. **Given** a mixed lane whose canceled WP was canceled before it entered implementation, **When** the operator consolidates with either strategy, **Then** consolidation exits 0 (the existing merge-strategy regression pin keeps passing and gains a default-strategy twin).

---

### User Story 3 - Unknown authorship fails closed (Priority: P1)

An operator consolidates a mission in which a canceled WP shares a lane with an approved WP, but the system cannot establish which lane commits the canceled WP authored — for example the mission predates commit attribution, or the attribution evidence for the canceled WP is missing, unreadable, or contradictory.

**Why this priority**: Per-WP attribution is only as sound as its evidence; when the evidence is missing or contradictory the gate must not fall back to today's trust-the-whole-lane behaviour.

**Independent Test**: Build a mixed lane whose canceled WP committed content but for which no commit attribution exists; consolidate; observe a REFUSE verdict (non-zero exit, target at its pre-consolidation commit) with a message telling the operator how to recover.

**Acceptance Scenarios**:

1. **Given** a mixed lane whose canceled WP entered implementation (its lifecycle history contains a transition into `claimed` or `in_progress`) but has no commit attribution, **When** the operator consolidates, **Then** consolidation refuses with a REFUSE verdict, exits non-zero, the target branch ends at its pre-consolidation commit, and the message names the lane and the WP lacking attribution and states the recovery action.
2. **Given** a mixed lane in which a lane commit is attributed both to the canceled WP and to another WP (the attribution evidence contradicts itself), **When** the operator consolidates, **Then** consolidation refuses in the same way.
3. **Given** a lane whose WPs are all approved (no canceled WP), **When** the operator consolidates a mission with no commit attribution at all (a legacy mission), **Then** consolidation behaves exactly as it does today — the new refusal applies only to mixed lanes.
4. **Given** a legacy or in-flight mission (created before this change) with a mixed lane whose canceled WP entered implementation, **When** the operator consolidates after upgrading, **Then** consolidation refuses (by design); the recovery is to revert the canceled WP's commits on the lane branch through a surviving WP's governed work, after which its paths are superseded.

---

### User Story 4 - Maintainers can reproduce mixed-lane defects under the default strategy (Priority: P2)

A maintainer writing a reconciliation regression test needs a mixed-lane mission fixture in which a canceled WP's commits (and, optionally, a superseding commit by a surviving WP) are already on the lane, and which consolidates end to end under the default squash strategy as well as the merge strategy.

**Why this priority**: It enables red-first coverage of stories 1–3 (issue #5047); it has no product behaviour of its own.

**Independent Test**: Use the fixture to build a mixed-lane mission and run a real consolidation with the default strategy; it reaches the reconciliation gate rather than aborting early with an unmaterialized-coordination error.

**Acceptance Scenarios**:

1. **Given** the fixture configured with a canceled WP that committed, **When** a test runs consolidation with the default strategy, **Then** the run reaches the reconciliation verdict (it does not abort on coordination-worktree materialization).
4. **Given** the fixture, **When** a test needs commit attribution, **Then** the fixture can either record it the way the governed workflow does or deliberately omit it (to exercise the refusal).
2. **Given** the fixture configured with a superseding survivor commit, **When** a test runs consolidation, **Then** the planted history is observable on the lane branch exactly as configured.
3. **Given** the fixture, **When** a maintainer reads its documentation, **Then** the documented reason why lanes must be planted before the fixture resolves the coordination workspace matches the observed behaviour (time-boxed: if the cause is in consolidation start, it is filed to the sibling slice rather than fixed here).

### User Story 5 - Attribution is recorded by the real workflow (Priority: P1)

A mixed-lane mission is driven through the real governed workflow — start implementation, hand to review, rework after a rejection, cancel — without any hand-written attribution. Consolidating it must behave as in stories 1 and 2.

**Why this priority**: The gate's verdicts are only as good as the attribution the workflow records; a fixture that writes attribution by hand cannot prove the workflow records it.

**Independent Test**: Drive WP transitions through the CLI in a real repository, commit through the lane worktree between them, cancel one WP, consolidate; observe FAIL for the unsuperseded variant and PASS for the superseded variant.

**Acceptance Scenarios**:

1. **Given** a lane where WP01 and WP02 were driven through the CLI (implement, commit, hand to review; WP02 then canceled) with WP02's files untouched afterwards, **When** the operator consolidates, **Then** the gate returns FAIL naming WP02.
2. **Given** the same history plus a later WP01 rework round that rewrites WP02's files, **When** the operator consolidates, **Then** consolidation exits 0.

### Edge Cases

- A canceled WP's final action on a path is a deletion, and no survivor recreated the path → must not exit 0 with the path deleted.
- A canceled WP touched a path the survivor never touched → the core hole; must not exit 0.
- The canceled WP and a survivor both touched a path, but the canceled WP wrote it last → unsuperseded; must not exit 0.
- A survivor edits *on top of* the canceled WP's changes to a file (keeping part of them) → supersession is judged per path, so this counts as superseded and passes. This is a known residual limitation: the *ideal* outcome (FAIL) is pinned as a strict expected-failure test and handed to a follow-up under the parent epic (out of scope).
- A WP is canceled and later re-opened (forced out of canceled) → it counts as a surviving WP.
- A WP goes through several review rounds (rejected, reworked), including rework that happens after a sibling WP committed to the same lane → all of its commits across rounds are attributed to it; interleaved rework in a lane with three or more WPs attributes cleanly.
- Commits made between governed work sessions (e.g. merges the workflow makes when starting a WP, or an operator's manual commit) are not attributed to the canceled WP and are treated exactly as today.
- A WP canceled without an acceptable-ending record → already fails consolidation today; unchanged.
- A surviving WP added or changed a path and the canceled WP later deleted it or set it back to the original content → the canceled change is compared with the lane content just before it (the pre-state), not with the mission base, so the survivor's approved change being undone must not exit 0.
- The canceled change to a file was merged during consolidation with an independent change to the same file (so the result is neither the canceled content nor the pre-state) → REFUSE: the gate cannot prove the canceled hunk is absent.
- The target branch already carried exactly the canceled content before consolidation (it did not come from this consolidation) → not flagged.
- Workflow merges on the lane (e.g. syncing the lane with the coordination branch) and mission bookkeeping files inside a canceled WP's work session → never counted as the canceled WP's content.
- Two WPs in one lane are in implementation at the same time so a commit cannot be assigned → REFUSE with an actionable message (lane WPs are expected to run in sequence).
- A commit made while the canceled WP was blocked counts as its work; a commit made after its cancellation is not attributed to it (documented limitation).
- Both unsuperseded canceled content and missing attribution are present → REFUSE takes precedence over FAIL.
- A canceled WP entered implementation but made no commits → it has attribution with empty work, so nothing is flagged and the lane passes (a legacy WP without attribution refuses, by design).
- A lane contains only canceled WPs → unchanged: the whole lane is excluded from consolidation, as today.
- A canceled WP never reached implementation (canceled from planned) → nothing to attribute; passes.
- Attribution exists for some WPs in a mixed lane but not for the canceled one → refuse.

## Domain Language

| Term | Meaning in this mission | Avoid |
|------|-------------------------|-------|
| **Mission** | The unit of governed work being consolidated. | "feature" |
| **Work package (WP)** | One unit of work inside a Mission, with its own lifecycle state (planned … approved/done/canceled). | "task" when meaning a WP |
| **Execution lane** | A branch/worktree shared by one or more WPs whose write scopes overlap; WPs in a lane commit to it in sequence. | "lane" when meaning a WP's lifecycle state |
| **Mixed lane** | An execution lane that contains at least one surviving WP and at least one WP canceled with an acceptable-ending record (the consolidation's existing single authority for canceled WPs). A WP canceled *without* that record already fails consolidation loudly today and is unchanged. | — |
| **Surviving WP** | A WP whose final lifecycle state is approved or done (including a WP re-opened after cancellation). | — |
| **Entered implementation** | The WP's lifecycle history contains a transition into `claimed` or `in_progress`. A WP canceled without ever entering implementation has no commits to attribute. | "could have committed" |
| **WP commit attribution** | Evidence, recorded by the governed workflow at the moments a WP's work on its lane starts and stops, that identifies which lane commits a WP made. | "provenance" (in this codebase that word already means the operator's acceptable-ending record on a cancellation) |
| **Canceled content** | For each path, the last change a canceled WP's attributed commits made to it (an addition, a modification, or a deletion). | — |
| **Pre-state** | For a path the canceled WP changed: the path's content on the lane immediately before the canceled WP's first change to it (absent counts as a state). | "base" (the mission's consolidation base can differ from this) |
| **Superseded (path-level)** | A path the canceled WP changed whose final lane content either equals its pre-state (net-zero) or was last changed — including by deletion — by a non-merge, non-bookkeeping commit the canceled WP did not make. Merge commits and mission bookkeeping neither attribute to nor supersede a WP. | "reverted" (supersession need not be a revert) |
| **Reconciliation gate verdicts** | **PASS** — consolidation proceeds; **FAIL** — the gate found content no surviving WP accounts for, and the target is restored; **REFUSE** — the gate cannot evaluate authorship, the target is restored and the message says so. The verdicts are distinguishable in the operator-visible output. | "error", "block" |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record WP commit attribution in the governed workflow | As an operator, I want the governed workflow to record, each time a WP's work on its execution lane starts (including every rework round) and each time it stops (hand to review, cancel), enough evidence to identify the lane commits that WP made, so that the gate can tell WPs in a shared lane apart. | High | Open | [build] | no — SC-006 drives the real workflow with no hand-written attribution and must FAIL; with no recording it would REFUSE instead |
| FR-002 | Attribute lane content per WP, not per lane | As an operator, I want the reconciliation gate to stop counting a canceled WP's attributed commits as approved authorship merely because the WP shares a lane with a surviving WP, so that the canceled sibling's content must be accounted for on its own. | High | Open | [build] | no — today's lane-granular attribution is what passes the canceled content |
| FR-003 | FAIL on unsuperseded canceled content | As an operator, I want consolidation to return a FAIL verdict, restore the target branch to its pre-consolidation commit, and exit non-zero — naming the lane, the canceled WP and every offending path — when a canceled WP's content (addition, modification or deletion) was not superseded, under the default squash strategy and the merge strategy, so that canceled work never ships at exit 0. | High | Open | [build] | no — the red-first repro exits 0 with the canceled content on the target today; the FAIL verdict (not a refusal) is asserted |
| FR-004 | PASS on superseded canceled content | As an operator, I want consolidation to succeed when every path a canceled WP changed is superseded, so that the gate does not reintroduce the mixed-lane false FAIL. | High | Open | [build] | yes — today's gate also passes this shape; the positive control is FR-003's repro on the same fixture builder, which must FAIL while this one PASSes |
| FR-005 | REFUSE when attribution is missing, contradictory, or inconclusive | As an operator, I want consolidation to return a REFUSE verdict — non-zero exit, target restored, message naming the lane and WP and stating the recovery action — whenever a mixed lane contains a canceled WP that entered implementation and the gate cannot establish that WP's attributed commits (evidence absent, unreadable, not in the lane's history, or claiming a commit that another WP's evidence also claims), or when the canceled WP's change to a file was merged with an independent change so its absence cannot be proven, so that missing evidence never degrades into trusting the whole lane. REFUSE takes precedence over FAIL. | High | Open | [build] | no — today the same shape PASSes silently |
| FR-006 | Non-mixed lanes and never-implemented cancellations unchanged | As an operator, I want lanes with no canceled WP, mixed lanes whose canceled WPs never entered implementation, and fully-canceled lanes to consolidate exactly as they do today — including in legacy missions with no attribution at all — so that the new checks add no verdict changes outside mixed lanes with an implemented canceled WP. | High | Open | [ratchet] | yes — by design; guarded by the existing merge-strategy mixed-lane pin plus a default-strategy twin, on the same builders where FR-003/FR-005 repros must fail |
| FR-007 | Mixed-lane fixture with in-fixture planting and attribution | As a maintainer, I want a mixed-lane mission fixture that plants a canceled WP's lane commits (add/modify/delete, and optionally a superseding survivor commit) with or without commit attribution before the coordination workspace is resolved, that consolidates end to end under the default squash strategy and merge, and that cannot accidentally stage its own worktrees into a lane commit, so that mixed-lane reconciliation defects can be reproduced red-first in one builder call. | Medium | Open | [build] | no — no existing builder plants a committed-then-canceled WP, and none records attribution |
| FR-008 | Correct the recorded fixture limitation | As a maintainer, I want the fixture documentation to state what actually breaks a later consolidation (grounding on 2026-09-28 found that the existing mixed-lane builder already consolidates under the default strategy and survives post-build lane ref and worktree mutations; the unmaterialized-coordination abort occurs only when the coordination worktree directory is missing, and staging the repository root captures the worktrees directory), backed by a test that shows both the working post-build mutation and the real trigger, so that future repros do not re-discover or mis-attribute it. | Low | Open | [build] | no — both behaviours are asserted by a test |
| FR-010 | Every REFUSE restores the target | As an operator, I want a reconciliation-gate REFUSE verdict to restore the target branch to its pre-consolidation commit exactly as a FAIL does (compare-and-swap, never overwriting a ref that moved), so that no gate refusal — new or pre-existing — leaves the advanced target in place at a non-zero exit. (The separate post-PASS squash-projection refusal, `_assert_squash_projected_content_landed`, is out of scope and becomes a follow-up.) (Grounding 2026-09-28: today only FAIL rolls back; operator decision `01M3MAB8FTDKKVVTXPREK75AEP`.) | High | Open | [build] | no — a red-first test shows a REFUSE leaving the advanced target today |
| FR-011 | Migration-synthesized events never affect attribution | As an operator, I want lifecycle events synthesized by migrations (e.g. birth-cutover backfill seeds, actor prefix `migration:`) to be ignored when reconstructing WP work windows, so that a first FAIL/REFUSE does not make every later consolidation refuse with an "open window". (Pre-PR squad blocker, 2026-09-29.) | High | Open | [build] | no — a red-first real-CLI test shows FAIL followed by a permanent REFUSE today |
| FR-012 | Operator-attested override for an unresolvable mixed lane | As an operator, I want `spec-kitty consolidate --attest-canceled-superseded <WP> --attest-reason "<text>"` to record an append-only, operator-provenance attestation that the canceled WP's content is absent or superseded, after which the gate evaluates that WP's lane with the pre-change whole-lane behaviour; a FAIL (content the gate can see) is never overridable, infrastructure refusals (unreadable events or git history) are not overridable, and every REFUSE message names the reason and, where applicable, this flag. (Operator decision `01M3NR7QRXJBZXQR1B91XKY3JQ`.) | High | Open | [build] | no — today an unstamped, straddling or late-cancel mixed lane refuses forever |
| FR-013 | Closed-world check on mixed lanes | As an operator, I want consolidation to REFUSE when a mixed lane carries a non-merge, non-bookkeeping commit that falls outside every resolved WP work window, so that commits no governed WP owns (e.g. a straggler after a cancel) cannot ship silently; the decision and its unknown real-world impact are recorded in an ADR due for revision. (Operator decision `01M3NR7XAJGSJCK5YP937KT91H`.) | High | Open | [build] | no — a real-CLI repro shows such a commit landing at exit 0 today |
| FR-009 | Pin the per-path supersession residual | As a maintainer, I want the ideal outcome for a survivor that edits on top of a canceled WP's changes (FAIL) recorded as a strict expected-failure test and named in the gate's documentation, so that the limitation is visible and cannot silently change. | Low | Open | [build] | no — a strict expected failure turns red if the behaviour changes |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate overhead | Per-WP attribution adds no more than 1 second to the reconciliation gate on a mixed lane of 5 WPs and 50 first-parent commits, measured by a dedicated benchmark test built on the new mixed-lane builder. | Performance | Medium | Open |
| NFR-002 | Fail-closed on evidence errors | 100% of attribution read or parse failures in a mixed lane with an implemented canceled WP produce a REFUSE verdict; 0 produce PASS (unlike the existing fail-open acceptable-ending reader, which must not be copied). | Reliability | High | Open |
| NFR-003 | Actionable messages | Every new FAIL and REFUSE message names the lane, the WP id(s) and at least one offending path or the missing evidence, and states one recovery action. | Usability | Medium | Open |
| NFR-004 | Test runtime budget | Each new real-CLI reproduction's test body takes no more than 1.5× the existing mixed-lane repro's body time on the same machine (measured 2026-09-28: ~32 s body, ~39 s fixture setup); the new builder adds no more than one extra consolidation per test. | Maintainability | Medium | Open |
| NFR-005 | Code quality gates | New and touched code passes `ruff check`, `ruff format --check` and `mypy` with zero new findings and keeps every function at cyclomatic complexity ≤ 15; new branches are covered by focused tests (diff coverage ≥ 90%). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No external event-schema change | WP commit attribution must be recorded without changing the `spec_kitty_events` package's schema or version; if that proves impossible, stop and escalate to the operator. | Technical | High | Open |
| C-002 | Single authorship authority | Attribution lives in one canonical, CLI-owned place alongside the WP lifecycle history, and the gate reads it from there; no second parallel record. | Architectural | High | Open |
| C-003 | Strategy-independent fix | The fix corrects the gate's authorship claim, which all consolidation strategies share (squash, merge, rebase). Real-CLI reproductions cover squash and merge; rebase is covered at the claim level. | Technical | High | Open |
| C-004 | Stay off neighbouring missions' seams | Do not change `tests/integration/**`, consolidation start ordering, the `--dry-run` forecast, or resume-marker handling (owned by a sibling slice; listed under Dependencies and References). | Process | High | Open |
| C-005 | Targeted test runs only | Run the targeted test files, the owning module's fast tier and the specific named architectural gates; never a full `tests/architectural/`, integration, e2e or `make test-full` sweep during mission work. | Process | High | Open |
| C-006 | Red-first | Each defect scenario (User Stories 1, 3 and 5) gets a failing reproduction through the real `spec-kitty consolidate` entry point, committed before the fix. | Process | High | Open |
| C-007 | Out of scope | Surfacing the new verdicts in `consolidate --dry-run` (a dry run will forecast clean where the real run refuses or fails), hunk-level supersession, and a dedicated command to back-fill attribution for legacy missions are out of scope and become follow-up issues under the parent epic, filed before the PR. | Scope | Medium | Open |

### Key Entities

- **Work package lifecycle history**: the ordered record of a WP's lifecycle transitions; the source of truth for which WPs are surviving or canceled and whether a WP entered implementation.
- **WP commit attribution**: per-WP evidence, recorded with the lifecycle history, that bounds each of the WP's work sessions on its lane so its commits can be identified.
- **Mixed lane**: an execution lane with ≥1 surviving and ≥1 canceled WP; the only lane shape the new FAIL/REFUSE verdicts apply to.
- **Reconciliation claim**: the gate's statement of which content is approved and which is excluded for a consolidation; after this mission a canceled WP's attributed content is excluded unless superseded.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of the committed-then-canceled mixed-lane reproductions (add, modify, delete × default and merge strategy — 6 cases), the gate returns a FAIL verdict (not a refusal) naming the canceled WP and each offending path, consolidation exits non-zero, and the target ends at its pre-consolidation commit. — [build] · no-op passable: no
- **SC-007**: In 100% of the survivor-undone reproductions (survivor adds a file the canceled WP later deletes; survivor changes a file the canceled WP later sets back to its original content), consolidation does not exit 0. — [build] · no-op passable: no
- **SC-002**: In 100% of the superseded (survivor rewrite, survivor delete, self-revert, workflow merge inside the canceled session) and never-implemented mixed-lane reproductions under both strategies, consolidation exits 0 with the surviving WP's content on the target. — [build] · no-op passable: yes — paired with SC-001 on the same fixture builder as its positive control
- **SC-003**: In 100% of the attribution-missing or attribution-contradictory mixed-lane reproductions, the gate returns a REFUSE verdict naming the lane and WP; 0 such reproductions exit 0. — [build] · no-op passable: no
- **SC-004**: 0 verdict changes outside mixed lanes with an implemented canceled WP: every terminus and reconciliation test that passes on the mission's base still passes, and a legacy all-approved lane with no attribution exits 0 on the same builder where its committed-then-canceled twin refuses. — [ratchet] · no-op passable: yes — guarded by the paired twin that must refuse
- **SC-005**: A maintainer can build a squash-strategy mixed-lane reproduction with the fixture in a single builder call, with no post-build lane mutation. — [build] · no-op passable: no
- **SC-006**: A mixed-lane mission driven through the real CLI transitions (implement, commit, hand to review, rework, cancel) with no hand-written attribution consolidates to FAIL; its twin with a superseding survivor rework consolidates to PASS; reverting either the attribution recording or the gate change alone turns the FAIL case back to a non-FAIL outcome. — [build] · no-op passable: no

## Assumptions

- WPs that share an execution lane do their work on it in sequence through the governed workflow; the transitions that start a work session (entering `in_progress`, including rework), hand to review, and cancel are recorded by the CLI when they happen.
- Commits made on a lane outside any recorded work session of the canceled WP are not attributed to it; they are treated exactly as today.
- Operators recovering from a REFUSE revert the canceled WP's commits on the lane branch through a surviving WP's governed work (which supersedes the paths); no new back-fill command is added in this mission (C-007).
- Missions in flight at upgrade time that have a mixed lane with an implemented canceled WP will refuse at consolidation until recovered; this is the intended fail-closed trade-off.

## Dependencies and References

- Parent epic: #5001.
see #5018 — the false-FAIL direction on a mixed lane and its fix (context only).

see #5048 — architecture residuals sequenced behind this mission (context only).

see #5053 — a distinct attribution axis, not touched (context only).

see #5111, #5110, #5044 — owned by the sibling consolidation-start slice; not touched (context only).

- Enabler first: #5047 (fixture) before #5046 (gate).
