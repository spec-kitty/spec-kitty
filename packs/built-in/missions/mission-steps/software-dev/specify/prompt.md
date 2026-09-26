---
description: Create a mission specification
---
# /spec-kitty.specify - Create Mission Specification

**Version**: 0.11.0+

<!-- spdd:reasons-block:start -->

### REASONS Guidance — Specify

This project's charter selected the SPDD/REASONS doctrine pack. While capturing
the spec, populate or update these REASONS canvas sections:

- **Requirements** — problem statement, acceptance criteria, definition of done.
- **Entities** — domain concepts, relationships, canonical glossary terms.

Reference: `kitty-specs/<mission>/reasons-canvas.md` if present. Use the
template at `src/doctrine/templates/fragments/reasons-canvas-template.md` if
the canvas does not yet exist.

Charter directives take precedence over canvas content.

<!-- spdd:reasons-block:end -->

## 📍 WORKING DIRECTORY: Stay in the repository root checkout

**IMPORTANT**: Specify works in the repository root checkout. NO worktrees are created.

```bash
# Run from the repository root checkout:
cd /path/to/project/root  # Your repository root checkout

# All planning artifacts are created in the project root and committed:
# - kitty-specs/<mission_slug>/spec.md → Created in project root
#   (use the mission_slug returned by `mission create`; the numeric NNN- prefix
#    is display-only and is assigned at merge time)
# - Committed to target branch (from create JSON: target_branch/base_branch)
# - NO worktrees created
```

**Worktrees are created later** during `/spec-kitty.implement`, after task finalization computes execution lanes.

## Mission Handle Rule

Create the Mission scaffold before asking any discovery or brief-intake question.
The initial invocation text is enough to derive a provisional identity; it is
not the final specification. Mission creation establishes the handle and empty
scaffold only: it does not authorize writing substantive spec content or
committing it.

- Do **not** pass `--mission` to `spec-kitty agent mission branch-context` or
  to the initial `spec-kitty agent mission create` command.
- Derive a concise provisional title and kebab-case slug from the initial user
  input, resolve branch intent, then run `mission create` before interview.
- After `create` succeeds, use the returned `mission_slug` or `mission_id` as
  `<handle>` for every Decision Moment and command that operates on the Mission.
- `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of
  the ULID), or `mission_slug`.
- The resolver disambiguates by `mission_id` and returns a structured
  `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Mission Type and Creation Metadata Bootstrap (before create)

Mission creation emits the canonical `MissionCreated` lifecycle event and
selects the type-specific spec scaffold. Resolve and freeze the activated
Mission type before `mission create`. Mission type cannot be changed after
creation.

1. List the Mission types activated for this project:

   ```bash
   spec-kitty mission list --json
   ```

2. Infer the type from the initial invocation text, an available brief, or an
   explicit user selection. Building or changing software normally selects
   `software-dev`; investigation or analysis may select `research`. Never
   select a type that is absent from the activation-filtered list.
3. If the type is genuinely ambiguous, ask one short Mission-type selection
   question before `create`. This is immutable lifecycle bootstrap and
   operational preflight, not a discovery interview; do not open a Decision
   Moment for it. If the user supplied an explicit type, do not ask again.
4. Derive and freeze a truthful creation snapshot: `friendly_name`,
   `purpose_tldr`, and `purpose_context`. These values describe the initial
   Mission purpose recorded by `MissionCreated`; the later confirmed Intent
   Summary governs `spec.md` and may be more precise.

This prompt owns only the `software-dev` specification contract. It may
bootstrap another activated Mission type so the Mission exists before its
agent-host interaction, but after create/resume it must hand off immediately to
that type's runtime action as described below. Never apply this prompt's
FR/NFR/C schema, software quality checklist, `spec-commit`, or `setup-plan`
steps to a non-`software-dev` Mission.

Do not rewrite `friendly_name`, `purpose_tldr`, `purpose_context`, or
`mission_type` during specify. There is no metadata-update lifecycle event in
this flow, so mutating those fields after creation would make `meta.json`
disagree with canonical event history.

## Execution Order Contract

Follow these transitions in order; do not advance by merely finding similarly
named headings elsewhere in this prompt:

1. Load charter/brief context, resolve branch strategy, freeze the Mission type
   and creation metadata, then perform the resume probe.
2. If no matching scaffold exists, run `spec-kitty agent mission create`
   exactly once with the frozen type and metadata. If a matching incomplete
   scaffold exists, reuse it and do not create another Mission.
3. After creation or verified resume succeeds, branch on the frozen type:
   - For `software-dev`, run `spec-kitty agent decision open` for the first
     interview Decision Moment.
   - For any other type, first query its runtime state with
     `spec-kitty next --agent <agent> --mission <handle> --json`. Only when
     that query reports `kind: "query"` and `mission_state: "not_started"`
     may you issue the first runtime action with `--result success`. If the
     query reports an existing run or outstanding step, never report success
     for work you did not execute; stop this prompt and resume or recover that
     type-specific action explicitly.
4. For `software-dev`, ask the discovery question. Resolve, defer, or cancel that Decision
   Moment before opening the next one.
5. Only after the user confirms the Intent Summary, write substantive
   requirements and run `spec-kitty spec-commit` with both `spec.md` and
   `meta.json`.

## Primary Invariant: What Are We Building?

