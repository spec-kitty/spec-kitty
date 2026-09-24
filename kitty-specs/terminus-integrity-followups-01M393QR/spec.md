# Mission Specification: Terminus Integrity Follow-ups

**Mission Branch**: `fix/terminus-integrity-followups`
**Created**: 2026-09-24
**Status**: Draft
**Input**: Close the remaining open children of Epic #5001 (terminus/merge-coord integrity) left after PR #5012 landed the reconciliation-gate spine — three coupled workstreams: squash-content-soundness (#5013), resume-strategy + lane-tip SHA-preservation (#4982 #4997 #4985 #4991), and surface-write self-materialization hardening (#4970).

## Intent Summary *(confirmed)*

- **Primary actor**: an operator (or fleet agent) running a terminus command — `spec-kitty merge`, `spec-kitty merge --resume`, or `spec-kitty agent issue-verdict`.
- **Trigger**: the operator consolidates a mission's approved work, on the DEFAULT path (`spec-kitty merge`, which resolves to the squash strategy), possibly after an interruption, or records an issue verdict.
- **Desired outcome**: the exit code and printed outcome reflect what actually landed on the target tree; approved work is preserved; removed/canceled work is never silently shipped; a resumed merge behaves identically to the uninterrupted one.
- **Invariant that must always hold**: *after any exit-0 terminus command, every approved WP's committed content is reachable from the target and nothing excluded is — on every strategy, including the default squash, and across interruptions.* On divergence the command refuses fail-closed (non-zero) and rolls back rather than reporting success.
- **Confirmed scope** (Decision `01M393S0NKWJRRDGFND4WGFBMY`): all three workstreams. **WS2 depth** (Decision `01M393S7EVNPY707FPWYDCPDGM`): full — both strategy-honoring and lane-tip SHA-preservation, closing all four resume children.
- **Explicitly out of scope**: #4990 (reducer wall-clock LWW; lives in the `spec_kitty_events` package — C-002 boundary) and #4972 (upgrade per-branch stamping; different subsystem). These are sequenced sibling missions.

This mission builds on the reconciliation-gate spine landed by PR #5012 (still open at authoring time); it is based on the `fix/terminus-merge-integrity` branch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Default merge never silently ships removed work (Priority: P1)

An operator runs `spec-kitty merge` (no `--strategy`, so it resolves to squash — the common default). A canceled/removed work package's commit has ridden a carrier lane into the mission history (the #4945/#4977/#4981 shape). Today the squash path early-returns a PASS from the reconciliation gate *before* the content/excluded/closed-world checks run, so the merge exits 0 with the removed work on the target. This story makes the default squash merge enforce the same tree-authoritative content guarantee that `--strategy merge` already enforces.

**Why this priority**: This is the P0 child #5013 (milestone 11 / MVP launch) and it is the DEFAULT operator invocation — the unprotected path is the one almost everyone uses. It is data-loss-critical: silent shipment of removed work is exactly the epic invariant violation.

**Independent Test**: Drive `spec-kitty merge` (default squash) in a real on-disk mission where a canceled WP's file rode a carrier lane; assert the merge refuses (non-zero) and the removed file is absent from the target tree. Independently valuable even if WS2/WS3 are not delivered.

**Acceptance Scenarios**:

1. **Given** a mission whose target would, after a default squash merge, contain a file authored only by a canceled/removed WP, **When** the operator runs `spec-kitty merge` with no `--strategy`, **Then** the reconciliation gate FAILs, the target is rolled back to its pre-merge tip, and the command exits non-zero.
2. **Given** a clean mission where all approved work is present and nothing is excluded, **When** the operator runs the default `spec-kitty merge`, **Then** the content axis PASSes and the merge completes exit 0 (no false-refusal of a legitimate squash).
3. **Given** a default squash merge that passes, **When** the success message is printed, **Then** it does not claim excluded-commit reachability was verified in a way the gate did not actually perform.

---

### User Story 2 - A resumed merge behaves exactly like the uninterrupted one (Priority: P2)

An operator's `spec-kitty merge --strategy merge` is interrupted (SIGINT/crash/conflict) partway. They run `spec-kitty merge --resume`. Today the resume (a) silently downgrades to the default squash because the operator's chosen strategy is never persisted/read, and (b) re-anchors the reconciliation claim to the resume-start checkpoint, so pre-interrupt lane-tip commits can be judged "already consolidated" and dropped while the gate passes vacuously. This story makes resume honor the persisted strategy and preserve the pre-interrupt lane tips.

