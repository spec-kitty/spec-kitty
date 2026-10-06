---
name: spec-kitty-spdd-reasons
description: >-
  Drive REASONS Canvas authoring and review for Spec Kitty missions that
  opted in to Structured-Prompt-Driven Development (SPDD) via charter
  selection.
  Triggers: "use SPDD", "use REASONS", "generate a REASONS canvas",
  "apply structured prompt driven development", "make this mission SPDD".
  Does NOT handle: enforcing SPDD on projects whose charter has not
  selected the doctrine pack (escalate to charter workflow instead). Does
  NOT mirror code as prose; code remains the source of truth for current
  behavior.
---

# spec-kitty-spdd-reasons

Drive REASONS Canvas authoring and review for missions that opted in to
Structured-Prompt-Driven Development (SPDD) via charter selection. The
canvas is a thin, agent-curated reasoning layer that sits next to the spec,
plan, and tasks; it is **not** a duplicate system mirror.

This skill is documentation for the agent. It assumes the SPDD/REASONS
doctrine pack (paradigm, tactics, styleguide, directive, template) has
already been shipped under `src/charter/offering/` and that activation can be
detected via the helper described below.

---

## What this skill does

- Detects whether the SPDD/REASONS pack is active for the current project.
- Loads mission context: `spec.md`, `plan.md`, `tasks.md`, per-WP prompts,
  charter context, glossary, research notes, contracts, and relevant code.
- Generates or updates `kitty-specs/<mission>/reasons-canvas.md` from the
  seven-section template fragment.
- Compiles per-WP REASONS summaries when an implementer or reviewer asks
  for one (a focused slice of the canvas scoped to a single work package).
- Runs comparison-mode review: traces a diff against the canvas and
  classifies divergences using the drift taxonomy.

## What this skill does NOT do

- It does NOT mirror the code as prose. The canvas references source
  artifacts; it does not duplicate them. Code remains the source of truth
  for current behavior.
- It does NOT overwrite user-authored mission artifacts. When a canvas
  section already contains user content, the skill **merges** by appending
  or refining, never by silent rewrite.
- It does NOT silently enforce SPDD on projects that did not opt in via
  charter. If the user demands enforcement and the charter is not
  configured, escalate to the charter workflow.

## Activation rules

Three branches:

1. **Active** — charter selected the SPDD/REASONS pack (paradigm
   `structured-prompt-driven-development`, tactic `reasons-canvas-fill`,
   tactic `reasons-canvas-review`, or directive `DIRECTIVE_038`). Proceed
   with canvas authoring or review using the seven-section template at
   `src/charter/offering/templates/fragments/reasons-canvas-template.md`.
2. **Inactive + ad-hoc request** — user asked to "use REASONS" once,
   without charter opt-in. Proceed, but stamp the canvas header with a
   "not formally opted in via charter" note so reviewers know the canvas
   is advisory only.
3. **Inactive + enforcement demand** — user wants REASONS enforced as a
   gate but the charter has not selected the pack. Do NOT enforce. Escalate
   to the charter workflow: suggest running the charter interview to add
   the paradigm or directive, then return to this skill.

## How to detect activation

Programmatic (preferred):

```python
from charter.offering.spdd_reasons.activation import is_spdd_reasons_active

active = is_spdd_reasons_active(repo_root)
```

The helper inspects the project's active charter -- the top-level
`activated_paradigms`, `activated_tactics` and `activated_directives` keys in
`.kittify/config.yaml`, or in the `charter.yaml` its `charter:` pointer names --
and returns `True` iff any of the four selectors is present:

- paradigm `structured-prompt-driven-development`
- tactic `reasons-canvas-fill`
- tactic `reasons-canvas-review`
- directive `DIRECTIVE_038`

Manual fallback: read `.kittify/config.yaml` (or the `charter.yaml` its
`charter:` pointer names) directly and look for the same selectors under
`activated_paradigms`, `activated_tactics`, or `activated_directives`.

## How to author the canvas

1. **Read mission artifacts**: `kitty-specs/<mission>/spec.md`, `plan.md`,
   `tasks.md`, per-WP prompts, `research/*`, `contracts/*`, the project
   glossary, and any source files the spec or plan calls out.
2. **Map content to the seven sections** using the template at
   `src/charter/offering/templates/fragments/reasons-canvas-template.md`:
   - **Requirements** — problem statement, acceptance criteria, DoD.
   - **Entities** — domain concepts, relationships, canonical glossary
     terms.
   - **Approach** — selected strategy and tradeoffs considered.
   - **Structure** — code surfaces affected, components, dependencies,
     ownership boundaries.
   - **Operations** — ordered implementation steps, test strategy.
   - **Norms** — coding/style conventions, observability and team rules.
   - **Safeguards** — hard constraints, security rules, performance limits,
     things not to break.
3. **Link, don't duplicate**: prefer `[see spec.md §X](../spec.md#x)` over
   inlining spec content. The canvas is a reasoning layer, not a copy.
4. **Preserve user content**: if the canvas already exists, read it before
   writing. Merge new content into existing sections; never blow away
   user-authored prose.
5. **Append-only Deviations**: the `## Deviations` section is append-only.
   New entries go at the bottom in the form
   `- <date> — <wp> — <description> — <rationale>`. Never rewrite or
   re-order existing entries.

Output path: `kitty-specs/<mission>/reasons-canvas.md`.

## How to review with the canvas

Comparison-mode review pairs an implementation diff against the canvas:

1. **Trace** every changed file in the diff to a Requirement and an
   Operation step in the canvas. Unmapped changes are signal.
2. **Detect** uninvented entities — files, functions, modules, or domain
   terms that appear in the diff but not in the canvas, the spec, the
   plan, or the glossary.
3. **Verify** the diff respects the canvas Norms and Safeguards
   (style/observability/security/performance/invariants).
4. **Classify** every divergence using the drift taxonomy from
   `data-model.md §Drift classification`:
   - `approved` — diff matches canvas exactly.
   - `approved_with_deviation` — small, documented divergence; record in
     the canvas Deviations section.
   - `canvas_update_needed` — implementation is correct, canvas is stale.
   - `glossary_update_needed` — new canonical term surfaced; escalate to
     glossary skill.
   - `charter_follow_up` — divergence touches charter policy; escalate.
   - `follow_up_mission` — divergence is real but out of scope for this
     mission; file a follow-up.
   - `scope_drift_block` — diff exceeds mission scope; block.
   - `safeguard_violation_block` — diff violates a Safeguard; block hard.

Surface the classification in the review output. Two of the eight
classifications (`scope_drift_block`, `safeguard_violation_block`) block
landing; the rest are advisory or escalate.

## Charter precedence

The charter is the governance source of truth. If a directive, tactic, or
norm declared in the charter conflicts with content in the canvas, the
charter wins. The canvas must update; the charter does not. Treat any
canvas claim that contradicts the charter as `canvas_update_needed`.

## Glossary discipline

When canvas authoring or review surfaces a term that is missing,
ambiguous, or in conflict with the project glossary, do NOT redefine the
term inline. Escalate to the glossary skill (`spec-kitty-glossary-context`)
so the canonical entry is updated once and propagated everywhere.

---

## Reference paths

- Template fragment:
  `src/charter/offering/templates/fragments/reasons-canvas-template.md`
- Activation helper:
  `src/charter/offering/spdd_reasons/activation.py` (`is_spdd_reasons_active`)
- Activation authority:
  `.kittify/config.yaml` (or the `charter.yaml` its `charter:` pointer names)
- Drift taxonomy:
  `kitty-specs/<mission>/data-model.md §Drift classification`
