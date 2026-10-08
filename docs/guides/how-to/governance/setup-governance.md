---
title: How to Set Up Project Governance
description: The complete interview-to-generation flow for creating, validating, and activating your Spec Kitty project charter.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/external/tech-lead-evaluator.md
type: how-to
related:
- docs/context/charter-overview.md
- docs/guides/tutorials/charter-governed-workflow.md
- docs/guides/how-to/governance/troubleshoot-charter.md
- docs/guides/how-to/governance/synthesize-doctrine.md
- docs/guides/how-to/missions/create-specification.md
- docs/guides/how-to/installation/non-interactive-init.md
- docs/guides/how-to/missions/switch-missions.md
- docs/architecture/charter-pack-usage-journey.md
---
# How to Set Up Project Governance

This is the single, start-to-finish walkthrough for creating your project's Charter: from a
project with no governance configured, through the interview, generation, validation, and
synthesis, to a charter that is active and automatically injected into every governed mission
action.

- For the conceptual model behind these steps — the DRG, bootstrap vs. compact context,
  governed profile invocation — see [How Charter Works](../../../context/charter-overview.md).
- If a step below fails, see [Troubleshooting Charter Failures](troubleshoot-charter.md).
- For the full doctrine-synthesis workflow (partial resynthesis, provenance, recovery from a
  stale bundle) beyond the quick version in Step 4 below, see
  [How to Synthesize and Maintain Doctrine](synthesize-doctrine.md).
- For the faster, preset-driven alternative to this interview-driven walkthrough — `charter
  activate --preset` plus the required `charter generate` follow-up, and how the dispatch fallback
  behaves at each step — see
  [Activation Preset Usage Journey](../../../architecture/charter-pack-usage-journey.md).

## Prerequisites

- Spec Kitty 3.x installed — verify with `uv run spec-kitty --version`
- A git repository (new or existing). Charter requires a git working tree.
- A Spec Kitty project scaffold. For a fresh repository, run
  `uv run spec-kitty init --ai claude --non-interactive` before continuing. `init` is idempotent,
  so rerunning it in an already-initialized project exits cleanly.

## The governance model, briefly

Two files matter, and they are not peers:

- **`.kittify/charter/charter.yaml`** is the single git-tracked, **authoritative**, structured
  charter. Its `governance`, `directives`, `catalog`, activation, and `overrides` sections all
  live here. You author `governance`, `directives`, activation, and `overrides` (directly, or via
  the interview); `charter generate` refreshes `catalog` and `metadata` deterministically from
  the active charter, without touching your authored sections.
- **`.kittify/charter/charter.md`** is a **curated companion**: a human-readable narrative the
  runtime never parses, scrapes, or resolves policy from. Editing it has no effect on governed
  mission behavior. `charter generate` seeds a starter `charter.md` only when one is absent, and
  never overwrites an existing one.

`.kittify/config.yaml` carries a single `charter:` pointer that resolves the active
`charter.yaml`. When `spec-kitty next` invokes an agent profile for a mission action, the runtime
reads `charter.yaml` directly and injects the relevant governance context into the prompt
automatically — that is what "governed" means throughout this guide.

## Step 1: Run the Interview

The interview captures your project's policy decisions and saves them as structured answers to
`.kittify/charter/interview/answers.yaml`.

### Quick path (non-interactive)

Use `--defaults` to accept deterministic defaults without prompts. Good for bootstrapping or CI:

```bash
spec-kitty charter interview \
  --profile minimal \
  --defaults \
  --json
```

### Full interactive path

For a thorough setup, use the comprehensive profile, which asks 11 questions:

```bash
spec-kitty charter interview \
  --profile comprehensive
```

### What the interview asks

**Minimal profile (8 questions):**

| Question | What it controls |
|----------|-----------------|
| Project intent | Policy summary in the charter preamble |
| Languages and frameworks | Styleguide selection (e.g., Python) |
| Testing requirements | Test framework, minimum coverage |
| Quality gates | Linting, type checking, pre-commit hooks |
| Review policy | Required PR approvals, branch strategy |
| Performance targets | CLI timeout thresholds |
| Deployment constraints | Branch naming and protection rules |

**Comprehensive profile adds 4 more:**

| Question | What it controls |
|----------|-----------------|
| Documentation policy | Added as a project directive |
| Risk boundaries | Added as a project directive |
| Amendment process | How the charter itself can be changed |
| Exception policy | How to handle one-off policy exceptions |

### Override selections

You can override the interview's artifact selections on the command line:

```bash
spec-kitty charter interview \
  --profile minimal \
  --defaults \
  --selected-paradigms "test-first" \
  --selected-directives "TEST_FIRST" \
  --available-tools "spec-kitty,git,python,pytest,ruff,mypy,uv" \
  --json
```

## Step 2: Generate the Charter Bundle

Generate (or refresh) the charter bundle from your interview answers:

