# Work Packages: Scoped agent-profile sentinel lookup for the board

**Inputs**: Design documents from `kitty-specs/issue-6917-sentinel-scoped-profile-read-01M6BV17/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/agent-profile-sentinels.md, quickstart.md

**Tests**: red-first. WP01 and WP02 each begin by writing the failing guard for their own
behaviour, then make it pass.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work
package is independently reviewable; WP02 depends on WP01 because it consumes the accessor.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different file, no shared state).
- Subtasks are reference rows, not checkboxes: completion is recorded with
  `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Scoped load, lazy lineage, sole-door accessor (Priority: P1)

**Goal**: The charter layer can answer `sentinel` for a named id set without materialising the
profile catalogue or the lineage graph.
**Independent Test**: `uv run pytest tests/charter/test_agent_profile_scoped_load.py -q` passes, and
a two-id lookup parses at most three shipped profile documents where the full repository parses 26.
**Prompt**: `/tasks/WP01-scoped-load-and-accessor.md`
**Requirement Refs**: FR-001, FR-003, FR-007, C-001, C-002, C-003, NFR-004, SC-004

### Included Subtasks

- T001 Red-first scoped-loader parity test over the shipped catalogue and overlay fixtures.
- T002 Add the opt-in `only_ids` scope to `AgentProfileRepository` (default unchanged).
- T003 Restore the lazy `_graph()` lineage accessor and add a graph-parse census assertion.
- T004 Add `CharterOfferingService.agent_profile_sentinels(ids)`.
- T005 Add `ActiveCharterService.agent_profile_sentinels(ids)` and `build_agent_profile_sentinels(repo_root, ids)`.

### Implementation Notes

- Layer order, overlay field merge, schema/skip handling, and the `applies_to_languages` filter all
  come from the repository's own pipeline — do not re-implement any of them.
- The scoped read resolves ids by the repository's `<profile-id>.agent.yaml` file convention; document
  it on the parameter, and pin it with the parity test.
- `build_agent_profile_sentinels` must not construct `PackContext` or an activation ledger.

### Parallel Opportunities

- T002 and T003 touch the same file: run them in order. T004/T005 follow T002.

### Dependencies

- None (root).

### Risks & Mitigations

- Scope creep into the default load: guarded by a test that asserts the unscoped load is unchanged.
- Gate 1/2 construction census: all new construction stays in `charter/offering/`, the sole door and
  the builder — run the four sole-door gates before handing off.

---

## Work Package WP02: Board reads only the profiles it names (Priority: P1)

**Goal**: `agent tasks status` performs one scoped sentinel lookup per render and renders the 👤
marker from that mapping, with parity for every row that shows it today.
**Independent Test**: `uv run pytest tests/charter/test_tasks_status_sentinel_scope_6917.py -q`
passes; the census case counts ≤ 3 profile parses for a two-profile board and fails on unmodified
`src` (26).
**Prompt**: `/tasks/WP02-board-scoped-marker.md`
**Requirement Refs**: FR-002, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, SC-001, SC-002, SC-003

### Included Subtasks

- T006 Red-first census test through the production `status` render (count profile parses + marker text).
- T007 Replace the repository plumbing in `tasks_status_cmd` with one id-scoped lookup per render.
- T008 Update the existing marker tests (`test_human_in_charge_profile.py`, `test_cli_readers_honour_deny.py`) to the new contract, keeping deny/narrowing parity.
- T009 Prove empty-board and unknown-id behaviour (no parse, no marker, no error).

### Implementation Notes

- `_get_hic_marker` keeps its name and its `tasks.py` re-export (`test_tasks_status_cmd_seam.py` patches
  it by name); only the lookup parameter changes from a repository to a `Mapping[str, bool]`.
- The `ImportError` degrade must keep its existing narrow meaning; any other failure (malformed
  config) must still propagate to `_do_status`'s structured error handler.

### Parallel Opportunities

- T007 and T008 touch different files; T006 must land first (red).

### Dependencies

- WP01.

### Risks & Mitigations

- Marker drift on overlay layers: covered by WP01's parity fixtures plus the deny/narrowing ratchets.
- Silent relief of the fail-closed contract: keep an explicit test for the malformed-config path.

---

## Work Package WP03: Changelog and docs (Priority: P2)

**Goal**: Record the user-visible change and the new pinned accessor where maintainers look.
**Independent Test**: `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
the changelog entry passes the repo's char limit.
**Prompt**: `/tasks/WP03-changelog-and-docs.md`
**Requirement Refs**: FR-001, NFR-002

### Included Subtasks

- T010 Add the `[Unreleased]` changelog entry naming both effects of the fix.
- T011 Note the scoped sentinel read and the lazy lineage graph in the profile-load architecture page.
- T012 Close the mission tracers and the issue matrix row for #6917.

### Dependencies

- WP01, WP02.

### Risks & Mitigations

- Do not regenerate the whole CLI reference: the shared machine cache is contended by other agents.
  Regenerate only what the diff changes and verify with `check_docs_freshness --ci`.
