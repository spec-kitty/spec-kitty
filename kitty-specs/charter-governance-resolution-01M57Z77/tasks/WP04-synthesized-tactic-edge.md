---
work_package_id: WP04
title: Synthesized tactic suggests edge and reconcile ownership
dependencies: []
requirement_refs:
- FR-001
- FR-004
- FR-005
- C-004
subtasks:
- T017
- T018
- T019
- T020
- T021
phase: Phase 1 - Foundation
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/reconcile.py
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/synthesizer/project_drg.py
- src/charter/activation/synthesizer/reconcile.py
- src/charter/offering/drg/models.py
- src/charter/offering/drg/merge.py
- docs/architecture/doctrine-relationships.md
- tests/charter/synthesizer/test_project_drg.py
- tests/charter/synthesizer/test_synthesize_reconcile.py
- tests/charter/synthesizer/test_synthesize_conflict_routing.py
- tests/charter/synthesizer/test_synthesize_node_preservation.py
- tests/charter/synthesizer/test_validation_gate.py
- tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py
role: implementer
task_type: implement
---

# Work Package Prompt: WP04 – Synthesized tactic suggests edge and reconcile ownership

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt. Then load action doctrine: `spec-kitty charter context --action implement --mission-type software-dev --no-mark-loaded`.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission charter-governance-resolution-01M57Z77`). Address every feedback item; record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `issue-6404-charter-governance-resolution-work`
- **Merge target branch**: `issue-6404-charter-governance-resolution-work`

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement <WPID> --agent claude --mission charter-governance-resolution-01M57Z77
```

Never construct a workspace path by hand.

## Shared Rules (every WP)

- **Red first** (ADR 2026-07-17-1): write the issue-pinned failing test(s) for the WP's acceptance scenarios and commit them on their own *before* the fix commit (`test: red repro for #NNNN ...`). After the fix, keep them as focused tests (not left marked `regression`).
- **Non-vacuity**: every absence/refusal assertion is paired with a positive control on the same fixture (tactic `acceptance-criteria-non-vacuity`).
- **Quality gates** (NFR-001): `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check --force-exclude <changed files>`, `uv run --frozen mypy --strict <changed src files>`; cyclomatic complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

