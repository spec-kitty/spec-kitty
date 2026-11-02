# Mission Specification: Pre-review gate scope recovery

**Mission Branch**: `issue-6865-pre-review-gate-scope-recovery`
**Created**: 2026-11-02
**Status**: Draft
**Input**: User description: "Issue #6865 — The pre-review regression gate cannot run in this repo: empty derived scope falls back to full `make test-fast`, and the frontmatter `pre_review_test_scope` recovery is rejected by `WPMetadata`."

## Intent Summary (confirmed scope, no open interview questions)

- **Primary actor**: a maintainer or agent driving a work package through
  `in_progress → for_review` in a repository that declares a review test
  command.
- **Trigger**: `move-task --to for_review` runs the doctrine-bound pre-review
  regression gate.
- **Desired outcome**: the gate runs the check it says it runs, inside a budget
  that matches that check, and the documented bounded-scope recovery is
  readable and honoured — so the move completes without
  `--skip-pre-review-gate`.
- **Invariant**: no gate is weakened. `TIMED_OUT`/`CANCELLED` stay terminal, the
  opt-in `NEW_FAILURES` block is unchanged, `--skip-pre-review-gate` stays an
  explicit per-invocation opt-out, and the baseline-receipt budget identity
  still invalidates a stale receipt.
- **Boundary that matters**: the retired census derivation
  (mission `scopesource-gate-followup-01KY6S9P`, FR-001) is not resurrected. The
  gate does not invent `src/**` → `tests/**` mappings.

Scope note: this specification resolves the issue through its own second
alternative — *the budget matches the scope the gate actually chose* — plus the
recovery and diagnosability the issue asks for. Scoping the **baseline** leg to
a pinned WP scope is deliberately out of scope (see "Out of scope").

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The documented bounded-scope recovery works (Priority: P1)

An operator whose whole declared review command cannot fit a sensible gate
budget pins a bounded list of test targets in the work package's frontmatter
(`pre_review_test_scope: tests/review tests/status`) and re-runs the move. The
work-package file stays readable to the runtime, and the gate runs exactly those
targets at head instead of the whole declared command.

**Why this priority**: it is the only escape hatch the gate itself advertises,
and today applying it makes the WP unreadable — the operator is worse off than
before they used the documented recovery.

**Independent Test**: drive a `for_review` move for a WP file that carries the
key through the CLI; assert the subtask-roster read succeeds and the head run's
argv is a scoped pytest invocation over the pinned targets. Positive control:
the same fixture without the key runs the declared command.

**Acceptance Scenarios**:

1. **Given** a WP file whose frontmatter carries `pre_review_test_scope: tests/review`,
   **When** the runtime reads its subtask roster, **Then** the roster resolves
   and the key is readable as `pre_review_test_scope`.
2. **Given** the same WP, **When** the `in_progress → for_review` gate runs,
   **Then** the head run executes the pinned targets, not the whole declared
   command, and the transition evidence records those targets.

---

### User Story 2 - The budget matches the scope the gate chose (Priority: P1)

A maintainer in a repository that declares a whole-suite review command (this
repository: `make test-fast`) runs an ordinary `for_review` move. Because the
gate's chosen scope *is* the whole declared command, the run is bounded by a
whole-command budget instead of the scoped-run default, so the move completes
inside the budget without `--skip-pre-review-gate`.

**Why this priority**: without it the gate is unusable in precisely the
repository that maintains it, and the only practical path stays the skip flag.

**Independent Test**: resolve the review budget for this repository's config
through the production resolution seam and assert it is the whole-command
default; assert a repo that declares `review.test_timeout_seconds` still
resolves its declared value, and a repo that declares nothing under the scoped
shape keeps the 300 s default.

**Acceptance Scenarios**:

1. **Given** a repo with a declared `review.test_command` that runs in full and no
   declared budget, **When** the gate resolves its budget, **Then** the
   whole-command default (1,200 s) applies.
2. **Given** the same repo with `review.test_timeout_seconds: 900`, **When** the
   gate resolves its budget, **Then** 900 s applies.
3. **Given** a repo whose scope source narrows per file, **When** the gate
   resolves its budget, **Then** the scoped default (300 s) is unchanged.
4. **Given** the move's baseline capture, its receipt match and its head run,
   **When** the budget is resolved, **Then** all three see the same number.

---

### User Story 3 - The refusal says what ran and what to do (Priority: P2)

An operator whose gate run timed out reads a message that names the scope shape
the gate chose (whole declared command versus a bounded target list), the
declared command that actually ran, the policy metadata that classifies scopes,
and the concrete recovery for that shape. They do not have to read the source to
find out why a "scoped" run took the whole budget.

