# Tasks: Canonical doctrine artifact slug convention

**Mission**: `doctrine-slug-canonicalization-01M31SP9` | **Branch**: `fix/doctrine-slug-canonicalization`
Scope: #4832 (kebab slug convention) + #4833 (5-kind validator table) + #4834 (path-update, independent). Migration dropped (go-forward only). Design of record: `plan.md`, `research.md`, `contracts/`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Mint module-level `DIRECT_WRITE_KINDS` constant in `artifact_kinds.py` | WP01 | |
| T002 | Add pure `slug_for(kind, identifier)` (quoted; directive-kebab / other-verbatim) in `artifact_kinds.py` | WP01 | |
| T003 | Reference `DIRECT_WRITE_KINDS` from `scan_project_artifacts` (`project_scan.py`) and `ManifestArtifactEntry.kind` (`manifest.py`) | WP01 | |
| T004 | Unit tests for `slug_for` (directive kebab, non-directive verbatim, namespaced `quote`) | WP01 | [P] |
| T005 | Parity guard test: validator/scanner/manifest kind sets all equal `DIRECT_WRITE_KINDS` | WP01 | [P] |
| T006 | Derive `_KIND_SUFFIX`/`_ALL_ARTIFACT_PATTERNS` from `DIRECT_WRITE_KINDS` (3→5) in `bundle.py` | WP02 | |
| T007 | Make registered-artifact resolution manifest-driven (`_find_artifact`/`_kind_and_slug_from_artifact`) | WP02 | |
| T008 | Retain filesystem orphan sweep in BOTH directions (orphan sidecar; orphan artifact absent from manifest) | WP02 | |
| T009 | Tests: 5-kind coverage (agent_profile+procedure no "unknown kind"); registered SCREAMING-file directive validates clean unmodified; orphan both-directions still error; legacy no-manifest still passes | WP02 | |
| T010 | Route engine slug through `slug_for` at `project_registration.py:187` (single authority; preserve `quote`) | WP03 | |
| T011 | Fix `_registration_records` early-`continue` to re-write manifest entry on path/provenance drift (#4834) | WP03 | |
| T012 | Reconcile `previous.slug` against `slug_for(kind, id)` (do not perpetuate a legacy non-canonical slug) | WP03 | |
| T013 | Route `charter new` scaffolder `_artifact_filename` (`doctrine.py`) through `slug_for` | WP03 | |
| T014 | Cross-surface convergence test (scaffolder == engine == manifest slug); namespaced-id path-escape guard stays green | WP03 | |
| T015 | Real-engine e2e acceptance test: author SCREAMING directive + activate project profile → `charter bundle validate` green, files unmodified | WP03 | |
| T016 | #4834 path-update test (drifted path, unchanged content → manifest re-written, sidecar not deleted) | WP03 | [P] |
| T017 | Author ADR: kebab canonical slug, id/slug decoupling, single `slug_for` authority, hybrid manifest-driven validation, `DIRECT_WRITE_KINDS` | WP04 | |
| T018 | Update CHANGELOG.md entry referencing #4832/#4833/#4834 | WP04 | [P] |

## Work Packages

### WP01 — Authority foundation: `DIRECT_WRITE_KINDS` + `slug_for` (prompt: `tasks/WP01-authority-foundation.md`)
- **Goal**: One importable kind constant and one pure slug authority, referenced by the scanner and the manifest. Closes the drift class by construction (DIRECTIVE_043).
- **Priority**: P1 (foundation; the edit #4832 and #4833 collide on — lands first).
- **Independent test**: `slug_for` unit tests + the parity guard pass; no consumer wired yet beyond scanner/manifest reference.
- **Subtasks**: T001, T002, T003, T004, T005.
- **Dependencies**: none.
- **Est. size**: ~300 lines.

### WP02 — Hybrid manifest-driven validator + 5-kind table (prompt: `tasks/WP02-hybrid-validator.md`)
- **Goal**: `charter bundle validate` recognises all five registration-writing kinds and resolves registered artifacts via the manifest, while keeping the filesystem orphan sweep in both directions. Fixes existing SCREAMING-filename repos without renaming.
- **Priority**: P1.
- **Independent test**: bundle-validate tests green (5-kind, registered-SCREAMING-file clean, orphan both-directions error, legacy passes).
- **Subtasks**: T006, T007, T008, T009.
- **Dependencies**: WP01.
- **Est. size**: ~420 lines.

### WP03 — Producers via `slug_for` + #4834 (prompt: `tasks/WP03-producers-and-path-update.md`)
- **Goal**: Scaffolder and engine derive slugs through the single `slug_for` authority (preserving `quote`); the #4834 path/provenance-drift re-write and `previous.slug` reconciliation land here; the real-engine e2e acceptance test proves the field-report scenario green.
- **Priority**: P1.
- **Independent test**: convergence + e2e acceptance + #4834 path-update tests green; existing `test_project_registration.py:165-166` namespaced-id guard stays green.
- **Subtasks**: T010, T011, T012, T013, T014, T015, T016.
- **Dependencies**: WP01, WP02 (e2e test needs the hybrid validator).
- **Est. size**: ~480 lines.

### WP04 — ADR + changelog (prompt: `tasks/WP04-adr.md`)
- **Goal**: Record the canonical-convention decision as an ADR and a changelog entry.
- **Priority**: P2 (documentation; no code dependency beyond the decision).
- **Independent test**: ADR file present with context/decision/consequences; changelog entry added.
- **Subtasks**: T017, T018.
- **Dependencies**: WP01.
- **Est. size**: ~150 lines (planning_artifact).

## MVP scope
WP01 + WP02 deliver the core: existing repos validate green (WP02) on a single kind authority (WP01). WP03 completes go-forward correctness (new artifacts born kebab) + #4834. WP04 is documentation.

## Parallelization
WP01 first (foundation). WP02 and WP03's non-e2e work depend only on WP01, but WP03's e2e acceptance test depends on WP02, so WP03 sequences after WP02. WP04 can run any time after WP01.