Synthesis links each directive to its how-we-apply tactic with `directive:<declared id> --suggests--> tactic:how-we-apply-<x>` instead of the inert `tactic --applies--> directive`; reconcile assigns each edge to the synthesized node it was derived for, so full and partial re-runs neither duplicate nor wrongly prune it; pruning a node drops every edge touching it; legacy `applies` edges from synthesized nodes are stripped on any run (#6404).

Done when:
- the emitted overlay for a selected directive holds the `suggests` edge (and no `applies` edge);
- a second full synthesize and a `--topic` partial resynthesize each leave exactly one such edge (positive control: it exists);
- `--prune` of a how-we-apply tactic removes its inbound edge (no `preserved_dangling_endpoint`);
- a fixture overlay with legacy `applies` edges has none after a run;
- plain runs do not report spurious orphan removals (edge backing artifact resolved through the owner);
- relation prose updated in lockstep (`test_relation_doc_parity.py` green).

Requirement refs: FR-001, FR-004, FR-005, C-004.

## Context & Constraints

- Plan D2. Operator decision (2026-10-18): built-in `suggests` convention, not reverse-`applies` traversal.
- Emission: `src/charter/activation/synthesizer/project_drg.py:349-375` — today `relation = REQUIRES if target.kind == "directive" else APPLIES`, edge `source=urn, target=source_urn`; built-in duplicate-triple guard :358-370. `source_urns` for how-we-apply tactics come from `interview_mapping._append_selected_directives` (:377-396) as `directive:<declared id>` (ids via `compiler.resolve_config_activated_roots` → `resolve_artifact_urn`, compiler.py:185-187, layer-aware). Slugs: `targets.py:86-88`.
- Reconcile (`src/charter/activation/synthesizer/reconcile.py`): `merge_project_overlay` :215-262 (edges grouped by `edge.source`; a directive-sourced edge is never in `updated_urns` → kept and re-appended = duplicate); `_edge_ref` :418-423 (`backing_artifact = urn_to_path.get(edge.source)` → None for built-in sources → spurious orphan refusal in `src/specify_cli/cli/commands/charter/_synthesis.py:859-878`); `_graph_delta` :430-455 (:446, :450 use `e.source`); `_edge_conflict` :480-495; `_classify_conflicts` :516; `apply_prune` :652-655 (drops only edges whose source is removable).
- Partial runs: `resynthesize_pipeline.py:364,375` (`emit_project_layer(resolved.targets, ...)` then `merge_project_overlay`); topic matching uses provenance `source_urns` (`topic_resolver.py:246-249`) — unaffected.
- Hand-authored project profiles emit `agent_profile --requires--> X` (`project_scan.py:225-248`) — ownership must stay with the profile.
- Prose: `src/charter/offering/drg/models.py:181-193` `RELATION_DESCRIPTIONS[Relation.APPLIES]` names `project_drg` as emitter; `docs/architecture/doctrine-relationships.md:163` must match verbatim (`tests/charter_offering/test_relation_doc_parity.py`); `src/charter/offering/drg/merge.py:92-98` comment. `tests/architectural/test_no_authored_applies_edge.py` scans shipped packs only — must stay green (C-004).
- Fixtures: `tests/charter/synthesizer/conftest.py` (`minimal_*_snapshot`, `fixture_adapter`, `tests/charter/fixtures/synthesizer/tactic/how-we-apply-directive-00{3,10}`).

## Subtasks & Detailed Guidance

### Subtask T017 – Red tests

- `tests/charter/synthesizer/test_project_drg.py:245-260`: flip the expected triple to `("directive:DIRECTIVE_003", "tactic:how-we-apply-003", SUGGESTS)` (use the real slug the fixture produces) and assert no `APPLIES` edge exists.
- `tests/charter/synthesizer/test_synthesize_reconcile.py`: (a) two consecutive synthesize runs → exactly one suggests edge; (b) legacy overlay with an `applies` edge from a synthesized tactic (reuse `_inject_legacy_overlay_content` :115-140) → no `applies` edge after the run; (c) `apply_prune` with an inbound `directive → tactic:prune-me` edge → edge removed (extend the unit test at :586-635); (d) `_edge_ref` for a directive-sourced edge has a non-None `backing_artifact`.
- Partial run: a `--topic directive:DIRECTIVE_003` resynthesis keeps one edge (extend the resynthesize tests or `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py`).
Commit red: `test: red repro for #6404 synthesized tactic edge`.

### Subtask T018 – Emission

- Tactic targets: `DRGEdge(source=source_urn, target=urn, relation=Relation.SUGGESTS, reason=...)`; directive targets keep `(urn, source_urn, REQUIRES)`; any other kind with source_urns keeps REQUIRES (no producer today). Oriented triple in the built-in duplicate check. Remove `APPLIES` from this module; fix the comment that says "derived_from".

### Subtask T019 – `edge_owner` and reconcile call sites

- Add `edge_owner(edge, overlay_urns) -> str | None`: synthesis shape (`relation is SUGGESTS`, source `directive:*`, target a `tactic:*` in `overlay_urns`) → target; else source if in `overlay_urns`; else target if in `overlay_urns`; else `None`.
- Use it in `merge_project_overlay` (group, preserve test, dedup/insert; `all_urns = existing ∪ updated`), `_graph_delta`, `_edge_ref` (thread `overlay_urns`), `_edge_conflict` (provenance and backing), `_classify_conflicts` (`overlay_urns = {n.urn for n in merged_overlay.nodes}`).
- `apply_prune`: keep an edge only if neither endpoint is removable.

### Subtask T020 – Legacy `applies` strip

- In `merge_project_overlay` (and the same filter in `_graph_delta` so stripped edges are not reported as retained/removable): drop existing edges with `relation is APPLIES and source in existing_node_urns`. Applies to full and partial runs.

### Subtask T021 – Prose in lockstep

- Rewrite `RELATION_DESCRIPTIONS[APPLIES]` (no synthesis emitter; still traversed by nothing), the same text in `docs/architecture/doctrine-relationships.md:163`, and the `merge.py:92-98` comment. Update the `test_no_authored_applies_edge.py` docstring only if it names project_drg (leave the gate logic).
- Update every remaining legacy-shape test fixture: `test_synthesize_conflict_routing.py` (:175-196, :273-280, :349-387, :513-520, :564), `test_synthesize_node_preservation.py:119-135`, `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py:183,241`, `test_validation_gate.py:194`.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/ tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py tests/charter_offering/test_relation_doc_parity.py tests/architectural/test_no_authored_applies_edge.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ -q -p no:randomly
uv run --frozen mypy --strict src/charter/activation/synthesizer/project_drg.py src/charter/activation/synthesizer/reconcile.py src/charter/offering/drg/models.py src/charter/offering/drg/merge.py
```

## Risks & Mitigations

- Many reconcile tests encode the legacy shape → update fixtures, never weaken assertions.
- Wrong owner for profile edges → explicit test that a project `agent_profile --requires--> tactic:how-we-apply-*` edge is owned by the profile.

## Review Guidance

- No `Relation.APPLIES` emission left in `src/charter/activation/synthesizer/`.
- Owner helper is the single authority in reconcile (`git grep "edge.source" src/charter/activation/synthesizer/reconcile.py` shows no ownership decisions bypassing it).
