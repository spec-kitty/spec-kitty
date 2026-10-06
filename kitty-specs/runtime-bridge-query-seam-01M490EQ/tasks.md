# Work Packages: Extract the runtime_bridge query/answer decision-builder seam

**Inputs**: Design documents from `kitty-specs/runtime-bridge-query-seam-01M490EQ/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/module-layout.md, quickstart.md

**Tests**: required (ATDD red-first, charter SO #4). The acceptance gate is the module-layout contract test that WP01 lands. Its per-module rows start strict-xfail and flip as each module is extracted.

**Organization**: subtasks (`Txxx`) roll up into six work packages (WP06 added after #5822 merged; it runs before WP05). They run in sequence in the repository root checkout (`single_branch`), one new module per migration WP, and close with a false-green sweep.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows, not checkboxes. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done --mission runtime-bridge-query-seam-01M490EQ`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Module-layout contract test, per-module rows strict-xfail | WP01 | |
| T002 | Characterise mapping gaps (`_build_decision_required_prompt_file`, `_resolve_wp_board_action` declines, `_count_wp_endings`, `_reduced_wp_lane`) | WP01 | [P] |
| T003 | Characterise read-path gaps (answer missing-dir / typed re-raise, `_query_read_runtime_plan` re-raise, query blocked + temp-run cleanup) | WP01 | [P] |
| T004 | Characterise the decision-log owned re-raise | WP01 | [P] |
| T005 | Create `runtime_bridge_decision_mapping.py`, move the D-1 names | WP02 | |
| T006 | Bridge calls mapping names on `_mapping`; drop now-unused imports | WP02 | |
| T007 | Engine imports mapping at top level; remove the `_rb` back-edge | WP02 | |
| T008 | Repoint tests for mapping names (call-path review, fake-ran assertions) | WP02 | |
| T009 | Extend the `test_bridge_decision_builder.py` source scans; flip the mapping rows | WP02 | |
| T010 | Create `runtime_bridge_decision_log.py`; move the wrapper + helpers | WP03 | |
| T011 | Repoint io's deferred import; bridge calls `_decision_log` | WP03 | |
| T012 | Repoint tests + write-side census / consumer list | WP03 | |
| T013 | Flip the decision-log rows | WP03 | |
| T014 | Create `runtime_bridge_query.py`; move the read path | WP04 | |
| T015 | Plain re-exports on the bridge; drop unused imports | WP04 | |
| T016 | Repoint tests for query/answer names (call-path review) | WP04 | |
| T017 | Emitter-seam S8 + coord-read gate follow the move | WP04 | |
| T018 | Flip the query rows (gate fully green) | WP04 | |
| T019 | Dead-patch probe after the move; diff call counts against the baseline | WP05 | |
| T020 | Static go-silent cross-check; disposition every hit | WP05 | |
| T021 | Bridge/engine/io header docs for the new layout | WP05 | |
| T022 | Full targeted verification + static checks | WP05 | |
| T023 | Create `runtime_bridge_guards.py`; move the guard facts + WP-advance guard | WP06 | |
| T024 | Move `_resolve_runtime_feature_dir` to identity; repoint `decision.py` | WP06 | |
| T025 | io + composition import the guards module at top level; drop their `_rb` imports | WP06 | |
| T026 | Repoint tests for the moved names (call-path review) | WP06 | |
| T027 | Extend the canonical no-compat-delegates gate with the new seams; layout gate: no seam imports the bridge | WP06 | |

---

## Work Package WP01: Acceptance gate and characterisation (Priority: P1)

**Goal**: the layout contract exists and is red where the move has not happened yet (strict-xfail rows), and the thin-coverage branches of the moved code are pinned through public entries.
**Independent test**: `pytest tests/runtime/test_runtime_bridge_query_seam_layout.py tests/runtime/test_runtime_bridge_query_characterisation.py` passes on the base, with the layout rows xfailing strictly.
**Prompt**: `tasks/WP01-acceptance-gate-and-characterisation.md`

