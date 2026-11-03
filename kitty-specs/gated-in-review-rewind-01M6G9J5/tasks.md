# Tasks: Gated in_review rewind (#7080)

**Mission**: `gated-in-review-rewind-01M6G9J5` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Branch**: `issue-7080-gated-in-review-rewind` (planning base and merge target)

Two sequential work packages. WP01 closes the reported defect end to end: the emit path
threads the structured review pointer and `in_review -> in_progress` joins the one owning set,
with every door refusing a pointerless row before the append. WP02 ships the operator-facing
position (reference page + changelog fragment) and the docs gates.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: `prepare_transition` records `review_result.reference` as the event's `review_ref` when the caller supplied none; the recorded row validates against the pinned contract | WP01 | |
| T002 | Red-first: `agent status emit` refuses a pointerless `in_review -> in_progress` before the append (log byte-identical), and the same request carrying a structured review result appends one row and validates | WP01 | |
| T003 | Add `(IN_REVIEW, IN_PROGRESS)` to `REVIEW_REF_REQUIRED_EDGES`; update the owning comment and the auditor docstring | WP01 | |
| T004 | Flip the #6955 deferral pins deliberately: `in_review` moves from the exclusion lists to the positive pin, with the reason in place; no assertion about `approved` either way | WP01 | |
| T005 | Ratchet: every local member is a real requirement of the pinned dependency (pointerless invalid / pointer-carrying valid), the set is a subset of the contract's gated family, and the derivation performs no I/O | WP01 | |
| T006 | Golden parity fixture: only the `in_review -> in_progress`/`in_review -> doing` rows move (four verdicts flip; the rest report the review_ref refusal), with the amendment note in `test_transitions.py` | WP01 | |
| T007 | Writer/auditor pins: force-insurmountable on the added edge, migration exemption, explicit-pointer-wins and blank-pointer-still-refused controls | WP01 | |
| T008 | `docs/architecture/status-model.md`: the gated family, the pointer each writer supplies (including the derivation), and the append-only position for pre-fix rows | WP02 | |
| T009 | Changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` | WP02 | |
| T010 | Docs gates: `check_docs_freshness --ci` (errors=0) and the terminology guard | WP02 | [P] |

## WP01 — One seam derives the pointer, one set gates the edge

**Prompt**: [tasks/WP01-derive-pointer-and-gate-edge.md](tasks/WP01-derive-pointer-and-gate-edge.md)
**Goal**: `agent status emit WP01 --to in_progress` from `in_review` with a structured review
result records that result's `reference` as `review_ref` and the row validates against the
pinned `spec_kitty_events` contract; a pointerless request on the same edge is refused before
the append with the ledger byte-identical; every other edge keeps its verdicts.
**Priority**: P1.
**Independent test**: `pytest -q tests/status/test_forced_rewind_requires_review_ref.py tests/status/test_transition_pipeline.py tests/status/test_transitions.py`.
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-009, SC-001, SC-002, SC-003, SC-004, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-006.
**Dependencies**: none.

T001 pipeline derivation (red) (WP01)
T002 door refusal (red) (WP01)
T003 edge set + docstrings (WP01)
T004 deferral pin flip (WP01)
T005 contract ratchet + purity probe (WP01)
T006 golden fixture amendment (WP01)
T007 writer/auditor pins (WP01)

**Sketch**: two red commits first (T001, T002) → the edge and its docstrings (T003) → the
pins, ratchet and golden rows (T004–T007). **Risks**: deriving over a caller-supplied pointer;
adding an exact-set assertion that #7102's `approved` edge would falsify; touching any edge
outside `in_review -> in_progress`.

## WP02 — The operator-facing position

**Prompt**: [tasks/WP02-docs-and-changelog.md](tasks/WP02-docs-and-changelog.md)
**Goal**: the status reference states the contract's three gated rewinds, names the pointer
each writer supplies (including the structured-review derivation), keeps the edge-set
statement true for this branch, and states the append-only position for rows written before
the fix; the change ships as a per-PR changelog fragment.
**Priority**: P2.
**Independent test**: `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0) and `uv run pytest -q tests/docs -k "terminology or status_model"`.
**Requirements**: FR-008, SC-001, C-003, C-005.
**Dependencies**: WP01.

T008 status reference update (WP02)
T009 changelog fragment (WP02)
T010 docs gates (WP02)

**Sketch**: family statement → writer table → edge-set statement → append-only position →
fragment. **Risks**: documenting the `approved` edge as locally gated when this branch leaves
it to #7102; a full CLI-reference rebuild on a shared machine (regenerate only what this diff
changes).
