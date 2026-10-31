# Mission Specification: Companion tactic neutrality scope

**Mission Branch**: `issue-6724-companion-tactic-neutrality-scope`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6724 — "charter synthesize: neutrality gate refuses a companion tactic for language-specific terms (reported: 'pytest')". Guidance from the run: decide from the gate's own contract what neutrality means here, reproduce the false refusal, and narrow the rule rather than adding an allowlist of tool names.

## Context: what the gate's contract actually says

The neutrality gate exists to stop Spec Kitty's own defaults from imposing a
language on a project that has not chosen one. Its two governing statements are:

- `charter-ownership-consolidation-and-neutrality-hardening-01KPD880` FR-008:
  *generic-scoped* shipped artifacts must not carry a registered banned term.
- the same mission's `charter-ownership-consolidation-and-neutrality-hardening-01KPD880`#FR-012: an unconfigured/generic project must not trigger a
  Python-specific runtime command (a `pytest` invocation, `pip install`,
  `python -m`) **as a default** from charter-driven flows.

Both statements are about **scope**, not about vocabulary: a term is "bias" only
when the artifact is addressed to a project whose language the term does not
describe. `_is_generic_scoped` currently infers that scope one way — from the
hyphen-separated components of the artifact slug. That inference is sound for the
artifact class it was written for (`<lang>-style-guide`, `jvm-build-guide`), and
`charter-synthesis-graph-and-languages-01M59RZ5`#FR-011 pinned it deliberately.

It is unsound for a **companion tactic**. A companion tactic's slug is
machine-derived from the identity of the artifact it applies
(`how-we-apply-<directive-id>`, `interview_mapping._append_selected_directives`):
its components name a directive, never a language. So the gate cannot see a scope
that *is* known elsewhere, falls through to "unknown ⇒ generic", and refuses the
companion for naming the very stack the project already declared.

Reproduced on `main` at `512567eee7` with a Python project whose
`.kittify/config.yaml` activates `003-decision-documentation-requirement` and
whose generated companion says `Run pytest -q before opening the pull request.`:

```
NeutralityGateViolation: Neutrality gate blocked promotion of
tactic:how-we-apply-directive-003.
Language-specific terms detected in a generic-scoped artifact: 'pytest'.
```

The artifact is not generic. It is the project's own application note, authored
by the project's harness from that project's interview answer, delivered to that
project's actions, linked from that project's directive. It has no cross-project
audience to bias, so the gate has no basis to call its vocabulary a default.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A companion tactic may name the project's own stack (Priority: P1)

An operator of a repository whose language scope is known (observed from the
code, or declared in the interview) activates a built-in directive. The harness
writes the companion tactic `how-we-apply-<directive-id>` naming that project's
own test runner. `spec-kitty charter synthesize` promotes the whole set instead of
refusing the companion.

**Why this priority**: it is the reported defect; without it synthesis cannot
complete on any project that activates a directive and names its own tooling in
the companion.

**Independent Test**: build a Python tmp project (declared `language_scope:
[Python]`, source files present), activate one built-in directive, write a
generated companion tactic whose body contains `pytest`, run the real
`charter synthesize` command, and assert exit 0 with the companion listed in
`written_artifacts`.

**Acceptance Scenarios**:

1. **Given** a project with a known language scope and an activated built-in
   directive, **When** the generated companion tactic for that directive names
   the project's own test runner, **Then** `charter synthesize` exits 0 and the
   companion is promoted.
2. **Given** the same project, **When** the companion names a test framework of a
   language the project has *not* declared or observed, **Then** the run still
   succeeds: without a term-to-language map the gate cannot call that term a
   default, and the companion is project-authored content (recorded as D-3).

---

### User Story 2 - An unconfigured project still gets no language default (Priority: P2)

An operator of a repository with no observed and no declared language writes a
companion tactic naming `pytest`. The gate still refuses it, exactly as today.

**Why this priority**: it is the half of the contract the narrowing must not
touch. An unconfigured project is precisely the audience
   `charter-ownership-consolidation-and-neutrality-hardening-01KPD880`#FR-012 protects.

**Independent Test**: same fixture as Story 1 with the language scope removed
(no declared language, no detectable sources); `charter synthesize` exits 1 with
`NeutralityGateViolation` and preserves the staging directory.

**Acceptance Scenarios**:

1. **Given** a project with no observed and no declared language, **When** a
   generated companion tactic names `pytest`, **Then** the gate refuses and names
   the offending URN and term.
2. **Given** that refusal, **When** the operator inspects the staging tree named
   in the error, **Then** the staged artifact is still there (unchanged
   behaviour).

---

### User Story 3 - The narrowing is exactly one artifact class (Priority: P3)

A maintainer reads the gate and can state what it lints: every synthesized
artifact whose scope is not the project's stack stays linted, including
`testing-philosophy-tactic` and non-companion styleguides in a known-scope
project.

**Why this priority**: prevents the fix from becoming "the gate stopped firing".

**Independent Test**: unit assertions on `_is_generic_scoped` for a known-scope
project: companion → language-scoped; `testing-philosophy` and
`java-style-guide` → generic. Plus a CLI-level negative fixture that keeps a
non-companion tactic refused in the same project where the companion passes.

**Acceptance Scenarios**:

