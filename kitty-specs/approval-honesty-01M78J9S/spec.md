# Mission Specification: Approval honesty: no fabricated reviewer or review cycle

**Mission Branch**: `kitty/mission-approval-honesty-01M78J9S` (lands on `fix/3044-approval-honesty`)
**Created**: 2026-11-12
**Status**: Draft
**Input**: Operator brief: deliver the "approval honesty" slice of epic #3044, "no path may fabricate a verdict nobody authored". Core issues: #7569, #7571, #7570, #7573. Scope and design were set by four operator rulings recorded as decisions `scope`, `reviewer_identity`, `claimant_mismatch` and `review_cycles` (2026-11-12). Grounding: `research/code-grounding.md`, `research/foldable-issues.md`.

## Intent Summary (confirmed)

- **Primary actor:** a reviewing agent (or human reviewer) recording a verdict with `spec-kitty agent tasks move-task <WP> --to approved`. Secondary actors are a supervising orchestrator driving the same command, and the operator forcing a move.
- **Trigger:** a work package leaves review as approved, or moves on from approved to done.
- **Desired outcome:** every record of that approval names the identity that actually asserted or claimed the review. This covers the status event's actor, its review result, its evidence and its policy metadata, as well as the review-cycle artifact. One review produces exactly one review cycle. A cited review cycle exists.
- **Rule that always holds:** the CLI never invents a reviewer. A name is never taken from the git configuration, and a reference is never minted as a synthetic token. When no real identity exists, the approval is refused. A forced move is recorded as forced, never as a review.
- **Main exception:** a supervisor (or any other identity) tries to approve a work package that a different identity claimed for review. The approval is refused, and the refusal names how to re-claim the review.

Discovery was replaced by the research squad plus the operator rulings above (brief-intake mode, comprehensive brief). The operator's answers to the escalation are the confirmation of this summary.

## Domain Language

| Canonical term | Meaning | Avoid |
|---|---|---|
| **review claimant** | The identity on the most recent unforced move into `in_review` (`agent action review <WP> --agent <id>`) | "current reviewer" (ambiguous) |
| **asserted identity** | An identity the caller passes explicitly (`--agent`, `--reviewer`) | "detected reviewer" |
| **reviewer of record** | The single identity the approval records in every field | "reviewer name" (it may have been a git user) |
| **review cycle** | One `review-cycle-N.md` artifact holding one review verdict | "render" when it means the artifact |
| **synthetic reference** | A machine-minted token standing in for a review pointer (`auto-approval:…`) | — |
| **forced move** | A transition made with `--force`; it is never a review | "forced review" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The approval names its real reviewer (Priority: P1)

