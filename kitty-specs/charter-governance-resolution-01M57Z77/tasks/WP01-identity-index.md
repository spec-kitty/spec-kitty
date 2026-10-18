---
work_package_id: WP01
title: Identity index and default in-force snapshot
dependencies: []
requirement_refs:
- FR-006
- NFR-003
- NFR-004
- C-002
- C-007
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
agent: claude
history:
- at: '2026-10-18T17:40:00Z'
  actor: claude-code/opus
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/identity_index.py
create_intent:
- src/charter/activation/identity_index.py
- tests/charter/activation/test_identity_index.py
- tests/charter/test_default_in_force_snapshot.py
- tests/charter/fixtures/default_in_force_snapshot.json
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/identity_index.py
- src/charter/activation/kind_vocabulary.py
- src/charter/activation/api.py
- tests/charter/activation/test_identity_index.py
- tests/charter/test_kind_vocabulary.py
- tests/architectural/test_charter_activation_api_reexport.py
- tests/charter/test_default_in_force_snapshot.py
- tests/charter/fixtures/default_in_force_snapshot.json
role: implementer
task_type: implement
---

# Work Package Prompt: WP01 – Identity index and default in-force snapshot

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

Build the per-invocation, layer-aware **identity index** that maps an activation token or selection (file stem or declared `id:`) to the artifact's declared id for every activatable kind, and back to its stem. Capture the NFR-004 default-in-force golden snapshot on the unchanged code first.

Done when:
- `IdentityIndex` exists in `src/charter/activation/identity_index.py`, is exported from `charter.activation.api`, and is unit-tested for every activatable kind with stem = id, stem ≠ id (org and project layers), declared-id tokens, precedence and unknown tokens.
- `resolve_artifact_urn` accepts an exact declared id for **every** kind (stem match still wins).
- One index scans each (kind, layer set) at most once (NFR-003), proven by a counting probe.
- A golden snapshot of the default in-force sets (NFR-004) is committed **before** any behaviour change in this Mission.

Requirement refs: FR-006, NFR-003, NFR-004, C-002, C-007.

## Context & Constraints

- Spec: `kitty-specs/charter-governance-resolution-01M57Z77/spec.md` (US2, FR-006, NFR-003, NFR-004). Plan D1.
- Existing machinery (`src/charter/activation/kind_vocabulary.py`): `__all__` :76-88; `_scan_roots` :159 (order: project layer `layer_roots["project"]` :293 → org roots reverse declaration order :234 → built-in `built_in_dir(kind)` :218; first match wins); `ResolutionPass` :320 (scans keyed by `(kind, offering_root, tuple(org_roots), sorted(layer_roots))` :340 — not canonical); `resolve_artifact_urn` :421 with the **directive-only** declared-id fallback :466-480 (round-trip via `resolve_config_id`); `resolve_config_id` :574 (directives: `_directive_ids_by_stem` :516, `_directive_stem_represents` :536, `UnrepresentableDirectiveIdError` :512); `resolve_selected_id_to_stem` :674 (directives id-first; other kinds stem-first).
- Roots today: `layer_roots.resolve_layer_roots(repo_root)` (layer_roots.py:24), `resolve_pack_chain(repo_root, strict=)` (:51), `PackContext.from_config(repo_root).org_roots` (pack_context.py:188/205; unfiltered).
- **Import rule**: `identity_index.py` may import `charter.offering.*`, `kind_vocabulary`, `layer_roots`, and `pack_context` (TYPE_CHECKING only). It must **not** import `resolver` or `profile_resolution` (cycle). Use `charter.offering.drg.migration.id_normalizer.normalize_directive_id` for the directive fallback.
- C-007: the index changes how ids are spelled, not which artifacts any base contains.

## Subtasks & Detailed Guidance

### Subtask T001 – Capture the NFR-004 golden snapshot (before any change)

- **Purpose**: freeze today's default in-force sets so later WPs can prove they did not change them.
- **Steps**:
  1. Create `tests/charter/test_default_in_force_snapshot.py`. Reuse the `_delivered()` approach from `tests/charter_offering/test_owner_delivery.py:88-105` (write a bare project: no `.kittify/config.yaml` activation keys, no org packs, no synthesized artifacts; call `_load_action_governance_bundle(..., mission_type="software-dev")` and collect delivered directive/tactic/styleguide ids per action).
  2. Parametrise over every action directory under `packs/built-in/missions/mission-steps/software-dev/`.
  3. Also snapshot `asdict(resolve_project_governance(root))` (directives, paradigms, tools, template set, diagnostics).
  4. Store the golden as `tests/charter/fixtures/default_in_force_snapshot.json` (sorted lists, stable key order). Provide a helper `UPDATE_SNAPSHOT=1` env path that rewrites the golden; default mode compares.
  5. Generate the golden on the unmodified code and commit it alone: `test: capture default in-force snapshot (NFR-004)`.
- **Files**: `tests/charter/test_default_in_force_snapshot.py` (new), `tests/charter/fixtures/default_in_force_snapshot.json` (new).
- **Notes**: the `catalog_fallback` diagnostic text is part of `resolve_project_governance` output — keep it in the snapshot; later WPs must not change it for this fixture.

### Subtask T002 – Red tests for the identity index

