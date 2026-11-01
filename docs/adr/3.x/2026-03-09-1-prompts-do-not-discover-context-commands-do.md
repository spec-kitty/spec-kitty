---
title: Prompts Do Not Discover Context, Commands Do
description: 'Command-layer context resolution becomes canonical: prompt templates may no longer infer mission, work package, or base branch from cwd, branch name, or repo scans.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-03-09'
---

## Context and Problem Statement

Spec Kitty currently has two overlapping execution models:

1. `spec-kitty next`, which is runtime-driven and already knows mission state and feature context.
2. Legacy slash commands (`/spec-kitty.tasks`, `/spec-kitty.implement`, `/spec-kitty.review`, and related generated prompt files), which are static templates rendered once and then interpreted by an LLM at runtime.

This split has created context drift and contradictory behavior.

### Observed failures

1. `/spec-kitty.tasks` in a multi-feature repository instructed the model to detect feature context from repo state, then called `finalize-tasks` without an explicit feature slug. The command correctly rejected the request with `FEATURE_CONTEXT_UNRESOLVED`.
2. `/spec-kitty.implement` called `spec-kitty agent workflow implement` without a resolved work package or base. The command auto-selected the first planned WP, then immediately failed because the selected WP had a dependency and required `--base`.
3. Review prompts instructed agents to approve a WP by moving it directly to `done`, while the task command now treats `done` as a merge-verified state and blocks that transition until merge ancestry is confirmed.

These failures are not random prompt mistakes. They are symptoms of an architectural mismatch:

* Runtime-backed flows already know context.
* Static prompts do not.
* Prompt templates are compensating by asking the model to rediscover context from cwd, branch name, feature directories, and heuristics.

That design is fragile in multi-feature repositories, dependency-heavy work package graphs, and workflows where review approval and merge completion are distinct states.

## Decision Drivers

1. Deterministic agent behavior in multi-feature repositories.
2. Single source of truth for feature, WP, dependency, and branch context.
3. Elimination of prompt drift between `next` and legacy slash-command flows.
4. Better compatibility across agent hosts where generated prompt files are static.
5. Testable action resolution without depending on LLM prompt interpretation.
6. Clear separation between review approval state and merge/integration state.

## Considered Options

### Option 1: Keep prompt-level discovery as-is

Legacy slash commands continue asking the model to inspect cwd, branch, repo contents, and command errors to infer what to do.

### Option 2: Add richer static placeholder injection to generated slash-command files

Extend prompt rendering with more placeholders such as `{FEATURE_SLUG}`, `{WP_ID}`, `{TARGET_BRANCH}`, and `{RESOLVED_BASE}`.

### Option 3: Introduce a canonical action-context resolver command and make prompts consume it

Add a single command-level contract that resolves feature/WP/base/workspace/review context for each action. `next` and legacy slash commands both use this resolver.

### Option 4: Deprecate legacy slash commands entirely and require `spec-kitty next` for all agent loops

Make `next` the only supported agent loop and stop investing in direct slash-command execution.

## Decision Outcome

**Chosen option:** Option 3, "Introduce a canonical action-context resolver command and make prompts consume it."

### Core decision

Prompts do not discover context. Commands do.

This means:

1. Prompt templates MUST NOT ask the model to infer feature context from current branch, cwd, or repository scans when command-layer context can be resolved directly.
2. Prompt templates MUST treat command JSON output as canonical execution context.
3. Legacy slash commands remain supported, but they become thin wrappers around command-owned context resolution instead of free-form workflow guides.
4. `spec-kitty next` remains the canonical mission loop, but it MUST share the same context-resolution backend as legacy slash commands.

### Canonical contract

Spec Kitty SHALL expose a single action-context resolver command, for example:

```bash
spec-kitty agent context resolve --action <tasks|tasks_finalize|implement|review|accept|merge> --json
```

The resolver SHALL return, as applicable:

* `feature_slug`
* `feature_dir`
* `mission_key`
* `target_branch`
* `wp_id`
* `wp_file`
* `lane`
* `dependencies`
* `resolved_base`
* `workspace_path`
* `exact_command`
* `blocked_reason`
* `remediation`

If ambiguity remains after command-owned resolution, the command SHALL return structured remediation or a decision-required response. The prompt MUST NOT be responsible for inventing the missing context.

