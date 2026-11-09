---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: consolidation-window-provenance-01M6Y84D
mission_id: 01M6Y84DMCSNYCP6XTD4C4Q8M6
generated_at: '2026-11-08T22:02:54.806270+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: .worktrees/consolidation-window-provenance-01M6Y84D-coord/kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md
    sha256: bc5e872e8b4c1e3c823d43bc73b8df3149fee666090d33e41139d2ba8abb5e5d
  plan.md:
    path: .worktrees/consolidation-window-provenance-01M6Y84D-coord/kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md
    sha256: dc877cf3d17727c5d0e2128e2b4980a9ac0457dd235d439c1b0718153a314bc4
  tasks.md:
    path: .worktrees/consolidation-window-provenance-01M6Y84D-coord/kitty-specs/consolidation-window-provenance-01M6Y84D/tasks.md
    sha256: a459648e5f108fffa9109eba766583333192981b89cec37b0f6d06b7055283fa
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  medium: 2
  high: 0
  critical: 0
  low: 3
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: Spec's 'Claim inputs' term (Domain Language, Key Entities) lists seven values without the status directory or source, while plan IC-08, data-model §6 and FR-013 treat status_dir as a ClaimInputs field compared for parity.
- id: U1
  severity: medium
  category: underspecification
  summary: WP21 T111 edits the WP01-owned Mission ADR as a 'sanctioned out-of-map edit' that is not in WP21 owned_files; ownership/scope review may flag it.
- id: I2
  severity: low
  category: inconsistency
  summary: plan.md header says the Mission branch uses single_branch topology, not yet settled; meta.json records topology lanes_with_coord, settled by finalize-tasks.
- id: I3
  severity: low
  category: inconsistency
  summary: plan.md Charter Check row labels the __all__ convention as C-007, but spec C-007 is 'Authorship and presence move as one slice'; the charter __all__ MUST binds src/charter and src/kernel only.
- id: C1
  severity: low
  category: coverage
  summary: "issue-matrix.json rows for #5048, #5721 and #5703 are placeholder 'unknown' verdicts; #5703 is context-only (out of scope) and will need not-applicable before approval."
---

## Specification Analysis Report

Mission `consolidation-window-provenance-01M6Y84D`. Inputs: spec.md (271 lines), plan.md (324), tasks.md (728), data-model.md, 21 WP prompt files, charter. `finalize-tasks --validate-only` passes (21 WPs, 4 lanes, 0 ownership or requirement-extraction warnings, every SC referenced).

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | spec.md:160, spec.md:235; plan.md:215; data-model.md:148 | The spec's "Claim inputs" lists target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins, excluded canceled WPs and strategy. The plan and data-model add `status_dir` and `source`, and FR-013 compares the status directory. | When the spec is next touched, add "status directory read" and "source" to the Domain Language row and the Key Entities bullet. WP09/WP17 already follow the plan and data-model, so implementation is not blocked. |
| U1 | Underspecification | MEDIUM | tasks/WP21:164-166, :255; tasks.md:536-538 | WP21 edits `docs/adr/4.x/2026-11-08-2-…` (owned by WP01) and writes the WP16/WP18 changelog fragments. The fragments are in WP21's owned_files; the ADR is not. | The WP21 reviewer accepts the ADR diff as the documented sanctioned exception. If a scope gate refuses it, add the ADR to WP21 owned_files and re-run finalize-tasks. |
| I2 | Inconsistency | LOW | plan.md:3 | The header still describes the pre-settlement topology. | Informational. meta.json is the authority (lanes_with_coord). |
| I3 | Inconsistency | LOW | plan.md:52 | Wrong constraint ID on the `__all__` row. | Cosmetic. The new modules declaring `__all__` is still good practice. |
| C1 | Coverage | LOW | issue-matrix.json | Placeholder rows. This is expected at this stage (non-gating heads-up, #3469). | Fill at review: #5048(b) → WP16, #5721 bullet → WP19, #5703 → not-applicable (context-only). |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 ADR window model | Yes | WP01 (T001-T006), WP21 (T111) | |
| FR-002 window-open SHA recorded | Yes | WP07 (T034-T038) | |
| FR-003 typed capture gap | Yes | WP07 | `lane_branch_missing` / `capture_failed` |
| FR-004 mixed logs readable | Yes | WP08 | |
| FR-005 dossier SHA classification | Yes | WP08 (T045) | registry row, not an allowlist (plan interpretation) |
| FR-006 events writer issue | Yes | WP01, WP21 (T112) | filed as spec-kitty-events#229 |
| FR-007 lane window refusal | Yes | WP19 (T097-T103) | dependency-chain exception pinned |
| FR-008 no over-refusal | Yes | WP19 (T098) | |
| FR-009 gap fallback | Yes | WP19 | |
| FR-010 gap report | Yes | WP20 (T104-T106) | |
| FR-011 single_branch recorded window | Yes | WP20 (T107) | |
| FR-012 one claim-input constructor | Yes | WP09, WP17 | |
| FR-013 forecast/fresh/resume parity | Yes | WP09 (T053), WP17 | |
| FR-014 read error is not a deletion | Yes | WP16 | |
| FR-015 frozen anchors on resume | Yes | WP18 (T091-T096) | all four consumers incl. the attestation red-first test |
| FR-016 characterization corpus | Yes | WP02, WP05 | |
| FR-017 precedence matrix | Yes | WP03 | |
| FR-018 surface pin | Yes | WP04 | |
| FR-019 split by check | Yes | WP10-WP15 | |
| FR-020 patch interception guard | Yes | WP04, WP11, WP13, WP15 | |
| FR-021 window opener rule | Yes | WP08, WP19 | |
| FR-022 one lane tip | Yes | WP08, WP19 (T101) | incl. the `approved_bound_refusal` door |
| FR-023 all-gap lane unchanged | Yes | WP19 | |
| NFR-001..NFR-010 | Yes | see tasks.md coverage table | NFR-004/005/009 also checked in every review |
| C-001..C-014 | Yes | see tasks.md coverage table | cross-cutting constraints listed in tasks.md header |
| SC-001..SC-006 | Yes | WP19, WP20, WP17, WP16/WP18, WP02/WP06, WP15 | |

**Charter Alignment Issues:** None. Phase 1 pins land before any code moves (ATDD-first/red-first). Each guard has a self-mutation control. The plan adds no allowlist entry or suppression and leaves the rollback authority untouched. Terminology uses Mission and names the sense of "merge". The no-version-bump ruling for the `status/__init__.py` re-export is recorded as an operator ruling consistent with charter standing order 7.

**Unmapped Tasks:** None. Every WP carries requirement_refs, and every subtask T001-T113 belongs to a WP.

**Metrics:**

- Total Requirements: 23 FR + 10 NFR + 14 C + 6 SC = 53
- Total Tasks: 21 work packages, 113 subtasks
- Coverage %: 100% (every requirement has at least one WP)
- Ambiguity Count: 0 (no vague adjectives without a metric; no placeholders in spec/plan/tasks)
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions

- No CRITICAL or HIGH findings: implementation may proceed (`spec-kitty next` → implement WP01/WP02/WP03).
- I1: optional spec touch-up via `spec-kitty spec-commit`. This would make this report stale and need a re-run, so defer it to a later planning edit.
- U1: brief the WP21 reviewer on the sanctioned ADR edit.
- C1: fill issue-matrix verdicts at WP review with `spec-kitty agent issue-verdict`.