```bash
spec-kitty charter generate --from-interview --json
```

This refreshes `charter.yaml`'s `catalog` and `metadata` sections from the active charter,
seeds a starter `charter.md` companion if one is not already present (an existing `charter.md` is
left untouched), and auto-stages the produced files via `git add --force` so the immediately
following `charter bundle validate` succeeds without a manual `git add`. It also ensures
`.gitignore` carries the required entries for derived charter artifacts.

> **Note**: `charter generate` requires a git working tree. If you run it outside a git repo it
> exits non-zero with an error directing you to run `git init` first.

### Overwrite an existing charter

To force a full regeneration from your interview answers:

```bash
spec-kitty charter generate --from-interview --force --json
```

### Choose a template set

Override the doctrine template set if your project needs a different workflow shape:

```bash
spec-kitty charter generate \
  --from-interview \
  --template-set plan-default \
  --json
```

Available template sets: `software-dev-default`, `plan-default`, `documentation-default`,
`research-default`.

### Point at an existing public constitution

If your repository already publishes governance outside `.kittify/` — for example
`spec/constitution.md` — keep that document in place and reference it from `charter.yaml` rather
than duplicating it. Declare it under `governance.charter.governance_references` (the
interview's equivalent question writes into this same section):

```yaml
governance:
  charter:
    governance_references:
      - spec/constitution.md
```

`spec-kitty charter context --action ...` renders these paths as required governance reading, and
`spec-kitty charter status` reports missing or unsafe references so you can fix stale paths. All
referenced paths must be repository-relative and stay inside the repo root. Spec Kitty does not
require the public document and `charter.yaml` to be byte-for-byte equal — `charter.yaml` is the
only one the runtime resolves.

## Step 3: Validate the Bundle

Before promoting doctrine, verify the bundle is internally consistent.

### 3a. Check for graph-native decay

```bash
spec-kitty charter lint
```

`charter lint` detects orphaned directives (referenced in the DRG but without a backing tactic),
contradictions between directives, and staleness (directives whose provenance points to a deleted
or superseded built-in directive).

### 3b. Validate the bundle schema

```bash
spec-kitty charter bundle validate
```

This validates the charter bundle against the `CharterBundleManifest` v2.0.0 schema — the
structured-`charter.yaml` manifest — checking that all required files are present, correctly
structured, and consistent.

### 3c. Check status

```bash
spec-kitty charter status --json
```

`charter status` reports the bundle's freshness (charter → bundle → DRG), synthesis state,
org-layer state, and the health of any declared `governance_references`. If lint and validate
both pass and status shows no drift, you are ready to synthesize.

## Step 4: Synthesize Doctrine

Synthesis promotes agent-generated project-local doctrine artifacts into `.kittify/charter-packs/`,
making them available for runtime context injection.

```bash
# Preview first
spec-kitty charter synthesize --dry-run

# Apply
spec-kitty charter synthesize

# Confirm
spec-kitty charter status
```

On a fresh project where `.kittify/charter/generated/` is missing or empty (the agent harness has
not yet written candidate artifacts), synthesize creates the minimal artifact set — a
`.kittify/charter-packs/` directory marker and a `PROVENANCE.md` record — and the runtime falls back to
the built-in Charter Pack until a full synthesis run with agent-generated content completes. For partial
resynthesis, provenance inspection, and recovery from a stale bundle, see
[How to Synthesize and Maintain Doctrine](synthesize-doctrine.md).

### Quick baseline via an activation preset

If you'd rather start from a small curated baseline than write directives from scratch, activate a
preset of the built-in Charter Pack instead of running the full interview:

```bash
spec-kitty charter activate --preset minimal
spec-kitty charter generate --no-from-interview
```

`charter activate --preset` writes the preset's activation keys into the active charter
(`.kittify/config.yaml`, or the pointed-at `charter.yaml`) with replace semantics: keys the preset
lists are written, keys it governs but leaves out are removed. A change to a key you customised is
refused unless you pass `--force`. Two honest caveats: activating config entries does not by
itself guarantee an unmatched `spec-kitty dispatch` routes to a specialist profile — you may still
need `--profile <profile-id>` to be explicit — and on a fresh project the activations need the
`charter generate --no-from-interview` compile step before they render into
`.kittify/charter/charter.yaml` (see issue #3105 in the project issue tracker; check that issue for
current resolution status). That same compile step is also what resolves the "routed to the
generic agent" symptom in
[Troubleshooting Charter Failures](troubleshoot-charter.md#2-missing-doctrine): the generic-agent
fallback only checks whether the compiled bundle exists, not what it activates — `minimal` still
activates no `agent_profiles`, so `--profile` may still be needed to resolve ambiguity.

## Step 5: Confirm Governance Is Active

Your charter is active once `spec-kitty charter status` reports no drift after synthesis. From
here, governance context loads automatically — you don't call anything manually in normal use.

### How context loading works

When `spec-kitty next` builds a prompt for a mission action, the runtime traverses the DRG from
that action's entry point and renders the relevant governance context into the prompt. The same
resolution is exposed for debugging as:

```bash
spec-kitty charter context --action <action> --json
```

| Mode | When it fires | What the agent sees |
|------|--------------|---------------------|
| Bootstrap | First time an action loads context (or a freshly generated charter) | Full relevant DRG subgraph — all applicable directives and tactics |
| Compact | Subsequent loads, or when the DRG payload is too large to include in full | Resolved paradigms, directives, tools, and template set only — a known limitation, see issue #787 |
| Missing | No charter exists | Instructions telling the agent to create one |

First-load state is tracked per action in `.kittify/charter/context-state.json`. Each action
(specify, plan, implement, review, ...) has an independent first-load timestamp.

### Verify with a real mission action

```bash
spec-kitty charter context --action implement --json
```

This is useful when diagnosing unexpected agent behavior during a workflow step, or simply to
confirm governance context is flowing before you start real mission work.

## Anti-Patterns to Avoid

### Editing derived sections directly

`charter.yaml`'s `catalog` and `metadata` sections, plus `references.yaml`, runtime state, and
synthesis outputs, are owned by CLI commands. Manual edits there can be overwritten or make bundle
validation misleading. Edit `charter.yaml`'s `governance:` and `directives:` sections (or run the
interview) instead, then re-run `charter generate` and synthesis as needed.

### Skipping the interview

Running `generate` without an interview produces generic defaults. The charter is most valuable
when it contains your project's actual policy decisions — testing thresholds, review
requirements, branching rules. Take the time to answer the questions.

### Enforcing public-charter equality

Do not require `spec/constitution.md` and `.kittify/charter/charter.yaml` to be equivalent unless
your project explicitly chooses that mirror policy. Spec Kitty treats external governance docs as
supporting reading declared via `governance_references`, not an alternate authoritative source.

### Keeping constitution-era paths

Do not use `.kittify/memory/constitution.md`, `.kittify/constitution/constitution.md`, or
`.kittify/constitution/{governance,directives,metadata}.yaml` as current runtime paths. Migrate
current policy into `.kittify/charter/charter.yaml`; move any still-useful public document to a
normal repo path such as `spec/constitution.md` and declare it in `governance_references`.

## Complete Workflow Example

Set up governance for a new project from scratch:

```bash
# 1. Create the Spec Kitty project scaffold
uv run spec-kitty init --ai claude --non-interactive

# 2. Run the interview
uv run spec-kitty charter interview --profile comprehensive

# 3. Generate the charter bundle
uv run spec-kitty charter generate --from-interview --json

# 4. Validate
uv run spec-kitty charter lint
uv run spec-kitty charter bundle validate

# 5. Synthesize doctrine
uv run spec-kitty charter synthesize --dry-run
uv run spec-kitty charter synthesize

# 6. Confirm everything is current
uv run spec-kitty charter status --json

# 7. Start working — governance context loads automatically
uv run spec-kitty specify "Build user authentication module"
```

Later, after updating your charter, edit `.kittify/charter/charter.yaml` directly (its
`governance:`/`directives:` sections), then re-run status/lint/synthesize as needed — there is no
separate sync step; the next `charter context` call reads the file as-is.

## What's Next

You now have an active, governed charter. From here:

- [How to Synthesize and Maintain Doctrine](synthesize-doctrine.md) — partial resynthesis,
  provenance, recovery from stale bundles
- [How to Run a Governed Mission](run-governed-mission.md) — composed steps, prompt resolution,
  blocked decisions
- [How to Use Retrospective Learning](use-retrospective-learning.md) — preview and apply
  synthesis proposals after a mission completes
- [Charter-Governed Workflow](../../tutorials/charter-governed-workflow.md) — a guided tour connecting this setup
  flow to a full mission run
- [How Charter Works](../../../context/charter-overview.md) — the DRG, bootstrap/compact context, and
  governed profile invocation in depth

## Command Reference

- [CLI Commands](../../../api/cli-commands.md) — full CLI reference including charter subcommands

## See Also

- [How Charter Works](../../../context/charter-overview.md) — Charter mental model and the DRG
- [Troubleshooting Charter Failures](troubleshoot-charter.md) — fixes for stale bundles, missing
  doctrine, compact-context limits, retrospective gate failures, and synthesizer rejections
- [Create a Specification](../missions/create-specification.md) — start a mission with governance active
- [Switch Missions](../missions/switch-missions.md) — how missions interact with governance
- [Non-Interactive Init](../installation/non-interactive-init.md) — automated project setup including charter
- [Activation Preset Usage Journey](../../../architecture/charter-pack-usage-journey.md) — the
  preset onboarding alternative and the dispatch safety net

## Background

- [Mission System](../../../architecture/mission-system.md) — how missions use governance context