### State-model decision

Review approval and merge completion SHALL be treated as separate concepts.

`done` SHALL mean merge/integration-complete, not merely "review passed". Review approval SHALL be represented separately, either by:

1. an explicit `approved` lane, or
2. an equivalent gate-backed intermediate state that is not conflated with `done`.

The current model, where prompts instruct "approve by moving to done" while the command guard interprets `done` as merge-verified, is explicitly rejected.

## Consequences

### Positive

1. No prompt-level feature discovery in multi-feature repositories.
2. `next` and legacy slash commands use the same context rules and exact commands.
3. Implement flows stop failing immediately after auto-selecting a dependent WP without a base.
4. Review prompts stop instructing actions that command guards forbid.
5. Action selection becomes unit-testable and integration-testable without relying on LLM interpretation.
6. Generated prompt files remain simple and portable across agent hosts.

### Negative

1. Requires a non-trivial refactor across prompt templates, runtime bridge code, and workflow commands.
2. Introduces a new context-resolution surface that must be maintained as a stable JSON contract.
3. Requires migration of existing slash-command templates and likely regeneration of prompt files in downstream repos.
4. May require a lane/state migration if `approved` is introduced explicitly.

### Neutral

1. Existing simple placeholders such as `{ARGS}`, `{SCRIPT}`, `{AGENT_SCRIPT}`, and `__AGENT__` can remain for static generation.
2. Legacy slash commands can remain available during migration, but they are no longer allowed to own workflow discovery logic.
3. `spec-kitty next` remains the preferred top-level loop for long-lived agent execution.

## Rejected Approaches

### Static placeholder expansion as the primary fix

Adding more static placeholders to rendered command files does not solve the core problem. Generated slash-command files are created before runtime action context is known. They cannot safely encode live feature/WP/base choices in repositories with multiple active features and evolving task graphs.

### Prompt heuristics plus better wording

Improving prompt instructions without moving context resolution into commands would reduce some failures, but it would still leave action correctness dependent on LLM reasoning over repo state, command errors, and conventions. That is not a stable execution model.

### Redefining `done` to mean both approved and merged

One lane should not carry both review approval and merge ancestry semantics. That conflation is the source of the current review/done contradiction.

## Migration Plan

1. Add a shared context-resolution module in CLI core and expose it through `spec-kitty agent context resolve`.
2. Route `spec-kitty next` action planning and prompt generation through the shared resolver wherever action context is needed.
3. Update software-dev command templates for `tasks`, `tasks-outline`, `tasks-packages`, `tasks-finalize`, `implement`, and `review` to call the resolver first and use its JSON output as canonical.
4. Unify top-level `implement` and `agent workflow implement` so single-parent dependency handling is identical.
5. Introduce an explicit review-approved state that is distinct from `done`, then update prompts, lane logic, and mission guards accordingly.
6. Add migrations for generated prompt files and any lane/state transition docs affected by the new contract.
7. Add regression tests proving that `next` and legacy slash-command flows resolve identical context for the same repository state.

## Verification

This ADR will be considered implemented when all of the following are true:

1. No software-dev slash command instructs agents to detect feature context from branch or cwd.
2. `tasks-finalize` is always invoked with canonical feature context.
3. `implement` resolves a safe base strategy before presenting the execution command.
4. Review prompts do not instruct direct `done` transitions that violate merge ancestry guards.
5. `done` transitions reflect merge-complete state, not just review approval.
6. `spec-kitty next` and legacy slash-command execution resolve the same `feature_slug`, `wp_id`, `resolved_base`, and `workspace_path` for the same repository state.

## Related ADRs

* [2026-02-17-1-canonical-next-command-runtime-loop.md](../2.x/2026-02-17-1-canonical-next-command-runtime-loop.md)
* [2026-02-17-2-runtime-owned-mission-discovery-loading.md](../2.x/2026-02-17-2-runtime-owned-mission-discovery-loading.md)

## More Information

Key current seams this ADR is intended to remove:

* Static slash-command rendering only injects a small fixed placeholder set.
* `next` already has runtime-owned feature context.
* Legacy prompt templates still contain branch/cwd/context rediscovery instructions.
* Review prompts and `move-task --to done` guards currently disagree on what `done` means.
