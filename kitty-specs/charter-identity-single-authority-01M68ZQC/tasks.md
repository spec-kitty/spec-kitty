# Work Packages: Charter identity single authority (#6433)

**Inputs**: Design documents from `/kitty-specs/charter-identity-single-authority-01M68ZQC/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: Red-first. Each work package writes its failing test through the pre-existing entry point before the fix (charter, ATDD-First Discipline; DIRECTIVE_034).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package is independently deliverable and testable.

**Prompt Files**: Each work package references a matching prompt file in `/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`.

---

## Work Package WP01: The facades answer from the identity index (Priority: P1)

**Goal**: `resolve_artifact_urn`, `resolve_config_id` and `resolve_selected_id_to_stem` answer from `IdentityIndex`, and the index reads its file list through the shared `ResolutionPass` memo, so no second stem↔id rule and no second scan remains.
**Independent Test**: the parity matrix over built-in/org/project layers × stem/declared-id/URN/normalised-id spellings passes in both directions, the ambiguous-directive refusal still fires, and a multi-call pass performs one scan per kind.
**Prompt**: `/tasks/WP01-facade-over-index.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008; NFR-004, NFR-005; C-001, C-002, C-003, C-004
**Owned files (incl. the read-seam update)**: `src/charter/activation/{kind_vocabulary,identity_index}.py`, `tests/charter/activation/test_identity_facade_6433.py` (new), `tests/charter/test_directive_resolution_memoization.py`

### Included Subtasks

T001 Write the failing parity matrix and scan-count tests for the three facades (`tests/charter/activation/test_identity_facade_6433.py`)
T002 Add `resolution_pass` to `IdentityIndex.from_roots` and read the scan through `kind_vocabulary._iter_artifact_paths`
T003 Route `resolve_artifact_urn` through the index, keeping `UnknownArtifactIdError` and the directive representable-stem refusal
T004 [P] Route `resolve_config_id` through the index, keeping `UnrepresentableDirectiveIdError` and its message
T005 [P] Route `resolve_selected_id_to_stem`'s stem probe through the index

### Implementation Notes

- The facade→index dependency is a function-local import (`identity_index` already imports `kind_vocabulary`); annotate the import with `# noqa: PLC0415`, the pattern this package already uses.
- "Directive known but no representable stem" is exactly `index.declared_id(...) is not None and index.stem(...) is None` — do not add a second rule.
- The index's fast-id read path is allowed to win for malformed YAML (documented limitation); do not reintroduce a second reader to restore the full parse.

### Parallel Opportunities

- T004 and T005 are independent once T003 establishes the delegation shape.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Syntax/behaviour drift in the existing pins (`test_kind_vocabulary.py`, `test_config_stem_parity.py`, `test_directive_identity_mapping.py`): run them unchanged; if one must change, stop and re-read the spec's C-001/C-002.

---

## Work Package WP02: Cascade-source surfaces share one index (Priority: P1)

**Goal**: `activate`/`deactivate`/`--resynthesize` resolve the cascade source token through one `IdentityIndex` per command, so a URN, declared id or normalised id cascades exactly as the stem does.
**Independent Test**: the two red-first CLI tests show identical operator output for stem, URN and normalised id on one fixture, and the ledger is identical.
**Prompt**: `/tasks/WP02-cascade-source-index.md`
**Requirement Refs**: FR-004, FR-005, FR-006; C-001; NFR-004

### Included Subtasks

T006 Write the failing CLI tests for `activate --cascade` and `deactivate --cascade` by URN and by normalised directive id (`tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py`)
T007 Route `activate._source_urn` through one index per command
T008 [P] Route `deactivate._source_urn` and `deactivate._active_urns` through one index per command
T009 [P] Route `_resynthesis_preflight._cascade_source` through the index

### Implementation Notes

- `_source_urn` returning `None` for a genuinely unknown token is a documented no-op contract; keep it.
- `_active_urns` resolves every active token in a loop: build the index once outside the loop (NFR-004), never per token.
- The CLI tests run through `typer.testing.CliRunner` on `charter_app` with `--repo-root`, `--no-compile` and a ledger-seeded project, matching `test_activate_declared_id_identity.py`.

### Parallel Opportunities

- T008 and T009 touch different files.

### Dependencies

- WP01 (the facades must already answer from the index, so the CLI sites inherit one rule).

### Risks & Mitigations

- The built-in DRG does not change between runs, so the cascade target is stable; assert on the rendered line, not on a whole-output snapshot that other fixes could shift.

---

## Work Package WP03: Pin every unknown-token policy, docs and changelog (Priority: P2)

**Goal**: one test module states the unknown-token policy of the runtime gate, the consistency check, compile and cascade-source resolution; the architecture doc and the changelog say what changed for an operator.
**Independent Test**: flipping any one surface's policy fails exactly one assertion; the changelog entry passes `validate-pr-body`-independent review and the docs freshness check.
**Prompt**: `/tasks/WP03-policies-docs-changelog.md`
**Requirement Refs**: FR-007, FR-009; SC-004

### Included Subtasks

T010 Write the four-surface unknown-token policy module (`tests/charter/activation/test_unknown_token_policies_6433.py`)
T011 Document the facade in `docs/architecture/activation-ledger-and-charter-contract.md`
T012 Add the `[Unreleased]` changelog entry with the `(#6433)` reference

### Implementation Notes

- The runtime-gate and consistency-check policies are already exercised in `tests/charter/activation/test_compile_check_identity_6433.py`; reference it rather than duplicating its fixtures, and add only the cascade-source policy there if a shared fixture is cheaper.
- The changelog entry leads with the operator-visible effect (cascade by URN), then before/after, under 1,200 characters, bold impact-first lead with `(#6433)`.

### Dependencies

- WP01, WP02.

### Risks & Mitigations

- Docs index freshness: run `uv run python -m scripts.docs.check_docs_freshness --ci` after editing; do not rebuild the whole CLI reference for a doc line.

---

## Dependency Graph

```
WP01 ──► WP02 ──► WP03
```
