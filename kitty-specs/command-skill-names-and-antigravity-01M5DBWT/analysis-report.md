---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: command-skill-names-and-antigravity-01M5DBWT
mission_id: 01M5DBWTRXZQ3ZJWGKX0KES8JP
generated_at: '2026-10-21T05:22:14.491208+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/command-skill-names-and-antigravity-01M5DBWT/spec.md
    sha256: 235868b5e2c395db6f32e0003d02bcc214d9aadd42e6917096ab8368cfdfb324
  plan.md:
    path: kitty-specs/command-skill-names-and-antigravity-01M5DBWT/plan.md
    sha256: a5d92ead8ff654b93aae63d3bf867cd210eb61215f48d2c49d0733b6aad7cc21
  tasks.md:
    path: kitty-specs/command-skill-names-and-antigravity-01M5DBWT/tasks.md
    sha256: 24d4e43e5a72ca6b5798be28e604d8033d469c11d152e202a27a9b2656ed5fd9
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 2efd56dd3a968d08fa0b764f7e554d4d64963b46707d77c06c3d4cc7957636a0
verdict: ready
issue_counts:
  low: 3
  high: 0
  medium: 2
  critical: 0
  info: 0
findings:
- id: C1
  severity: low
  category: coverage
  summary: SC-002 and SC-003 are not listed in any WP requirement_refs (covered in substance by WP05/WP06 and WP04 tests).
- id: F1
  severity: medium
  category: inconsistency
  summary: plan.md concern text (IC-01..IC-06) predates the post-plan dispositions table; the table overrides it, which an implementer must read in that order.
- id: U1
  severity: medium
  category: underspecification
  summary: Several WPs need small out-of-map edits (WP05 -> init.py, order_manifest.txt, _command_surface_doctor.py; WP07 -> command_renderer.py, command_installer.py; WP06 -> agent/config.py); allowed by ownership-map leeway but must be recorded.
- id: U2
  severity: low
  category: underspecification
  summary: p0_repro marker removal is assigned in WP01/WP06/WP07 prompts but not in tasks.md subtask rows.
- id: A1
  severity: low
  category: ambiguity
  summary: WP03 T010 leaves the classification of a directory or symlink at a canonical path (collision vs preserve) to the implementer with a trace record.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | LOW | spec.md SC-002/SC-003; tasks/WP04, WP05, WP06 | SC-002/SC-003 unreferenced in requirement_refs | Reference SC-002 in WP05/WP06 and SC-003 in WP04 on the next refinalize; tests already target them |
| F1 | Inconsistency | MEDIUM | plan.md IC map vs "Post-plan squad dispositions" | Two layers of plan text | Every WP prompt already says the dispositions table overrides; reviewers check against it |
| U1 | Underspecification | MEDIUM | WP05, WP06, WP07 prompts | Out-of-map edits | Record each with a one-line rationale in the commit body (ownership-map leeway, single-branch sequential execution) |
| U2 | Underspecification | LOW | tasks.md WP06/WP07 | Marker removal not a subtask row | Follow the WP prompts; reviewer checks the markers are gone at WP06/WP07 |
| A1 | Ambiguity | LOW | WP03 T010 | Dir/symlink at canonical path | Conservative default (preserve) + trace entry |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 names | yes | T001,T004,T006,T009 | |
| FR-002 one authority | yes | T004,T008 | |
| FR-003 uniqueness | yes | T005 | |
| FR-004 ownership by set | yes | T011 | |
| FR-005 migration | yes | T015,T016 | |
| FR-006 notice | yes | T012,T017,T036 | |
| FR-007 doctor legacy | yes | T013 | |
| FR-008 antigravity skills | yes | T002,T018,T021 | |
| FR-009 no project workflows | yes | T021 | ratchet guard |
| FR-010 archive migration | yes | T020 | |
| FR-011 home writer | yes | T022-T024 | |
| FR-012/013 frontmatter | yes | T026-T028 | |
| FR-014 limits | yes | T029 | |
| FR-015 CI validator | yes | T031-T033 | |
| FR-016 prompts/open-packs | yes | T006,T037,T038 | |
| FR-017 legacy names | yes | T004 | |
| FR-018 docs/ADR | yes | T034,T035 | |
| FR-019 collision | yes | T010,T014 | |
| FR-020 every repair path | yes | T009,T014 | |
| NFR-001..005 | yes | T014,T016,T020,T023,T025,T030 | |

**Charter Alignment Issues:** none (single authority, ownership proof, red-first, ledger rules, upstream pack source, targeted tests all planned).

**Unmapped Tasks:** none.

**Metrics:** 20 FR + 5 NFR + 6 C + 4 SC; 38 subtasks; FR coverage 100%; ambiguity 1; duplication 0; critical 0.

**Re-run 2026-10-21:** spec.md US2 scenario 3 now reflects the operator ruling (unrecorded dotted folder removed only when byte-identical to Spec Kitty's render; otherwise kept with a warning). Implemented in the installer (WP03 surface, via WP04 rework); no new findings, coverage unchanged.

### Next Actions

No critical or high findings; proceed to implementation. C1/U2 can be folded at the next refinalize; F1/U1 are handled by reviewer guidance.
