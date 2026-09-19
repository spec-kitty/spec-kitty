---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: drupal-dries-profile-01M28X69
mission_id: 01M28X69AVNQKDXK2HQ4MVSSD9
generated_at: '2026-09-11T21:02:42.007600+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/drupal-dries-profile-01M28X69/spec.md
    sha256: 030bc060760c354f8e6e6742c35d667fed221658f86624ecb3d656e68a11afb9
  plan.md:
    path: kitty-specs/drupal-dries-profile-01M28X69/plan.md
    sha256: ac3c468e2dbf4863790be66158aa780ebe972a92bec1cecc48a645d35e65256b
  tasks.md:
    path: kitty-specs/drupal-dries-profile-01M28X69/tasks.md
    sha256: 833d00464c77b0d7e45a1a9cd5f19233539b171ab3f096ba7516d6f7919e4e92
  charter:
    path: .kittify/charter/charter.yaml
    sha256: cded0cf700d030b6f13d6c6f58d237e371ec41e0b874ca2630dcf234dd695fdf
verdict: blocked
issue_counts:
  high: 1
  critical: 0
  low: 1
  medium: 5
  info: 0
findings:
- id: D1
  severity: high
  category: coverage
  summary: NFR-004 mandates a type gate and the charter mandates mypy --strict, but no work package runs mypy — WP08's verification command list stops at ruff check and ruff format.
- id: I1
  severity: medium
  category: inconsistency
  summary: spec.md describes one conventions styleguide covering security; plan.md splits it into two artifacts. Decision is recorded but spec.md was never reconciled.
- id: I2
  severity: medium
  category: inconsistency
  summary: plan.md R-006 requires a verification-versus-authorship clause in both profiles; spec.md FR-004 never states it, so the plan demands strictly more than the spec.
- id: C1
  severity: medium
  category: coverage
  summary: C-006 (no new runtime dependencies) has no verification step in any work package.
- id: C2
  severity: medium
  category: coverage
  summary: NFR-003 (>=90% diff coverage) is mapped to WP01, but the only coverage-bearing executable diff belongs to WP07, which does not carry the requirement.
- id: A1
  severity: medium
  category: ambiguity
  summary: "'anti-pattern' is used both as a generic spec concept and as a literal artifact kind in this codebase; FR-008 read alone points at the wrong channel."
- id: U1
  severity: low
  category: underspecification
  summary: SC-004 and SC-007 are human-judgement criteria with no automatable check; acceptable but they cannot gate CI.
---

## Specification Analysis Report

