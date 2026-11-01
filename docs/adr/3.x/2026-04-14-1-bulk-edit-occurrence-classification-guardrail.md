---
title: 'ADR 1 (2026-04-14): Bulk-Edit Occurrence Classification Guardrail'
description: 'Bulk-edit missions must classify every occurrence into eight categories; review blocks when a changed file lands in a do-not-change category with no exception.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-14'
---

## Context and Problem Statement

When a codebase-wide edit changes a term — a rename, a terminology migration, a
package-path move, a feature-label swap — the **same string** appears in
semantically different contexts. A token like `constitution` might appear as:

- A Python class name (`CompiledConstitution`)
- An import path (`from constitution.sync import sync`)
- A filesystem path literal (`".kittify/constitution/constitution.md"`)
- A serialized dict/YAML key (`"constitution_hash"`)
- A CLI command name (`spec-kitty constitution sync`)
- A log message or docstring
- A telemetry label referenced by dashboards
- A test fixture or snapshot

Each category has **different change rules**. A Python class name can be safely
renamed. A serialized dict key writes to existing data files that downstream
systems read — renaming the key breaks deserialization. A CLI command name is a
public API with users running scripts — renaming breaks those scripts. A
telemetry label is referenced by dashboards, alerts, and queries outside the
repo — renaming silently bifurcates metrics.

Mechanical find-and-replace (`sed`, LLM mass-edit, IDE rename refactor) treats
all of these as a single operation. The edits produce no warnings. Tests and
build systems often don't catch the breakage because the code still compiles
and unit tests pass — the harm is in the data layer, the API contract, or the
observability surface. The failure only surfaces in production, long after the
diff is merged.

Spec Kitty missions have no workflow mechanism to force a deliberate
per-category classification before bulk edits begin. This is the failure shape
issue #393 was created to close.

## Decision Drivers

- Bulk renames and terminology migrations are common and will recur; the
  system must prevent the silent-breakage class without requiring a new mission
  type or a parallel review mechanism for every mission.
- The cost of a false negative (an unchecked bulk edit corrupting serialized
  data or breaking a CLI) is orders of magnitude higher than the cost of a
  false positive (an author drafts an occurrence map the user approves in one
  pass).
- The guardrail must work identically across all 12 supported AI agents
  (Claude Code, Codex, Gemini, Copilot, OpenCode, Qwen, Cursor, Windsurf,
  Kilocode, Augment, Roo, Q) without agent-specific behavior.
- Existing doctrine extensibility (directives + tactics, `mission_v1` guard
  registry, expected-artifacts manifest) should be preferred over new
  infrastructure.
- The user of spec-kitty never says "bulk edit"; they say "rename Coffee to
  Tea." Therefore the workflow must be **agent-driven**, not user-declarative.
- The Spec Kitty CLI is the only layer where edits can be gated **before they
  begin** (pre-commit, CI, and PR review all run after the mechanical rename
  has already happened).

## Considered Options

- **Option A:** New workflow step type (`classify_occurrences`) injected into
  mission configs, surfaced on the dashboard, tracked as a first-class status
  lane, with its own approval cycle.
- **Option B:** Guard condition on the existing `implement` and `review`
  actions. A classification artifact (`occurrence_map.yaml`) is a mission-level
  planning deliverable; the guard blocks action dispatch when the mission is
  marked `change_mode: bulk_edit` and the artifact is absent or inadmissible.
- **Option C:** Post-hoc validation — accept any edit, detect violations via a
  pre-merge or CI-level scan (git hook or GitHub Action) that grep-classifies
  the diff.
- **Option D:** AST-level or tree-sitter-level occurrence classification that
  inspects every changed line and assigns a semantic category, then enforces
  per-category rules at the line level.

Within the gate for option B, three sub-options on review-time compliance were
considered:

- **B.1:** Artifact-admissibility only. Review checks that the map exists and
  is structurally valid; human/AI reviewer uses the map as a reference.
- **B.2:** Path-heuristic diff compliance. Review additionally inspects the
  git diff, classifies each changed file by filesystem path and extension, and
  rejects when a changed file lands in a `do_not_change` category or cannot be
  mapped.
- **B.3:** Full semantic diff compliance. Review parses each changed file,
  identifies individual occurrences of the target string, classifies each one,
  and rejects at line granularity.

## Decision

Adopt **Option B**: guard condition on the `implement` and `review` actions, driven
by a mission-level `change_mode: bulk_edit` flag and an `occurrence_map.yaml`
artifact that classifies the 8 standard occurrence categories with per-category
actions (`rename`, `manual_review`, `do_not_change`, `rename_if_user_visible`).

Within Option B, adopt **B.2**: path-heuristic diff compliance at review time.
The gate inspects `git diff --name-only`, classifies each changed file by path
pattern, and blocks the review when any changed file is classified into a
`do_not_change` category or cannot be mapped to any category and no matching
exception is declared. Exceptions in the map can override category rules on a
per-path basis with a documented `reason:`.

