---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: charter-offering-surface-freeze-01M6BTTR
mission_id: 01M6BTTR4SQZ6AWY9G8TS4Y0V5
generated_at: '2026-11-01T17:35:10.558415+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/charter-offering-surface-freeze-01M6BTTR/spec.md
    sha256: 0631895de68ff8710884c8c6d32b922f9885679863d0e941a89d74ca4074f9a9
  plan.md:
    path: kitty-specs/charter-offering-surface-freeze-01M6BTTR/plan.md
    sha256: 58536d8c66f4b409461971dbddbcf4e1ec4afbdca675a88a4a8f30bccb74f069
  tasks.md:
    path: kitty-specs/charter-offering-surface-freeze-01M6BTTR/tasks.md
    sha256: 523d465d7e50fb0ddeaaa378f53975392288a469488a73177a0d40aaed04c5a2
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  critical: 0
  low: 3
  high: 0
  medium: 0
  info: 0
findings:
- id: A1
  severity: low
  category: coverage
  summary: NFR-003 (ruff/mypy clean, complexity <= 15) is not named in any WP requirement_refs, though T006 and T009 run the commands.
- id: A2
  severity: low
  category: duplication
  summary: FR-003's facade-set check overlaps the existing strict coverage assertion in the same gate file.
- id: A3
  severity: low
  category: ambiguity
  summary: FR-002 says the census must match api.__all__ 'in order' without naming which order; plan T002 fixes it to api.__all__ order (which the gate already asserts is sorted).
---

## Specification Analysis Report

Re-run after two WP01-driven planning amendments: NFR-001's gate-cost bar was
raised from 2.0 s to 8.0 s to match the measured cost of the single authoritative
reached-path scan (a faster second scanner would be a forbidden second source of
truth), and `research.md` D-004 was corrected from `_FACADE_TABLE` to the facade
modules' own `from charter.offering.api import …` statements, because the table
keys `charter.languages`' `LANGUAGE_TOKENS` row to its origin submodule and would
have produced a false facade gap. Neither amendment loosens a gate: the first is a
performance bound on a test, the second is a provenance correction.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | LOW | spec.md NFR-003; tasks.md WP01/WP02 | NFR-003 has no `requirement_refs` owner. The evidence exists operationally: T006 runs `ruff` on the gate file and T009 runs `ruff` + `mypy` on `api.py`; complexity is trivially 1 for the changed functions. | Accept as-is: metadata-only gap with the command coverage already in the WP subtasks. |
| A2 | Duplication | LOW | spec.md FR-003; test_charter_offering_public_surface.py T007 | FR-003 pins each row's facade set; the existing strict T007 assertion already pins *coverage*. Complementary (record vs coverage), sharing one authority (the facade imports), so there are not two competing sources. | Keep both; NFR-004 forbids a second gate file. |
| A3 | Ambiguity | LOW | spec.md FR-002, US1 AS1 | "in order" does not state the order. `api.__all__` is asserted sorted, and plan T002 says "in the same order" as `__all__`, so both readings coincide. | No edit needed; the WP prompt states it. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | Yes | T002 | Census file with 12 rows |
| FR-002 | Yes | T001, T002, T005 | Pin + mutation proof |
| FR-003 | Yes | T004, T005 | Facade set from facade imports |
| FR-004 | Yes | T002, T005 | Per-row annotations + `final` rejection |
| FR-005 | Yes | T003, T005 | Classification + delta |
| FR-006 | Yes | T007 | C-003 reword |
| FR-007 | Yes | T006 | No-import-activation gate run unmodified |
| FR-008 | Yes | T008, T009 | README section + changelog |
| NFR-001 | Yes | T006 | Timing recorded |
| NFR-002 | Yes | T002, T003 | Committed file, live scan, no network |
| NFR-003 | Partial | T006, T009 | Commands present; no requirement_refs owner (A1) |
| NFR-004 | Yes | T001, T004 | Additive checks in the owning gate |
| C-001 | Yes | (all) | No `src/charter/offering` file created or moved |
| C-002 | Yes | T001, T005 | Additive assertions, no skip/xfail |
| C-003 | Yes | T003 | Delta asserted empty |
| C-004 | Yes | T007 | #6218 consumed, not closed |
| SC-001 | Yes | T001, T005 | |
| SC-002 | Yes | T002, T005 | |
| SC-003 | Yes | T003, T005 | |
| SC-004 | Yes | T006, T009 | |

**Charter Alignment Issues:** none. Single canonical authority is honoured (one census; the disposition manifest referenced, not restated); no layering or import-direction change; no allowlist or baseline added.

**Unmapped Tasks:** none. Every T001-T009 rolls into WP01 or WP02.

**Metrics:**

- Total Requirements: 20 (8 FR, 4 NFR, 4 C, 4 SC)
- Total Tasks: 9
- Coverage %: 100% of FR/SC covered by at least one task; NFR-003 covered by commands but not by metadata (A1)
- Ambiguity Count: 1 (A3, resolved in the WP prompt)
- Duplication Count: 1 (A2, complementary and deliberately shared)
- Critical Issues Count: 0
