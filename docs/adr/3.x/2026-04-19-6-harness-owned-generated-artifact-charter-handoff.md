---
title: Harness-Owned Generated-Artifact Charter Handoff Contract
description: 'Fixes the layout and identity rules the harness must satisfy for generated doctrine YAML before it is promoted from the staging tree into the live doctrine tree.'
status: Accepted
date: '2026-04-19'
---

## Context

Charter synthesis is no longer an internal model call. The host LLM or harness
does the reasoning work, reads project evidence, and writes doctrine YAML into
the generated-artifact staging area. `spec-kitty` then validates those files,
records provenance, emits the project DRG layer, and promotes the results into
the live project doctrine tree.

The important boundary is simple:

- The harness owns **reading evidence and generating doctrine**
- `spec-kitty` owns **validation, neutrality gating, provenance, staging, and promotion**

This ADR exists to keep that boundary explicit and prevent future drift back to
an in-process model adapter.

## Decision

### 1. Canonical generated-artifact layout

The harness writes generated doctrine YAML under:

```text
.kittify/charter/generated/
  directives/
    <NNN>-<slug>.directive.yaml
  tactics/
    <slug>.tactic.yaml
  styleguides/
    <slug>.styleguide.yaml
```

The live promoted tree remains:

```text
.kittify/doctrine/
  directives/
  tactics/
  styleguides/

.kittify/charter/
  provenance/
  synthesis-manifest.yaml
```

### 2. Canonical identity rules

The harness must match both the filename rule and the YAML identity rule.

- Directives use `artifact_id = PROJECT_<NNN>` and filename `<NNN>-<slug>.directive.yaml`
- Tactics use `artifact_id = <slug>` and filename `<slug>.tactic.yaml`
- Styleguides use `artifact_id = <slug>` and filename `<slug>.styleguide.yaml`
- The top-level YAML `id` field must exactly match the target `artifact_id`

Examples:

- `directive:PROJECT_001` → `.kittify/charter/generated/directives/001-project-intent-directive.directive.yaml` (renamed from `001-mission-type-scope-directive`, see the 2026-10-19 amendment)
- `tactic:testing-philosophy-tactic` → `.kittify/charter/generated/tactics/testing-philosophy-tactic.tactic.yaml`
- `styleguide:python-style-guide` → `.kittify/charter/generated/styleguides/python-style-guide.styleguide.yaml`

If the file is missing or the YAML `id` does not match, synthesis fails closed.

### 3. Evidence ownership

Evidence is split on purpose:

- `spec-kitty` owns evidence declaration and identity:
  - code-reading signals
  - configured URL lists
  - bundled corpus snapshots
  - hashing and provenance fields derived from that evidence
- The harness owns evidence consumption:
  - reading the repo and the URLs
  - deciding how that evidence should shape generated doctrine text
  - writing the generated YAML files that `spec-kitty` will validate

No internal HTTP fetcher, browser reader, or model client belongs inside
`spec-kitty` for this contract.

### 4. Operator CLI sequence

The canonical operator flow is:

1. Collect interview answers and any configured synthesis inputs.
2. Have the harness write generated YAML into `.kittify/charter/generated/`.
3. Validate the handoff without promotion:

```bash
spec-kitty charter synthesize --dry-run
```

4. Promote the validated artifacts into the live tree:

```bash
spec-kitty charter synthesize
```

5. Regenerate one bounded topic after the harness updates the corresponding
generated artifact:

```bash
spec-kitty charter resynthesize --topic directive:PROJECT_001
```

6. Inspect operator state, evidence summary, manifest health, and provenance:

```bash
spec-kitty charter status --provenance
```

### 5. Fixture adapter policy

`--adapter fixture` remains supported only as the deterministic regression
harness. It is not the default runtime path and it is not a production
generation policy.

## Consequences

### Positive

- One inference engine, the host harness already talking to the user.
- No hidden SDK calls or second API-key story inside `spec-kitty`.
- Clear separation between generation and validation.
- Provenance stays trustworthy because the CLI records the exact validated
handoff, not a hidden model invocation.

### Negative

- The harness now has to respect the file layout and identity rules exactly.
- Operator tooling must make the handoff state visible enough that a bad file is
easy to diagnose. That is why `charter status` and generated-artifact error UX
matter.

## More information

- `src/charter/synthesizer/generated_artifact_adapter.py`
- `src/specify_cli/cli/commands/charter.py`
- `src/charter/synthesizer/write_pipeline.py`
- `tests/agent/cli/commands/test_charter_status_cli.py`

## Amendment 2026-10-19: the always-synthesized directive is renamed

The always-synthesized directive's slug is now `project-intent-directive` (title "Project Intent Directive"); it was `mission-type-scope-directive` (#6443, mission `charter-synthesis-graph-and-languages-01M59RZ5`). The generated-input layout above is unchanged except for that file name: `directives/<NNN>-project-intent-directive.directive.yaml`. The declared `PROJECT_00N` id, the `directive:PROJECT_00N` URN and the interview section label `mission_type` do not change, and synthesis no longer emits a `requires --> mission_type:*` edge for it.

An existing project converges through one charter-layer helper, `rename_legacy_project_intent_directive` (`charter.activation.api`). It moves the artifact file and this harness input, rewrites the provenance and synthesis-manifest entries (recomputing the manifest hashes), relabels the overlay node, drops the dead edge, rewrites stem tokens in the activation write target and restamps the bundle hash. It never rewrites the artifact body, is idempotent, and refuses on a target collision having changed nothing. The upgrade migration `4.0.0rc8_project_intent_directive_rename` and `charter synthesize` / `resynthesize` (before they write, so a legacy file can never leave two files declaring `PROJECT_00N`) both call it. Without the harness-input move, the next synthesize would raise `GeneratedArtifactMissingError` for the new file name.

## Amendment 2026-10-30: what the neutrality gate judges

`spec-kitty` owns "neutrality gating" (above) without saying what the gate judges.
It judges **scope**, not vocabulary (#6724, mission
`companion-tactic-neutrality-scope-01M67JR8`).

A generic-scoped artifact addresses every project, so a language-specific term in
it is an unstated assumption about the reader's stack — that is the bias the gate
exists to stop, and it is the harm FR-008 and FR-012 of
`charter-ownership-consolidation-and-neutrality-hardening-01KPD880` name. An
artifact whose audience is one known stack has no such assumption to make.

Two halves, both required:

- A **companion tactic** — the `tactic:how-we-apply-<directive-id>` that
  `interview_mapping` expands from the `selected_directives` interview section, one
  per explicitly activated directive — is the project's own application note. It is
  still linted, but it may name the banned terms of the project's **own** languages:
  those observed in the code plus those declared in the interview snapshot
  (`language_scope`; org packs contribute none), each expanded to its family. Terms
  of any other language stay banned, so a Rust-only project's companion cannot name
  `pytest`. A banned term's language is its id prefix (`PY-` is Python), owned by
  `neutrality.lint._term_language`; a term with an unmapped prefix is never exempted.
  Its slug is derived from a directive id and names no language, so the old
  slug-component inference could only answer "unknown", read as "generic", which is
  what refused a companion naming the project's own test runner.
- When **no** language is observed and none is declared, nothing is exempted: the
  companion is still refused for any banned term. An unconfigured project still gets
  no Python default, and `banned_terms.yaml` gains no entry.

Detection reads provenance (`source_section`), which records why the artifact
exists, and the artifact kind — never the slug. The gate's exemption therefore
cannot admit a styleguide, and cannot admit a tactic authored outside the
companion expansion.
