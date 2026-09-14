# Tasks: Charter directive-resolution hardening

**Mission**: charter-directive-resolution-hardening-01M29022
**Issues**: #4239, #4240 (epic #2519) — deferred from #4194/#4185
**Branch**: fix/charter-directive-resolution-hardening → PR targets `main`

Two independent, outcome-preserving WPs on disjoint files. Both may run in parallel.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Memoize `_iter_artifact_paths` per-layer scan keyed on `(path, mtime)` (or pass-scoped), preserving high→low ordering | WP01 | [P] |
| T002 | Route the memo through `resolve_config_id`'s per-stem `resolve_artifact_urn` round-trip so repeated stems reuse the scan | WP01 | [P] |
| T003 | Add a counted-scan seam + test: ≤1 scan per layer per resolution pass, and mtime-correct invalidation across passes | WP01 | [P] |
| T004 | Verify no resolution-outcome change (tests/charter/ subset) + ruff/format/mypy clean, complexity ≤15 | WP01 | [P] |
| T005 | Emit a per-token `logging` WARNING (raw token + normalized form) ONLY on the fully-unresolvable fallback in `resolver.directives` | WP02 | [P] |
| T006 | Add a `caplog` test: warns on unresolvable token; silent when token resolves by stem / exact id / known catalog id | WP02 | [P] |
| T007 | Verify resolution outcome unchanged + ruff/format/mypy clean, complexity ≤15 | WP02 | [P] |

## Work Packages

### WP01 — Memoize directive resolver filesystem scans (#4239)

- **Goal**: One filesystem scan per doctrine layer per directive resolution pass, down from up-to layers×stems. No resolution-outcome change; single overlay-precedence authority preserved.
- **Priority**: P1
- **Independent test**: a scan-count seam asserts ≤1 scan/layer/pass on a multi-layer fixture; existing `tests/charter/test_directive_identity_mapping.py` stays green.
- **Requirements**: FR-001, FR-002, NFR-001, NFR-002, NFR-003, C-001, C-002
- **Included subtasks**:
  T001 Memoize the per-layer scan (WP01)
  T002 Route memo through the round-trip (WP01)
  T003 Scan-count + mtime-invalidation test (WP01)
  T004 Verify no outcome change + quality gates (WP01)
- **Prompt**: `tasks/WP01-memoize-directive-resolver-scans.md`
- **Dependencies**: none

### WP02 — Diagnostic for a silently-normalized unresolvable token (#4240)

- **Goal**: Surface a per-token WARNING when `resolver.directives` best-effort normalizes a fully-unresolvable activation token, without changing the resolution result.
- **Priority**: P1
- **Independent test**: `caplog` asserts a warning on an unresolvable token and none on a resolvable one; delivered directives unchanged.
- **Requirements**: FR-003, FR-004, NFR-002, NFR-003, C-001, C-003
- **Included subtasks**:
  T005 Emit the per-token WARNING on the unresolved fallback (WP02)
  T006 caplog test: warn-on-unresolved / silent-on-resolved (WP02)
  T007 Verify no outcome change + quality gates (WP02)
- **Prompt**: `tasks/WP02-unresolvable-token-warning.md`
- **Dependencies**: none

## MVP

Both WPs are small and independent; WP01 is the higher-value (perf on the hot resolution path). Either can land first.
