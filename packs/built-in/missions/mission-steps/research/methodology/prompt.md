---
description: Design and document a reproducible research methodology from the locked spec
---
# Methodology Design — Lock the Research Approach

**Mission type**: `research` | **Step**: `methodology` (sequence index 1, depends on `scoping`) | **Agent profile**: `researcher-robbie`

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/plan.md`). Never refer to a file by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be `mission_id`, `mid8`, or `mission_slug`; ambiguity returns `MISSION_AMBIGUOUS_SELECTOR` rather than silently guessing.

## User Input

```text
$ARGUMENTS
```

Consider any refinement in `$ARGUMENTS`, but treat it as secondary to `kitty-specs/<mission>/spec.md` — the spec is the locked contract for this phase.

## Bootstrap

```bash
spec-kitty charter context --action methodology --json
```

## What This Step Produces

`kitty-specs/<mission>/plan.md`, rendered from `research-plan-template.md`. This is the gate on `methodology -> gathering` (`mission.yaml`: `artifact_exists("plan.md")`). A `plan.md` that exists but lists an approach with no concrete search strategy or analysis framework has satisfied the filesystem gate while failing this step's actual purpose.

## Read the Locked Spec First

- Read `kitty-specs/<mission>/spec.md` in full before writing anything. The research question, scope boundaries, and research type were locked at scoping — this phase designs *how* to answer the question, not *whether* the question is still the right one.
- If the spec's boundaries turn out to be infeasible with available data sources, that is a scoping gap, not a license to quietly redefine scope here. Flag it explicitly rather than silently narrowing.

## Core Authorship Focus

- Choose a **research approach** explicitly: Systematic Literature Review, Survey, Experiment, Case Study, Mixed Methods, or Review-of-Reviews. Name the framework you are following — do not invent an unnamed ad-hoc procedure.
- Document methodology decisions as **ADR-shaped artifacts** (`003-decision-documentation-requirement`): the choice, the rationale, the alternatives considered, the trade-offs accepted.
- Write for **reproducibility and peer review** — a reader who has not done this research must be able to redo it from `plan.md` alone.

## Methodology Components to Lock Down

- **Phases and timeline** — name each phase (question formation, gathering, analysis, synthesis, publication) and the deliverable that ends it.
- **Data sources** — which databases, repositories, or populations; distinguish primary from secondary sources.
- **Search strategy** — keywords, inclusion criteria, exclusion criteria. A vague search strategy produces a non-reproducible review.
- **Analysis framework** — coding scheme, synthesis method (thematic analysis, meta-analysis, narrative synthesis), and quality assessment approach.
- **Quality criteria** — how source quality will be evaluated and how confidence levels will be assigned; this is what `research-citation-discipline`'s evidence-tiering later depends on.

## Reproducibility Standards

- Every methodology decision must be **traceable** — a later reader finds the rationale in `plan.md`, without asking the original researcher.
- **Cite the framework** you are following (e.g., PRISMA for systematic reviews) rather than inventing an ad-hoc procedure.
- Where you deviate from a standard framework, document the deviation and why.
- **Pre-register exclusion criteria.** Adjusting exclusion criteria after seeing results is a validity threat, not a refinement — write them down before gathering starts.

## What This Phase Does NOT Cover

The methodology step locks the research design. It does **not**:

- Re-open the research question or scope (`scoping` decisions are locked).
- Begin source gathering or evidence extraction (`gathering` step's job).
- Draw conclusions or synthesize findings (`synthesis` step's job).
- Format publication output (`output` step's job).

A methodology document that already cites specific findings is a leaked synthesis. Keep the phases clean.

## What To Do

1. Read `kitty-specs/<mission>/spec.md`.
2. Fill `kitty-specs/<mission>/plan.md` (from `research-plan-template.md`): research approach, phases and timeline, primary/secondary data sources, search strategy (keywords, inclusion criteria, exclusion criteria), analysis framework, and quality criteria.
3. Record each non-obvious methodology choice as a decision entry — the alternative considered and why it was rejected.
4. Cross-check the minimum-source floor the `gathering` step will be held to (`event_count("source_documented", 3)` in `mission.yaml`) and set a real target above that floor in the plan, driven by the scoping success criteria — three is a machine-enforced floor, not a target.
5. Commit `plan.md` per the `029-agent-commit-signing-policy` / `033-targeted-staging-policy` directives.

## Quality Gates

- The methodology specifies enough detail that an independent researcher could reproduce the gathering and analysis.
- Each major design choice is documented as a decision with rationale.
- Inclusion and exclusion criteria are concrete (not "relevant sources").
- The chosen framework is named, and any deviations from it are explicit.
- `plan.md` exists **and** is substantive — satisfying `artifact_exists("plan.md")` without a real search strategy is a gate pass that fails this step's intent.