This workflow answers "What are we building?" before it writes substantive
artifacts. The raw invocation text is only a starting point for discovery, not
the final truth.

Before writing substantive `spec.md` content or committing it, you **MUST** have
one of these:

- A completed discovery interview with an acknowledged Intent Summary.
- A brief-intake summary and extracted requirement set explicitly confirmed by
  the user.
- An explicit user instruction to minimize or skip discovery; even then, record
  the minimal confirmed scenario and assumptions in the Intent Summary.

For non-trivial work, the confirmed Intent Summary must cover the primary actor,
trigger, desired outcome, one rule or invariant, and any canonical domain term
or boundary that materially affects the work.

The early Mission scaffold exists so the interview can record Decision Moments;
it does not weaken this confirmed-intent gate.

## Branch Strategy Confirmation (MANDATORY)

Branch target and strategy confirmation is operational preflight, not a
discovery interview. It may require a user response before `create`, but do
not open a Decision Moment for it. Do not ask a product, requirements, or
implementation question before `create` succeeds. For an empty invocation,
one bootstrap identity prompt is permitted before `create` solely to obtain a
working Mission name; it is not a discovery question. The Decision Moment
Protocol begins only after `create` succeeds.

Before discovery, resolve branch intent through the Python helper, not by probing git directly:

```bash
spec-kitty agent mission branch-context --json
```

If the user already told you the intended landing branch, pass it explicitly:

```bash
spec-kitty agent mission branch-context --json --target-branch <intended-branch>
```

Parse the JSON and, in your next reply, explicitly tell the user:

- Current branch at workflow start: `current_branch`
- Default planning/base branch if you create the mission right now: `planning_base_branch`
- Final merge target for completed changes: `merge_target_branch`
- Whether `branch_matches_target` is true or false
- If that is not the intended landing branch, stop and ask which branch should receive this feature before you run `create`

Never talk generically about `main` or "the default branch". Name the actual branch values from the helper JSON. Do not shell out to git to *resolve* branch state for this prompt — the helper is the source of truth.

### Primary-branch recommendation (issue #765)

The helper JSON also returns a primary-branch recommendation payload:

- `primary_branch` — the repository's primary branch (e.g. `main`)
- `current_is_primary` — `true` when you are standing on that primary branch
- `recommended_strategy` — `feature-branch` (start a dedicated branch) or `stay`
- `reason` — a human-readable explanation you should relay to the user

When `current_is_primary` is `true`, you **must** have an explicit branching-strategy conversation **before** calling `create` and create on a dedicated feature branch:

1. Relay the `reason` to the user and ask whether they expect to open a pull request for this work later (the default assumption for mission work is yes).
2. **If they expect a PR (recommended path):** recommend starting on a dedicated feature branch now, and propose a name derived from the provisional slug — e.g. `feat/<slug>` (use `fix/<slug>` for a bug-fix mission). Pass that branch to `create` with `--start-branch` so the CLI creates/switches to it before writing any mission artifacts:

   ```bash
   spec-kitty agent mission create "<slug>" \
     --mission-type "<mission-type>" \
     --friendly-name "<title>" \
     --purpose-tldr "<purpose_tldr>" \
     --purpose-context "<purpose_context>" \
     --json \
     --pr-bound \
     --branch-strategy already-confirmed \
     --start-branch feat/<slug>
   ```

   Use the full `create` command in the Outline section below; the example here only shows the required branch flags. Do not run a separate raw `git switch` for this flow.
3. **If they do not expect a PR:** a dedicated feature branch is still required
   for specify. Planning artifacts do not fall back to the coordination branch,
   and `spec-commit` refuses a protected primary ref. Explain that invariant,
   propose a non-protected `feat/<slug>` or `fix/<slug>` branch, and use
   `--start-branch`. If the user declines, stop before `create` rather than
   beginning a Mission that cannot complete specify safely.

When `current_is_primary` is `false`, you are already on a feature branch — no branch switch is needed; proceed normally.

## Commit Boundary (issue #846)

`spec-kitty agent mission create` no longer auto-commits `spec.md`. The empty
template is written to disk untracked at create time; **you** are responsible
for committing it after writing substantive content.

"Substantive content" for `spec.md` means **at least one Functional
Requirements row** (`FR-###`) whose description is real (not a template
placeholder like `[NEEDS CLARIFICATION …]`, `[e.g., …]`, or a bare user-story
scaffold). Section presence is the only signal — adding 300 bytes of arbitrary
prose without an FR row does **not** count as substantive.

Workflow:

1. Run `spec-kitty agent mission create …`. Note that `spec.md` is left
   untracked.
2. Populate `spec.md` with real Functional / Non-Functional / Constraint rows.
3. Commit `spec.md` yourself using the mission-aware entrypoint. To capture
   post-create fields such as `pr_bound`, pending-origin binding, or an optional
   `source_description`, always commit `spec.md` and `meta.json` together:
   ```bash
   spec-kitty spec-commit --mission <slug> --message "Add spec for mission <slug>" \
     <feature_dir>/spec.md <feature_dir>/meta.json
   ```
   Planning/spec artifacts stay in the primary partition and never transit the
   coordination worktree. On the dedicated non-protected feature branch this
   commit is direct. If routing reports a protected-ref refusal, stop and repair
   branch placement; do not retry against the protected ref or claim that the
   coordination branch is a fallback.