**Why this priority**: the current wording ("classification candidate for a
reviewed metadata update") names neither the scope nor the metadata it refers
to, so the operator cannot act on it.

**Independent Test**: render the timeout diagnostic for a whole-command run and
for a bounded-target run on the same fixture family; assert each names its own
shape, that the whole-command one names the declared command and the policy
metadata owner, and that neither claims the other's shape.

**Acceptance Scenarios**:

1. **Given** a timed-out whole-command gate run, **When** the refusal is rendered,
   **Then** it names the whole-declared-command shape, the command, the budget,
   the policy metadata location, and the two recoveries (declare a budget; pin a
   bounded `pre_review_test_scope`).
2. **Given** a timed-out bounded-target run, **When** the refusal is rendered,
   **Then** it names the bounded shape and its targets, and does not describe a
   whole-command run.
3. **Given** an oversized scope, **When** the refusal is rendered, **Then** it
   names the bounded shape alongside the targets it already lists.

### Edge Cases

- A WP with `pre_review_test_scope` that is present but empty: the frontmatter
  value is falsy, so the gate keeps its auto-derived tier (no silent empty
  scope); the field itself must still parse.
- A malformed budget declaration (`review.test_timeout_seconds: true`): refuses
  as today — the shape-aware default must never mask an invalid declaration.
- A repo with no `review.test_command`: the gate stays a quiet `skipped`
  verdict; the shape-aware budget must not turn that into a run.
- A previously captured baseline receipt recorded under the scoped default: the
  receipt no longer matches the resolved whole-command budget, so it is
  recaptured rather than trusted (existing receipt policy, unchanged).
- `--skip-pre-review-gate` and `SPEC_KITTY_SKIP_PRE_REVIEW_GATE`: still skip
  before any budget or workspace resolution.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | WP model accepts the pinned scope key | As an operator, I want the WP file that carries `pre_review_test_scope` to parse, so that the documented recovery does not make the WP unreadable. | High | Open | [build] | no — the strict model rejects the key today |
| FR-002 | Subtask-roster guard reads a WP carrying the key | As the runtime, I want `authored_subtask_roster` to resolve on such a WP, so that the move is not refused before the gate runs. | High | Open | [build] | no — it raises `SubtaskRosterResolutionError` today |
| FR-003 | Pinned scope is honoured end to end | As an operator, I want the gate to run my pinned targets at head, so that the recovery actually narrows the run. | High | Open | [build] | no — unreachable while FR-001/FR-002 fail |
| FR-004 | Whole-command budget default | As a maintainer, I want a whole-declared-command run bounded by a whole-command budget, so that the gate completes inside its budget. | High | Open | [build] | no — 300 s scoped default today |
| FR-005 | Declared budget still wins | As a maintainer, I want `review.test_timeout_seconds` to override the shape default, so that my declaration stays authoritative. | High | Open | [ratchet] | yes — pinned by a paired fixture against FR-004's default |
| FR-006 | Timeout diagnostic names the chosen scope | As an operator, I want the timeout refusal to name the shape, the command, the policy metadata and the recovery, so that I can act without reading the source. | High | Open | [build] | no — current wording names neither |
| FR-007 | Oversize diagnostic names the bounded shape | As an operator, I want the oversize refusal to say it chose a bounded target list, so that the two refusals are distinguishable. | Medium | Open | [ratchet] | yes — pinned by the paired whole-command/shape assertions |
| FR-008 | One budget per transition | As the runtime, I want capture, the receipt match and the head run to resolve the same budget, so that a good baseline is never discarded by a shape mismatch. | High | Open | [ratchet] | no — a divergent number silently degrades to `UNVERIFIED_BASELINE` |
| FR-009 | No gate weakened | As a maintainer, I want the terminal and block semantics unchanged, so that the fix does not buy usability with a softer gate. | High | Open | [ratchet] | yes — pinned by the existing terminal/block/skip tests |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Diff coverage | At least 90% coverage on the changed lines (the repository's diff-cover gate). | Maintainability | High | Open |
| NFR-002 | Diagnostic size | Each generated refusal reason is a single line, at most 800 characters, and JSON-safe (no raw newlines, no non-ASCII control characters). | Operability | High | Open |
| NFR-003 | Single budget authority | Exactly one module resolves the review budget (`review/test_timeout.py`); no second timeout reader and no new configuration key. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No resurrected census | The retired census/shard derivation stays retired: no heuristic source-to-test path mapping is added anywhere. | Technical | High | Open |
| C-002 | Command authority unchanged | `review.test_command` stays the single test-command authority; `review.pre_review_test_command` stays a deprecated alias, never a second scope surface. | Technical | High | Open |
| C-003 | Declared-budget neutrality | A repository that declares `review.test_timeout_seconds` resolves exactly that value, before and after this change. | Technical | High | Open |

### Out of scope (named so a reader does not assume coverage)

- Scoping the **baseline capture** leg to a pinned WP scope. The baseline remains
  a whole-declared-command reference run; a pinned scope bounds the head leg
  only. Narrowing capture is a capture-semantics change (receipt comparability
  across the two legs) and gets its own follow-up issue.
- Re-deriving shard/composite targets (C-001).
- Any change to the block/warn policy, to `gate_budget._RULES`, or to the
  `scope_oversized` classification policy.

### Key Entities

- **Review budget**: the single per-transition number that bounds the baseline
  capture and the candidate head run (`review.test_timeout_seconds`, else a
  shape-dependent default).
- **Scope shape**: what the gate actually chose to run — *bounded target list*
  (an explicit override, or a source that narrows per file) versus *whole
  declared command* (a source that contributes no per-file narrowing).
- **Pinned scope**: the per-WP `pre_review_test_scope` frontmatter value, a
  whitespace-separated pytest target list.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Through the CLI, a WP carrying `pre_review_test_scope` is readable by the subtask-roster guard and its head run executes the pinned targets (paired positive control: the same WP without the key runs the declared command). — [build] · no-op passable: no
- **SC-002**: For this repository's configuration (no declared budget), the resolved review budget is 1,200 s while the measured whole-command cost (`make test-fast` = 215.31 s of pytest on 2026-11-02 on this host) keeps at least 5× headroom. — [build] · no-op passable: no
- **SC-003**: The whole-command timeout reason contains the shape, the declared command, the policy-metadata location and both recoveries; the bounded-target timeout reason contains its shape and targets and never describes a whole-command run. — [build] · no-op passable: no
- **SC-004**: Every pre-existing gate outcome/verdict golden (including the terminal `TIMED_OUT`, `CANCELLED`, opt-in `NEW_FAILURES` block, and both skip paths) still passes unchanged. — [ratchet] · no-op passable: yes — paired with FR-004/FR-006 fixtures that fail if the semantics drift
