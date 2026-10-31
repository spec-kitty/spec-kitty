# Work Packages: Render only the charter scope the command reads (#6462)

Mission: `issue-6462-charter-render-scope-per-call-01M69065`.
Spec: `kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/spec.md` ·
Plan: `.../plan.md` · Contracts: `.../contracts/offering-catalog-scope.md`,
`.../contracts/render-scope-census.md`.

## Subtask Format: `[Txxx] [P?] Description`

`[P]` marks a subtask safe to parallelize within its work package (different files,
no shared state). Subtask completion lives in the event log: record it with
`spec-kitty agent tasks mark-status T001 --status done --mission <mission>`. Rows below
are references, never checkboxes.

## Path Conventions

All paths are repo-root-relative. Source: `src/charter/**`, tests: `tests/charter/**`.

## Work Package WP01: Scope the offering-catalog load (Priority: P0) 🎯 MVP

**Goal**: A persona render parses only the domains its governance resolution reads, and
the census guard proves it.

**Independent test**: `uv run --frozen pytest tests/charter/test_charter_render_scope_6462.py tests/charter/activation/test_offering_catalog_scope_6462.py -q` — both fail on
unmodified `main` naming 265 parsed documents / a tactic parse, and pass after.

### Included Subtasks

- T001 Write the failing census guard: count parsed shipped documents through `parse_shipped_yaml`, assert `charter context --action implement` (and the `plan` action) parses zero tactic/styleguide/toolguide/procedure/agent-profile documents and ≤ 60 catalog documents (`tests/charter/test_charter_render_scope_6462.py`, plus the shared census helper).
- T002 Confirm the guard is red on `main` for the documented reason (265 parses, tactic documents present) and record the numbers in the mission trace.
- T003 Add the validated `domains` scope to `load_offering_catalog` (`src/charter/activation/catalog.py`): `str` or `ArtifactKind` tokens, `None` = all eight (byte-identical behaviour), unknown token → `ValueError`, `domains_scanned` on the catalog.
- T004 Unit-test the loader scope contract S-1..S-5 (`tests/charter/activation/test_offering_catalog_scope_6462.py`): default = all, scoped reads only that domain, unknown domain raises, empty scope reads nothing, absent directory semantics unchanged.
- T005 Declare the scope at the two governance call sites: `resolve_project_governance` → paradigms/directives/template_sets, `default_interview` → paradigms/directives, with the census guard green.
- T006 Prove parity: rendered text and resolved governance selections byte-identical for all six actions, with a test that pins each call site's declared scope to the fields it reads.

### Implementation Notes

- Keep the scope a parameter of the single loader (contract S-6); do not add a second
  catalog, a cache, or per-domain loading path.
- `domains_present` keeps its meaning: only scanned-and-present domains are named.
- Correct the two now-stale "parses at most once per change" comments in place
  (`DIRECTIVE_025`).

### Parallel Opportunities

- T003+T004 (loader) are one file pair; T001/T002 (guard) and T005 (call sites) touch
  different files and can be prepared in parallel, but T005 must land after T003.

### Dependencies

None. WP02 depends on this work package for the shared census helper.

### Risks & Mitigations

- **A caller reading an unscanned field gets an empty set.** Mitigated by the default
  all-domains behaviour and T006's scope-vs-reads pinning test.
- **`include_proposed`/`active_languages` interactions.** Untouched; S-7 pins them.

---

## Work Package WP02: Load profile lineage on first use (Priority: P1)

**Goal**: A profile-map reader (the read-only `agent tasks status` board, `agent profile
list`, provenance reads) never parses the shipped DRG; lineage readers still get the
graph, and still degrade to an empty graph when it cannot be loaded.

**Independent test**: `uv run --frozen pytest tests/charter/test_charter_render_scope_board_6462.py -q` — fails on unmodified `main` with 13 graph parses, passes after; the
existing agent-profile repository suites stay green.

### Included Subtasks

- T007 Write the failing board census guard: `agent tasks status` parses zero `*.graph.yaml` documents and ≤ 70 catalog documents, and a mission with a `human-in-charge` work package still renders the 👤 marker (`tests/charter/test_charter_render_scope_board_6462.py`).
- T008 Confirm the guard is red on `main` (13 graph fragments parsed) and record the number.
- T009 Make the lineage graph lazy in `AgentProfileRepository`: one `_graph()` accessor used by `_lineage_parent` and channel reachability, `drg=` argument short-circuits the lazy build, `DRGLoadError` degrades to the empty graph exactly as today.
- T010 Cover the lazy path with tests: profile-map reads build no graph (spy on the loader), `get_ancestors`/`get_children`/reachability still build it once, explicit `drg=` bypasses, unloadable graph still degrades.
- T011 Changelog `[Unreleased]` entry (impact-first, `(#6462)`, before/after) plus the module notes the change touches; append the measurement to the mission traces.

### Implementation Notes

- `src/charter/offering/agent_profiles/repository.py` line ~266: replace the eager
  `self._drg = drg if drg is not None else self._default_drg()` with a `None`-until-first-use
  field plus `_graph()`; the three `self._drg` readers become `self._graph()`.
- No new public API; `agent_profile_repository` accessor semantics are unchanged.
- The changelog entry must say what an operator observes (fewer files read per call),
  not what the code does.

### Parallel Opportunities

T009/T010 are one module; T011 is docs-only and can be prepared in parallel.

### Dependencies

Depends on WP01 (shared census helper).

### Risks & Mitigations

- **Degrade path moves.** A `DRGLoadError` that used to be swallowed in `__init__` must
  still be swallowed at first use, not raised at the call site. Pinned by T010.
- **Hidden eager reader.** Any code reading `repo._drg` directly would now see `None`;
  T009 keeps `_drg` private and T010 greps for external readers (none today).

---

## Dependency & Execution Summary

```
WP01 ──> WP02
```

Both WPs are `code_change`; WP02 carries the docs/changelog edit in the same diff (one
changelog entry, no separate planning WP).

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP02 |
| FR-005 | WP01, WP02 |
| FR-006 | WP01 |
| FR-007 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP02 |
| NFR-003 | WP01 |
| NFR-004 | WP01, WP02 |
| C-001 | WP01, WP02 |
| C-002 | WP01, WP02 |
| C-003 | WP01 |
| C-004 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP02 |
| SC-003 | WP01 |
| SC-004 | WP02 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Failing render-ceiling census guard | WP01 | P0 | No |
| T002 | Record the red baseline numbers | WP01 | P0 | No |
| T003 | Validated `domains` scope on the loader | WP01 | P0 | No |
| T004 | Loader scope contract tests | WP01 | P0 | No |
| T005 | Declare scope at the two call sites | WP01 | P0 | No |
| T006 | Parity + scope-equals-reads pinning | WP01 | P0 | No |
| T007 | Failing board census guard (👤 parity) | WP02 | P1 | No |
| T008 | Record the 13-graph-fragment baseline | WP02 | P1 | No |
| T009 | Lazy lineage graph accessor | WP02 | P1 | No |
| T010 | Lazy-path tests incl. degrade contract | WP02 | P1 | No |
| T011 | Changelog + trace measurement | WP02 | P1 | Yes |
