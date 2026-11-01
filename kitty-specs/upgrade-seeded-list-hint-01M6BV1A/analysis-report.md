---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: upgrade-seeded-list-hint-01M6BV1A
mission_id: 01M6BV1AF5CJVJC7MQAVQN9C0M
generated_at: '2026-11-01T15:20:56.953263+00:00'
analyzer_agent: planner-priti
input_artifacts:
  spec.md:
    path: kitty-specs/upgrade-seeded-list-hint-01M6BV1A/spec.md
    sha256: d6457e8ae24496c2367710dbbaa9b6575533c71598d39829a587aac666c060a0
  plan.md:
    path: kitty-specs/upgrade-seeded-list-hint-01M6BV1A/plan.md
    sha256: 0b216336fe5c88af8a619e256088e6fd15c73ec4b7894d07d850174e8aad5a2d
  tasks.md:
    path: kitty-specs/upgrade-seeded-list-hint-01M6BV1A/tasks.md
    sha256: 5e2f97a0aaa45e845b385cfd0f7432a0e3e6a28f014421cdf8291ecae3369b93
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  critical: 0
  low: 3
  medium: 3
  info: 0
findings:
- id: A1
  severity: medium
  category: consistency
  summary: Two provenances can both match (a release whose default preset listed the whole catalogue), so the new check must not emit a second hint for the same key; one hint per kind, today's-in-force first.
- id: A2
  severity: medium
  category: correctness
  summary: A bare "listed contains the released preset" test would fire on a hand-picked list that merely contains all preset ids; the upper bound D union selected is what makes the provenance claim true.
- id: A3
  severity: medium
  category: correctness
  summary: Without bounding the list by today's in-force set, a list holding a retired id would be told to narrow, hiding the real defect.
- id: A4
  severity: low
  category: coverage
  summary: The existing "resolved once and only for a candidate kind" test pins the resolution call count; the new check must reuse that map, not resolve again.
- id: A5
  severity: low
  category: determinism
  summary: DEFAULT_SNAPSHOTS can hold several distinct released lists per key; the selection must be deterministic (smallest, then lexicographic) so a warning does not vary by host.
- id: A6
  severity: low
  category: scope
  summary: A whole-catalogue seed from a release whose catalogue later grows stays unreported; not reachable with any released CLI today, recorded as a residual in the ADR with the follow-up shape.
---

# Analysis Report — upgrade-seeded-list-hint-01M6BV1A

**Mission**: `upgrade-seeded-list-hint-01M6BV1A` (#6684) · **Date**: 2026-11-01
**Scope**: consistency of spec/plan/tasks against the code and the frozen data they depend on.
**Method**: an independent pass over the four artifacts and the files they name, checking every
assumption the plan makes about the migration, the snapshot module, the existing test module and the
operator ruling. (This run is a single implementation sub-agent; the checks below were executed
directly, and the review round is recorded in the PR's `Self-review:` block.)

## Verified premises

| # | Premise | Evidence |
|---|---------|----------|
| P-1 | Today's hint compares only with today's in-force set | `_seeded_list_hints`: `listed == resolver.stems(kind, entry.ids)` |
| P-2 | The superseded seeding wrote the **released** `default.yaml` list | `git show v3.2.6rc1:src/specify_cli/upgrade/migrations/m_unify_charter_activation.py` passes `load_default_pack_activation_ids()` as `default_ids` |
| P-3 | Those released lists are already frozen in-tree | `DEFAULT_SNAPSHOTS` equals the 3.2.6rc1 `default.yaml` per key for all eight kinds (checked: equal-any = True for each) |
| P-4 | The frozen module is an accepted comparand for exactly this purpose | `_charter_pack_cutover_resets` already compares a project list against `DEFAULT_SNAPSHOTS` |
| P-5 | The #6629-scale seed (38 directives / 14 paradigms) is today's catalogue | `resolve_effective_sets` returns 38 directive stems today; the whole-catalogue seeding era (4.0.0rc6/rc7) shipped the same catalogue as today for every kind |
| P-6 | The ruling forbids a reset and asks for the hint gap only | Issue #6684 comment, 2026-10-26: "option (b). No reset migration… The warning's hint gap still gets fixed" |

## Findings

**A1 (medium)** — one hint per kind, today's provenance first. Encoded in plan D-3 and T004.

**A2 (medium)** — the superset is bounded above by `D ∪ selected`, the exact shape the superseded
seeding produced (preset first, then the interview's missing ids). Encoded in plan D-1, T002/T003.

**A3 (medium)** — bound the list by today's in-force set, so a list holding a retired id is not told to
narrow. Encoded in FR-003 and plan D-2.

**A4 (low)** — the existing test `test_the_in_force_set_is_resolved_at_most_once_and_only_for_a_candidate`
pins one resolution call per apply and only for candidate kinds; the new provenance reads the same map.

**A5 (low)** — deterministic selection among several matching released lists (smallest, then
lexicographic). Added to WP01's notes.

**A6 (low)** — the residual: a whole-catalogue seed from a release whose catalogue later grows. Not
reachable with any released CLI today (P-5); the ADR names the condition and the follow-up shape instead
of adding a per-release frozen catalogue, which would be an order of magnitude more frozen data for a
case that cannot occur yet.

## Verdict

Spec, plan and tasks are consistent with the code and the ruling. The only artifact change made during
finalization was the ownership fix (the module docstring lives in WP01's owned file, so its subtask moved
from WP02 to WP01). Proceed to implementation with A1, A2, A3 and A5 as the constraints the code must
encode.
