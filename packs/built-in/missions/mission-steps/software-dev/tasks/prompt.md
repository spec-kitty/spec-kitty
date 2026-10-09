---
description: Translate implementation concerns into work packages
---
# /spec-kitty.tasks - Generate Work Packages

<!-- spdd:reasons-block:start -->

### REASONS Guidance — Tasks

While translating implementation concerns from plan.md into executable work packages, capture:

- **Operations** — ordered implementation and test steps per WP.
- **WP boundaries** — explicit `owned_files` and `authoritative_surface` for each WP, plus what each WP must NOT touch (Safeguards subset).

If multiple WPs are proposed for the same surface, surface that as a Safeguard
rather than dividing it implicitly.

<!-- spdd:reasons-block:end -->

## ⚠️ CRITICAL: THIS IS THE MOST IMPORTANT PLANNING WORK

**You are creating the blueprint for implementation**. The quality of work packages determines:
- How easily agents can implement the mission
- How parallelizable the work is
- How reviewable the code will be
- Whether the mission succeeds or fails

**QUALITY OVER SPEED**: This is NOT the time to save tokens or rush. Take your time to:
- Understand the full scope deeply
- Break work into clear, manageable pieces
- Write detailed, actionable guidance
- Think through risks and edge cases

**Token usage is EXPECTED and GOOD here**. A thorough task breakdown saves 10x the effort during implementation. Do not cut corners.

---

## 📍 WORKING DIRECTORY: Stay in the repository root checkout

**IMPORTANT**: Tasks works in the repository root checkout. NO worktrees created.

```bash
# Run from project root (same directory as /spec-kitty.plan):
# You should already be here if you just ran /spec-kitty.plan

# Creates:
# - kitty-specs/<mission_slug>/tasks/WP01-*.md → In repository root checkout
# - kitty-specs/<mission_slug>/tasks/WP02-*.md → In repository root checkout
#   (the NNN- prefix in directory listings is display-only metadata)
# - Commits ALL to target branch
# - NO worktrees created
```

**Do NOT cd anywhere**. Stay in the repository root checkout.

**Worktrees created later**: After tasks are finalized, `spec-kitty next --agent <agent> --mission <handle>` issues the analyze step first (the required `/spec-kitty.analyze` gate), then hands out `spec-kitty agent action implement WP## --agent <name>` for each WP. `finalize_tasks` computes the execution lanes, and each lane gets exactly one worktree.

**In repos with multiple missions, pass `--mission <handle>` to every command that accepts `--mission`.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Context Resolution (0.11.0+)

Before proceeding, resolve canonical command context:

```bash
spec-kitty agent context resolve --action tasks --mission <mission-slug> --json
```

Treat the resolver JSON as canonical for:
- `mission_slug`
- `mission_dir`
- `current_branch`
- `target_branch`
- `planning_base_branch`
- `merge_target_branch`
- `branch_matches_target`
- exact follow-up commands (`check_prerequisites`, `finalize_tasks`)

Prompts do not rediscover mission context. Commands do.

## Outline

1. **Setup**: Run the exact `check_prerequisites` command returned by the resolver and capture:
   - `mission_dir`
   - `artifact_files` / `artifact_dirs` (if present)
   - `available_docs`
   - `current_branch`
   - `target_branch` / `base_branch`
   - `planning_base_branch` / `merge_target_branch`
   - `branch_matches_target`
   All paths must be absolute.

   If `branch_matches_target` is false, stop and tell the user the checkout is on the wrong planning branch instead of probing git manually in the prompt.

   **CRITICAL**: The command returns JSON with `mission_dir` as an ABSOLUTE path. It also returns `runtime_vars.now_utc_iso` (`NOW_UTC_ISO`) for deterministic timestamp fields.

   **YOU MUST USE THIS PATH** for ALL subsequent file operations. Example:
   ```
   mission_dir = "/path/to/project/kitty-specs/a-simple-hello-01KQ7X2M"
   tasks.md location: mission_dir + "/tasks.md"
   prompt location: mission_dir + "/tasks/WP01-slug.md"
   ```

   **DO NOT CREATE** paths like:
   - ❌ `tasks/WP01-slug.md` (missing mission_dir prefix)
   - ❌ `/tasks/WP01-slug.md` (wrong root)
   - ❌ `mission_dir/tasks/planned/WP01-slug.md` (WRONG - no subdirectories!)
   - ❌ `WP01-slug.md` (wrong directory)

