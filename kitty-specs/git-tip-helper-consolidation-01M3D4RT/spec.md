# Mission Specification: Consolidate target-branch tip-capture helper + reclaim tasks-lifecycle squad MINORs

**Mission Branch**: `fix/git-tip-helper-consolidation`
**Created**: 2026-09-25
**Status**: Draft
**Input**: Epic #4883 slice — anchor #4857 (consolidate target-branch tip-capture) plus folded squad MINORs #4593 (item 1) and #4152 (items 2 & 3).

## Intent Summary

Spec Kitty's planning-pin classifier (`classify_recorded_pin`) decides whether a lane's recorded planning commit is behind, at, or ahead of the target-branch tip. It **trusts whatever tip value each caller hands it**, and that tip is captured today by **two helpers** — but, contrary to the original issue framing, they are **behaviourally identical** (empirically verified on git 2.43.0: bare `git rev-parse <name>` and `git rev-parse --verify <name>` both resolve a branch+tag name collision to the *tag* SHA and exit 0; the env difference is inert). The **real latent defect** is one both helpers share: they resolve the **bare** branch name, so if a tag ever collides with the target-branch name the pin is classified against the *tag*, not the branch tip — whereas the merge-preflight and coordination-doctor paths already resolve `refs/heads/{target_branch}`. This mission gives "the target-branch tip" **one canonical owner** that resolves `refs/heads/{branch}` deterministically, closing that inconsistency, proven RED-first by a branch/tag-collision test.

Batched with the anchor (same tasks→lanes→finalize lifecycle, and a shared `core/vcs/git.py` blast radius) are two low-risk squad-flagged tidies: a merge-history-accuracy fix for the move-task behind-count message, and the removal of a behavior-preserving dead guard plus a load-bearing test-assertion fix in the finalize path.

