# Charter Governance Workflow (spk-charter-governance reference)

Manage the charter lifecycle: interview, generate, context-load, sync,
and status. Access doctrine artifacts programmatically via `DoctrineService`.
Resolve agent profiles for role-scoped behavior. Load governance context
iteratively at action boundaries rather than dumping everything upfront.

`.kittify/charter/charter.yaml` is the Spec Kitty runtime governance
source for a project — the single git-tracked, structured file nesting
`governance`, `directives`, `catalog`, activation, and `overrides`.
`.kittify/charter/charter.md` is a curated, human-readable companion the
runtime never parses or resolves policy from. A repository may also keep
public governance docs outside `.kittify/`; those docs are human-facing
authority unless `charter.yaml`'s `governance.charter.governance_references`
points at them. The charter offering (`src/charter/offering/`) provides the
reusable knowledge artifacts (directives, tactics, paradigms, styleguides,
toolguides, procedures, agent profiles, step contracts) that the charter
references.

---

## ⛔ ARCHITECTURAL INVARIANT: spec-kitty NEVER calls LLMs

**spec-kitty is a CLI tool invoked BY an LLM harness (Claude Code, Codex, Cursor,
Gemini, etc.). The LLM harness IS the inference engine. spec-kitty must NEVER
call any LLM API itself.**

This is not a preference. It is a hard architectural rule with no exceptions.

### Why this rule exists

| What you are reading this in | What that means |
|------------------------------|-----------------|
| Claude Code | Claude IS already running. It should generate doctrine. |
| Codex CLI | Codex IS already running. It should generate doctrine. |
| Cursor / Gemini / Kiro / ... | Same — the harness IS the inference engine. |

If spec-kitty called the Anthropic SDK internally:
- It would need a separate `ANTHROPIC_API_KEY` — a second API key alongside the one
  the harness already uses.
- It would bypass the harness entirely, making the agent's reasoning invisible.
- It would make spec-kitty Anthropic-specific, breaking all other harnesses.
- It would be a hidden inference call the user never authorized or configured.
- It would duplicate what the harness can already do better, with full context.

### What this means for charter synthesis

**Charter synthesis is an LLM reasoning task. YOU (the agent running this skill)
are the LLM that should do it.**

The synthesis workflow is:

```
answers.yaml   (the interview answers — what the user told spec-kitty about the project)
     +
doctrine schemas  (the YAML shapes expected for directives, tactics, styleguides)
     +
THIS SKILL  (the instructions you are reading right now)
     ↓
YOU generate the doctrine YAML files
     ↓
spec-kitty CLI commands  (validate, stage, and promote the files you wrote)
```

spec-kitty's CLI provides validation, schema-checking, DRG validation, neutrality
gating, staging, and atomic promotion. It does NOT provide generation — that is
your job as the agent.

### If you see code that calls `anthropic.Anthropic()` or imports the `anthropic` SDK
inside spec-kitty source files, that is a bug. Remove it immediately.

Canonical locations that must NEVER contain `import anthropic` or any Anthropic SDK call:
- `src/charter/` — any file
- `src/specify_cli/` — any file
- `pyproject.toml` — must not list `anthropic` as a runtime dependency

---

## How to Synthesize Doctrine Artifacts (Agent-Driven)

When a user says "synthesize charter doctrine", "generate project doctrine", or
"run charter synthesize", you do the following — you do NOT call any CLI command
that triggers an LLM. You ARE the LLM.

### Step 1 — Read the interview answers

```bash
cat .kittify/charter/interview/answers.yaml
```

This file contains the user's responses: project intent, languages, testing
requirements, quality gates, etc.

### Step 2 — Read the doctrine schemas for the target artifact kinds

The current synthesis scope is: `directive`, `tactic`, `styleguide`.

Read shipped examples to understand the expected YAML shape.
There is no `doctrine list` or `doctrine show` CLI command — use the programmatic
`DoctrineService` API (documented in the *Programmatic Doctrine Access* section below)
or read the YAML files directly from `packs/built-in/<kind>/` (artifacts live at
`<type>/<pack>/[<category>/]<name>` — ADR 2026-07-26-2):

```python
from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

service = build_activation_aware_doctrine_service(project_root)

# Read a directive
directive = service.directives.get("<a-directive-id>")

# Read a tactic
tactic = service.tactics.get("<a-tactic-id>")

# Read a styleguide
styleguide = service.styleguides.get("<a-styleguide-id>")
```