3. **Load design documents** from `mission_dir` (only those present):
   - **Required**: plan.md (tech architecture, stack), spec.md (user stories & priorities)
   - **Optional**: data-model.md (entities), contracts/ (API schemas), research.md (decisions), quickstart.md (validation scenarios)
   - Scale your effort to the mission: simple UI tweaks deserve lighter coverage, multi-system releases require deeper decomposition.

4. **Derive fine-grained subtasks** (IDs `T001`, `T002`, ...):
   - Parse plan/spec to enumerate concrete implementation steps, tests (only if explicitly requested), migrations, and operational work.
   - Capture prerequisites, dependencies, and parallelizability markers (`[P]` means safe to parallelize per file/concern).
   - Maintain the subtask list internally; it feeds the work-package roll-up and the prompts.

   ### Task Tracking Format

   Per-WP subtask rows in `tasks.md` are **reference rows**, not checkboxes. Subtask
   completion is **solely event-sourced** — the reduced event-log snapshot is the
   authority; there is **no `- [ ]` box to tick**. Emit each
   `Txxx` as a plain reference row under its work package:

   ```markdown
   T001 Description of task (WP01)
   T002 Another task (WP01)
   ```

   Record completion with `spec-kitty agent tasks mark-status T001 T002 --status done`
   (single or batch). `mark-status` writes the completion into the event log; it does
   **not** flip a markdown checkbox. Do **not** use pipe-table format for tracking rows
   in work-package sections.

   **Important distinction — Subtask Index vs. reference rows**:
   The top-level **Subtask Index** pipe-table (e.g. `| T001 | desc | WP | Parallel |`) is
   a **reference table** only — it is not a tracking surface. The `[P]` marker in its
   "Parallel" column indicates parallelism, not task status. `mark-status` records
   completion in the reduced event-log snapshot keyed by the `Txxx` id, never by
   editing a markdown row.

5. **Roll subtasks into work packages** (IDs `WP01`, `WP02`, ...):

   **IDEAL WORK PACKAGE SIZE** (most important guideline):
   - **Target: 3-7 subtasks per WP** (results in 200-500 line prompts)
   - **Maximum: 10 subtasks per WP** (results in ~700 line prompts)
   - **If more than 10 subtasks needed**: Create additional WPs, don't pack them in

   **WHY SIZE MATTERS**:
   - **Too large** (>10 subtasks, >700 lines): Agents get overwhelmed, skip details, make mistakes
   - **Too small** (<3 subtasks, <150 lines): Overhead of worktree creation not worth it
   - **Just right** (3-7 subtasks, 200-500 lines): Agent can hold entire context, implements thoroughly

   **NUMBER OF WPs**: Let the work dictate the count
   - Simple mission (5-10 subtasks total): 2-3 WPs
   - Medium mission (20-40 subtasks): 5-8 WPs
   - Complex mission (50+ subtasks): 10-20 WPs ← **This is OK!**
   - **Better to have 20 focused WPs than 5 overwhelming WPs**

   **GROUPING PRINCIPLES**:
   - Each WP should be independently implementable
   - Root in a single user story or cohesive subsystem
   - Ensure every subtask appears in exactly one work package
   - Name with succinct goal (e.g., "User Story 1 – Real-time chat happy path")
   - Record metadata: priority, success criteria, risks, dependencies, included subtasks