**Primary actor**: a Spec Kitty maintainer / mission author driving the `finalize-tasks` → lane-allocation → `move-task` → merge lifecycle.
**Trigger**: the target-branch tip is captured for pin classification (and, in the defect case, a tag shares the target branch's name).
**Desired outcome**: the pin is always classified against the target **branch** tip, from one canonical authority — never a same-named tag, and never divergent across callers.
**Invariant that must always hold**: for the same repository state, every `classify_recorded_pin` caller observes the identical target-**branch** tip value (`refs/heads/{branch}`), including the identical result for a missing branch (`None`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One canonical target-branch tip authority (Priority: P1)

Today the classifier-tip callers capture the tip by the **bare** branch name (`_rev_parse`/`_capture_target_branch_tip`). When a tag collides with the target-branch name, git resolves the bare name to the **tag** (verified: bare `dup`→tag SHA), so the pin is classified against the wrong commit — while `merge/preflight.py` and `_coordination_doctor.py` already resolve `refs/heads/{target_branch}` and get the branch tip. This mission introduces one canonical `capture_branch_tip` that resolves `refs/heads/{branch}`, and routes all classifier-tip callers through it.

**Why this priority**: this is the anchor (#4857); it closes a real (if rare) misresolution and establishes the single tip-capture authority DIRECTIVE_044 wants.

**Independent Test**: a branch/tag-collision test — a branch `dup`@C1 and a tag `dup`@C2 — asserts `capture_branch_tip(repo,"dup")` returns C1 (the branch), demonstrating the bare form returned C2 (the tag). RED against a bare-name helper, GREEN with `refs/heads/`.

**Acceptance Scenarios**:

1. **Given** a target branch with no same-named tag, **When** the tip is captured, **Then** the canonical helper returns the same SHA as before (no change for the common case).
2. **Given** a missing target branch, **When** the tip is captured, **Then** the helper returns `None` — never raises.
3. **Given** a tag colliding with the target-branch name (branch@C1, tag@C2), **When** the tip is captured, **Then** the helper returns the **branch** tip C1 (via `refs/heads/`), not the tag C2 that the bare name resolved to.
4. **Given** the consolidated helper, **When** a maintainer reads its docstring, **Then** the single resolution/error contract (`rev-parse --verify refs/heads/{branch}`, env, `None`-on-missing) is stated in one place.

---

### User Story 2 - Accurate behind-count on merge-rich target branches (Priority: P2)

When a lane is behind its target branch, `move-task` reports how many *source* commits it must rebase across (excluding orchestrator ledger commits). On a merge-heavy target branch, commits that arrived via a merge TREESAME to the followed parent are dropped from the count under git's default history simplification, so the block message can understate divergence (#4593 item 1). This is message-only — the actual gate still blocks from the full merge-base diff.

**Why this priority**: a correctness improvement to operator-facing guidance; no gate impact, so lower than the anchor.

**Independent Test**: on a synthetic merge-rich target branch, the behind-count reported matches the true number of source-touching commits (not the history-simplified undercount).

**Acceptance Scenarios**:

1. **Given** a target branch whose divergence includes a TREESAME merge of source commits, **When** the behind-count is computed, **Then** the count includes those commits.
2. **Given** any target branch, **When** the count cannot be determined, **Then** the existing fail-open fallback (raw behind count) is preserved.

---

### User Story 3 - Honest finalize-path code and tests (Priority: P3)

Two behavior-neutral tidies in the finalize dependency-resolution path (#4152 items 2 & 3): a guard/read pair that is provably dead weight, and a test whose exit-code assertion cannot actually distinguish success from the failure it claims to prove.

**Why this priority**: pure hygiene; no user-visible behaviour change.

**Independent Test**: the dependency-resolution result is byte-identical before and after removing the guard (covered by the existing resolution tests); the finalize cyclic-dependency test fails if the production path ever returns exit 0.

**Acceptance Scenarios**:

1. **Given** a WP whose frontmatter omits `dependencies`, a WP with `dependencies: []`, and a WP with non-empty `dependencies`, **When** dependencies are resolved, **Then** the resolved values are identical to the pre-change output for all three.
2. **Given** the finalize cyclic-dependency regression test, **When** the production path returns a success exit code, **Then** the test fails (the exit-code assertion is load-bearing, not masked by a fallback).

### Edge Cases

- **Tag/branch name collision**: a tag sharing the target-branch name — the canonical helper resolves the **branch** (`refs/heads/{branch}`), never the tag (the defect this closes).
- **Missing branch**: the canonical helper degrades to `None` and never raises (preserving finalize's graceful-degradation and the lane path's `None`-on-failure behaviour).
- **Merge-env ratchet**: every subprocess in `lanes/merge.py` must continue to route its environment through the single merge-env authority (existing architectural ratchet); the consolidation must not bypass it.
- **Behind-count undeterminable**: preserve the existing fail-open fallback to the raw behind count.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Single canonical tip-capture authority | As a maintainer, I want one helper to own "capture the target-branch tip", resolving `refs/heads/{branch}`, so all classifier-tip callers get the branch tip from one place. | High | Open |
| FR-002 | Documented resolution/error contract | As a maintainer, I want the canonical helper to document one contract (`rev-parse --verify refs/heads/{branch}`, env, `None`-on-missing) so the resolution semantics have a single stated authority. | High | Open |
| FR-003 | Branch/tag-collision regression (RED-first) | As a maintainer, I want a test proving the pin resolves the branch tip, not a same-named tag, so the misresolution is closed by construction and cannot regress. | High | Open |
| FR-004 | Accurate move-task behind-count on merge-rich targets | As an operator, I want the behind-count message to include source commits reachable through TREESAME merges so that the reported divergence is not understated. | Medium | Open |
| FR-005 | Remove dead frontmatter-field guard + redundant read | As a maintainer, I want the provably dead `dependencies`-field guard and its per-WP full-file read removed without any change to resolved dependencies so that the finalize path carries no misleading dead weight. | Low | Open |
| FR-006 | Load-bearing cyclic-dependency exit-code assertion | As a maintainer, I want the finalize cyclic-dependency test to fail on a success exit code so that its exit-code claim actually protects the behaviour it names. | Low | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No behaviour change for the common case | For a target branch with no same-named tag, the consolidated helper returns the byte-identical SHA the prior helpers returned today (verified by a regression on a no-collision ref). Only the tag-collision case changes (now correctly the branch tip). | Reliability | High | Open |
| NFR-002 | Complexity ceiling | Every function added or modified stays at cyclomatic complexity ≤ 15 (Ruff C901 / Sonar S3776 aligned). | Maintainability | Medium | Open |
| NFR-003 | New-code test coverage | Every new or changed branch/helper is exercised by a focused test in this mission (Sonar new-code coverage gate; diff-cover ≥ 90%). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Scope excludes the third tip helper | `implement_support._rev_parse` has a distinct contract (returns a string with an `"unknown"` sentinel, resolves a base branch not a tip) and is explicitly out of scope; it must not be folded into the consolidation. | Technical | High | Open |
| C-002 | Preserve the merge-env ratchet | The consolidation must keep every `lanes/merge.py` subprocess routing its env through the single merge-env authority (FR-008b architectural ratchet). | Technical | High | Open |
| C-003 | Message-only for #4593 | The behind-count accuracy fix is message-only; the blocking decision must continue to derive from the full merge-base diff, and the fail-open fallback must be preserved. | Technical | Medium | Open |
| C-004 | Behavior-preserving tidies | The #4152 code tidy must not change resolved dependencies for any of {absent field, present-empty `[]`, present non-empty}; it is a pure dead-code removal. | Technical | High | Open |

### Key Entities

- **Target-branch tip**: the commit SHA at the head of the mission's target branch; the value `classify_recorded_pin` compares a lane's recorded planning commit against.
- **Recorded planning pin**: the SHA a lane records at allocation/finalize time, later classified as behind/at/ahead of the tip.
- **Tip-capture helper**: the code surface that resolves a branch ref to a tip SHA (today two; after this mission, one canonical authority for the classifier callers).

## Issue Matrix *(mandatory — mission addresses GitHub issues)*

| Issue | Relationship | Owes work? | Planned verdict |
|-------|--------------|-----------|-----------------|
| #4857 | Anchor — tip-capture consolidation | Yes | Addressed by FR-001/002/003 |
| #4593 | Folded — item 1 (`--full-history` behind-count) | Yes (item 1) | item 1 addressed by FR-004; **item 2 declined** (body-form on merged PR #4581) |
| #4152 | Folded — items 2 & 3 | Yes (items 2 & 3) | item 2 → FR-005; item 3 → FR-006; **item 1 declined** (conflicts with item 2; would warn on the intended #4135 path) |
| #4883 | Parent epic (reclaim deferred squad MINORs) | No (context) | not-applicable (parent) |
| #4611 | Considered, **dropped from this slice** | No (here) | not-applicable — reparented under Epic #4441 (template authoring-contract completeness); belongs to a future template-contract mission |
| #4441 | Context — #4611's functional epic | No (context) | not-applicable (context) |

### Explicit dispositions (Epic #4883 "never silently lost")

- **#4152 item 1** — DECLINED. Emitting a warning when a present-but-empty `dependencies: []` is discarded requires the `_raw_frontmatter_has_field` guard that #4152 item 2 removes as dead weight (mutually exclusive), and the discard is the *intended* #4135 map-requirements serialization behaviour, so the warning would fire on the happy path.
- **#4593 item 2** — DECLINED (body-form). PR #4581 is merged; its `## Blast radius` `Files:` line is historical and the coverage claim was squad-verified.
- **#4611 (all items)** — DROPPED from this slice. #4611 is parented under Epic #4441 ("a rule added to one template must reach every shipped copy"), a more specific functional home than #4883; its stale-override fix also cannot be applied as the finding literally proposes without reddening the ownership-rule test suite, so it deserves that epic's dedicated treatment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Exactly one code surface resolves the target-branch tip for `classify_recorded_pin` callers (down from two), and it resolves `refs/heads/{branch}`.
- **SC-002**: The branch/tag-collision regression passes (helper returns the branch tip C1, not the tag C2), and is demonstrably RED against a bare-name resolution.
- **SC-003**: The move-task behind-count equals the true source-commit divergence on a merge-rich target branch (no history-simplification undercount) in a focused regression.
- **SC-004**: The finalize dependency-resolution output is unchanged across {absent, present-empty, present-non-empty} `dependencies` (existing tests green with the dead guard removed), and the cyclic-dependency test fails if the production path returns exit 0.

## Assumptions

- The consolidated helper resolves `git rev-parse --verify refs/heads/{branch}` and keeps the optional merge-env pass-through (inert for `rev-parse`, but preserved for the C-002 ratchet). The `refs/heads/` decision was confirmed with the operator (2026-09-25) after the adversarial squad disproved the original ambiguous-divergence premise; it matches the resolution `merge/preflight.py` and `_coordination_doctor.py` already use.
- All six classifier-tip callers pass a plain local branch name (`target_branch` / `manifest.target_branch`) — never a SHA or a qualified/remote ref (verified) — so `refs/heads/{branch}` is the correct, low-risk resolution.
- Both former call paths terminate at `classify_recorded_pin`, confirming they are the same semantic operation (tip capture for pin classification) and a legitimate consolidation target.
- The only behaviour change is the tag/branch-collision case (now correctly the branch tip); the common no-collision case is unchanged. #4857 is a small correctness fix + single-authority consolidation; #4593/#4152 are message/hygiene folds.
