---
description: Materialize work package files
---
# /spec-kitty.tasks-packages - Generate Work Package Files

**Version**: 3.2.0

## Purpose

Generate individual `tasks/WP*.md` prompt files from the manifest in `wps.yaml`.
This step reads `wps.yaml` (written in tasks-outline), updates it with per-WP
details, then generates the WP prompt files.

This step assumes `wps.yaml` already exists with complete WP definitions.

---

## 📍 WORKING DIRECTORY: Stay in the repository root checkout

**IMPORTANT**: This step works in the repository root checkout. NO worktrees created.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

## Steps

### 1. Setup

Run:

```bash
spec-kitty agent context resolve --action tasks_packages --mission <mission-slug> --json
```

Then execute the returned `check_prerequisites` command and capture
`feature_dir`. All paths must be absolute.

### 2. Load `wps.yaml`

Read `feature_dir/wps.yaml`. This is the manifest written in the previous step.
Each entry defines a WP with its `id`, `title`, `dependencies`, and partial metadata.

Parse all work package entries. The YAML structure is:

```yaml
work_packages:
  - id: WP01
    title: "..."
    dependencies: [...]   # may be present (authoritative) or absent
    owned_files: [...]    # may be absent — fill in this step
    requirement_refs: [...] # may be absent — fill in this step
    subtasks: [...]
    prompt_file: null     # fill in this step
```

### 3. Generate Prompt Files in Parallel

Parse all WP definitions from `wps.yaml`. Each WP prompt file is independent —
dispatch one sub-agent per WP in a **single message** so they run concurrently
rather than generating all WP content in one serial response.

**CRITICAL PATH RULE**: All WP files MUST be created in a FLAT `feature_dir/tasks/`
directory, NOT in subdirectories!

- Correct: `feature_dir/tasks/WPxx-slug.md` (flat, no subdirectories)
- WRONG: `feature_dir/tasks/planned/`, `feature_dir/tasks/doing/`, or ANY status subdirectories

**Batching for large missions**: If there are more than 6 WPs, dispatch in groups
of 4. Send all agents in a group in one message, wait for all to complete, then
start the next group.

**Sub-agent prompt** (send one per WP, all dispatched simultaneously in one message):

---

You are writing a single Work Package prompt file for the spec-kitty planning
pipeline. Write exactly one file and return the filename and final line count.

**Feature directory**: `{feature_dir}` (absolute path)
**Write to**: `{feature_dir}/tasks/{wp_id}-{slug}.md`

**Work Package** (from wps.yaml):
- id: `{wp_id}`
- title: `{title}`
- dependencies: `{dependencies}`
- owned_files: `{owned_files}`
- execution_mode: derive from `owned_files` (`planning_artifact` only when every entry is confined to `kitty-specs/` or `docs/`, otherwise `code_change`; see Ownership rules below)
- requirement_refs: `{requirement_refs}`
- subtasks: `{subtasks}`

**Read for context** (all from `feature_dir`):
- `plan.md` (required — tech architecture, stack)
- `spec.md` (required — user stories, acceptance criteria)
- `data-model.md`, `research.md` (read if present)

**Write the WP prompt file with this structure:**

Frontmatter:
```yaml
---
work_package_id: "{wp_id}"
title: "{title}"
dependencies: {dependencies}
requirement_refs: {requirement_refs}
subtasks: {subtasks}
owned_files: {owned_files}
authoritative_surface: "{longest common path prefix of owned_files}"
execution_mode: "{execution_mode}"
agent_profile: ""  # filled in Step 4a — profile identifier (e.g., implementer-ivan)
role: ""           # filled in Step 4a — role within the profile (e.g., "implementer")
agent: ""          # filled in Step 4a — CLI agent identifier (claude, codex, copilot, etc.)
model: ""          # filled in Step 4a — model identifier (e.g., claude-sonnet-4-6), optional
---
```

**IMPORTANT — `plan_concern_refs` lives in `wps.yaml` only.** Do NOT copy `plan_concern_refs` into WP prompt frontmatter. `WPMetadata` uses `extra="forbid"`, so any WP prompt file with `plan_concern_refs` in its frontmatter will cause `finalize-tasks --validate-only` to raise a `ValidationError`.

