# Implementation Plan: CI speed and verdict hardening

**Branch**: `ci/speed-and-verdict-hardening` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

## Summary

Implement the operator-approved review through four disjoint implementation concerns and an integration pass. Keep the existing selection authority, collection-policy validator, source pins and required check names. Replace repeated work rather than weaken verification. The PR remains draft and the operator owns merge.

## Technical Context

- **Language/Version**: Python 3.11+, GitHub Actions YAML and Bash.
- **Primary Dependencies**: pytest, uv/uv.lock, pinned Actions cache/checkout/setup actions.
- **Storage**: Actions caches and existing committed timing JSON.
- **Testing**: Actual shipped shard-shell execution with failing fake pytest, real temporary git diffs, content-key invalidation tests, source-mutation guard controls, selector/capture fidelity and focused workflow graph tests.
- **Target Platform**: Linux PR checks, Windows installation checks and three-platform nightly acceptance tooling.
- **Performance Goals**: Remove identified duplicated scans/jobs/checkout by construction; expose policy scan hit/miss and phase durations. No unmeasured percentage or runner-quota claim.
- **Constraints**: No mutable repository sharing, unchecked policy skips, narrowed coverage, full heavy local sweep or mainline merge.
- **Scale/Scope**: Existing 20-module/40-shard registry, code/test infrastructure and workflow integration only.

## Charter Check

- Read the active charter and resolved action/profile context before implementation.
- ATDD: committed executable workflow regressions before fixing the false-green and duplicate-job behavior; retain red/green logs.
- Keep a single canonical selector and validator; cache candidates are still validated against actual source content and authentication.
- Independent review checks aggregate changes; all delegated implementation uses the operator-named model.
- Baseline test policy uses make test-fast with bounded auto workers plus affected files and named architectural gates, never a full heavy suite.
- No product module seam, package inventory, public CLI flag or version change.

## Project Structure

### Documentation (this Mission)

`spec.md`, `plan.md`, `reasons-canvas.md`, and `tooling-friction.md`, `approach.md`, `design-decisions.md` track intent, boundaries and observed deviations. Validation evidence belongs in the PR and the implementation notes, not invented Mission verdicts.

### Source Code (repository root)

- `.github/workflows/`: workflow graph, stable checks, caching, source provenance and observability.
- `.github/actions/`: early pack restore, truthful environment setup, asset-class-specific service caches and validated policy-cache candidates.
- `scripts/ci/`: node-identity timings, conservative packaging selection and pinned tooling/provenance helpers.
- `tests/ci/`, `tests/release/`, `tests/architectural/`: focused regression and contract tests.
- `tests/charter/conftest.py`: narrow repository setup without weakening real repository consumers.
- `tests/_support/wall_clock_assertions.py`: preserve the policy guard and expose scan/cache timing.

**Structure Decision**: Extend existing infrastructure owners. No new orchestration framework or parallel CI authority.

## Complexity Tracking

The scope spans several CI domains because the operator explicitly requested all review fixes. Capacity changes requiring fresh run evidence (extra consolidation shards, debounce, cache deletion, WIP policy changes) are not silently substituted for implementation. Record their disposition explicitly.

## Implementation Concern Map

### IC-01 — Immutable test facts and fixture setup

- **Purpose**: Avoid repeated parsing and accidental repository initialization.
- **Relevant requirements**: FR-003, FR-009; NFR-001.
- **Affected surfaces**: Named architectural guards, charter fixture and focused tests.
- **Sequencing/depends-on**: None; integration preserves mutation controls.
- **Risks**: Mutable scratch probes must never inherit stale repository facts.

### IC-02 — Measurement identity

- **Purpose**: Associate timing data with exact collected tests, not array positions.
- **Relevant requirements**: FR-008, FR-011; SC-002.
- **Affected surfaces**: Existing selector/capture/recapture and timing consumers.
- **Sequencing/depends-on**: None; integrate backward compatibility explicitly.
- **Risks**: Legacy arrays lack identities and cannot be relabeled honestly; capture completeness and test failures need explicit provenance.

### IC-03 — Cache and tooling inputs

- **Purpose**: Restore useful material before build hooks, and distinguish environment/runtime/asset identities.
- **Relevant requirements**: FR-005, FR-006, FR-007, FR-013.
- **Affected surfaces**: Composite actions, workflow setup and tooling helpers.
- **Sequencing/depends-on**: Action interfaces precede parent workflow wiring.
- **Risks**: Cached interpreter links, untrusted PR scope, full versus frozen resolution, cross-platform assets and tool checksum integrity.

### IC-04 — Truthful gates and complete handoff

- **Purpose**: Correct full-mode statuses/provenance, consolidate checks, cancel stale work and scope only proven non-input prose.
- **Relevant requirements**: FR-001, FR-002, FR-004, FR-010, FR-012, FR-014.
- **Affected surfaces**: Router/quality/modules/aggregate/Windows/Sonar workflows and targeted contracts.
- **Sequencing/depends-on**: Integrates IC-01 through IC-03 before aggregate review.
- **Risks**: Required names, label pause events, uncertain diffs and no-evidence coverage must remain fail-closed.
