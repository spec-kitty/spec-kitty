---
work_package_id: WP01
title: 'Authority foundation: DIRECT_WRITE_KINDS + slug_for'
dependencies: []
requirement_refs:
- FR-004
- FR-005
- NFR-002
- NFR-004
planning_base_branch: fix/doctrine-slug-canonicalization
merge_target_branch: fix/doctrine-slug-canonicalization
branch_strategy: Planning artifacts for this mission were generated on fix/doctrine-slug-canonicalization. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctrine-slug-canonicalization unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctrine-slug-canonicalization-01M31SP9
base_commit: d1c32805171b9685275587a111eb0a24155d9746
created_at: '2026-09-21T11:44:04.861851+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- at: '2026-09-21T11:10:00+00:00'
  actor: claude
  note: WP created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/
create_intent:
- tests/charter/test_slug_for.py
- tests/charter/test_direct_write_kinds_parity.py
execution_mode: code_change
owned_files:
- src/charter/offering/artifact_kinds.py
- src/charter/offering/drg/project_scan.py
- src/charter/activation/synthesizer/manifest.py
- tests/charter/test_slug_for.py
- tests/charter/test_direct_write_kinds_parity.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: run `/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --json`) and apply its initialization, boundaries, directives, and tactics. State which you applied.

## Objective

Establish the two single authorities the rest of the mission depends on, so the slug-derivation drift (three surfaces disagreeing) is closed by construction (DIRECTIVE_043):
1. A module-level, importable `DIRECT_WRITE_KINDS` constant (the five registration-writing kinds).
2. A pure `slug_for(kind, identifier)` helper that preserves the engine's existing `quote(…, safe="")` URL-encoding.

Read `plan.md`, `research.md` (Decisions 2 & 3), and `contracts/slug-authority-contract.md` before starting. This WP wires no consumers beyond making the scanner and manifest reference the constant; the scaffolder/engine/validator are WP02/WP03.

## Subtasks

### T001 — Mint `DIRECT_WRITE_KINDS`
- In `src/charter/offering/artifact_kinds.py` (leaf module, stdlib-only), add a module-level constant:
  `DIRECT_WRITE_KINDS: tuple[str, ...] = ("directive", "tactic", "styleguide", "procedure", "agent_profile")`.
- These are exactly the kinds `scan_project_artifacts` produces (today a function-local tuple at `project_scan.py:193`) and for which the registration engine writes a `<kind>-<slug>.yaml` provenance sidecar.
- Add a docstring tying it to the registration engine + `_PATTERNS` so a future sixth kind is a one-line, obvious edit.

### T002 — Add pure `slug_for(kind, identifier)`
- In `artifact_kinds.py`, add `def slug_for(kind: str, identifier: str) -> str`. Extract the logic verbatim from `project_registration.py:187`:
  - directive → `quote(identifier.lower().replace("_", "-"), safe="")`
  - other kinds → `quote(identifier, safe="")`
- **`quote(…, safe="")` is load-bearing, not decoration** (post-plan squad CRITICAL): dropping it reintroduces a provenance-directory path escape for a namespaced id (e.g. `agent_profile:team/ops-responder`) and would regress `tests/charter/test_project_registration.py:165-166`. Keep it. Add a docstring stating the id-grammar precondition (directive `^[A-Z][A-Z0-9_-]*$`; non-directive lowercase-kebab, URN-safe).
- Pure: no IO, deterministic. `from urllib.parse import quote`.
- Add BOTH `DIRECT_WRITE_KINDS` and `slug_for` to the module's `__all__` (post-tasks squad MEDIUM — `artifact_kinds.py` enumerates its public exports; omitting them violates the module's public-contract convention).

