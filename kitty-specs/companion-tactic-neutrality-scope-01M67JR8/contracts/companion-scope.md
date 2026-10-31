# C-1 — Companion tactic scope rule

The neutrality gate's scope contract, as implemented in
`charter.activation.synthesizer.write_pipeline._is_generic_scoped` (#6724).

## The subject

An artifact's **scope** is its audience. A *generic-scoped* artifact addresses
every project whatever its language, so a language-specific term in it is an
unstated assumption about the reader's stack. That assumption is the bias the
gate exists to stop
(`charter-ownership-consolidation-and-neutrality-hardening-01KPD880` FR-008,
FR-012). An artifact whose audience is one known stack has no such assumption to
make.

## Classification

Let `scope = observed ∪ declared`, family-expanded, where *observed* comes from
`CodeSignals.languages` (or `scope_tag`) and *declared* comes from the interview's
`language_scope` / `languages_frameworks`.

|candidate|condition|verdict|
|---|---|---|
|any artifact|`scope` is empty|**generic-scoped** — lint it|
|companion tactic|`artifact_kind == "tactic"` and `source_section == selected_directives`|**language-scoped** — skip|
|anything else|a hyphen-separated slug component is in `scope`|**language-scoped** — skip|
|anything else|otherwise|**generic-scoped** — lint it|

A **companion tactic** is the artifact `interview_mapping` expands from the
`selected_directives` interview section: exactly one
`tactic:how-we-apply-<directive-id>` per *explicitly activated* directive, whose
provenance records that section. Its slug is derived from a directive id and
carries no language, so the slug-component test cannot see its scope; the
provenance records why the artifact exists, and that is what the gate reads.

## Invariants

1. The companion exemption is keyed on the artifact **kind** as well as the
   section, so a `styleguide` or `directive` can never reach it.
2. An empty `scope` stays generic even for a companion, so an unconfigured
   project is still refused (FR-012's audience).
3. Provenance with no `source_section` is not a companion, so older records keep
   the previous behaviour.
4. `banned_terms.yaml` and `language_scoped_allowlist.yaml` are not part of this
   rule: a term is never exempted by name, and no term-to-language table is
   introduced.
5. The error shape is unchanged: `NeutralityGateViolation` still carries
   `artifact_urn`, `detected_terms`, `staging_dir`, and the staging tree is still
   preserved for inspection.

## Worked examples

| project scope | slug | `source_section` | verdict |
|---|---|---|---|
| `python` | `how-we-apply-directive-003` | `selected_directives` | language-scoped |
| `python` | `testing-philosophy` | `testing_philosophy` | generic |
| `python` | `java-style-guide` | `language_scope` | generic |
| none | `how-we-apply-directive-003` | `selected_directives` | generic |