1. **Given** a Python project, **When** the gate classifies
   `tactic:how-we-apply-directive-003`, **Then** it is language-scoped.
2. **Given** the same project, **When** the gate classifies
   `tactic:testing-philosophy-tactic` or `styleguide:java-style-guide`, **Then**
   both stay generic-scoped and a banned term in either still refuses.

### Edge Cases

- A project with a *declared* language but no detectable sources: scope is known,
  companion passes — the declared half of the scope already counted.
- A polyglot project (`kotlin` + `typescript`): the companion passes (its scope
  is the project's stack, which is not empty); `java-style-guide` stays linted.
- A companion tactic in a project whose evidence says `scope_tag: unknown` and
  whose interview declares nothing: still refused (Story 2).
- Provenance with no `source_section` (older records, hand-written provenance):
  treated as non-companion, so the gate behaves exactly as before — a safe
  fallback, and `ProvenanceEntry` already requires `source_section` or
  `source_urns`.
- A user-authored project artifact that happens to be in `selected_directives`
  but is not a tactic: the exemption is keyed on the companion section *and* the
  artifact kind, so a styleguide can never slip through it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Companion detected from provenance, not the slug | As a maintainer, I want the gate to learn an artifact is a companion tactic from its provenance `source_section`, so that detection follows the recorded reason instead of a slug string match. | High | Open | [build] | no |
| FR-002 | One owner for the companion section label | As a maintainer, I want the `selected_directives` section label declared once in `interview_mapping` and imported by the gate, so that the mapping and the gate cannot drift. | Medium | Open | [ratchet] | no — pinned by a test that imports the constant from its owner |
| FR-003 | A companion's scope is the project's stack | As an operator with a known language scope, I want a companion tactic naming my stack to be promoted so that synthesis completes. | High | Open | [build] | no |
| FR-004 | No scope known ⇒ still linted | As a maintainer, I want a companion in a project with no observed and no declared language to stay refused, so that `charter-ownership-consolidation-and-neutrality-hardening-01KPD880`#FR-012 keeps its teeth. | High | Open | [ratchet] | no |
| FR-005 | Non-companion artifacts unchanged | As a maintainer, I want `testing-philosophy-tactic`, `testing-style-guide` and other non-companion artifacts to keep the current slug-component rule. | High | Open | [ratchet] | no |
| FR-006 | Red-first reproduction through the CLI | As a maintainer, I want a test that drives the real `charter synthesize` command on a known-scope project with a pytest-naming companion, so that the fix is proven at the entry point the reporter used. | High | Open | [build] | no |
| FR-007 | Gate wording states the rule | As an operator, I want the gate's module and function contract text to say that a companion tactic's scope is the project's, so that the next reader does not re-derive it from the slug. | Medium | Open | [build] | no |
| FR-008 | Recorded as a contract amendment | As a maintainer, I want the harness-handoff ADR amended, so that the governed contract matches the code. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate stays fast | `_run_neutrality_gate` stays under the existing 5-second envelope on a staged artifact set (the existing `test_gate_timing` performance test). | Performance | Medium | Open |
| NFR-002 | No new dependency, no new file format | The change adds no third-party dependency, no new YAML/JSON surface, and no new allowlist file. | Maintainability | High | Open |
| NFR-003 | Changed lines covered | CI's diff-cover gate reports at least 90% coverage on the changed lines. | Testability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No allowlist of tool names | `banned_terms.yaml` and `language_scoped_allowlist.yaml` are not edited, and no term-to-language table is introduced. | Technical | High | Open |
| C-002 | Exit codes and error shape unchanged | `charter synthesize` keeps exit 0 on success and exit 1 on `NeutralityGateViolation`; the error keeps `artifact_urn`, `detected_terms` and `staging_dir`. | Technical | High | Open |
| C-003 | One canonical authority | The companion section label is not duplicated; the gate reads it from `interview_mapping`. | Technical | High | Open |

### Key Entities

- **Companion tactic**: a tactic synthesized once per *explicitly activated*
  built-in directive, slug `how-we-apply-<directive-id>`, provenance
  `source_section = selected_directives`, `source_urns = (directive:<ID>,)`.
- **Project language scope**: the languages observed from evidence
  (`CodeSignals.languages` or `scope_tag`) united with the languages the
  interview declares, family-expanded. Empty means "unknown".
- **Neutrality gate**: the pre-promote scan that lints generic-scoped staged
  artifacts for registered banned terms.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A known-scope project with an activated directive and a companion tactic naming its own test runner promotes on the first `charter synthesize` — exit 0, companion present in `written_artifacts` — [build] · no-op passable: no
- **SC-002**: An unconfigured project with the same companion text still exits 1 with `NeutralityGateViolation` and a preserved staging directory — [ratchet] · no-op passable: no
- **SC-003**: No entry is added to `banned_terms.yaml` or `language_scoped_allowlist.yaml` (diff assertion in review) — [ratchet] · no-op passable: no
- **SC-004**: The gate's targeted test files pass with no regressions: `tests/charter/synthesizer/test_write_pipeline.py`, `tests/charter/synthesizer/test_multi_language_evidence.py`, `tests/charter/test_neutrality_lint.py`, `tests/charter/test_phase3_integration.py` — [ratchet] · no-op passable: no