Body sections (in order):
0. `## ⚡ Do This First: Load Agent Profile` — **REQUIRED. Must be the first section after the H1 title, before Objective.** Instructs the implementing agent to load the assigned profile via `/ad-hoc-profile-load` before reading anything else. Use this exact structure, substituting frontmatter values:
   ```markdown
   ## ⚡ Do This First: Load Agent Profile

   Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

   - **Profile**: `{agent_profile}`
   - **Role**: `{role}`
   - **Agent/tool**: `{agent}`

   If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

   ---
   ```
1. `## Objective` — 1–3 sentence goal
2. `## Context` — why this WP exists, what depends on it, key design decisions from plan.md
3. `### Subtask {T-id}: {name}` — one section per subtask, ~60 lines each:
   - **Purpose**: what this subtask accomplishes
   - **Steps**: numbered, with specific file paths and implementation details
   - **Files**: what to create/modify, approximate size
   - **Validation**: how to verify it works
4. `## Definition of Done` — verifiable criteria covering all subtasks; per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox
5. `## Risks` — known risks and mitigations
6. `## Reviewer Guidance` — what reviewers should focus on

Include the implementation command: `spec-kitty agent action implement {wp_id} --agent <name>`

Sizing: target 200–500 lines (3–7 subtasks), maximum 700 lines (10 subtasks).
If >700 lines would be needed: write the file anyway but add a `> NOTE: This WP
should be split` callout at the top.

---

**After all sub-agents confirm completion**, proceed to Step 4.

**Fallback — if your host does not support sub-agents**: Generate all WP files
sequentially and issue all Write tool calls in a single batched response.

Do NOT update `wps.yaml` during sub-agent dispatch — collect all confirmations,
then update once in Step 4.

### 4. Update `wps.yaml` With Per-WP Details

After all sub-agents have confirmed completion, update `wps.yaml` once with all
per-WP details collected from sub-agent results: `owned_files`, `requirement_refs`,
`subtasks`, and `prompt_file` for every WP. Write the updated `wps.yaml` in a
single write.

**Critical rule**: Do NOT modify a `dependencies` field that is already present in
`wps.yaml` — even if it is empty (`[]`). It is authoritative. Only populate
`dependencies` for entries where the key is **absent** from `wps.yaml`.

Example of a fully-populated entry after this step:

```yaml
- id: WP02
  title: "Build API"
  dependencies:
    - WP01
  owned_files:
    - "src/api/**"
  requirement_refs:
    - FR-001
    - NFR-001
  plan_concern_refs:
    - IC-02
  subtasks:
    - T001
    - T002
  prompt_file: "tasks/WP02-build-api.md"
```

The frontmatter in each WP prompt file MUST include a `dependencies` field:

```yaml
---
work_package_id: "WP02"
title: "Build API"
dependencies: ["WP01"]  # From wps.yaml
requirement_refs: ["FR-001", "NFR-001"]  # From wps.yaml requirement_refs
subtasks: ["T001", "T002"]
owned_files: ["src/api/**"]
authoritative_surface: "src/api/"
execution_mode: "code_change"
---
```

**Note**: `plan_concern_refs` is a `wps.yaml`-only field. It must NOT appear in WP prompt frontmatter — `WPMetadata` (`extra="forbid"`) will reject any WP file that includes it.

Include the correct implementation command:
- `spec-kitty agent action implement WP01 --agent <name>`
- `spec-kitty agent action implement WP02 --agent <name>`

`finalize_tasks` computes execution lanes from dependencies and write ownership. Agents never choose a base branch manually.

