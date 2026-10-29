# Mission Specification: Mission walkers share one residue rule

**Mission Branch**: `issue-5875-mission-walker-is-mission-dir`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Issue #5875. Route every `kitty-specs/` Mission walker through `is_mission_dir`, so residue and Mission no longer disagree. The operator ruled on 2026-10-27 that a folder with only a `spec.md` is residue.

## Intent Summary (confirmed)

- **Primary actor:** an operator, or an agent harness, running Mission selection (`spec-kitty next`, `setup-plan`, `agent tasks status`, `migrate backfill-wp-status`, owned-checkout discovery) and the `doctor identity` and `doctor mission-type` audits.
- **Trigger:** a `kitty-specs/` child that holds a `spec.md` but no `meta.json` (or an untracked `meta.json` with no `mission_id`).
- **Desired outcome:** every walker gives the same answer. Selection does not list such a folder and does not auto-select it. `doctor identity` names it as `residue` with a remedy. `doctor mission-type` stops calling it `typeless`.
- **Rule / invariant:** a folder is listed by selection exactly when `doctor identity` does not report it as `residue`, and exactly when `doctor mission-type` audits it (the parity invariant).
- **Boundary:** read-side walkers only. The write-seam residue rule `is_kitty_specs_residue` (#6680), its `RESIDUE_NOTICE`, the upgrade migrations and the resolver index `_build_index` stay unchanged. The index already needs a `mission_id`. No new command or migration (operator).

Confirmed by the operator: the binding ruling plus the answers to D1–D4 in `research.md` §4.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Selection ignores residue (Priority: P1)

An operator has one real Mission plus a leftover `kitty-specs/old-thing/` holding only a `spec.md`. They run `spec-kitty next` without `--mission`. Today that folder counts as a second Mission, so auto-select refuses and lists it as a candidate. After the change, the real Mission is the only one, and it is selected.

**Why this priority**: this is the user-visible disagreement the issue reports.

**Independent Test**: build a fixture with one identity-bearing Mission and one spec.md-only folder. `list_missions_for_selection` returns only the Mission, `sole_mission_for_selection` returns its slug, and the agent-side `_list_feature_spec_candidates` agrees.

**Acceptance Scenarios**:

1. **Given** a spec.md-only folder (tracked or untracked), **When** selection lists Missions, **Then** the folder is absent.
2. **Given** a folder whose `meta.json` carries a `mission_id`, committed or not, **When** selection lists Missions, **Then** it is present.
3. **Given** a git-tracked legacy `meta.json` with no `mission_id`, **When** selection lists Missions, **Then** it is present (`backfill-identity` repairs it).
4. **Given** an untracked `meta.json` with no `mission_id`, in a git repository, **When** selection lists Missions, **Then** it is absent (`is_mission_dir` calls it residue).
5. **Given** a non-git project root with a `meta.json` that has no `mission_id`, **When** selection lists Missions, **Then** it is present (the existence fallback).

### User Story 2 - Doctor names residue with a way out (Priority: P1)

An operator runs `spec-kitty doctor identity`. Folders that selection does not list appear in a separate `residue` state. That state has its own count, its own path section and a remedy, and it is a valid `--fail-on` value. Real Missions with an unreadable or id-less `meta.json` stay `orphan`.

**Why this priority**: the operator ruling requires a way out once selection stops listing these folders.

**Independent Test**: run `doctor identity --json` and the human output against the fixture. The spec.md-only folder has state `residue`, `summary.residue == 1`, the human output prints the remedy, and `--fail-on residue` exits 1.

**Acceptance Scenarios**:

1. **Given** a spec.md-only folder, **When** `doctor identity` runs, **Then** it is reported `residue`, never `orphan`, and the remedy says: delete the folder if it is residue; if it is a real Mission, restore its `meta.json` from git history, or re-create it with `spec-kitty agent mission create` and move the `spec.md` into it.
2. **Given** residue folders that share a numeric prefix, or a human slug, with a Mission, **When** `doctor identity` runs, **Then** they do not show up in the duplicate-prefix or ambiguous-selector sections.
3. **Given** `doctor identity --mission <residue-slug>`, **When** it runs, **Then** the folder is reported as `residue`.

### User Story 3 - Mission-type audit skips residue (Priority: P2)

`spec-kitty doctor mission-type` stops reporting a spec.md-only folder as `typeless`. It audits exactly the folders selection lists.

**Independent Test**: `audit_mission_types` on the fixture returns only the real Mission.

**Acceptance Scenarios**:

1. **Given** a spec.md-only folder, **When** `doctor mission-type` runs, **Then** the folder is absent from its rows and counts.

### Edge Cases

- A Mission whose tracked `meta.json` was deleted on disk (#6673): no `meta.json` on disk, so it is not listed. Doctor reports `residue`, and the remedy points to restoring from git.
- A `meta.json` that is present but unreadable or unparseable, in a git repository, with neither marker tracked: residue with reason `corrupt_meta`. The read error is shown and the remedy says the Mission content is corrupt (D5, 2026-10-29). A tracked corrupt `meta.json` stays a Mission (`orphan`).
- `migrate backfill-wp-status`: its scope (`--mission`, evidence manifest) uses its own write-seam walker rule (D6).
- A broken git index: selection and the mission-type walker use the hardened `probe_tracked_mission_paths` (it degrades to file presence with one warning). `doctor identity` is a read-only reporter and uses `tracked_mission_paths`, so a broken index surfaces as an error there, the same posture as the audit engine. It is rendered as a one-line error and, under `--json`, as a `GIT_INDEX_UNREADABLE` envelope (exit 1), never as a traceback.
- Non-directory children (`README.md`) and unstattable entries are skipped as today (`safe_is_dir` and the `OSError` posture).
- A nested project inside a larger repository: the tracked paths are prefix-stripped by `tracked_mission_paths` (#5856 behaviour, unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One selection predicate | As an operator, I want selection to list a `kitty-specs/` child only when it has a `meta.json` on disk and `is_mission_dir` accepts it, so that residue is never offered as a Mission. | High | Open | build | no |
| FR-002 | Agent candidates agree | As an agent harness, I want `_list_feature_spec_candidates` (setup-plan auto-select, `agent tasks status` default, the detection-error payload) to use the same predicate as FR-001, so that `next` and plan/tasks never disagree on the count. | High | Open | build | no |
| FR-003 | Residue state in doctor identity | As an operator, I want `doctor identity` to classify every child that FR-001 rejects as `residue`, with its own count, path section, JSON value and `--fail-on` value, so that I can see what selection no longer lists. | High | Open | build | no |
| FR-004 | Remedy text | As an operator, I want each residue row to name its reason (`no_meta`, `untracked_idless_meta`, `corrupt_meta`) and to get one remedy per reason, using existing commands only: delete residue; `git restore` or recover a deleted `meta.json` from history; commit it or run `migrate backfill-identity`; or repair a corrupt one (D5). That way I have a correct way out with no new command. | High | Open | build | no |
| FR-005 | Residue excluded from collisions | As an operator, I want residue excluded from the duplicate-prefix and ambiguous-selector reports, so that a folder no selector can reach does not fake a collision. | Medium | Open | build | no |
| FR-006 | Mission-type audit skips residue | As an operator, I want `doctor mission-type` to audit only the children FR-001 accepts, so that residue is not mislabelled `typeless`. | Medium | Open | build | no |
| FR-007 | Parity test | As a maintainer, I want one parity case in `tests/context/test_is_mission_dir.py` that asserts selection, both doctor audits and the agent candidates agree on one fixture (Mission, spec.md-only folder tracked and untracked, tracked id-less legacy, untracked id-less meta, lock-only), so that the walkers cannot drift again. | High | Open | build | no |
| FR-008 | Documented differences | As a maintainer, I want every walker that still differs from FR-001 to say why in its docstring: the resolver index (identity required), the write-seam rule `is_kitty_specs_residue` (a `spec.md` on disk shields it so upgrade can repair), and the audit engine. Then the reasons are visible. | Low | Open | build | no |
| FR-009 | Changelog | As an operator reading the release notes, I want an `[Unreleased]` entry saying that spec.md-only folders are no longer listed as Missions, plus the doctor remedy. | Medium | Open | build | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git cost | Selection spawns no git subprocess when every listed child carries a `mission_id`. Otherwise it runs at most one batch `git ls-files` per listing call, and the walkers in the doctor audits at most one per walk. | Performance | High | Open |
| NFR-002 | Audit budget | `doctor identity` over 200 Missions still completes in under 3 s (the existing NFR-002 of `identity_audit`). | Performance | Medium | Open |
| NFR-003 | Quality gates | Touched code passes ruff, `ruff format --check --force-exclude` and mypy with no new suppressions. Cyclomatic complexity stays at or below 15. Diff coverage is at least 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No new command or migration | Reuse existing commands and `is_mission_dir`, `tracked_mission_paths` and `probe_tracked_mission_paths`. Adding any command or migration needs the operator first. | Business | High | Open |
| C-002 | Write seams untouched | `is_kitty_specs_residue`, `residue_notice_path` and the upgrade migrations do not change their logic. *Amended 2026-10-29 (D7):* the `RESIDUE_NOTICE` remedy text is reworded to "add a meta.json with a mission_id", and its parsing still round-trips. | Technical | High | Open |
| C-003 | Walker gate | No new raw `kitty-specs` walk outside the allowlist. *Amended 2026-10-29:* the doctor walkers now delegate to `mission_resolver.iter_kitty_specs_children`, so `_mission_type_audit.py` and `status/identity_audit.py` left the allowlist. | Technical | High | Open |
| C-004 | Existing states keep meaning | `assigned`, `pending`, `legacy` and `orphan` keep their FR-045 definitions for Missions. `classify_mission` (used by the audit engine's identity adapter) keeps its contract. | Technical | Medium | Open |
| C-005 | Terminology | Say "Mission", never "feature", in all new user-facing text. | Business | Medium | Open |

### Key Entities

- **Mission directory**: a `kitty-specs/` child that FR-001 accepts.
- **Residue directory (read side)**: a `kitty-specs/` directory child that FR-001 rejects. It is stricter than the write-seam residue of #6680 by design: a `spec.md` on disk does not make it a Mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the red-first probe (`research.md` §1), selection returns `['real']`, `doctor identity` reports `legacy-spec-only` as `residue`, and `doctor mission-type` returns only `real`. — build · no-op passable: no
- **SC-002**: The FR-007 parity test fails on the base commit and passes after the change. — build · no-op passable: no
- **SC-003**: The targeted and blast-radius suites (`tests/context`, `tests/status`, `tests/doctor`, selection, resolver and identity tests, `tests/cli`) and `make test-fast` are green. — build · no-op passable: no
