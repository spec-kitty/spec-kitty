# Doctrine Skills

Shipped skills that teach agents how to operate Spec Kitty correctly.

## Scope and Boundary

Skills are the **product-operation layer**: they answer "how do I use Spec
Kitty?" They are not the canonical source for mission behavior or team-
specific workflow — that role belongs to doctrine mission composition (step
contracts, procedures, action indices, mission definitions).

Two tracks exist and should remain distinct:

1. **Skills** — how an external agent correctly uses Spec Kitty itself:
   runtime-next control loop, charter/doctrine access, review workflow,
   setup/repair, glossary context, git workflow, orchestrator API.

2. **Doctrine mission composition** — how a team does product work: which
   steps a mission follows, what procedures each step delegates to, which
   directives and tactics scope each action.

Skills may *consume* doctrine outputs (e.g., calling `DoctrineService` to
load a tactic, reading an action index to scope context). Skills should
**not** become a second source of truth for mission behavior.

> "Skills answer: how do I operate Spec Kitty correctly? Doctrine mission
> composition answers: how should this team do product work? The compiler
> is what should bridge those without expanding the visible slash-command
> surface." — internal design review, PR #305

## Pack Skills (separate from shipped skills)

Teams can also ship **pack skills**: thin, parameterised entry points declared
in an org pack (`<pack>/skills/`) or the project tier
(`.kittify/doctrine/skills/`) as the `skill` doctrine kind. They are not part
of this shipped catalog. They are charter-activated
(`spec-kitty charter activate skill <id>`), rendered as
`<skill_namespace>-<id>` (the `spk-`, `spec-kitty-` and `spec-kitty.` prefixes
stay reserved for the skills here), and projected to project skill roots only.
A pack skill `requires` the procedure that carries the substance, so it obeys
the boundary above. `spec-kitty doctor skills` reports a locally edited, stale or
orphaned rendered copy and names its pack source. To author one, see
`docs/development/how-to/create-a-pack-skill.md`. See ADR
`docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`.
Converging the built-in `spk-*` skills onto the pack-skill kind is later work
(slice 3, #5193); until then the skills in this catalog stay as shipped.

## Context Loading Pattern

Skills should teach agents to load doctrine **iteratively**:

1. At init: resolve agent profile, load initialization declaration.
2. At each step boundary: call `build_charter_context(action, depth=1)`.
3. When stuck or need guidance: pull specific tactic/directive by ID.
4. Never: load the full doctrine catalog into prompt context upfront.

## Naming Convention

Spec Kitty 3.2.0 public operating skills use short hierarchical names:
`spk-<family>-<action-or-topic>`.

Families:

- `spk-start-*`: onboarding, first use, command map, agent surface.
- `spk-mission-*`: specify, research, plan, tasks, documentation, mission
  type selection.
- `spk-run-*`: runtime-next, program orchestration, implementation/review
  loops, single-WP review, blocked recovery.
- `spk-gate-*`: accept, merge, mission review, retrospective.
- `spk-admin-*`: setup, agent config, upgrade.
- `spk-doctrine-*`: charter, glossary, SPDD, profile load, bulk-edit policy.
- `spk-doctrine-show-me`: compact visual communication grounded in diagram doctrine.
- `spk-doctrine-semantic-compression`: behavior-preserving code reduction.
- `spk-integrate-*`: orchestrator API, CI, external automation.
- `spk-meta-*`: skill discovery and future skill authoring.

Generated slash-command skills keep their command names
(`spec-kitty.<command>`) for slash-command compatibility. Existing
`spec-kitty-*` skills remain legacy aliases or detailed workflow guides while
the public user-facing hierarchy moves to `spk-*`.

## Public `spk-*` Inventory

| Skill | Purpose |
|---|---|
| `spk-start-here` | First route for users and agents |
| `spk-start-first-feature` | First mission walkthrough |
| `spk-start-command-map` | Command-to-skill map |
| `spk-start-agent-surface` | Agent host compatibility |
| `spk-mission-specify` | Specification phase |
| `spk-mission-plan` | Planning phase |
| `spk-mission-tasks` | Tasks and WP authoring |
| `spk-mission-types` | Mission type selection |
| `spk-mission-research` | Research workflows |
| `spk-mission-documentation` | Documentation missions |
| `spk-run-next` | Runtime-next control loop |
| `spk-run-program-orchestrate` | Multi-mission program orchestration |
| `spk-run-implement-review` | WP implementation/review orchestration |
| `spk-run-review-wp` | Single-WP review |
| `spk-run-blocked-recovery` | Blocked-state recovery |
| `spk-gate-accept` | Accept gate |
| `spk-gate-merge` | Merge gate |
| `spk-gate-mission-review` | Post-merge mission review |
| `spk-gate-retrospective` | Post-merge retrospective |
| `spk-admin-setup-doctor` | Install and repair |
| `spk-admin-agent-config` | Agent setup |
| `spk-admin-upgrade` | Upgrade and migrations |
| `spk-admin-git-workflow` | Git and worktree workflows |
| `spk-doctrine-charter` | Charter workflows |
| `spk-doctrine-glossary` | Terminology |
| `spk-doctrine-spdd-reasons` | REASONS Canvas |
| `spk-doctrine-profile-load` | Agent profiles |
| `spk-doctrine-show-me` | Compact visuals, diagrams, and TUI status rendering |
| `spk-doctrine-semantic-compression` | Semantic compression |
| `spk-doctrine-bulk-edit` | Bulk-edit classification |
| `spk-integrate-orchestrator-api` | External orchestrator API |
| `spk-meta-skill-map` | Discovery and naming convention |
| `spk-meta-skill-authoring` | Future skill authoring |

## Legacy / Detailed Workflow Inventory

| Skill | Purpose |
|---|---|
| `spec-kitty-runtime-next` | Drive the `next --agent` control loop with doctrine-aware context loading |
| `spec-kitty-charter-doctrine` | Charter lifecycle + `DoctrineService` programmatic access |
| `spec-kitty-mission-system` | Mission types, step contracts, procedures, action indices, template resolution |
| `ad-hoc-profile-load` | Load an agent profile on demand for interactive sessions outside the mission loop |
| `spec-kitty-runtime-review` | Review workflow surface: claim, review, approve/reject |
| `spec-kitty-mission-review` | Post-merge mission review: FR trace, drift analysis, risk/security audit, final verdict |
| `spec-kitty-implement-review` | Implement-review orchestration loop across WPs |
| `spec-kitty-program-orchestrate` | Multi-repo program orchestration: drive several missions end-to-end in dependency order with parallel sub-agents and a pulse-heartbeat safety net |
| `spec-kitty-setup-doctor` | Installation diagnostics and repair |
| `spec-kitty-git-workflow` | Git operations, worktree lifecycle, safe-commit pattern |
| `spec-kitty-glossary-context` | Terminology curation and semantic integrity |
| `spec-kitty-orchestrator-api-operator` | External automation via orchestrator-api |
| `spec-kitty-bulk-edit-classification` | Detect bulk-edit intent and drive occurrence-map guardrail (DIRECTIVE_035) |

## Source Location

These files in `src/charter/offering/skills/` are the **source of truth**. Agent
copies (`.claude/skills/`, `.agents/skills/`, etc.) are generated during
`spec-kitty upgrade` and should not be edited directly.

## Related

- Issue #327: Doctrine mission compiler proposal
- PR #305 / #348: Doctrine artifact domain, agent profiles, charter bootstrap
- `packs/built-in/missions/`: Mission type definitions with action indices
- `src/charter/offering/agent_profiles/`: Agent profile repository and shipped profiles