4. Only then will `spec-kitty agent mission setup-plan` accept the spec phase
   as complete; otherwise it returns `phase_complete=false` with a
   `blocked_reason` mentioning "committed AND substantive".

Reference: `kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/specify-plan-commit-boundary.md`.

## DO NOT

- Do not mix functional, non-functional, and constraint requirements in one list.
- Do not emit requirements without stable IDs (`FR-###`, `NFR-###`, `C-###`).
- Do not leave requirement status fields empty.
- Do not write non-functional requirements without measurable thresholds.
- Do not proceed to planning with unresolved requirement quality checklist failures.

## Issue-Matrix Approval Heads-Up (non-gating, #3469)

If the spec cites a GitHub issue number (`#NNNN`), a bare/unmarked reference will later
require an issue-matrix row before its owning work package can be approved. A
context-only citation (e.g. `Follow-up:`, `see #`, `parent`, `epic`) or a PR/commit
reference (`PR #NNNN`, a `/pull/NNNN` URL) is non-gating and needs no row; if an issue
genuinely owes the mission no work, it can later be recorded with the `not-applicable`
verdict. This is informational only — it does not gate `/spec-kitty.specify`.

## Charter Context Bootstrap (required)

Before discovery questions, load charter context for this action:

```bash
spec-kitty charter context --action specify --json
```

- If JSON `mode` is `bootstrap`, treat JSON `text` as the initial governance context and consult referenced docs as needed.
- If JSON `mode` is `compact`, proceed with concise governance context.
- If no charter exists yet, note that and continue. Missing charter is not a
  blocker for `/spec-kitty.specify`.

## Visual Communication (recommended)

Apply the visual doctrine when a non-trivial actor flow, domain lifecycle,
rule, or concept boundary is clearer visually. Load `spk-doctrine-show-me` and
add the smallest useful diagram. Prefer an inline Mermaid diagram; use PlantUML
only when its richer layout or DSL materially helps. Keep the visual focused on
product intent—do not introduce implementation architecture into the
specification. Requirements and acceptance scenarios remain authoritative, and
trivial content needs no diagram.

## Brief Context Detection (check before discovery)

Before starting discovery, check for a pre-existing mission brief:

```bash
ls .kittify/mission-brief.md 2>/dev/null && echo "MISSION_BRIEF_FOUND"
ls .kittify/ticket-context.md 2>/dev/null && echo "TICKET_CONTEXT_FOUND"
```

Check in priority order:
1. `.kittify/mission-brief.md` — general plan intake (written by `spec-kitty intake`)
2. `.kittify/ticket-context.md` — tracker ticket (written by `mission create --from-ticket`)

### If a brief file is found → Enter Brief-Intake Mode

**BRIEF DETECTED: `.kittify/<filename>` (source: `<source_file>`)**

1. **Read the full brief.** Do not skim.

1b. **If the brief is a structured handoff packet, adopt its IDs verbatim.**
    A structured packet is a Markdown file whose YAML frontmatter declares
    `handoff_packet: 1` (contract: `docs/contracts/handoff-packet-v1.md`).
    Also inspect `.kittify/brief-source.yaml` for `packet_version` /
    `requirement_ids` written by `spec-kitty intake`.

    When a v1 packet is present:
    - Use each `requirements[].id` as the `FR-###` id. Do **not** renumber.
    - Copy `requirements[].statement` as the FR statement.
    - Preserve `requirements[].source_id` as a trace on that FR (e.g.
      `Source: TKT-1042` or an equivalent spec.md trace field).
    - Adopt nested `acceptance_criteria[].id` verbatim; do not mint new AC ids
      for criteria the packet already numbered.
    - Adopt `constraints[].id` as `C-###` (and `NFR-###` only when the
      constraint is genuinely non-functional and unnumbered).
    - Treat packet quality as **Comprehensive** (0–1 gap-filling questions)
      when `requirements` is non-empty.
    - Unknown `handoff_packet` versions, malformed YAML, or a missing
      `requirements` list are **not** packets — fall through to prose
      extraction below. Do not fail specify because the overlay is absent.

    Still run the one-round user confirmation in step 5. Packet intake does
    not skip the discovery gate.

2. **Summarise for the user.** Present a single paragraph: what the brief says the goal is, who it is for, and what the key constraints are. Example: "I found a plan document from Claude Code plan mode. Here's what I understand the goal to be: [summary]. I'll extract the spec from this brief rather than running a full discovery interview." For a structured packet, name the `source_tool` and how many FR ids you adopted.

3. **Extract requirements directly.** Map the brief's content to `FR-###`, `NFR-###`, and `C-###` IDs. Do not ask questions the brief already answers. Specifically extract:
   - Objective → Functional Requirements
   - Constraints and non-goals → Non-Functional Requirements and Constraints
   - Acceptance criteria → FR status and Definition of Done markers
   - Risks and open questions → Assumptions or `[NEEDS CLARIFICATION: <text>] <!-- decision_id: <id> -->` markers (max 3; use `decision defer` before writing each marker)

4. **Ask gap-filling questions only.** Scale to brief quality:

   | Brief quality | Discovery questions |
   |---------------|---------------------|
   | Comprehensive (objective + constraints + approach + ACs) | 0–1 gap-filling questions |
   | Good (objective + constraints, no ACs) | 2–3 questions |
   | Partial (goal statement only) | 4–5 questions |
   | Empty / missing | Proceed to normal Discovery Gate below |

