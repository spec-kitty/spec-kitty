# Implementation Plan: Canonical doctrine artifact slug convention

**Branch**: `fix/doctrine-slug-canonicalization` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/doctrine-slug-canonicalization-01M31SP9/spec.md`

## Summary

Three surfaces derive a doctrine artifact's on-disk slug independently — the `charter new` scaffolder emits the id verbatim (SCREAMING for directives), the registration engine kebab-cases directive ids, and the bundle validator re-parses the filename — so `charter bundle validate` reports two errors per project directive (#4832) while its kind table (three kinds) rejects the `agent_profile`/`procedure` sidecars the engine itself writes (#4833). The fix adopts **kebab-case as the single canonical filename/slug** (authored `id` preserved and formally decoupled from slug), routes the scaffolder and engine through one pure `slug_for(kind, identifier)` authority (which **preserves the engine's `quote(…, safe="")` URL-encoding** — a post-plan-squad CRITICAL: an unquoted slug reintroduces a provenance-path escape for namespaced ids), makes the bundle validator **hybrid manifest-driven** (trust the recorded `(kind, slug, path, provenance_path)` for registered artifacts, keep the filesystem walk for orphan/legacy), extends the validator kind table to all **five** registration-writing kinds behind one importable `DIRECT_WRITE_KINDS` constant, and fixes the `_registration_records` path-update early-`continue` gap (#4834, now an independent correctness fix). The convention is recorded as an ADR. Drift is closed by construction (DIRECTIVE_043): a single slug authority + a validator kind-set derived from one importable constant.

**Post-plan brownfield squad revision (see `research.md` § Adversarial evidence):** the filename **migration/self-heal was dropped** — the manifest already records the kebab slug regardless of the on-disk filename, so the hybrid validator fixes existing SCREAMING-filename repos **without renaming**; a rename is cosmetic and would risk silently dropping stem-keyed directive activations (#3816 class). Go-forward only.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: stdlib only (`ast` not required); existing `charter`/`specify_cli` internals — no new third-party dependency (supply-chain section N/A)
**Storage**: filesystem — `.kittify/doctrine/**` artifacts, `.kittify/charter/provenance/*.yaml` sidecars, the synthesis manifest
**Testing**: pytest (`make test-fast` baseline + targeted `tests/charter/`, `tests/specify_cli/`), ruff, mypy
**Target Platform**: Spec Kitty CLI (Linux/macOS/Windows)
**Project Type**: single project (CLI tool)
**Performance Goals**: no regression; `slug_for` is O(len(id)) pure; validation cost unchanged
**Constraints**: ruff + mypy zero-issue, no suppressions; complexity ≤15; no new/changed literal duplicated ≥3× (hoist per S1192); loopback/localhost N/A
**Scale/Scope**: ~5 source files + new pure helper + migration + 1 ADR; blast radius contained to the charter bundle/registration/scaffolder surface (validated by the research+design squad)

## Constitution Check (Charter Check)

Charter present (`.kittify/charter/charter.md`). Relevant directives (from `charter context --action plan`):

- **DIRECTIVE_043 (close the drift class by construction)** — SATISFIED by design: one `slug_for` authority for all producers + a validator kind-set derived from / guarded equal to the engine's kind list (NFR-002), so the three-way drift cannot recur.
- **Single canonical authority** — SATISFIED: the synthesis manifest becomes the validator's authority (no second filename-parsing derivation); `slug_for` is the single slug authority; `ArtifactKind._PATTERNS` / `scan_project_artifacts` kind list is the single kind authority.
- **ATDD / red-first (DIRECTIVE_003)** — every WP lands failing tests first (the reported bug scenarios are the acceptance tests).
- **Terminology** — canonical "doctrine artifact", "provenance sidecar", "synthesis manifest"; no `feature*` aliases introduced.
- **Campsite / no suppressions** — C-003 binds.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/doctrine-slug-canonicalization-01M31SP9/
├── plan.md              # this file
├── research.md          # Phase 0 — decisions/rationale/alternatives + adversarial evidence
├── data-model.md        # Phase 1 — artifact / sidecar / manifest / slug-authority model
├── quickstart.md        # Phase 1 — how to verify the fix end to end
├── contracts/           # Phase 1 — behavioral contracts (slug_for, manifest-driven validate, path-update, migration)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/charter/
├── offering/
│   ├── artifact_kinds.py            # _PATTERNS / kind authority; home for pure slug_for(kind, id) + the new importable DIRECT_WRITE_KINDS constant
│   └── drg/project_scan.py          # scan_project_artifacts references DIRECT_WRITE_KINDS (was a function-local tuple)
├── bundle.py                        # _KIND_SUFFIX/_ALL_ARTIFACT_PATTERNS derived from DIRECT_WRITE_KINDS (3→5); HYBRID resolution: manifest for registered, filesystem walk for orphans (both directions); NNN- parse retained for orphan path
└── activation/
    ├── project_registration.py      # route slug via slug_for (preserving quote); fix _registration_records path/provenance-drift early-continue (#4834); reconcile previous.slug vs slug_for; NO rename (migration dropped)
    ├── synthesizer/provenance.py    # provenance sidecar path (unchanged; consumes slug_for output)
    └── synthesizer/manifest.py      # ManifestArtifactEntry.kind Literal references DIRECT_WRITE_KINDS

src/specify_cli/cli/commands/
└── doctrine.py                      # _artifact_filename → slug_for(kind, id) for the `charter new` scaffolder

docs/adr/3.x/
└── 2026-09-21-*-kebab-canonical-doctrine-artifact-slug.md   # the ADR (FR-008)

tests/charter/                        # DIRECT_WRITE_KINDS parity guard; bundle-validate 5-kind; hybrid manifest resolution; orphan-caught BOTH directions; namespaced-id path-escape guard; slug_for unit + convergence; #4834 path-update; all via the real engine (test_project_registration.py seam)
tests/specify_cli/cli/commands/       # scaffolder kebab filename + cross-surface convergence
```

**Structure Decision**: single-project CLI. The new `slug_for` authority and `DIRECT_WRITE_KINDS` constant live in `src/charter/offering/artifact_kinds.py` (co-located with `_PATTERNS`, a leaf module importing only stdlib) so the scaffolder (`specify_cli`), the engine (`charter`), the scanner, the manifest, and the validator all reference one authority — the existing `specify_cli → charter.offering` edge is the sanctioned down-direction (architect lens confirmed: zero new cross-layer edge, no pytestarch LayerRule risk).

## Complexity Tracking

None. No charter violations to justify. Watch: keep `_kind_and_slug_from_artifact`/`_find_artifact` and the migration self-heal under complexity 15 by extracting the manifest lookup as a small helper.

## Parallel Work Analysis

### Dependency Graph

```
WP01 (authority foundation) ──┬──► WP02 (hybrid manifest-driven validator + 5-kind table, #4833)
  DIRECT_WRITE_KINDS constant  │
  + slug_for (quoted)          └──► WP03 (producers via slug_for + #4834 path-update, #4832 #4834)
  + 5-kind table + parity              (WP03 also depends on WP02: its real-engine e2e needs the validator)

WP04 (ADR + changelog) — parallel, no code dep (lands with/after WP01)
```

(Migration self-heal removed — go-forward only per the post-plan squad. This is the authoritative 4-WP decomposition; `tasks.md` carries the binding lane graph + ownership.)

### Work Distribution

- **Sequential (foundation first)**: WP01 — the importable `DIRECT_WRITE_KINDS` constant, the pure `slug_for(kind, identifier)` authority (preserving `quote(…, safe="")`), the 3→5 `_KIND_SUFFIX` extension derived from the constant, and the parity guard. This is the edit both #4832 and #4833 collide on, so it lands first to remove the collision.
- **After WP01**: WP02 (hybrid manifest-driven validator + 5-kind table + both-direction orphan guards) and WP04 (ADR + changelog, docs-only) run in parallel.
- **After WP01 + WP02**: WP03 (scaffolder + engine routed through `slug_for`, `previous.slug` reconciliation, #4834 path/provenance-drift re-write, namespaced-id path-escape guard, and the real-engine e2e acceptance test — which needs WP02's validator).

### Coordination Points

- **Shared surface**: `bundle.py` (`_KIND_SUFFIX`/`_kind_and_slug_from_artifact`) and `project_registration.py` (slug logic) are touched by WP01/WP03/WP04 — lane sequencing (WP01 first) prevents self-collision.
- **Real-engine acceptance gate** (`quickstart.md`): author a SCREAMING project directive AND activate a project profile in a fixture repo **via the real engine** (`test_project_registration.py` seam — NOT hand-written sidecars), assert `charter bundle validate` is green with the files unmodified. This is the mission's acceptance gate; a hand-written-sidecar test that bypasses the scaffolder→engine slug path is a fakeable DoD and is rejected.

## Adversarial evidence

The post-plan brownfield point-cut (3 profile-loaded lenses) findings and dispositions are recorded in `research.md` § Adversarial evidence (1 CRITICAL, 4 HIGH, 5 MEDIUM — all `accepted`; 1 LOW `deferred_with_rationale`). Notable outcomes folded here: `quote()` preserved in `slug_for`; migration dropped; hybrid validator with both-direction orphan sweep; importable `DIRECT_WRITE_KINDS`; real-engine acceptance tests.
