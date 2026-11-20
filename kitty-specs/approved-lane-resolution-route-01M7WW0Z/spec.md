# Mission Specification: Approved-lane conflict resolution route

**Mission Branch**: `kitty/mission-approved-lane-resolution-route-01M7WW0Z` (lands on topic branch `fix/approved-lane-resolution-route`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: Issue #5604 and its recurrence comment, plus the folded issues #7754, #7755, #7767, the merge-commit part of #5721, and #7497. Operator rulings of 2026-11-20 (approach A+B+E; approach C rejected), relayed by the orchestrator. Intent confirmed in DM-01M7WW1RVG4TQ9S2CABCCVK9G9.

## Intent Summary

- **Primary actor:** an operator, or an agent acting for one, running `spec-kitty consolidate` on a Mission whose approved lanes conflict on a shared file.
- **Trigger:** either refusal:
  - the stale-lane refusal (a sibling lane's approved content conflicts with this lane);
  - the reconciliation refusal "belongs to NO approved WP".
- **Desired outcome:** the CLI names one route that works and is reviewed, and following it lands the Mission with exit 0. The route:
  1. incorporate the named sibling lane into the stale lane;
  2. send the work package back;
  3. resolve the conflict;
  4. an independent reviewer reviews it and approves it again;
  5. re-run consolidate.

  An unreviewed resolution is refused before anything changes, with a named message that points at that route.
- **Invariant:** no unreviewed content ever lands.
  - A conflict resolution is new authored content. It counts as approved only when a review approval reaches it.
  - The gate stays fail-closed: a probe error refuses, and no new attestation lifts any verdict.
- **Rejected:** attributing a conflict resolution mechanically, without review (approach C). Unanimous squad finding; operator ruling.

## Background

Today the stale-lane remedy tells the operator to resolve the conflict on the lane and commit. On an approved lane, that commit is a merge made after approval that carries content of its own. The gate leaves such a merge out of the approved claim by design (ADR 2026-09-29-1, Amendment 2026-11-07), so the run lands every lane, then refuses at the gate and rolls back.

The rollback also restores the Mission branch. The remedy's "incorporate changes from the Mission branch" then brings in nothing. The printed re-entry command (`agent action implement`) refuses every approved work package anyway.

Since #7630, a merge that a new review approval reaches is kept and authors what it brought in from approved lanes, so re-review is already the sanctioned exit. No message names it, and no test drives it end to end.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The stale-lane remedy names a route that works for approved lanes (Priority: P1)

An operator runs consolidate. Two approved lanes edit adjacent hunks of one file, so git conflicts. The stale-lane refusal must say:
- which sibling lane holds the content that made this lane stale;
- that the auto-rebase stopped on a conflict, and on which paths;
- the route: send the work package back, merge the sibling lane into this lane and resolve the conflict, have it reviewed and approved again (the new approval must reach the resolution merge), then re-run consolidate.

It never prints a command that refuses an approved work package.

**Why this priority**: the remedy is where operators are sent today, and it leads into a refusal (#5604, #7754, #7755).

**Independent Test**: drive consolidate on the two-lane conflicting fixture and assert on the stale-refusal text, then execute each printed command and assert that none is refused for being approved.

**Acceptance Scenarios**:

1. **Given** two approved lanes whose edits to one file conflict, **When** consolidate refuses the second lane as stale, **Then**:
   - the remedy names the first lane as the sibling to incorporate;
   - it names the conflicted path;
   - it names the send-back, review and re-approval route.
2. **Given** that refusal, **When** the operator runs the commands it prints, in order, **Then** no command refuses because the work package is approved.
3. **Given** a stale lane whose work package is *not* approved (a planning lane, or another caller outside consolidate), **When** the stale remedy is rendered, **Then** today's re-entry command is unchanged.

---

### User Story 2 - The re-review route lands end to end (Priority: P1)

An operator follows the route from User Story 1:
1. sends the work package back;
2. merges the sibling lane into the lane and hand-resolves the conflict;
3. submits it for review;
4. an independent reviewer approves it.

Consolidate then lands the Mission with exit 0 under the default squash strategy and under the merge strategy.

**Why this priority**: this is the one sanctioned exit. It must be proven with real lifecycle commands, not a synthetic approval stamp.

**Independent Test**: one end-to-end test through the real CLI, run once per strategy.

**Acceptance Scenarios**:

1. **Given** the hand-resolved merge and a new independent review approval that reaches it, **When** consolidate runs (fresh run or resume, whichever the remedy prescribes), **Then** it exits 0 and the target holds the resolved content.
2. **Given** the same state under `--strategy merge`, **When** consolidate runs, **Then** it exits 0.
3. **Given** a resolution that also adds a line from neither side and was never re-approved, **When** consolidate runs, **Then** it refuses (negative control N1).
4. **Given** a merge made *after* the re-approval, **When** consolidate runs, **Then** it refuses (negative control N2).

---

### User Story 3 - An unreviewed resolution is refused early and by name (Priority: P1)

Before any branch moves, consolidate finds a merge on an approved lane that is newer than that lane's latest review approval and carries content of its own. It refuses with a named code. The remedy names:
- the merge commit;
- the lane;
- the work package;
- the re-review route.

Merges that consolidate's own auto-rebase made are never refused this way.

**Why this priority**: today the operator learns this only after every lane landed and the run rolled back, through a generic message that suggests a flag that does not apply here.

**Independent Test**: claim-time test on the hand-merge fixture; a control fixture where the only merge on the lane is consolidate's own auto-rebase merge.

**Acceptance Scenarios**:

1. **Given** a post-approval hand merge with its own content on an approved lane, **When** consolidate starts, **Then** it refuses before the first mutation with the named code, and nothing is rolled back because nothing moved.
2. **Given** a post-approval merge that only brings in the parents' content (a clean merge with no own content), **When** consolidate starts, **Then** the named refusal does not fire.
3. **Given** a lane whose only post-approval merge is one consolidate's own auto-rebase recorded, **When** consolidate starts, **Then** the named refusal does not fire, even when that merge resolved a conflict automatically.
4. **Given** a hand merge whose commit message imitates consolidate's auto-rebase message, **When** consolidate starts, **Then** the named refusal fires.

---

### User Story 4 - The reconciliation refusal names the right route (Priority: P2)

The un-attributable path may have been authored by approved lanes, or may reach the target through a merge made after approval. In that case the gate refusal names:
- the re-review route;
- the merge commit, lane and work package.

It does not suggest `--dependency-ref`.

**Why this priority**: the current hint sends operators toward a flag that never applies to Mission work, and that flag has a laundering route of its own (#7766, out of scope here).

**Independent Test**: render the refusal for the hand-merge fixture and for a canceled-content fixture.

**Acceptance Scenarios**:

1. **Given** the #5604 shape reaching the gate, **When** it refuses, **Then** the message names the re-review route with the merge SHA, the lane and the work package, and contains no `--dependency-ref` suggestion.
2. **Given** a canceled-content refusal fixture, **When** it refuses, **Then** the re-review hint is not shown (negative control N4).
3. **Given** foreign content that no approved lane authored, **When** the gate refuses, **Then** the existing message is unchanged.

---

### User Story 5 - The reviewer sees the resolution bytes (Priority: P2)

A reviewer reviews a work package whose review range holds merge commits. The review context shows each merge's own resolution, meaning what the merge changed beyond its parents. It is labelled as operator-authored content to review.

**Why this priority**: the re-approval is the only guard. A plain range diff blends the resolution into the sibling's already-approved content, which can hide a novel line.

**Independent Test**: render the review context for the hand-merge fixture.

**Acceptance Scenarios**:

1. **Given** a review range containing a hand-resolved merge, **When** the review context is rendered, **Then** it shows that merge's resolution, labelled for review.
2. **Given** a git version that cannot show it, **When** the review context is rendered, **Then** it says the resolution cannot be shown. The review proceeds and the gate verdicts are unchanged.
3. **Given** a review range with no merge commits, **When** the review context is rendered, **Then** it is unchanged.

---

### User Story 6 - A rolled-back run leaves the lanes as it found them (Priority: P2)

A consolidate run's auto-rebase merges the Mission branch into a stale lane. The run then fails and rolls back. The rollback undoes that merge on the lane, using compare-and-swap. A lane that moved since the merge is reported, never reset.

The next run and `--resume` do not refuse on lane-tip divergence.

**Why this priority**: today the left-over merge makes `--resume` refuse, and the operator needs `--abort` (#7767).

**Independent Test**: drive a run that auto-rebases a lane and then fails at the gate. Assert the lane tip is back at its pre-run value and that the next run proceeds past the lane-tip check.

**Acceptance Scenarios**:

1. **Given** a run that auto-rebased lane B and then rolled back, **When** the rollback completes, **Then** lane B's tip equals its pre-run tip and the rollback report says so.
2. **Given** lane B moved after the auto-rebase merge (an operator commit), **When** the rollback runs, **Then** lane B is not reset and the report names it with a recovery hint.
3. **Given** the restored state, **When** `consolidate --resume` (or a fresh run) starts, **Then** it does not refuse on lane-tip divergence.

---

### User Story 7 - Local git merge settings cannot forge a clean merge (Priority: P1)

The existing check accepts a clean merge of approved content as attributed. It must fail closed when a clone-local merge attribute or a custom merge driver applies to the path, for example `merge=union` in the repository's info attributes, or a `merge.<name>.driver` in local config.

**Why this priority**: the integrity lens showed that both settings make arbitrary bytes pass as a clean merge of approved content.

**Independent Test**: red attack tests for both bypasses, written first.

**Acceptance Scenarios**:

1. **Given** a conflicting fold and an info-attributes `merge=union` on the path, **When** the check runs, **Then** it does not attribute the result. The gate refuses as it would for a conflict.
2. **Given** a custom merge driver that emits arbitrary bytes, **When** the check runs, **Then** it does not attribute those bytes.
3. **Given** no merge attribute and no driver, **When** the check runs on a clean fold, **Then** today's behaviour is unchanged (positive control).

---

### User Story 8 - Canceled content cannot ride a re-approved dependency lane (Priority: P2)

Suppose:
- a fully-canceled lane's commits were merged into a dependency lane;
- that dependency lane was then approved again over them.

A fresh consolidate must not land the canceled content (#7497).

**Why this priority**: advertising re-approval as the route must not open a bypass for canceled work.

**Independent Test**: red-first test in the intended-verdicts corpus: A approved, C fully canceled and merged into A, A re-approved, fresh consolidate.

**Acceptance Scenarios**:

1. **Given** that state, **When** a fresh consolidate runs, **Then** it refuses and names the canceled content, or the canceled content is excluded from what lands.
2. **Given** the same lanes where A was not re-approved over C's merge, **When** consolidate runs, **Then** today's refusal is unchanged.

---

### Edge Cases

- **Three lanes:** lane-c depends on both conflicting lanes. The remedy and route must cover lane-c too, since lane-c's own merge of the resolved lane is a post-approval merge as well.
- **Clean post-approval merge:** a merge that brings in only already-approved content stays allowed under the #7630 trust model and is not refused by name.
- **Planning lanes and `single_branch` Missions:** the stale remedy for them is unchanged.
- **Git without remerge-diff support:** the named refusal of User Story 3 fails closed (it refuses, naming the git version). The review context only reports that it cannot show the resolution.
- **Probe errors:** any git probe failure in the new checks refuses; it never passes.
- **`orchestrator-api consolidate-mission`:** it gets the claim-time named refusal through the same public entry point the CLI uses. It has no attestation flag.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Approved-lane stale remedy names the re-review route | As an operator, I want the stale-lane refusal for an approved lane to name the send-back, resolve, independent review, re-approve and re-run route, and to state that the new approval must reach the resolution merge. It must never print `agent action implement` for an approved work package, so that the advice I follow does not lead into a refusal (#7754, #5604). | High | Open | [build] | no — today's text prints `implement` and no route; a do-nothing change fails the text assertion and the execute-each-printed-command step |
| FR-002 | Stale remedy names the sibling lane | As an operator, I want the stale refusal to name the sibling lane (or lanes) whose approved content made my lane stale, so that I can still incorporate it after the rollback restored the Mission branch (#7755). | High | Open | [build] | no — today's text names only the Mission branch |
| FR-003 | Auto-rebase halt reason is surfaced | As an operator, I want the stale refusal to say that the in-run auto-rebase stopped on a conflict and to list the conflicted paths, so that I know what has to be resolved (#7755). | Medium | Open | [build] | no — the halt reason is discarded today |
| FR-004 | Claim-time named refusal for an unreviewed resolution merge | As an operator, I want consolidate to refuse before any mutation, with a named code, when a merge on an approved lane is newer than the lane's latest review approval and carries content of its own. The remedy names the merge SHA, the lane, the work package and the re-review route, so that I learn this before anything lands and rolls back (#5721 merge-commit slice). | High | Open | [build] | no — today the run mutates, fails at the gate and rolls back; the assertion on "no branch moved" plus the named code fails on a do-nothing change |
| FR-005 | Consolidate's own auto-rebase merges are not refused | As an operator, I want merges that consolidate's auto-rebase made on my lanes to be recognised by a record the tool keeps, not by commit-message text, so that FR-004 never refuses the tool's own work and a forged message does not escape it. | High | Open | [build] | no — paired controls: a tool-recorded auto-rebase merge passes and a message-forged hand merge refuses, on the same fixture |
| FR-006 | Reconciliation refusal names re-review, not `--dependency-ref`, for this shape | As an operator, I want the un-attributable refusal to name the re-review route with the merge SHA, lane and work package when the path was authored by approved lanes or arrived through a post-approval merge. For this shape it must not suggest `--dependency-ref`, and the hint must not appear on canceled-content refusals (#5604; the hint side of #7766). | Medium | Open | [build] | no — paired with the canceled-content negative control N4 and the unchanged foreign-content message |
| FR-007 | Review context shows merge resolutions | As a reviewer, I want the review context to show each merge commit's own resolution in the review range, labelled as operator-authored content to review, so that a novel line in a resolution is not hidden in a large approved diff. | Medium | Open | [build] | no — today's context shows only the range diff |
| FR-008 | Re-review route proven end to end | As an operator, I want the route of FR-001 proven through the real CLI lifecycle under both squash and merge strategies, with negative controls N1 (novel line, no re-approval, refuses) and N2 (merge after re-approval, refuses), so that the advertised exit is known to work and known not to admit unreviewed content. | High | Open | [build] | no — N1/N2 are same-fixture controls; the positive path is red today because the printed route cannot be followed |
| FR-009 | Rollback undoes the run's own auto-rebase merges on lanes | As an operator, I want a rolled-back run to restore each lane it auto-rebased to its pre-run tip under compare-and-swap, reporting rather than resetting any lane that moved since, so that the next run or `--resume` does not refuse on lane-tip divergence (#7767). | High | Open | [build] | no — today the merge stays and `--resume` refuses |
| FR-010 | Merge-resolution recognizer fails closed on clone-local merge settings | As a maintainer, I want the clean-merge attribution check to refuse to attribute when a clone-local merge attribute or a custom merge driver applies to the path, so that local, unreviewed git settings cannot make arbitrary bytes pass as a clean merge of approved content. | High | Open | [build] | no — red attack tests (union, custom driver) plus a positive control with no attribute |
| FR-011 | Canceled content cannot land via a re-approved dependency lane | As a maintainer, I want a fresh consolidate to refuse (or exclude) a fully-canceled lane's content that reaches the target through a dependency lane approved again over its merged commits. The work starts with a red-first test, and the fix follows if the test is red (#7497). | High | Open | [build] | no — red-first corpus cell; a control cell without re-approval keeps today's verdict |
| FR-012 | #7307 post-approval-merge tests are not vacuous | As a maintainer, I want the post-approval-merge tests to assert the expected refusal code (or the absence of a refusal) instead of returning early on any refusal, so that a change that refuses for another reason cannot pass them. | Medium | Open | [ratchet] | no — a mutated claim that refuses for an unrelated reason must fail the tightened tests |
| FR-013 | ADR amendment records the model | As a maintainer, I want amendments to ADR 2026-10-04-5 and ADR 2026-09-29-1 that record: the #7630 trust model; re-review as the sanctioned exit for a conflict between approved lanes; the FR-004 refusal and its FR-005 discriminator; and the FR-010 fail-closed rule. | Medium | Open | [build] | no — a document review checks each of the four points is stated |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded claim-time cost | The FR-004 check adds at most one git process per merge commit that lies on an approved lane after its latest approval; a lane with no such merge adds zero git processes. | Performance | Medium | Open |
| NFR-002 | Fail-closed probes | 100% of git probe failures in the FR-004, FR-005, FR-009 and FR-010 checks refuse (or, for FR-009, report the lane as not restored); 0 paths treat a probe failure as a pass. | Security | High | Open |
| NFR-003 | Code quality gates | All changed files pass ruff, `ruff format --check --force-exclude` and mypy with zero findings and no new suppressions; every changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-004 | Test discipline | Every behavioural fix lands with a test that was red before the fix (recorded in the work package); the Mission runs `make test-fast` plus the blast radius and only the named architectural gate files it implicates, with no full heavy suites. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No mechanical attribution of conflict resolutions | A conflict resolution is never attributed without a review approval that reaches it (approach C rejected, operator ruling 2026-11-20). | Technical | High | Open |
| C-002 | No new verdict-lifting attestation | No new attestation, flag or override may lift a FAIL or REFUSE verdict; existing attestation semantics are unchanged. | Technical | High | Open |
| C-003 | Keep the post-approval merge rule | The rule that a merge no approval stamp reaches does not author content (#7307) stays; the re-approval route works through it, not around it. | Technical | High | Open |
| C-004 | Re-approval is a real review | The route counts only an unforced, independent review approval (#5721, #6715 rules unchanged); a forced or synthetic approval does not restamp. | Technical | High | Open |
| C-005 | Out of scope | The pre-mutation conflict forecast (approach D′) stays with #7324; fixing the `--dependency-ref` laundering route stays with #7766; #5053, #7749, #3936 and #5722 are cross-referenced only. | Business | Medium | Open |
| C-006 | Canonical surfaces only | Changes use the existing single rollback authority, the existing status lifecycle commands and the existing review context renderer; no parallel second authority is introduced. | Technical | High | Open |

### Key Entities

- **Stale-lane refusal**: the message consolidate prints when a lane must incorporate other content before it can land. It now carries the sibling lane(s), the auto-rebase halt reason and a route.
- **Resolution merge**: a merge commit on an approved lane that carries content beyond what its parents bring in. It is reviewed content only when a review approval stamp reaches it.
- **Auto-rebase merge record**: what consolidate records about the merges its own auto-rebase made. It is used to discriminate tool merges from hand merges, and to undo them at rollback.
- **Named refusal (claim time)**: a refusal code and remedy for an unreviewed resolution merge, raised before any mutation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5604 recurrence shape, an operator who runs only the commands the CLI prints reaches a landed Mission (exit 0) in one send-back and one review cycle, with zero commands refused for an approved work package. — [build] · no-op passable: no
- **SC-002**: 0 of the negative controls N1, N2 and N4 and the two git-setting attacks land unreviewed or canceled content. — [build] · no-op passable: no
- **SC-003**: An unreviewed resolution merge is refused with zero branch movements, before any lane is consolidated, in 100% of test runs. — [build] · no-op passable: no
- **SC-004**: After a rolled-back run, the next run or `--resume` refuses on lane-tip divergence in 0 of the test runs. — [build] · no-op passable: no

## Assumptions

- The re-review route uses the existing lifecycle: moving an approved work package back, then submitting it for review, then an independent approval. The squad traced this transition path in code but has not driven it end to end. FR-008 proves it; if it fails, the gap is fixed in this Mission.
- Remerge-diff support (git ≥ 2.36) is already a requirement of the existing merge own-content probe. The new checks reuse it.
- The sibling-lane naming of FR-002 can be derived from the same run's merge order and overlap computation the stale check already performs.
