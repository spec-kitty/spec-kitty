# Mission Specification: Fail-closed acceptance-matrix merge driver (#4880)

**Mission Branch**: `fix/acceptance-matrix-merge-fail-closed`
**Created**: 2026-09-22
**Status**: Draft
**Input**: P0 #4880 — the `acceptance-matrix.json` merge driver embeds git conflict markers as JSON field values and exits 0, silently flipping a merged mission's `overall_verdict` from `pass` to `fail`.

## Intent Summary *(confirmed scope — discovery minimized per operator delegation; grounded in the 3-lens investigation of #4880)*

- **Primary actor**: a maintainer or agent running an ordinary `git merge` (or `spec-kitty merge`) that touches a gate/verdict artifact (`acceptance-matrix.json`, and its sibling issue-matrix).
- **Trigger**: during merge reconciliation a keyed-row field has diverged on **both** sides (add/add) from the merge base.
- **Desired outcome**: the merge **fails closed** — it leaves a git conflict for a human to resolve — instead of writing conflict-marker text into a JSON value and committing a silently-corrupted verdict.
- **Rule that must always hold**: a matrix produced by the merge driver must never contain a conflict-marker string in any field; a computed `overall_verdict` must never be silently derived from a value no one authored.
- **Boundary**: fix at the shared field-merge mechanism so **both** matrix drivers fail closed (operator-chosen altitude). The **review-cycle** merge driver is deliberately untouched (its non-aborting behavior over non-authoritative prose is correct and separately justified).
- **Known constraint**: fail-closed **reverses recorded decisions** (ADR `2026-07-23-2`, contract `merge-driver-algorithm.md:29`, completed-mission `01KZPG7V` FR-004 negative control). Amending those is in scope and must land with the fix.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A diverged verdict stops the merge instead of corrupting it (Priority: P1)

A merged mission's `acceptance-matrix.json` holds an accepted verdict (`overall_verdict: pass`). Another branch changed the same verdict field. A routine `git merge` runs the registered driver. Today the driver embeds `<<<<<<< / ======= / >>>>>>>` into the field value, exits 0, the merge commits, and the verdict silently recomputes to `fail`. This story makes that merge stop for a human.

**Why this priority**: This is the P0 defect — silent corruption of a verdict-authority record, invisible until someone opens the raw JSON. Fixing it is the whole mission.

**Independent Test**: Reproduce the incident (base `pass_fail=pending`, ours `pass`, theirs `fail`), run the driver, and assert the merge is refused (non-zero exit, conflict left in the tree) rather than committing a matrix whose verdict reads `fail`.

**Acceptance Scenarios**:

1. **Given** an acceptance matrix whose `pass_fail`/`result` diverged on both sides, **When** the merge driver runs, **Then** it fails closed (exit non-zero), the integration path does not advance the target ref, and no corrupted matrix is committed.
2. **Given** the same conflict, **When** the driver refuses, **Then** the human sees a standard git conflict to resolve — not a valid-JSON file with marker strings inside a value.

---

### User Story 2 - The "lesser variant" (prose-only divergence) also fails loudly (Priority: P1)

Even when only non-verdict fields (`description`, `notes`, `evidence`) diverge, today the file still silently gains conflict-marker strings while the verdict survives.

**Why this priority**: Leaving this uncovered is the "whack-a-field" trap the architecture review flagged — a verdict-authority artifact would still carry marker strings with no human alerted.

**Independent Test**: Diverge only `notes` on both sides; assert the driver fails closed (no marker string committed in any field).

**Acceptance Scenarios**:

1. **Given** only `description`/`notes` diverged on both sides, **When** the driver runs, **Then** it fails closed rather than embedding a marker in the prose field.

---

### User Story 3 - Corruption from any source is caught on read (Priority: P2)

If a marker-laden matrix reaches disk by any path, reading it must fail loudly rather than silently recomputing the verdict to `fail`.

**Why this priority**: Defense-in-depth. Not load-bearing once the driver fails closed, but cheap and it makes the failure mode loud for any future writer.

**Independent Test**: Construct a matrix dict with a conflict-marker string in a field; assert `AcceptanceMatrix.from_dict` raises a clear parse error instead of returning a matrix that recomputes to `fail`.

**Acceptance Scenarios**:

1. **Given** a matrix value containing `<<<<<<<`/`=======`/`>>>>>>>`, **When** it is parsed, **Then** parsing raises `AcceptanceMatrixParseError` naming the offending field.

### Edge Cases