5. **Show the extracted requirement set.** Present the full FR/NFR/C table to the user: "I extracted X functional requirements and Y non-functional requirements. Does this look right?" Wait for one round of confirmation. This confirmation is the discovery gate for brief-intake mode; do not write or commit `spec.md` before it happens unless the user explicitly asks to minimize or skip discovery. The user may correct or supplement before you write the spec.

6. **Write spec.md normally.** Apply the same quality checklist and readiness gate as standard specify. Brief-intake mode does NOT lower the quality bar — spec.md must still pass all validation items.

7. **After spec.md is committed, delete all brief files** (each only if present):
   ```bash
   rm -f .kittify/mission-brief.md
   rm -f .kittify/brief-source.yaml
   rm -f .kittify/ticket-context.md
   rm -f .kittify/pending-origin.yaml
   ```

**What brief-intake mode does NOT do:**
- Does not copy brief prose verbatim into spec.md — it extracts and structures requirements
- Does not skip the quality checklist
- Does not skip the readiness gate
- Does not require the brief to be in any particular format — Markdown prose is fine
- Does not renumber `FR-###` / `AC-###` ids when a v1 handoff packet supplied them

### If no brief file is found → Proceed with normal Discovery Gate

No change to current behaviour. Continue to the Discovery Gate section below.

## Decision Moment Protocol

Before asking **any** interview question during this command, you MUST:

1. Run `spec-kitty agent decision open` to mint a decision_id:
   ```
   spec-kitty agent decision open \
     --mission <mission-slug> \
     --flow specify \
     --slot-key specify.<section>.<question-slug> \
     --input-key <snake_case_key> \
     --question "<question text>" \
     [--options '["option1","option2","Other"]']
   ```
   Capture the returned `decision_id` from the JSON output.

2. Ask the question to the user in chat.

3. After the user answers, run **exactly one** of:
   - Resolved answer:
     `spec-kitty agent decision resolve <decision_id> --mission <slug> --final-answer "<answer>" [--other-answer]`
   - Deferred / skip:
     `spec-kitty agent decision defer <decision_id> --mission <slug> --rationale "<reason>"`
   - Not applicable / cancel:
     `spec-kitty agent decision cancel <decision_id> --mission <slug> --rationale "<reason>"`

4. When deferring, write the inline marker into `spec.md` immediately after the
   relevant section:
   ```
   [NEEDS CLARIFICATION: <brief description of what needs answering>] <!-- decision_id: <decision_id> -->
   ```

5. Before declaring the interview phase complete, run:
   `spec-kitty agent decision verify --mission <slug>`
   Address any findings (`DEFERRED_WITHOUT_MARKER`, `MARKER_WITHOUT_DECISION`,
   `STALE_MARKER`) before proceeding.

**Important constraints:**
- `--slot-key` format: `specify.<section>.<question-slug>` (e.g.,
  `specify.auth.strategy`).
- `--input-key` is the snake_case programmatic key (e.g., `auth_strategy`).
- The `decision_id` on the wire is a plain ULID (26 chars). The `DM-` prefix
  appears only in artifact filenames, not in CLI arguments.
- Widening is represented by the CLI/SaaS widen flow; if that flow returns
  canonical thread metadata, it must be recorded as `DecisionPointWidened`.
- SaaS sync is not required; all operations are local-only.

## Discovery Gate (mandatory)

Only after `create` succeeds, begin brief intake or the Discovery Gate. Before
writing substantive `spec.md` content, committing it, or otherwise advancing
planning, you **must** conduct or verify a structured discovery interview.

- **Scope proportionality (CRITICAL)**: FIRST, gauge the inherent complexity of the request:
  - **Trivial/Test Features** (hello world, simple pages, proof-of-concept): Ask 1-2 questions maximum, then proceed. Examples: "a simple hello world page", "tic-tac-toe game", "basic contact form"
  - **Simple Features** (small UI additions, minor enhancements): Ask 2-3 questions covering purpose and basic constraints
  - **Complex Features** (new subsystems, integrations): Ask 3-5 questions covering goals, users, constraints, risks
  - **Platform/Critical Features** (authentication, payments, infrastructure): Full discovery with 5+ questions

- **Scenario-first discovery**: For any non-trivial feature, prefer concrete
  workflow questions over abstract opinion prompts. Ask for the primary actor,
  trigger, happy-path outcome, and the most common exception or branch.

- **Terminology discipline**: If the request introduces business or domain
  terms that may drift, ask which term is canonical and which synonyms should
  be avoided. When relevant, carry those choices into the optional Domain
  Language section of the spec instead of leaving them implicit.

- **Rule probing**: For workflows with approvals, validations, state changes,
  or compliance implications, ask what must always be true and which
  transitions or checks cannot be skipped.

- **User signals to reduce questioning**: If the user says "just testing", "quick prototype", "skip to next phase", "stop asking questions" - recognize this as a signal to minimize discovery and proceed with reasonable defaults.

- **First response rule**:
  - For TRIVIAL features (hello world, simple test): Ask ONE clarifying question, then if the answer confirms it's simple, proceed directly to spec generation
  - For other features: Ask a single focused discovery question anchored in the primary user scenario and end with `WAITING_FOR_DISCOVERY_INPUT`

- If the user provides no initial description (empty command), stay in **Interactive Interview Mode**: keep probing with one question at a time.

