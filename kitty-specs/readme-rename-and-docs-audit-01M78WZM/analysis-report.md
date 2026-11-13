---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: readme-rename-and-docs-audit-01M78WZM
mission_id: 01M78WZM48VJHP4HJVHKG2FDBN
generated_at: '2026-11-13T01:10:19.399925+00:00'
analyzer_agent: claude
input_artifacts:
  spec.md:
    path: kitty-specs/readme-rename-and-docs-audit-01M78WZM/spec.md
    sha256: fc56177c188dbfcc768c6fbcf33e1921ea38debf26f3e7af0c6a914cc6fdfa85
  plan.md:
    path: kitty-specs/readme-rename-and-docs-audit-01M78WZM/plan.md
    sha256: 71175e9ebce321754f0efb5ea24743d9f41d8d91102630ef21e80f1f7d8fdb32
  tasks.md:
    path: kitty-specs/readme-rename-and-docs-audit-01M78WZM/tasks.md
    sha256: 60affbd82574f8d9d2b791ba7dd8f3fa3c2abea3011ed6ee53136622ff4d3b28
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: unknown
issue_counts:
  high:
  medium:
  low:
  critical:
  info:
findings: []
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| R1 | Risk | MEDIUM | plan.md D-2 | The ledger's return rule changes `collapse` semantics: a later move back into a route supersedes the earlier move away. Eight folders need it (#3914, #6928 moved them README -> index). | Pin it with a unit test (return, self-loop still refused) and record it in the ADR amendment. |
| R2 | Risk | MEDIUM | plan.md D-7 | Moving the retired lists out of `test_no_retired_subsystems.py` touches an enforcement gate other tests import (`_p1_census_oracle`, `test_p1_planted_regression`). | Keep the old module-level names bound in the test; run the P1 gates in the blast radius. |
| R3 | Risk | LOW | spec.md Context | The issue counts 60 files; 59 remain because `docs/templates/index.md` left with #6943. | State it in the PR and the ADR amendment. |
| R4 | Risk | LOW | plan.md D-5 | `check_docs_freshness --ci` reports the bot-owned inventory's lag as warnings; a gate red only for that is named in the PR, never weakened. | PR body. |
| A1 | Ambiguity | LOW | spec.md FR-009 | "Text-drawn diagram" and "mixed Divio type" are heuristics. | Label them as hints in the inventory, with the rule stated. |
| C1 | Coverage | LOW | spec.md SC-002 | Built-site redirect coverage needs `make docs-site` (Docker). | Run when Docker is available; otherwise say so and rely on `site_redirects --check` plus CI's docs-site job. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 | yes | WP01 (T002) | |
| FR-002 | yes | WP01 (T001) | planted control |
| FR-003 | yes | WP01 (T001, T003) | |
| FR-004 | yes | WP01 (T005) | |
| FR-005 | yes | WP01 (T004) | |
| FR-006 | yes | WP01 (T006) | |
| FR-007 | yes | WP01 (T004) | map unchanged |
| FR-008 | yes | WP01 (T006) | |
| FR-009 | yes | WP02 (T008, T010) | |
| FR-010 | yes | WP02 (T009) | |
| FR-011 | yes | WP02 (T008, T011) | |
| FR-012 | yes | WP02 (T011) | ratchet |
| FR-013 | yes | WP02 (T012) | |
| FR-014 | yes | WP02 (T013) | |
| FR-015 | yes | WP01 (T007), WP02 (T013) | |
| NFR-001..005 | yes | WP01, WP02 | |
| C-001..C-005 | yes | WP01, WP02 | |

**Charter Alignment Issues:** none. Red-first tests open each WP; the retired set gets one authority; the new allowlist is size-ratcheted in `_baselines.yaml` and tied to issues. The charter's tracker-assignment rule is overridden by the operator's brief (do not change #6939's assignee); recorded in the plan.

**Plan revision (WP02):** D-6 now records that `check_docs_freshness.py` is not extended; no requirement or task changes.

**Unmapped Tasks:** none.