Activate the workflow **via an agent skill**, not via user declaration. The
`spec-kitty-bulk-edit-classification` doctrine skill teaches agents to recognize
bulk-edit intent in user requests ("rename X to Y", "the Blue feature is now
Red") during specify/plan, set `change_mode` on the user's behalf, draft the
occurrence map, and interview the user about per-category actions in plain
language. Trigger references in the specify and plan command templates point
agents to the skill at the right phase boundaries.

Codify the governance rule as a doctrine directive (`DIRECTIVE_035`) referencing a
new tactic (`occurrence-classification-workflow`).

Defer Option D (full semantic classification) to a future hardening mission.

## Rationale

### Why B over A, C, and D

**Why not A (first-class workflow step):** The classification decision is a
mission-level planning deliverable, not a work-package output. Treating it as a
workflow step would require new step types, new dashboard semantics, new
status-lane accounting, and a new approval cycle — infrastructure weight out of
proportion to the value. A guard condition on `implement` enforces the rule at
the only point that matters (before edits begin) without requiring any of that
infrastructure. A follow-on mission can promote B to a first-class step if
dashboard visibility becomes important; demoting A would be significantly
harder.

**Why not C (post-hoc validation):** By the time CI runs, the mechanical rename
has already happened. Violations show up as PR blockers that force a full
re-implementation rather than a deliberate up-front classification. Post-hoc
validation is valuable as a **backstop** but cannot replace the pre-edit
classification step that gives #393 its value. The guard fires at the one
moment where the author is positioned to decide; CI fires at the moment where
the author must fix or revert.

**Why not D (full semantic classification):** Out of scope per constraint
C-001. Full semantic classification requires per-language AST or tree-sitter
infrastructure for every language in the repo, plus heuristics for
distinguishing identifiers from string literals inside a single file. The
maintenance cost of that across 12 agents and the full matrix of supported
languages is prohibitive for v1. Path-heuristic classification at the file
granularity captures the most common silent-breakage shapes (serialized-key
YAML files, CLI command modules, test fixtures, telemetry config) without
touching source parsing.

### Why B.2 over B.1

**B.1 shipped first and was immediately critiqued** in post-merge review (P1
finding, this ADR supersedes it). The critique was correct: "review validates
the artifact exists" does not satisfy FR-007/FR-008's actual requirement that
review *reject diffs that violate the classification*. The map is a contract;
B.1 only verified the contract was written, not that execution respected it.

B.2 runs path-heuristic classification at the file level. This is imperfect —
a `.py` file mixes code symbols, import paths, string literals, and log
messages, and path heuristics cannot distinguish them — but it is sufficient
to catch the highest-value failure classes: whole-file modifications inside a
protected surface. The exception mechanism (glob patterns with action
overrides and documented reasons) bridges the cases where the heuristic is too
coarse or too fine.

### Why B.3 is out of scope

Full semantic diff compliance requires language-aware occurrence detection
(C-001 excludes this) and a per-occurrence classification model. Building that
for v1 would delay delivery by an order of magnitude. B.2's path-level
classification addresses the failure classes that motivated #393 (serialized
keys, CLI surfaces, telemetry labels, test fixtures) and leaves line-level
refinement to a future mission.

### Why agent-driven, not user-declarative

A declarative model requires every spec author to know the `change_mode` field
exists and remember to set it. This requirement is not satisfiable by the
product's users, who describe changes in product language ("rename Coffee to
Tea"), not operational language ("this is a bulk-edit mission"). Either the
system becomes something only expert users can drive — which fails
constraint C-004's breadth requirement — or the agent closes the knowledge
gap on the user's behalf.

The doctrine skill is the load-bearing piece of this decision. Without it, the
guardrail exists but is invisible to the people and agents who should be
applying it. The command-template triggers ensure the skill is loaded at the
right phase (specify, plan) without expanding prompt surface at other phases.

### Why the runtime gate has no bypass flag

The artifact-admissibility gate and the diff-compliance gate both exit with a
hard error and no bypass flag. Intentional. The mechanism that blocks must be
stronger than a stray keyword or a tired reviewer. If the gate is wrong on a
specific case, the remediation is **editing the occurrence map** (an
auditable, reviewable change with a recorded `reason:`), not a silent
command-line flag that leaves no trace. This places the friction where it
belongs: on deliberate rule modification, not on runtime execution.

The inference warning (`--acknowledge-not-bulk-edit`) is the exception to this
rule and is deliberately advisory, because it fires when `change_mode` is
**not** set — i.e., the mission may not be a bulk edit at all, and a blocking
false positive in that path is worse than a bypassable false positive.

## Consequences

### Positive

- Missions that describe bulk edits cannot begin implementation without an
  explicit, per-category classification decision.
- High-risk surfaces (serialized keys, CLI commands, telemetry labels) that
  would silently break under mechanical rename are protected by default.
- The 8 standard categories force the author to consider every risk surface,
  even ones they would not have thought to check (`logs_telemetry` is a
  common blind spot).
- Doctrine extensibility is preserved — the feature uses existing mechanisms
  (directive + tactic, mission_v1 guard, expected-artifacts manifest) without
  adding new infrastructure.