**Mission**: `drupal-dries-profile-01M28X69`
**Artifacts**: spec.md, plan.md, tasks.md (+ research.md, data-model.md, contracts/, quickstart.md)
**Date**: 2026-09-11

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| D1 | Charter Alignment / Coverage | HIGH | spec.md:201 (NFR-004); tasks/WP08:T041; tasks/WP07:T034 | NFR-004 requires "Lint, format, **type**, and terminology gates pass with zero new issues". The charter's Testing Requirements state "**mypy --strict** must pass (no type errors)". WP07 modifies Python (`extractor.py`), yet `mypy` appears nowhere in any work package — it occurs exactly once in the whole mission, as prose in plan.md:73. WP08's T041 command list runs `make test-fast`, two pytest directories, the terminology guard, `ruff check`, and `ruff format --check`, and stops. | Add `uv run mypy --strict src/charter/offering/drg/migration/extractor.py` to WP07's Definition of Done and to WP08's T041 command list. The change is six lines added to a typed tuple, so the gate should pass immediately — the defect is that nothing proves it. |
| I1 | Inconsistency | MEDIUM | spec.md:26, spec.md:99 vs plan.md Structure + Complexity Tracking | spec.md's Domain Language and User Story 2 acceptance scenario both describe a single "conventions styleguide" covering "code style, development patterns, and security requirements". plan.md delivers **two** artifacts, splitting security/performance out. | Not an error — decision `01M28YDW8F49V927NNPWMWCBVJ` is recorded and plan.md's Complexity Tracking justifies the deviation. But spec.md now understates the deliverable. Update FR-006 and the US2 scenario to name both artifacts, or accept the drift knowingly. |
| I2 | Inconsistency | MEDIUM | spec.md:183 (FR-004) vs research.md R-006, tasks/WP06:T032 | plan.md resolves the JS-gate tension by requiring both profiles to distinguish *verifying* from *authoring*. WP06 T032 makes that a Definition-of-Done item. spec.md's FR-004 requires only that each profile "name each other's territory" — the distinction is absent. | The plan demands more than the spec. Either fold the distinction into FR-004's text, or note in spec.md that FR-004 is refined by R-006. As it stands a reviewer checking WP06 against spec.md alone would not know to look for it. |
| C1 | Coverage | MEDIUM | spec.md C-006; tasks/WP08 | C-006 ("Delivery adds no new runtime dependency") is asserted in plan.md's supply-chain section but has no verification step. No work package checks `pyproject.toml` / `uv.lock` are unchanged. | Add a one-line check to WP08 T041: `git diff --stat pyproject.toml uv.lock` must be empty. Cheap, and it converts an assertion into evidence. |
| C2 | Coverage / Mapping | MEDIUM | tasks.md requirement coverage table; WP01 vs WP07 | NFR-003 (≥90% diff coverage) is mapped to WP01. WP01 writes only test files. The mission's sole executable diff is WP07's six-line `extractor.py` change, and WP07 carries FR-005 + NFR-002 only. | Re-map NFR-003 to WP07 (or to both). Today the requirement is nominally covered by a package that cannot satisfy it. |
| A1 | Ambiguity / Terminology | MEDIUM | spec.md FR-008; research.md R-004 | FR-008 says the forbidden practices are "recorded as Drupal anti-patterns". In this codebase `anti_pattern` is also a literal `ArtifactKind` with its own graph channel. research.md R-004 establishes that the Drupal entries belong in the **styleguide** channel instead, but FR-008 read in isolation points the other way. | The plan resolves this correctly; the spec wording is the hazard. Add "(recorded within the conventions styleguides, per R-004)" to FR-008, or rely on WP03/WP04 prompts, which already state the destination explicitly. |
| U1 | Underspecification | LOW | spec.md SC-004, SC-007 | Both success criteria depend on a human reader — ten task assignments with no ties, ten sampled claims all traceable. Neither can be automated. | Acceptable and honestly labelled as such in contracts/profile-contract.md C-P6. No action needed; noted so the gap is deliberate rather than discovered later. |

### Post-analysis correction (recorded 2026-09-11, after WP04 cycle 1)

A factual error was found in the contract chain during WP04's review and has been corrected. It is
recorded here because it changed `plan.md`, `data-model.md`, `contracts/styleguide-toolguide-contract.md`,
and three WP prompts after this report was first written.

**What was wrong.** The upstream source (amazee.io `drupal-agents-md`, Vanilla variant) states at its
line 701 that `accessCheck(TRUE)` is "required from Drupal 10.2" and "will be required in Drupal 12".
That claim is false, and it was propagated verbatim into C-S8 and five other planning artifacts during
the plan and tasks phases.

