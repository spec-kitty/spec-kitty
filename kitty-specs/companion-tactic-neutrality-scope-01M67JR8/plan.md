# Implementation Plan: Companion tactic neutrality scope

**Branch**: `issue-6724-companion-tactic-neutrality-scope` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/companion-tactic-neutrality-scope-01M67JR8/spec.md`
**Input**: Issue spec-kitty/spec-kitty#6724

## Summary

The neutrality gate decides whether to lint a synthesized artifact with
`_is_generic_scoped`, which infers the artifact's scope from the hyphen-separated
components of its slug. That inference is right for `<lang>-style-guide` and
`jvm-build-guide`, and wrong for the companion tactic `how-we-apply-<directive-id>`,
whose slug components name a directive and therefore never a language. The gate
then falls back to "unknown ⇒ generic" and refuses a companion tactic that names
the project's own test runner.

The fix narrows the *classification*, not the ban list: a companion tactic's scope
is the project's own language scope (observed ∪ declared, family-expanded), which
is known whenever that set is non-empty. No scope known ⇒ the artifact stays
generic and stays linted, which is exactly the audience
`charter-ownership-consolidation-and-neutrality-hardening-01KPD880`#FR-012
protects. `banned_terms.yaml` is untouched and no term-to-language table is
introduced.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new (`ruamel.yaml` already used by the lint)
**Storage**: files only — staged artifact YAML under `.kittify/charter/.staging/`
**Testing**: pytest; CLI-level fixture driving the real `charter synthesize`
command via `typer.testing.CliRunner` + `charter_cwd_isolation`
**Target Platform**: the `spec-kitty` CLI
**Constraints**: no allowlist edits, unchanged exit codes and error fields, no
full heavy-suite run (charter Standing Order + `NO_FULL_HEAVY_SUITES_IN_MISSION`)

Touched surfaces, surveyed before planning:

| Surface | Role today |
|---|---|
| `charter/activation/synthesizer/write_pipeline.py::_is_generic_scoped` | the scope decision — the one place the rule lives |
| `charter/activation/synthesizer/write_pipeline.py::_run_neutrality_gate` | calls it, and already holds each artifact's `ProvenanceEntry` |
| `charter/activation/synthesizer/interview_mapping.py` | owns the `selected_directives` → companion-tactic expansion and the literal section label |
| `charter/activation/synthesizer/errors.py::NeutralityGateViolation` | error shape (unchanged) |
| `docs/adr/3.x/2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md` | states that `spec-kitty` owns "neutrality gating" — the contract the rule implements |
| `docs/changelog/CHANGELOG.md` | `[Unreleased]` entry |

Second sources of truth checked and rejected:

- A term→language map (PY-001 → python) derived from banned-term ids: the ids are
  *not* language-faithful (`PY-002` is `junit`, a JVM reporter), and building the
  map is the "allowlist of tool names" the run's guidance rules out. Rejected.
- Scope-tagging the companion slug (e.g. `how-we-apply-directive-003-python`):
  the slug is the artifact identity carried by the URN, the synthesis manifest,
  provenance, the project-graph `directive --suggests--> tactic` edge and
  `synthesized-artifacts.yaml`. Renaming it churns all of those and needs a
  migration; it also misstates the artifact (a companion is not *about* a
  language). Rejected — recorded as D-2.
- A glob entry in `language_scoped_allowlist.yaml` for
  `.kittify/charter-packs/tactic/how-we-apply-*`: the allowlist is a *path* list
  for the repository's own shipped/project artifacts, and the gate scans a
  staging tree, so a path entry cannot name a staged file per run. It would also
  be a tool-shaped allowlist that exempts every companion forever, including in
  an unconfigured project. Rejected — recorded as D-1.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority (DIRECTIVE_044) | The companion section label is declared once, in `interview_mapping`, and imported by the gate; no second literal. |
| Smallest viable diff / locality (DIRECTIVE_024, `change-apply-smallest-viable-diff`) | One predicate gains one branch and one keyword argument; the literal moves to its existing owner; call sites pass provenance they already hold. |
| ATDD-first / red-first (DIRECTIVE_034, DIRECTIVE_041) | A CLI-level test drives `charter synthesize` and fails on `main` with the reported `NeutralityGateViolation` before the rule changes. |
| Architectural gate discipline (DIRECTIVE_043) | The gate is narrowed by construction, not weakened by an exemption list; a same-fixture positive control proves the unconfigured case still fires. |
| Terminology canon | "Mission", "work package"; no `feature*` aliases introduced. |
| No full heavy suites in mission work | Targeted test files only; CI owns the full matrix. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/companion-tactic-neutrality-scope-01M67JR8/
├── plan.md              # This file
├── spec.md              # Mission specification
├── tasks.md             # Work-package outline
├── tasks/
│   ├── WP01-companion-scope-rule.md
│   └── WP02-docs-and-changelog.md
└── traces/
    ├── approach.md
    ├── design-decisions.md
    └── tooling-friction.md
```

### Source (repository root, single project)