**Why this priority**: Four coupled children (#4982 #4997 #4985 #4991). A resumed merge that downgrades strategy or loses committed lane work is a real data-loss and wrong-tree hazard on a recovery path operators reach precisely when something already went wrong.

**Independent Test**: Interrupt a `--strategy merge` after the target advance, then `merge --resume`; assert the resumed run uses the merge strategy (not squash) and every approved commit that existed before the interruption is reachable from the target afterward. #4985/#4991 land on the correct non-default target; #4982/#4997 preserve the lane tips.

**Acceptance Scenarios**:

1. **Given** an interrupted `spec-kitty merge --strategy merge`, **When** the operator runs `spec-kitty merge --resume` with no `--strategy`, **Then** the resumed run uses the persisted `merge` strategy, not the default squash.
2. **Given** a resume where the operator passes a `--strategy` that differs from the persisted one, **When** they resume, **Then** the command REFUSEs fail-closed (a strategy flip across resume is a hazard, not a silent override).
3. **Given** an interrupted merge whose pre-interrupt lane tips carried approved commits, **When** the operator resumes, **Then** the reconciliation gate judges reachability against the true pre-interrupt lane tips and every such commit remains reachable from the target.
4. **Given** an interrupted merge whose target is a non-default branch, **When** the operator resumes, **Then** the merge lands on that target with no `SafeCommitHeadMismatch` and #4985/#4991 close.

---

### User Story 3 - A verdict write never clobbers committed coordination content (Priority: P3)

An operator records an issue verdict (`spec-kitty agent issue-verdict`) for a mission whose coordination branch exists as a stale local head that already carries committed issue-matrix rows, but whose worktree is unmaterialized. Today the write gate misclassifies this as a sanctioned first-write self-materialization window, and the issue-verdict path resolves its surface through the degrading READ resolver — so the write can fork off an empty row map and clobber the committed rows. This story refuses that write and routes verdict writes through the fail-closed write resolver.

**Why this priority**: One child (#4970). Real corruption of the very matrix the reconciliation gate later trusts, but narrower and lower-frequency than the merge paths.

**Independent Test**: Seed a coordination branch as a local head with committed matrix rows for one issue, remove its worktree, then run a second `issue-verdict` for a different issue; assert the committed rows survive (whether the second write refuses or merges), never clobbered.

**Acceptance Scenarios**:

1. **Given** a coordination branch that is an unmaterialized local head already carrying committed issue-matrix content, **When** a coord-routed write attempts to self-materialize onto it, **Then** the write gate REFUSEs (this is not a genuine first-write window).
2. **Given** a genuine first-write with no committed matrix content on the coordination branch, **When** the write self-materializes, **Then** it succeeds (no false-refusal of the legitimate bootstrap).
3. **Given** an `issue-verdict` write, **When** it resolves its write surface, **Then** it uses the fail-closed write resolver (not the degrading read resolver), so it cannot land on a degraded primary surface.

### Edge Cases

- **Squash loses SHAs**: post-squash there are no lane-tip SHAs or per-lane patch-ids, so the content axis must attribute by *blob content*, not by SHA/patch-id, or it silently no-ops to PASS.
- **3-way merge-resolution content**: a path whose final target blob equals neither parent verbatim cannot be attributed to a single approved lane; this is a bounded residual, handled as an honest tracked follow-up rather than green-washed.
- **Git-probe error / unresolvable window base**: any git error or missing window base in a windowed/content axis must REFUSE (fail-closed), never collapse to PASS.
- **Resume window base already advanced**: the pre-mutation target tip is persisted (landed in #5012); the coordination base must be persisted symmetrically or the resume claim judges an empty window.
- **Strategy flip across resume**: an explicit `--strategy` that contradicts the persisted one is refused, not silently honored.
- **Legitimate first-write vs stale local head**: the write gate must distinguish an empty-content first materialization (allow) from a stale local head carrying committed rows (refuse).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Squash-sound excluded/closed-world content axis | As an operator, I want the DEFAULT squash merge to fail-close when a removed/canceled WP's committed content is reachable from the target, so removed work is never silently shipped (#5013; unblocks #4945 #4977 #4981 for the default flow). | High | Open |
| FR-002 | Honest squash outcome reporting | As an operator, I want the squash merge's success message to reflect only what the gate actually verified, so a passing report never overstates the guarantee. | High | Open |
| FR-003 | Resume honors persisted strategy | As an operator, I want `merge --resume` to use the strategy I chose on the interrupted run rather than silently downgrading to the default squash (part of #4985 #4991). | High | Open |
| FR-004 | Resume preserves pre-interrupt lane tips | As an operator, I want a resumed merge to keep every approved commit that existed before the interruption reachable from the target, judged against the true pre-interrupt lane tips, not the resume-start checkpoint (#4982 #4997). | High | Open |
| FR-005 | Resumed non-default-target merge lands correctly | As an operator, I want a resumed merge targeting a non-default branch to land the full merge on that target (closes #4985 #4991 together with FR-003). | High | Open |
| FR-006 | Write gate refuses stale-local-head self-materialization | As an operator, I want the coordination write gate to refuse a self-materialization write onto a stale local-head branch that already carries committed matrix content, so committed rows are never clobbered (part of #4970). | Medium | Open |
| FR-007 | Issue-verdict writes use the fail-closed write resolver | As an operator, I want `issue-verdict` to resolve its write surface through the fail-closed write resolver rather than the degrading read resolver, so a verdict never lands on a degraded surface (closes #4970 with FR-006). | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fail-closed on ambiguity | Every new content/window/self-materialization check REFUSEs (non-zero, no teardown) on any git-probe error, unresolvable window base, or unreadable ref; zero fail-open paths in new code (verified by direct error-injection tests). | Reliability | High | Open |
| NFR-002 | No regression in the blast radius | 100% of pre-existing passing tests in `tests/merge`, `tests/coordination`, `tests/git`, `tests/lanes`, `tests/terminus`, and `make test-fast` remain green; `mypy --strict`, `ruff check`, and `ruff format --check` report zero new issues. | Reliability | High | Open |
| NFR-003 | No false-refusal of legitimate flows | A clean default squash merge (all approved present, nothing excluded) PASSes, and a genuine first-write self-materialization succeeds — each proven by a dedicated red→green test that is RED without the fix's over-broad form and GREEN with the correct one. | Correctness | High | Open |
| NFR-004 | Maintainable helpers | Every new function stays at or below McCabe complexity 15; a non-trivial literal repeated ≥3 times in a module is hoisted to a named constant (Sonar S1192/S3776); no new `# noqa`, `# type: ignore`, or Sonar suppressions. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Red-first, no green-washing | Every fix is reproduced RED first through the existing `tests/terminus/` harness (real CLI, mock-free); an `xfail(strict)` marker is removed only when the repro is genuinely GREEN; any residual gap stays `xfail(strict)` with a specific, code-grounded reason (ATDD C-011). | Process | High | Open |
| C-002 | Respect package + layer boundaries | Do NOT modify the `spec_kitty_events` package; #4990 and #4972 stay out of scope. Add no new `mission_runtime → specify_cli` first-level subpackage import edge and do not grow `tests/architectural/_baselines.yaml` caps. | Technical | High | Open |
| C-003 | Scope discipline on write-gating | Do NOT blanket-flip high-frequency writers (status_transition / decision-log / bookkeeping / retrospective) to `terminus_write`; only the issue-verdict/matrix chain is rerouted. The 3-way merge-resolution content residual is a tracked follow-up, not folded or green-washed. | Technical | High | Open |
| C-004 | Preserve the transaction boundary | All new checks run BEFORE any branch/worktree teardown, push, or exit-0; the existing verify → FAIL → CAS-rollback → exit-1 boundary and the compare-and-swap ref discipline are preserved, never bypassed. | Technical | High | Open |

### Key Entities

- **Reconciliation claim (`ApprovedWpCommitSet`)**: the approved-WP content authority the gate verifies the target against; must gain a squash-sound, content-based (blob) attribution basis.
- **Merge run/resume state (`MergeState`)**: the persisted record a resumed merge reads; must carry the operator's strategy and the pre-interrupt lane-tip / coordination base so resume reconstructs the true pre-mutation window.
- **Coordination surface authority (write gate)**: the fail-closed decision of where a coord-routed write lands; must refuse a stale-local-head-with-committed-content self-materialization and be the resolver every terminus verdict write uses.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The `tests/terminus/` repros `#4970`, `#4982`, `#4985`, `#4991`, `#4997` and the property parameter `no_excluded_commit_reachable[squash]` flip from `xfail(strict)` to genuine green; `#4945/#4977/#4981` additionally pass under the DEFAULT squash strategy (asserted via blob/tree-presence, not patch-id).
- **SC-002**: In a real mission where a canceled WP's file rode a carrier lane, a default `spec-kitty merge` refuses (exit ≠ 0) and the removed file is absent from the target tree — zero exit-0 data loss on the default path.
- **SC-003**: An interrupted `spec-kitty merge --strategy merge`, resumed with `spec-kitty merge --resume`, lands the full merge on the correct target with every pre-interrupt approved commit reachable — zero silent strategy downgrade and zero lost lane tips.
- **SC-004**: A stale local-head coordination branch carrying committed matrix rows survives a second `issue-verdict` write; the committed rows are never clobbered.
- **SC-005**: The blast-radius suites (`tests/merge`, `tests/coordination`, `tests/git`, `tests/lanes`, `tests/terminus`) and `make test-fast` are green, with zero new `ruff` / `mypy` / `ruff format` findings attributable to this mission.
- **SC-006**: A clean default squash merge and a genuine first-write self-materialization both still succeed (the fixes add no false-refusal), each proven by a dedicated red→green test.
