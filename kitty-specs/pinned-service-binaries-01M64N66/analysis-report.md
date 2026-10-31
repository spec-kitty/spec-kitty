---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: pinned-service-binaries-01M64N66
mission_id: 01M64N66GS3NT6K1W89PTC28AS
generated_at: '2026-10-29T21:54:48.602308+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/pinned-service-binaries-01M64N66/spec.md
    sha256: 821dd5a745b913ce5fce178ae86592f4c7049a9e75debbab5a7aa58a1be4e8f7
  plan.md:
    path: kitty-specs/pinned-service-binaries-01M64N66/plan.md
    sha256: 41afa4da631b32fa8f5f91df07709a743d613b45cf89905a3a1e6f0268ed03dc
  tasks.md:
    path: kitty-specs/pinned-service-binaries-01M64N66/tasks.md
    sha256: 2664d21c9254657435e0471d72e86d987ceafe5614f5c0a16a2c2d67f11beed2
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 4
  low: 3
  critical: 0
  high: 0
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: 'Where installed pins live is split: WP03 implements find_pin (importlib.resources) while WP06 picks the wheel location; WP03 runs first.'
- id: U1
  severity: medium
  category: underspecification
  summary: protocol_versions has no release-metadata source; vendor takes it from a flag defaulting to 1, so a pin can record versions the build does not serve.
- id: E1
  severity: medium
  category: coverage
  summary: NFR-001 (warm path <=150 ms p95) is verified only by a timing-marked test that runs in the serial timing pass, not per PR.
- id: E2
  severity: medium
  category: coverage
  summary: NFR-006 (Windows) has no WP subtask that wires the launcher tests into the Windows lane; WP04 only notes the marker question.
- id: E3
  severity: low
  category: coverage
  summary: SC-003 (reads work with no binary) has no dedicated test; it holds by construction (reads never import the launcher) but nothing pins it.
- id: C1
  severity: low
  category: coverage
  summary: ADR D-6 read-service CI pin and its conformance job are not in this mission; they need the first release and belong to the cut-over, which is not stated in spec C-005.
- id: F1
  severity: low
  category: inconsistency
  summary: FR-010 is delivered by WP02 (asset directory) and WP05 (fetch command) but mapped only to WP02.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | WP03 Context (find_pin), WP06 Context (wheel pins) | The installed-pin location is decided in WP06 but consumed by WP03, which lands first. | WP03 fixes the location (`specify_cli/_pins` via force-include) and WP06 implements the packaging to match; the reviewer checks both use the same constant. |
| U1 | Underspecification | MEDIUM | WP05 Context (protocol_versions), contracts/service-pin.schema.md | Vendor cannot derive protocol versions from a release. | Keep the flag, but have the launcher treat a handshake protocol list that disagrees with the pin as `SERVICE_VERSION_MISMATCH` (already in WP04), and ask spec-kitty-events to publish a manifest. Track it as a follow-up. |
| E1 | Coverage | MEDIUM | spec NFR-001, WP04 T021 | The latency check runs only in the timing pass. | Acceptable: per-PR runs stay deterministic. Note in the PR that NFR-001 is verified in the timing pass, and record the local measurement. |
| E2 | Coverage | MEDIUM | spec NFR-006, WP04 Risks | Windows coverage depends on lane selection by marker. | WP04 checks `ci-windows.yml` and marks the portable launcher tests for the Windows lane, or records the gap in the PR. |
| E3 | Coverage | LOW | spec SC-003 | No explicit test. | Optional: an import-graph assertion that the status read path does not import `specify_cli.services`. |
| C1 | Coverage | LOW | ADR D-6, spec C-005 | The read-service pin is deferred. | Name it in the PR's Deferred section, for the cut-over. |
| F1 | Inconsistency | LOW | tasks.md WP05 | FR-010 is mapped only to WP02. | Cosmetic; WP05's prompt already cites FR-010. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 pin lockfile | yes | T001–T004 | |
| FR-002 verified fetch/cache | yes | T006, T009 | |
| FR-003 single download owner | yes | T005, T010 | gate starts with an empty allowlist |
| FR-004 resolution order | yes | T013, T015 | |
| FR-005 fail-closed refusals | yes | T011, T015, T021 | |
| FR-006 launch-when-down/reuse | yes | T019, T021 | |
| FR-007 health + identity | yes | T017, T019, T021 | |
| FR-008 stale recovery | yes | T020, T021 | |
| FR-009 explicit stop | yes | T020, T023 | |
| FR-010 pre-fetch + asset dir | yes | T007, T023 | F1 |
| FR-011 unpinned opt-in | yes | T014, T015 | |
| FR-012 sync command + action | yes | T026, T027 | |
| FR-013 vendor + pin gate | yes | T022, T025 | the CI pin-gate job waits for the first pin (R-7) |
| FR-014 no binary in wheel/sdist | yes | T028 | |
| NFR-001..007 | yes | T021, T019, T013, T005, T019, T021, all | E1, E2 |
| C-001..C-007 | yes | across WPs | |

**Charter Alignment Issues:** none.
- Layering kernel ← specify_cli is respected.
- The new gate starts empty, with a floor and a planted self-test (SO #5).
- ATDD: acceptance tests per user story.
- Loopback HTTP is kept on purpose.
- "sync" appears only in names that mirror packs.

**Unmapped Tasks:** none (T030, docs/changelog, supports NFR-007 and C-002).

**Metrics:**
- Total requirements: 14 FR, 7 NFR, 7 C, 5 SC
- Total tasks: 30
- Coverage: 100% of FRs have ≥1 task
- Ambiguity count: 1 (U1)
- Duplication count: 0
- Critical issues: 0

## Next Actions
- No critical or high findings; implementation may proceed.
- Fold I1 into the WP03 implementation (pick the location there) and E2 into WP04.
- Record U1 and C1 as PR deferrals and follow-ups.