A reviewing agent claims a work package with `agent action review WP01 --agent claude:sonnet:reviewer-renata:reviewer` and then approves it with `move-task WP01 --to approved`, with or without repeating `--agent`. Today the approval event records the git user name (for example "Claude" or the operator's own name) as reviewer, and a synthetic `auto-approval:WP01:<date>` reference. After the fix, every identity field of the approval names the claimant, and the reference points at the real review cycle.

**Why this priority**: #7569 (P1). Fabricated reviewers are on most recent approvals in this repository (931 of 1,390 since 2026-09-18). They also propagate into the committed acceptance matrix.

**Independent Test**: Drive `agent action review` and then `move-task --to approved` against a fixture Mission, in a repository whose git `user.name` is a distinctive human-looking name. Assert that this name appears nowhere in the resulting status event or review-cycle artifact.

**Acceptance Scenarios**:

1. **Given** WP01 was claimed for review by identity R and git `user.name` is "Pat Example", **When** `move-task WP01 --to approved` runs without `--agent` or `--reviewer`, **Then** the event's actor, review-result reviewer, evidence reviewer and policy-metadata tool all equal R, and "Pat Example" appears in none of them.
2. **Given** the same setup, **When** the approval is recorded, **Then** its reference is the `review-cycle://` pointer to the review cycle holding this approval, and no `auto-approval:` token is written anywhere.
3. **Given** WP01 has no review claim and no `--agent` or `--reviewer` is passed, **When** an unforced `move-task WP01 --to approved` runs, **Then** it is refused, nothing is written, and the refusal names the command that records a review claim.
4. **Given** WP01 was approved by R, **When** `move-task WP01 --to done` runs, **Then** the done event carries R and the approval's reference forward, and no git name or synthetic token is introduced.

---

### User Story 2 - Only the claimant can approve (Priority: P1)

A supervising orchestrator runs `move-task WP11 --to approved --agent kitty-orchestrator` on a work package that reviewer R claimed. Today this is accepted. The supervisor becomes the actor and the review cycle's `reviewer_agent`, and the ledger carries yet another identity. After the fix, the unforced approval is refused because the approver is not the claimant.

**Why this priority**: #7573. A supervisor approving another identity's review is a fabricated verdict.

**Independent Test**: Claim with identity R, then approve with `--agent S` where S is not R. Assert the refusal, its code and remedy, and that nothing was written.

**Acceptance Scenarios**:

1. **Given** WP11 was claimed by R, **When** an unforced `move-task WP11 --to approved --agent S` runs with S different from R, **Then** it is refused naming both identities and the remedy `spec-kitty agent action review WP11 --agent <id>` (re-claim). No event or review cycle is written.
2. **Given** the same, **When** `--reviewer S` is passed instead of `--agent S`, **Then** the same refusal applies.
3. **Given** WP11 was claimed by R, **When** `move-task WP11 --to approved --agent R` runs, **Then** it succeeds as in Story 1.
4. **Given** WP11 was claimed by R, **When** the operator runs `move-task WP11 --to approved --force --agent S`, **Then** the move is recorded as forced with reviewer S and reference `force-override`. It is never recorded as a review approval, and no review cycle attributed to S as a reviewer is written.

---

### User Story 3 - One review is one review cycle (Priority: P2)

Reviewer R writes their verdict into `review-cycle-2.md` (verdict approved) after claiming WP01, then runs `move-task WP01 --to approved`. Today move-task writes its own `review-cycle-3.md` ("Approved by R: approval:WP01"), so one review is counted as two cycles. After the fix, the approval adopts cycle 2 and writes no new cycle.

**Why this priority**: #7571 (16 work packages in 11 local Missions). It also answers #6709's open questions about approval-time cycle writes, and #3451 if that issue reproduces with the same cause.

**Independent Test**: Write an approved review cycle after the claim, approve, and assert that the cycle count is unchanged and the event references the existing cycle.

**Acceptance Scenarios**:

1. **Given** R claimed WP01 and then wrote an approved `review-cycle-2.md` attributed to R, **When** R approves, **Then** no `review-cycle-3.md` exists afterwards and the approval references `review-cycle-2.md`.
2. **Given** R claimed WP01 and wrote no review cycle since the claim, **When** R approves, **Then** exactly one new review cycle is written, attributed to R, and referenced. This is the current behaviour, kept.
3. **Given** an approved cycle was written *before* the latest claim (for example cycle 1 approved, then cycle 2 rejected, then a new claim), **When** R approves, **Then** cycle 1 is not adopted, a new cycle is written, and the reference does not point behind the latest rejection.
4. **Given** WP01 is already approved, **When** it moves `approved -> done`, **Then** no review cycle is written.

---

### User Story 4 - A cited review cycle must exist (Priority: P2)

A reviewer approves with `--note "cycle 4 APPROVE"` or `--approval-ref review-cycle://…/review-cycle-4.md` while only `review-cycle-1.md` exists. Today the approval is accepted. After the fix, it is refused and the refusal names the missing path.

**Why this priority**: #7570 (75 such approvals locally).

**Independent Test**: Approve citing a cycle that does not exist, and assert the refusal. Approve citing one that does exist, and assert success.

**Acceptance Scenarios**:

1. **Given** WP04 has only `review-cycle-1.md`, **When** an approval passes `--approval-ref` as a `review-cycle://` pointer to cycle 4, **Then** it is refused, naming the expected path, and nothing is written.
2. **Given** the same, **When** an approval's `--note` or `--approval-ref` text cites "cycle 4", **Then** it is refused in the same way.
3. **Given** WP04 has an approved `review-cycle-4.md`, **When** an approval cites cycle 4, **Then** it succeeds and references that artifact.
4. **Given** a `review-cycle://` pointer that resolves but whose verdict is not approved, **When** it is cited as the approval reference, **Then** the approval is refused.

---

### User Story 5 - Shipped guidance teaches the honest command (Priority: P3)

An agent following the shipped `spk-run-verdict-capture` skill, or the approval hint printed by `spec-kitty next`, is shown an approve command that passes its identity (`--agent <identity>`). It is no longer shown a command that leaves the identity to be detected.

**Why this priority**: These are the routes by which agents learn the approval command. Leaving them stale reintroduces refusals and confusion.

**Independent Test**: Render the hint and read the skill text; assert the approve command carries `--agent`.

**Acceptance Scenarios**:

1. **Given** the `spk-run-verdict-capture` skill, **When** it shows the approve command, **Then** that command includes `--agent <identity>` and does not imply that the reviewer is auto-detected.
2. **Given** `spec-kitty next` prints its approval hint, **Then** the hint includes `--agent`.

### Edge Cases

- **Approval leaving `in_review` vs a direct approval.** An unforced approval from `for_review` or `in_progress`, with no claim, needs an asserted identity (`--agent` or `--reviewer`). The approval is refused without one (Story 1, scenario 3). With one, the existing independence check against the implementer still applies.
- **`--reviewer` and `--agent` both passed and different, on an unforced approval out of `in_review`.** Both must equal the claimant, or the approval is refused (Story 2).
- **Identity comparison.** "Equal to the claimant" uses the repository's existing segment-wise identity rules. It accepts the same identity written with or without trailing empty segments. It never accepts a different tool or profile.
- **Arbiter override.** It records the arbiter's asserted identity and the arbiter decision's own reference. It never records a git name or a synthetic token.
- **`approved -> done` with no recorded approval** (a forced done). It follows the forced-move rule: reviewer = the forcing actor, reference `force-override`.
- **`--no-auto-commit` and a damaged approval slot.** The reviewer of record and the reference are the same as on the default path. The honesty does not depend on whether the cycle write was durable.
- **Feedback file on an already-approved work package, damaged verdict slot, empty feedback file on approval (#6709).** Today's warn-and-continue behaviour is kept unchanged. No new review cycle is written for an already-approved work package.
- **Historical records.** Existing event logs and review cycles are not rewritten (append-only). Readers keep accepting old `auto-approval:` references as historical.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One reviewer of record | As a reviewer, I want every identity field of an approval (event actor, review result, evidence, policy-metadata tool, review-cycle `reviewer_agent`) to name the same reviewer of record, resolved as `--reviewer`/`--agent`, else the review claimant, so that the ledger never contradicts itself. | High | Open | [build] | no — the fixture's git `user.name` is distinctive and asserted absent |
| FR-002 | Never the git user | As an operator, I want the approval path never to read the git `user.name` as a reviewer identity, so that a human who did not review is never named as reviewer. | High | Open | [build] | no — same distinctive git name, positive control is the claimant appearing |
| FR-003 | No synthetic reference | As an auditor, I want an approval's reference to be the `review-cycle://` pointer of its review cycle, or a validated caller reference, or `force-override` for a forced move, and never a newly minted `auto-approval:` token, so that every reference points at real evidence. | High | Open | [build] | no — asserts the pointer resolves to an existing file |
| FR-004 | Refuse an approval with no identity | As an operator, I want an unforced approval with no asserted identity and no review claim refused, writing nothing, with a remedy naming how to claim the review, so that no approval is recorded without a reviewer. | High | Open | [build] | no — paired with the claimed-and-approved success case on the same fixture |
| FR-005 | Approver must be the claimant | As an operator, I want an unforced approval out of `in_review` refused when its asserted identity is not the review claimant, naming both identities and the re-claim command, so that a supervisor cannot approve another identity's review. | High | Open | [build] | no — paired with the claimant-approves success case |
| FR-006 | Forced moves are not reviews | As an auditor, I want a forced approval recorded with the forcing actor's identity and reference `force-override`, never as a review approval and never with a fabricated reviewer, so that forced moves stay distinguishable. | Medium | Open | [build] | no — asserts reviewer equals the passed `--agent` and reference equals `force-override` |
| FR-007 | Done carries the approval forward | As an auditor, I want `approved -> done` (and the arbiter-override path) to carry the reviewer and reference of the approval it follows, introducing no new identity or token, so that the done record matches the approval. | Medium | Open | [build] | no — asserts the done event's reviewer equals the approval's |
| FR-008 | Adopt the reviewer's cycle | As a reviewer, I want an approval to adopt the approved review cycle that I wrote after the latest review claim, instead of writing a second one, so that one review is one cycle. | High | Open | [build] | no — asserts the cycle count is unchanged and the reference names the existing cycle |
| FR-009 | Never adopt a stale cycle | As a reviewer, I want a review cycle written before the latest review claim never adopted, so that an approval never points behind a later rejection. | Medium | Open | [build] | no — fixture has an older approved cycle that must not be referenced |
| FR-010 | Cited cycle must exist | As an auditor, I want an approval whose `--approval-ref` is a `review-cycle://` pointer, or whose note or reference text cites "cycle N", refused when that work package's `review-cycle-N.md` does not exist or is not an approved verdict, naming the expected path, so that cited evidence is real. | Medium | Open | [build] | no — paired with the existing-cycle success case |
| FR-011 | Shipped guidance passes identity | As an agent, I want the `spk-run-verdict-capture` skill and the `spec-kitty next` approval hint to show the approve command with `--agent <identity>`, so that following the guidance records an honest approval. | Low | Open | [build] | no — asserts the rendered text contains `--agent` |
| FR-012 | #6709 edge semantics settled | As an operator, I want an approval-time feedback file on an already-approved work package, a damaged verdict slot, and an empty feedback file on approval to keep today's warn-and-continue behaviour, writing no new review cycle for an already-approved work package, so that #6709's open questions are answered without changing any refusal. | Low | Open | [ratchet] | yes — pins existing behaviour; positive control is the existing #6696 tests |
| FR-013 | Review-cycle writer is named for what it does | As a maintainer, I want the review-cycle writer that writes both approvals and rejections named for that, with the old name kept as an alias, so that #6709's rename item is done without breaking callers. | Low | Open | [build] | yes — a pure rename; covered by existing writer tests |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No slower approvals | A `move-task --to approved` run on the existing CLI test fixtures takes at most 10% longer (wall time, median of 5 runs) than on the base commit. | Performance | Medium | Open |
| NFR-002 | Clean static checks | Changed code passes `ruff check`, `ruff format --check --force-exclude` and `mypy` with 0 findings and no new suppressions. No touched function exceeds cyclomatic complexity 15. | Maintainability | High | Open |
| NFR-003 | Refusals write nothing | For 100% of the new refusal paths, the status event log, the review-cycle files and the git index are byte-identical before and after the refused command. | Reliability | High | Open |
| NFR-004 | Coverage of new code | New and changed lines reach at least 90% line coverage in the mission's targeted tests (the diff-cover gate). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No events-schema change | The status event schema and the `spec-kitty-events` contracts are unchanged. The reviewer stays a required, non-empty field. | Technical | High | Open |
| C-002 | Append-only history | Existing event logs and review-cycle artifacts are neither rewritten nor backfilled. Readers keep accepting historical `auto-approval:` references. | Technical | High | Open |
| C-003 | Stay out of in-flight files | No edits to `cli/commands/agent/workflow.py`, `workflow_cores.py` or `workflow_executor.py` (open PR #7596), and no change to where review-cycle artifacts are placed (#7546). | Process | High | Open |
| C-004 | Consolidation untouched | No change to consolidation verdict logic (`consolidation/approved_bound.py`, `wp_evidence.py`, `preflight.py`, `done_bookkeeping.py`). #5721 is Refs only. | Technical | High | Open |
| C-005 | Packs edited upstream | No edits under `packs/built-in/` or `packs/internal/`. The open-packs review prompt is fixed through an upstream issue. | Process | High | Open |
| C-006 | No new size or ratchet gates | The fix closes defect classes by construction (removal of the fabricating code path). It adds no new size, allowlist or ratchet gate. | Process | Medium | Open |
| C-007 | Review independence and the approval bound are not weakened | The existing implementer-independence refusal and the approval-stamp bound (ADR `2026-10-04-5`) keep their current behaviour. This mission only adds refusals. | Technical | High | Open |
| C-008 | Refusal grammar | New refusals follow the existing move-task refusal shape (code, what was refused, why, the next command). Their codes are named in the plan and added to the ADR amendment. | Technical | Medium | Open |

### Key Entities

- **Approval record**: the status event of an approval hop. It holds the actor, the review result (reviewer, verdict, reference), the evidence review triple, and policy metadata (tool, model, profile).
- **Review claim**: the most recent unforced move of a work package into `in_review`. Its actor is the review claimant.
- **Review cycle**: `tasks/<WP>/review-cycle-N.md`, with frontmatter holding `reviewer_agent`, verdict and cycle number. It is addressed by a `review-cycle://` pointer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an end-to-end run of claim → approve → done, the git `user.name` of the repository appears in 0 approval-related fields or artifacts. — [build] · no-op passable: no
- **SC-002**: Across the approval paths exercised by the mission's tests (unforced, `--no-auto-commit`, forced, `approved -> done`, arbiter override), 0 newly written records carry an `auto-approval:` token. — [build] · no-op passable: no
- **SC-003**: One claimed review followed by one approval yields exactly 1 review cycle, both when the reviewer wrote the cycle and when they did not. — [build] · no-op passable: no
- **SC-004**: 100% of approvals that cite a non-existent cycle, come from a non-claimant, or carry no identity are refused, with nothing written. — [build] · no-op passable: no
- **SC-005**: #7569, #7571, #7570, #7573 and #6709 are each closed by the mission's pull request with a passing reproduction test. #3451 is closed only if its reproduction shows the same cause. — [build] · no-op passable: no

## Scope

**In scope:** the `move-task` approval and done paths and the review-cycle write they trigger; the identity of the arbiter-override record; the `spk-run-verdict-capture` skill text in core; the `spec-kitty next` approval hint; #6709's edge semantics and rename.

**Out of scope (follow-up issues filed by this mission):**
- consolidation done-bookkeeping (git-user actor, and the `lane-approved:` / `snapshot-review:` references);
- `agent status emit` and `orchestrator-api transition`, which accept any asserted reviewer;
- the open-packs review prompt (`--actor <name>`);
- a doctor report that flags historical fabricated approvals;
- lane-tip citations in approval notes (#7570's secondary ask).

## Assumptions

- Agents record review claims with `agent action review <WP> --agent <identity>`, which already requires `--agent`. A move-task approval without one therefore relies on `--agent` or `--reviewer`.
- Refusing approvals with no identity changes behaviour for scripts and tests that approved without one. The operator accepted this in the `reviewer_identity` ruling. Tests that pin the old fallback are re-pinned, not deleted.
- The "cycle N" citation check reads only explicit "cycle N" forms (for example "cycle 4", "cycle-4", "review-cycle-4"). Other prose is not interpreted.
- #3451's counter is the review-cycle number. If its reproduction on the base commit shows another counter, #3451 stays open as Refs.
