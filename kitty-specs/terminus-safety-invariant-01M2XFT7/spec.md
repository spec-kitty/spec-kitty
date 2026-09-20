# Mission Specification: Terminus-Safety Invariant

**Mission Branch**: `issue-4764-terminus-safety-invariant`
**Created**: 2026-09-19
**Status**: Draft
**Input**: Milestone-#11 Slice C — merge/close completion-safety. Anchors #4764, #4765; folds #4474, #2745. Parent epic #3897.

## Summary

Spec Kitty's completion commands — `spec-kitty merge`, `spec-kitty accept`, and `spec-kitty mission close` — share a latent defect **class**: a command mutates (or destroys) mission state *past a precondition it never hard-enforced*, and when a later step fails there is **no rollback**, leaving the mission wedged, split-brain, or falsely completed. This mission establishes ONE **terminus-safety invariant**: every completion command must **gate-then-mutate(-with-rollback)** — refuse before it changes any state when its terminal precondition is not met (regardless of a "soft"/`warn` gate mode), and if a later step fails after mutation has begun, roll the mutation back to the pre-command state. The invariant is enforced through a single shared terminal-readiness authority rather than the ~9 divergent inline definitions that exist today.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merge refuses an unapproved mission before it mutates (Priority: P1)

An operator runs `spec-kitty merge` on a mission whose work packages are still in progress (never reviewed/approved), under the **default** gate configuration (`policy.merge_gates.mode: warn`). Today the merge prints the missing-approval gate as a *warning*, then proceeds to consolidate the lane branches onto the coordination branch and bake `mission_number` into the coordination `meta.json`, and only then fails the post-merge backstop with exit 1 — with nothing rolled back. The lane branch is left with zero commits beyond coordination, so the `for_review` gate rejects it forever; coordination and primary `meta.json` disagree on `mission_number` (split-brain); the work package can never be reviewed again without `--force` or hand git surgery. (#4764, and the same bake fail-open surfaced by #4474.)

**Why this priority**: A single default-config command run one step early turns an in-flight mission into an unrecoverable, split-brain state, and consolidates **unreviewed code** onto the mission branch that a later successful merge squashes to the mainline — a correctness *and* review-integrity failure on the MVP-launch path.

**Independent Test**: On a mission with an unapproved non-cancelled work package, run `spec-kitty merge` under default (`warn`) config; assert the command refuses (non-zero exit) and that the coordination branch, lane commits, and `mission_number` are all unchanged, and the work package can still transition to `for_review`.

**Acceptance Scenarios**:

1. **Given** a mission with a work package that is `in_progress` (unapproved, not cancelled) and `merge_gates.mode: warn`, **When** the operator runs `spec-kitty merge`, **Then** the command exits non-zero, prints a clear "not merge-ready — WPs missing approval" refusal, and performs no lane consolidation and no `mission_number` bake.
2. **Given** the same refused merge, **When** the operator inspects the mission afterward, **Then** the lane branch still has its implementation commits beyond coordination, the coordination and primary `meta.json` still agree (`mission_number` still unassigned), and the work package can still move to `for_review`.
3. **Given** a normal merge-ready mission (every non-cancelled WP `approved` or `done`), **When** the operator runs `spec-kitty merge` under any gate mode, **Then** the merge proceeds exactly as before (the new precondition never false-blocks a legitimate merge).
4. **Given** `merge_gates.mode: warn` and a mission that is merge-ready but has a *soft* evidence-quality concern (e.g. a hollow-review signal), **When** the operator merges, **Then** the soft gate is still softened to a warning (the invariant hardens only the terminal-lane readiness, not evidence quality).
5. **Given** a `--resume`d merge whose merge baseline was already stamped mid-flight AND a non-cancelled work package is still unapproved, **When** merge runs, **Then** it re-evaluates **live** terminal readiness and still refuses — it does NOT pass vacuously on the stale `merged_at`/baseline marker. (Pins the `is_mission_completed`/`merged_at` short-circuit anti-pattern rejected in D4.)
6. **Given** a work package `canceled` **without** operator provenance, **When** any completion command evaluates terminal readiness, **Then** the shared authority returns not-ready and the command refuses (the operator-provenance check is load-bearing and must not be dropped).

---

### User Story 2 - Mission close refuses an unmerged mission instead of fabricating completion (Priority: P1)

An operator runs `spec-kitty mission close --mission <slug>` (without `--discard`) on an unmerged, in-flight mission. Today the command exits 0, prints "closed", commits a `retrospective.yaml` with `kind: runtime_post_completion` to the mainline, and tears down the coordination worktree — even though its own `--help` says "Without --discard, requires that the mission has already been merged (no-op cleanup otherwise)". Afterward `next` reports the mission blocked and `implement` fails until the operator guesses to re-run `finalize-tasks`. (#4765.)

**Why this priority**: The command fabricates a post-completion record on the mainline for a mission that was never completed — `retrospect summary` and downstream tooling then count it as done — and half-terminates a live mission. Silent false success that corrupts the completion record.

**Independent Test**: On an unmerged mission with an in-progress work package, run `spec-kitty mission close` without `--discard`; assert the command refuses (non-zero exit), writes nothing (no `retrospective.yaml` committed), does not tear down the coordination worktree, and points the operator at `--discard`.

**Acceptance Scenarios**:

1. **Given** an unmerged mission (no merge baseline recorded) with a work package still in progress, **When** the operator runs `spec-kitty mission close` without `--discard`, **Then** the command exits non-zero, writes no retrospective and no commit, leaves the coordination worktree intact, and instructs the operator to use `--discard` to abandon an in-flight mission.
2. **Given** a mission that has been merged, **When** the operator runs `spec-kitty mission close` without `--discard`, **Then** the post-merge completion teardown runs as it does today (the guard admits genuinely-merged missions).
3. **Given** an in-flight mission the operator genuinely wants to abandon, **When** they run `spec-kitty mission close --discard`, **Then** the existing discard path is unchanged.

---

### User Story 3 - A completion command that fails after mutating rolls back cleanly (Priority: P1)

When a completion command has begun mutating durable state (lane consolidation, `mission_number` bake, target-ref advance) and a *later* step fails, the command must return the mission to its pre-command state rather than leaving a half-terminated wedge. This is the defense-in-depth half of the invariant and the general statement of the terminus half-termination class (#2745), covering both the coordination-topology path and the direct-on-target path.

**Why this priority**: Preconditions (US1/US2) close the reported entry points, but any *other* post-mutation failure (e.g. a status-store error mid-backstop) reproduces the same wedge. A transactional rollback makes the whole class recoverable.

**Independent Test**: Force a post-mutation failure in a completion command; assert the coordination ref / worktree (and, on the direct-on-target path, the target ref) are restored to their pre-command state and the mission remains reviewable and resumable.

**Acceptance Scenarios**:

1. **Given** a merge that has consolidated a lane and baked `mission_number`, **When** a later step fails, **Then** the coordination ref and worktree are reset to their pre-merge state (consolidation and bake undone), the mission remains reviewable, and a subsequent `--resume` reads a coherent state (no split-brain between committed coordination `done` markers and worktree bytes).
2. **(rollback arm)** **Given** a direct-on-target completion that has advanced the target ref, **When** a later step fails, **Then** the target ref is rolled back to its pre-command state so the mission is not left half-terminated.
3. **(refuse-before-advance arm — the interim guard if the target-advance rollback is deferred)** **Given** a direct-on-target mission that is NOT merge-ready, **When** a completion command runs, **Then** it refuses BEFORE advancing the target ref, and the target ref is provably unchanged — the half-terminated state is unreachable regardless of whether the rollback arm has shipped yet.

---

### User Story 4 - Completion commands agree on what "ready" means (Priority: P2)

`merge`, `accept`, and `mission close` today each compute "is this mission terminally ready" a different way (an evidence-gate loop, an acceptance matrix, a reopen-style completion reader, and ~9 hand-inlined `is_acceptable_ending` loops). The invariant is only trustworthy if all three route their terminal-readiness check through ONE shared authority, so a fix in one place cannot silently diverge from another.

**Why this priority**: Consolidation is what prevents this from becoming three drifting point-fixes and a future 6th definition; it is the durable-fix backbone, but it is behavior-preserving and lower-risk than US1–US3.

**Independent Test**: Assert `merge`, `accept`, and `mission close` all derive terminal readiness from the same shared reader, and that the reader's truth table (approved/done ⇒ ready; cancelled ⇒ ready only with operator provenance; otherwise not ready) is exercised directly.

**Acceptance Scenarios**:

1. **Given** the shared terminal-readiness authority, **When** any of the three `specify_cli` terminus commands (`merge`, `accept`, `mission close`) evaluates readiness, **Then** it calls that one authority (none of the three re-inlines its own acceptable-ending loop). Surviving runtime-side loops are out of scope by C-002 and are not a regression against this mission.
2. **Given** a mission with a provenance-cancelled work package, **When** each completion command evaluates readiness, **Then** all agree it is an acceptable ending (no lossy lane-only variant disagrees with a provenance-aware one).

---

### User Story 5 - Direct-on-target missions can be completed and closed cleanly (Priority: P2)

The safety guards (US1–US3) make the direct-on-target path *safe* (refuse-before-advance), but a mission whose work package was implemented directly on the target branch (the sanctioned fallback with no lane branch) is then safe-but-**stuck** — merge hard-fails on the missing lane branch, and `mission close` chokes on an orphaned `coordination_branch` (printing a doubled slug, with no `--json`). This story provides the completion **affordances** so the operator has a real path forward, not just a safe dead-end. (#2745 facets 1-affordance and 3; folded by operator decision D6.)

**Why this priority**: Safety without an escape hatch leaves the operator blocked; the affordances make the direct-on-target lifecycle whole. Lower priority than the safety invariant itself because it is additive capability, not a corruption fix.

**Independent Test**: On a direct-on-target mission (WP committed on the target branch, no lane branch), complete it via the documented completion affordance and then close it; assert the mission reaches a merged/terminal state without a hard-fail and `mission close` succeeds (and emits `--json` when asked) without choking on the orphaned coordination branch.

**Acceptance Scenarios**:

1. **Given** a merge-ready direct-on-target mission with no lane branch, **When** the operator completes it via the documented affordance (e.g. `spec-kitty merge --skip-lanes`/`--no-lanes`), **Then** the mission is consolidated/recorded transactionally (no half-termination) and reaches a merged state — the merge does not hard-fail on the absent lane branch.
2. **Given** the affordance flag on a mission that is NOT merge-ready, **When** the operator runs it, **Then** the same terminal-readiness precondition (US1) still refuses before any mutation — the affordance is not a bypass of the invariant.
3. **Given** a mission left with an orphaned `coordination_branch` marker, **When** the operator runs `spec-kitty mission close`, **Then** it tolerates the orphan (no traceback), renders the mission slug once (not doubled), and honors `--json`.

### Edge Cases

- A mission whose work packages are **all cancelled but never merged**: `mission close` without `--discard` must refuse (it is not merged) and point at `--discard`; it must NOT be treated as "completed" and torn down.
- A `--resume`d merge whose baseline was already stamped mid-flight: the merge precondition must still evaluate live terminal readiness and must not pass *vacuously* on a stale "merged" marker.
- A merge with a legitimately-softened evidence-quality gate (`warn` mode) but full terminal readiness: must proceed.
- A rollback attempted after the coordination worktree has already been torn down: the transactional reset must run before teardown, or detect and fail closed rather than silently no-op.
- The `--force` merge path (operator override) must retain its existing hollow-review warning semantics and is out of scope for softening.
- **All-cancelled-with-provenance (merge-ready) boundary**: a mission where *every* non-excluded work package is acceptably-cancelled (no `approved`/`done`) technically satisfies the merge-ready predicate. The spec must state merge's behavior here explicitly so the merge-ready predicate (admits it) and the `mission close` predicate (an all-cancelled-**unmerged** mission must go via `--discard`) stay mutually consistent on this boundary rather than silently diverging.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Merge refuses a not-merge-ready mission before any mutation | As an operator, I want `merge` to refuse (non-zero, no state change) when any non-cancelled work package is not at an acceptable ending, so an unapproved mission is never consolidated. | High | Open |
| FR-002 | Merge terminal precondition is unconditional across gate modes | As an operator, I want the "all non-cancelled WPs approved/done" invariant enforced regardless of `merge_gates.mode`, so `warn` cannot fail-open into consolidating unapproved lanes. | High | Open |
| FR-003 | `warn` softens only evidence-quality gates | As an operator, I want `warn` mode to keep softening review-quality/risk/hollow-review gates while never softening the terminal-lane invariant, so the default config stays usable without being unsafe. | High | Open |
| FR-004 | `mission close` (non-discard) refuses an unmerged mission | As an operator, I want `mission close` without `--discard` to refuse (non-zero, no writes, no teardown) when the mission has no merge baseline, pointing me at `--discard`, so it can never fabricate a completion record. | High | Open |
| FR-005 | No fabricated completion artifact on refusal | As an operator, I want a refused `mission close` to commit no `retrospective.yaml` and emit no `RetrospectiveCaptured`/completion event, so downstream tooling never counts an in-flight mission as done. | High | Open |
| FR-006 | mission_number is never baked for a not-merge-ready mission | As an operator, I want `mission_number` baking to be unreachable when the terminal precondition fails, so coordination and primary `meta.json` never split-brain. | High | Open |
| FR-007 | Failed completion after mutation rolls back to pre-command state | As an operator, I want a completion command that fails after it began mutating to restore the coordination ref/worktree (and, on the direct-on-target path, the target ref) to their pre-command state, so no half-terminated wedge survives. | High | Open |
| FR-008 | Resume-coherent rollback | As an operator, I want a rolled-back merge to leave committed coordination `done` markers and worktree state mutually coherent, so a later `--resume` reads a consistent state. | High | Open |
| FR-009 | Single shared terminal-readiness authority (tidy-first enabler) | As a maintainer, I want the three terminus commands in `specify_cli` (`merge`, `accept`, `mission close`) to evaluate terminal readiness through one shared reader (not re-inlined loops), so the invariant cannot silently diverge and a 6th definition is never introduced. This aggregate is a **behavior-preserving tidy-first enabler** to be built and adopted BEFORE FR-001/FR-004 consume it (its Medium priority is value-ranking, not build-order). Adoption is scoped to `specify_cli`; the runtime-side inline loops are intentionally NOT rewired (protects the shrink-only `runtime → specify_cli` layer ledger). | Medium | Open |
| FR-010 | Direct-on-target path safety covered by the invariant | As an operator, I want the refuse-before-advance guard (and, where tractable, the rollback) to apply to the direct-on-target completion path, not only the coordination-topology path, so #2745's half-termination is closed on both paths. | Medium | Open |
| FR-011 | mission_number bake is topology-aware, never a silent fail-open | As an operator, I want the `mission_number` write-back on a **merge-ready** coord-topology mission to reach the correct (primary-tree) `meta.json`, or — if it genuinely cannot — surface the unbaked field as a queryable event + merge-summary line, so a successful merge never silently loses `mission_number` (leaving `doctor` stuck at `pending`). This is #4474's actual defect and is DISTINCT from FR-006 (which prevents baking a *not*-merge-ready mission). | High | Open |
| FR-012 | Direct-on-target missions can be completed | As an operator, I want a documented, transactional way to complete a merge-ready direct-on-target mission that has no lane branch (e.g. `spec-kitty merge --skip-lanes`/`--no-lanes`), so the sanctioned fallback is not a safe-but-stuck dead-end. The affordance still enforces the FR-001 terminal precondition (no bypass). | Medium | Open |
| FR-013 | mission close tolerates an orphaned coordination branch | As an operator, I want `mission close` to tolerate a mission left with an orphaned `coordination_branch` marker (no traceback), render the mission slug once (not doubled), and honor `--json`, so closing a direct-on-target / partially-torn-down mission is clean. | Medium | Open |
| FR-014 | accept escape-hatch guidance is followable | As an operator, I want `accept` to give followable guidance (naming the real escape hatch) rather than impossible "materialize-then-retry" instructions when a mission has no lane branch. NOTE: the protected-primary hard-reject appears already removed (`accept.py`); this FR is a **liveness confirmation** — verified-already-fixed if a red-first probe cannot reproduce it, otherwise fixed. | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Recoverability | After any refused or failed completion command, the mission requires **zero** manual git-surgery or `--force` steps to continue; `next`, `implement`, and the `for_review` gate keep working. | Reliability | High | Open |
| NFR-002 | No regression on legitimate completions | Every previously-passing merge/accept/close path stays green; no merge-ready mission is false-blocked, including on `--resume`. Verified against the full `tests/merge/`, `tests/integration/test_mission_close.py`, and acceptance suites. | Reliability | High | Open |
| NFR-003 | Review integrity | Unreviewed code can never be consolidated onto the mission branch by a default-config command; verified by the FR-001 regression test. | Security | High | Open |
| NFR-004 | Command latency | The added precondition adds negligible latency; `merge`/`close` stay within the charter's < 2s typical-CLI budget. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority (no new definition) | Reuse `status_lanes.is_acceptable_ending` / `TERMINAL_LANES`; add at most ONE shared aggregate reader; introduce no 6th "done/terminal" definition (DIRECTIVE_044, canonical-source-unification). | Technical | High | Open |
| C-002 | Respect module boundaries | Import mission-completion readers via the `specify_cli.status` facade; keep the new aggregate in the orchestration-free `status_lanes` module; do NOT grow the shrink-only `runtime → specify_cli` outbound ledger (adoption scoped to `specify_cli`). | Technical | High | Open |
| C-003 | No new uncaught error surface | Preconditions raise through the existing per-command error envelopes (`typer.Exit(1)` in-executor for merge; structured `_emit_mission_error` for close); add no error type that escapes the fixed CLI translation chains. | Technical | High | Open |
| C-004 | ATDD red-first per defect | Each defect (#4764, #4765, #4474, #2745) gets an issue-pinned `@pytest.mark.regression` test that is RED through the pre-existing CLI entry point before the fix and GREEN after. | Process | High | Open |
| C-005 | No version prescription | Assign no version number in scope (PO owns versioning); record impact-first `[Unreleased]` CHANGELOG entries only. | Process | Medium | Open |
| C-006 | Complexity ceiling | Keep touched/new functions at cyclomatic complexity ≤ 15 (extract testable helpers rather than inline the precondition). | Technical | Medium | Open |

### Key Entities

- **Terminus command**: a completion command (`merge`, `accept`, `mission close`) that ends or finalizes a mission's lifecycle by mutating durable state.
- **Terminal-readiness authority**: the single shared reader that answers "is every non-cancelled work package at an acceptable ending?" (approved/done ⇒ ready; cancelled ⇒ ready only with operator provenance).
- **Merge baseline**: the recorded marker (`merged_at` / baseline merge commit) proving a mission was actually merged; the correct predicate for `mission close` (non-discard).
- **Coordination checkpoint**: a captured pre-mutation coordination ref/worktree state a failed completion can be reset to.

## Domain Language *(canonical terms)*

- **gate-then-mutate(-with-rollback)** — the required shape: enforce the terminal precondition *before* any mutation; roll back on later failure. Avoid "validate after".
- **terminal-lane invariant** — "every non-cancelled WP is at an acceptable ending". Enforced HARD regardless of gate mode. Distinct from **evidence-quality** gates (review verdict / risk / hollow-review), which `warn` may soften.
- **acceptable ending** — `approved` or `done`; `canceled` only with operator provenance. Canonical reader: `status_lanes.is_acceptable_ending`.
- **merge-ready** vs **merged** vs **completed** — *merge-ready* = all non-cancelled WPs approved/done (merge's precondition). *merged* = a merge baseline was recorded (`mission close`'s precondition). *completed* = merged OR all-terminal (used by `reopen`). These are DISTINCT; do not collapse them onto one predicate.
- **direct-on-target path** — the sanctioned fallback where a work package is implemented directly on the target branch with no lane branch (topology without a coordination lane). Its completion needs the `--skip-lanes`/`--no-lanes` affordance (FR-012).
- **fail-open** — a guard that, on an unmet condition, silently proceeds/skips (e.g. #4474's `mission_number` bake logging a warning and returning without writing) instead of refusing or surfacing. The invariant replaces fail-open with refuse-or-surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `merge` under default configuration on a mission with an unapproved work package is refused before any state change, and the work package can still be reviewed afterward — **0** wedged missions across the #4764 reproduction (previously 100% wedged).
- **SC-002**: Closing an unmerged in-flight mission without `--discard` is refused and writes nothing — **0** fabricated `runtime_post_completion` records on the mainline across the #4765 reproduction.
- **SC-003**: A completion command interrupted by a failure after it began mutating leaves the mission in its pre-command state — **0** split-brain `meta.json` states and **0** manual recovery steps.
- **SC-004**: Each of the four reported defects (#4764, #4765, #4474, #2745) has an issue-pinned regression test that is **red before** the fix and **green after** (for #4474, a *merge-ready* coord-topology bake test; for #2745, both the safety guard and the completion affordance), and every previously-passing completion path remains green. Where a facet is verified-already-fixed (e.g. #2745 accept guidance), the red-first probe is documented as green-on-current-main rather than fabricated.
- **SC-005**: A merge-ready direct-on-target mission with no lane branch can be completed to a merged state via the documented affordance without a hard-fail, and can then be closed cleanly (including `--json`) — **0** safe-but-stuck missions across the #2745 reproduction.

## Assumptions & Recorded Decisions

- **D1 (operator)**: Scope is the FULL terminus-safety invariant across merge + accept + mission-close, folding #4764 + #4765 + #4474 + #2745. (Decision Moment `01M2XFVSK8JCCXMXCJNTBB0X5V`.)
- **D2 (operator)**: `warn` softens evidence-quality gates only; the terminal-lane invariant is hard regardless of mode ⇒ merge gets an unconditional merge-ready precondition (not a rollback-only fix). (Decision Moment `01M2XFW9B71WKJ4XPCDCH8VYCQ`.)
- **D3 (operator)**: Parent this mission under epic #3897 (Mission-lifecycle robustness).
- **D4 (agent, flagged for operator veto)**: `mission close` (non-discard) guards on **merged** (`is_mission_merged`), NOT **completed** (`is_mission_completed`). Rationale: an all-terminal-but-*unmerged* mission (e.g. all cancelled) must be abandoned via `--discard`, not torn down as a completion; this also matches the command's own `--help`. `merge` uses a distinct **merge-ready** predicate. Reusing a single `is_mission_completed` for both is explicitly rejected (it would false-block normal merges and pass vacuously on `--resume`).
- **D5 (agent, flagged)**: #2745's **rollback-after-target-advance on the direct-on-target path** is a distinct, harder seam with no existing machinery. It is planned as its own work package with a red-first test; if it proves mission-sized, only that sub-part is deferred as a tracked #3897 follow-up, with the direct-on-target path still made safe by a *refuse-before-advance* precondition so the half-terminated state is unreachable in the interim (FR-010 acceptance arm 3).
- **D6 (operator, 2026-09-19)**: After the post-spec squad found #2745 is a 3-facet bundle, the operator ruled to **fold #2745's completion affordances too** (not just the safety facet): `merge --skip-lanes`/`--no-lanes` to complete a direct-on-target mission (FR-012), and mission-close orphan-branch tolerance / doubled-slug fix / `--json` (FR-013). This mission therefore fully closes #2745. Facet-2 (accept guidance, FR-014) is a liveness confirmation — the protected-primary hard-reject already appears removed.
- **D7 (agent, post-spec repair)**: #4474 was originally folded in name only (FR-006 prevents baking a *not-merge-ready* mission but does not touch #4474's *merge-ready* fail-open). FR-011 is added as the delivering requirement for #4474's actual defect (topology-aware bake write-back or operator-visible surfacing), so its red-first test is genuinely green-after. Confirmed at `merge/ordering.py:398-414` (the bake fail-opens with `return False` when meta.json is absent on the mission-branch tree).
- Post-spec adversarial squad (reviewer-renata fakeability + planner-priti scope) findings folded: numbered `--resume` vacuous-pass scenario (US1-5), cancelled-without-provenance negative (US1-6), split rollback vs refuse-before-advance arms (US3-2/US3-3), all-cancelled merge boundary (Edge Cases), FR-009/US4 scoped to the three `specify_cli` terminus commands, and the FR-009 tidy-first-enabler sequencing note.
- Reproductions were confirmed still-real on current `main` (4.0.0rc4); the reporter baseline SHA is an ancestor of `main` and the only intervening commit on these files (#4724) is unrelated.
