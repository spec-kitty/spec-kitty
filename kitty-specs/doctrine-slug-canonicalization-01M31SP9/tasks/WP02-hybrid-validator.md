---
work_package_id: WP02
title: Hybrid manifest-driven validator + 5-kind table
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-006
- NFR-001
- NFR-003
planning_base_branch: fix/doctrine-slug-canonicalization
merge_target_branch: fix/doctrine-slug-canonicalization
branch_strategy: Planning artifacts for this mission were generated on fix/doctrine-slug-canonicalization. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctrine-slug-canonicalization unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
history:
- at: '2026-09-21T11:10:00+00:00'
  actor: claude
  note: WP created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/bundle.py
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/bundle.py
- tests/charter/synthesizer/test_bundle_validate_extension.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Run `/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --json`) and apply it. State which you applied.

## Objective

Make `charter bundle validate` (a) recognise all five registration-writing kinds (#4833 — `agent_profile`/`procedure` no longer trip "unknown kind"), and (b) resolve *registered* artifacts through the synthesis manifest rather than re-parsing the filename (#4832 for existing repos — a registered `LOVE_THY_ENEMY.directive.yaml` with manifest slug `love-thy-enemy` validates clean, file unmodified), **while keeping the filesystem orphan sweep in BOTH directions**. Read `contracts/bundle-validate-contract.md` and `research.md` (Decision 4). Depends on WP01 (`DIRECT_WRITE_KINDS`).

## Subtasks

### T006 — Derive the 5-kind table from `DIRECT_WRITE_KINDS`
- In `src/charter/bundle.py`, replace the hand-maintained 3-entry `_KIND_SUFFIX` (L68-72) with a mapping derived from `DIRECT_WRITE_KINDS` × `ArtifactKind._PATTERNS` extensions, yielding `directive/.directive.yaml, tactic/.tactic.yaml, styleguide/.styleguide.yaml, procedure/.procedure.yaml, agent_profile/.agent.yaml`. `_ALL_ARTIFACT_PATTERNS` follows. Import the constant from `artifact_kinds` (existing sanctioned direction; watch for import cycles — `artifact_kinds` is a leaf, so importing it into `bundle.py` is safe).
- Confirm `stem.split("-",1)` kind extraction (L438-448) still recovers `agent_profile`/`procedure` (no leading-dash ambiguity — verified in design).
- **Own the third parity surface (post-tasks squad HIGH):** in this WP's own test file (`test_bundle_validate_extension.py`), add the assertion `set(bundle._KIND_SUFFIX) == set(DIRECT_WRITE_KINDS)` (introspecting the live constant, not a hardcoded copy). WP01's parity test covers scanner+manifest; this completes the NFR-002 three-surface closer without WP02 editing a WP01-owned file.

### T007 — Manifest-driven resolution for registered artifacts
- **Scope names three functions, not two (post-tasks squad MEDIUM):** load the synthesis manifest in `validate_synthesis_state` (~L263) and thread it into BOTH `_check_artifacts_have_provenance` (~L408, forward: artifact→sidecar) AND `_check_provenance_have_artifacts` (~L427, reverse: sidecar→artifact) — the forward+reverse pair is what produces the "2 errors per directive". The leaf helpers `_find_artifact` (~L502) / `_kind_and_slug_from_artifact` (~L482) are where the manifest lookup lands.
- For an artifact/sidecar that IS in the manifest, resolve `(kind, slug, path, provenance_path)` from the manifest entry (already recorded — `manifest.py:47-61`), NOT by re-parsing the filename. This is what lets a registered SCREAMING-named directive validate clean without a rename. Do not halve the scope to just the leaf helpers.

### T008 — Keep the filesystem orphan sweep BOTH directions
- **Do NOT go fully manifest-driven** (post-plan squad MEDIUM). Retain a filesystem walk so that:
  - an on-disk provenance sidecar with no manifest entry / no backing artifact still errors ("references non-existent artifact");
  - an on-disk doctrine artifact absent from the manifest with no sidecar still errors ("has no provenance sidecar").
  - Compare disk sidecars against the manifest `provenance_path` set and disk artifacts against the manifest `path` set. The `<NNN>-` digit-strip in `_kind_and_slug_from_artifact` is retained for this orphan/legacy path (its test at `test_bundle_validate_extension.py:500` stays green, or is retired deliberately with the parse if you refactor it).

### T009 — Tests
- Extend `tests/charter/synthesizer/test_bundle_validate_extension.py`:
  - **5-kind + registered-clean coverage MUST drive the real engine (post-tasks squad HIGH — non-fakeable):** author the directive + `agent_profile` + `procedure` via `author_guidance()` and register them with `commit_project_registration()` (the seam in `tests/charter/test_project_registration.py`), THEN run `validate_synthesis_state`. Assert no "unknown kind" (agent_profile/procedure) and that a registered SCREAMING-filename directive validates clean with the file unmodified (FR-006). **Do NOT** satisfy this by hand-writing artifact+sidecar+manifest via `_write_artifact`/`_write_provenance`, and **do NOT** extend the 3-kind `_write_artifact` strawman helper to 5 kinds — a hand-fabricated manifest never exercises the engine's slug derivation, so it cannot catch the bug this WP fixes.
  - orphan BOTH directions still error (NFR-001) — these MAY use filesystem fabrication (orphans are by definition non-registered): (a) `agent_profile-ghost.yaml` with no artifact; (b) `orphan.directive.yaml` on disk absent from the manifest with no sidecar.
  - legacy no-synthesis-state project still passes (NFR-003) — keep the existing ~8 walk-based tests green.

## Branch Strategy
Base/merge: `fix/doctrine-slug-canonicalization`. Worktree per `lanes.json` lane. Topology coord.

## Definition of Done
- `charter bundle validate` recognises 5 kinds; registered artifacts resolve via manifest; orphans caught both directions; legacy passes.
- The existing walk-based tests in `test_bundle_validate_extension.py` remain green (hybrid, not fully manifest-driven).
- `ruff` + `mypy` clean, no suppressions. Complexity ≤15 (extract a manifest-lookup helper if `_kind_and_slug_from_artifact` grows).

## Risks
- Going fully manifest-driven would silently skip orphan/legacy artifacts — the highest-risk mistake here. Keep the hybrid split explicit and tested.
- Import cycle bundle↔artifact_kinds — none expected (leaf), but verify.

## Reviewer guidance
Verify the orphan sweep is still filesystem-driven (grep for the retained walk); confirm both orphan-direction tests exist and fail if the sweep is removed; confirm the 5-kind table is derived from `DIRECT_WRITE_KINDS`, not a fresh literal.
