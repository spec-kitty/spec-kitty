---
name: spk-doctrine-show-me
description: "Explain Spec Kitty work with compact, checkable visuals. Use for specs, plans, architecture, control flow, diffs, status boards, or whenever prose obscures structure."
---

# spk-doctrine-show-me

Make the current point visible. Skip the preamble, keep prose brief, and pick
the smallest representation that answers the question. Do not add a diagram
when a sentence or short list is clearer.

## Choose the Shape

- Logic or an algorithm: compact pseudocode.
- Runtime behavior: call tree or sequence diagram.
- UI composition: component tree with only relevant state and boundaries.
- Ownership or refactor scope: shallow file tree with one responsibility per entry.
- Existing-to-proposed change: `diff` over the matching tree, flow, or pseudocode.
- Domain lifecycle: state diagram.
- Data or concept relationships: entity-relationship or class diagram.
- Architecture: C4 Context first, then Container or Component only when useful.
- Dense visual UI/layout comparison: one focused HTML artifact when the host can
  open it; keep durable project documentation diagram-as-code.

Place each visual beside the text it supports. Include only the calls, files,
states, relationships, and boundaries needed for the current decision. Label
relationships and preserve source paths or identifiers that make the visual
checkable against code and artifacts.

## Load Spec Kitty's Diagram Doctrine

Prefer Mermaid inline; use PlantUML when richer layout, C4 support, or its DSL
earns the rendering cost. Read `references/spec-kitty-diagram-sources.md`, then
load only the needed toolguide, directive, or tactic through `spec-kitty charter
context --include ...`. It maps portable commands to the canonical Mermaid and
PlantUML guides, C4 directive, diagram-review tactic, and bundled theme assets.

In specification, visualize actor flows, concepts, rules, and lifecycle states;
do not smuggle implementation choices into product requirements. In planning,
visualize architecture, data/control flow, boundaries, migrations, and risky
interactions. Prose requirements and contracts remain authoritative.

## Render `/spec-kitty.status` in a TUI

Use the command's Rich human output in a capable terminal. For a custom TUI,
consume structured data instead of scraping ANSI output:

```bash
spec-kitty agent tasks status --json --mission <handle>
```

Keep lifecycle truth distinct from the current status display projection:

```text
planned → claimed → in_progress → for_review → in_review → approved → done
Display: Planned → Doing → For Review → Approved → Done
```

For the five-group display only, fold `claimed`, `in_progress`, and `in_review`
into **Doing** and mark claimed/review entries. Read blocked/canceled from
`work_packages[].lane`, stale from `work_packages[].is_stale`, and review
warnings from `stalled_wps` and `stale_verdicts`; show them off-board. On narrow
screens, stack the same groups vertically.

Show **Done progress** (`done_count / total_wps`) separately from **Weighted readiness**
(`progress_percentage`). Never label weighted readiness as completed
work. JSON has no `next_action`: reproduce the human hint from `mission_slug` as
`spec-kitty next --agent <your-name> --mission <mission_slug>`, with the caller
supplying the agent. That command—not status—selects the exact workflow action.

## Origin and Attribution

Adapted from HumanLayer's MIT-licensed `show-me` skill by Dexter Horthy:
<https://github.com/humanlayer/skills/tree/main/plugins/show-me/skills/show-me>.
The source article also credits Dillon Mulroy for the call-tree shape and Matt
Pocock for HTML-explainer inspiration. Preserve the notice and provenance in
`references/humanlayer-origin-and-license.md` when redistributing this skill.