To validate your project-layer doctrine artifacts run:
```bash
spec-kitty charter validate .kittify/charter-packs
```

### Step 3 — Read the interview mapping to know what to generate

The interview fields map to target artifact kinds:
- `project_intent`, `quality_gates`, `risk_boundaries` → directives
- `testing_requirements` → directives + tactics (TDD flavour)
- `languages_frameworks` → styleguides (language-specific)
- `performance_targets`, `deployment_constraints` → directives

For each synthesis target, derive: `kind`, `slug` (kebab-case, project-specific),
`title`, and `body` (the full artifact content as YAML matching the shipped schema).

### Step 4 — Author the project doctrine

All five supported project kinds are `directive`, `tactic`, `styleguide`,
`procedure`, and `agent_profile`. For direct authoring, run `charter new <kind>
<id>`, complete the scaffold, and run `charter validate .kittify/charter-packs`.
`charter activate agent-profile <id> --cascade all` registers authored project
artifacts in the DRG and provenance manifest and activates referenced guidance.
Project procedures live in `.kittify/charter-packs/procedure/`; profiles live in
`.kittify/charter-packs/agent_profiles/`. These source files remain user-owned.

For interview-generated directives, tactics and styleguides, use the generated
input path below. Procedures and profiles use the direct-authoring path above.

The harness writes artifact inputs here; `spec-kitty charter synthesize`
validates, stages, and promotes them into the live doctrine tree.

```
.kittify/charter/generated/
  directives/
    <NNN>-<slug>.directive.yaml
  tactics/
    <slug>.tactic.yaml
  styleguides/
    <slug>.styleguide.yaml
```

Use the shipped artifact YAML structure as your template. Make the content
**specific to the project** based on the interview answers. Do not write
generic filler.

### Step 5 — Run the full validation stack without promoting

```bash
spec-kitty charter synthesize --dry-run
```

This is a real stage-and-validate pass. It writes the agent-authored artifacts
into the staging tree, runs schema validation, project DRG validation, and the
neutrality gate, then wipes the staging directory on success.

### Step 6 — Promote the validated artifact set

```bash
spec-kitty charter synthesize
```

By default this reads from `.kittify/charter/generated/` via the generated
adapter and promotes the validated outputs into:
- `.kittify/charter-packs/` for artifact content and project `graph.yaml`
- `.kittify/charter/provenance/` plus `synthesis-manifest.yaml` for bookkeeping

### Step 7 — Commit the promoted charter synthesis state

```bash
git add .kittify/charter-packs/ .kittify/charter/provenance/ .kittify/charter/synthesis-manifest.yaml
git commit -m "feat(charter): promote project-local doctrine from generated inputs"
```

---

---

## How the Charter System Works

The charter is a **governance-as-code** framework. A single git-tracked,
structured YAML file — `charter.yaml` — holds the project policy directly;
the runtime reads it without any parse/extract step in between.

### The 2-Layer Model

1. **Structured charter** (`.kittify/charter/charter.yaml`) — The single
   authoritative source. Nests four kinds of section:
   - `governance` / `directives` — **hand-authored** policy (testing,
     quality, performance, branching, doctrine selections; numbered project
     rules with severity and scope). Edit these directly; nothing overwrites
     them except a deliberate hand edit.
   - Flat-root activation keys (`activated_kinds`, `activated_directives`,
     `mission_type_activations`, …) — **hand-authored**, mirrors
     the activation presets (`packs/built-in/presets/default.yaml`, applied
     with `spec-kitty charter activate --preset <name>`).
   - `catalog` / `metadata` — **generator-refreshed**. `charter generate`
     rewrites these two sections deterministically on every run (doctrine
     reference manifest, generation timestamp); everything else in the file
     is preserved byte-for-byte through a round-trip merge.
   - `overrides` — hand-authored, forward-compatible project doctrine
     overrides.

2. **Curated companion** (`.kittify/charter/charter.md`) — Human-editable
   markdown. Written by hand, or by an agent during `/spec-kitty.charter`'s
   chat flow — never by `charter generate`. The runtime never
   parses it for policy — it exists purely for human review/onboarding, and
   optionally to summarize `charter.yaml` or point at a public constitution.
   If the repository also has a public constitution or handbook, reference
   it from `charter.yaml`'s `governance.charter.governance_references` (or
   `authority_paths`), not just from the companion prose.

