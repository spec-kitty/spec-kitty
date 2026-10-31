---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: companion-services-wheel-01M694B1
mission_id: 01M694B16SZNKYDDB6WFSFBJSX
generated_at: '2026-10-31T14:12:30.598264+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/companion-services-wheel-01M694B1/spec.md
    sha256: dd3317dc2e9f836069ec48bfd3f41083d137e17b948248a106215000126d6cd0
  plan.md:
    path: kitty-specs/companion-services-wheel-01M694B1/plan.md
    sha256: aee1f02b13ae54f24aa742503a93768d252e1da1a2511eaa9e2600b74f6b8e77
  tasks.md:
    path: kitty-specs/companion-services-wheel-01M694B1/tasks.md
    sha256: 2f8b43767deb4c1363c6f665e7dc420ea6d1c6c93bf9ef6c6583a9e18e3fec39
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 3
  low: 3
  critical: 0
  high: 0
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: NFR-004 (ruff/format/mypy clean) is mapped only to WP06, but it binds every code WP.
- id: C2
  severity: medium
  category: coverage
  summary: The spec edge case 'a native target pinned for one service but not the other' has no explicit WP03 test.
- id: U1
  severity: medium
  category: underspecification
  summary: WP06 T021 leaves the companion job's tooling install (uv sync scope, twine) loosely specified.
- id: A1
  severity: low
  category: ambiguity
  summary: WP01 T001 carries a self-answered aside about the ADR frontmatter ('Also update ...? No').
- id: A2
  severity: low
  category: ambiguity
  summary: The macosx_11_0_arm64 floor is the usual Apple Silicon floor but is not sourced (research note §2).
- id: D1
  severity: low
  category: duplication
  summary: FR-010 is split across WP03 (companion half) and WP04 (main-wheel half); intentional, but both must be reviewed together.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | spec.md NFR-004; tasks WP02–WP06 | NFR-004 mapped only to WP06 | Treat it as a Definition-of-Done item for every code WP; the reviewer checks ruff/format/mypy per WP |
| C2 | Coverage | MEDIUM | spec.md Edge Cases; WP03 T008 | Asymmetric per-target pins not tested | Add a WP03 test: charter-service pins linux-x64 only; the linux-arm64 wheel carries write-service alone |
| U1 | Underspecification | MEDIUM | WP06 T021 | Companion job tooling install loosely specified | Implement with `uv sync --frozen --no-install-project` + `PYTHONPATH=src`, and `pip install twine==6.2.0` as build-release does |
| A1 | Ambiguity | LOW | WP01 T001 | Self-answered aside | Ignore; append-only amendment |
| A2 | Ambiguity | LOW | data-model.md, FR-006 | macOS tag floor unsourced | Accept 11.0 (first Apple Silicon macOS); note it in the ADR amendment |
| D1 | Duplication | LOW | FR-010; WP03, WP04 | Split requirement | Review WP03 and WP04 together |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 adr-amendment | Yes | T001–T003 | |
| FR-002 companion-package | Yes | T004–T007 | |
| FR-003 version-skew-guard | Yes | T004, T006 | |
| FR-004 build-from-pinned-assets | Yes | T008, T009 | |
| FR-005 read-service-excluded | Yes | T008 | |
| FR-006 honest-tags | Yes | T004, T005, T008 | |
| FR-007 size-gate | Yes | T008, T010 | |
| FR-008 services-extra | Yes | T012, T013 | |
| FR-009 release-pipeline | Yes | T019, T021 | |
| FR-010 packaging-guard | Yes | T010, T015 | split (D1) |
| FR-011 resolution-ratchet | Yes | T016–T018, T011 | |
| FR-012 release-checks-checklist | Yes | T020, T022 | |
| NFR-001 reproducible | Yes | T004, T008 | |
| NFR-002 fast-tests | Yes | T008 | |
| NFR-003 digest-integrity | Yes | T010, T015 | |
| NFR-004 code-quality | Partial | WP06 | C1 |

**Charter Alignment Issues:** none. The `[tool.uv.sources]` tension with CLAUDE.md was ruled (Decision Moment 01M694GPQYVGRKCF3B582FWQ1Y) and is recorded in plan Complexity Tracking; WP01 T002 adds the clarification. D-9 frozen paths are untouched (C-002).

**Unmapped Tasks:** none.

**Metrics:** 12 FR + 4 NFR + 7 C; 22 tasks; coverage 100% (NFR-004 partial); ambiguity 2; duplication 1; critical 0.

### Next Actions

No CRITICAL or HIGH findings: proceed to implementation. Fold C1, C2 and U1 during WP02/WP03/WP06 implementation (no planning-artifact edit needed).