- **Conversational cadence**: After each user reply, decide if you have ENOUGH context for this feature's complexity level. For trivial features, 1-2 questions is sufficient. Only continue asking if truly necessary for the scope.

Discovery requirements (scale to feature complexity):

1. Maintain a **Discovery Questions** table internally covering questions appropriate to the feature's complexity (1-2 for trivial, up to 5+ for complex). Track columns `#`, `Question`, `Why it matters`, and `Current insight`. Do **not** render this table to the user.
2. For trivial features, reasonable defaults are acceptable. Only probe if truly ambiguous.
3. When you have sufficient context for the feature's scope, paraphrase into an **Intent Summary** and confirm. For trivial features, this can be very brief. For non-trivial features, include the primary actor, trigger/success outcome, key constraint, and any explicit assumptions or deferred decisions.
4. Before leaving the interview loop, do a short playback of the primary scenario, the main exception or edge case, and any rule that must always hold.
5. If user explicitly asks to skip questions or says "just testing", acknowledge and proceed with minimal discovery.

## Bulk-Edit Detection (mandatory check)

Before finalizing the Intent Summary, ask yourself one question:

> Does fulfilling this request require changing the **same existing string**
> (identifier, path, key, label, or term) in more than one file?

Typical shapes: "rename X to Y", "the Blue feature is now the Red feature",
"change the terminology from X to Y", "move package A to package B", "replace
ACME with GlobalCorp everywhere in docs and UI".

**If yes or uncertain**: load the `spec-kitty-bulk-edit-classification` skill
and follow it. You will set `change_mode: bulk_edit` in `meta.json` after
`mission create` and produce an `occurrence_map.yaml` during plan. The user
does not need to know these field names — the skill teaches you the workflow.

**If clearly no** (a new feature with new identifiers, a bug fix that doesn't
rename anything, a refactor inside one file): proceed normally.

When in doubt, treat as bulk edit. The false-positive cost is drafting one map
the user approves in a pass; the false-negative cost is the silent cross-file
breakage that DIRECTIVE_035 exists to prevent.

## Workflow (0.11.0+)

**Planning happens in the repository root checkout - NO worktree created!**

1. Creates `kitty-specs/<mission_slug>/spec.md` directly in project root (the optional `NNN-` prefix is display-only metadata assigned at merge time)
2. Commits creation metadata; `spec.md` remains untracked until it is substantive and explicitly committed
3. No worktree created during specify

**Worktrees created later**: After `/spec-kitty.tasks` finishes, run: `spec-kitty next --agent <agent> --mission <handle>`. The `--mission` handle can be the mission's `mission_id` (ULID), `mid8` (first 8 chars), or `mission_slug`; the resolver disambiguates by `mission_id` and returns a structured error on ambiguity (no silent fallback). Your agent will call `spec-kitty agent action implement WP## --agent <name>` for each WP. Each lane gets exactly one worktree, for example `.worktrees/<human-slug>-<mid8>-lane-a/` (e.g. `.worktrees/my-feature-01J6XW9K-lane-a/`).

## Location

- Work in: **Repository root checkout** (not a worktree)
- Creates: `kitty-specs/<mission_slug>/spec.md` (the `NNN-` prefix is display-only and assigned at merge time)
- Commits to: target branch (from `create --json` → `target_branch`)

## Outline

### 0. Establish a Provisional Mission Identity

- Before interview, derive a short provisional title and kebab-case slug from
  the initial request (avoid filler like "feature" or "thing"). This identity
  only establishes the Mission handle; do not treat it as confirmed intent.
- Resolve branch intent, then create the Mission scaffold using that provisional
  identity before asking any discovery or brief-intake question.
- Read the confirmed Intent Summary back to the user during discovery. It
  governs the substantive spec even though the Mission identity is immutable.
- Before creating, freeze the activated Mission type and the creation metadata
  snapshot as described above. Do not defer type selection until discovery.

The text the user typed after `/spec-kitty.specify` in the triggering message **is** the initial feature description. Capture it verbatim, but treat it only as a starting point for discovery—not the final truth. Your job is to interrogate the request, surface gaps, and co-create a complete specification with the user.

Given that feature description, do this:

- **Generation Mode (arguments provided)**: Use the provided text as a starting point, validate it through discovery, and fill gaps with explicit questions or clearly documented assumptions (limit `[NEEDS CLARIFICATION: …] <!-- decision_id: <id> -->` to at most three critical decisions the user has postponed; call `decision defer` before writing each such marker).
- **Interactive Interview Mode (no arguments)**: Ask the single bootstrap identity prompt, create the scaffold, then use the discovery interview to elicit all necessary context and confirm it before writing substantive `spec.md` content.

