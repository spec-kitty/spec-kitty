# Mission Specification: Coord/lane actor-identity representation cluster

**Mission Branch**: `fix/actor-identity-representation`
**Created**: 2026-09-18
**Status**: Draft
**Input**: User description: "Coord/lane actor-identity representation cluster — fix #4665, #4670, #4673, #3029"

## Overview

An agent's identity — the tool, model, profile, and role that acted — is recorded on a
work package in more than one place and in two different shapes: a **structured** form
(the four fields separately) and a **compact-string** form (`tool:model:profile:role`).
Those two shapes do not reconcile when the system asks "who owns this work package?", and
the review/ownership surfaces read the wrong recorded slot. Four observable defects follow,
all real on current `main` (grounded at `0f5973a639`; none superseded):

- **#4665** — a fresh implementation claim made with a full agent identity rejects its own claim.
- **#4670** — an agent's review verdict is attributed to the configured git user.
- **#4673** — after a rejection, a successful fix-mode claim is blocked by stale reviewer ownership.
- **#3029** — `move-task --agent` fails to persist the acting identity (folded as its representation half only).

This mission reconciles the identity representation on the **claim**, **verdict**, and
**ownership** surfaces so these agent workflows behave honestly on the 4.0.0 candidate,
without rewriting historical events and without blessing the recovery workarounds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fresh implementation claim with a full agent identity completes once (Priority: P1)

An agent (or an operator dispatching one) starts a work package with a fully-qualified
identity, e.g. `agent action implement WP01 --agent codex:gpt-6:python-pedro:implementer`.
Today the command creates the lane, moves the work package to `in_progress`, and then
**refuses its own claim** ("already claimed by 'codex:...'") without printing the prompt.