### T003 — Reference the constant from scanner + manifest
- `project_scan.py`: replace the function-local `kinds = (...)` tuple (~L193) with a reference to `DIRECT_WRITE_KINDS` (keep the parallel `schemas` tuple ordering aligned).
- `synthesizer/manifest.py`: make `ManifestArtifactEntry.kind`'s `Literal` reference the same five kinds (or a type derived from `DIRECT_WRITE_KINDS`); if a `Literal` cannot consume a runtime tuple, keep the `Literal` spelling but add a module-level assertion/test (T005) that its args equal `DIRECT_WRITE_KINDS`.

### T004 — `slug_for` unit tests [P]
- New `tests/charter/test_slug_for.py`: assert `slug_for("directive","LOVE_THY_ENEMY")=="love-thy-enemy"`; `slug_for("agent_profile","retrospective-facilitator")=="retrospective-facilitator"`; `slug_for("agent_profile","team/ops-responder")=="team%2Fops-responder"` (quoted — no escape); determinism; leading-letter guarantee (no pure-digit leading segment for a directive).
- **Equivalence-to-old-inline guard (post-tasks squad MEDIUM):** assert `slug_for(kind, id)` equals the pre-refactor inline expression `quote(id.lower().replace('_','-') if kind=='directive' else id, safe='')` over a representative table — a digit-bearing directive (`DIRECTIVE_025` → `directive-025`), an underscore directive (`LOVE_THY_ENEMY`), a kebab non-directive, and a namespaced profile (`team/ops-responder`). This is what makes WP03's extraction *provably* byte-identical rather than a post-refactor tautology; WP03 T014's "convergence" check alone cannot catch drift from the old expression.

### T005 — Parity guard test [P]
- New `tests/charter/test_direct_write_kinds_parity.py`: assert the **scanner** kind tuple (`project_scan.py`) and the **manifest** `ManifestArtifactEntry.kind` `Literal` args both equal `set(DIRECT_WRITE_KINDS)`. **Introspect the live annotations** — `typing.get_args(...)` on the live `ManifestArtifactEntry.kind` field and import the live scanner tuple — do NOT hardcode a set literal (a hardcoded copy proves nothing and is itself fakeable).
- **Scope boundary (post-tasks squad HIGH, paula+renata):** WP01 asserts scanner+manifest ONLY. The third surface `bundle._KIND_SUFFIX` is only 5-kind after WP02 and its test file is WP02-owned, so the `bundle._KIND_SUFFIX.keys() == set(DIRECT_WRITE_KINDS)` assertion is added by **WP02 T006 in WP02's own test file** — NOT here. Do not import or reach into `bundle.py` from this WP01-owned test.
- NFR-002 anti-drift closer (completed jointly with WP02 T006). The manifest `Literal` stays hand-typed (a `Literal` can't consume a runtime tuple), so its alignment is by-test, not by-construction — that is why this guard exists.

## Branch Strategy
Planning/base branch: `fix/doctrine-slug-canonicalization`. Final merge target: `fix/doctrine-slug-canonicalization`. Execution worktree is allocated per the computed lane in `lanes.json` (do not reconstruct the path). This mission's topology is coord.

## Definition of Done
- `DIRECT_WRITE_KINDS` and `slug_for` exist in `artifact_kinds.py`; scanner + manifest reference the constant.
- `test_slug_for.py` + `test_direct_write_kinds_parity.py` pass.
- `ruff check` + `ruff format --check` (if applicable) + `mypy` clean on touched files; no suppressions (C-003).
- No behavior change to any consumer yet (pure additions + one refactor of the scanner tuple).

## Risks
- `Literal` cannot be built from a runtime tuple — mitigate with the T005 assertion rather than forcing a fragile construct.
- Import direction: `artifact_kinds.py` must stay stdlib-only (leaf). Do not import scanner/manifest into it.

## Reviewer guidance
Confirm `quote()` is preserved in `slug_for`; confirm the scanner/manifest now reference the single constant (no duplicated 5-kind literal remains except the guarded `Literal`); confirm the parity test would fail if a kind were added to one place but not the constant.
