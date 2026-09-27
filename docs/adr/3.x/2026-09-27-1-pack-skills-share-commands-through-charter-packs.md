---
title: 'ADR: pack skills — share and co-maintain agent commands through charter packs'
description: 'Proposed: a charter-activatable `skill` doctrine kind so teams share and co-maintain agent commands through pack tiers, not private per-user copies.'
status: Proposed
date: '2026-09-27'
---

**Status:** Proposed

**Date:** 2026-09-27

**Deciders:** Stijn Dejongh (owner). Design produced by a profile-loaded research and
architecture squad: `researcher-robbie` (prior art), `architect-alphonso` (design),
`doctrine-daphne` (doctrine integrity), `paula-patterns` (second-opinion adjudication).

**Technical Story:** tracker issue to follow (filed by `planner-priti`, referencing this ADR).

---

## Context and Problem Statement

Spec Kitty's vision is governed, shared, consistent AI usage. Doctrine already delivers that
for *rules and techniques*: directives, tactics, procedures, and profiles live in pack tiers
(`packs/built-in/` for consumers, org packs such as `packs/internal/` for a team, and the
project's `.kittify/doctrine/`), are merged by `merge_three_layers`
(`src/charter/offering/drg/merge.py`), and are switched on per project through
`spec-kitty charter activate`.

There is no equivalent for the **entry points** people actually type. The shorthands a team
relies on (for this repository: landing a contributor PR, driving a mission from an issue,
triaging the tracker, curating memory) live as private, per-user agent skills. The research
pass found:

- **No pack can ship a skill or command today.** `SkillRegistry` reads one package root
  (`src/specify_cli/skills/registry.py:66-93`); the command-skill set is a closed tuple with a
  parity assert (`src/specify_cli/skills/command_installer.py:81-106`); every rendered command
  is forced to `spec-kitty.<cmd>` (`src/specify_cli/skills/command_renderer.py:468`).
- **No doctrine concept exists** for a skill, command, alias, or shorthand, and no ADR, spec,
  or plan discusses shareable entry points.
- **The private copies duplicate doctrine and drift.** The landing shorthand restates the
  internal procedure `landing-contributor-prs`
  (`packs/internal/procedures/landing-contributor-prs.procedure.yaml`) and already cites a doc
  path that does not exist (`docs/development/pr-landing.md`; the page is
  `docs/development/how-to/pr-landing.md`). Memory curation restates
  `memory-curation-and-escalation`; triage restates the built-in
  `tracker-organisation-workflow` and `issue-triage-state-machine` procedures.
- **They hard-code people and places** (an operator handle, the repository slug, check
  names) and **squat on the built-in `spk-` namespace** (`src/charter/offering/skills/README.md`,
  "Naming Convention").

A second, drifting, unreviewed copy of doctrine per person is exactly what the charter's
*single canonical authority* principle forbids. Sharing a shorthand today means pasting it
into someone else's account.

## Decision Drivers

- **Single canonical authority** (`DIRECTIVE_044`): the substance stays in procedures; the
  entry point must reference it, not restate it.
- **Relationships are DRG edges, not fields.** ADR
  [2026-07-26-1](2026-07-26-1-drg-edges-are-the-canonical-relationship-authority.md) treats inline
  `references:` as pre-DRG residue (pinned by `tests/architectural/test_reference_enum_ratchet.py`);
  C-009 says the same for profile lineage.
- **One activation authority.** The only non-kind activatable token today, `mission-type`, is
  recorded as debt awaiting promotion (ADR [2026-08-05-1](2026-08-05-1-mission-type-availability-before-kind-promotion.md)). A second outlier would be a
  parallel authority.
- **Pack-tier boundary** (ADR [2026-08-16-3](2026-08-16-3-spec-kitty-internal-is-a-public-org-pack-not-force-shipped.md)): in-house shorthands must never ship in the wheel.
- **Terminology canon:** do not add an eighth sense of "command" or a fifth of "alias".
- **Every configured tool**, not one harness: 13 slash-command tools plus 4 Agent Skills tools.
- **Trust:** a shared prompt runs with the tool's repository permissions.

## Considered Options

1. **New doctrine kind `command`** ("Pack Command"; forms `full | alias`), DRG-wired and
   charter-activatable (architect's draft).
2. **No new kind: "pack skills" on the existing skill surface**, installed whenever their bound
   procedure is active, with the binding in SKILL.md frontmatter (doctrine-integrity lens).
3. **New doctrine kind `skill`** (URN `skill:<id>`, prose "pack skill"; forms `prompt | wrapper`),
   DRG-wired, charter-activatable, projected by the managed doctrine-skill installer
   (adjudicated synthesis of 1 and 2).
4. Make procedures directly invocable (`invocable: true` on `procedure`).
5. Tool-native plugin marketplaces (for example Claude Code plugins).

## Decision Outcome

**Chosen option: 3, a charter-activatable `skill` doctrine kind.** It keeps option 1's
structure (a real `ArtifactKind`/`NodeKind`, DRG edges, charter activation) because option 2
has nowhere to put the skill → procedure binding except an inline reference block, which
ADR 2026-07-26-1 forbids, and any independent activation would add a second `mission-type`
style outlier. It takes option 2's naming ("skill" is already the glossary term:
`packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml:545`) and its sequencing
(derive the lockstep kind lists first; augment procedures before thinning skills).

The skills README's rule that skills are "not the source of team workflow"
(`src/charter/offering/skills/README.md:7-24`) constrains *substance*. A pack skill is a thin,
parameterised entry point that `requires` the procedure carrying the substance, so it
complies with that rule rather than breaking it.

### Shape of the artifact

```yaml
# packs/internal/skills/land-pr.skill.yaml   (org tier; never in the wheel)
schema_version: "1.0"
id: land-pr                        # URN skill:land-pr
title: Land a contributor PR
description: Maintainer landing pass on a PR — triage, rebase, classify reds, squad, hand off.
triggers: ["land this PR", "landing pass"]
form: prompt                       # prompt | wrapper
body_path: land-pr.skill.md        # prompt form only; uses $ARGUMENTS
parameters:
  - {name: pr, required: true, description: "PR number or URL"}
  - {name: steer, required: false, description: "free-text steer"}
invocation:
  user_invocable: true
  model_invocable: false           # forced false when side_effects is non-empty
  side_effects: [git-push, gh-write]
tools: ["*"]                       # filtered by the project's configured tools
version: 1.0.0
maintainers: ["@spec-kitty/core"]
```

```yaml
# a wrapper-form skill: a thin shorthand over an existing command
id: ship
form: wrapper
expands_to: {target: "builtin:spec-kitty.merge", args: "--strategy squash $ARGUMENTS"}
```

Relationships live only in the pack's DRG fragment:

```yaml
edges:
  - {source: "skill:land-pr", target: "procedure:landing-contributor-prs", relation: requires}
  - {source: "skill:land-pr", target: "directive:NO_FULL_HEAVY_SUITES_IN_MISSION", relation: requires}
  - {source: "skill:land-pr", target: "agent_profile:reviewer-renata", relation: suggests}
```

Dangling endpoints fail closed with `unresolved_edge_endpoint`
(`src/charter/offering/drg/merge.py`). The rendered skill carries a generated preamble that
fetches each `requires` target at run time with `spec-kitty charter context --include <urn>`,
so the substance is never copied into the skill.

### Tiers, merge, and activation

| Tier | Location | Ships? | Example content |
| --- | --- | --- | --- |
| built-in | `packs/built-in/skills/` + generated `skill.graph.yaml` shard | yes | consumer-safe shorthands (empty at MVP) |
| org | `<pack>/skills/`, declared in `drg/fragment.yaml`, `required_skills:` in `org-charter.yaml` | never for `packs/internal` | `land-pr`, `mission-from-issue`, `issue-triage`, `curate-memory` |
| project | `.kittify/doctrine/skills/` | repo-local | repository-specific shorthands |

- Activation: `spec-kitty charter activate skill land-pr --cascade procedure,directive`
  through `plan_activation` / `commit_plan`; config key `activated_skills`. Cascade pulls in
  what the skill `requires`; deactivation keeps anything another active artifact still
  references (C-005).
- Default in force when the key is absent: `required_skills` of registered org packs plus
  built-in defaults, **not** every available skill, supplied through the existing
  `effective_ids` seam and one kind attribute rather than per-kind branching. Registering a
  pack must not silently add N commands to every tool.
- `overrides: skill:<id>` replaces a skill (built-in replacement still needs
  `replaceable-builtins.yaml`); `enhances` may change parameter defaults, triggers, tool
  targeting, or narrow invocation, but never the body or expansion. Same id in two sibling
  org packs is a hard conflict.
- Co-maintenance: the pack's `pack_version`, the skill's `version`, per-constituent
  `content_hash` in the pack manifest, `maintainers`, and review through the pack
  repository's PRs. A locally edited rendered copy is reported as drift pointing back at the
  pack source, so tweaks become upstream PRs rather than forks.

### Rendering and installation

```
charter (pure)                                  specify_cli (adapter)
merged DRG + activated_skills
  └─ prepare_skill_activations()  ─────────►  resolve_project_skill_catalog(project_root)
       (id, rendered name, body, expansion,       ├─ render via command_renderer frontmatter
        provenance, content_hash)                 │   + User-Input block rewrite
                                                  ├─ project skill roots only, never global
                                                  └─ .kittify/skills-manifest.json ownership
```

- The **managed doctrine-skill installer** (`src/specify_cli/skills/installer.py`) is the
  owner. `command_installer.py` and its `spec-kitty.*` contract stay closed.
- **One catalog-composition seam** used by every caller that today builds
  `SkillRegistry.from_package()` and installs with `retire=True` (`init`, `upgrade`
  migrations, the verifier, the managed-skills tool-surface provider). Injecting pack skills
  into a single call site would let the others prune them on the next `upgrade`.
- Charter emits unresolved `builtin:` expansion targets; the `specify_cli` adapter validates
  them against its command set, keeping the enforced
  `kernel <- charter <- … <- specify_cli` direction. `cli:` targets are limited to
  `spec-kitty` argv.
- **Project scope only.** Activation is per repository, so rendered skills go to project
  skill roots (`.claude/skills/`, `.agents/skills/`, and the other roots in
  `AGENT_SKILL_CONFIG`), never to user-global directories.
- Coverage at MVP: the 16 tools with a project skill root. Amazon Q is wrapper-only and gets
  a research-gap finding; project-local command files for non-skill tools come later.
- Deactivation re-runs projection and retires manifest-owned entries only.
- Rendered copies are gitignored in this repository, so `doctor` / `upgrade` flag a pack
  whose `content_hash` differs from the manifest provenance (staleness, not only tampering).

### Namespaces and trust

- `spk-`, `spec-kitty-`, and `spec-kitty.` are reserved for built-in. Org and project packs
  declare a `skill_namespace`; skills render as `<namespace>-<id>`. Two activated skills that
  render to the same name fail before any write; an unowned existing directory with that name
  is preserved and reported.
- A pack acts only after a maintainer registers it in `charter_packs.org.packs`; remote packs
  must pin an immutable ref; content hashes are verified at preparation.
- Activation prints a trust summary over the skill's whole `requires`/`suggests` closure,
  assets included (assets already ship executables), and requires `--accept` for side effects
  or remote packs. No `scripts/` and no permission-widening frontmatter (such as
  `allowed-tools`) for org or project skills.
- Bindings (repository, operator) resolve at run time from project config, never baked into
  rendered files; public packs carry no personal identifiers.

### Consequences

#### Positive

- A team shorthand has one reviewed, versioned source that reaches every configured tool.
- Procedures stay the single home of substance; entry points cannot silently drift from it.
- Private skills get a promotion path into a project or org pack.
- The kind is the convergence target for the built-in `spk-*` product skills later.

#### Negative

- A new kind is real work: four total tables in `artifact_kinds.py`, `NodeKind`, a doctor
  health dimension, an extractor helper, the delivery table (`slot=None` with a reason),
  a generated shard, and roughly a dozen exact-set tests (precedent: the `glossary_pack` kind).
- It expands the visible slash surface per project, which the skills README otherwise avoids;
  that is deliberate and scoped to activated skills only.
- `packs/built-in/skills/` coexists with `src/charter/offering/skills/` until convergence.

#### Neutral

- Invocation costs one extra `charter context --include` call per required artifact.

### Confirmation

- ATDD: activate a pack skill → it appears in `.claude/skills/` and `.agents/skills/`;
  run `upgrade` → still present; deactivate → removed; nothing else touched.
- Packaging safety: no `packs/internal/skills/**` path in the wheel.
- The four internal shorthands run from the pack with no private copy, and the landing
  procedure carries the content that only the private skill held before.

## Delivery slices

0. **Campsite (precondition):** derive `_BUILTIN_ARTIFACT_KINDS`
   (`src/charter/activation/pack_context.py`), `_ALLOWED_KINDS`
   (`src/charter/activation/activations.py`), `_ORG_DRG_KIND_ALIASES`
   (`src/charter/offering/drg/org_pack_loader.py`), and `REQUIRED_KIND_FIELDS` from
   `ArtifactKind`, so this and every later kind adds no lockstep copies.
1. **MVP:** kind and node registration, schema and validator for both forms, activation and
   cascade with the default-in-force rule, `prepare_skill_activations`, the catalog seam,
   project-root projection, namespaces, drift and staleness findings, retire on deactivate.
2. **Migration:** augment `landing-contributor-prs` and the other procedures with the content
   only the private skills hold, then add the four thin `packs/internal/skills/*` entries and
   retire the private copies.
3. **Later:** trust `--accept` gate and remote pinning, command-file projection for non-skill
   tools, a `charter skill promote <dir>` scaffolder, an Op-opening preamble, and converging the
   built-in `spk-*` skills onto the kind.

## Pros and Cons of the Options

### Option 1: new kind `command`

- Good: correct structure (kind, edges, activation, managed installer, project scope).
- Bad: "command" already has six or more senses (Slash Command, Command Template, Command
  Envelope, CLI command, `CANONICAL_COMMANDS`, command-skill tools) and `form: alias` adds a
  fifth sense of "alias". Blocks later convergence of the product skills.

### Option 2: pack skills without a kind

- Good: cheapest doctrine-side change; reuses the glossary term.
- Bad: the skill → procedure link would live in frontmatter, a second relationship authority;
  no own activation (breaks for wrapper skills, many skills over one procedure, and projects
  that want the procedure but not the entry point); no cascade, `--include`, or doctor health.
  The installer work, the dominant cost, is the same as option 3.

### Option 3: new kind `skill` (chosen)

- Good: one relationship authority, one activation authority, canonical term, convergence path.
- Bad: kind-registration cost (reduced by slice 0).

### Option 4: invocable procedures

- Bad: procedures have no parameters, bindings, or tool targeting; every procedure edit would
  become a surface change.

### Option 5: tool-native plugin marketplaces

- Bad: tied to one tool; loses the single cross-tool source. It can stay a later projection
  target.

## Open questions

- Which of the 16 skill-root tools expose project skills as `/name` rather than model-routed
  only? Verify against `src/specify_cli/tool_surface/profiles/capability_matrix.py`.
- Project-tier namespace: required config key, or derived from the repository name?
- Placeholder syntax for run-time bindings must not collide with `$ARGUMENTS` or TOML `{{args}}`.

## Related drift found during research

- CLAUDE.md names the org-pack key `doctrine.org.packs`; the code reads
  `charter_packs.org.packs` and treats the old key as a legacy fallback
  (`src/charter/offering/drg/org_pack_config.py`).
