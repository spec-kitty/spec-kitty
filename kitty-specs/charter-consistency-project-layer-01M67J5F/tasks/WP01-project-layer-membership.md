---
work_package_id: WP01
title: Project-layer membership for the charter consistency check (#6749)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6749-charter-consistency-project-layer
merge_target_branch: issue-6749-charter-consistency-project-layer
branch_strategy: Planning artifacts for this mission were generated on issue-6749-charter-consistency-project-layer. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6749-charter-consistency-project-layer unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- Created by /spec-kitty.tasks 2026-10-30
agent_profile: python-pedro
authoritative_surface: src/charter/activation/consistency_check.py
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/activation/consistency_check.py
- tests/charter/test_consistency_check.py
- tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Project-layer membership for the charter consistency check (#6749)

## Objective

`charter consistency-check` currently answers "is this activated token known?" from
`_collect_all_offering_ids`, which passes only the org chain to `list_available`. After
#6433 that catalogue only decides `mission-type`, so a project-layer mission type that
`charter mission-type list` reports as `activated: true, source_layer: project` (and that
the runtime roster resolves) is reported `mission-type/<id>: Not found in doctrine`,
`coherent: false`, exit 1.

Make membership come from the layered authorities the readers already use, and make the
catalogue project-aware so no future consumer re-introduces the omission.

## Context to read first

- `kitty-specs/charter-consistency-project-layer-01M67J5F/spec.md` (FR-001..FR-007, C-001..C-004)
- `kitty-specs/charter-consistency-project-layer-01M67J5F/research.md` (decisions D-001..D-006, the repro)
- `src/charter/activation/consistency_check.py` — `_collect_all_offering_ids` (L376),
  `_is_known` (L426), `_check_unknown_references`, `run_consistency_check` (call site L1663)
- `src/charter/activation/layer_roots.py` — `resolve_layer_roots`, `resolve_pack_chain`
- `src/charter/missions.py` — the facade re-export of `resolve_layered_mission_types`
- `tests/charter_offering/test_activation_parity_guard.py` — the #6337 org-overlay test
  pair this WP mirrors for the project layer

## Subtasks

### T001 — Red-first CLI acceptance (fails before the fix)

Add to `tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py`:

- a fixture builder that writes a project-layer mission type at
  `.kittify/missions/mission_types/proj-mission.yaml`
  (`schema_version: 1`, `id: proj-mission`, `display_name: ...`, `extends: software-dev`)
  and seeds `.kittify/charter/activation.yaml` with
  `mission_type_activations: [proj-mission]` through
  `tests._factories.activation_ledger.seed_activation_ledger`;
- `test_project_layer_mission_type_is_coherent`: `charter consistency-check --json` via
  `CliRunner(charter_app, ...)` exits 0, `coherent is True`, no `unknown_references`
  entry mentions `mission-type/proj-mission`;
- the same-fixture positive control in the same test (or its sibling): the layered
  roster / `charter mission-type list --json` reports the type `activated` with
  `source_layer: project`, so the assertion proves the probe can see the artifact.

Record the RED output in the commit message (`T001 red: ...`).

### T002 — Red-first controls and the catalogue unit test

- unknown mission type (`ghost-type`) still appears in `unknown_references`, report
  incoherent (same fixture builder — same construction path);
- a malformed project-layer mission-type file (unparseable YAML) leaves the report
  incoherent **with** a `verification_errors` entry, and `run_consistency_check` does not
  raise;
- `tests/charter/test_consistency_check.py`: a project-layer directive
  (`.kittify/charter-packs/directive/proj-dir.directive.yaml`) appears in the ids
  `_collect_all_offering_ids` returns for kind `directive`, with a companion assertion
  that the run's `IdentityIndex` knows the same token (the two answers cannot drift).

Keep the existing `test_no_activation_keys_skips_doctrine_scan` invariant intact: with no
activation keys, neither the catalogue nor the roster may run. Update that test's spy
target if the function it monkeypatches changes name or signature.

### T003 — Fix: the catalogue passes the canonical project layer roots

In `_collect_all_offering_ids`, resolve the layer roots once
(`resolve_layer_roots(ctx.require_repo_root())`) and pass them alongside the existing
`org_root_chain` (the full chain stays). Keep the per-kind `ValueError` → empty-set
fallback. Correct the docstring: it explains the org chain (#6338) and now the project
layer; do not restate the org-only rationale.

### T004 — Fix: `mission-type` membership from the layered roster

`list_available`'s `mission-type` branch is flat/built-in-only
(`_scan_layout_for(None)` → `layered=False`) and the project mission types live at
`.kittify/missions/mission_types/`, not under the project pack root — so layer roots
cannot reach them. Source the `mission-type` entry of the catalogue from
`charter.missions.resolve_layered_mission_types(
    (MissionTemplateRepository.default_missions_root() / "mission_types",),
    ctx.require_pack_context(),
)`:

- read it **lazily**: only when at least one `mission_type_activations` entry exists
  (NFR-002); the implicit-all-active path must perform no roster read;
- read it **once** per run and reuse the ids (NFR-001);
- fail **closed**: a roster read error (malformed/unreadable file in any layer) appends
  one `verification_errors` entry naming the roster failure plus a suggestion, leaves the
  report incoherent, and never raises out of `run_consistency_check` (NFR-004). Do not
  fall back to a partial set.

Keep the import inside the function (lazy) so CLI startup cost is unchanged, and reach
the roster only through `charter.missions` (C-002 layer ratchet).

### T005 — Verify red→green, blast radius, lint and types

- demonstrate each new test RED before T003/T004 and GREEN after (record both outputs);
- run: `uv run pytest tests/charter/test_consistency_check.py
  tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py -q`,
  `uv run pytest tests/charter -q`, `uv run pytest tests/charter_offering -q`,
  `uv run pytest tests/charter/activation/test_compile_check_identity_6433.py -q`;
- `uv run ruff check src/charter/activation/consistency_check.py tests/charter/test_consistency_check.py tests/specify_cli/cli/commands/charter/test_charter_consistency_check.py`,
  `uv run ruff format --check` on the same files, `uv run mypy src/charter/activation/consistency_check.py`;
- confirm the diff-cover need: every changed line in
  `consistency_check.py` is exercised by an added or existing test;
- do **not** run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

### T006 — Changelog

Add one `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a
symlink): bold impact-first lead with `(#6749)`, then **Before** and **After**, under
1,200 characters. Name the project-layer mission type as the live case and say the
directive/styleguide instance was already fixed by #6433 and is now pinned.

## Safeguards

- Do **not** touch `src/charter/activation/pack_manager.py`, `layer_roots.py`,
  `identity_index.py` or the activation writer — reuse them, never fork their rules.
- Do **not** add a second membership rule (no hand-rolled `missions/mission_types` walk,
  no `MissionTypeRepository.default()` fallback, no re-scan of the project pack root for
  mission types).
- Do **not** weaken a check to make a fixture pass: an unknown token must still be
  reported, and a malformed layer must still be incoherent.
- Do **not** add `kitty-specs/` paths to this WP's `owned_files`.
- Never push `main`; the branch is `issue-6749-charter-consistency-project-layer`.

## Definition of done

- FR-001..FR-007 each have a test that fails on the pre-fix tree and passes after it
  (or, for the ratchet rows, a same-fixture positive control proving non-vacuity).
- The four suites named in T005 pass; lint/format/mypy clean on the touched files.
- The changelog entry is in place, the diff is confined to `owned_files`, and the
  commit history shows the red-first step before the fix.
