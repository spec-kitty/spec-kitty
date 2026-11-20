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
3. **Given** a lane whose only post-approval merge is one an auto-rebase writer recorded, **When** consolidate starts, **Then** the named refusal does not fire. If that merge auto-resolved a conflict in non-bookkeeping content, the gate still judges it (its existing verdict is unchanged).
4. **Given** a hand merge whose commit message imitates the auto-rebase message, **When** consolidate starts, **Then** the named refusal fires.
5. **Given** a hand merge of the Mission branch into the lane (the same parent shape as a tool merge), **When** consolidate starts, **Then** the named refusal fires.
6. **Given** three lanes where a dependent lane's approval stamp reaches the unreviewed merge but the merge's own lane's stamps do not, **When** consolidate starts, **Then** the named refusal fires (same predicate as the gate).

---

### User Story 4 - The reconciliation refusal names the right route (Priority: P2)

The un-attributable path may have been authored by approved lanes, or may reach the target through a merge made after approval. In that case the gate refusal names:
- the re-review route;
- the merge commit, lane and work package.

It does not suggest `--dependency-ref`.

**Why this priority**: the current hint sends operators toward a flag that never applies to Mission work, and that flag has a laundering route of its own (#7766, out of scope here).

**Independent Test**: render the refusal from claim fields for the hand-merge shape (with FR-004 in place the CLI stops earlier, so this is a renderer-level test), for a canceled-content divergence and for a mixed divergence.

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

**Independent Test**: red-first: drive a run that auto-rebases a lane and then fails at the gate, then show the observed harm on the next run (the left-over merge is refused by name or fails the gate). After the fix, assert the lane tip, checkout and lane work-tip record are back at their pre-run values and the next run is not refused because of that merge.

**Acceptance Scenarios**:

1. **Given** a run that auto-rebased lane B and then rolled back, **When** the rollback completes, **Then** lane B's tip equals its pre-run tip and the rollback report says so.
2. **Given** lane B moved after the auto-rebase merge (an operator commit), **When** the rollback runs, **Then** lane B is not reset and the report names it with a recovery hint.
3. **Given** the restored state, **When** `consolidate --resume` (or a fresh run) starts, **Then** it is not refused because of the run's own left-over merge.
4. **Given** an operator commit on the lane made after the rollback, **When** the next run starts, **Then** that commit is judged as today (never reset, never silently accepted).

---

### User Story 7 - Local git merge settings cannot forge a clean merge (Priority: P1)

The existing check accepts a clean merge of approved content as attributed. It must fail closed when a clone-local merge attribute or a custom merge driver applies to the path, for example `merge=union` in the repository's info attributes, or a `merge.<name>.driver` in local config.

**Why this priority**: the integrity lens showed that both settings make arbitrary bytes pass as a clean merge of approved content.

**Independent Test**: red attack tests, written first, for each route (info attributes, an uncommitted working-tree attributes file, a configured attributes file, a custom driver), against the clean-fold recognizer, the claim-time own-content probe and the merge-strategy closed world.

**Acceptance Scenarios**:

1. **Given** a conflicting fold and `merge=union` from any clone-local source on the path (info attributes, an uncommitted attributes file, a configured attributes file, `merge.default`), **When** the check runs, **Then** it does not attribute the result. The gate refuses as it would for a conflict.
2. **Given** a custom merge driver that emits arbitrary bytes, **When** the check runs, **Then** it does not attribute those bytes.
3. **Given** a hand merge with its own resolution and `merge=union` on the path, **When** the claim-time own-content probe runs, **Then** it does not report "no own content"; it refuses.
4. **Given** only spec-kitty's own registered drivers on their registered bookkeeping patterns, **When** consolidate runs, **Then** today's behaviour is unchanged (positive control).
5. **Given** a committed `merge=union` on a path (for example this repository's `kitty-ops/lifecycle.jsonl`), no clone-local source and no configured union driver, on git ≥ 2.40, **When** the check runs, **Then** the committed value is honoured; with a configured driver for that name, or on older git, it refuses.

---

### User Story 8 - Canceled content cannot ride a re-approved dependency lane (Priority: P2)

Suppose:
- a fully-canceled lane's commits were merged into a dependency lane;
- that dependency lane was then approved again over them.

A fresh consolidate must not land the canceled content (#7497).

**Why this priority**: advertising re-approval as the route must not open a bypass for canceled work.

**Independent Test**: red-first test with the existing canceled-dependency builder: A approved, C fully canceled and merged into A, A re-approved with an unforced review approval, fresh consolidate. Preconditions are asserted in the test. If it is green at the base, it stays as a ratchet pin and #7497 is closed with that evidence.

**Acceptance Scenarios**:

1. **Given** that state, **When** a fresh consolidate runs, **Then** it refuses with `CANCELED_REACHABLE_VIA_DEPENDENCY` naming the canceled content.
2. **Given** the same lanes where A was not re-approved over C's merge, **When** consolidate runs, **Then** today's refusal is unchanged.

---

### Edge Cases

- **Three lanes:** lane-c depends on both conflicting lanes. The remedy and route must cover lane-c too, since lane-c's own merge of the resolved lane is a post-approval merge as well.
- **Clean post-approval merge:** a merge that brings in only already-approved content stays allowed under the #7630 trust model and is not refused by name.
- **Planning lanes and `single_branch` Missions:** the stale remedy for them is unchanged.
- **Git without remerge-diff support:** the named refusal of User Story 3 fails closed (it refuses, naming the git version). The review context only reports that it cannot show the resolution.
- **Probe errors:** any git probe failure in the new verdict-bearing checks (FR-004, FR-005, FR-009, FR-010) refuses; it never passes. The advisory stale remedy (FR-002) includes a sibling whose probe failed rather than hide it (over-inclusion in advice only, never in a verdict).
- **`done` work packages:** sending a `done` work package back needs `--force`; the remedy says so when it applies.
- **Records from earlier releases:** a lane merge an earlier release's auto-rebase left with no record is treated as a hand merge by FR-004 (it refuses by name only if it carries its own content; otherwise nothing fires).
- **Residual by design:** a novel line in a resolution that the independent reviewer approved lands; the review is the guard (FR-007 makes the resolution visible).
- **`orchestrator-api consolidate-mission`:** it gets the claim-time named refusal through the same public entry point the CLI uses. It has no attestation flag.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Approved-lane stale remedy prints a runnable re-review route | As an operator, I want the stale-lane refusal for a code lane whose work packages are approved to print, as runnable commands: send the work package back; incorporate the named sibling lane at its approval stamp into my lane with `spec-kitty agent action implement <WP> --mission <m> --incorporate <lane>`, which stops on a conflict for hand resolution (operator ruling DM-01M7WX8AX56E23AXBZRWGNX4EM: option b; the no-raw-git-recipe rule of #7285 stays); after resolving, submit for review; re-run consolidate. It states that the new approval must be an independent review that reaches the resolution merge, and never prints `agent action implement` alone for an approved work package (#7754, #5604). | High | Open | [build] | no — the test asserts each command is present and executes each in order on the conflicting fixture; a prose-only or unchanged remedy fails |
| FR-002 | Stale remedy names exactly the sibling lane(s) | As an operator, I want the stale refusal to name the sibling lane (or lanes) whose approved content conflicts with my lane, and no other lane, so that I can still incorporate it after the rollback restored the Mission branch (#7755). | High | Open | [build] | no — three-lane control: a third, non-overlapping lane must not be named |
| FR-003 | Auto-rebase halt reason is surfaced | As an operator, I want the stale refusal to say why the in-run auto-rebase did not refresh my lane: a conflict (listing exactly the conflicted paths), a missing lane checkout, or a merge left in progress (#7755). | Medium | Open | [build] | no — the conflicted-path list is compared exactly; a non-conflicting overlapping path is not listed |
| FR-004 | Claim-time named refusal for an unreviewed resolution merge | As an operator, I want consolidate (and `orchestrator-api consolidate-mission` and `--dry-run`) to refuse before any mutation, with a new named code in the existing approved-bound refusal family, when a merge on an approved code lane is reached by none of that lane's own approval stamps (the same predicate the gate uses to drop unreviewed merges, shared, not re-implemented) and carries non-bookkeeping content of its own. The remedy names the merge SHA, the lane, the work package and the re-review route (#5721 merge-commit slice). | High | Open | [build] | no — asserts the named code and that no branch moved; a predicate-agreement test pins that claim and gate classify the same merges |
| FR-005 | Consolidate's own auto-rebase merges are recognised by a durable tool record | As an operator, I want every merge an auto-rebase writer makes on a lane (consolidate, `orchestrator-api`, the implement sync point) to be recorded by the tool in a durable record that outlives `--abort`, re-baseline and run end. FR-004 does not refuse a recorded merge. The record never exempts anything at the reconciliation gate. | High | Open | [build] | no — controls on one fixture: a recorded tool merge is not refused by FR-004; a hand merge whose message imitates the tool and a hand merge of the Mission branch into the lane (same parent shape) are refused |
| FR-006 | Reconciliation refusal names re-review, not `--dependency-ref`, for this shape | As an operator, I want the un-attributable refusal, when the un-attributable blob is content a dropped (unreviewed) post-approval merge brought in, to name the re-review route with the merge SHA, lane and work package, without suggesting `--dependency-ref`. It uses the existing hint channel, and the divergence description itself is unchanged (#5604; the hint side of #7766). | Medium | Open | [build] | no — renderer-level test on the claim fields; controls: canceled-content and mixed divergences show no re-review hint (N4), foreign content keeps today's message |
| FR-007 | Review context points at each merge resolution | As a reviewer, I want the review range owner to list every merge commit in a work package's review range (without history simplification), and the review context to print, per merge, a labelled `git show --remerge-diff <sha>` command marked as operator-authored content to review. The context still prints commands only, never patch text. | Medium | Open | [build] | no — a range with a hand merge lists it; a range without merges is unchanged |
| FR-008 | Re-review route proven end to end | As an operator, I want the route of FR-001 proven through the real CLI with unforced transitions by distinct implementer and reviewer identities, under both squash and merge strategies, with negative controls: N1 (novel line, no re-approval) refuses; N2 (merge after the re-approval) refuses; N3 (forced or self re-approval) refuses. Includes a three-lane variant where a dependent lane also incorporates the resolved lane. | High | Open | [build] | no — red today (the printed route cannot be followed); N1–N3 are same-fixture controls |
| FR-009 | Rollback undoes the run's own auto-rebase merges on lanes | As an operator, I want a rolled-back run to restore each lane from this run's recorded auto-rebase move, under compare-and-swap and inside the single rollback authority, resyncing the lane checkout and resetting the lane work-tip record. A lane that moved since is not reset; it is reported as a new not-restored outcome, its record is kept, and the next run can still act on it (#7767). | High | Open | [build] | no — red-first on the observed harm (the left-over merge is refused by FR-004 or fails the gate on the next run); control: a foreign lane commit made after rollback is neither reset nor silently accepted |
| FR-010 | Merge probes fail closed on effective merge attributes and drivers | As a maintainer, I want every merge probe the gate and claim rely on (the clean-fold recognizer and the own-content remerge probe) to refuse to attribute or classify when the effective merge attribute for a path is anything other than: unspecified or unset; plain `set` (git's built-in merge); spec-kitty's own registered drivers on their registered bookkeeping patterns; or a built-in `union`/`set` value that comes from the committed tree (it equals `git check-attr --source <pre-run target tip>`, no clone-local source sets a merge attribute for the path, no `merge.<name>.driver` is configured for that name, and git ≥ 2.40). Clone-local sources (info attributes, an uncommitted working-tree attributes file, a configured attributes file, `merge.default`, a custom driver in any config scope) always refuse (operator ruling 2026-11-20, option (a)). | High | Open | [build] | no — red attack tests for each clone-local route and for `merge=binary` with a custom driver, against the fold recognizer, against FR-004 and against the merge-strategy closed world; positive controls: spec-kitty's own drivers, and a committed `union` honoured under the stated conditions |
| FR-011 | Canceled content cannot land via a re-approved dependency lane | As a maintainer, I want a red-first test (built with the existing canceled-dependency builder) of: lane A approved, lane C fully canceled and merged into A, A re-approved with an unforced review approval whose stamp descends from that merge, then a fresh consolidate. The test asserts these preconditions and expects `CANCELED_REACHABLE_VIA_DEPENDENCY`. If it is red, it is fixed in this Mission; if green at the base, it becomes a [ratchet] pin and #7497 is closed with that evidence (#7497). | High | Open | [build] | yes if green at the base (then the row is a ratchet pin, stated in the issue matrix); no if red |
| FR-012 | #7307 post-approval-merge tests are not vacuous | As a maintainer, I want the post-approval-merge tests to assert the expected refusal code (or the absence of a refusal) instead of returning early on any refusal, and to keep at least one assertion that exercises the gate's own unreviewed-merge rule with the FR-004 claim check bypassed. The strict residual xfail that pins the post-approval-merge shape is converted when FR-004 turns it green. | Medium | Open | [ratchet] | no — a claim mutated to refuse for an unrelated reason must fail the tightened tests |
| FR-013 | ADR and doc amendments record the model | As a maintainer, I want amendments to: ADR 2026-10-04-5 (re-review as the sanctioned exit; the FR-004 refusal and FR-005 record); ADR 2026-09-29-1 (the #7630 trust model; FR-010 fail-closed rule); ADR 2026-09-19-1 (lanes restorable from the run's own recorded auto-rebase move, FR-009); ADR 2026-11-08-2 and the review-context contract (FR-007); the stale-remedy rule of #7285 if the ruling changes it; and the CLAUDE.md residual sentence about auto-rebase merges surviving a rollback. | Medium | Open | [build] | no — a document review checks each listed point |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded claim-time cost | Beyond the merge enumeration the approved bound already performs, each merge on an approved lane that no own stamp reaches costs at most one own-content probe, three attribute queries (effective, committed-source, empty-tree) and two changed-path listings; the git version is read once per run. A Mission with no such merge adds none of these. | Performance | Medium | Open |
| NFR-002 | Fail-closed probes | 100% of git probe failures in the FR-004, FR-005, FR-009 and FR-010 checks refuse (or, for FR-009, report the lane as not restored and keep its record); 0 paths treat a probe failure as a pass. | Security | High | Open |
| NFR-003 | Code quality gates | All changed files pass ruff, `ruff format --check --force-exclude` and mypy with zero findings and no new suppressions; every changed function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-004 | Test discipline | Every behavioural fix lands with a test that was red before the fix (recorded in the work package); the Mission runs `make test-fast` plus the blast radius and only the named architectural gate files it implicates, with no full heavy suites. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No mechanical attribution of conflict resolutions | A conflict resolution is never attributed without a review approval that reaches it (approach C rejected, operator ruling 2026-11-20). | Technical | High | Open |
| C-002 | No new verdict-lifting attestation | No new attestation, flag, record or override may lift a FAIL or REFUSE verdict at the gate; existing attestation semantics are unchanged. | Technical | High | Open |
| C-003 | Keep the post-approval merge rule | The rule that a merge no approval stamp reaches does not author content (#7307) stays; the re-approval route works through it, and FR-004 reuses it rather than redefining it. | Technical | High | Open |
| C-004 | Re-approval is a real review | The route counts only an unforced, independent review approval (#5721, #6715 rules unchanged); a forced or synthetic approval does not restamp. | Technical | High | Open |
| C-005 | Out of scope | The pre-mutation conflict forecast (approach D′) stays with #7324; fixing the `--dependency-ref` laundering route stays with #7766; #5053, #7749, #3936 and #5722 are cross-referenced only. | Business | Medium | Open |
| C-006 | Canonical surfaces only | Changes extend the existing single rollback authority, refusal renderer, merge probes, review range owner, status lifecycle commands and lane sync point; no parallel second authority is introduced. | Technical | High | Open |
| C-007 | Contract versioning | A new refusal code on `orchestrator-api` bumps its contract version and is listed in its preflight error codes. | Technical | Medium | Open |

### Key Entities

- **Stale-lane refusal**: the message consolidate prints when a lane must incorporate other content before it can land. It now carries the sibling lane(s), the auto-rebase halt reason and a route.
- **Resolution merge**: a merge commit on an approved lane that carries content beyond what its parents bring in. It is reviewed content only when a review approval stamp reaches it.
- **Auto-rebase merge record**: a durable, tool-written record of the merges an auto-rebase writer made on a lane. It discriminates tool merges from hand merges for FR-004 only, and tells the rollback which lane moves are this run's to undo.
- **Named refusal (claim time)**: a refusal code and remedy for an unreviewed resolution merge, raised before any mutation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5604 recurrence shape, an operator who runs the commands the CLI prints, plus the hand resolution and the independent review, reaches a landed Mission (exit 0) with one send-back and review cycle per conflicting lane, and zero printed commands refused for an approved work package. — [build] · no-op passable: no
- **SC-002**: 0 of the negative controls N1–N4 and the FR-010 attacks (info attributes, uncommitted attributes file, configured attributes file, `merge.default`, custom driver, `merge=binary` with a custom driver) land unreviewed or canceled content; at least the info-attributes attack also runs through the real CLI. — [build] · no-op passable: no
- **SC-003**: An unreviewed resolution merge is refused with zero branch movements, before any lane is consolidated, in 100% of test runs. — [build] · no-op passable: no
- **SC-004**: After a rolled-back run, the next run or `--resume` refuses on lane-tip divergence in 0 of the test runs. — [build] · no-op passable: no

## Assumptions

- The re-review route uses the existing lifecycle: moving an approved work package back, then submitting it for review, then an independent approval. The squad traced this transition path in code but has not driven it end to end. FR-008 proves it; if it fails, the gap is fixed in this Mission.
- Remerge-diff support (git ≥ 2.36) is already a requirement of the existing merge own-content probe. The new checks reuse it.
- The sibling-lane naming of FR-002 can be derived from the same run's merge order and overlap computation the stale check already performs.
