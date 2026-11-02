# Tasks: Wire-valid approved reopen (#6955)

**Mission**: `wire-valid-approved-reopen-01M6EJW0` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Branch**: planning base and merge target `main`

Two sequential work packages. WP01 is the MVP: it closes #6955 on the reported door, makes
every other door refuse a pointerless gated rewind, and pins the family against the pinned
wire contract. WP02 ships the operator-facing position and the changelog fragment.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: the owned-checkout `move-task` repro — `absent` asserts the sentinel and wire validity, `provided`/`empty` assert the restored #6699 evidence arm | WP01 | |
| T002 | Red-first: `agent status emit` refuses a pointerless `approved` rewind before the append (with pointer-carrying positive control; the deferred `in_review` edge is pinned as still admitted, #7080) | WP01 | |
| T003 | Widen `REVIEW_REF_REQUIRED_EDGES` to the pinned contract's gated family; make the approved reopen feedback-recordable again (`_feedback_edge_recordable`); update the docstrings that name either rule | WP01 | |
| T004 | Pin the emitter: forced approved reopen plans `force-override`; family ratchet reads the pinned contract | WP01 | |
| T005 | Writer pins: force-insurmountable on the added edges, migration exemption, unchanged-edge matrix (`NFR-003`) | WP01 | |
| T006 | Auditor pins: pointerless family row reported, pointer-carrying row clean | WP01 | |
| T007 | `docs/architecture/status-model.md`: gated family, per-writer pointer table, edge-set statement, append-only position | WP02 | |
| T008 | Changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` | WP02 | |
| T009 | Docs freshness + terminology gates + a grep pin on the reference | WP02 | [P] |

## WP01 — One definition, conforming payload, refusing doors (#6955)

**Prompt**: [tasks/WP01-family-predicate-and-conformance.md](tasks/WP01-family-predicate-and-conformance.md)
**Goal**: the forced `approved -> in_progress` reopen records `force: true` with
`review_ref: "force-override"` and its payload validates against the pinned contract, while
every write door refuses a pointerless `approved` (or `for_review`) rewind before the append,
with the contract's third gated edge (`in_review`) explicitly deferred to #7080.
**Priority**: P1.
**Independent test**: `pytest -q tests/status/test_forced_rewind_requires_review_ref.py tests/integration/test_owned_reopen_feedback.py`.
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-008, FR-009, SC-001, SC-002, SC-003, SC-004, SC-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-006.
**Dependencies**: none.

T001 owned-checkout repro (red) (WP01)
T002 door refusal (red) (WP01)
T003 predicate widening (WP01)
T004 emitter pin + family ratchet (WP01)
T005 writer pins + matrix (WP01)
T006 auditor pins (WP01)

**Sketch**: two red commits first (T001, T002) → the one-line predicate + docstrings (T003) → emitter/ratchet/writer/auditor pins (T004–T006). **Risks**: a second literal edge set; changing the evidence arm; touching `* -> planned`.

## WP02 — The operator-facing position

**Prompt**: [tasks/WP02-docs-and-changelog.md](tasks/WP02-docs-and-changelog.md)
**Goal**: the status reference states the gated family as force-insurmountable, names the
pointer each writer supplies (including the sentinel), and states the append-only position
for rows written before the fix; the change ships as a per-PR changelog fragment.
**Priority**: P2.
**Independent test**: `uv run pytest -q tests/status/test_status_model_reference.py` and `uv run python -m scripts.docs.check_docs_freshness --ci`.
**Requirements**: FR-007, SC-001, C-003, C-005.
**Dependencies**: WP01.

T007 status reference update (WP02)
T008 changelog fragment (WP02)
T009 docs gates + reference grep pin (WP02)

**Sketch**: family paragraph → writer table → edge-set statement → append-only position → fragment. **Risks**: documenting a repair the tool does not ship; a full CLI-reference rebuild on a shared machine (regenerate nothing this diff does not change).