6. **Write `tasks.md`** following the canonical tasks template structure (`tasks-template.md`, resolved through the command's template resolver — write the content directly, do not emit instructions to read a template file):
   - **Location**: Write to `mission_dir/tasks.md` (use the absolute mission_dir path from step 1)
   - Populate the Work Package sections (setup, foundational, per-story, polish) with the `WPxx` entries
   - Under each work package include:
     - Summary (goal, priority, independent test)
     - Included subtasks (reference list of `Txxx` ids, tracked via `mark-status`)
     - Implementation sketch (high-level sequence)
     - Parallel opportunities, dependencies, and risks
   - Keep the reference-list style; implementers record progress with `spec-kitty agent tasks mark-status`, not by ticking boxes

7. **Generate prompt files (one per work package)**:
   - **CRITICAL PATH RULE**: All work package files MUST be created in a FLAT `mission_dir/tasks/` directory, NOT in subdirectories!
   - Correct structure: `mission_dir/tasks/WPxx-slug.md` (flat, no subdirectories)
   - WRONG (do not create): `mission_dir/tasks/planned/`, `mission_dir/tasks/doing/`, or ANY status subdirectories
   - WRONG (do not create): `/tasks/`, `tasks/`, or any path not under mission_dir
   - Use `artifact_dirs.tasks_dir` when available.
   - Do **not** shell out with `mkdir -p`; `create` already creates `tasks/` in normal flow.
   - If `tasks/` is missing unexpectedly, report the mismatch instead of improvising shell directory setup.
   - For each work package:
     - Derive a kebab-case slug from the title; filename: `WPxx-slug.md`
     - Full path example: `mission_dir/tasks/WP01-create-html-page.md` (use ABSOLUTE path from mission_dir variable)
     - Follow the canonical WP prompt template structure (`task-prompt-template.md`, resolved through the command's template resolver — write the content directly, do not emit instructions to read a template file) to capture:
     - Frontmatter with `work_package_id`, `subtasks` array, `dependencies`, `planning_base_branch`, `merge_target_branch`, `branch_strategy`, `owned_files`, `authoritative_surface`, `execution_mode`, `agent_profile`, `role`, `agent`, `model` (optional), and history entry
       - **`## ⚡ Do This First: Load Agent Profile`** — REQUIRED, must be the first body section (before Objective). Instructs the implementing agent to load the assigned profile via the `spk-doctrine-profile-load` skill before reading anything else. See `task-prompt-template.md` for the exact block.
       - Objective, context, detailed guidance per subtask
       - A Branch Strategy section that repeats the planning branch, final merge target, and explains that execution worktrees are allocated per computed lane from `lanes.json`
       - Test strategy (only if requested)
       - Definition of Done, risks, reviewer guidance
     - Update `tasks.md` to reference the prompt filename
   - **TARGET PROMPT SIZE**: 200-500 lines per WP (results from 3-7 subtasks)
   - **MAXIMUM PROMPT SIZE**: 700 lines per WP (10 subtasks max)
   - **If prompts are >700 lines**: Split the WP - it's too large

   **IMPORTANT**: All WP files live in flat `tasks/` directory.

   **OWNERSHIP METADATA (required by finalize-tasks)**:
   Each WP MUST declare these fields in frontmatter. If omitted, the finalizer infers them (often incorrectly, causing validation failures):
   - `execution_mode`: Either `"code_change"` (source code) or `"planning_artifact"` (deliverables confined to planning surfaces — every `owned_files` entry under `kitty-specs/` or `docs/`)
   - `owned_files`: List of glob patterns for files this WP touches. Example: `["src/myapp/auth/**", "tests/myapp/test_auth.py"]`. A `code_change` WP must never list a `kitty-specs/` path here (see Ownership rules below).
   - `authoritative_surface`: Path prefix that must be a prefix of at least one owned_files entry. Example: `"src/myapp/auth/"`
   - `create_intent`: List of repo-root-relative literal paths this WP will create. Use this when an `owned_files` entry names a planned-new file that does not exist yet, so finalize-tasks treats the zero-match as an intentional planned-new-file instead of a validation failure. Example: `["tests/myapp/test_new_auth.py"]`. Keep a single `create_intent` key; if a stub `create_intent: []` already exists, replace it instead of adding a duplicate block.

   **Ownership rules**:
   - No two WPs may have overlapping `owned_files`.
   - Use specific paths, not broad globs like `src/**`.
   - **kitty-specs ownership ban**: a `code_change` WP must NOT list any `kitty-specs/` path in `owned_files` — `finalize-tasks --validate-only` rejects it with `INVALID_WP_OWNED_FILES_KITTY_SPECS`. The exemption is a `planning_artifact` WP whose **every** `owned_files` entry is confined to `kitty-specs/` or `docs/` — a planning WP that also owns a `src/`/`tests/` (or any other non-planning) path is not exempt and is rejected the same way.
   - **Where per-WP design notes go**: design notes, plan-marker edits, and other `kitty-specs/` deliverables a work package must produce belong in their own confined `planning_artifact` WP (all `owned_files` under `kitty-specs/`/`docs/`) — never inside a code WP's `owned_files`. Split a mixed WP into a planning WP plus a code WP rather than mixing the two ownership kinds.
   - Agents working on a WP should prefer to stay within their `owned_files` list; a small, well-justified out-of-map edit is acceptable when recorded with a one-line rationale (the no-overlap rule above is the real guard against parallel-WP collisions).
   - Run `spec-kitty agent mission finalize-tasks --validate-only --mission <mission-slug> --json` to check ownership before committing.

8. **Finalize tasks with dependency parsing and commit**:
   After generating all WP prompt files, run validate-only first to prove the
   finalization requirements are met:
   - Parse dependencies from tasks.md
   - Preview WP frontmatter updates without writing files
   - Validate dependencies (check for cycles, invalid references)
   - Validate requirement coverage before any commit

   **CRITICAL**: Run this preflight command from repo root:
   ```bash
   spec-kitty agent mission finalize-tasks --validate-only --mission <mission-slug> --json
   ```

   If the JSON output contains `"error": "Requirement mapping validation failed"`,
   do **not** run the mutating finalization command. Report
   `missing_requirement_refs_wps`, `unknown_requirement_refs`,
   `unmapped_functional_requirements`, and `rejected_requirement_refs` (each
   ref's reason), checked against `parsed_spec_ids`, then fix mappings with
   `spec-kitty agent tasks map-requirements --mission <mission-slug> --json` or
   by updating WP `requirement_refs`.

   Only after validate-only exits successfully, run the mutating command from
   repo root:
   ```bash
   spec-kitty agent mission finalize-tasks --mission <mission-slug> --json
   ```

   This step is MANDATORY. Without it:
   - Dependencies won't be in frontmatter
   - Branching-strategy metadata won't be normalized into every WP prompt
   - `lanes.json` won't be available to resolve the real workspace path/branch for each WP
   - Requirement refs won't be validated/normalized
   - Agents won't know which lane a WP belongs to or which workspace to enter
   - Tasks won't be committed to target branch

   **IMPORTANT - DO NOT COMMIT AGAIN AFTER THIS COMMAND**:
   - finalize-tasks COMMITS the files automatically
   - JSON output includes "commit_created": true/false and "commit_hash"
   - If commit_created=true, files are ALREADY committed - do not run git commit again
   - Other dirty files shown by 'git status' (templates, config) are UNRELATED
   - Verify using the commit_hash from JSON output, not by running git add/commit again

9. **Report**: Provide a concise outcome summary:
   - Path to `tasks.md`
   - Work package count and per-package subtask tallies
   - **Average prompt size** (estimate lines per WP)
   - **Validation**: Flag if any WP has >10 subtasks or >700 estimated lines, or is missing the `## ⚡ Do This First` section
   - Parallelization highlights
   - MVP scope recommendation (usually Work Package 1)
   - Prompt generation stats (files written, directory structure, any skipped items with rationale)
   - Finalization status (dependencies parsed, X WP files updated, committed to target branch)
   - Next required step: `/spec-kitty.analyze` — the readiness gate that must run before `/spec-kitty.implement`
   - **Implementation handoff offer** (see the Implementation Handoff section below)

Context for work-package planning: (refer to the User Input section above)

The combination of `tasks.md` and the bundled prompt files must enable a new engineer to pick up any work package and deliver it end-to-end without further specification spelunking.

## Dependency Detection (0.11.0+)

**Parse dependencies from tasks.md structure**:

The LLM should analyze tasks.md for dependency relationships:
- Explicit phrases: "Depends on WP##", "Dependencies: WP##"
- Phase grouping: Phase 2 WPs typically depend on Phase 1
- Default to empty if unclear

**Generate dependencies in WP frontmatter**:

Each WP prompt file MUST include a `dependencies` field:
```yaml
---
work_package_id: "WP02"
title: "Build API"
dependencies: ["WP01"]  # Generated from tasks.md
subtasks: ["T001", "T002"]
---
```

**Include the implementation command** in each WP prompt:

```bash
spec-kitty agent action implement <WP-id> --agent <name> --mission <mission-slug>
```

The command is the same whether or not the WP has dependencies — agents never
choose a base branch manually (`finalize-tasks` computes lanes from the declared
dependencies). Dependencies are a *claim gate*, not a different command: a WP
whose `dependencies` are not all `approved` or `done` refuses to be claimed, so
record the dependencies accurately in frontmatter rather than hand-picking a base.

## Requirement Reference Mapping (MANDATORY)

After creating all WP sections and prompt files, register requirement mappings using the CLI.
The CLI validates each ref against the requirement-ID grammar (FR, NFR, C or SC, digits, an optional lowercase letter suffix) and the IDs spec.md declares, and writes `requirement_refs` directly into each
WP file's YAML frontmatter — no sidecar files needed.

**Batch mode (recommended)** — register all WP mappings at once:
```bash
spec-kitty agent tasks map-requirements --batch '{"WP01":["FR-001","FR-002"],"WP02":["FR-003","FR-004"]}' --mission <mission-slug> --json
```

**Individual mode** — register one WP at a time:
```bash
spec-kitty agent tasks map-requirements --wp WP01 --refs FR-001,FR-002 --mission <mission-slug> --json
```

The response includes a coverage summary showing which FRs are still unmapped. Keep calling
until `unmapped_functional` is empty. Default mode is append-only: existing items stay exactly
as written and in order, and new refs are appended in canonical form (kind uppercase, suffix
lowercase). A refusal lists `parsed_spec_ids` and gives each rejected ref one reason
(`malformed`, `unknown_spec_id` or `foreign_qualified`). Cite another mission's ID as
`<mission-slug>#<ID>`; it never blocks and never counts as coverage. Use `--replace` to
overwrite a WP's refs (e.g., to correct a bad mapping).

## Issue-Matrix Approval Heads-Up (non-gating)

If a WP prompt cites a GitHub issue number (`#NNNN`), a bare/unmarked reference will
later require an issue-matrix row before that work package can be approved. A
context-only citation (e.g. `Follow-up:`, `see #`, `parent`, `epic`) or a PR/commit
reference (`PR #NNNN`, a `/pull/NNNN` URL) is non-gating and needs no row; if an issue
genuinely owes the mission no work, it can later be recorded with the `not-applicable`
verdict. This is informational only — it does not gate `/spec-kitty.tasks`.

## Task Generation Rules

**Tests remain optional**. Only include testing tasks/steps if the mission spec or user explicitly demands them.

1. **Subtask derivation**:
   - Assign IDs `Txxx` sequentially in execution order.
   - Use `[P]` for parallel-safe items (different files/components).
   - Include migrations, data seeding, observability, and operational chores.
   - **Ideal subtask granularity**: One clear action (e.g., "Create user model", "Add login endpoint")
   - **Too granular**: "Add import statement", "Fix typo" (bundle these)
   - **Too coarse**: "Build entire API" (split into endpoints)

2. **Work package grouping**:
   - **Focus on SIZE first, count second**
   - Target 3-7 subtasks per WP (200-500 line prompts)
   - Maximum 10 subtasks per WP (700 line prompts)
   - Keep each work package laser-focused on a single goal
   - Avoid mixing unrelated concerns
   - **Let complexity dictate WP count**: 20+ WPs is fine for complex missions

3. **Prioritisation & dependencies**:
   - Sequence work packages: setup → foundational → story phases (priority order) → polish.
   - Call out inter-package dependencies explicitly in both `tasks.md` and the prompts.
   - Front-load infrastructure/foundation WPs (enable parallelization)

4. **Prompt composition**:
   - Mirror subtask order inside the prompt.
   - Provide actionable implementation and test guidance per subtask—short for trivial work, exhaustive for complex flows.
   - **Aim for 30-70 lines per subtask** in the prompt (includes purpose, steps, files, validation)
   - Surface risks, integration points, and acceptance gates clearly so reviewers know what to verify.
   - Include examples where helpful (API request/response shapes, config file structures, test cases)

5. **Quality checkpoints**:
   - After drafting WPs, review each prompt size estimate
   - If any WP >700 lines: **STOP and split it**
   - If most WPs <200 lines: Consider merging related ones
   - Aim for consistency: Most WPs should be similar size (within 200-line range)
   - **Think like an implementer**: Can I complete this WP in one focused session? If not, it's too big.

6. **Think like a reviewer**: Any vague requirement should be tightened until a reviewer can objectively mark it done or not done.

## Implementation Handoff

### Step 10: Implementation Handoff Offer

After reporting, ask the user directly:

> **Should I use the `/spec-kitty-implement-review` skill to fully implement all WPs until completion?**
> This will dispatch implementing and reviewing agents for every WP, handle rejection cycles, and merge all lanes when done.
>
> **Required pre-implementation gate:** `/spec-kitty.analyze` must run before any WP implementation. It persists an `analysis-report.md` and reviews spec/plan/task consistency; the implement gate refuses to start (`analysis_report_required`) until that report exists. This is not optional — it is the readiness gate `/spec-kitty.implement` enforces.

**Staleness rule:** the analysis report is current only while the spec, plan,
tasks and charter are unchanged. Editing any of the spec, plan, tasks or charter
after `/spec-kitty.analyze` makes the report stale, and `/spec-kitty.implement`
refuses again until you re-run `/spec-kitty.analyze`. Run analyze last, after the
planning artifacts have settled.

- If the user says **yes**: first ensure `/spec-kitty.analyze` has been run for this mission (run it now if `analysis-report.md` is missing — implementation cannot claim a WP without it), then invoke the `spec-kitty-implement-review` skill with the mission slug. The user may also specify which agents to use for implementation and review (e.g., "yes, use sonnet for implementing and opus for reviewing").
- If the user says **no** or wants to do it manually: end here and let them run `/spec-kitty.implement` at their own pace — reminding them that `/spec-kitty.analyze` is a required prerequisite the implement gate enforces.
- If the user wants to review consistency findings first: run `/spec-kitty.analyze --mission <mission-slug>` (also the required gate) and wait for the user's decision on whether to address findings before invoking implementation.
- If the user asks for a subset (e.g., "just WP01 and WP02 for now"): invoke the skill with that scope.

This handoff is the natural transition from planning to execution. Do NOT skip the question — always offer it explicitly so the user can choose their execution strategy.

## ⚠️ Common Mistakes to Avoid

### ❌ MISTAKE 1: Optimizing for WP Count

**Bad thinking**: "I'll create exactly 5-7 WPs to keep it manageable"
→ Results in: 20 subtasks per WP, 1200-line prompts, overwhelmed agents

**Good thinking**: "Each WP should be 3-7 subtasks (200-500 lines). If that means 15 WPs, that's fine."
→ Results in: Focused WPs, successful implementation, happy agents

### ❌ MISTAKE 2: Token Conservation During Planning

**Bad thinking**: "I'll save tokens by writing brief prompts with minimal guidance"
→ Results in: Agents confused during implementation, asking clarifying questions, doing work wrong, requiring rework

**Good thinking**: "I'll invest tokens now to write thorough prompts with examples and edge cases"
→ Results in: Agents implement correctly the first time, no rework needed, net token savings

### ❌ MISTAKE 3: Mixing Unrelated Concerns

**Bad example**: WP03: Misc Backend Work (12 subtasks)
- T010: Add user model
- T011: Configure logging
- T012: Set up email service
- T013: Add admin dashboard
- ... (8 more unrelated tasks)

**Good approach**: Split by concern
- WP03: User Management (T010-T013, 4 subtasks)
- WP04: Infrastructure Services (T014-T017, 4 subtasks)
- WP05: Admin Dashboard (T018-T021, 4 subtasks)

### ❌ MISTAKE 4: Insufficient Prompt Detail

**Bad prompt** (~20 lines per subtask):
```markdown
### Subtask T001: Add user authentication

**Purpose**: Implement login

**Steps**:
1. Create endpoint
2. Add validation
3. Test it
```

**Good prompt** (~60 lines per subtask):
```markdown
### Subtask T001: Implement User Login Endpoint

**Purpose**: Create POST /api/auth/login endpoint that validates credentials and returns JWT token.

**Steps**:
1. Create endpoint handler in `src/api/auth.py`:
   - Route: POST /api/auth/login
   - Request body: `{email: string, password: string}`
   - Response: `{token: string, user: UserProfile}` on success
   - Error codes: 400 (invalid input), 401 (bad credentials), 429 (rate limited)

2. Implement credential validation:
   - Hash password with bcrypt (matches registration hash)
   - Compare against stored hash from database
   - Use constant-time comparison to prevent timing attacks

3. Generate JWT token on success:
   - Include: user_id, email, issued_at, expires_at (24 hours)
   - Sign with SECRET_KEY from environment
   - Algorithm: HS256

4. Add rate limiting:
   - Max 5 attempts per IP per 15 minutes
   - Return 429 with Retry-After header

**Files**:
- `src/api/auth.py` (new file, ~80 lines)
- `tests/api/test_auth.py` (new file, ~120 lines)

**Validation**:
- [ ] Valid credentials return 200 with token
- [ ] Invalid credentials return 401
- [ ] Missing fields return 400
- [ ] Rate limit enforced (test with 6 requests)
- [ ] JWT token is valid and contains correct claims
- [ ] Token expires after 24 hours

**Edge Cases**:
- Account doesn't exist: Return 401 (same as wrong password - don't leak info)
- Empty password: Return 400
- SQL injection in email field: Prevented by parameterized queries
- Concurrent login attempts: Handle with database locking
```

## Remember

**This is the most important planning work you'll do.**

A well-crafted set of work packages with detailed prompts makes implementation smooth and parallelizable.

A rushed job with vague, oversized WPs causes:
- Agents getting stuck
- Implementation taking 2-3x longer
- Rework and review cycles
- Mission failure