1. **Resume safely or create the Mission before interview**:
   - From the initial request, derive a provisional title, purpose summary, and
     kebab-case slug. Resolve branch intent as required above, then call the
     creation command now. This must happen before the first discovery or
     brief-intake question so each question can open a Decision Moment against
     the created Mission.
   - Before `create`, probe for an interrupted earlier attempt:

     ```bash
     spec-kitty agent mission check-prerequisites --mission <provisional-slug> \
       --resume-probe --json
     ```

     Route only on the structured `resume_state` field:
     - `found`: reuse only when `spec_committed_and_substantive` is false and
       the returned Mission type and frozen creation snapshot match this
       invocation. The returned `target_branch`, `topology`, and `pr_bound` must
       also match the confirmed branch contract for this run. Use the returned
       `mission_id` or exact `mission_slug` for every later command. If specify
       is already complete, branch intent changed, or metadata differs, stop and
       report the existing Mission.
     - `not_found`: this is the only state that authorizes a new `create`.
     - `existing`: stop and report the valid merged Mission. Preserve it; never
       repair, remove, or reuse it as an interrupted specify scaffold.
     - `ambiguous`: stop and ask the user to select one returned candidate.
     - `malformed`: stop and repair or explicitly remove the partial scaffold;
       do not create through it.

     Any result without `resume_state` is a probe/preflight failure, not proof
     of absence. Stop and repair it. Never infer `not_found` by parsing error
     prose or by observing unrelated Missions.
   - If this is your first message or discovery questions remain unanswered,
     stay in the one-question loop, capture the user's response, update your
     internal table, and end with `WAITING_FOR_DISCOVERY_INPUT`. Do **not**
     surface the table; keep it internal.
   - Only proceed once every discovery question has an explicit answer and the user has acknowledged the Intent Summary.
   - Empty invocation rule: use the response to the one bootstrap identity
     prompt as the provisional slug, then create before any discovery question.
     Stay in interview mode until you can restate the agreed-upon description.
     Do not write substantive spec content while the description is missing or
     provisional.

2. Run the creation command from repo root before the interview:

   ```bash
   spec-kitty agent mission create "<slug>" \
     --mission-type "<mission-type>" \
     --friendly-name "<title>" \
     --purpose-tldr "<purpose_tldr>" \
     --purpose-context "<purpose_context>" \
     --json
   ```

   Where `<slug>` is a kebab-case version of the provisional title (e.g.,
   "Checkout Upsell Flow" → "checkout-upsell-flow").

   If the user expects a pull request for this work, add `--pr-bound --branch-strategy already-confirmed`. When `current_is_primary` is true and they accept the recommended feature-branch path, also add `--start-branch <branch>` so no mission artifacts are written on the primary branch.

   If this mission must preserve its lane branches and/or worktrees after `spec-kitty merge` (e.g. for post-merge inspection or a PR review window), declare that up front with `--retain-branches` and/or `--retain-worktrees` — this mints a machine-readable retention policy into `meta.json` so merge honors it automatically, rather than relying on a prose note nothing reads.

   The command returns JSON with:
   - `result`: "success" or error message
   - `mission_id`: Canonical ULID machine identity (e.g., `01J6XW9KQT7M0YB3N4R5CQZ2EX`). Immutable.
   - `mission_slug`: Human-readable mission slug (e.g., `checkout-upsell-flow`)
   - `mission_number`: **Display-only** numeric prefix, `null` pre-merge. Assigned at merge time. **Never** use this as a selector or identity.
   - `mission_type`: Mission type key (for example `software-dev`)
   - `slug`: Unnumbered mission slug (e.g., `checkout-upsell-flow`)
   - `friendly_name`: provisional title
   - `purpose_tldr`: provisional one-line stakeholder-facing Mission summary
   - `purpose_context`: provisional stakeholder-facing context paragraph
   - `feature_dir`: Absolute path to the feature directory inside the repository root checkout
   - `current_branch`: the branch you started from
   - `target_branch` / `base_branch`: deterministic branch contract for downstream commands
   - `planning_base_branch` / `merge_target_branch`: explicit landing-branch aliases
   - `branch_strategy_summary`: human-readable summary of the branch contract

   Parse these values for use in subsequent steps. All file paths are absolute.

   **IMPORTANT**: Run this command at most once for a new Mission. The JSON is
   provided in terminal output; preserve it to get the actual paths. Retry
   `create` only after a confirmed non-zero failure, and repeat the resume probe
   before retrying because a failed caller may still have observed a completed
   write. Never retry after lost, truncated, or merely unparsed success output.
   Immediately restate the branch contract to the user after parsing the JSON:
   - Current branch at start
   - Intended planning/base branch
   - Final merge target for later changes
   - Whether that matches the user's intended landing branch

   If the frozen `<mission-type>` is not `software-dev`, query before handoff:

   ```bash
   spec-kitty next --agent <agent> --mission <handle> --json
   ```

   The read-only query is the replay guard:
   - If it returns `kind: "query"`, `mission_state: "not_started"`, and a
     type-specific `preview_step` (for example, `research` begins at
     `scoping`), issue that first action exactly once:

     ```bash
     spec-kitty next --agent <agent> --mission <handle> --result success --json
     ```

     Follow the returned action and `prompt_file`.
   - If it returns any other `mission_state`, `step_id`, `decision_id`, or
     non-null `run_id`, a type-specific run or action already exists. Never pass
     `--result success` merely to recover lost output: that would falsely mark
     the outstanding action complete. Stop this prompt and report the Mission
     handle plus returned runtime fields so the outstanding action can be
     resumed from its original host context or recovered explicitly.

   Then stop executing this prompt. Do not open software-dev specify Decision
   Moments, write FR/NFR/C rows, create the software-dev requirements checklist,
   run `spec-kitty spec-commit`, or run `spec-kitty agent mission setup-plan`
   for that Mission.
3. **Stay in the repository root checkout**: No worktree is created during specify.

