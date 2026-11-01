---
title: WP-Prompt Governance Contract — ATDD Findings
description: "Python Pedro's ATDD findings (2026-05-16) for the WP-prompt governance contract: the acceptance tests and what they revealed about the contract."
doc_status: deprecated
updated: '2026-05-19'
related:
- docs/plans/doctrine/org-doctrine-layer-architecture-review.md
---
# WP-Prompt Governance Contract — ATDD Findings

> **Retired (deprecated).** Design shipped via the org-doctrine-layer three-layer model (all 8 layer-rule tests pass; PRs #305/#348; drivers #832/#883/#1013/#391). Preserved as a historical record.

**Author:** Python Pedro
**Date:** 2026-05-16
**Test file:** `tests/specify_cli/next/test_wp_prompt_governance_contract.py`
**Related architecture review:** [org-doctrine-layer-architecture-review.md](../../../plans/doctrine/org-doctrine-layer-architecture-review.md) — sections "Process architecture", "Root cause", and "Empirical addendum".

---

## Purpose

These ATDD failing-first acceptance tests pin the contract for what the WP implement / review prompt must contain, so that the next mission has an executable specification to make pass. The tests encode the structural fixes called out in the architecture review's empirical addendum.

The test suite has nine substantive failures and fourteen passing wirings. The split is informative and is the input to the remediation mission spec.

---

## Test result summary (run on `feat/org-doctrine-layer` at `76c9f3b4`)

```
9 failed, 14 passed, 1 warning in 6.03s
```

### Passing (entry-point IS wired)

| Test | What it proves |
|---|---|
| `TestImplementPromptInvokesCharterPipeline::test_build_wp_prompt_for_implement_calls_governance_context` | The implement prompt builder DOES call `_governance_context(action="implement")`. |
| `TestImplementPromptInvokesCharterPipeline::test_build_wp_prompt_for_review_calls_governance_context` | Same for the review action. |
| `TestImplementPromptInvokesCharterPipeline::test_governance_context_output_is_present_in_wp_prompt_text` | Whatever `_governance_context` returns IS embedded in the final prompt. |
| `TestImplementPromptContainsActionableGovernance::test_implement_prompt_terminology_canon_body_or_fetch_with_when_doing_rule` | Passes incidentally because the fixture charter's body itself contains the phrase "canonical term for a unit of governed work is **Mission**". When a charter body explicitly contains the rule prose, that prose appears in the resolved context. |
| `TestImplementPromptContainsActionableGovernance::test_implement_prompt_is_not_only_section_anchors` | Negative-form check that the prompt is not pure anchor list — also passes incidentally. |
| `TestProfileDirectivesSurfacedInWpPrompt::test_python_pedro_directive_024_locality_referenced_in_implement_prompt` | Passes only because the fixture charter mentions "Locality of Change" in its body. |
| `TestProfileDirectivesSurfacedInWpPrompt::test_python_pedro_directive_030_test_typecheck_gate_referenced` | Passes only because the fixture charter mentions "Test and Typecheck Quality Gate". |
| `TestProfileDirectivesSurfacedInWpPrompt::test_reviewer_renata_directive_032_conceptual_alignment_in_review_prompt` | Passes only because the fixture charter explicitly cites DIRECTIVE_032. |
| `TestProfileDirectivesSurfacedInWpPrompt::test_reviewer_renata_tactic_language_driven_design_in_review_prompt` | Passes via the fixture charter body. |
| `TestProfileDirectivesSurfacedInWpPrompt::test_profile_directives_use_doctrine_catalog_namespace_in_prompt` | Passes because the fixture charter cites DIRECTIVE_032 in catalog form. |
| `TestCharterContextResolverCompleteness::test_implement_action_context_includes_terminology_canon_body` | Passes because the body is in the fixture charter. |
| `TestCharterContextResolverCompleteness::test_implement_action_context_includes_code_review_checklist_body` | Same. |
| `TestCharterContextResolverCompleteness::test_implement_action_context_emits_no_template_set_fallback_diagnostic` | Passes — fixture charter declares `template_set` explicitly. |
| `TestCharterContextResolverCompleteness::test_implement_action_context_includes_profile_directive_references_when_profile_known` | Passes because the fixture charter cites a catalog directive that matches the regex. |

**Interpretation.** The wired-but-passive entry point works fine *when the charter is hand-authored to include every rule the profiles would want.* The system relies on the operator to manually mirror profile-directive content into the charter prose. That defeats the purpose of having profile-declared directive references in the first place.

### Failing (substantive payload gaps)

These nine failures are the executable specification for the remediation mission:

| # | Test | Substantive gap |
|---|---|---|
| 1 | `TestImplementPromptContainsActionableGovernance::test_implement_prompt_regression_vigilance_body_or_fetch_with_when_doing_rule` | The prompt contains the "Regression Vigilance" section ANCHOR but not the body. No fetch + when-doing rule either. |
| 2 | `TestProfileDirectivesSurfacedInWpPrompt::test_python_pedro_directive_010_referenced_in_implement_prompt` | When the fixture charter does NOT explicitly cite DIRECTIVE_010 in its body, the system does not auto-surface it from the loaded profile's `directive-references`. The profile-declared link is silently ignored. |
| 3 | `TestPromptReferencesAuthorityPaths::test_implement_prompt_references_glossary_path` | No `docs/context/` pointer; no fetch command paired with a "when you introduce a term, consult …" rule. The implementer has no signposted way to discover the project glossary. |
| 4 | `TestPromptReferencesAuthorityPaths::test_implement_prompt_references_adr_path` | Same for `docs/adr/2.x/`. |
| 5 | `TestImplementTemplateForbidClauseIsHonest::test_template_either_drops_forbid_or_guarantees_governance_payload` | `src/specify_cli/missions/software-dev/command-templates/implement.md` still forbids the agent from calling `charter context` itself but does not declare a "Governance Payload Contract" that lists the bodies the prompt is guaranteed to carry. The trap from the architecture review is intact. |
| 6 | `TestCharterDirectiveNamespaceCrossLink::test_charter_sync_emits_cross_link_when_body_cites_catalog_id` | When the charter body cites DIRECTIVE_032, `spec-kitty charter sync` extracts a `DIR-NNN` entry but does not preserve a structured `references:` cross-link to the doctrine catalog ID. The two namespaces stay disconnected. |
| 7 | `TestPromptSelfSufficiency::test_implement_prompt_self_sufficiency` | Aggregate: prompt is missing `adr_pointer`, `regression_vigilance_body_or_fetch`, and `fetch_command_with_when_doing`. The implementer reading only the prompt cannot satisfy the architectural checks. |
| 8 | `TestProjectCharterDeclaresResolverInputs::test_project_charter_declares_template_set` | `.kittify/charter/charter.md` (this project's own charter) has no `template_set` declaration, so spec-kitty's own missions get the fallback diagnostic. |
| 9 | `TestProjectCharterDeclaresResolverInputs::test_project_charter_declares_available_tools` | Same for `available_tools`. |

---

## What the failures collectively say

Reading the nine failures as one statement: **the system invokes the right pipeline at the right boundary, but the pipeline emits only what the operator manually wrote into the charter prose.** Three classes of content are systematically lost between the data sources and the agent-facing prompt:

1. **Profile-declared directive and tactic references.** The agent profile YAML is a source of truth that says "this profile cares about these directives and tactics". The WP prompt never reads from that source. (Test 2 alone proves this; tests 6–10 in the passing list pass only because the fixture charter accidentally restates what the profile already says.)

2. **External authority paths.** Glossary and ADR locations are nowhere in the rendered prompt. The agent has no signposted way to discover the canonical source of project terminology or architectural intent. (Tests 3, 4.)

3. **Inter-namespace cross-links.** Charter-extracted `DIR-NNN` directives and doctrine-catalog `DIRECTIVE_NNN` directives are not linked at sync time, so the resolver cannot surface a catalog body when a charter `DIR-NNN` cites one by reference. (Test 6.)

Three additional structural problems compound:

4. **The runtime template's forbid clause is unhonest.** It tells the agent to trust the prompt as authoritative without listing what the prompt is contractually required to contain. (Test 5.)

5. **Anchor-only section listings give the appearance of governance without the substance.** "Regression Vigilance" appears in the prompt as a heading; the rules under that heading do not. (Test 1.)

6. **Spec-kitty's own charter (the dogfood case) under-specifies its resolver inputs.** Missing `template_set` and `available_tools` declarations cause the resolver to emit fallback diagnostics that obscure which directives the charter actually intends to inject. (Tests 8, 9.)

---

## How these findings map to the remediation mission spec

Translating the nine failures into mission-level requirements (the next step):

| Failure(s) | Functional requirement candidate |
|---|---|
| 1 | FR — The charter context resolver MUST embed the full body (or a fetch command + "when …" conditional) of every charter section whose anchor is included in the resolved context. |
| 2 | FR — When `build_charter_context(profile=...)` is called with a profile ID, the resolver MUST iterate `profile.directive_references` and `profile.tactic_references` and surface each (by ID + body, or by fetch + when-doing rule). |
| 3, 4 | FR — The resolved context for actions in `BOOTSTRAP_ACTIONS` MUST include a `Project authority paths:` block naming `docs/context/`, `docs/adr/2.x/`, and any project-charter-declared additional authority directories. |
| 5 | FR — The runtime implement template MUST contain either (a) no forbid clause, or (b) a "Governance Payload Contract" section that explicitly enumerates the body sections, profile directives, glossary pointer, and ADR pointer the prompt is guaranteed to carry. |
| 6 | FR — `spec-kitty charter sync` MUST detect catalog-namespace citations (`DIRECTIVE_NNN`, tactic IDs) inside extracted directive bodies and emit a structured `references:` cross-link field in `.kittify/charter/directives.yaml`. |
| 7 | FR — Aggregate self-sufficiency: the rendered prompt for `implement` and `review` MUST satisfy the contracts above for every action invocation in a software-dev mission. |
| 8, 9 | FR — Operator-facing: spec-kitty's own `.kittify/charter/charter.md` MUST declare `template_set` and `available_tools` in machine-readable form (either YAML front-matter or a fenced YAML block parsed by `charter sync`). |

Plus one cross-cutting non-functional requirement:

| Failure | NFR candidate |
|---|---|
| All | NFR — The augmented governance payload MUST not bloat the WP prompt beyond a budget that keeps the prompt comfortably under the agent's prompt-token allowance for a typical software-dev WP. Tokens spent on governance must be measured; if a payload exceeds the budget, the system MUST automatically substitute fetch commands for the longest sections. |

---

## Suggested mission name

`wp-prompt-governance-payload` (mission slug: `wp-prompt-governance-payload-<ulid>`)

Mission target branch: **`feat/org-doctrine-layer`** (the current branch — the next mission stays on the same integration branch so the post-merge mission-review can audit both deliverables together before the integration branch is promoted).

---

## Self-test discipline

Per the architectural review's "dogfood gap" framing, the success criterion for this mission is **not** that the tests turn green. It is that, after the mission ships, the **next** mission run on spec-kitty itself — any next mission — surfaces in its WP prompts:

- the loaded profile's directive and tactic references,
- the project glossary path,
- the ADR path,
- the body (or fetch + when-doing) of every charter section critical to the action.

The test suite is the executable contract; satisfying it is necessary but not sufficient. Satisfying it on spec-kitty's own missions is the acceptance test that has previously been missing.
