---
work_package_id: WP05
title: Requirement-kinds loader seam (#5956)
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- FR-011
- SC-004
- FR-002
planning_base_branch: kitty/org-pack-chain-authority-stack
merge_target_branch: kitty/org-pack-chain-authority-stack
branch_strategy: Planning artifacts for this mission were generated on kitty/org-pack-chain-authority-stack. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/org-pack-chain-authority-stack unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-authority-01M4JXF5
base_commit: b73fea91f9c7003995364f8bb61df3e23ed2487d
created_at: '2026-10-10T14:29:35.226093+00:00'
subtasks:
- T026
- T027
- T028
- T029
- T030
- T031
- T036
phase: Phase 2 - Migration
history:
- at: '2026-10-10T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/missions/requirement_kinds.py
create_intent:
- src/charter/offering/missions/requirement_kinds.py
- src/charter/activation/org_requirement_kinds.py
- tests/charter/activation/test_load_requirement_kinds.py
- tests/charter_offering/missions/test_requirement_kinds_model.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/missions/requirement_kinds.py
- src/charter/activation/org_requirement_kinds.py
- src/charter/activation/manifest_loader.py
- tests/charter/activation/test_load_requirement_kinds.py
- tests/charter_offering/missions/test_requirement_kinds_model.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Requirement-kinds loader seam (#5956)

## ⚡ Do This First: Load Agent Profile

Use `/spk-charter-profile-load` to load the frontmatter profile first.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Build the **loader seam** #5956 will consume — a model plus a tier-walking loader for `requirement-kinds.yaml` that uses the WP01 chain authority. This is the loader ONLY: no gate handlers, no glossary, no grammar integration (C-003).

Done when:
- `RequirementKind` and `RequirementKindDeclaration` are frozen Pydantic models with `extra="forbid"`, mirroring `ExpectedArtifactSpec`/`ExpectedArtifactManifest`.
- `load_requirement_kinds(mission_type, repo_root)` resolves `requirement-kinds.yaml` through built-in → org (full chain, last-matching-file-wins, via the **strict** authority) → project tier (`.kittify/doctrine/missions/<type>/requirement-kinds.yaml`, **project wins**), whole-file override.
- A present-but-invalid file refuses (schema/unparseable → a `ManifestSchemaError`-shaped error); a declared-but-missing pack refuses (strict chain). Absence at every tier returns the built-in default kind set (code constant), never a refusal.
- ruff/mypy clean; complexity ≤15; focused tests for every branch.

## Context & Constraints

Spec: FR-009, FR-010, FR-011, SC-004. #5956 design is in the issue body (operator rulings D1-D5; whole-file override D2). Depends on **WP01** (`resolve_pack_chain`).

Mirror precedent (verified file:line):
- `manifest_loader.load_manifest` (:193): org via `_resolve_existing_org_roots` (:171) → cache key `(mission_type, tuple(roots))` (:254) → `resolve_org_expected_artifacts(org_roots, type)` (org wins first) → `_validate_and_cache_org_manifest` (:291) → `model_validate` → `ManifestSchemaError` (:82, NOT a `ValidationError` subclass; chains via `from`). Else built-in.
- `org_expected_artifacts.resolve_org_expected_artifacts` (:53): iterate roots, `<root>/missions/<type>/expected-artifacts.yaml`, **last matching file wins** (:86-92); `_read_yaml_mapping` (:95) returns `None` only for genuine absence; present-but-unparseable/non-mapping → `MalformedManifestError` (fail-closed).
- `extra="forbid"` precedent: `expected_artifact_manifest.py:32/35/57/60`.

TWO deliberate divergences from `load_manifest` (research.md Decision 6 — document them inline so a later reader does not "fix" them back):
- **Divergence A**: `load_manifest` has NO project tier. This loader ADDS `.kittify/doctrine/missions/<type>/requirement-kinds.yaml`, and **project wins** over org/built-in.
- **Divergence B**: `load_manifest` uses the lenient `resolve_existing_org_roots`. This loader resolves its org chain through `resolve_pack_chain(repo_root, strict=True)` so a declared-but-missing pack refuses (FR-007/FR-011).

File shape (`requirement-kinds.yaml`): see `data-model.md`. Default kind set = a code constant derived from today's `FR|NFR|SC|C` set (`grammar.py:76` `_KIND_ALT`), returned when no file exists at any tier.

## Subtasks

### T026 — Models
`src/charter/offering/missions/requirement_kinds.py`: `RequirementKind` (`prefix`, `label`, `glossary_term`, `must_map_to_wp`) and `RequirementKindDeclaration` (`schema_version`, `mission_type`, `kinds: list[RequirementKind]` non-empty), both frozen, `extra="forbid"`.

### T027 — Org resolver sibling
`src/charter/activation/org_requirement_kinds.py`: `resolve_org_requirement_kinds(chain, mission_type)` mirroring `resolve_org_expected_artifacts` — iterate the chain, `<root>/missions/<type>/requirement-kinds.yaml`, last-matching-file wins, whole-file, `MalformedManifestError` on present-but-invalid. (New file to avoid touching `org_expected_artifacts.py`.)

### T028 — Loader tier walk
`load_requirement_kinds(mission_type, repo_root)` in `manifest_loader.py`, beside `load_manifest`: own module-level cache keyed `(mission_type, tuple(str(root) for root in chain))`. Order: project (wins) → org (strict chain, last-wins) → built-in default constant. Validate via `model_validate`; a schema failure raises a `ManifestSchemaError`-shaped error (reuse the shape or add `RequirementKindsSchemaError` with the same `from exc` chaining).

### T029 — Project tier [Divergence A]
Read `.kittify/doctrine/missions/<type>/requirement-kinds.yaml`; when present it wins over org and built-in (whole file). Document the divergence from `load_manifest` inline.

### T030 — Fail-closed [Divergence B] + default
Resolve the org chain via `resolve_pack_chain(repo_root, strict=True)` so a declared-but-missing pack refuses. A present-but-invalid file at any tier refuses. Absence everywhere → the built-in default kind-set constant (no refusal).

### T031 — Tests
`tests/charter_offering/missions/test_requirement_kinds_model.py`: model accepts a valid declaration, rejects an unknown field (`extra="forbid"`). `tests/charter/activation/test_load_requirement_kinds.py`: pack-2 file overrides pack-1 (field-by-field distinct, not vacuous equality); project file overrides both; a one-field-corrupted file refuses (same-fixture positive: the valid sibling loads); a declared-but-missing pack refuses; absence → default constant. ruff/mypy clean.

### T036 — Migrate `load_manifest`'s existing chain call (gate scope)
`manifest_loader.py` is in the gate's charter-surface scope, and its existing `load_manifest` path resolves the org chain via `_resolve_existing_org_roots` (:171 → `resolve_existing_org_roots`, :190). Re-point that helper onto `resolve_pack_chain(repo_root, strict=False)` (behaviour byte-identical — `load_manifest`'s own fail-closed is about the *file*, not the pack, so keep it **lenient**; do NOT make `load_manifest` strict). This clears `manifest_loader.py` for the WP06 census. Confirm the existing `tests/charter/` manifest/expected-artifacts suites stay green unchanged.

## Test strategy
```bash
.venv/bin/python -m pytest tests/charter/activation/test_load_requirement_kinds.py tests/charter_offering/missions/test_requirement_kinds_model.py -q
```

## Branch strategy
Planning base / merge target `kitty/org-pack-chain-authority-stack`; worktree per lane from `lanes.json`. Depends on **WP01**.

## Definition of Done
- Models + org resolver + loader implemented; both divergences honoured and documented; fail-closed on invalid/missing; default-on-absence; all branch tests green; ruff/mypy clean. No gate-handler/glossary/grammar code (C-003).

## Risks & reviewer guidance
- **Scope creep into #5956 proper**: reviewer rejects any gate-handler, glossary, or grammar-integration code — loader seam only.
- **Lenient org chain**: using `resolve_existing_org_roots` instead of the strict authority fails FR-011 — reviewer checks Divergence B.
- **Field-merge override**: must be whole-file (D2) — reviewer checks a pack-2 file fully replaces pack-1, not merges.
- **Vacuous override test**: the override test must assert distinct field values, not equal objects.
