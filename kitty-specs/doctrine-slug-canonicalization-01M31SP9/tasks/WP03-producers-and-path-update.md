---
work_package_id: WP03
title: 'Producers via slug_for + #4834 path-update'
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-007
planning_base_branch: fix/doctrine-slug-canonicalization
merge_target_branch: fix/doctrine-slug-canonicalization
branch_strategy: Planning artifacts for this mission were generated on fix/doctrine-slug-canonicalization. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctrine-slug-canonicalization unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
- T016
history:
- at: '2026-09-21T11:10:00+00:00'
  actor: claude
  note: WP created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_slug_canonicalization_e2e.py
execution_mode: code_change
owned_files:
- src/charter/activation/project_registration.py
- src/specify_cli/cli/commands/doctrine.py
- tests/charter/test_project_registration.py
- tests/specify_cli/cli/commands/test_doctrine_new.py
- tests/charter/test_slug_canonicalization_e2e.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Run `/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --json`) and apply it. State which you applied.

## Objective

Route both slug producers — the `charter new` scaffolder and the registration engine — through the single `slug_for` authority (WP01), preserving `quote()`; fix the #4834 manifest path/provenance-drift gap; and prove the end-to-end field-report scenario green with the real engine. Read `contracts/slug-authority-contract.md`, `contracts/registration-path-update-and-migration-contract.md`, and `quickstart.md`. Depends on WP01 (`slug_for`) and WP02 (hybrid validator, for the e2e test). **No file renames** — migration was dropped (go-forward only); do not add rename logic.

## Subtasks

### T010 — Engine slug via `slug_for`
- In `src/charter/activation/project_registration.py:187`, replace the inline `quote(identifier.lower().replace("_","-") if kind=="directive" else identifier, safe="")` with a call to `slug_for(kind, identifier)`. Behavior must be byte-identical (that's the point — single authority, no change).

### T011 — #4834 path-update
- Fix the `_registration_records` early-`continue` (~L195): when `previous.content_hash == content_hash and sidecar.is_file()` it currently skips the manifest rebuild entirely. Change it to still re-write the entry when `previous.path != resolved_path` OR `previous.provenance_path != resolved_provenance_path`. Do not delete sidecars.

### T012 — Reconcile `previous.slug`
- Where an existing entry's `previous.slug` is reused (`project_registration.py:191`), reconcile it against `slug_for(kind, id)`; do not perpetuate a legacy non-canonical slug. Benign under today's data, but stated so a future non-canonical slug cannot silently survive.
- **Falsifying test REQUIRED (post-tasks squad MEDIUM — otherwise this DoD has no test that could fail):** hand-seed a manifest entry with a non-canonical `previous.slug` (e.g. `LOVE_THY_ENEMY`) on unchanged content (a legitimate legacy scenario — hand-seeding is correct here), run one registration pass, assert the slug is rewritten to `love-thy-enemy` (and the sidecar renamed accordingly). Without this test, T012 can be skipped entirely with every other test still green.

### T013 — Scaffolder via `slug_for`
- In `src/specify_cli/cli/commands/doctrine.py`, `_artifact_filename` (~L583): derive the filename stem via `slug_for(kind, artifact_id)` (keep the extension from `_PATTERNS`). A directive `LOVE_THY_ENEMY` now scaffolds as `love-thy-enemy.directive.yaml` with `id: LOVE_THY_ENEMY` preserved inside the stub body. Non-directive kinds unchanged (slug_for is verbatim+quote for them).

### T014 — Convergence + path-escape guard tests
- `tests/specify_cli/cli/commands/test_doctrine_new.py`: assert `charter new directive MY_DIRECTIVE` writes `my-directive.directive.yaml` with `id: MY_DIRECTIVE` inside.
- Cross-surface convergence: scaffolder stem == engine slug == manifest slug for a SCREAMING directive id. **Note (post-tasks squad MEDIUM):** once T010+T013 route all producers through `slug_for`, this convergence is trivially true (same function) and does NOT prove byte-identity with the OLD inline expression — that anti-regression guard lives in WP01 T004's equivalence table, not here. Keep this as a wiring check, not the byte-identity proof.
- Confirm the existing namespaced-id path-escape guard `tests/charter/test_project_registration.py:165-166` stays green after routing through `slug_for`.

### T015 — Real-engine e2e acceptance test
- New `tests/charter/test_slug_canonicalization_e2e.py`: in a fixture repo, via the REAL engine (`plan_project_registration`/`commit_project_registration`, reusing the seam in `test_project_registration.py` — NOT hand-written sidecars): author a SCREAMING-filename directive AND activate a project agent profile, then assert `validate_synthesis_state` (`charter bundle validate`) is green with no "unknown kind" and the on-disk files unmodified. This is the mission's acceptance gate (SC-001/SC-002/SC-003).

### T016 — #4834 path-update test [P]
- Seed a manifest entry whose `path`/`provenance_path` differs from the resolved values on unchanged content; run one registration pass; assert the entry is re-written (not skipped) and no sidecar deleted; `verify_manifest` green.

## Branch Strategy
Base/merge: `fix/doctrine-slug-canonicalization`. Worktree per `lanes.json` lane. Topology coord.

## Definition of Done
- Scaffolder + engine both derive slugs via `slug_for` (single authority); `quote()` preserved.
- #4834 path/provenance-drift re-write lands; `previous.slug` reconciled.
- e2e acceptance test green (directive + profile, real engine, files unmodified); convergence + path-escape + scaffolder tests green.
- `ruff` + `mypy` clean, no suppressions; complexity ≤15.
- No rename logic anywhere (migration out of scope).

## Risks
- Behavior drift when swapping the inline slug for `slug_for` — assert byte-identity for existing ids.
- Fakeable test: a hand-written-sidecar e2e is a strawman; MUST drive the real engine.

## Reviewer guidance
Confirm no rename/`os.rename`/`PathGuard.rename` was added; confirm the e2e test uses the real engine; confirm `slug_for` is the only slug derivation left in both producers (no duplicated inline logic).
