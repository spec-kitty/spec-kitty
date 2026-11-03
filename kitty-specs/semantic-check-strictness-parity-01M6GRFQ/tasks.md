# Work Packages: Semantic-check strictness parity

**Inputs**: Design documents from `kitty-specs/semantic-check-strictness-parity-01M6GRFQ/`
**Prerequisites**: plan.md, spec.md

**Tests**: red-first. WP01 begins with a failing parity test through the pre-existing
entry points (`emit_semantic_check_evaluated` + `GenerationGateMiddleware`) on a repo
configured `glossary.strictness: off`, then removes the `"medium"` fallback. WP02
records the delivered behaviour and closes the mission's own bookkeeping.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).
WP02 depends on WP01 because it documents the delivered behaviour.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different file, no shared state).
- Subtasks are reference rows, not checkboxes: completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/glossary/`, `tests/agent/glossary/`, `docs/`.

---

## Work Package WP01: One resolved strictness for the event and the gate (Priority: P1)

**Goal**: `SemanticCheckEvaluated` records the strictness the generation gate enforces and
the blocking decision the gate derives, because both read the same resolution.
**Independent Test**: `uv run pytest tests/agent/glossary -q` fails on unmodified `src`
because the configured-`off` parity test sees `medium`/`blocked=True` while the gate
resolves `off`; it passes after the fix.
**Prompt**: `/tasks/WP01-single-resolution-parity.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

- T001 Red-first parity test: configured `strictness: off` + high-severity conflict, through the real emitter and the real gate, asserting both agree.
- T002 Red-first parity test: runtime `--strictness off` over a configured `max`, and configured `max` over a low-severity conflict.
- T003 Add `resolve_context_strictness` to `src/glossary/strictness.py` and make `GenerationGateMiddleware` call it.
- T004 `SemanticCheckMiddleware` gains `runtime_override`, resolves and stores `context.effective_strictness` before emitting.
- T005 `emit_semantic_check_evaluated` drops `or "medium"`, resolves through the helper when nothing was passed, and derives `blocked` from `should_block()`.
- T006 `create_standard_pipeline` threads `runtime_strictness` into the semantic-check layer; replace the test that pinned the bug.

### Implementation Notes

- The helper is the only place that knows the global → mission → step → runtime order;
  the gate must not keep a second copy of the chain.
- The emitter's resolution order is: explicit argument, then `context.effective_strictness`,
  then `resolve_context_strictness(...)`. All three yield a `Strictness`.
- `recommended_action` keeps its severity-only derivation; this mission does not change it.
- `blocked` records the gate's decision for the conflicts present at check time; layer 3
  clarification can still resolve conflicts afterwards (documented in the spec).

### Parallel Opportunities

- T001 and T002 are the same new test module and share a fixture; write both before T003.
- T004 and T005 touch different files and can proceed in parallel once T003 exists.

### Dependencies

- None (root).

### Risks & Mitigations

- **Second copy of the precedence chain** → T003 is the only site that orders the tiers;
  T005's helper call and the gate both delegate to it.
- **Deleted test looks like weakening a gate** → the removed test asserted the defect
  (`test_unresolved_strictness_is_written_as_medium`); its replacement is named in the PR body.
- **Contract drift** → NFR-001 is pinned by `build_record()` on every new event fixture.

---

## Work Package WP02: Changelog fragment, docs and mission record (Priority: P2)

**Goal**: The behaviour change is documented where users look, and the Mission's own record
(issue matrix, tracers) is complete.
**Independent Test**: `uv run --frozen python -m scripts.docs.check_changelog_style` passes on
the new fragment; the issue matrix carries a resolved `#7065` row.
**Prompt**: `/tasks/WP02-changelog-docs-record.md`
**Requirement Refs**: FR-001, FR-002, SC-001

### Included Subtasks

- T007 Changelog fragment `docs/changelog/unreleased/<pr>.fixed.md` with the impact-first lead.
- T008 Document the resolved-strictness source for `SemanticCheckEvaluated` in the glossary docs surface the change touches.
- T009 Close the Mission tracers and resolve the `#7065` issue-matrix row.

### Implementation Notes

- Fragments, not `docs/changelog/CHANGELOG.md` (#6988): `check_changelog_style` rejects the old
  `[Unreleased]`-entry shape.
- Name the fragment with the PR number once the PR exists, per `docs/changelog/unreleased/README.md`.
- Regenerate only the docs surface this diff changes; verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci` (errors=0) rather than a full rebuild
  on a shared machine.

### Parallel Opportunities

- T007 and T008 touch different files and can proceed in parallel.

### Dependencies

- WP01 (the documented behaviour must exist).
