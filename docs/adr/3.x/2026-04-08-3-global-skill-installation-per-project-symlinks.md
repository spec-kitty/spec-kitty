---
title: 'ADR 3 (2026-04-08): Global Skill Installation with Per-Project Symlinks'
description: 'Skills live canonically under ~/.kittify/agent-skills/<agent>/ and projects reference them by symlink, with a file-copy fallback where symlinks are unavailable.'
status: Superseded
doc_status: superseded
kind: ADR
date: '2026-04-08'
---

> **Superseded (2026-07-19):** the per-project **symlink** wiring decided here is
> replaced by copy delivery — absolute symlinks dangle in dev-containers and are
> unreadable to sandboxed agent harnesses (#2412). The **global canonical
> install** half of this decision stands unchanged and is reaffirmed in
> [ADR 2026-07-19-2](2026-07-19-2-skill-projection-copies-not-symlinks.md).

## Context and Problem Statement

Skills are markdown files that extend agent capabilities — they encode domain-specific workflows, patterns, and shortcuts that agents invoke during mission execution. Examples include `spec-kitty-git-workflow.md`, `spec-kitty-charter-doctrine.md`, and `spec-kitty-implement-review.md`.

Prior to this decision, skills were installed on a per-project basis during `spec-kitty init`. Each project received its own copy of every skill file for every configured agent. The installation wrote files to `.claude/commands/`, `.codex/prompts/`, `.github/prompts/`, and so on within the project directory.

This per-project model created several operational problems:

1. **Upgrade burden.** When a skill file is updated in a new release of spec-kitty-cli, the developer must run `spec-kitty upgrade` in every project to propagate the change. A developer with ten projects has ten separate upgrade operations. Missing any one of them means that project continues to use an outdated skill.

2. **Disk duplication.** A developer with ten projects and 13 agents configured has up to 130 × (number of skill files) copies of identical markdown files spread across their filesystem.

3. **Scope confusion.** Skills, like mission templates, are machine-level capabilities. They describe what the agent knows how to do on this developer's machine, not anything specific to a given project. Installing them per-project conflates capability configuration with project configuration.

4. **Double-prompt problem (interaction).** Per-project skill copies interact with the global installation to produce duplicate slash commands in AI tools (see ADR-F for the migration that addresses this interaction). The root cause is that skills are installed in both per-project directories and global agent command directories simultaneously.

## Decision Drivers

* **Single upgrade touch-point:** Upgrading skills should update all projects automatically.
* **Disk efficiency:** One copy of a skill per agent per machine, not N copies per project.
* **Alignment with global runtime model:** Skills are a machine-level capability; their canonical location should be machine-level (see ADR-A).
* **Practical compatibility:** Not all filesystems and developer environments support symlinks (e.g., some Windows configurations, network shares, certain container mounts).

## Considered Options

* **Option A: Global install to `~/.kittify/agent-skills/`, per-project symlinks (chosen)**
* **Option B: Per-project full copy (status quo)**
* **Option C: Symlink only, no copy fallback**

## Decision Outcome

**Chosen option: Option A — Skills are installed canonically to `~/.kittify/agent-skills/{agent}/`. Per-project agent directories reference skills via symlinks, with a copy fallback for environments that do not support symlinks.**

### Installation Target

```
~/.kittify/agent-skills/
  claude/
    spec-kitty-git-workflow.md
    spec-kitty-charter-doctrine.md
    spec-kitty-implement-review.md
    ...
  codex/
    ...
  opencode/
    ...
```

`spec-kitty init` is responsible for populating these directories from the package-bundled skill sources (see ADR-B).

### Per-Project Wiring

When a project directory references skills, it creates symlinks from its agent command directories into the global installation:

```
.claude/commands/spec-kitty-git-workflow.md -> ~/.kittify/agent-skills/claude/spec-kitty-git-workflow.md
```

On filesystems where symlinks are not supported, the installer falls back to copying the file.

### Known Current Limitation

The feature 076 implementation installs per-project skill wiring during `spec-kitty init` (a known gap from the intended architecture). This means skill files continue to be present in project agent directories for now. This ADR documents the intended architecture — global install is canonical, per-project is derived — and the per-project wiring will be moved to a dedicated per-project setup flow in a future feature. The double-prompt problem caused by this gap is addressed by the hardened command-globalization path that ships in `3.2.0a4` (see ADR-F).

### Consequences

#### Positive

* Upgrading skills requires a single `spec-kitty init` or `spec-kitty upgrade` on the machine; all projects that symlink to global skills see the update immediately.
* Disk usage is proportional to the number of agents configured, not agents × projects.
* The machine-level / project-level boundary is reinforced.

#### Negative

* Per-project setup (creating symlinks or copies) requires a wiring step that is currently bundled into init rather than into a dedicated per-project setup command. This will be addressed in a future feature.
* Symlink-based wiring can break if the global install is moved or deleted. Projects must detect broken symlinks and surface an actionable error.
* Copy fallback diverges from the global install when skills are upgraded; the fallback case requires a re-run of the wiring step to refresh.

#### Neutral

* The per-project agent command directories (`.claude/commands/`, etc.) continue to exist; their content is now derived from global skills rather than independent copies.

### Confirmation

Correct behavior is confirmed when: `spec-kitty init` populates `~/.kittify/agent-skills/{agent}/` with all skill files; and a subsequent `spec-kitty upgrade` on a project refreshes any stale skill references without losing project-local customizations. Integration tests cover both the symlink and copy-fallback paths.

## Pros and Cons of the Options

### Option A: Global install with per-project symlinks (chosen)

Skills live in `~/.kittify/agent-skills/`. Per-project agent directories contain symlinks (or copies as fallback) pointing to the global location.

**Pros:**
* One upgrade point for all projects.
* Disk-efficient.
* Consistent with the global runtime model established in ADR-A.

**Cons:**
* Symlink creation must handle fallback.
* Broken symlinks require detection and user guidance.

### Option B: Per-project full copy (status quo)

`spec-kitty init` copies skill files into each project's agent command directories. Each project is independently up to date.

**Pros:**
* Self-contained: the project has everything it needs without relying on a global install.
* No symlink complexity or broken-link scenarios.
* Works on any filesystem.

**Cons:**
* N copies of identical files across N projects.
* Upgrades require per-project `spec-kitty upgrade` runs.
* Reinforces the conflation of machine-level and project-level state.
* Root cause of the double-prompt problem (local and global copies both visible to the agent).

**Why Rejected:** The upgrade burden and the double-prompt problem are both directly caused by this model. Neither can be fixed without changing the installation architecture.

### Option C: Symlink only, no copy fallback

Skills are always symlinks to the global installation. Copy fallback is not implemented.

**Pros:**
* Simpler implementation: no branching for symlink vs copy.
* Forces all environments to support symlinks (progressive enhancement).

**Cons:**
* Windows environments with symlink restrictions (requires elevated permissions or Developer Mode) would fail silently or with cryptic errors.
* Network-mounted project directories (common in remote development setups) may not support symlinks.
* Failing loudly on an unsupported filesystem is worse than copying.

**Why Rejected:** The potential failure modes on Windows and network filesystems affect a non-trivial portion of the user base. The copy fallback is a small implementation cost relative to the compatibility gain.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — FR-007 (skills installed to `~/.kittify/`; per-project directories reference global install)
* **Related ADR:** ADR-A (2026-04-08-1) — Global `~/.kittify/` as machine-level runtime (establishes the global directory structure that skills live in)
* **Related ADR:** ADR-F (2026-04-08-6) — Global agent commands supersede per-project copies (migration that resolves the double-prompt problem caused by the current per-project gap)
* **Related ADR:** ADR-6 (2026-01-23-6) — Config-driven agent management
* **Code locations:**
  * `src/specify_cli/init.py` — skill installation logic
  * `src/specify_cli/shims/generator.py` — shim/command file generation (distinct from skill installation)