**Ownership rules**:
- `owned_files`: List of glob patterns for files this WP touches — no two WPs may overlap.
- `authoritative_surface`: Path prefix that must be a prefix of at least one `owned_files` entry.
- `execution_mode`: `"code_change"` for source code changes, `"planning_artifact"` only for work confined to planning surfaces.
- **kitty-specs ownership ban**: a `code_change` WP must NOT list any `kitty-specs/` path in `owned_files` — `finalize-tasks --validate-only` rejects it with `INVALID_WP_OWNED_FILES_KITTY_SPECS`. The exemption is a `planning_artifact` WP whose **every** `owned_files` entry is confined to `kitty-specs/` or `docs/` — a planning WP that also owns a `src/`, `tests/`, or any other non-planning path is not exempt and is rejected the same way.
- **Where per-WP design notes go**: design notes, plan-marker edits, and other `kitty-specs/` deliverables belong in their own separate confined `planning_artifact` WP, with every `owned_files` entry under `kitty-specs/` or `docs/`. Split a mixed WP into a planning WP plus a code WP rather than mixing the two ownership kinds.
- Agents working on a WP should prefer to stay within their `owned_files` list; a small, well-justified out-of-map edit is acceptable when recorded with a one-line rationale (the no-overlap rule above is the real guard against parallel-WP collisions).

### 4a. Assign Agent Profiles

After all WP files are written and `wps.yaml` is updated, review all available doctrine-provided and user-created agent profiles and assign the most relevant profile to each work package.

List available profiles:
```bash
spec-kitty agent profile list --json
```

> Only a read-only harness that cannot invoke the CLI may inspect profiles under
> `packs/built-in/agent_profiles/` and any user-defined profile directory.
> This degraded fallback can diverge because organization/project overlays,
> `specializes_from` lineage, and `enhances`/`overrides` semantics are not applied;
> state that limitation when selecting a profile this way.

For each WP, select the best-matching profile based on `task_type`, `authoritative_surface`, `owned_files`, and subtask content. Then update the WP prompt file's frontmatter **in place** with:
- `agent_profile`: the profile identifier (e.g., `"implementer-ivan"`, `"architect-alphonso"`, `"curator-carla"`)
- `role`: the role within the profile (e.g., `"implementer"`, `"reviewer"`)
- `agent`: the CLI agent/tool identifier (e.g., `"claude"`, `"codex"`, `"copilot"`)
- `model`: the model identifier (optional, e.g., `"claude-sonnet-4-6"`)

Also update the corresponding entry in `wps.yaml` with these fields.

### 5. Self-Check

After all sub-agents complete, verify each generated prompt:
- `## ⚡ Do This First: Load Agent Profile` is the **first body section** (before Objective)? ✓ ❌ if missing
- Subtask count: 3-7? ✓ | 8-10? ⚠️ | 11+? ❌ needs splitting
- Estimated lines: 200-500? ✓ | 500-700? ⚠️ | 700+? ❌ needs splitting
- `agent_profile`, `role`, `agent` set for every WP? ✓
- owned_files glob patterns non-overlapping across all WPs? ✓
- Can implement in one session? ✓ | Multiple sessions needed? ❌ needs splitting

## Output

After completing this step:
- `feature_dir/tasks/WP*.md` prompt files exist for all work packages
- Each has proper frontmatter with `work_package_id`, `dependencies`, `owned_files`, `authoritative_surface`, `execution_mode`
- `feature_dir/wps.yaml` is fully populated: all `owned_files`, `requirement_refs`, `subtasks`, and `prompt_file` fields are set

**Next step**: `spec-kitty next --agent <name>` will advance to finalization.

## Prompt Quality Guidelines

**Good prompt** (~60 lines per subtask):
```markdown
### Subtask T001: Implement User Login Endpoint

**Purpose**: Create POST /api/auth/login endpoint that validates credentials and returns JWT token.

**Steps**:
1. Create endpoint handler in `src/api/auth.py`:
   - Route: POST /api/auth/login
   - Request body: `{email: string, password: string}`
   - Response: `{token: string, user: UserProfile}` on success
   - Error codes: 400, 401, 429

2. Implement credential validation:
   - Hash password with bcrypt
   - Use constant-time comparison

**Files**: `src/api/auth.py` (new, ~80 lines)
**Validation**: Valid credentials return 200 with token
```

**Bad prompt** (~20 lines per subtask):
```markdown
### T001: Add auth
Steps: Create endpoint. Add validation. Test it.
```

Context for work-package planning: (refer to the User Input section above)
