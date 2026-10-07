# Mission Specification: meta.json merge driver honours the merge base

**Mission Branch**: `fix/meta-driver-base-aware`  
**Created**: 2026-10-06  
**Status**: Draft  
**Input**: User description: "Fix #5460 (P0): the kitty-specs/**/meta.json git merge driver ignores the merge base, so an ordinary `git pull` in the clone that ran `mission close --discard` silently reverts the discard with exit 0 and the reverted state is pushed. Single WP, base-aware 3-way field merge, red-first per ADR 2026-07-17-1."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A discarded mission stays discarded after a pull (Priority: P1)

A team member closes a mission with `mission close --discard` in their clone while a teammate is still moving work packages on the same mission. The push is rejected because the teammate pushed first, so the member runs an ordinary `git pull`. The merge must keep the discard (the `discarded_at` stamp, the coordination flatten that removes `topology` and `coordination_branch`, and `flattened: true`) because only this clone changed those fields since the common ancestor; the teammate's own fields (`vcs`, `vcs_locked_at`) must be taken because only the teammate changed them. Today the merge driver copies the teammate's whole record and the discard disappears, exit 0.

**Why this priority**: silent loss of a lifecycle marker that the whole team relies on; the shared record then says the mission is live and the teammate's workflow carries on where it should have been refused (#5460, P0 under the honesty ADR).

**Independent Test**: two branches of one repository diverge from a common `meta.json`; one side discards (deletes two keys, adds one, flips one), the other changes two unrelated keys; a `git merge` through the registered driver yields a record containing both sides' changes and no reverted field, and git exits 0.

**Acceptance Scenarios**:

1. **Given** a common ancestor `meta.json` with `topology: coord` and `coordination_branch` set, **When** side A deletes both keys, adds `discarded_at` and sets `flattened: true` while side B only sets `vcs` and `vcs_locked_at`, **Then** the merged record has A's four changes and B's two changes and nothing else differs from the ancestor.
2. **Given** the same setup, **When** side A integrates with `git pull --rebase` instead of a merge (the sides swap: the discard commit is replayed on top of B's), **Then** the discard also survives — this is the same-fixture positive control that is green before and after the change (today's two-way rule already keeps it under rebase).
3. **Given** the same divergence, **When** the merge runs, **Then** git exits 0 and the record was written by the driver (the test proves the driver's invocation; a merge that "passes" because the driver did not fire is not a pass).

---

### User Story 2 - Consolidation keeps its reconciliation results (Priority: P1)

When a mission branch is squashed onto its target, the same driver reconciles the target's accepted-newer provenance (acceptance and VCS stamps, mission number, merge bookkeeping) with the mission's planning keys. A squash records no ancestry, so after `mission reopen` and a second consolidate git hands the driver the *original* fork point as the ancestor; a base-aware merge would then resurrect target-side content the mission removed. Therefore the consolidation squash keeps today's two-way rule explicitly (Decision Moment `01M493BC3KPSC4FT6XSC7ESNDN`): every result the driver produces for the mission→target squash stays byte-identical, and base-awareness applies to every merge with real ancestry (ordinary merges, pulls, rebases, and the lane→mission merges inside consolidation).

**Why this priority**: the driver is shared by the pull path and the consolidation path; a fix for one must not move the other.

**Independent Test**: the existing driver goldens and reconciler tests pass unchanged; a consolidation squash on a fixture with a real, differing ancestor reconciles exactly as today (two-way), and the same fixture through an ordinary merge reconciles base-aware.

**Acceptance Scenarios**:

1. **Given** the five existing meta-driver golden cases (`base-absent`, `field-union` whose ancestor parses to `{}`, `identical-sides`, `malformed-json`, `path-injection`), **When** the driver runs, **Then** every `expected_A` byte sequence and exit code is unchanged, and the pull request shows zero diff under those five case directories.
2. **Given** both sides changed the same target-authoritative key differently (e.g. `status`) in an ordinary merge with a real ancestor, **When** the driver runs, **Then** the target side's value wins, including the existing `mission_number` rule that an unassigned target number never overrides an assigned mission number.
3. **Given** both sides changed the same planning key differently (e.g. `purpose_tldr`) in an ordinary merge with a real ancestor, **When** the driver runs, **Then** the mission side's value wins, as today.
4. **Given** only the mission side changed a target-authoritative key since the ancestor in an ordinary merge, **When** the driver runs, **Then** the mission's value survives (decided: target-authoritative keys win only on a genuine conflict, Decision Moment `01M490FHTGTH51TAD3KNPVMG8H`).
5. **Given** a consolidation squash whose ancestor differs from both sides, **When** the driver runs for the lane-merge pipeline, **Then** the output equals today's two-way result byte-for-byte (the squash opt-out is proven by a fixture whose two-way and three-way results differ).

---

### User Story 3 - A damaged ancestor never produces a quiet guess (Priority: P2)

If the ancestor record git hands to the driver cannot be read, the driver must stop loudly so git shows a conflict, exactly as it already does for a damaged side.

**Why this priority**: a silent fallback on a corrupt ancestor would reintroduce the wrong-authority write this mission removes.

**Independent Test**: a driver run with a malformed ancestor file fails with the driver's named error that identifies the ancestor path; a missing or empty ancestor is not an error (git passes an empty file for add/add).

**Acceptance Scenarios**:

1. **Given** an ancestor file that is not a JSON object, **When** the driver runs, **Then** it exits non-zero with the named driver error and writes nothing.
2. **Given** an absent or empty ancestor, **When** the driver runs, **Then** the result equals today's two-way field merge byte-for-byte.

---

### Edge Cases

- A key deleted on one side and changed on the other: the deletion and the change are a genuine conflict; precedence applies (target-authoritative → target wins; otherwise mission wins), never a silent resurrection of the ancestor value.
- Coupled key groups are merged as one unit, never key by key: the coordination flatten triple (`coordination_branch`, `topology`, `flattened`), the merge bookkeeping block (`merged_at`, `merged_by`, `merged_into`, `merged_strategy`, `merged_push`, `merged_commit`) and the acceptance stamp group (`accepted_at`, `accepted_by`, `accepted_from_commit`, `acceptance_mode`, `accept_commit`). If only one side changed any member, the whole group comes from that side; if both sides changed members, the whole group comes from the precedence winner. A half-flattened or half-merged record is never produced.
- An unassigned `mission_number` (missing, `null`, non-integer, zero or negative) never replaces an assigned one, whatever the ancestor says — not only on a genuine conflict (the #4900 rule holds for one-sided changes too).
- "Absent" and `null` are different values: a key missing on one side is a deletion, a key set to `null` is a change to `null`; the output contains a key exactly when the winning side contains it.
- "Empty ancestor" means an absent file, a whitespace-only file, or a file that parses to `{}`; all three select today's two-way rule.
- The ancestor is decoded exactly as the two sides are today (same reader, same tolerance); an ancestor that reader cannot decode fails the merge loud and named. A criss-cross merge whose virtual ancestor carries conflict markers is an accepted fail-loud case.
- `merge_history` stays a whole-value planning key (mission wins on conflict); losing one side's appended entry on a genuine both-sides append is a recorded residual, unchanged from today.
- Nested values (`documentation_state`, `origin_ticket`, …) are compared whole; a both-sides edit of different sub-keys is a conflict resolved by precedence, not a deep merge.
- The `acceptance_history` union can exceed the writer's history cap by restoring an entry one side trimmed; unchanged from today, recorded as a residual.
- Safety-relevant booleans (`retain_branches`, `retain_worktrees`, `commit_to_target`) follow the same precedence on a genuine conflict; failing closed on such a conflict is out of scope (C-003) and recorded as a residual.
- A key present in the ancestor and deleted on both sides stays deleted.
- A key absent from the ancestor and added on both sides with the same value appears once; with different values it is a conflict resolved by precedence.
- `acceptance_history` is append-only and is always the union of both sides; a deletion on one side is deliberately not honoured.
- `mission_number: null` is a meaningful value, not an absence: the existing #4900 rule is preserved verbatim.
- The driver output must remain byte-stable (same serialisation as the canonical writer) so a merge that changes nothing produces no diff churn.
- Rebase and `pull --rebase` invoke the same driver with the roles swapped; the per-key rule is symmetric except for precedence, which is the existing documented one.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One-sided change survives | As a team member who pulls after a rejected push, I want a `meta.json` field that only my side changed since the common ancestor (including a deleted field and an added field) to survive the merge so that my discard is not silently undone. | High | Open | [build] | no — the same fixture resolves to the teammate's record today (US1 scenario 1), and scenario 2 is the positive control |
| FR-002 | Other side's one-sided change taken | As that team member, I want a field only the other side changed to be taken from the other side so that the merge loses nothing on either side. | High | Open | [build] | no — paired with FR-001 on one fixture |
| FR-003 | Genuine conflicts keep today's precedence | As an operator consolidating a mission, I want a field changed differently on both sides to resolve as today (target-authoritative keys from the target, every other key from the mission, the existing unassigned-mission-number rule intact) so that consolidation results do not move. | High | Open | [ratchet] | no — a both-sides fixture with a real ancestor asserts each branch of the precedence |
| FR-004 | Equal changes collapse | As an operator, I want a field both sides changed to the same value to appear once with that value. | Medium | Open | [build] | no — asserted on a fixture whose ancestor differs from both sides |
| FR-005 | Acceptance history always unioned | As an operator, I want `acceptance_history` to remain the deduplicated, time-ordered union of both sides regardless of the ancestor. | High | Open | [ratchet] | no — existing union test plus a case where one side dropped an entry |
| FR-006 | Empty ancestor keeps the two-way rule | As a maintainer, I want an absent or empty ancestor to yield exactly today's two-way result so that add/add merges and every existing golden stay byte-identical. | High | Open | [ratchet] | no — the five existing goldens are the fixture; a changed byte fails them |
| FR-007 | Damaged ancestor fails loud | As a maintainer, I want a malformed ancestor to stop the driver with its named error identifying the ancestor path so that git shows a conflict instead of a guess. | Medium | Open | [build] | no — an unreadable-ancestor fixture must raise; the empty-ancestor fixture is the control |
| FR-008 | Red-first reproduction | As a release owner, I want an issue-pinned reproduction of the pull scenario that fails on today's driver for the right reason and passes after the fix — a file-level case through the driver entry point with a real ancestor file, and a real-git merge through the registered driver whose first assertions are git exit 0 and proof that the driver was invoked, with `pull --rebase` as the green-before-and-after control — so that the P0 is honestly represented per ADR 2026-07-17-1. | High | Open | [build] | no — the test is committed red before the fix commit, and a red caused by a missing driver registration fails its own invocation assertion instead |
| FR-009 | Fixtures and documentation follow | As a maintainer, I want golden cases for the one-sided-deletion, both-changed-precedence and zero-byte-ancestor shapes committed in the red commit with their correct expected bytes (so they are red before the fix), the stale "driver never reads the ancestor" golden note refreshed, the five existing golden directories unchanged, the driver documentation updated, and a user-facing changelog entry so that the new rule is discoverable. | Medium | Open | [build] | no — the new goldens are red on the pre-fix driver; the existing five must show zero diff |
| FR-010 | Coupled key groups move together | As an operator, I want the coordination flatten triple, the merge bookkeeping block and the acceptance stamp group each merged as one unit so that a merge never produces a half-flattened or half-merged record. | High | Open | [build] | no — a fixture where one member conflicts and another is one-sided must yield the whole group from one side |
| FR-011 | Consolidation squash keeps the two-way rule | As an operator consolidating a mission, I want the mission→target squash (the real integration and its dry-run preview) to keep today's two-way reconciliation explicitly, because a squash records no ancestry and its ancestor is unreliable after a reopen, so that consolidation results do not move; every merge that has real ancestry (ordinary merges, pulls, lane rebases, the lane→mission merge) is base-aware. | High | Open | [build] | no — a fixture whose two-way and three-way results differ proves the opt-out is in effect for the squash subprocess and not for an ordinary merge |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte stability | A merge whose sides equal the ancestor writes a record byte-identical to the canonical writer's output (zero diff churn); all five existing goldens produce identical `expected_A` bytes. | Reliability | High | Open |
| NFR-002 | No regression in the merge suites | The consolidation, merge-driver and discard/close test modules that pass before the change pass after it with zero changed expectations (the grounding dry run measured 2270 passed / 2 skipped / 6 xfailed). | Reliability | High | Open |
| NFR-003 | Driver latency unchanged | A driver invocation on a typical `meta.json` (under 4 KiB) takes no longer than the pre-fix driver (measured ~1.4 s wall per subprocess before and after, dominated by CLI import; the reconciliation itself is under 1 ms), so pulls and consolidations are not slowed. | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single surface | The change is confined to the meta merge-driver body, the driver's command shell (to read the pipeline opt-out), the one `git merge --squash` subprocess call in the consolidation pipeline, `_run_squash_merge`, which the dry-run preview reuses (to set it), and the tests, goldens and docs; no change to `.gitattributes` writers, `init`, migrations or merge strategy selection. | Technical | High | Open |
| C-002 | Precedence decisions | In ordinary merges target-authoritative keys win only on a genuine both-sides conflict (Decision Moment `01M490FHTGTH51TAD3KNPVMG8H`); the mission→target squash keeps the two-way rule (Decision Moment `01M493BC3KPSC4FT6XSC7ESNDN`). | Business | High | Open |
| C-003 | Out of scope | #5292 (attribute glob depth), #4316 (`reopen` after discard), #4169 (flatten commit when the target branch is gone) and failing closed on a genuine conflict stay out of this mission. | Business | Medium | Open |
| C-004 | Red-first discipline | The reproduction tests land in a commit before the fix commit and are RED there through the pre-existing entry points; after the fix they become focused unit/integration tests (no lingering `regression`/`p0_repro` marker). | Regulatory | High | Open |

### Key Entities *(include if the mission involves data)*

- **Mission record (`meta.json`)**: the per-mission lifecycle and planning record; the fields that matter here are the lifecycle markers (`discarded_at`, `flattened`, `topology`, `coordination_branch`), the target-minted provenance (acceptance and VCS stamps, `mission_number`, `status`, merge bookkeeping) and the append-only `acceptance_history`.
- **Merge sides**: the ancestor (common base), "ours" (the target checkout in a consolidation squash; the local branch in a pull) and "theirs" (the mission branch in a squash; the remote in a pull).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's two-clone reproducer reports the discard *kept* on the remote after the pull (today: *lost*), with every command still exiting 0 — [build] · no-op passable: no
- **SC-002**: 100% of the existing meta-driver goldens and reconciler tests pass with unchanged expectations, and the five existing golden directories show zero diff in the pull request — [ratchet] · no-op passable: no
- **SC-003**: The red-first reproduction tests fail on the pre-fix commit and pass on the fix commit, verified by the reviewer — [build] · no-op passable: no
- **SC-004**: A reader of the driver documentation and the changelog can tell, without reading code, which side wins for a one-sided change, a both-sides conflict and an empty ancestor — [build] · no-op passable: no

## Assumptions

- The merge base git supplies (`%O`) is the right ancestor for ordinary merges, pulls and rebases; it is unreliable for the consolidation squash (no ancestry recorded), which is why the pipeline opts out.
- Honouring a one-sided deletion is correct for every key outside `acceptance_history`; `merge_history` is also append-only but stays whole-value (recorded residual).
- The precedence list of target-authoritative keys is already correct and is reused unchanged.

## Issue Matrix

- #5460 — P0, the defect this mission fixes (claimed; verdict recorded at close).
- Context only: #4900 (closed; rule reused), #4933 (closed), #5292 / #4316 / #4169 (out of scope, see C-003).