- **Both sides identical** → no conflict; merge proceeds unchanged.
- **One-sided change only** → clean auto-merge; no refusal.
- **Out-of-domain but *authored* `pass_fail`** (a real invalid token, not a marker) → still recomputes to `fail` — that is correct and must remain (the existing `test_a4` control stays green).
- **Issue-matrix field divergence** → also fails closed under the shared mechanism (operator-confirmed altitude); non-verdict tracking rows now refuse rather than embed markers.
- **Review-cycle `.md` conflict** → unchanged; still non-aborting (non-authoritative prose).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Driver fails closed on a both-sides field divergence | As a maintainer, I want the matrix merge driver to raise/refuse on a genuine add/add field conflict instead of embedding a conflict-marker string as the field value, so a verdict is never silently corrupted. | High | Open |
| FR-002 | Refusal aborts the merge, target ref not advanced | As a maintainer, I want a driver refusal to leave a git conflict for a human and stop the integration path from advancing the target ref, so no partial/corrupt matrix is committed. | High | Open |
| FR-003 | Red-first regression proving the flip is closed | As a maintainer, I want a regression that reproduces the pre-fix `pass→fail` flip (and the prose-only marker embed) and passes only when the driver fails closed, extending the existing tests that currently green-pin the bug. | High | Open |
| FR-004 | Read-side guard rejects marker-laden values | As a maintainer, I want `AcceptanceMatrix.from_dict` to reject any field value containing a conflict marker with a clear error, so corruption from any path fails loudly instead of recomputing to `fail`. | Medium | Open |
| FR-005 | Remove the now-unreachable marker-embed path | As a maintainer, I want the dead `_field_conflict_marker` embed path removed once the driver fails closed, so the corruption mechanism cannot be reintroduced. | Medium | Open |
| FR-006 | Amend the recorded decisions and re-anchor test pins | As a maintainer, I want ADR `2026-07-23-2`, contract `merge-driver-algorithm.md:29`, and mission `01KZPG7V` FR-004, plus the pinning tests, amended in the same change to reflect fail-closed for verdict artifacts, so the fix does not red a landed gate. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero marker strings in committed matrices | No acceptance/issue matrix produced by the driver may contain `<<<<<<<`/`=======`/`>>>>>>>` in any field — asserted at 0 occurrences across driver outputs. | Reliability | High | Open |
| NFR-002 | Review-cycle behavior unchanged | The review-cycle merge driver remains non-aborting; its existing tests stay green with no behavior change. | Compatibility | High | Open |
| NFR-003 | No new cross-layer coupling | The change stays within `specify_cli` (merge driver + acceptance domain); no new import edge that violates the enforced `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli` chain. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mechanism-level, bounded scope | Fix the shared field-merge mechanism + the acceptance/issue matrix drivers + the read-side guard only. NOT a general merge-driver rewrite; NOT the review-cycle driver; NOT widening `overall_verdict` recompute semantics (raise-on-unknown is a deferred follow-up). | Technical | High | Open |
| C-002 | Closed-mission mutation guard is out of scope | The "refuse gate-artifact edits on an already-merged/done mission" guard (#4880 fix #2) is a separate follow-up issue and must consume canonical mission-state, not re-derive it. | Technical | Medium | Open |
| C-003 | Decision reversal must land with the fix | Fail-closed reverses ADR `2026-07-23-2` and mission `01KZPG7V` FR-004; those amendments are in-scope deliverables, not optional. | Regulatory | High | Open |
| C-004 | Parent epic | Tracked under epic #3044 (review-artifact & verdict integrity). | Business | Medium | Open |

### Key Entities

- **Acceptance matrix** (`acceptance-matrix.json`): the verdict-authority record for a mission; `overall_verdict` is recomputed on read from per-criterion `pass_fail` / per-invariant `result` values drawn from fixed enumerations.
- **Matrix merge driver**: the git custom merge driver (registered via `.gitattributes`) that reconciles two matrix versions during a merge; shares its field-merge step with the issue-matrix driver.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A both-sides-diverged `pass_fail`/`result` on a merged mission's acceptance matrix results in a stopped merge (human sees the conflict) — 0% silent verdict flips.
- **SC-002**: 0 conflict-marker strings appear in any field of any matrix committed by the driver, across all tested divergence shapes (including prose-only).
- **SC-003**: The pre-fix repro test is red before the change and green after; the previously bug-pinning tests are re-anchored to expect refusal.
- **SC-004**: Review-cycle merge behavior is unchanged (its tests pass without modification).

## Issue References

- **#4880** — owning issue (P0). Gating: will require an issue-matrix row before its WP can be approved.
- **#3044** — parent epic (verdict integrity). Context-only.
- **#4887** — write-seam hardening; candidate to co-scope the FR-004 read/write guard. Context-only.
- **#1424** — history: the recompute default was originally fail-*open* (unknown → `pass`); it has since inverted to `fail`. Context-only.