```
src/charter/activation/synthesizer/
├── interview_mapping.py     # companion section label owner (constant)
└── write_pipeline.py        # _is_generic_scoped + _run_neutrality_gate
tests/charter/synthesizer/
├── test_companion_tactic_neutrality_6724.py   # new: red-first CLI + unit proofs
├── test_write_pipeline.py                     # existing gate unit tests
└── test_multi_language_evidence.py            # existing FR-011 scope tests
docs/adr/3.x/2026-04-19-6-...-charter-handoff.md  # amendment
docs/changelog/CHANGELOG.md                       # [Unreleased] entry
```

## Implementation Concern Map

| IC | Concern | Owner surface | Why it is a separate concern |
|---|---|---|---|
| IC-01 | Which interview section produces companion tactics | `interview_mapping` | the mapping is the single authority; the gate must not restate it |
| IC-02 | Whether an artifact is linted | `write_pipeline._is_generic_scoped` | one predicate, one decision |
| IC-03 | What the gate lints and how it refuses | `write_pipeline._run_neutrality_gate` | wiring only: pass the provenance the loop already has |
| IC-04 | Proving the reported refusal is gone | new CLI-level test | the reporter's entry point, not a helper |
| IC-05 | Proving the gate still fires where it must | unit + CLI negative cases | the other half of a compound fix |

## Phase 0 — Research

Recorded in `design-decisions.md` rather than a separate research file: the
mission is one rule, and the evidence (the reproduction, the pinned FR-011
contract, the rejected alternatives) is short enough to keep in one place.

**Reproduction (witness).** On `main` `512567eee7`, a tmp project that

- declares `language_scope: [Python]` in `answers.yaml` and has
  `pyproject.toml` + `src/app.py`,
- activates `003-decision-documentation-requirement` in the activation ledger,
- writes `.kittify/charter/generated/tactics/how-we-apply-directive-003.tactic.yaml`
  with the step text `Run pytest -q before opening the pull request.`,

fails `charter synthesize` with:

```
NeutralityGateViolation: Neutrality gate blocked promotion of tactic:how-we-apply-directive-003.
Language-specific terms detected in a generic-scoped artifact: 'pytest'.
```

while `styleguide:python-style-guide`, in the same run and with the same banned
term in its body, is promoted — the asymmetry the narrowing removes.

## Phase 1 — Design

### The rule

`_is_generic_scoped` keeps its slug-component test and gains one antecedent:

```
scope = observed ∪ declared, family-expanded
if not scope:            → generic            (unchanged: unknown ⇒ lint)
if is a companion tactic → language-scoped    (new: the artifact's scope is the project's stack)
otherwise                → scope.isdisjoint(slug components)   (unchanged)
```

"Companion tactic" is `provenance.source_section` equal to the section label that
`interview_mapping` expands into companion tactics (`selected_directives`), and
the artifact kind is a tactic. The provenance is the artifact's own record of why
it exists; the slug is not consulted for the classification at all.

### Data flow

```
run_all() → [(body, ProvenanceEntry)]
                  │  source_section, artifact_kind, artifact_slug
                  ▼
        _run_neutrality_gate(staging_dir, results, evidence, declared)
                  │
                  ▼
        _is_generic_scoped(kind, slug, evidence, declared,
                           source_section=prov.source_section)
                  │ True → run_neutrality_lint(staged file) → hits → refuse
                  ▼ False → skip
```

### Error handling

Unchanged. `NeutralityGateViolation` keeps `artifact_urn`, `detected_terms`,
`staging_dir`; the staging directory is still preserved for inspection; the CLI
keeps exit 1 and its `--json` envelope.

## Phase 2 — Tasks

Two work packages, sequentially owned by one implementer:

- **WP01** — the rule, its wiring, and the red-first CLI proof plus the
  unit-level positive and negative controls (FR-001…FR-006).
- **WP02** — the gate's contract text, the ADR amendment and the changelog entry
  (FR-007, FR-008).

## Review and Validation Strategy

- Targeted suites only: `tests/charter/synthesizer/test_companion_tactic_neutrality_6724.py`,
  `tests/charter/synthesizer/test_write_pipeline.py`,
  `tests/charter/synthesizer/test_multi_language_evidence.py`,
  `tests/charter/test_neutrality_lint.py`, `tests/charter/test_phase3_integration.py`,
  `tests/charter/synthesizer/test_interview_mapping.py`.
- `ruff check` on the touched files; `mypy` on the touched module if the repo's
  configured scope includes it.
- Non-vacuity: the companion case (promotes) and the unconfigured case (refuses)
  are built from one shared fixture builder, so neither can drift; the CLI
  refusal case asserts the staging tree survives.
- Squad: two reviewers, one on the rule's boundary (does the exemption admit
  anything that is not a companion?) and one on the evidence (does the CLI test
  really fail on `main`?).

## Complexity Tracking

No violations. One predicate branch, one new keyword-only parameter, one new
constant in its existing owner, one new test module, one ADR amendment.
