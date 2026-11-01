---
title: 'ADR 2 (2026-04-14): Agent Skills Renderer for Codex and Vibe'
description: 'Adds a scoped renderer emitting per-command SKILL.md packages for Codex and Vibe only, installed additively and tracked through an ownership manifest.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-14'
---

## Context and Problem Statement

Spec Kitty supports multiple coding-agent integrations (claude, codex,
gemini, cursor, opencode, windsurf, and others). Each agent discovers the
`/spec-kitty.*` slash commands by reading a directory of prompt files at a
vendor-specific path — e.g. `.claude/commands/`, `.codex/prompts/`,
`.gemini/commands/`. That pipeline has worked for a year, but two new
pressures made it untenable for the next release:

1. **Mistral Vibe** — announced April 2026 — ships with no prompt-file
   surface at all. It is a *skills-first* agent: slash commands are
   discovered as Agent Skills packages (`SKILL.md` + body) under
   `.agents/skills/`, `.vibe/skills/`, or `~/.vibe/skills/`. Spec Kitty
   cannot support Vibe by adding another `AGENT_COMMAND_CONFIG` row.

2. **OpenAI Codex** has **deprecated** `.codex/prompts/*.md` in favor of
   Agent Skills at `.agents/skills/` (documented at
   https://developers.openai.com/codex/custom-prompts and
   https://developers.openai.com/codex/skills). Spec Kitty's Codex
   integration was writing to the deprecated path while *also* shipping
   skills to `.agents/skills/` for other purposes. The prompt-file side
   had become obsolete without our noticing.

During P0 research for this mission we confirmed a second, subtler
constraint: the `$ARGUMENTS` pre-substitution pattern Spec Kitty uses in
its command templates is a **command-layer** feature, not a **skills-layer**
feature. Codex's documented skill invocation mechanism (`$skill-name
<free-form text>`) delivers user input as *turn content*, not via a
placeholder the runtime substitutes. Vibe's vendor docs are silent on
substitution semantics. Moving all agents' Spec Kitty commands into the
skills layer would therefore lose deterministic argument delivery on Codex
and (worst case) on Vibe, and would degrade TUI autocomplete UX on
opencode (whose skills are model-loaded, not user-invoked slash entries).

Full per-agent research is recorded in
`kitty-specs/083-agent-skills-codex-vibe/research.md`.

## Decision

Introduce a **scoped** Agent Skills renderer and installer that serves
**Codex and Vibe only**. The renderer reads the same
`command-templates/*.md` source files that the legacy command-file
pipeline reads, transforms the `## User Input` block (the one place the
templates rely on `$ARGUMENTS` substitution) into an explicit instruction
telling the model to read turn content as user input, and emits per-command
`SKILL.md` packages under `.agents/skills/spec-kitty.<command>/`. The
installer writes those packages **additively** into the shared
`.agents/skills/` root and tracks ownership via
`.kittify/command-skills-manifest.json`.

The twelve remaining command-layer agents (claude, gemini, copilot,
cursor, qwen, opencode, windsurf, kilocode, auggie, roo, q, antigravity)
continue to use the existing command-file pipeline unchanged. A
post-mission regression snapshot (132 fixture files: 12 agents × 11
commands) locks that parity in place.

Concretely:

- **Canonical command key** for Mistral Vibe: `vibe` (following the
  `claude`/`codex`/`gemini` product-name convention, not the vendor
  name).
- **Primary discovery root** for Codex in this release:
  project-local `.agents/skills/`. Vibe is pointed at that shared tree via
  project-local `.vibe/config.toml` `skill_paths`, which matches Mistral's
  documented custom-path mechanism. Vendor-specific skill copies remain out of
  scope.
- **Ownership manifest** at `.kittify/command-skills-manifest.json` records every
  Spec-Kitty-owned file with its SHA-256 hash and a reference-counted
  list of agents that installed it. Removing an agent drops its entry
  from the list; files are physically deleted only when the list
  empties. Third-party files sharing the `.agents/skills/` root are
  never read, modified, or deleted by the installer.
- **Zero-touch Codex migration**: an upgrade migration moves existing
  `.codex/prompts/spec-kitty.*.md` files to
  `.codex/prompts.superseded/` (preserving them for user review) and
  installs the equivalent `.agents/skills/spec-kitty.<command>/SKILL.md`
  packages. Non-Spec-Kitty files under `.codex/prompts/` are untouched.
- **Template rendering is a package operation**, not a project
  operation. Command templates ship inside the installed `specify_cli`
  Python package. The installer locates them via
  `Path(specify_cli.__file__).parent / "missions" / ...`, never via a
  path relative to the user's project root.

## Alternatives Considered

### A. Unified skills-only renderer covering all agents

Rejected. This would have:

- Broken deterministic `$ARGUMENTS` substitution on Codex (no documented
  substitution mechanism in Agent Skills) and possibly on Vibe (no vendor
  commitment either way).
- Regressed TUI autocomplete UX on opencode, whose skills layer is
  model-loaded via a `skill` tool rather than surfaced as slash commands.
  Users who currently see `/spec-kitty.specify` in opencode's autocomplete
  would lose it.
- Rewritten every canonical command template to stop relying on
  `$ARGUMENTS` pre-substitution, with a blast radius spanning every
  supported agent.

### B. Vendor-specific roots (.vibe/skills/, .codex/skills/, plus shared)

Rejected for this release. Shared `.agents/skills/` is documented as a
first-class discovery root for both vendors. Vendor-specific roots would
add installer complexity and potential coexistence issues without a clear
user-visible benefit. Deferred to a follow-up if demand emerges.

### C. Filename-only classification vs hash-based edit detection for the Codex migration

Rejected (hash-based). Reproducing the pre-3.2 renderer's exact output
bytes requires either pinning an archived copy of the pre-3.2 rendering
pipeline or running a sandboxed subprocess against historic templates.
Both options are fragile, and the payoff (distinguishing unedited from
edited files) is dominated by the simpler guarantee: **preserve every
Spec-Kitty-named file from `.codex/prompts/` on disk**, in a sibling
`prompts.superseded/` directory, and surface the list to the user. No
content-hashing needed; no user edits lost; users who never edited the
files can delete `prompts.superseded/` in one command.

### D. Render templates via `importlib.resources.files()` Traversable

Rejected in favor of deriving the path from `specify_cli.__file__`. The
Traversable API returns a `MultiplexedPath` when the package has multiple
sources (e.g., editable install + installed wheel coexisting), which does
not coerce to `pathlib.Path` and requires the renderer to accept a
`Traversable` instead. Since `specify_cli.missions.software-dev.command-templates`
is a regular directory inside a regular package (not a zipapp), a real
`Path` derived from `__file__` is both simpler and equivalent.

## Consequences

### Positive

- **Mistral Vibe becomes a first-class supported agent** in the same
  release that retires the deprecated Codex prompt path.
- **Codex users get a zero-touch upgrade** — `spec-kitty upgrade` moves
  legacy files and installs skill packages with no manual steps.
- **Shared-root safety** is formally guaranteed by the ownership manifest
  and the installer's reference-counted removal semantics. Installing or
  removing Codex or Vibe cannot affect third-party files in
  `.agents/skills/`.
- **The renderer is pure and deterministic** — same template inputs
  produce byte-identical outputs on repeated runs, verified by 22
  snapshot fixtures (11 commands × 2 agents).
- **The 12 non-migrated agents are locked** against unintended drift via
  a 132-fixture regression snapshot.

### Negative

- **Two parallel installers** now coexist for `.agents/skills/`: the
  pre-existing canonical-skill installer (doctrine, tactics) and the new
  command-skill installer. They share the ownership manifest's shape
  but run independently. A future unification is desirable but not
  required for correctness.
- **FR-004 in the mission spec named 16 canonical commands** but the
  codebase has only 11 template files for them. The 5 missing commands
  (`tasks-finalize`, `accept`, `merge`, `status`, `dashboard`) are
  CLI-only and never had templates in either pipeline. The renderer
  correctly installs the 11 that exist. Adding the missing 5 templates
  is follow-up work, not a regression introduced by this mission.
- **Vendor-specific roots remain unsupported.** Users who prefer
  `.vibe/skills/` over `.agents/skills/` cannot opt into that today.

### Security

No new security surface. The installer does not invoke subprocesses, make
network calls, or handle credentials. Agent keys are validated against
an allowlist (`SUPPORTED_AGENTS = ("codex", "vibe")`) before being used to
construct filesystem paths. Command names come from a hardcoded
`CANONICAL_COMMANDS` tuple — no user input flows into paths.

## Implementation references

- Mission spec: kitty-specs/083-agent-skills-codex-vibe/spec.md
- Plan + research: plan.md, research.md
- Contracts: contracts/skill-renderer.contract.md, contracts/skills-manifest.schema.json
- Post-merge review: mission-review.md
- Core modules: `src/specify_cli/skills/command_renderer.py`, `src/specify_cli/skills/command_installer.py`, `src/specify_cli/skills/manifest_store.py`
- Codex migration: `src/specify_cli/upgrade/migrations/m_3_2_0_codex_to_skills.py`