### Included Subtasks
- T001, T002, T003, T004

### Dependencies
- none

### Risks & Mitigations
- Characterisation tests that patch `runtime_bridge.<name>` would become false greens themselves. They drive public entries with real fixtures and patch only modules below the moved code.

---

## Work Package WP02: Decision-mapping module and engine back-edge (Priority: P1)

**Goal**: the shared mapping lives in `runtime_bridge_decision_mapping.py`; the engine adapter imports it directly.
**Independent test**: mapping rows of the layout gate flip to pass; `grep "import runtime_bridge" runtime_bridge_engine.py` is empty.
**Prompt**: `tasks/WP02-decision-mapping-module-and-engine-back-edge.md`

### Included Subtasks
- T005, T006, T007, T008, T009

### Dependencies
- Depends on WP01

### Risks & Mitigations
- Squad T-1: repointing an import of a moved name leaves sibling patches (`_state_to_action`, `_build_prompt_or_error`) on the bridge dead. Review every patch in the same block and add fake-ran assertions.

---

## Work Package WP03: Decision-log module (Priority: P1)

**Goal**: `_wrap_with_decision_git_log` and its helpers live in `runtime_bridge_decision_log.py`; io no longer imports the bridge for `DecisionGitLogUnavailable`.
**Independent test**: decision-log rows of the gate flip; the write-side census gate is green against the new path.
**Prompt**: `tasks/WP03-decision-log-module.md`

### Included Subtasks
- T010, T011, T012, T013

### Dependencies
- Depends on WP02

### Risks & Mitigations
- `DecisionGitLogUnavailable` is caught by class outside the package; it stays one class object, re-exported later in WP04 (the bridge imports it from the new module in this WP already).

---

## Work Package WP04: Query module and public re-exports (Priority: P1)

**Goal**: the read path lives in `runtime_bridge_query.py`; the bridge re-exports the public names as the same objects and keeps no unused import.
**Independent test**: the whole layout gate passes; the targeted surface is green.
**Prompt**: `tasks/WP04-query-module-and-public-re-exports.md`

### Included Subtasks
- T014, T015, T016, T017, T018

### Dependencies
- Depends on WP03

### Risks & Mitigations
- The largest go-silent exposure (`get_mission_type`, `_compute_wp_progress`, `runtime_emitter_for_mission`). Review each by call path and add fake-ran assertions.

---

## Work Package WP05: False-green sweep, docs and verification (Priority: P1)

**Goal**: prove no patch went dead because of the move (probe call counts plus the static cross-check), document the new layout, and run the full targeted verification.
**Independent test**: the probe diff lists no `(test, name)` whose call count dropped; each static hit has a disposition in research.md R-6.
**Prompt**: `tasks/WP05-false-green-sweep-docs-and-verification.md`

### Included Subtasks
- T019, T020, T021, T022

### Dependencies
- Depends on WP06

### Risks & Mitigations
- A repointed patch that now intercepts may change which branch a test exercises; check it against the test's intent.

---

## Work Package WP06: Guards module and the last back-edges (Priority: P1)

**Goal**: no `runtime_bridge_*` module imports the bridge. The guard facts and the WP-advance guard live in `runtime_bridge_guards.py`, and `_resolve_runtime_feature_dir` lives in identity (plan D-7).
**Independent test**: the layout gate's "no seam imports the bridge" row passes; the canonical `test_bridge_no_compat_delegates.py` covers the new seams and is green.
**Prompt**: `tasks/WP06-guards-module-and-the-last-back-edges.md`

### Included Subtasks
- T023, T024, T025, T026, T027

### Dependencies
- Depends on WP04

### Risks & Mitigations
- Tests that patch `runtime_bridge.<guard>` to steer io's fact port fail loudly once the name leaves the bridge. Repoint them at the guards module and prove the fake ran.