**Why this priority**: This is the escalated, MVP-launch-gating defect (#4665). The
documented first-use path of the compact `--agent` form is broken; the only recovery is an
agentless resume, which is a workaround, not the intended path.

**Independent Test**: Run the real fresh-worktree compact-identity claim end-to-end; assert
the move to `in_progress` is recorded, the prompt renders once, and no self-conflict is raised.

**Acceptance Scenarios**:

1. **Given** a finalized work package in `planned` with no prior claim, **When** an agent runs `implement` with a full `tool:model:profile:role` identity, **Then** the work package moves to `in_progress`, the supplied model/profile/role metadata is retained, and the implementation prompt is rendered in the same invocation.
2. **Given** that work package now `in_progress` under that identity, **When** the SAME identity re-invokes `implement`, **Then** it is an idempotent resume that renders the prompt again (no conflict).
3. **Given** that work package `in_progress` under one identity, **When** a genuinely DIFFERENT agent attempts to claim it, **Then** the claim is refused with an ownership-conflict error.
4. **Given** a work package claimed by a generic actor (`implement-command`/`unknown`/`user`), **When** any actor re-invokes `implement`, **Then** the re-claim is allowed (the deliberate resume mechanism, FR-010) — distinct from the full-identity self-reject (scenario 1) and the cross-identity conflict (scenario 3).
5. **Given** a completed claim under a full identity, **When** the transition-derived `actor` slot and the runtime `agent` slot are both read, **Then** they resolve to the same canonical (tool-scoped) identity (C-006).

---

### User Story 2 - An agent's review verdict is attributed to that agent (Priority: P1)

An independent reviewer agent claims a review with a full identity
(`review WP02 --agent codex:gpt-6:reviewer-renata:reviewer`), performs the review, and runs
the generated completion command to approve. Today the generated command omits `--agent`, so
the recorded approval is attributed to the configured git user (`actor.tool: user`, null
model/profile) — the verdict looks like a human approval when an agent did the work.

**Why this priority**: Provenance integrity (#4670, parent epic #3044). A misattributed
verdict corrupts the review-artifact record that release decisions depend on.

**Independent Test**: Drive the real claim → generated handoff → completion flow for BOTH an
approval and a rejection; assert the appended verdict event's actor is the reviewing agent, the
recorded reviewer carries the agent identity (not the git user), and the review evidence/reference
is retained.

**Acceptance Scenarios**:

1a. **Given** a review claimed by an agent identity, **When** the agent runs the generated **approval** completion command, **Then** the recorded verdict is attributed to that reviewing agent's identity.
1b. **Given** a review claimed by an agent identity, **When** the agent runs the generated **rejection** completion command, **Then** the recorded rejection verdict is likewise attributed to that reviewing agent's identity.
2. **Given** an agent-driven completion that omits an explicit identity, **When** the verdict is recorded, **Then** the system resolves the active claimed reviewer from the authoritative record rather than defaulting to the git user.
3. **Given** a genuine human-operated approval (no agent claim), **When** the human approves, **Then** the verdict remains attributed to the human as a distinct, truthful case (no fabricated agent).
4. **Given** the active reviewer is resolved for an identity-omitting completion (scenario 2), **When** the verdict is appended, **Then** it carries BOTH the reviewing agent's identity AND the review evidence/reference (evidence is not dropped by the attribution fix).

---

### User Story 3 - Fix-mode claim after rejection records the new implementer (Priority: P1)

A reviewer rejects a work package back to `planned`; an implementer then successfully claims
it in fix mode and does a real red→green correction. Today the reduced ownership slot still
holds the previous **reviewer**, so the ordinary `move-task --to for_review --agent <implementer>`
is refused for an ownership mismatch, forcing a `--force` reassignment.

**Why this priority**: The rejection/rework cycle is a core loop (#4673, parent epic #3044,
MVP-launch milestone). Requiring `--force` to complete a legitimate correction is a
guard blocking a legitimate action.

**Independent Test**: Canonical end-to-end state regression — implement → for_review →
independent review → rejection → fix-mode claim by implementer → for_review WITHOUT `--force`;
assert the transition `actor` slot, the runtime `agent` slot, AND the sticky `role` slot BY NAME
(C-006) at every hop, and that a genuine ownership conflict is still refused. Re-verify on the
WP's `planning_base_branch` that the CLI-side rejection-release fix produces green end-to-end;
if any residual ownership block remains, it is attributable to the upstream reducer (C-001).

**Acceptance Scenarios**:

1. **Given** a work package rejected by a reviewer and then successfully claimed in fix mode by an implementer, **When** the recorded owner is read, **Then** it is the new implementer (not the prior reviewer).
2. **Given** that fix-mode-owned work package, **When** the implementer submits it for review without `--force`, **Then** the submission is accepted.
3. **Given** a work package owned by one agent, **When** a genuinely different agent submits it, **Then** the submission is still refused (the real ownership guard is preserved).
4. **Given** the CLI-side rejection-release fix is landed, **When** the end-to-end loop is re-verified on the WP's `planning_base_branch`, **Then** either it is green (FR-007 fully met) or any residual block is attributable to the upstream reducer and FR-007 is recorded as *partially met, upstream-blocked* with a filed `spec-kitty-events` follow-up handle (C-001) — never silently marked green.

---

### User Story 4 - move-task --agent persists the acting identity (Priority: P2)

An operator or agent moves a work package with an explicit `move-task --agent <identity>`.
The acting identity must persist into the authoritative record so downstream ownership checks
see it (the same reduced ownership slot exercised by Story 3).

**Why this priority**: Folded from #3029 (same reduced-owner slot, same parent #2017 as
Story 1). It is the representation half only; its reported "no agent key at all" symptom may
be partially stale on current `main`, so this story's work **re-verifies the live path first**.

**Independent Test**: On current `main`, drive `move-task --agent` and read the reduced owner
slot; if the identity does not persist, that is the red-first repro; if it already persists,
capture the evidence and close #3029 as resolved rather than re-fixing.

**Acceptance Scenarios**:

1. **Given** a work package and an explicit `move-task --agent <identity>`, **When** the move is recorded, **Then** the acting identity persists into the reduced ownership slot and is visible to later ownership checks.
2. **Given** the live `move-task --agent` path is re-verified on the WP's `planning_base_branch`, **When** it already satisfies scenario 1, **Then** a captured transcript/regression artifact demonstrating the reduced owner already carries the acting identity is recorded on the mission and #3029 is closed citing it (no redundant code change).

### Edge Cases

- **Two representations of ONE agent must compare EQUAL on the impl-claim identity key** (structured dict vs compact string) — this is the #4665 fix. The impl-claim key is deliberately **tool-scoped and role-blind**; it must stay a bare string (never a tuple/struct), because the generic-actor allowance is a bare-string membership test.
- **Reviewer-vs-implementer distinctness is a SEPARATE concern** carried on the review-claim role channel, NOT on the impl-claim identity key. Reconciling the two representations for #4665 must not attempt to encode role distinctness into the identity key (doing so would break the same-agent resume in FR-002 and the generic-actor `in` test).
- A binding-less / agentless claim records a generic actor (`implement-command`, `unknown`, `user`); the generic-actor allowance that lets such a claim be re-claimed must be preserved (it is the deliberate resume path — the *mechanism* is preserved; agentless resume is not thereby blessed as the intended first-use path, see FR-010 and C-003).
- A rejection must genuinely release the prior claim (the released-on-rejection ownership slot) so the next claimant is not blocked by a stale owner; note a sticky role slot may survive a claim release and must not be read as current ownership.
- Ownership semantics across `blocked` / `canceled` transitions are out of scope for this cluster, except that a `blocked → resume` by the same identity remains an idempotent same-owner resume.
- Historical events that already recorded a wrong attribution are immutable; corrections are additive evidence, never rewrites.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Fresh full-identity claim completes once | As an agent, I want a fresh `implement --agent <tool:model:profile:role>` claim to move the WP to in_progress and render the prompt in one invocation, so that I do not reject my own claim (#4665). | High | Open |
| FR-002 | Idempotent same-owner resume; different-owner refused | As an agent, I want re-invoking implement under the same identity to resume idempotently while a different identity is refused, so that resume is safe and collisions are still caught (#4665). | High | Open |
| FR-003 | Claim retains model/profile/role metadata | As an operator, I want the supplied model/profile/role to be retained in the recorded state, so that provenance survives the claim (#4665). | High | Open |
| FR-004 | Generated review-completion carries reviewer identity | As a reviewer agent, I want the generated approval/rejection completion command to carry my claimed identity, so that my verdict is attributed to me, not the git user (#4670). | High | Open |
| FR-005 | Agent-driven completion resolves the active reviewer | As a reviewer agent, I want an identity-omitting agent-driven completion to resolve the active claimed reviewer from the authoritative record, so that the fix survives even if the generated text is bypassed (#4670). | High | Open |
| FR-006 | Genuine human approvals stay attributed to the human | As an operator, I want a real human approval to remain a truthful human-attributed verdict, so that we never fabricate an agent (#4670). | High | Open |
| FR-007 | Fix-mode claim records the new implementer | As an implementer, I want a successful fix-mode claim after rejection to record me as the owner and let me submit for review without `--force`, so that a legitimate correction is not blocked (#4673). | High | Open |
| FR-008 | Genuine ownership conflicts still refused | As the workflow, I want a genuinely different agent acting on another's WP to still be refused, so that the ownership guard remains real (#4673). | High | Open |
| FR-009 | move-task --agent persists the acting identity | As an operator, I want `move-task --agent <identity>` to persist the acting identity into the reduced ownership slot, so that downstream ownership checks see it (#3029, representation half). | Medium | Open |
| FR-010 | Generic-actor claims remain re-claimable | As an agent, I want a WP claimed by a generic actor (`implement-command`/`unknown`/`user`) to remain re-claimable by any actor (the deliberate resume mechanism), distinct from a full-identity self-reject (FR-001) and a genuine cross-identity conflict (FR-002/FR-008), so that reconciling the identity key does not silently break the generic-actor allowance (#4665). | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Additive-only corrections | Zero mutations to historical recorded events; any correction of a prior wrong attribution is an appended event, verified by a test asserting no prior event bytes change. | Integrity | High | Open |
| NFR-002 | Seam-correct identity reconciliation | Two representations of ONE agent (structured dict, compact string) compare EQUAL on the impl-claim identity key, which stays a bare string; reviewer-vs-implementer same-tool distinctness is enforced on the review-claim role channel, NOT the identity key. Proven by a matrix test with named required rows: (a) same agent, dict vs compact → EQUAL on the key; (b) generic actor still matches the bare-string allowance; (c) reviewer-vs-implementer same-tool → REFUSED at the review-claim seam (role channel); (d) same tool, differing profile, both implementers → covered by the existing tool-scoped impl-claim discipline (documented, not silently changed). No matrix row may require the identity key to become a tuple/struct. | Correctness | High | Open |
| NFR-003 | Red-first regression per defect | #4665, #4670, #4673 each land an issue-pinned regression that is RED on the WP's `planning_base_branch` (current `main` `0f5973a639`, of which the issue-filing baseline `be490214` is an ancestor) and GREEN after the fix (ADR 2026-07-17-1). #3029 is re-verified live first (FR-009/US4): if reproducible it follows the same red→green rule; if already green, it lands a characterization regression pinning the correct behavior plus the evidence justifying no code change. | Testability | High | Open |
| NFR-004 | Clean gates | New/changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero new suppressions; cyclomatic complexity of touched functions stays ≤15. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Shared reducer is upstream-owned | `spec-kitty-events` (the reducer that folds the ownership slot) is PyPI-pinned and not editable here. The mission fixes the CLI-owned rejection/ownership/claim path only; if a shared-reducer fold-ordering root still contributes to #4673 after the CLI fix, file a scoped upstream follow-up issue rather than vendoring or editing the installed package. | Technical | High | Open |
| C-002 | Reconcile in the CLI-local comparison layer | Reconcile the two representations in the CLI-local impl-claim comparison layer (the `_actor_key`/comparison seam), NOT the shared display projection. The reconciliation MUST NOT convert the identity key to a non-string (tuple/struct) form and MUST NOT fold role/profile into it — the generic-actor allowance is a bare-string membership test, and a full-tuple key would make one agent's dict form (model may be absent) and compact form (model present) compare UNEQUAL, reintroducing #4665. | Technical | High | Open |
| C-003 | Do not bless the workarounds | Agentless resume (#4665) and `--force` reassignment (#4673) are recovery workarounds; the mission must not codify them as the intended path. Preserving the generic-actor re-claim *mechanism* (FR-010) is distinct from blessing agentless resume as the intended first-use path — the full-identity first-use path (FR-001) must work without resume. | Business | High | Open |
| C-004 | #3029 is the representation half only | Fold only "make `--agent` persist the acting identity". Exclude #3029's alternative resolutions (drop the flag; demote the accept gate to a warning) and its #2993 precondition; re-verify the live path first and close as resolved if already fixed. | Technical | Medium | Open |
| C-005 | Projection stays byte-identical to upstream | The identity projection helper (`actor_identity_str`/`decode_actor`) is byte-identical in the CLI-local status module and the upstream `spec-kitty-events` reducer, and the reduced `actor` slot the local guard reads is written by the upstream copy. Leave the projection UNCHANGED in both; reconciliation happens only in the CLI-local comparison layer (C-002). CLI code reading the reduced `actor` slot must treat it as already tool-projected by the upstream reducer and MUST NOT re-parse it for role. | Technical | High | Open |
| C-006 | Three ownership authorities, named and bounded | Ownership is carried by three distinct reduced authorities, read by different guards: (a) the transition-derived `actor` slot (overwritten every hop; = reviewer after a rejection), read by the claim/review gates; (b) the runtime `agent` slot (released on rejection), read by the move-task gate; (c) a sticky resolved-binding `role` slot NOT released with the claim. The fix must state which slot is authoritative for ownership at each gate, reconcile the release-set asymmetry (or justify leaving `role` sticky), and its regressions must assert the specific named slots at each hop — not read one slot twice. | Technical | High | Open |

### Key Entities

- **Actor identity**: the acting agent, expressed as tool, model, profile, and role — recorded either as a structured record or as a compact `tool:model:profile:role` string; the two forms must reconcile to one canonical identity for ownership.
- **Work-package ownership**: the recorded answer to "who owns this WP", read from a reduced snapshot; there are THREE authorities (transition `actor` slot, runtime `agent` slot released on rejection, sticky resolved-binding `role` slot) consulted by different guards — see C-006.
- **Claim**: a transition that takes a WP into `in_progress` (fresh or fix-mode) and asserts an owner.
- **Review verdict**: an appended approval/rejection carrying the reviewer's identity and evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time `implement --agent <full identity>` on a finalized WP renders the prompt and records `in_progress` in exactly one invocation with zero self-conflicts (was: always failed), and the supplied model/profile/role metadata is present in the recorded state.
- **SC-002**: An agent-performed review verdict — approval AND rejection — is attributed to the reviewing agent identity in 100% of agent-driven completions, with the review evidence/reference retained; human approvals remain attributed to the human.
- **SC-003**: The rejection → fix-mode-claim → resubmit-for-review loop completes with zero `--force` overrides for the legitimate implementer via CLI-owned paths, while a different-agent submission is still refused. If a residual reducer fold-ordering contribution is proven (C-001), the obligation is discharged by (a) the CLI fix landing, (b) a regression pinning the reducer-attributable residue, and (c) a filed upstream follow-up handle — not by an in-repo reducer edit.
- **SC-004**: #4665/#4670/#4673 carry a regression red-before/green-after; historical events are byte-unchanged; the touched test surfaces pass and `ruff`/`mypy`/format gates are clean.
- **SC-005**: `move-task --agent <identity>` persists the acting identity into the reduced ownership slot such that a subsequent ownership check reads that identity (or, if already satisfied on the base, a recorded evidence artifact demonstrates it and #3029 is closed) — verified end-to-end.

## Assumptions

- The finder squad's single fold recommendation (#3029, representation half) is the whole additional sweep; #3010, #3469, #3859, #3532, and epics #2400/#2093/#2017/#3044 stay separate (cross-referenced, not folded).
- #2861 (compact `--agent` claim-side parse) is already closed; its parser and resolved-actor pattern are reused, not re-litigated.
- The CLI-side fix for #4673's rejection-release path is expected to resolve the observed defect end-to-end; the shared-reducer fold-ordering mechanism is handled per C-001 only if it still contributes (FR-007/US3-AC4 make this hedge explicit rather than assuming green).
- Code-verified seam facts (post-spec squad): the impl-claim identity key is tool-scoped and role-blind by design; reviewer-vs-implementer distinctness is a separate role channel that degrades to ALLOW when the reduced `role` slot is stale/None; the projection helper is byte-identical local↔upstream and the reduced `actor` slot is written upstream. These shape C-002/C-005/C-006 and NFR-002 — the fix belongs in the CLI-local comparison layer, never the shared projection.
