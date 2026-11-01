---
work_package_id: WP02
title: Load profile lineage on first use, not at construction
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- FR-007
- NFR-002
- NFR-004
- C-001
- C-002
- SC-002
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Read-only surface cost
history:
- at: '2026-10-31T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/agent_profiles/
create_intent:
- tests/charter/test_charter_render_scope_board_6462.py
execution_mode: code_change
model: glm-5.3
owned_files:
- src/charter/offering/agent_profiles/repository.py
- tests/charter/test_charter_render_scope_board_6462.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Load profile lineage on first use, not at construction

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`), address
every item, and record progress with
`spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

`AgentProfileRepository` builds its lineage graph in `__init__`, so every reader of the
profile *map* pays 13 shipped DRG fragment parses. The read-only `agent tasks status`
board pays that to answer one structural boolean (`profile.sentinel`) for the 👤 marker,
and `agent profile list` pays it twice (101 documents total).

Done when:

- A profile-map read (`get`, `list_all`, provenance, `sentinel`, `skipped_profiles`)
  parses **zero** `*.graph.yaml` documents.
- A lineage read (`get_ancestors`, `get_children`, `get_descendants`, profile-channel
  reachability) builds the graph exactly once, with unchanged results.
- An unloadable DRG still degrades to an empty graph — at first lineage use instead of
  at construction — and never raises from a profile-map read.
- An explicit `drg=` argument is used verbatim and never triggers a lazy build.
- The board census guard is red on `main` (13 graph fragments) and green after
  (≤ 70 catalog documents, 0 graph fragments), with the 👤 marker still rendered for a
  `human-in-charge` work package.
- Changelog `[Unreleased]` entry landed.

## Context & Constraints

Read first: `.../spec.md` (FR-004, FR-005, FR-007; NFR-002; C-002, C-003),
`.../research.md` (D-4, D-5), `.../data-model.md` ("AgentProfileRepository"),
`.../contracts/render-scope-census.md` (C-2).

Measured baseline (`main` @ `dfe9efb0e8`, isolated `HOME`): `agent tasks status` parses
107 shipped documents — 30 mission-step contracts, 26 agent profiles, **13 DRG
fragments**, 12 WP frontmatter reads, 4 mission types — and builds one
`ActiveCharterService` plus one `AgentProfileRepository`.

Constraints:

- **Do not** narrow the profile catalog, drop the org/project layer, or route the board
  around `ActiveCharterService`. That accessor is pinned by
  charter-sole-door-bypass-closure-01KZ3WAA FR-001 and a second profile reader is
  forbidden (spec C-002, research D-5). Only the *lineage graph* timing changes here.
- `self._drg` is read in exactly three places: `_lineage_parent` (line ~700) and the two
  reachability helpers (~934, ~957). Keep it private; add one `_graph()` accessor.
- Warning behaviour and the `DRGLoadError` → empty-graph degradation are unchanged
  (spec C-003).

## Branch Strategy

- **Planning base branch**: `kitty/mission-issue-6462-charter-render-scope-per-call-01M69065`
- **Merge target branch**: `main` (via PR from `issue-6462-charter-render-scope-per-call`)
- Execution worktrees come from `lanes.json`; claim with
  `spec-kitty agent action implement WP02 --agent <name> --mission issue-6462-charter-render-scope-per-call-01M69065`.

## Subtask Guidance

**T007 / T008 — guard first.** `tests/charter/test_charter_render_scope_board_6462.py`
reuses `tests/charter/_render_census.py` (WP01). Assert that rendering the `agent tasks
status` board for a mission whose WPs carry `agent_profile` parses zero `*.graph.yaml`
documents and at most 70 catalog documents, and that a `human-in-charge` WP still gets
the `👤` marker. Run it on unmodified `src/` and record 13 graph fragments in the trace.

**T009 — lazy graph.** In `src/charter/offering/agent_profiles/repository.py`:

- Store the explicit `drg` argument as-is; when it is `None`, leave the field unset
  (`None`) and build on first use.
- `def _graph(self) -> DRGGraph:` returns the stored graph, else builds
  `self._default_drg()` once and caches it. `_default_drg` already catches `DRGLoadError`
  and returns the empty graph — keep that exact degradation, just later.
- Replace the three `self._drg` reads with `self._graph()`.
- Do not change `_load`, `_load_layer`, `_parse_profile_from_file`, merge/override
  semantics, or any public signature.

**T010 — tests for the lazy path.** Profile-map reads build no graph (spy on
`load_built_in_graph` / `_default_drg`); each lineage accessor builds it once; two
successive lineage calls reuse the cached graph; explicit `drg=` bypasses; a
`DRGLoadError` on first lineage use still yields empty lineage results rather than
raising; `list_all()` before and after a lineage call returns the same profiles.

**T011 — changelog and trace.** Add one `[Unreleased]` entry to
`docs/changelog/CHANGELOG.md`: bold, impact-first lead with `(#6462)`, then before/after,
under 1,200 characters. State the operator-visible effect (fewer doctrine files read per
CLI call, one parse set that matches what the command renders) and the measured numbers.
Append the measurement to the mission traces with
`spec-kitty agent tracer-append --mission <mission> --actor <name> --category approach --entry "..."`.

## Definition of Done

- Board census guard and the new lazy-path tests pass; both were red/did-not-exist
  before this WP for the documented reason.
- `uv run --frozen pytest tests/charter/activation tests/charter/test_agent_profile_repository.py tests/charter/test_charter_render_scope_board_6462.py -q` green
  (adjust to the real repository-suite paths you find).
- `uv run --frozen ruff check src/charter tests/charter` and
  `uv run --frozen mypy src/charter/offering/agent_profiles/repository.py` clean.
- `spec-kitty agent tasks status --mission <any mission with a claimed WP>` shows the 👤
  marker unchanged.
- Changelog entry passes `uv run --frozen python -m scripts.docs.check_changelog_style`.

## Risks & Review Guidance

- The degrade contract is the subtle part: `DRGLoadError` must still be swallowed, just
  later. A reviewer should confirm a profile-map-only read can never raise it and a
  lineage read never raises it either.
- Confirm no eager reader of `_drg` remains anywhere in the tree
  (`git grep -n "_drg" src/`).
- Confirm the lazy build is per-repository-instance, not global (no cross-process or
  cross-repo cache: spec C-001).