**The actual facts**, per change record [node/3201242](https://www.drupal.org/node/3201242) and core's
own deprecation message (`deprecated in drupal:9.2.0 and an error will be thrown from drupal:10.0.0`):
implicit access checking was deprecated in **9.2.0** and throws an error from **10.0.0**. On this
mission's declared Drupal 10.x/11.x baseline an unchecked entity query is **already a fatal error** —
not a deprecation warning, and nothing is deferred to Drupal 12.

**Why it matters beyond one line.** The guidance was wrong in the reassuring direction: it told readers
they had runway until Drupal 12 on a version where the query already fails. It also reached two
deliverables (WP03's and WP04's styleguides) before being caught.

**How it was caught.** The WP04 reviewer verified against the official change record rather than against
the source guide, which is exactly what NFR-006 requires and what C-S8's stated purpose ("assertions a
reviewer can verify against official Drupal documentation") demands. The check that would have caught it
earlier — tracing to primary Drupal documentation rather than to the distillation source — is now
explicit in the corrected C-S8 row and in WP08's T042 sampling instruction.

**Standing risk this exposes.** Every Drupal claim in this mission inherits the source's accuracy. One
error in it is now confirmed. WP08's ten-claim sampling (SC-007) is the remaining defence and should be
treated as a real audit, not a formality.

### Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 profile exists | ✅ | T007–T013 (WP02) | |
| FR-002 backend competence | ✅ | T008, T010 (WP02) | |
| FR-003 theming competence | ✅ | T008, T010 (WP02); T017 (WP03) | |
| FR-004 reciprocal boundary | ✅ | T008 (WP02); T031–T033 (WP06) | See I2 — plan requires more than spec states |
| FR-005 lineage inherited | ✅ | T034 (WP07) | |
| FR-006 conventions guidance | ✅ | T014–T019 (WP03); T020–T025 (WP04) | See I1 — spec describes one artifact, plan delivers two |
| FR-007 verification commands | ✅ | T026–T030 (WP05) | |
| FR-008 anti-patterns recorded | ✅ | T018 (WP03); T021–T024 (WP04); T042 (WP08) | See A1 — channel ambiguity in spec wording |
| FR-009 self-review protocol | ✅ | T011 (WP02) | |
| FR-010 provenance | ✅ | T012 (WP02); T019, T025; T039 (WP08) | |
| FR-011 version baseline | ✅ | T013 (WP02) | |
| FR-012 activation opt-in | ✅ | T040 (WP08) | |
| FR-013 load health observable | ✅ | T004 (WP01); T037 (WP07) | Negative-case assertion present — non-vacuous |
| NFR-001 size band | ✅ | T013 (WP02) | |
| NFR-002 zero skipped profiles | ✅ | T003 (WP01); T036–T037 (WP07) | |
| NFR-003 diff coverage | ⚠️ | T004–T006 (WP01) | **See C2** — mapped to a package with no executable diff |
| NFR-004 gates stay green | ⚠️ | T041 (WP08) | **See D1** — type gate named in the requirement, absent from the command list |
| NFR-005 context unchanged | ✅ | T040 (WP08) | |
| NFR-006 distillation fidelity | ✅ | T013, T019, T025, T030; T042 (WP08) | |
| NFR-007 existing profiles undisturbed | ✅ | T033 (WP06) | |
| C-001 source pack only | ✅ | WP02–WP06 owned_files; quickstart trap table | |
| C-002 lineage endpoint form | ✅ | T034 (WP07); T005 (WP01) | |
| C-003 distillation not copy | ✅ | T039 (WP08) | |
| C-004 environment-agnostic | ✅ | T011 (WP02); T029 (WP05) | |
| C-005 version baseline | ✅ | T013 (WP02); T022 (WP04) | |
| C-006 no new dependencies | ❌ | — | **See C1** — asserted in plan.md, verified nowhere |
| C-007 no mission type | ✅ | implicit in owned_files; no WP touches mission types | Structurally enforced by ownership |
| C-008 terminology canon | ✅ | T041 (WP08) | |

### Charter Alignment Issues

One. The charter's Technical Standards section states **"mypy --strict must pass (no type errors)"** as a Testing Requirement, and spec.md's own NFR-004 names the type gate explicitly. No work package runs it. This is finding **D1**, and it is the reason this report's verdict is `blocked`.

Everything else checks out against the charter: ATDD-first is honoured (WP01 is red-first, and its assertions must fail for absence rather than error), single canonical authority is respected (lineage goes to the one table the code names as lineage truth), architectural alignment holds (no new module, no new boundary), and terminology is gated in WP08.

### Unmapped Tasks

None. All 43 subtasks trace to at least one requirement.

### Metrics

- **Total requirements**: 28 (13 FR, 7 NFR, 8 C)
- **Total work packages**: 8 · **Total subtasks**: 43
- **Functional requirement coverage**: 13/13 = **100%**
- **Full requirement coverage**: 26/28 fully covered, 2 partially (NFR-003, NFR-004), 1 uncovered (C-006) = **93%**
- **Ambiguity count**: 1 · **Duplication count**: 0 · **Critical issues**: 0 · **High issues**: 1

### Next Actions

No CRITICAL issues — nothing here blocks starting work. The one HIGH is a missing gate, not a broken design, and it is confined to packages that run late:

1. **Before WP07 lands**: add `mypy --strict` to WP07's Definition of Done and WP08's T041 list (D1). WP07 is the only package touching Python, so this does not affect WP01 or WP02.
2. **Before WP08 runs**: add the `pyproject.toml` / `uv.lock` no-change check (C1), and re-map NFR-003 onto WP07 (C2) via `spec-kitty agent tasks map-requirements --wp WP07 --refs NFR-003`.
3. **Optional, spec hygiene**: reconcile I1, I2, and A1 in spec.md so it describes what the plan actually builds. All three are recorded decisions, not mistakes — the spec simply lags them.

**WP01 and WP02 are unaffected by every finding above.** D1 concerns Python that WP07 writes; C1, C2 and A1 land on WP07/WP08 and WP03/WP04. Implementation of the first two packages can proceed now.

### Remediation

Should all of these findings be addressed before moving on to implementation? I can suggest concrete remediation edits for the findings you want to resolve.
