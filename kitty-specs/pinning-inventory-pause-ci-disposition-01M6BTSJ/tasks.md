# Work Packages: Record the `pr:pause-ci` pin's disposition and refresh the derived pinning inventory

**Inputs**: `kitty-specs/pinning-inventory-pause-ci-disposition-01M6BTSJ/` — spec.md, plan.md
**Prerequisites**: spec.md, plan.md

Two work packages, in dependency order: the recorded decision and its regenerated artefact, then the written record. There is no new test: the invariant is already owned by two existing gates, and this defect is missing *data*, not missing coverage (spec, `Directive 041` row).

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Record the disposition and regenerate the artefact (Priority: P1)

**Goal**: `DISPOSITIONS` carries the adjudication for `tests/ci/test_pause_ci_label.py::_REQUIRED_GATES`, and `tests/release/pinning_rule_inventory.json` is committed exactly as the deriver emits it — no `disposition: null` row, `--check` exit 0.
**Independent Test**: `PYTHONPATH=src python scripts/ci/derive_pinning_inventory.py --check` exits 0, and `SPEC_KITTY_STRICT_PINNING_INVENTORY=1 pytest tests/release/test_pinning_inventory_fresh.py` passes with that test file unmodified. Removing the new `DISPOSITIONS` entry and re-deriving reds the completeness gate on the same fixture; hand-editing one artefact line reds the freshness gate.
**Prompt**: `tasks/WP01-record-disposition-and-regenerate.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

- T001 Confirm both halves red on the branch tip before any edit (`--check` exits 1; blind regeneration reds the completeness gate with `disposition None`)
- T002 Add the `DISPOSITIONS` entry — `("none", <reason ≥ 60 chars naming the surviving host job and that the file never names the retired job>)` — as the trailing entry of the executed-`rewrite`/`none` block, matching the surrounding style
- T003 Regenerate with `python3 scripts/ci/derive_pinning_inventory.py`; confirm the only added row is `_REQUIRED_GATES` with `disposition: "none"` and zero rows removed
- T004 Prove non-vacuity half by half: drop the entry → completeness reds; hand-edit one artefact line → freshness reds; restore both
- T005 Confirm determinism: two consecutive derivations are byte-identical, and the committed artefact equals the derivation output
- T006 Confirm `git diff --stat` over `scripts/` and `tests/` shows exactly the deriver plus the artefact, with `tests/release/test_pinning_inventory_fresh.py` untouched

### Dependencies

- None

---

## Work Package WP02: Record the adjudication in the changelog (Priority: P2)

**Goal**: An `[Unreleased]` changelog entry naming #6998 with an impact-first bold lead, before/after, under 1,200 characters, stating that no behaviour and no gate changed.
**Independent Test**: the changelog validators pass, and the entry read alone tells a maintainer what changed and that CI semantics are unchanged.
**Prompt**: `tasks/WP02-record-the-adjudication.md`
**Requirement Refs**: FR-005, C-004

### Included Subtasks

- T007 Author the `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it)
- T008 Run the changelog validators (`tests/release/test_validate_changelog_entry.py`, `tests/release/test_changelog_fragments.py`)
- T009 Confirm #6998 still carries `status:claimed` + `taken-by-human` and the PR will carry `taken-by-human`, `ready-for-squad`, `pr:pause-ci`

### Dependencies

- Depends on WP01 (the entry describes what landed)
