---
description: Create an implementation plan
---
# /spec-kitty.plan - Create Implementation Plan

**Version**: 0.11.0+

<!-- spdd:reasons-block:start -->

### REASONS Guidance — Plan

While composing the plan, fill or update:

- **Approach** — chosen strategy and rejected alternatives with rationale.
- **Structure** — code surfaces, components, dependencies, ownership boundaries.

Link to source artifacts (spec, contracts) instead of duplicating them.

<!-- spdd:reasons-block:end -->

## 📍 WORKING DIRECTORY: Stay in the repository root checkout

**IMPORTANT**: Plan works in the repository root checkout. NO worktrees created.

```bash
# Run from project root (same directory as /spec-kitty.specify):
# You should already be here if you just ran /spec-kitty.specify

# Creates:
# - kitty-specs/<mission_slug>/plan.md → In repository root checkout
#   (the NNN- prefix in the directory listing is display-only metadata)
# - Commits to target branch
# - NO worktrees created
```

**Do NOT cd anywhere**. Stay in the repository root checkout.

## Mission Handle Rule

`/spec-kitty.plan` operates on an existing mission, so use `--mission <handle>`
when the CLI needs a mission selector.

- `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of
  the ULID), or `mission_slug`.
- Prefer `mission_id` or `mid8` when the repo has multiple similarly named
  missions.
- The resolver disambiguates by `mission_id` and returns a structured
  `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Commit Boundary (issue #846)

`/spec-kitty.plan` will refuse to advance the plan phase unless **two**
gates pass:

1. **Entry gate.** `spec.md` must already be both **committed** (tracked +
   present at HEAD) and **substantive** (at least one populated `FR-###`
   row — not just template placeholders). If either check fails, the CLI
   returns `phase_complete=false` with a `blocked_reason` naming "committed
   AND substantive" and does **not** create or commit `plan.md`.

2. **Exit gate.** `plan.md` is only auto-committed when its Technical Context
   section contains a real `Language/Version` value (and at least one peer
   field) — not the `[e.g., …]` / `[NEEDS CLARIFICATION …]` placeholders.

   - The FIRST `setup-plan` call after the entry gate passes scaffolds
     `plan.md` from the template. This is a **non-error** state: the CLI
     returns `result: "success"` with `scaffold_only: true` and
     `phase_complete: false` — it means "plan.md is ready for you to
     populate", not a failure. Do **not** treat this call as blocked; proceed
     to fill in the Technical Context.
   - Once `plan.md` has been edited but its Technical Context is still not
     substantive, the CLI returns `result: "blocked"` with
     `phase_complete: false` and a populated-but-insufficient
     `blocked_reason` naming the missing field(s) — populate the section and
     re-run.

Section presence is the only signal — adding arbitrary prose without the
required structural rows does **not** count as substantive (no byte-length
escape hatch).

To advance: populate the Technical Context with real values, then re-run
`spec-kitty agent mission setup-plan --mission <mission-slug> --json`. The substantive plan will be
auto-committed and `phase_complete` will report `true`.

Reference: `kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/specify-plan-commit-boundary.md`.

## Issue-Matrix Approval Heads-Up (non-gating, #3469)

If `plan.md`/`research.md` cite a GitHub issue number (`#NNNN`), a bare/unmarked
reference will later require an issue-matrix row before its owning work package can be
approved. A context-only citation (e.g. `Follow-up:`, `see #`, `parent`, `epic`) or a
PR/commit reference (`PR #NNNN`, a `/pull/NNNN` URL) is non-gating and needs no row; if
an issue genuinely owes the mission no work, it can later be recorded with the
`not-applicable` verdict. This is informational only — it does not gate
`/spec-kitty.plan`.

## Branch Strategy Confirmation (MANDATORY)

Before asking planning questions or generating artifacts, you must make the branch contract explicit.

- Never describe the landing branch vaguely. Always name the actual branch value.
- If the user says the feature should land somewhere else, stop and resolve that before writing `plan.md`.
- You must repeat the branch contract twice during this command:
  1. immediately after parsing `setup-plan --json`
  2. again in the final report before suggesting `/spec-kitty.tasks`

## Charter Context Bootstrap (required)

Before planning interrogation, load charter context for this action:

```bash
spec-kitty charter context --action plan --json
```

- If JSON `mode` is `bootstrap`, apply JSON `text` as first-run governance context and follow referenced docs as needed.
- If JSON `mode` is `compact`, continue with condensed governance context.

## Visual Communication (recommended)

Apply the visual doctrine for non-trivial architecture, data/control flow,
boundaries, migrations, or risky interactions. Load `spk-doctrine-show-me` and
use the smallest diagram
that materially reduces prose. Prefer Mermaid in Markdown; use PlantUML when
richer layout, mature C4 support, or its DSL earns the added rendering cost.
Apply C4 progressive zoom for architecture and stop at the first level that
answers the planning question. Text contracts and plan decisions remain
authoritative; do not generate speculative diagrams.

## Location Check (0.11.0+)

This command runs in the **repository root checkout**, not in a worktree.

- Resolve branch context from deterministic JSON output, not from `meta.json` inspection:
  - Run `spec-kitty agent mission setup-plan --mission <mission-slug> --json`
  - Use `current_branch`, `target_branch` / `base_branch`, and `planning_base_branch` / `merge_target_branch` (plus uppercase aliases) from that payload
  - Use `branch_matches_target` from that payload to detect branch mismatch; do not probe branch state manually inside the prompt
- Planning artifacts live in `kitty-specs/<mission_slug>/` (the `NNN-` prefix is display-only metadata)
- The plan template is committed to the target branch after generation

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/tasks/`). Never refer to a folder by name alone.

## Agent Context Files (do not mutate)

This command does **not** update agent-specific context files.

- Do **not** search for or mutate `CLAUDE.md`, `AGENTS.md`, or similar
  agent-specific files as part of `/spec-kitty.plan`.
- Do **not** hunt for updater scripts or imaginary `spec-kitty agent context update`
  commands. No supported context-update command exists in this release.
- Planning outputs are the mission planning artifacts only:
  - `plan.md`
  - `research.md`
  - `data-model.md`
  - `contracts/`
  - `quickstart.md`
  - `occurrence_map.yaml` when bulk-edit planning applies

## Decision Moment Protocol

Before asking **any** clarifying question during plan elaboration, you MUST:

1. Run `spec-kitty agent decision open` to mint a decision_id:
   ```
   spec-kitty agent decision open \
     --mission <mission-slug> \
     --flow plan \
     --slot-key plan.<section>.<question-slug> \
     --input-key <snake_case_key> \
     --question "<question text>" \
     [--options '["option1","option2","Other"]']
   ```
   Capture the returned `decision_id` from the JSON output.

2. Ask the question to the user in chat.

3. After the user answers, run **exactly one** of:
   - Resolved:
     `spec-kitty agent decision resolve <decision_id> --mission <slug> --final-answer "<answer>"`
   - Deferred:
     `spec-kitty agent decision defer <decision_id> --mission <slug> --rationale "<reason>"`
   - Canceled:
     `spec-kitty agent decision cancel <decision_id> --mission <slug> --rationale "<reason>"`

4. When deferring, write the inline marker into `plan.md`:
   ```
   [NEEDS CLARIFICATION: <brief description>] <!-- decision_id: <decision_id> -->
   ```

5. Before finishing this command, run:
   `spec-kitty agent decision verify --mission <slug>`
   Resolve all findings (`DEFERRED_WITHOUT_MARKER`, `MARKER_WITHOUT_DECISION`,
   `STALE_MARKER`) before proceeding.

**Important constraints:**
- `--slot-key` format: `plan.<section>.<question-slug>` (e.g.,
  `plan.architecture.db-choice`).
- `--input-key` is the snake_case programmatic key (e.g., `db_choice`).
- The `decision_id` on the wire is a plain ULID (26 chars). The `DM-` prefix
  appears only in artifact filenames, not in CLI arguments.
- The verifier cross-checks `[NEEDS CLARIFICATION: …] <!-- decision_id: <id> -->`
  sentinels in `plan.md` against the decisions index and exits non-zero on drift.
- Widening is represented by the CLI/SaaS widen flow; if that flow returns
  canonical thread metadata, it must be recorded as `DecisionPointWidened`.
- Local-only; no SaaS calls needed.

## Planning Interrogation (mandatory)

Before executing any scripts or generating artifacts you must interrogate the specification and stakeholders.

- **Scope proportionality (CRITICAL)**: FIRST, assess the feature's complexity from the spec:
  - **Trivial/Test Features** (hello world, simple static pages, basic demos): Ask 1-2 questions maximum about tech stack preference, then proceed with sensible defaults
  - **Simple Features** (small components, minor API additions): Ask 2-3 questions about tech choices and constraints
  - **Complex Features** (new subsystems, multi-component features): Ask 3-5 questions covering architecture, NFRs, integrations
  - **Platform/Critical Features** (core infrastructure, security, payments): Full interrogation with 5+ questions

- **Scenario-to-design handoff**: For non-trivial features, anchor planning
  questions in the concrete user flows from the spec rather than generic
  architecture preferences.

- **Domain rule follow-through**: When the spec implies approvals, lifecycle
  states, irreversible operations, or business-critical validations, ask 1-2
  targeted questions about invariants, transitions, atomicity, and externally
  visible events or integrations. Skip this for trivial features.

- **User signals to reduce questioning**: If the user says "use defaults", "just make it simple", "skip to implementation", "vanilla HTML/CSS/JS" - recognize these as signals to minimize planning questions and use standard approaches.

- **First response rule**:
  - For TRIVIAL features: Ask ONE tech stack question, then if answer is simple (e.g., "vanilla HTML"), proceed directly to plan generation
  - For other features: Ask a single architecture question tied to the riskiest scenario, rule, or lifecycle constraint and end with `WAITING_FOR_PLANNING_INPUT`

- If the user has not provided plan context, keep interrogating with one question at a time.

- **Conversational cadence**: After each reply, assess if you have SUFFICIENT context for this feature's scope. For trivial features, knowing the basic stack is enough. Only continue if critical unknowns remain.

Planning requirements (scale to complexity):

1. Maintain a **Planning Questions** table internally covering questions appropriate to the feature's complexity (1-2 for trivial, up to 5+ for platform-level). Track columns `#`, `Question`, `Why it matters`, and `Current insight`. Do **not** render this table to the user.
2. For trivial features, standard practices are acceptable (vanilla HTML, simple file structure, no build tools). Only probe if the user's request suggests otherwise.
3. When you have sufficient context for the scope, summarize into an **Engineering Alignment** note and confirm. Include invariant, state-transition, or event assumptions when they materially affect the design.
4. If user explicitly asks to skip questions or use defaults, acknowledge and proceed with best practices for that feature type.

## Bulk-Edit Check (if applicable)

If this mission is marked `change_mode: bulk_edit` in `meta.json` — or if the
spec describes renaming the same string (identifier, path, key, label, term)
across many files — load the `spec-kitty-bulk-edit-classification` skill and
follow it. You will produce `kitty-specs/<mission>/occurrence_map.yaml`
alongside the other planning artifacts. Every one of the 8 standard categories
(code_symbols, import_paths, filesystem_paths, serialized_keys, cli_commands,
user_facing_strings, tests_fixtures, logs_telemetry) must have an explicit
action. Without that artifact, the `implement` command will refuse to start
the first WP.

If the mission is not a bulk edit, skip this step.

## Supply-Chain Security & Adversarial Evidence (Planning)

Apply this section whenever the plan adds, upgrades, or removes a dependency, in any ecosystem (npm/yarn/pnpm, pip/uv, Maven/Gradle, etc.).

- **Security checks**: Reference the `051-supply-chain-install-safety` directive and the `supply-chain-install-safety` tactic. Planning output (Technical Context and/or `research.md`) must surface registry authenticity, package freshness, lifecycle-script discipline (deny-by-default `preinstall`/`install`/`postinstall`), and Node Active LTS awareness for any dependency decision — this mirrors the `supply_chain_security_check` step already present in the `plan` step contract.
- **Advisory posture**: This is advisory in v1 — it does not add a new blocking gate to the Commit Boundary gates above — but an unexamined default is a gap in the plan, not a pass. Silence is not compliance.
- **Adversarial evidence (mandatory for plan/research)**: When a security-impacting dependency decision is made, run (or explicitly document deferral of) an adversarial-squad challenge pass before claiming plan readiness. Record each contested finding's disposition — `accepted`, `changed`, or `deferred_with_rationale` — in `research.md`, per `contracts/adversarial-evidence-contract.md`. No contested finding may be silently dropped.

## Outline

1. **Check planning discovery status**:
   - If any planning questions remain unanswered or the user has not confirmed the **Engineering Alignment** summary, stay in the one-question cadence, capture the user's response, update your internal table, and end with `WAITING_FOR_PLANNING_INPUT`. Do **not** surface the table. Do **not** run the setup command yet.
   - Once every planning question has a concrete answer and the alignment summary is confirmed by the user, continue.

2. **Resolve mission context deterministically** (CRITICAL - prevents wrong mission selection):
   - Prefer an explicit mission slug from user direction or from the current directory path (`kitty-specs/<mission-slug>/...`)
   - The resolver requires `--mission` — always pass an explicit handle. Running `setup-plan` without `--mission` returns `PLAN_CONTEXT_UNRESOLVED` even when exactly one mission is present.
   - Resolve the handle first: `spec-kitty agent context resolve --action plan --mission <handle> --json`, then pass the resolved slug to `setup-plan`
   - If the context resolve call returns an ambiguity error with `available_missions`, stop and pick one explicit mission slug before continuing

3. **Setup**: Run `spec-kitty agent mission setup-plan --mission <mission-slug> --json` from the repository root and parse JSON for:
   - `result`: "success" or error message
   - `scaffold_only`: `true` only on the first happy-path scaffold write (plan.md freshly copied from the template, untouched). This is `result: "success"` and NOT an error — populate the Technical Context and re-run `setup-plan` to commit. `phase_complete` stays `false` until then.
   - `mission_slug`: Resolved feature slug
   - `spec_file`: Absolute path to resolved spec.md
   - `plan_file`: Absolute path to the created plan.md
   - `feature_dir`: Absolute path to the feature directory
   - `current_branch`: branch checked out when planning started
   - `target_branch` / `base_branch` (deterministic branch contract for downstream commands)
   - `planning_base_branch` / `merge_target_branch`: explicit aliases for planning and merge intent
   - `branch_strategy_summary`: canonical sentence describing the branch strategy

   Before proceeding, explicitly state to the user:
   - Current branch at plan start
   - Intended planning/base branch
   - Final merge target for completed changes
   - Whether `branch_matches_target` says the current branch matches that intended target

   **Example**:
   ```bash
   # Resolve the active mission handle, then pass it to setup-plan.
   # The --mission flag accepts mission_id (ULID), mid8 (first 8 chars), or mission_slug.
   # The resolver disambiguates by mission_id; ambiguous handles become structured errors.
   # --action is required for context resolve; use the action matching this step.
   spec-kitty agent context resolve --action plan --mission <handle> --json
   spec-kitty agent mission setup-plan --mission <handle> --json
   ```

   **Error handling**: If the command fails with "Cannot detect mission", "Multiple missions found", or `MISSION_AMBIGUOUS_SELECTOR`, pass an unambiguous handle — the `mission_id` or its 8-char prefix `mid8` always disambiguates.

4. **Load context**: Read `spec_file` from setup-plan JSON output and `.kittify/charter/charter.md` if it exists. If the charter file is missing, skip Charter Check and note that it is absent. Load IMPL_PLAN template (already copied).

5. **Execute plan workflow**: Follow the structure in IMPL_PLAN template, using the validated planning answers as ground truth:
   - Update Technical Context with explicit statements from the user or discovery research; mark `[NEEDS CLARIFICATION: …] <!-- decision_id: <id> -->` only when the user deliberately postpones a decision (call `decision defer` before writing each such marker)
   - If a charter exists, fill Charter Check section from it and challenge any conflicts directly with the user. If no charter exists, mark the section as skipped.
   - Evaluate gates (ERROR if violations unjustified or questions remain unanswered)
   - Phase 0: Generate research.md (commission research to resolve every outstanding clarification, prioritizing unresolved domain rules, lifecycle questions, and event/integration behavior before generic tech comparisons)
   - Phase 1: Generate data-model.md, contracts/, quickstart.md based on confirmed intent; when applicable, capture entities/value objects, invariants, state transitions, and externally visible events in the design artifacts
   - Re-evaluate Charter Check post-design, asking the user to resolve new gaps before proceeding

6. **STOP and report**: This command ends after Phase 1 planning. Report branch, IMPL_PLAN path, and generated artifacts (including the Implementation Concern Map if present).

   **⚠️ CRITICAL: DO NOT proceed to task generation!** The user must explicitly run `/spec-kitty.tasks` to translate implementation concerns from `plan.md` into executable work packages. Your job is COMPLETE after reporting the planning artifacts.

## Phases

### Phase 0: Outline & Research

1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each unresolved rule, invariant, lifecycle edge, or event/integration ambiguity → domain research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each unresolved domain rule:
     Task: "Clarify invariant, state transition, or event behavior for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

### Phase 1: Design & Contracts

**Prerequisites:** `research.md` complete

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - Invariants or atomicity boundaries if applicable
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - For each externally visible event, webhook, or integration callback → contract or payload shape when applicable
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

**Output**: data-model.md, /contracts/*, quickstart.md

## Key rules

- Use absolute paths
- ERROR on gate failures or unresolved clarifications

---

## ⛔ MANDATORY STOP POINT

**This command is COMPLETE after generating planning artifacts.**

After reporting:
- `plan.md` path
- `research.md` path (if generated)
- `data-model.md` path (if generated)
- `contracts/` contents (if generated)

**YOU MUST STOP HERE.**

Do NOT:
- ❌ Generate `tasks.md`
- ❌ Create work package (WP) files
- ❌ Create `tasks/` subdirectories
- ❌ Proceed to implementation

`/spec-kitty.tasks` translates implementation concerns from `plan.md` into executable work packages. The user will run it when they are ready.

**Next suggested command**: `/spec-kitty.tasks` (user must invoke this explicitly)
