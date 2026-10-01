---
name: spec-kitty-setup-doctor
description: >-
  Install, verify, and recover the modern Spec Kitty 2.0.11+ operating surface.
  Triggers: "set up Spec Kitty", "skills missing", "next is blocked",
  "runtime is broken", "doctrine assets are missing", "my agent can't find the skills".
  Does NOT handle: generic coding questions with no Spec Kitty context,
  direct runtime loop advancement, or editorial glossary maintenance.
---

# spec-kitty-setup-doctor

Diagnose and repair the Spec Kitty installation for the current project and agent.

Use this skill when the user reports that Spec Kitty is not working, skills are
missing, slash commands are unavailable, or the runtime environment appears broken.

---

## Step 1: Detect Environment

Determine the active agent, repository state, and working directory.

**What to check:**

- Which AI agent is running (Claude Code, Codex, Gemini CLI, etc.)
- Whether the current directory is inside a git repository
- Whether a `.kittify/` directory exists (indicates prior initialization)
- Whether this is a worktree or the repository root checkout

**Commands:**

```bash
git rev-parse --show-toplevel
ls .kittify/config.yaml
spec-kitty --version
```

**Expected outcome:** You know the agent identity, repo root path, and whether
Spec Kitty was previously initialized.

---

## Step 2: Verify Installation

Check that skill roots, wrapper roots, manifest, and generated artifacts are present.

**What to check:**

- Skill root directory exists for the active agent (see `references/agent-path-matrix.md`)
- Wrapper root (slash-command directory) exists for the active agent
- The relevant manifest exists and is valid JSON:
  `.kittify/skills-manifest.json` for legacy canonical skills and/or
  `.kittify/command-skills-manifest.json` for command-skill agents
- Skill files listed in the manifest are present on disk

**Commands:**

```bash
spec-kitty doctor skills --json
```

If `spec-kitty` is not installed:

```bash
pipx install spec-kitty-cli
pipx ensurepath
spec-kitty --version
```

**Expected outcome:** `spec-kitty doctor skills --json` reports a healthy command
and skill surface, or lists specific missing/drifted files.

---

## Step 3: Check Prerequisites

Verify that the working environment meets runtime requirements.

**What to check:**

- Current working directory is the repository root (not a subdirectory)
- Active branch is correct for the current workflow stage
- If using worktrees, the worktree is properly linked
- Runtime configuration in `.kittify/config.yaml` is present and valid

**Commands:**

```bash
spec-kitty agent tasks status
spec-kitty agent config status
```

**Expected outcome:** Status output shows the current kanban board, configured
agents, and active missions without errors.

---

## Step 4: Diagnose Issues

Match observed symptoms against known failure patterns.

**What to check:**

Consult `references/common-failure-signatures.md` for a catalog of known issues.
Common patterns include:

- **Missing skill root** -- agent cannot find skills directory
- **Missing wrapper root** -- slash commands not available
- **Manifest drift** -- skill files were manually edited
- **Runtime not found** -- `.kittify/` directory missing or corrupted

**How to diagnose:**

```bash
spec-kitty doctor skills --json
spec-kitty agent config status
```

Review error messages and match them against the failure signatures. Each
signature includes a symptom, cause, and deterministic recovery step.

**Expected outcome:** You have identified the specific failure pattern(s)
affecting this installation.

---

## Step 5: Recover

Apply deterministic recovery steps for each identified issue.

**Recovery actions by issue type:**

| Issue | Recovery Command |
|-------|-----------------|
| Missing skill files | `spec-kitty doctor skills --fix` |
| Missing wrapper root | `spec-kitty doctor skills --fix` |
| Missing skill root | `spec-kitty doctor skills --fix` |
| Manifest drift | `spec-kitty doctor skills --fix` |
| Runtime not found | `spec-kitty init . --ai <agent>` |
| Corrupted config | Back up and remove `.kittify/config.yaml`, then run `spec-kitty init . --ai <agent>` |

**Commands:**

```bash
# Full re-initialization (fixes most issues)
spec-kitty init . --ai <agent>

# Targeted skill repair (preserves existing config)
spec-kitty doctor skills --fix
```

**Expected outcome:** After recovery, `spec-kitty doctor skills --json` reports no
issues and `spec-kitty agent tasks status` shows a healthy installation.

---

## Step 6: Direct Next Action

After recovery is complete, point the user to the correct next step.

**Decision tree:**

1. If the user wanted to **start a new project**: `spec-kitty init . --ai <agent>`
2. If the user wanted to **specify a mission**: `/spec-kitty.specify`
3. If the user wanted to **check status**: `spec-kitty agent tasks status`
4. If the user wanted to **implement a work package**: `/spec-kitty.implement`
5. If the problem was **skills missing**: confirm skills are now visible with `spec-kitty doctor skills --json`

**What to communicate:**

- Confirm the issue is resolved
- State what was repaired
- Suggest the next logical command based on the user's original intent
- If the issue persists, recommend checking `references/common-failure-signatures.md`
  for additional patterns or filing an issue

---

## References

- `references/agent-path-matrix.md` -- Agent skill roots and wrapper roots for supported agents; verify against `AI_CHOICES`, `AGENT_COMMAND_CONFIG`, and `AGENT_SKILL_CONFIG`
- `references/common-failure-signatures.md` -- Known failure patterns with symptom/cause/recovery