- The skill-driven activation model lets the guardrail protect users who
  have no knowledge of its existence. The feature scales to new contributors
  without training.
- The diff-compliance gate at review time is independent of the implement-time
  gate and provides a second check: implementation happened, did it stay
  within the classified surfaces?
- The audit trail is strong. Every exception in the occurrence map carries a
  `reason:` string. Any loosening of a `do_not_change` rule is visible in
  git history.

### Negative

- Path-heuristic classification is imperfect. A `.json` file carrying
  translation keys is treated identically to a `.json` file carrying API
  schema. Authors must use exceptions to distinguish — real friction when the
  repo's file conventions are not aligned with the heuristic's assumptions.
- Unclassified file types (`.graphql`, `.proto`, `.prisma`, `.sol`,
  domain-specific formats) block review until the author adds an explicit
  exception. This is intentional (FR-008) but adds setup cost for repos with
  unusual file types.
- The 8-category requirement forces authors to classify categories that may
  not apply to their specific rename (e.g., a UI-only change still has to
  declare `logs_telemetry: do_not_change`). This is a deliberate tradeoff —
  silent whitelisting of risk surfaces was the bug we were fixing.
- The guardrail only fires when the agent correctly detects bulk-edit intent
  during specify/plan. An agent that mis-classifies intent produces a
  false-negative silent rename exactly as before. The inference warning is
  the backstop but is advisory only.
- No cryptographic freezing of the occurrence map. An agent that edits the
  map mid-WP to exception-away a violation will pass the gate, and only
  careful reviewer attention to map-history diffs will catch it. Future
  hardening can add map-timestamp comparison.
- Exceptions are not required to carry a `reason`. A well-meaning agent can
  add `{ path: "foo", action: rename }` with no justification. Future
  hardening can require non-empty reasons.

### Neutral

- Review cycle time on bulk-edit missions is slightly longer because of the
  additional diff-classification step. Negligible (< 1s on realistic diffs).
- Missions without `change_mode: bulk_edit` experience zero additional gates
  or delays. NFR-005.

## Implementation Notes

- Directive: `src/doctrine/directives/shipped/035-bulk-edit-occurrence-classification.directive.yaml`
- Tactic: `src/doctrine/tactics/built-in/occurrence-classification-workflow.tactic.yaml`
- Skill: `src/doctrine/skills/spec-kitty-bulk-edit-classification/SKILL.md`
- Mission metadata field: `change_mode` (optional, valid values: `"bulk_edit"`)
  in `MissionMetaOptional` TypedDict.
- Artifact: `kitty-specs/<mission>/occurrence_map.yaml` with required
  `target`, `categories` (all 8 standard names), and optional `exceptions`
  and `status` sections.
- Gate function: `specify_cli.bulk_edit.gate.ensure_occurrence_classification_ready`
  is invoked from `cli/commands/implement.py` and `cli/commands/agent/workflow.py`.
- Diff checker: `specify_cli.bulk_edit.diff_check.check_diff_compliance`
  is invoked from the review path after artifact admissibility passes.
- Inference warning: `specify_cli.bulk_edit.inference.scan_spec_file`
  fires in the implement command when `change_mode` is not set and spec
  content scores >= 4 against weighted keyword patterns.
- Command template triggers: `specify.md` and `plan.md` under
  `src/specify_cli/missions/software-dev/command-templates/` point agents to
  the skill at the relevant phase boundaries.
- Guard registration: `occurrence_map_complete` in
  `specify_cli.mission_v1.guards.GUARD_REGISTRY` provides a declarative hook
  for future mission configs to reference the check from a state-machine
  transition. The primary enforcement path is the direct function call from
  the CLI commands, not the guard primitive.

## Related Decisions and References

- Issue: [Priivacy-ai/spec-kitty#393](https://github.com/Priivacy-ai/spec-kitty/issues/393)
- Parent: [#391 Tech Debt Remediation](https://github.com/Priivacy-ai/spec-kitty/issues/391)
- Mission dir: `kitty-specs/bulk-edit-occurrence-classification-guardrail-01KP423X/`
- Mission review report: `kitty-specs/bulk-edit-occurrence-classification-guardrail-01KP423X/mission-review.md`
- Related directive: `DIRECTIVE_035`
- Related tactic: `occurrence-classification-workflow`
- Related skill: `spec-kitty-bulk-edit-classification`
- Related ADR: none (first guardrail of this shape in spec-kitty)

## Follow-On Work

Documented but deferred:

- Map-history attestation: compare occurrence map at first-WP-implement time
  vs. at review time, flag any loosening of `do_not_change` rules.
- Per-exception `reason:` enforcement in the schema.
- Full semantic diff classification (Option D) for repos where file-level
  path heuristics produce too many false positives or negatives.
- Promote the guard to a first-class workflow step (Option A) if dashboard
  visibility of classification status becomes a user need.
- Extend path heuristics to domain-specific file types (`.graphql`, `.proto`,
  `.prisma`, `.sol`) once usage patterns emerge.
