# Implementation Plan: Charter identity single authority

**Branch**: `issue-6433-charter-identity-single-authority` | **Date**: 2026-10-30 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-identity-single-authority-01M68ZQC/spec.md`

Branch contract (from `setup-plan`): current branch at plan start, planning/base branch and final merge target are all `issue-6433-charter-identity-single-authority`; `branch_matches_target` is true.

## Summary

Issue #6433 asked for one stem↔declared-id authority across charter compile and consistency check. Grounding (`research.md`) shows the compile, consistency-check, DRG-filter, preset and project-layer routing already landed in #6406/#6457 (`a8dd1812a6`) and #6749. What remains is the trunk of the issue: `kind_vocabulary.resolve_artifact_urn` is still a second implementation of the rule, and four CLI cascade-source sites call it directly, so a `<kind>:<id>` URN or a normalised directive id (`24`) resolves in the write path and the runtime gate but is refused by the cascade-source resolver — the cascade then silently does nothing (verified red through the shipped CLI, see `research.md`).

The plan is therefore:

1. **Facade** (IC-01): `resolve_artifact_urn`, `resolve_config_id` and `resolve_selected_id_to_stem` answer from `IdentityIndex`; no filesystem scan-and-match loop remains in `kind_vocabulary`. Signatures, exception types and messages unchanged (C-002); the directive representable-stem refusal is expressed over the index's own table.
2. **One scan per pass** (IC-01): the index reads its file list from the existing `kind_vocabulary._iter_artifact_paths` memo, so a caller that threads a `ResolutionPass` keeps one scan per kind instead of acquiring a second scan per facade call (NFR-004).
3. **Cascade surfaces** (IC-02): `activate._source_urn`, `deactivate._source_urn`, `deactivate._active_urns` and `_resynthesis_preflight._cascade_source` resolve through one index per command, so a URN, a declared id and a normalised id cascade exactly as the stem does (FR-004..FR-006).
4. **Pins** (IC-03): a parity matrix over kinds × layers × spellings, a one-policy-per-surface test module for unknown tokens, a scan-count test, and two red-first CLI tests for the cascade reports.
5. **Docs + changelog** (IC-03).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: ruamel.yaml (artifact id reads, already inside `IdentityIndex`), typer/rich (CLI render)
**Storage**: none — the index is per-invocation and in-memory (C-003)
**Testing**: pytest; CLI tests through `typer.testing.CliRunner` on `charter_app` (ledger-seeded, `--no-compile`); unit tests on the facade and the index; `tests/charter/test_kind_vocabulary.py`, `test_config_stem_parity.py` and `test_directive_identity_mapping.py` are the existing behaviour pins (NFR-005)
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: NFR-004 — one layer scan per kind per resolution pass; the facade must not add scans
**Constraints**: no acceptance widening beyond spellings the gate already accepts (C-001); public signatures unchanged (C-002); precedence unchanged (C-004)
**Scale/Scope**: 1 source module (`kind_vocabulary.py`), 1 index module (`identity_index.py`), 4 CLI call sites in 3 files, 3 test modules, 1 architecture doc, 1 changelog entry

## Charter Check

| Gate | Status |
|---|---|
| Single canonical authority | Pass — the point of the Mission: the index becomes the only stem↔id rule; the facades stay as named entry points over it. |
| Architectural alignment | Pass — all changes stay inside `charter.activation`; `specify_cli` keeps orchestrating. No `charter.offering.api` or layer change (ADR 2026-10-16-1). |
| ATDD-first / red-first | Pass — FR-001/FR-004/FR-005 have red proofs recorded in `research.md`; each is written as a failing test before the fix. |
| Terminology | Pass — "activation token", "declared id", "file stem", "cascade source"; run the terminology guard. |
| Tidy-first (Standing Order #2) | Pass — IC-01 is behaviour-preserving for every token the facade already resolved (NFR-005 pins it), then IC-02 widens only where the gate already accepted. |
| No full heavy suites | Pass — targeted modules plus the charter blast radius; no `make test-full`. |
| Pre-existing failures | Pass — none known at this head; any CI red outside the diff is reported, not skipped. |
| Epic #6518 overlap | Pass — #6433 is a child of #6518; this Mission only closes #6433's own residue. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-identity-single-authority-01M68ZQC/
├── spec.md
├── plan.md
├── research.md      # grounding: landed routing, two CLI reproductions, prior-art decisions
├── tasks.md         # by /spec-kitty.tasks
└── traces/          # approach.md, design-decisions.md, tooling-friction.md
```