4. Read the files created by `create`:
   - `<feature_dir>/spec.md` (already created, may be empty/template-filled)
   - `<feature_dir>/meta.json` (already created with feature identity metadata)

   **Do NOT try to read a template file.** The spec structure is defined in this prompt (see sections below). The `create` command scaffolds an initial `spec.md` — read it, then update it following the structure in this prompt.

5. Update `<feature_dir>/meta.json` only when needed:
   - **Never** modify identity fields from `create` (`mission_id`, `slug`, `mission_slug`, `created_at`, `target_branch`). `mission_id` is the canonical ULID and is immutable. `mission_number` is display-only and is `null` pre-merge — do not set it by hand.
   - Keep `target_branch` aligned to the value from `create --json` output. Never hardcode `main`.
   - Preserve `friendly_name`, `purpose_tldr`, `purpose_context`, and
     `mission_type` exactly as emitted by `create`; confirmed intent belongs in
     `spec.md`, not an unrecorded rewrite of lifecycle metadata.
   - Optionally add/update `source_description`.
   - Ensure `vcs` exists (`"git"` default).

   Example `meta.json` schema (identity fields that must be present explicitly):
   ```json
   {
     "mission_id": "01J6XW9KQT7M0YB3N4R5CQZ2EX",
     "mission_number": null,
     "slug": "my-feature",
     "mission_slug": "my-feature",
     "friendly_name": "My Mission",
     "purpose_tldr": "Keep the mission understandable to product and executive stakeholders.",
     "purpose_context": "This mission exists to make the purpose of the work immediately legible to stakeholders who should not need to parse technical specification text to understand the value or expected outcome.",
     "mission_type": "software-dev",
     "target_branch": "<target-branch>",
     "vcs": "git",
     "created_at": "2026-01-01T00:00:00+00:00"
   }
   ```

   `mission_number` becomes a concrete integer only at merge time, assigned as
   `max(existing_numbers)+1` inside the merge-state lock. Selectors disambiguate
   by `mission_id` (or its 8-char prefix `mid8`), never by `mission_number`.

   **Do not regenerate timestamps or directory paths via shell commands.**

6. Generate the specification content by following this flow:
    - Use the discovery answers as your authoritative source of truth (do **not** rely on the raw invocation text)
    - For empty invocations, treat the synthesized interview summary as the canonical feature description
    - Identify: actors, actions, data, constraints, motivations, success metrics
    - Prefer concrete scenario walkthrough facts (actor, trigger, success outcome, exception path) over abstract restatements
    - For any remaining ambiguity:
      - Ask the user a focused follow-up question immediately and halt work until they answer
      - Only use `[NEEDS CLARIFICATION: …]` when the user explicitly defers the decision
      - Record any interim assumption in the Assumptions section
      - Prioritize clarifications by impact: scope > outcomes > risks/security > user experience > technical details
    - Fill User Scenarios & Testing section (ERROR if no clear user flow can be determined)
    - If terminology precision matters, fill the optional Domain Language section with canonical terms and ambiguous synonyms to avoid
    - Generate separated requirement tables: Functional (`FR-###`), Non-Functional (`NFR-###`), and Constraints (`C-###`)
    - Label every Functional Requirement row with a trailing `Delivery` value and a trailing `No-op passable?` mark (summary of tactic `acceptance-criteria-non-vacuity`: `[build]` new behaviour / `[ratchet]` pins existing behaviour / `[folded]` satisfied by another row; `yes`/`no` — `yes` means a do-nothing change would pass the row's check, so reword it or name a same-fixture positive control). Place both as trailing columns only — never inside or before the ID cell, never inline on an FR bullet/heading. Full label definitions and the non-vacuity rules live in tactic `acceptance-criteria-non-vacuity` (fetch: `spec-kitty charter context --include tactic:acceptance-criteria-non-vacuity`) — do not redefine them here.
    - Ensure each requirement entry has a status value and testable wording
    - Capture rules or invariants that shape acceptance scenarios, edge cases, permissions, or lifecycle boundaries
    - Define Success Criteria (measurable, technology-agnostic outcomes)
    - Identify Key Entities (if data involved)

7. Update the existing `<feature_dir>/spec.md` using the template structure, replacing placeholders with concrete details derived from the feature description while preserving section order and headings.

8. **Specification Quality Validation**: After writing the initial spec, validate it against quality criteria:

   a. **Create Spec Quality Checklist**: Generate a checklist file at `feature_dir/checklists/requirements.md` using the checklist template structure with these validation items:

      ```markdown
      # Specification Quality Checklist: [FEATURE NAME]

      **Purpose**: Validate specification completeness and quality before proceeding to planning
      **Created**: [DATE]
      **Feature**: [Link to spec.md]

      ## Content Quality

      - [ ] No implementation details (languages, frameworks, APIs)
      - [ ] Focused on user value and business needs
      - [ ] Written for non-technical stakeholders
      - [ ] All mandatory sections completed

      ## Requirement Completeness

      - [ ] No [NEEDS CLARIFICATION] markers remain
      - [ ] Requirements are testable and unambiguous
      - [ ] Requirement types are separated (Functional / Non-Functional / Constraints)
      - [ ] IDs are unique across FR-###, NFR-###, and C-### entries
      - [ ] All requirement rows include a non-empty Status value
      - [ ] Non-functional requirements include measurable thresholds
      - [ ] Every FR row and success criterion carries a delivery label and no-op mark
      - [ ] Success criteria are measurable
      - [ ] Success criteria are technology-agnostic (no implementation details)
      - [ ] All acceptance scenarios are defined
      - [ ] Edge cases are identified
      - [ ] Scope is clearly bounded
      - [ ] Dependencies and assumptions identified

      ## Feature Readiness

      - [ ] All functional requirements have clear acceptance criteria
      - [ ] User scenarios cover primary flows
      - [ ] Feature meets measurable outcomes defined in Success Criteria
      - [ ] No implementation details leak into specification

      ## Notes

      - Items marked incomplete require spec updates before `/spec-kitty.plan`
      ```

   b. **Run Validation Check**: Review the spec against each checklist item:
      - For each item, determine if it passes or fails
      - Document specific issues found (quote relevant spec sections)

   c. **Handle Validation Results**:

      - **If all items pass**: Mark checklist complete and proceed to step 6

      - **If items fail (excluding [NEEDS CLARIFICATION])**:
        1. List the failing items and specific issues
        2. Update the spec to address each issue
        3. Re-run validation until all items pass (max 3 iterations)
        4. If still failing after 3 iterations, document remaining issues in checklist notes and warn user

      - **If [NEEDS CLARIFICATION] markers remain**:
        1. Extract all [NEEDS CLARIFICATION: ...] markers from the spec
        2. Re-confirm with the user whether each outstanding decision truly needs to stay unresolved. Do not assume away critical gaps.
        3. For each clarification the user has explicitly deferred, present options using plain text—no tables:

           ```
           Question [N]: [Topic]
           Context: [Quote relevant spec section]
           Need: [Specific question from NEEDS CLARIFICATION marker]
           Options: (A) [First answer — implications] · (B) [Second answer — implications] · (C) [Third answer — implications] · (D) Custom (describe your own answer)
           Reply with a letter or a custom answer.
           ```

        4. Number questions sequentially (Q1, Q2, Q3 - max 3 total)
        5. Present all questions together before waiting for responses
        6. Wait for user to respond with their choices for all questions (e.g., "Q1: A, Q2: Custom - [details], Q3: B")
        7. Update the spec by replacing each [NEEDS CLARIFICATION] marker with the user's selected or provided answer
        9. Re-run validation after all clarifications are resolved

   d. **Update Checklist**: After each validation iteration, update the checklist file with current pass/fail status

9. Report completion with feature directory, spec file path, checklist results, and readiness for the next phase (`/spec-kitty.plan`).

**NOTE:** The script creates and checks out the new branch and initializes the spec file before writing.

## General Guidelines

## Quick Guidelines

- Focus on **WHAT** users need and **WHY**.
- Avoid HOW to implement (no tech stack, APIs, code structure).
- Written for business stakeholders, not developers.
- DO NOT create any checklists that are embedded in the spec. That will be a separate command.

### Section Requirements

- **Mandatory sections**: Must be completed for every feature
- **Optional sections**: Include only when relevant to the feature
- When a section doesn't apply, remove it entirely (don't leave as "N/A")

