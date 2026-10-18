---
work_package_id: WP05
title: Synthesized tactic delivery through its directive and activation append
dependencies:
- WP03
- WP04
requirement_refs:
- FR-002
- FR-003
- C-001
planning_base_branch: issue-6404-charter-governance-resolution-work
merge_target_branch: issue-6404-charter-governance-resolution-work
branch_strategy: Planning artifacts for this mission were generated on issue-6404-charter-governance-resolution-work. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6404-charter-governance-resolution-work unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 3 - Delivery and activation
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/reach_only.py
create_intent:
- src/charter/activation/synthesizer/reach_only.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- src/charter/activation/compiler.py
- src/specify_cli/cli/commands/charter/synthesize.py
- src/specify_cli/cli/commands/charter/resynthesize.py
- tests/charter/synthesizer/test_reach_only_delivery.py
- tests/charter/synthesizer/test_synthesize_activation_append.py
- tests/charter/test_action_bundle_delivery.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Synthesized tactic delivery through its directive and activation append

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
- **Tests**: run the WP's own test files plus the owning subsystem directory (`tests/charter/` and, for `src/charter/offering/**`, `tests/charter_offering/`). Subsystem sweeps are large (`tests/charter/` ≈ 3,900 tests): always run them with `-n auto --dist loadfile` (pytest-xdist is installed), never `--dist load`. Do not run `make test-full` or the whole `tests/architectural/` directory; run only the named gate files.
- **Terminology**: "Mission", never the retired term. Run `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` when touching prose or `src/charter/offering/`.
- **Commits**: conventional types (`fix`, `feat`, `test`, `refactor`, `docs`); end every commit message with the session attribution lines given to you.
- Diagnostic wording for unknown selected ids is fixed Mission-wide (WP02 defines the constant `UNKNOWN_SELECTION_DIAGNOSTIC` in `resolver.py`): `"Unknown selected {kind} '{token}' dropped: not found in built-in, org packs (charter_packs.org.packs) or .kittify/charter-packs/; see 'spec-kitty charter list'."`
- Stay inside `owned_files`; a small out-of-map edit is acceptable only with a one-line rationale in the commit message and `add-history` note.

## Objectives & Success Criteria

Synthesized how-we-apply tactics reach action context **only** through their directive's `suggests` edge, and `charter synthesize` appends the tactic ids it creates to an explicit `activated_tactics` list (absent key left absent) (#6404, operator decision 2026-10-18).

Done when, on a synthesized fixture with explicit `activated_directives` (including `DIRECTIVE_024`) and explicit `activated_tactics`:
- after `charter synthesize`, `activated_tactics` contains `how-we-apply-directive-024` (and the bundle hash in the synthesis manifest is restamped);
- `implement` action context with `--mission-type software-dev` delivers `how-we-apply-directive-024`; with the edge removed from the overlay it is not delivered;
- after deactivating `DIRECTIVE_024`, the tactic is not delivered, while a non-synthesized activated tactic still is;
- with no `activated_tactics` key, synthesis writes none, and synthesized edge-carrying tactics are still not roots (delivered only via edges);
- edgeless synthesized tactics (`testing-philosophy-tactic`, `review-policy-tactic`) and hand-authored project tactics remain roots;
- NFR-004 snapshot unchanged (it has no synthesized artifacts).

Requirement refs: FR-002, FR-003, C-001.

## Context & Constraints

