---
description: Interview and compile a project charter
---
# /spec-kitty.charter - Interview + Compile Charter

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Repo Scope

`/spec-kitty.charter` is a repo-scoped governance flow, not a per-mission flow.

- Run it from the repository root.
- Do **not** try to resolve a mission handle for this command.
- For charter subcommands, `--mission-type` means the reusable mission blueprint
  (for example `software-dev` or `documentation`), not a mission instance in
  `kitty-specs/`.
- The hidden `--mission` flag on `spec-kitty charter ...` is only a deprecated
  alias for `--mission-type`.

If you need deterministic context before interviewing:

1. Confirm you are in the repo root.
2. Check whether a charter already exists:

```bash
spec-kitty charter status --json
```

3. If needed, inspect available mission blueprints:

```bash
spec-kitty mission list
```

For this command, the default mission type is `software-dev` unless the user
explicitly wants a different mission blueprint.

## Skill Load

Before proceeding, load the `spk-charter-governance` skill for the charter
lifecycle model, doctrine access patterns, and action-context rules.

If the skill conflicts with this command contract, follow this command contract.

## Command Contract

This command owns charter discovery in chat. Do not default to
`spec-kitty charter interview --defaults` unless the user explicitly asks for a
fast bootstrap with canned defaults.

Listen intently to what the human-in-command says next. If any form of charter
already exists, assume the user is probably flagging a charter addition, course
correction, or new guidance they noticed while observing Spec Kitty or agent
behavior. Do not restart a full interview unless the user asks for one or the
existing charter is clearly unusable. The default goal is to update the charter
with the new guidance.

The CLI charter workflow is a compiler and persistence surface, not the primary
interview experience. Your job is to:

1. Inspect the repo quickly to form an initial governance hypothesis.
2. Discover the intended charter change in chat. For an existing charter, ask
   focused follow-up questions about the new guidance; for a missing charter,
   run a short targeted interview.
3. Synthesize the answers into `.kittify/charter/interview/answers.yaml`.
4. Run `spec-kitty charter generate --from-interview --json`.
5. Verify generation with `spec-kitty charter status --json`.

Do not preload governance context for all workflow actions as part of charter
generation. Action context is loaded iteratively at the actual action boundary.

## Doctrine Gaps

If no built-in paradigm or directive cleanly fits the user's needs:

- Do **not** force a near-match just to populate selections.
- Keep `selected_paradigms` and `selected_directives` narrow and truthful.
- Encode the missing policy as project-specific charter policy in the interview
  answers and generated charter.
- Say clearly that this is a doctrine gap, not an existing doctrine match.
- Treat it as a candidate for later doctrine extraction rather than solving it by
  misclassifying the project now.

### Output location

- Structured charter (authoritative): `.kittify/charter/charter.yaml` —
  `governance`/`directives`/activation/`overrides` sections. Edit these
  directly for policy changes; `charter generate` only refreshes the
  `catalog`/`metadata` sections.
- Curated companion (write this yourself when authoring/updating the
  charter): `.kittify/charter/charter.md` — a human-readable narrative.
  `charter generate` never writes this file; the runtime never reads it for
  policy.
- Interview answers: `.kittify/charter/interview/answers.yaml`

## Execution Paths

### Path A: LLM-led interview (default)

Use this for normal `/spec-kitty.charter` runs.

1. Inspect the repo quickly before asking questions. Prefer high-signal files:
   - `README.md`
   - `AGENTS.md`
   - `CLAUDE.md`
   - `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`
   - existing `.kittify/charter/*` artifacts if present
   - If `.claudeignore` exists, respect it during repo inspection and do not
     spend time reading ignored paths unless the user explicitly asks.
   - If `.claudeignore` does not exist, treat the following as low-signal Spec
     Kitty bootstrap artifacts by default and do not over-interpret them as
     project intent:
     - `.kittify/config.yaml`
     - `.kittify/metadata.yaml`
     - `.kittify/skills-manifest.json`
     - `.kittify/missions/`
     - `.kittify/templates/`
     - `.kittify/scripts/`
     - agent wrapper directories such as `.claude/`, `.codex/`, `.gemini/`,
       `.cursor/`, `.opencode/`
   - If the repo is otherwise sparse, say so plainly. A freshly initialized
     Spec Kitty workspace with mostly `.kittify/` metadata is a greenfield
     bootstrap case, not a signal-rich codebase.
   - In that greenfield case, stop spending time inspecting Spec Kitty init
     relics and start the interview. The user's answers are the primary source
     of governance intent.
   - If charter status or repo inspection reports "not inside a git repository"
     but the directory is clearly a new project bootstrap, treat that as a
     greenfield setup condition rather than a reason to delay the interview.