`contracts/`: none — no API, JSON envelope or persisted-shape change (C-002). `data-model.md` / `quickstart.md`: none — no new entity and no operator-facing new workflow; the change is a resolution seam.

### Source Code (repository root)

```
src/charter/activation/identity_index.py      # scan via the shared _iter_artifact_paths memo; from_roots(resolution_pass=...)
src/charter/activation/kind_vocabulary.py     # the three facades answer from the index; no scan loop remains
src/specify_cli/cli/commands/charter/activate.py            # _source_urn through one index
src/specify_cli/cli/commands/charter/deactivate.py          # _source_urn + _active_urns through one index per command
src/specify_cli/cli/commands/charter/_resynthesis_preflight.py  # _cascade_source through the index
docs/architecture/activation-ledger-and-charter-contract.md  # one sentence: the facades answer from the index
docs/changelog/CHANGELOG.md                   # [Unreleased] fixed entry

tests/charter/activation/test_identity_single_authority_6433.py   # new: parity matrix, unknown-token policies, scan count
tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py  # new: red-first URN/normalised-id cascade reports
tests/charter/test_kind_vocabulary.py, test_config_stem_parity.py, test_directive_identity_mapping.py  # existing pins, unchanged
```

## Implementation Concern Map

### IC-01 — The facades answer from the index

- **Purpose**: remove the second stem↔id implementation so the rule cannot drift, and keep the directive representable-stem refusal while doing it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-008; C-001, C-002, C-004; NFR-004, NFR-005.
- **Affected surfaces**: `src/charter/activation/kind_vocabulary.py` (`resolve_artifact_urn`, `resolve_config_id`, `resolve_selected_id_to_stem`), `src/charter/activation/identity_index.py` (`from_roots`, `_scan`).
- **Sequencing/depends-on**: none — this is the first change.
- **Risks**: import cycle (`identity_index` already imports `kind_vocabulary`), so the dependency is a function-local import; the index's fast-id read path differs from the full parse for malformed YAML (documented accepted limitation) and the facade must inherit that, not restore the second reader; `UnrepresentableDirectiveIdError` must still be raised for a directive declared id that no filename represents, while compile keeps accepting it.

### IC-02 — Cascade-source surfaces share one index

- **Purpose**: a token the write path accepts must reach the same DRG node the stem reaches, so the cascade and its safety reports never silently disappear.
- **Relevant requirements**: FR-004, FR-005, FR-006; C-001.
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/activate.py`, `deactivate.py`, `_resynthesis_preflight.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: `_active_urns` resolves every active token in a loop — building an index per token would be a scan regression (NFR-004), so one index is built per command and threaded; `_source_urn` returning `None` is a documented no-op contract (unknown token) and must stay `None` rather than raising.

### IC-03 — Pins, docs and changelog

- **Purpose**: state the new authority in tests and docs so a future refactor cannot reintroduce a second rule or change an unknown-token policy unnoticed.
- **Relevant requirements**: FR-007, FR-009; SC-001..SC-004.
- **Affected surfaces**: `tests/charter/activation/test_identity_single_authority_6433.py`, `tests/specify_cli/cli/commands/charter/test_cascade_identity_6433.py`, `docs/architecture/activation-ledger-and-charter-contract.md`, `docs/changelog/CHANGELOG.md`.
- **Sequencing/depends-on**: IC-01, IC-02.
- **Risks**: the parity test must exercise all three layers (built-in, org, project) or it proves nothing about precedence; the CLI test must assert the positive control (the by-stem run) on the same fixture, not just the new spelling.

## Complexity Tracking

No charter violations; no entry needed.
