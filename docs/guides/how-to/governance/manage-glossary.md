---
title: How to Manage the Glossary
description: Curate canonical terminology, resolve conflicts, and configure strictness enforcement.
doc_status: active
updated: '2026-10-08'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/context/charter-overview.md
- docs/guides/how-to/missions/create-specification.md
- docs/guides/how-to/installation/install-spec-kitty.md
- docs/guides/how-to/missions/switch-missions.md
- docs/guides/how-to/governance/synthesize-doctrine.md
---
# How to Manage the Glossary

The glossary keeps terminology consistent across all mission artifacts. Every term has a surface form (the word itself), a definition, a scope that determines its precedence, a confidence score, and a status. When the runtime detects a conflict between a term used in an artifact and its glossary definition, it can block generation until you resolve the inconsistency.

This guide covers listing terms, resolving conflicts, editing seed files, and configuring strictness enforcement.

## Prerequisites

- A spec-kitty project initialized with `spec-kitty init`
- Glossary seed files present under `.kittify/glossaries/`

---

**Quick Navigation**: [Glossary Concepts](#glossary-concepts) | [Listing Terms](#listing-terms) | [Viewing Conflicts](#viewing-conflicts) | [Resolving Conflicts](#resolving-conflicts) | [Strictness Modes](#strictness-modes) | [Editing Seed Files](#editing-seed-files) | [See Also](#see-also)

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `spec-kitty glossary list` | List all terms across scopes |
| `spec-kitty glossary list --scope team_domain --status active` | Filter by scope and status |
| `spec-kitty glossary list --json` | Machine-readable JSON output |
| `spec-kitty glossary conflicts` | Show all conflict history |
| `spec-kitty glossary conflicts --unresolved` | Show only unresolved conflicts |
| `spec-kitty glossary resolve <conflict-id>` | Resolve a conflict interactively |

## Glossary Concepts

### Terms and Senses

A glossary **term** is identified by its **surface** -- a normalized lowercase string like `work package` or `deployment`. Each term has:

- **definition** -- what the term means in your project
- **scope** -- where the term lives in the precedence hierarchy
- **confidence** -- a float from 0.0 to 1.0 indicating certainty (1.0 for human-curated terms, lower for auto-extracted)
- **status** -- lifecycle state: `draft`, `active`, or `deprecated`

### 4 Scopes

Terms are organized into four scopes. When the same surface exists in multiple scopes, the narrowest scope wins:

| Precedence | Scope | Use For |
|:---:|---|---|
| 0 (highest) | `mission_local` | Feature-specific jargon (e.g., "widget" meaning a specific UI component in this feature) |
| 1 | `team_domain` | Team or organization conventions (e.g., "sprint" meaning a 2-week iteration) |
| 2 | `audience_domain` | Industry or domain standards (e.g., "deployment" in DevOps) |
| 3 (lowest) | `spec_kitty_core` | Framework terms like "lane", "work package", "mission" |

For example, if `deployment` is defined in both `team_domain` and `audience_domain`, the `team_domain` definition takes precedence during conflict resolution.

### Status Lifecycle

Every term follows a three-state lifecycle:

```
draft  -->  active  -->  deprecated
  ^                          |
  +--------------------------+
         (re-draft)
```

- **draft** -- newly added or auto-extracted, not yet reviewed
- **active** -- promoted by a human, used in conflict resolution
- **deprecated** -- retired from active resolution but preserved in event history

Deprecated terms are excluded from conflict resolution but remain in the glossary for audit purposes.

## Listing Terms

List all terms across all scopes:

```bash
spec-kitty glossary list
```

Example table output:

```
                    Glossary Terms
+------------------+--------------+----------------------------+--------+------------+
| Scope            | Term         | Definition                 | Status | Confidence |
+------------------+--------------+----------------------------+--------+------------+
| mission_local    | widget       | The sidebar config panel    | active |       1.00 |
| team_domain      | deployment   | Releasing code to prod      | active |       1.00 |
| team_domain      | sprint       | A 2-week iteration cycle    | active |       0.90 |
| spec_kitty_core  | lane         | A status column on the ...  | active |       1.00 |
| spec_kitty_core  | work package | A unit of implementable ... | active |       1.00 |
+------------------+--------------+----------------------------+--------+------------+

Total: 5 term(s)
```

### Filter by Scope

Show only terms from a specific scope:

```bash
spec-kitty glossary list --scope team_domain
```

Valid scope values: `mission_local`, `team_domain`, `audience_domain`, `spec_kitty_core`.

### Filter by Status

Show only active terms:

```bash
spec-kitty glossary list --status active
```

Valid status values: `active`, `deprecated`, `draft`.

### Combine Filters

```bash
spec-kitty glossary list --scope team_domain --status active
```

### JSON Output

For scripting or piping to other tools:

```bash
spec-kitty glossary list --json
```

Example JSON output:

```json
[
  {
    "surface": "deployment",
    "scope": "team_domain",
    "definition": "The process of releasing code to production",
    "status": "active",
    "confidence": 1.0
  },
  {
    "surface": "lane",
    "scope": "spec_kitty_core",
    "definition": "A status column on the kanban board",
    "status": "active",
    "confidence": 1.0
  }
]
```

You can combine `--json` with scope and status filters:

```bash
spec-kitty glossary list --scope spec_kitty_core --status active --json
```

## Viewing Conflicts

When the glossary runtime detects terminology issues during mission execution, it records them as conflicts in the event log. View the conflict history:

```bash
spec-kitty glossary conflicts
```

Example table output:

```
                              Conflict History
+--------------+------------+---------+----------+------------+...
| Conflict ID  | Term       | Type    | Severity | Status     |...
+--------------+------------+---------+----------+------------+...
| a1b2c3d4e5.. | widget     | UNKNOWN | HIGH     | unresolved |...
| f6g7h8i9j0.. | deployment | AMBIGU  | HIGH     | resolved   |...
+--------------+------------+---------+----------+------------+...

Total: 2 conflict(s)
Unresolved: 1
```

### Show Only Unresolved

```bash
spec-kitty glossary conflicts --unresolved
```

### Filter by Mission

```bash
spec-kitty glossary conflicts --mission 012-documentation-mission
```

### Filter by Strictness

```bash
spec-kitty glossary conflicts --strictness max
```

### JSON Output

```bash
spec-kitty glossary conflicts --json
```

You can combine filters:

```bash
spec-kitty glossary conflicts --unresolved --mission 012-documentation-mission --json
```

## Resolving Conflicts

When a conflict blocks mission execution, resolve it using the conflict ID from `spec-kitty glossary conflicts`:

```bash
spec-kitty glossary resolve a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The resolver presents candidate senses and prompts you for a resolution:

```
Conflict: a1b2c3d4-e5f6-7890-abcd-ef1234567890
Term: widget
Type: UNKNOWN
Severity: HIGH

Candidate senses:
  1. [mission_local] The sidebar configuration panel
  2. [audience_domain] A generic UI element

Enter 1-2 to select a candidate, 'C' for custom definition, 'D' to defer
Resolution: _
```

Your options:

- **Enter a number** to select an existing candidate sense
- **Enter `C`** to provide a custom definition (creates a new sense and records it in the event log)
- **Enter `D`** to defer the conflict without resolving it

### Scope a Resolution to a Mission

```bash
spec-kitty glossary resolve a1b2c3d4-e5f6-7890-abcd-ef1234567890 --mission 012-docs
```

If you omit `--mission`, the command auto-detects the mission from the conflict event.

## Strictness Modes

Strictness controls whether unresolved conflicts block mission execution. There are three modes:

| Mode | Behavior |
|------|----------|
| `off` | Glossary never blocks mission execution. Conflicts are recorded but ignored. |
| `medium` (default) | Blocks only when HIGH severity conflicts are unresolved. |
| `max` | Blocks on any unresolved conflict, regardless of severity. |

### When Does Each Mode Make Sense?

- **`off`** -- Early prototyping where you want speed over consistency. Conflicts still accumulate in the event log for later review.
- **`medium`** -- Day-to-day development. High-severity conflicts (unknown critical terms, ambiguous terms in critical steps) block generation; lower-severity issues pass through.
- **`max`** -- Pre-release hardening or compliance-sensitive projects. Every terminology inconsistency must be resolved before generation proceeds.

### Configuring Strictness

Set the global default in `.kittify/config.yaml`:

```yaml
glossary:
  strictness: medium
```

Change it to any of the three values (`off`, `medium`, `max`). The setting takes effect on the next mission step execution.

### Precedence Chain

Strictness can be overridden at multiple levels. From highest to lowest precedence:

1. **Runtime flag** -- CLI `--strictness` argument
2. **Step metadata** -- `glossary_check_strictness` in a step definition
3. **Mission config** -- strictness set in the mission's configuration
4. **Global default** -- `.kittify/config.yaml` (the setting described above)

The most specific override wins. For example, if your global default is `medium` but a particular step sets `glossary_check_strictness: max`, that step uses `max`.

## Editing Seed Files

Seed files are YAML files in `.kittify/glossaries/` -- one per scope. They provide the initial set of terms before any runtime events are applied.

### Seed File Location

| Scope | File Path |
|-------|-----------|
| `mission_local` | `.kittify/glossaries/mission_local.yaml` |
| `team_domain` | `.kittify/glossaries/team_domain.yaml` |
| `audience_domain` | `.kittify/glossaries/audience_domain.yaml` |
| `spec_kitty_core` | `.kittify/glossaries/spec_kitty_core.yaml` |

### YAML Schema

Each seed file contains a `terms` list. Each term requires `surface` and `definition`; `confidence` and `status` are optional with defaults:

```yaml
terms:
  - surface: deployment
    definition: The process of releasing code to production
    confidence: 1.0       # optional, default 1.0
    status: active         # optional, default draft

  - surface: rollback
    definition: Reverting a deployment to the previous release
    confidence: 0.9
    status: active

  - surface: canary release
    definition: Deploying to a small subset of users before full rollout
    status: draft
```

### Validation Rules

- **surface** -- must be lowercase and trimmed (e.g., `work package`, not `Work Package` or ` work package `)
- **definition** -- must be a non-empty string
- **confidence** -- float between 0.0 and 1.0
- **status** -- one of `active`, `deprecated`, or `draft`

### Choosing the Right Scope

Pick the scope based on who "owns" the term:

- **Feature-specific jargon** that only makes sense within a single feature: `mission_local.yaml`
- **Team or organizational conventions** shared across features: `team_domain.yaml`
- **Industry-standard terminology** your audience expects: `audience_domain.yaml`
- **Spec Kitty framework terms** like "lane" or "work package": `spec_kitty_core.yaml` (rarely edited by users)

### Adding a New Term

1. Open the appropriate seed file for the term's scope.
2. Add a new entry under `terms`:

```yaml
terms:
  # existing terms...
  - surface: service mesh
    definition: Infrastructure layer handling service-to-service communication
    confidence: 1.0
    status: active
```

3. Save the file. The term is available immediately on the next `spec-kitty glossary list`.

### Deprecating a Term

Change the term's status to `deprecated`:

```yaml
  - surface: legacy api
    definition: The v1 REST API, superseded by v2
    status: deprecated
```

Deprecated terms remain in the seed file for audit but are excluded from conflict resolution.

## Detecting Term Drift

Over time, artifacts may gradually diverge from glossary definitions. Catch drift early:

1. **Compare definitions against specs**: Run `spec-kitty glossary list --json` and check whether your spec, plan, and task files use terms consistently.

2. **Check for unresolved conflicts**: Run `spec-kitty glossary conflicts --unresolved` to see terms the runtime flagged.

3. **Watch for informal synonyms**: If your glossary defines "work package" but artifacts use "task" or "ticket", add those synonyms to the glossary or correct the artifacts.

### Correcting Drift

- **Artifact is wrong**: Replace the informal term with the canonical surface form.
- **Glossary is outdated**: Update the seed file definition to match current usage.
- **Genuinely ambiguous**: Add a second sense and let the strictness system force disambiguation during mission execution.

---

## Charter 3.x: Glossary Integration with Governance

In Charter 3.x, the glossary is integrated with the governance layer. This section covers the
four aspects of that integration.

For background on the Charter model, see [How Charter Works](../../../context/charter-overview.md).

### Glossary as runtime doctrine

Spec Kitty exposes active glossary terms as part of the doctrine/DRG context so agents receive
consistent terminology during governed work. When a governed mission action is run via
`spec-kitty next`, the prompt can include glossary terms relevant to the current action.

To add a durable glossary term:

1. Add the term to the appropriate seed file under `.kittify/glossaries/`.
2. Run `spec-kitty glossary list --scope <scope>` to verify the term is active.
3. Run `charter synthesize` if your project-local doctrine/DRG overlay also needs to be refreshed:
   ```bash
   uv run spec-kitty charter synthesize
   ```
4. Validate the governance bundle and synthesis state:
   ```bash
   uv run spec-kitty charter bundle validate
   uv run spec-kitty charter status
   ```

### Glossary and the DRG

Active glossary terms are represented as glossary nodes in the Directive Relationship Graph
(DRG). The glossary DRG builder adds vocabulary edges from action nodes to active glossary terms,
making those terms reachable as part of action-scoped context.

For example, a term like `lifecycle-terminus` can be made available to governed prompts through
the glossary store and DRG vocabulary layer, ensuring the agent sees the project-canonical
definition when the context builder includes glossary material.

### Glossary as project-local doctrine

The durable glossary seed files live under `.kittify/glossaries/`. Those files are the operator
curation surface for glossary CLI workflows. Retrospective synthesis may also write project-local
glossary overlay files under `.kittify/glossary/`.

Adding or changing a durable term usually means:

1. Editing the appropriate `.kittify/glossaries/<scope>.yaml` seed file.
2. Re-running `spec-kitty glossary list` to verify it loads.
3. Re-running `charter synthesize` when the project layer needs to reflect the change.

Do not add terms by editing generated doctrine files under `.kittify/charter-packs/` directly.

### Glossary and retrospective proposals

The retrospective synthesizer can emit glossary-change proposals (`add_glossary_term`,
`update_glossary_term`) when the retrospective facilitator identifies terms that were missing
or incorrect during a mission.

Preview proposals for a completed mission:
```bash
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug
```

Sample output showing a glossary proposal:
```
Mode: dry-run (default)

Planned applications: 1
  ✔ P1  add_glossary_term  "lifecycle-terminus-hook"  (scope: team_domain)

Apply: not run (use --apply to mutate)
```

Apply accepted proposals:
```bash
uv run spec-kitty agent retrospect synthesize --mission my-feature-slug --apply
```

When `--apply` is used, accepted glossary proposals are written to the project-local glossary
overlay under `.kittify/glossary/` with provenance sidecars. If you want the change to become
part of the durable curated glossary, port it into the appropriate `.kittify/glossaries/<scope>.yaml`
seed file. Run `charter synthesize` afterward when the DRG/project layer should reflect the
updated terms:
```bash
uv run spec-kitty charter synthesize
```

---

## See Also

- [How to Synthesize and Maintain Doctrine](synthesize-doctrine.md) -- Propagate glossary changes
- [How Charter Works](../../../context/charter-overview.md) -- Charter mental model
- [Understanding the Retrospective Learning Loop](../../../architecture/retrospective-learning-loop.md) -- How proposals flow from retrospectives to glossary
- [Create a Specification](../missions/create-specification.md) -- Where terms first appear in your workflow
- [Switch Missions](../missions/switch-missions.md) -- Mission-level glossary configuration
- [Install and Upgrade](../installation/install-spec-kitty.md) -- Initial project setup including glossary initialization

## Background

- [Spec-Driven Development](../../../architecture/spec-driven-development.md) -- The philosophy behind terminology-driven workflows