- **Purpose**: pin the behaviour before writing the module.
- **Steps**: create `tests/charter/activation/test_identity_index.py` with fixtures built in `tmp_path`:
  - an org pack (registered through `.kittify/config.yaml` `charter_packs.org.packs`, follow the shape used in `tests/charter/activation/test_org_charter_pack_context.py` / `tests/specify_cli/cli/commands/test_charter_org_directive_identity.py`) containing `directives/qa-003-no-fake-green.directive.yaml` (`id: QA_003`), `tactics/qa-tactic-seven.tactic.yaml` (`id: qa-seven`), a paradigm and a styleguide with stem ≠ id;
  - a project-layer artifact under `.kittify/charter-packs/<kind>/` with stem ≠ id.
  Assert:
  - `declared_id(DIRECTIVE, "qa-003-no-fake-green") == "QA_003"`, `declared_id(DIRECTIVE, "QA_003") == "QA_003"`;
  - `declared_id(TACTIC, "qa-tactic-seven") == "qa-seven"` and `declared_id(TACTIC, "qa-seven") == "qa-seven"`; same for paradigm/styleguide/toolguide/procedure/agent_profile (uses `profile-id`);
  - built-in: `declared_id(DIRECTIVE, "001-architectural-integrity-standard") == "DIRECTIVE_001"`;
  - `stem(DIRECTIVE, "QA_003") == "qa-003-no-fake-green"`;
  - precedence: same declared id in project and org → project wins; `source_layer` reports it;
  - collision: token equal to A's stem and B's declared id → A (stem wins) for `declared_id`; `selection_id` for directives prefers the declared id (mirrors `resolve_selected_id_to_stem`);
  - unknown: `declared_id(...) is None`, `knows(...) is False`; `resolve_many` returns `(ids, unknown)`;
  - directive normaliser fallback: `declared_id(DIRECTIVE, "DIRECTIVE_1")`/`"024"` resolve only when the normalised id is known;
  - `anti_pattern` tokens pass through unchanged.
  Add a test in `tests/charter/test_kind_vocabulary.py`: `resolve_artifact_urn(TACTIC, "qa-seven", ...)` returns `tactic:qa-seven` (fails today; stem-only for non-directives).
  Commit red: `test: red repro for #6406 identity index`.

### Subtask T003 – Implement `IdentityIndex`

- **Steps**:
  1. `@dataclass(frozen=True) class IdentityEntry: kind: ArtifactKind; stem: str; declared_id: str; layer: str` (`"project" | "org" | "built-in"`).
  2. `IdentityIndex.build(repo_root, *, org_roots=None)`: canonicalise roots once — org roots that exist (declaration order, from `resolve_pack_chain(repo_root, strict=False)` when not given), `{"project": project_pack_root(repo_root)}` only when it is a dir, offering root = built-in; one private `ResolutionPass`. `from_pack_context(ctx)` uses `ctx.org_roots` filtered to existing dirs.
  3. Lazy per-kind build: walk the same roots in `_scan_roots` order (reuse kind_vocabulary's path iteration and `_read_id`; expose a small internal helper there if needed rather than duplicating), producing ordered entries; derive `by_stem` and `by_id` (first match), and `ids_by_stem` for directive ambiguity.
  4. Methods: `declared_id`, `selection_id`, `stem`, `knows`, `source_layer`, `resolve_many` as in plan D1. Keep each function ≤ 15 complexity.
  5. Export `IdentityIndex` (and `IdentityEntry`) from `charter/activation/api.py` `__all__`; update `tests/architectural/test_charter_activation_api_reexport.py` accordingly.
- **Files**: `src/charter/activation/identity_index.py` (new), `src/charter/activation/api.py`, `tests/architectural/test_charter_activation_api_reexport.py`.

### Subtask T004 – Declared-id fallback for every kind in `resolve_artifact_urn`

- **Steps**: generalise the fallback at `kind_vocabulary.py:466-480` so any kind accepts an exact declared id after the stem scan misses (directives keep their round-trip/ambiguity rule). Update the module comment ("other kinds remain stem-only"). Keep `UnknownArtifactIdError` for genuine misses.
- **Files**: `src/charter/activation/kind_vocabulary.py`, `tests/charter/test_kind_vocabulary.py`.

### Subtask T005 – Scan-count probe (NFR-003)

- **Steps**: in `test_identity_index.py`, wrap the per-root scan function (pattern: `tests/charter/test_directive_resolution_memoization.py:34-48` `scan_calls`) and assert that 50 lookups across stems and ids for one kind trigger exactly one scan per root for that kind; a second kind adds one scan per root.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/activation/test_identity_index.py tests/charter/test_kind_vocabulary.py tests/charter/test_default_in_force_snapshot.py tests/architectural/test_charter_activation_api_reexport.py -q
uv run --frozen pytest tests/charter/ -q -x -p no:randomly
uv run --frozen mypy --strict src/charter/activation/identity_index.py src/charter/activation/kind_vocabulary.py src/charter/activation/api.py
```

## Risks & Mitigations

- Cycle risk → import rule above; verify with `python -c "import charter.activation.identity_index"`.
- Generalising the declared-id fallback could change resolution where a stem of one artifact equals the declared id of another → stem match stays first; tested.
- Snapshot brittleness → sorted, deterministic JSON; regenerate only via the explicit env flag.

## Review Guidance

- Snapshot commit precedes every behaviour change and was generated on unmodified code.
- No import of `resolver`/`profile_resolution` from `identity_index.py`.
- Every activatable kind covered in tests (parametrise over `ArtifactKind` members with `activatable == True`, skipping file-less kinds explicitly).