- Depends on WP03 (bundle carries identity; owns `action_governance_bundle.py`) and WP04 (edge shape).
- Root seeding (`src/charter/activation/action_governance_bundle.py`): absent key → `selected_tactics = _catalog_default_or_activated(None, _graph_and_catalog_default_ids(merged, TACTIC, ...))` :347-351 (helper :91-106) seeds every graph tactic; explicit key seeds the listed ids; org-required union :377; `roots` tuple :412-417. Seeds are closure roots in `delivery_table.py:280-288`.
- Provenance is **not** tagged on the default merge path (`_drg_helpers.py:277` `merge_layers`), and the set must be computed **before** `filter_graph_by_activation` (else a deactivated directive's edge disappears and the tactic looks like a root).
- Reference seeds: `src/charter/activation/compiler.py` ~:1768 `start_urns |= direct_root_urns` — apply the same subtraction.
- Activation append hook: `src/charter/activation/synthesizer/orchestrator.py` `synthesize`, after `_apply_post_condition` (~:327-332), preserve and prune modes only (dry-run returns at ~:303). APIs: `pack_manager.resolve_activation_write_target(repo_root)` (:577), `activation_engine.promote_activations(...)` (:600, append-only, dedupes), `bundle_restamp.restamp_bundle_hash(repo_root)` (pair as in `pack_manager.py:770-771`). Ids: this run's results `[prov.artifact_slug for _, prov in results if prov.artifact_kind == "tactic"]` (tactic stem == declared id == slug).
- `action_governance_bundle.py` (owned by WP03) gets the subtraction call; WP05 depends on WP03.
- Test the topic path and the refused path (orphan refusal → `activated_tactics` unchanged).

## Subtasks & Detailed Guidance

### Subtask T022 – Red tests

- New `tests/charter/synthesizer/test_reach_only_delivery.py`:
  - unit: `reach_only_tactic_ids(repo_root)` returns the overlay tactic ids that are targets of an overlay `directive:* --suggests-->` edge; returns empty on a missing/invalid overlay; excludes an edgeless synthesized tactic and a hand-authored project tactic.
  - delivery (pattern: `tests/charter/test_action_governance_bundle_activation.py:128-250`, patching `charter.activation._drg_helpers.load_validated_graph` and writing the tactic YAML under the project pack root since `filter_graph_by_activation` resolves explicit stems from disk): directive active + edge → delivered; edge removed → not delivered; directive deactivated → not delivered; explicit list containing the tactic id does not make it a root; absent key → not a root.
- New `tests/charter/synthesizer/test_synthesize_activation_append.py`: real synthesize to `tmp_path` (fixtures in `tests/charter/synthesizer/conftest.py`) with `.kittify/config.yaml` `activated_tactics: [some-tactic]` → ids appended, existing entry kept, manifest bundle hash restamped (manifest verification passes); paired absent-key test → key stays absent; dry-run writes nothing.
- `tests/charter/test_action_bundle_delivery.py`: pure `_classify_artifact_urns` case where a reach-only tactic is reachable from a seeded directive.
Commit red: `test: red repro for #6404 synthesized tactic delivery`.

### Subtask T023 – `reach_only_tactic_ids`

- New module `src/charter/activation/synthesizer/reach_only.py`: load the project overlay (`project_pack_root(repo_root)`, `has_graph_files` / `load_graph_or_dir`), degrade to `frozenset()` on `DRGLoadError` (match `project_degrade`), return bare tactic ids targeted by overlay `directive:* --suggests-->` edges.

### Subtask T024 – Subtract from seeds

- `action_governance_bundle`: compute the set before activation filtering; after the org-required union, `selected_tactics -= reach_only` (both absent-key and explicit-key paths). `compiler.py` reference seeds: same subtraction.

### Subtask T025 – Activation append in synthesize (full and `--topic` paths)

- Placement: the CLI orphan refusal runs **after** `orchestrator.synthesize()` returns (`src/specify_cli/cli/commands/charter/synthesize.py:510-525`), and `resynthesize` (`--topic`, `orchestrator.py:342-383` / `resynthesize_pipeline`) bypasses `synthesize()`. So add a helper `append_synthesized_tactic_activations(repo_root, tactic_slugs) -> list[str]` (warnings) in `synthesizer/reach_only.py`, and call it from the CLI after the refusal check in `synthesize.py` and after a successful run in `resynthesize.py` (and from `activate --resynthesize` if it does not go through those commands). Never append on dry-run or refused runs. In the helper: collect this run's tactic slugs; `target_path, data, save = resolve_activation_write_target(repo_root)`; if `data.get("activated_tactics") is None`: return; else `promote_activations({"activated_tactics": ids}, config_path=target_path, config_data=data, save=save, effective_sets={})`; then `restamp_bundle_hash(repo_root)`. Surface promotion warnings in the synthesize result/output if the existing result type carries warnings.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/test_reach_only_delivery.py tests/charter/synthesizer/test_synthesize_activation_append.py tests/charter/test_action_bundle_delivery.py tests/charter/test_action_governance_bundle_activation.py tests/charter/test_default_in_force_snapshot.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ tests/specify_cli/cli/commands/charter/ -q -n auto --dist loadfile
uv run --frozen mypy --strict src/charter/activation/synthesizer/reach_only.py src/charter/activation/synthesizer/orchestrator.py src/charter/activation/compiler.py
```

## Risks & Mitigations

- Manifest staleness after append → restamp; test verifies.
- Non-vacuity: the edge-removed case proves the edge is the only route.

## Review Guidance

- C-001: absent `activated_tactics` never written by synthesis.
- Hand-authored and edgeless synthesized tactics still roots.