`.kittify/config.yaml` carries a single `charter:` pointer (default
`.kittify/charter/charter.yaml`) that resolves the active charter file —
useful for redirecting to a shared or cross-project charter.

### Data Flow

```
Interview Answers (answers.yaml)
        |
        v
  [generate command]  <-- doctrine templates, mission config
        |
        v
charter.yaml
  governance:    <-- hand-authored, preserved byte-for-byte by generate
  directives:    <-- hand-authored, preserved byte-for-byte by generate
  activated_*:   <-- hand-authored, preserved byte-for-byte by generate
  catalog:       <-- REFRESHED every run (doctrine reference manifest)
  metadata:      <-- REFRESHED every run (generation timestamp)
        |
        v
  [context command]  at each workflow action
        |
        v
    Text injected into agent prompt
```

`charter.md` sits beside this flow as a hand-authored (or agent-authored,
e.g. via `/spec-kitty.charter`'s chat flow) companion — `generate` never
writes it, and it is never read back in.

### How Charter.yaml Sections Are Populated

`governance` and `directives` deserialize straight into the existing
`GovernanceConfig` / `DirectivesConfig` models — the same shapes the old
`governance.yaml` / `directives.yaml` used, now nested inside `charter.yaml`
instead of living in separate files:

```yaml
governance:
  testing:
    min_coverage: 90              # Minimum test coverage %
    tdd_required: false           # TDD mandatory
    framework: <project-runner>   # Test framework / runner
    type_checking: "<project-type-checker>" # Type checker
  quality:
    linting: "<project-linter>"   # Linter
    pr_approvals: 1               # Required approvals before merge
    pre_commit_hooks: false       # Pre-commit hooks required
  commits:
    convention: conventional      # Commit convention (or null)
  performance:
    cli_timeout_seconds: 2.0      # Max CLI command duration
    dashboard_max_wps: 100        # Max work packages dashboard displays
  branch_strategy:
    main_branch: main             # Primary branch
    dev_branch: null              # Development branch (optional)
    rules: []                     # Branch naming/protection rules
  charter:
    selected_paradigms: []        # Active paradigm IDs
    selected_directives: []       # Active directive IDs
    available_tools: []           # Active tool IDs
    template_set: null            # Mission template set
    authority_paths: []           # Directories surfaced as required reading
    governance_references: []     # Supporting external governance documents
  enforcement: {}                 # Enforcement policy by domain
directives:
  - id: DIR-001                 # Auto-generated or custom ID
    title: "Short title"        # First 50 chars
    description: "Full text"    # Full description
    severity: warn              # error (blocks), warn (displayed), info (logged)
    applies_to: [implement, review]  # Actions where directive fires
```

There is no keyword-classified prose parser any more — the old "sync"
extraction that scanned `charter.md` headings and regex-matched values like
`90%+ coverage` is retired. Populate these sections directly (by hand, or
through the interview → `charter generate` bootstrap path) instead of
writing prose you expect a parser to interpret.

### Content-Hash Freshness (not hash-based staleness)

`charter.yaml` is the sole content-hash input (`content_hash_files`) for the
bundle's freshness signal — a SHA-256 over the file itself. There is no
`charter.md`-hash staleness check any more: `metadata` intentionally carries
no self-referential `charter_hash` field (a hash of `charter.yaml` cannot
live *inside* `charter.yaml`). `charter sync` is retained only for
canonical-root resolution and back-compat call sites — it performs no
extraction and always reports `synced=False`.

### How Context Gets Injected Into Workflow Actions

When you run `/spec-kitty.specify`, `/spec-kitty.plan`, `/spec-kitty.implement`,
or `/spec-kitty.review`, the runtime automatically calls
`spec-kitty charter context --action <action>`. The returned text is
injected into the agent prompt.

**Three context modes:**

| Mode | When | Content |
|---|---|---|
| `bootstrap` | First load for an action | Full policy summary (up to 8 bullets) + reference doc list (up to 10) |
| `compact` | Subsequent loads | Resolved paradigms, directives, tools, template_set only |
| `missing` | No charter exists | Instructions to create one |

First-load state is tracked in `.kittify/charter/context-state.json`.
Each action (specify, plan, implement, review) has an independent first-load
timestamp.

### Doctrine Artifact Kinds

Doctrine organizes knowledge into 8 artifact kinds. Each kind has a
dedicated repository in `DoctrineService`, follows built-in -> org -> project
loading, and is accessible programmatically or via CLI.

**Directives** — Numbered project rules that constrain agent behavior.
Each directive has a severity (`error`, `warn`, `info`), an `applies_to`
scope listing which actions it fires on, and may reference tactics.
Directives are the *what you must do* layer.

```python
directive = service.directives.get("DIRECTIVE_034")
# directive.title → "Test-First Development"
# directive.severity → "warn"
# directive.applies_to → ["implement", "review"]
# service.directives is a filtered dict (no .list_all()); to enumerate every
# directive regardless of activation, use the raw-repository escape hatch:
# service.raw_repository("directives").list_all()
# ...or read packs/built-in/directives/ directly.
```

**Tactics** — Reusable implementation approaches that describe *how* to do
something. Tactics cover testing (TDD, ZOMBIES, acceptance-test-first),
domain modeling (bounded context, aggregate boundaries), refactoring
(strangler fig, extract class), review (intent-and-risk-first), and
planning (problem decomposition, eisenhower). The shipped set includes a
refactoring sub-catalog.

```python
tactic = service.tactics.get("tdd-red-green-refactor")
# tactic.title, tactic.description, tactic.steps
```

**Paradigms** — High-level development philosophies that group related
tactics and directives. A paradigm (e.g., `domain-driven-design`) declares
which tactics it recommends. Paradigms are selected during the charter
interview and scope which tactics appear in governance context.

```python
paradigm = service.paradigms.get("domain-driven-design")
# paradigm.tactics → ["bounded-context-identification", ...]
```

**Styleguides** — Language- or domain-specific writing and coding style
rules. Applied when the charter's `languages_frameworks` answer
matches the styleguide's target language.

```python
styleguide = service.styleguides.get("python-conventions")
```

**Toolguides** — Operational guidance for specific tools. Teaches agents
how to use git, the project's test runner, diagramming tools, etc. within the project's
governance constraints.

```python
toolguide = service.toolguides.get("efficient-local-tooling")
```

**Procedures** — Multi-step workflow primitives with prerequisites and
ordered steps. Procedures are the reusable building blocks that step
contracts delegate to. They describe a complete mini-workflow (e.g.,
"refactoring", "test-first-bug-fixing", "situational-assessment").

```python
procedure = service.procedures.get("refactoring")
# procedure.steps → ordered list of actions
# procedure.prerequisites → what must be true before starting
```

**Agent Profiles** — Role definitions with these sections: purpose,
specialization, collaboration, mode_defaults, and initialization_declaration.
Doctrine references are authored on the top-level `*-references` fields
(`directive-references`, `tactic-references`, `toolguide-references`,
`styleguide-references`) — the retired `context-sources` block was removed
(mission `doctrine-drg-silent-drop-boundary`; #3629). Relationship fields such
as `specializes_from` are not profile fields; lineage belongs in the doctrine
DRG. Profiles support weighted matching against task context (DDR-011 algorithm).

```python
profile = service.agent_profiles.get("implementer")
# profile.purpose.mandate → what this agent is responsible for
# profile.specialization.boundaries → what it should not do

# `find_best_match` is a repository method, not available on the filtered
# `agent_profiles` dict above — reach it through the pinned lineage/mutation
# accessor instead:
best = service.agent_profile_repository.find_best_match(task_context)
```

```bash
spec-kitty agent profile list
spec-kitty agent profile show implementer
```

**Step Contracts** — Structured action definitions that link public actions
(specify, plan, implement, review) to doctrine artifacts via `DelegatesTo`.
Each contract defines ordered steps; each step may delegate to a tactic,
directive, or procedure by kind and candidate list.

```python
contract = service.mission_step_contracts.get("implement")
for step in contract.steps:
    if step.delegates_to:
        # Load the referenced doctrine artifact
        artifact = getattr(service, step.delegates_to.kind + "s").get(
            step.delegates_to.candidates[0]
        )
```

### Discovering Available Artifacts

There is no `doctrine list` or `doctrine show` CLI command. Use the programmatic
`DoctrineService` API or read artifact YAML files directly:

```python
from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

service = build_activation_aware_doctrine_service(project_root)

# List or inspect artifacts by kind
directive = service.directives.get("DIRECTIVE_034")
tactic = service.tactics.get("tdd-red-green-refactor")
paradigm = service.paradigms.get("<paradigm-id>")
# Shipped artifacts: packs/built-in/<kind>/
# Project-layer artifacts: .kittify/charter-packs/<kind dir>/ (written by
# `spec-kitty charter new`; see Step 4 for the per-kind directories)
```

To validate project-layer artifacts:
```bash
spec-kitty charter validate .kittify/charter-packs
```

To list registered mission types (every visible type, activated or not):
```bash
spec-kitty charter mission-type list --include-inactive
```

To list agent profiles:
```bash
spec-kitty agent profile list
```

Shipped artifacts live in `packs/built-in/<kind>/`. Project-local
overrides live in `.kittify/<kind>/`. Two-source loading merges both,
with project artifacts taking precedence on field-level merge.

**Template sets** (from `packs/built-in/missions/`):
- `software-dev-default` — Core development workflow
- `plan-default` — Goal-oriented planning
- `documentation-default` — Documentation creation (Divio)
- `research-default` — Research and evidence gathering

**Default tool registry:** spec-kitty, git

### Interview Profiles

**Minimal** (8 questions — fast bootstrap):

| Question | Governance use |
|---|---|
| `project_intent` | Policy summary, preamble |
| `languages_frameworks` | Styleguide selection (e.g., Python) |
| `testing_requirements` | `testing.framework`, `testing.min_coverage` |
| `quality_gates` | Quality Gates section |
| `review_policy` | `quality.pr_approvals`, Branch Strategy |
| `performance_targets` | `performance.cli_timeout_seconds` |
| `deployment_constraints` | `branch_strategy.rules` |

**Comprehensive** (11 questions — adds 4 more):

| Question | Governance use |
|---|---|
| `documentation_policy` | Added to Project Directives |
| `risk_boundaries` | Added to Project Directives |
| `amendment_process` | Amendment Process section |
| `exception_policy` | Exception Policy section |

### answers.yaml Schema

```yaml
schema_version: "1.0.0"
mission: "software-dev"
profile: "minimal"
answers:
  project_intent: "..."
  languages_frameworks: "..."
  testing_requirements: "..."
  quality_gates: "..."
  review_policy: "..."
  performance_targets: "..."
  deployment_constraints: "..."
  # comprehensive only:
  documentation_policy: "..."
  risk_boundaries: "..."
  amendment_process: "..."
  exception_policy: "..."
selected_paradigms:
  - "<project-paradigm>"
selected_directives:
  - "<project-directive>"
available_tools:
  - "spec-kitty"
  - "git"
  - "<project-tool>"
```

---

## Step 1: Check Current State

```bash
spec-kitty charter status --json
```

Reports `synced` or `stale`, current and stored hashes, library doc count,
and per-file sizes. `governance`/`directives` are always read live from
`charter.yaml` — a `stale` report here does not mean governance config is
out of date; it is a legacy staleness signal, not a gate on correctness.

---

## Step 2: Discover the Charter Change

For agent-mediated governance setup and revision, the preferred discovery
surface is the chat itself, not the CLI questionnaire.

Recommended flow:

1. Inspect the repo quickly.
2. If a charter already exists, listen for the new guidance the
   human-in-command is flagging: a charter addition, course correction,
   observed agent failure, desired norm, or policy change. Ask only the minimum
   follow-up needed to encode it precisely.
3. If no charter exists or the user asks to start over, ask a short targeted
   governance interview in chat.
4. Synthesize `.kittify/charter/interview/answers.yaml` directly.
5. Run `spec-kitty charter generate --from-interview --json`.

Use the CLI interview only as a fallback when the user explicitly wants the CLI
prompt loop or wants deterministic defaults.

**CLI defaults path (fallback only):**

```bash
spec-kitty charter interview --mission-type software-dev --profile minimal --defaults --json
```

**CLI comprehensive path (fallback only):**

```bash
spec-kitty charter interview --mission-type software-dev --profile comprehensive
```

Key flags: `--profile minimal|comprehensive`, `--defaults`, `--json`,
`--selected-paradigms`, `--selected-directives`, `--available-tools`.
See `charter-command-map.md` for all flags.

**Output:** `.kittify/charter/interview/answers.yaml`

---

## Step 3: Generate the Charter

```bash
spec-kitty charter generate --from-interview --json
```

Key flags: `--mission-type`, `--template-set`, `--force`, `--from-interview`, `--json`.

Generation refreshes `charter.yaml`'s `catalog` and `metadata` sections
deterministically. `governance`/`directives`/activation/`overrides` are
preserved byte-for-byte through the shared round-trip merge (bootstrapped
from a legacy triad only the first time `charter.yaml` is created).
`charter.md` is never written by this command.

**Output:** `.kittify/charter/charter.yaml` (refreshed sections).

To commit the generated charter inputs, use:

```bash
spec-kitty safe-commit --message "chore: generate project charter" \
  .kittify/charter/interview/answers.yaml \
  .kittify/charter/charter.yaml \
  .gitignore
```

---

## Step 4: Load Context for Workflow Actions

Do not preload all action contexts after generation.

The runtime calls context automatically during slash commands. Manual
invocation is useful only for debugging one immediate action, and should avoid
consuming first-load state:

```bash
spec-kitty charter context --action specify --json --no-mark-loaded
```

Load context iteratively at the action boundary, not as part of charter setup.

---

## Step 5: Manual Edits to `charter.yaml`

Edit `charter.yaml`'s `governance:` or `directives:` sections directly —
there is no separate sync step. The next `charter context` call reads the
file as-is.

```bash
spec-kitty charter sync --json   # retained for back-compat; always a no-op
```

`charter sync` no longer extracts anything from `charter.md`. It always
reports `synced=False` / `files_written=[]`, regardless of `--force`.

---

## Programmatic Doctrine Access (DoctrineService)

`charter.activation.resolver.DoctrineService` — built through
`charter.activation.doctrine_service_builder.build_activation_aware_doctrine_service` —
is the single, sanctioned entry point for programmatic access to all doctrine
artifacts. It wraps the inner `charter.offering.service.DoctrineService` and applies
charter activation filtering; never construct `charter.offering.service.DoctrineService`
or `charter.offering.agent_profiles.AgentProfileRepository` directly (five
architectural gates in `tests/architectural/` ban that construction outside
this module).

```python
from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

service = build_activation_aware_doctrine_service(project_root)
```

### Available Repositories (gated properties)

Nine properties are activation-gated: each returns a plain `dict[str, <Artifact>]`
filtered to whatever the charter has activated (or every shipped artifact of
that kind, when nothing is configured). A `dict` supports `.get(id)` but not
repository-only operations like `.list_all()`, `.save()`, or
`find_best_match()` — see the raw-repository escape hatch below for those.

| Property | Returns | Artifacts |
|---|---|---|
| `service.agent_profiles` | `dict[str, AgentProfile]` | Agent role profiles with DDR-011 matching |
| `service.directives` | `dict[str, Directive]` | Numbered project rules (TEST_FIRST, etc.) |
| `service.tactics` | `dict[str, Tactic]` | Reusable implementation approaches (TDD, ZOMBIES, etc.) |
| `service.styleguides` | `dict[str, Styleguide]` | Language/domain writing style guides |
| `service.toolguides` | `dict[str, Toolguide]` | Tool-specific operational guidance |
| `service.paradigms` | `dict[str, Paradigm]` | High-level development paradigms |
| `service.procedures` | `dict[str, Procedure]` | Multi-step reusable workflow primitives |
| `service.mission_step_contracts` | `dict[str, MissionStepContract]` | Structured action contracts with delegation |
| `service.glossary_packs` | `dict[str, GlossaryPack]` | Canonical terminology packs |

### Common Repository Operations

`.get()` works directly on the gated dict:

```python
# Get a specific artifact by ID
tactic = service.tactics.get("tdd-red-green-refactor")
```

Operations the filtered dict cannot support — `.list_all()`, `.save()`,
`.get_provenance()` — go through the raw-repository escape hatch,
`service.raw_repository(kind)`, which returns the underlying repository
object unfiltered (a deliberate, sanctioned bypass of activation filtering,
not of construction: it still comes from the one wrapped `service`, never a
second `DoctrineService()`):

```python
# List all artifacts of a kind (raw repository, not the filtered dict)
all_tactics = service.raw_repository("tactics").list_all()

# Save a project-local artifact (procedures, step contracts)
service.raw_repository("procedures").save(my_procedure)
```

### Agent Profile Resolution

Agent profiles support weighted context-based matching and `specializes_from`
lineage traversal. Both are repository operations, not available on the
filtered `agent_profiles` dict, so they go through the pinned
`agent_profile_repository` accessor instead of `raw_repository("agent_profiles")`:

```python
from charter.offering.agent_profiles.profile import TaskContext

context = TaskContext(
    language="python",
    framework="typer",
    file_paths=["src/specify_cli/cli.py"],
    keywords=["cli", "testing"],
)

profile = service.agent_profile_repository.find_best_match(context)
# profile.purpose.mandate → what this agent is responsible for
# profile.specialization.boundaries → what it should not do
# profile.initialization_declaration → startup context text
```

Profile lineage is represented by DRG edges, not a `specializes_from` field on
profile YAML. Language-specific profiles can still be related to base roles in
the DRG and resolved through profile matching.

### Action-Scoped Doctrine via Action Indices

Each mission action (specify, plan, implement, review) has an action index
that lists which doctrine artifacts are relevant to that step:

```python
from charter.offering.missions.action_index import load_action_index

index = load_action_index(missions_root, "software-dev", "implement")
# index.directives → ["TEST_FIRST"]
# index.tactics → ["tdd-red-green-refactor", "zombies-tdd"]
# index.procedures → ["implementation-handoff"]
```

The charter context builder uses these indices internally. When you call
`spec-kitty charter context --action implement`, only the doctrine
artifacts listed in the implement action index are included.

### MissionStepContract: Structured Action Contracts

Step contracts define the structure of each public action and link to
doctrine artifacts via `DelegatesTo`:

```python
contract = service.mission_step_contracts.get("implement")
for step in contract.steps:
    if step.delegates_to:
        # step.delegates_to.kind → ArtifactKind (e.g., "tactic")
        # step.delegates_to.candidates → ["tdd-red-green-refactor", ...]
        pass
```

This is the bridge between the mission execution surface and the doctrine
knowledge layer. Step contracts say *what* to do; doctrine artifacts say
*how*.

---

## Iterative Context Loading Pattern

Agents should load doctrine context **iteratively**, not all at once. The
architecture supports this through depth-controlled context and per-artifact
retrieval.

### The Pattern

1. **At session init**: Resolve agent profile. Load `initialization_declaration`.
2. **At each step boundary**: Call `charter context --action <action>`.
   First call gets bootstrap (depth-2), subsequent calls get compact (depth-1).
3. **Mid-step, when guidance needed**: Pull specific tactic or directive by ID
   through `DoctrineService`.
4. **Never**: Load the full doctrine catalog into prompt context.

### Why This Matters

Each doctrine artifact consumes tokens. Loading all directives, tactics,
paradigms, and styleguides at session start wastes context on artifacts that
are irrelevant to the current action. Action indices exist specifically to
scope which artifacts matter for each step.

---

## When Doctrine Constrains Runtime

Doctrine constrains runtime behavior when the charter has been generated
and the agent is executing a workflow action (specify, plan, implement, review).
The specific constraints come from the project's own charter — load them
with `spec-kitty charter context --action <action> --json` rather than
assuming fixed policy values.

Doctrine does NOT constrain when:

- The user works outside a mission.
- No charter has been generated.
- The action is not a workflow action (specify, plan, implement, review).

---

## Governance Anti-Patterns

1. **Editing `charter.yaml`'s generated sections** — `catalog` and
   `metadata` are overwritten by `charter generate` on every run. Edit
   `governance`/`directives`/activation/`overrides` instead — those are
   preserved byte-for-byte.
2. **Expecting `charter.md` edits to change runtime policy** — the runtime
   never parses `charter.md`. Edit `charter.yaml` for policy changes;
   `charter.md` is a curated companion only.
3. **Skipping the interview** — produces generic defaults; the charter
   is most valuable with project-specific decisions.
4. **Running `charter sync` expecting an effect** — it is retained for
   back-compat call sites only and always no-ops. There is no required
   post-edit step after changing `charter.yaml` by hand.
5. **Legacy path assumptions** — canonical path is
   `.kittify/charter/charter.yaml`, not `.kittify/memory/` and not a
   `governance.yaml`/`directives.yaml`/`references.yaml` triad.
6. **Upfront context dump** — loading all doctrine at session start wastes
   tokens and dilutes relevance. Use action-scoped loading and pull specific
   artifacts on demand.

See `doctrine-artifact-structure.md` for the full anti-pattern table.

---

## References

- `charter-command-map.md` -- Full CLI command reference with all flags and output fields
- `doctrine-artifact-structure.md` -- File layout, authority classes, and data flow