2. Discover the intended charter update in chat:
   - If a charter exists and the user gives a correction, complaint, observed
     agent failure, desired norm, or new policy, treat that as the primary
     source. Ask only the minimum follow-up needed to make the guidance precise
     enough to encode.
   - Preserve existing charter guidance unless the user clearly wants to replace
     or narrow it.
   - If the user's input names agent behavior that should change, translate it
     into enforceable review, planning, implementation, terminology, risk, or
     exception-policy guidance.
   - If the user input is a small course correction, avoid a broad charter
     interview. Update the relevant `answers.yaml` fields and regenerate.
   - If the charter is missing or the user asks to start fresh, ask a short
     targeted interview in chat.
   - If the user already gave strong context, ask 1-3 clarifying questions.
   - If the invocation is empty, start the interview and wait after one focused question.
   - Ask natural-language questions. Do **not** ask the user to answer in YAML,
     bullet-schema, numbered templates, or "Purpose / Work / Must enforce"
     formatting.
   - The LLM is responsible for structuring and normalizing the user's answers
     into the interview schema later. The user should only have to answer the
     substance of the question.
   - If the project uses dense business or domain language, ask one lightweight
     terminology question: which terms must stay precise across docs, specs,
     and code, and which overloaded terms or synonyms should be avoided. Fold
     that signal into existing documentation/review/risk answers rather than
     inventing new interview schema fields.
   - If failure modes differ materially, ask which kind of failure would be
     most costly (for example wrong behavior, privacy breach, downtime, data
     loss) and use that answer to sharpen risk boundaries and review policy.
   - If examples are needed, keep them conceptual and brief; do not imply that
     the user must mirror the example format.
   - Match interview depth to project complexity and the user's stated
     preference for speed vs rigor.
   - If the user wants "lightweight", "fast", "minimal", or clearly low-overhead
     governance, keep the interview to 2-3 questions maximum unless the user
     asks for more.
   - If the repo and user context indicate a large, long-lived, high-risk, or
     highly regulated codebase, increase interview depth accordingly and cover
     governance areas that would materially affect long-term operation.
   - For long interviews, check in periodically. If the user seems tired,
     impatient, or overloaded, ask whether they want to continue in depth,
     switch to a lighter pass, or stop and generate a first draft now.
   - Prefer progressive disclosure: start with the minimum set of questions
     needed to produce a truthful charter, then deepen only when the project
     complexity or the user's answers justify it.
3. Synthesize the interview into `.kittify/charter/interview/answers.yaml` using the
   schema expected by `spec-kitty charter generate`.
4. Run:

```bash
spec-kitty charter generate --from-interview --json
spec-kitty charter status --json
```
5. Update `.kittify/charter/charter.md` yourself (this command owns it — it is a
   curated companion `generate` never writes). Keep it in sync with the same
   policy you just wrote into `charter.yaml`'s `governance`/`directives`
   sections, in narrative form. Treat both `charter.yaml` (refreshed by
   `generate`) and `charter.md` (hand-updated by you) as a real repository
   change — stage and commit them before concluding the command unless the
   user explicitly asked not to commit.

### Commit expectation

- Do **not** stop at "there is an uncommitted charter change."
- After successful generation, the default behavior is to create the commit via
  Spec Kitty's safe-commit path.
- Use a concise commit message that makes the governance action explicit:

```bash
spec-kitty safe-commit --message "chore: generate project charter" \
  .kittify/charter/interview/answers.yaml \
  .kittify/charter/charter.yaml \
  .kittify/charter/charter.md \
  .gitignore
```

- If generation produced no diff, say so and do not create an empty commit.
- If unrelated dirty changes exist, avoid sweeping them into the charter commit;
  `spec-kitty safe-commit` commits only the requested files.

### Path B: CLI interview fallback

Use this only when the user explicitly wants the CLI questionnaire itself:

```bash
spec-kitty charter interview --profile comprehensive
spec-kitty charter generate --from-interview
```

### Path C: Deterministic defaults bootstrap

Use this only when the user explicitly asks for defaults, speed, CI bootstrap, or
“just make me a starter charter”:

```bash
spec-kitty charter interview --defaults --profile minimal --json
spec-kitty charter generate --from-interview --json
spec-kitty charter status --json
```

When you use defaults, say clearly that no real interview happened.

## Editing Rules

- The preferred editable source for this command is `.kittify/charter/interview/answers.yaml`.
- To revise policy inputs, edit `answers.yaml` (or rerun `charter interview`) and regenerate —
  or edit `charter.yaml`'s `governance`/`directives` sections directly for a targeted change.
- `--force` with generate no longer gates a destructive overwrite (there is none left to gate);
  it is accepted for CLI back-compat only.
- Keep `charter.md` concise; full detail belongs in `charter.yaml`'s `catalog` reference list and
  the doctrine artifacts it points at.

## Validation + Status

After generation, verify status:

```bash
spec-kitty charter status --json
```

Do not chain `status` with four `context` calls and dump all of it back into the
LLM. That burns first-load state and floods the context window with bootstrap
payloads intended for later action boundaries.

## Charter Context Bootstrap

Do not preload all action contexts here.

The next real workflow action will load its own context automatically.

If you need to inspect one action manually for debugging, query a single action
without consuming first-load state:

```bash
spec-kitty charter context --action specify --json --no-mark-loaded
```

Use JSON `text` as governance context only for the immediate next action. Do not
eagerly inject `specify`, `plan`, `implement`, and `review` all at once.

## Interview Output Shape

When you synthesize `.kittify/charter/interview/answers.yaml`, match the CLI schema:

```yaml
schema_version: 1.0.0
mission: software-dev
profile: comprehensive
answers:
  project_intent: "..."
  languages_frameworks: "..."
  testing_requirements: "..."
  quality_gates: "..."
  review_policy: "..."
  performance_targets: "..."
  deployment_constraints: "..."
  documentation_policy: "..."
  risk_boundaries: "..."
  amendment_process: "..."
  exception_policy: "..."
selected_paradigms:
  - domain-driven-design
selected_directives:
  - DIRECTIVE_001
available_tools:
  - git
```

Select paradigms, directives, and tools deliberately from repo evidence plus user
answers. Do not silently accept the full catalog unless the user explicitly asks
for defaults.
