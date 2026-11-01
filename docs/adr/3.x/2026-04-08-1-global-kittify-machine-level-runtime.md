---
title: 'ADR 1 (2026-04-08): Global `~/.kittify/` as Machine-Level Runtime'
description: 'Makes ~/.kittify the machine-level runtime that init bootstraps, leaving per-project .kittify directories holding nothing but project-specific state.'
status: Accepted
date: '2026-04-08'
doc_status: active
kind: ADR
updated: '2026-04-08T00:00:00Z'
---

## Context and Problem Statement

`spec-kitty init` was originally designed as a per-project installer: it copied mission templates, scripts, and agent command files into the current project directory. Each project therefore contained a full, independent copy of the spec-kitty runtime. This design made sense when spec-kitty was a lightweight scaffolding tool, but it created several structural problems as the tool matured into a multi-agent orchestration platform:

1. **Data duplication.** Missions, skills, and agent templates are identical across projects. Every `spec-kitty init` on a developer's machine produces another full copy.

2. **Inconsistent upgrades.** Running `spec-kitty upgrade` in one project updated its local copies; other projects remained on older templates. A developer working across three projects could have three different versions of the same slash commands.

3. **Blurred machine/project boundary.** Agent configuration (which AI tools are installed and trusted on a given machine) is a machine-level concern. Project metadata (charter, feature specifications, work package state) is a project-level concern. init was conflating the two in a single directory.

4. **No canonical runtime location.** Code that needed to resolve mission paths, skill locations, or agent configs had to guess: search upward from cwd, look in the package, or use a configurable path. There was no agreed-upon answer for "where does the runtime live?"

Feature 076 redesigns `spec-kitty init` to address these problems by establishing a global machine-level runtime at `~/.kittify/`.

## Decision Drivers

* **Upgrade consistency:** One update to the global runtime propagates to all projects without per-project re-runs.
* **Clear separation of concerns:** Machine state and project state must not share the same directory.
* **Explicit error surfaces:** Runtime bootstrap failures must be visible to the developer, not silently swallowed.
* **Simplicity:** init should do one thing — prepare the machine — and do it completely.
* **Disk efficiency:** A single global copy of mission templates replaces N per-project copies.

## Considered Options

* **Option A: Global `~/.kittify/` as machine-level runtime (chosen)**
* **Option B: Per-project full copy (status quo pre-076)**
* **Option C: Read-only global + writable per-project overlay**

## Decision Outcome

**Chosen option: Option A — Global `~/.kittify/` as machine-level runtime.**

`spec-kitty init` bootstraps a single global runtime at `~/.kittify/`. Re-running init updates the global runtime without touching any project directory. Per-project `.kittify/` directories contain only project-specific state.

### What Belongs Where

| Artifact | Location | Rationale |
|----------|----------|-----------|
| Mission templates | `~/.kittify/missions/` | Machine-level; identical across projects |
| Agent skills (global install) | `~/.kittify/agent-skills/{agent}/` | Machine-level; see ADR-C |
| Global agent config (which agents enabled) | `~/.kittify/config.yaml` | Machine-level; one setting per machine |
| Per-project agent config (overrides) | `.kittify/config.yaml` | Project-level; thin overlay |
| Charter and governance | `.kittify/charter.md` | Project-level; authored via `/spec-kitty.charter` |
| Feature specifications | `kitty-specs/{feature}/` | Project-level; created by `/spec-kitty.specify` |
| Local overrides / custom prompts | `.kittify/overrides/` | Project-level; never touched by init |

### `ensure_runtime()` Behavior

The `ensure_runtime()` function is the sole entry point for verifying that `~/.kittify/` is present and current. Failures must surface as explicit errors with actionable messages (e.g. "Global runtime not found. Run `spec-kitty init` to bootstrap."). Silent swallowing of `ensure_runtime()` failures — which occurred in several pre-076 code paths — is explicitly prohibited.

### Idempotency

Re-running init on an already-initialized machine is safe. The command detects the existing global runtime, presents current agent configuration, and exits without overwriting data.

### Consequences

#### Positive

* A single runtime upgrade propagates to all projects on the machine.
* Machine-level and project-level concerns are separated by directory boundary.
* `ensure_runtime()` has a canonical target; runtime resolution is unambiguous.
* Disk usage is reduced: one copy of mission templates instead of N copies.
* init is faster: no per-project file-copying for templates already in `~/.kittify/`.

#### Negative

* Developers who work on multiple machines must run `spec-kitty init` on each machine separately.
* CI environments (which may not have a persistent home directory) require explicit bootstrapping or `--non-interactive` mode.
* Legacy projects that relied on `.kittify/missions/` existing locally may need migration guidance.

#### Neutral

* The `.kittify/` directory in project roots continues to exist but is now a thin overlay rather than a full runtime copy.

### Confirmation

Correct behavior is confirmed when: `spec-kitty init` completes without creating or modifying any file outside `~/.kittify/` and the project scaffold files (`.gitignore`, `.kittify/metadata.yaml`, `.kittify/config.yaml`); and when running init twice produces identical filesystem state (idempotency). The acceptance test suite covers both conditions.

## Pros and Cons of the Options

### Option A: Global `~/.kittify/` as machine-level runtime (chosen)

A single canonical location for all machine-level runtime artifacts. `spec-kitty init` creates or updates this directory. Per-project `.kittify/` is a thin overlay.

**Pros:**
* One upgrade touches all projects.
* Unambiguous runtime location for code resolution.
* Clean machine/project boundary.
* Disk-efficient.

**Cons:**
* Per-machine setup required (cannot bundle runtime into project repo).
* CI environments need explicit handling.

### Option B: Per-project full copy (status quo pre-076)

Each `spec-kitty init` copies the full mission templates, skills, and agent configs into the project's `.kittify/` directory.

**Pros:**
* Self-contained: project carries everything it needs.
* Works in environments without a persistent home directory.
* Easy to version-control the runtime alongside the project.

**Cons:**
* Data duplication: N copies of identical templates across N projects.
* Upgrades require running `spec-kitty upgrade` in every project separately.
* Blurs machine-level and project-level state.
* Cannot distinguish "machine is configured" from "this project was initialized".

**Why Rejected:** The upgrade consistency problem alone makes this model unworkable at scale. Users with 5 or more projects experience diverging runtime versions as a regular frustration.

### Option C: Read-only global + writable per-project overlay

Global `~/.kittify/` provides read-only base templates; each project has a writable overlay that can override individual files.

**Pros:**
* Per-project customization supported at the filesystem level.
* Global upgrades still propagate to projects that don't override.

**Cons:**
* Adds a two-layer resolution system that must be implemented and documented.
* Most projects will never need per-project template overrides; the complexity has no current justification.
* Ambiguous: when a project overlay diverges from the global runtime, which one is authoritative?

**Why Rejected:** Premature generalization. The overlay mechanism solves a problem that does not yet exist in the user base. The simpler global-only model can be extended to an overlay model in a future feature if demand arises.

## More Information

* **Spec:** `kitty-specs/076-init-command-overhaul/spec.md` — FR-003 (bootstrap must surface failures explicitly), FR-016 (idempotent re-runs)
* **Related ADR:** ADR-C (2026-04-08-3) — Global skill installation with per-project symlinks
* **Related ADR:** ADR-D (2026-04-08-4) — Charter and doctrine are not init-time concerns
* **Related ADR:** ADR-6 (2026-01-23-6) — Config-driven agent management
* **Code locations:**
  * `src/specify_cli/init.py` — init command entry point
  * `src/specify_cli/core/runtime.py` — `ensure_runtime()` implementation
