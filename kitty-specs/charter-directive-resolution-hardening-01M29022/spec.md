# Mission Specification: Charter directive-resolution hardening

**Mission**: charter-directive-resolution-hardening-01M29022
**Issues**: #4239 (memoize resolver scans), #4240 (unresolvable-token diagnostic) — epic #2519
**Origin**: deferred robustness items from the #4194/#4185 landing.

## Intent Summary

Two internal robustness improvements to the charter **directive** resolution path,
neither of which changes what any resolution returns:

1. **Performance (#4239):** collapse repeated per-stem filesystem globbing during a
   single directive resolution so each doctrine layer is walked once, not once per
   candidate stem.
2. **Observability (#4240):** when the delivered directives service best-effort
   normalizes a *fully unresolvable* activation token, emit a per-token warning so a
   stale or mistyped `activated_directives` entry surfaces instead of resolving
   silently.

Primary actor: the operator/agent host that runs `spec-kitty charter generate` /
`interview` / `activate` (and the delivered `DoctrineService.directives`). Trigger:
directive resolution over an org/project doctrine layout. Desired outcome: same
resolution result, less repeated I/O, and a visible signal on an unresolved token.
Invariant that must always hold: the single overlay-precedence authority
(`_iter_artifact_paths` high→low order) remains the sole ordering, and no resolution
outcome changes.

Discovery was minimized per operator direction ("scale to the small work"); the
issues and steer are a complete prescriptive brief. Assumptions are recorded below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Directive resolution avoids redundant filesystem scans (Priority: P1)

An operator activates several org-pack directives and runs charter compile /
interview. Resolution reads each doctrine layer's directory once per resolution pass
rather than re-globbing every layer once per activated stem. The resolved directive
set is identical to before.

**Acceptance**: for a fixture with D directives across L layers, a single resolution
pass performs at most one filesystem scan per layer (asserted via a counted scan
seam); the resolved result is byte-for-byte identical to the pre-change result.

### User Story 2 - A stale activation entry is no longer silent (Priority: P1)

An operator's `activated_directives` contains a token that names no real directive
(a typo, or a directive removed from the pack). Today the delivered service
best-effort normalizes it and may co-activate an unrelated directive with no signal.
After this mission, the service emits a per-token warning naming the token and the
normalized form it fell back to, so the operator can spot and fix the stale entry.

**Acceptance**: a fully-unresolvable activated directive token produces a WARNING
that names the token and its normalized form; a token that resolves (by filename
stem, exact declared id, or a known catalog id) produces no warning; the set of
delivered directives is unchanged in both cases.

### Edge Cases

- A token that resolves normally by stem or exact id: no warning, no extra scan work
  beyond the single-pass minimum.
- A layer directory that does not exist on disk: scanned/absent handling is unchanged;
  memoization must not turn an absent layer into a spurious hit.
- Files changed on disk between two resolution passes (different service instances):
  a later pass must observe the new content (mtime-correct invalidation, or a
  cache scoped so a new pass cannot see stale content).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-001 | Directive resolution in `kind_vocabulary` memoizes each doctrine layer's artifact-path scan (and/or the stem→id map) so a single resolution pass walks each layer's filesystem at most once, instead of re-globbing per candidate stem. | Proposed |
| FR-002 | The memoization invalidates correctly when a scanned path changes: a resolution performed after an on-disk change observes the new content (keyed on `(path, mtime)`, or scoped so a fresh resolution cannot reuse stale content). | Proposed |
| FR-003 | The delivered `resolver.directives` property emits a per-token WARNING when it falls back to `normalize_directive_id` for a **fully unresolvable** activation token, naming both the raw token and the normalized form it used. | Proposed |
| FR-004 | The warning of FR-003 fires **only** on the fully-unresolvable fallback path; a token that resolves via filename stem, exact declared id, or an existing catalog id emits nothing. | Proposed |

### Non-Functional Requirements

| ID | Requirement | Threshold / Measure | Status |
|----|-------------|---------------------|--------|
| NFR-001 | Reduced filesystem work per resolution pass. | ≤ 1 layer scan per doctrine layer per single directive resolution pass (asserted by a counted scan seam in a test). | Proposed |
| NFR-002 | No resolution-outcome change. | The full `tests/charter/` suite passes unchanged (2850+ passed at mission start); resolved directive sets are identical pre/post. | Proposed |
| NFR-003 | Code quality. | New code passes `ruff`/`ruff format`/`mypy` with zero issues; per-function cyclomatic complexity ≤ 15; every new branch/helper has a focused test in the same commit. | Proposed |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | Resolution behavior/outcomes MUST NOT change — this mission is perf + observability only. | Active |
| C-002 | The single overlay-precedence authority (`_iter_artifact_paths` high→low order) remains the sole ordering; memoization MUST NOT introduce a second ordering or precedence path. | Active |
| C-003 | The FR-003 warning MUST NOT change the resolution result (it is a signal, not a gate); the best-effort legacy-compat fallback is preserved. | Active |

### Key Entities

- **Directive activation token** — an entry in `activated_directives` (a filename stem, an exact declared id, or a stale/typo'd value).
- **Doctrine layer scan** — the per-layer artifact-path enumeration produced by `_iter_artifact_paths` (built-in / org packs / project overlay), the unit being memoized.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- A single directive resolution pass over an N-layer doctrine layout performs at most N filesystem layer-scans (down from up-to N×stems), verified by a scan-count test.
- An operator with a stale/mistyped directive activation entry sees a warning naming the token on the next resolution, where previously they saw nothing.
- Zero change to resolved directive sets: the existing `tests/charter/` suite passes unchanged, plus new tests pinning the scan-count and the warning-only-on-unresolved behavior.
