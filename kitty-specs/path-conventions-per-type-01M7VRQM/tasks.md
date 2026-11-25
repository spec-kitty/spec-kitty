# Tasks: Per-mission-type path conventions and a narrow path waiver

**Mission**: `path-conventions-per-type-01M7VRQM` · **Planning branch**: `kitty/mission-path-conventions-per-type-01M7VRQM` · **Merge target**: `issue-7566-path-conventions-per-type`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first reader tests for per-type sections and every fail-closed case | WP01 | |
| T002 | `ProjectPathConventions` value object (dict subclass, `per_type`, `for_mission_type`) | WP01 | |
| T003 | Parse per-type sections; validate inner keys and values with the flat rules | WP01 | |
| T004 | Validate section ids against the injected or layered roster; roster read only when needed | WP01 | |
| T005 | Lint, type and targeted-test verification for the reader | WP01 | |
| T006 | Red-first waiver reader tests (`meta.json` `path_conventions: waived`) | WP03 | [P] |
| T007 | Generalize the #5298 waiver reader; add `read_path_conventions_waiver_from_meta` | WP03 | [P] |
| T008 | `MissionMetaOptional` fields + `record_acceptance(path_conventions_waiver_reason=...)` | WP03 | [P] |
| T009 | Verify WP03 (existing contracts waiver tests unchanged and green) | WP03 | [P] |
| T010 | Red-first seam tests: per-type wins for its type only; open-packs fixture | WP02 | |
| T011 | Resolve the Mission type at `evaluate_path_conventions`; pass per-type overrides and the type | WP02 | |
| T012 | Waiver effect at the seam (per-run flag input + `meta.json` waiver); notices | WP02 | |
| T013 | Red-first remedy tests; rewrite `_remap_guidance_lines` / `format_errors` / `format_warnings` | WP02 | |
| T014 | Update the #3783 / #7512 pins deliberately; verify WP02 | WP02 | |
| T015 | Red-first CLI tests for `--waive-path-conventions` / `--waive-reason` | WP04 | |
| T016 | Add the options, refuse a missing or blank reason, thread through `_AcceptRun` | WP04 | |
| T017 | Thread through `collect_feature_summary` / `perform_acceptance` / the record | WP04 | |
| T018 | Forward the flags from `agent mission accept`; update the `--lenient` help; orchestrator-api positive control | WP04 | |
| T019 | Verify WP04 (CLI tests, accept suites, single-caller gate) | WP04 | |
| T020 | ADR `2026-08-28-1` amendment | WP05 | |
| T021 | How-to `accept-and-merge.md` update | WP05 | |
| T022 | Changelog fragment(s) | WP05 | |

## Work Packages

### WP01 — Per-type configuration reader (foundational)

**Prompt**: [tasks/WP01-per-type-config-reader.md](tasks/WP01-per-type-config-reader.md)
**Goal**: `load_project_path_conventions` reads per-type sections fail-closed; the flat form is unchanged.
**Independent test**: `tests/specify_cli/config/test_path_conventions_reader.py`.
**Dependencies**: none.

T001 Red-first reader tests for per-type sections and every fail-closed case (WP01)
T002 `ProjectPathConventions` value object (WP01)
T003 Parse and validate per-type sections (WP01)
T004 Validate section ids against the layered roster (WP01)
T005 Verify (WP01)

### WP03 — `meta.json` path-conventions waiver and history field

**Prompt**: [tasks/WP03-meta-waiver-reader.md](tasks/WP03-meta-waiver-reader.md)
**Goal**: one fail-closed reader for the per-Mission waiver, and a history field for the per-run waiver.
**Dependencies**: none (parallel with WP01).

T006 Red-first waiver reader tests (WP03)
T007 Generalize the waiver reader (WP03)
T008 Metadata fields and history recording (WP03)
T009 Verify (WP03)

### WP02 — Per-type resolution, waiver effect and remedy text at the accept seam

**Prompt**: [tasks/WP02-seam-resolution-and-remedy.md](tasks/WP02-seam-resolution-and-remedy.md)
**Goal**: the single caller resolves per type and applies the waivers; the texts lead with the per-type remap.
**Dependencies**: WP01, WP03.

T010 Red-first seam tests and the open-packs fixture (WP02)
T011 Resolve the Mission type and per-type overrides (WP02)
T012 Waiver effect at the seam (WP02)
T013 Remedy text (WP02)
T014 Pins and verification (WP02)

### WP04 — `accept` CLI flags for the per-run waiver

**Prompt**: [tasks/WP04-accept-waiver-flags.md](tasks/WP04-accept-waiver-flags.md)
**Goal**: `accept --waive-path-conventions --waive-reason`, recorded on history, metadata still strict, orchestrator-api strict.
**Dependencies**: WP02, WP03.

T015 Red-first CLI tests (WP04)
T016 Options and refusal (WP04)
T017 Threading to summary and record (WP04)
T018 Agent wrapper, help text, orchestrator positive control (WP04)
T019 Verify (WP04)

### WP05 — Documentation

**Prompt**: [tasks/WP05-docs.md](tasks/WP05-docs.md)
**Goal**: ADR amendment, how-to and changelog.
**Dependencies**: WP04.

T020 ADR amendment (WP05)
T021 How-to update (WP05)
T022 Changelog fragment(s) (WP05)

## Parallelization

WP01 and WP03 are independent. WP02 needs both. WP04 follows WP02. WP05 is last.

## MVP

WP01 + WP02 deliver the per-type override (#7748) and the remedy (#7566 problems 1 and 3). WP03 + WP04 deliver the narrow escape (#7566 problem 2).