### For AI Generation

When creating this spec from a user prompt:

1. **Make informed guesses**: Use context, industry standards, and common patterns to fill gaps
2. **Document assumptions**: Record reasonable defaults in the Assumptions section
3. **Limit clarifications**: Maximum 3 [NEEDS CLARIFICATION] markers - use only for critical decisions that:
   - Significantly impact feature scope or user experience
   - Have multiple reasonable interpretations with different implications
   - Lack any reasonable default
4. **Prioritize clarifications**: scope > security/privacy > user experience > technical details
5. **Think like a tester**: Every vague requirement should fail the "testable and unambiguous" checklist item
6. **Common areas needing clarification** (only if no reasonable default exists):
   - Feature scope and boundaries (include/exclude specific use cases)
   - User types and permissions (if multiple conflicting interpretations possible)
   - Security/compliance requirements (when legally/financially significant)

**Examples of reasonable defaults** (don't ask about these):

- Data retention: Industry-standard practices for the domain
- Performance targets: Standard web/mobile app expectations unless specified
- Error handling: User-friendly messages with appropriate fallbacks
- Authentication method: Standard session-based or OAuth2 for web apps
- Integration patterns: RESTful APIs unless specified otherwise

### Success Criteria Guidelines

Success criteria must be:

1. **Measurable**: Include specific metrics (time, percentage, count, rate)
2. **Technology-agnostic**: No mention of frameworks, languages, databases, or tools
3. **User-focused**: Describe outcomes from user/business perspective, not system internals
4. **Verifiable**: Can be tested/validated without knowing implementation details
5. **Labelled**: Append a trailing delivery-label + no-op suffix to every criterion — `— [build/ratchet/folded] · no-op passable: [yes/no]` — the same label set and no-op mark used on the Functional Requirements table (defined once, in tactic `acceptance-criteria-non-vacuity`; see the Requirements section guidance above).

**Good examples**:

- "Users can complete checkout in under 3 minutes"
- "System supports 10,000 concurrent users"
- "95% of searches return results in under 1 second"
- "Task completion rate improves by 40%"

**Bad examples** (implementation-focused):

- "API response time is under 200ms" (too technical, use "Users see results instantly")
- "Database can handle 1000 TPS" (implementation detail, use user-facing metric)
- "React components render efficiently" (framework-specific)
- "Redis cache hit rate above 80%" (technology-specific)
