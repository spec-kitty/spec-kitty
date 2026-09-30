---
title: 'Initiative: Mission Nomenclature Reconciliation'
description: Initiative operationalizing the ADR on Mission Type / Mission / Mission Run terminology, reconciling nomenclature across the codebase and docs.
doc_status: deprecated
updated: '2026-09-30'
---
# Initiative: Mission Nomenclature Reconciliation

> **Historical (2.x-era initiative, retired 2026-09-30).** Kept as a record; not a live working surface. Its wording (for example "feature" for what is now a Mission) is a legacy snapshot. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../4-0-0-milestone-roadmap.md).

This initiative operationalizes ADR
`2026-04-04-2-mission-type-mission-and-mission-run-terminology-boundary.md`.

The goal is not a blind search/replace. The goal is to make every first-party
Spec Kitty surface describe the same model:

`Mission Type -> Mission -> Mission Run`

with:

- `Feature` retained only as a software-dev compatibility alias
- `Workflow` demoted to umbrella prose
- `Step Contract` and `Procedure` kept as distinct doctrine/runtime layers

## Success Criteria

1. Canonical docs, glossary entries, architecture docs, and public website copy
   describe the same terminology model.
2. Tracked-item selectors use `mission`, blueprint selectors use
   `mission-type`, and runtime/session selectors use `mission-run`.
3. `mission_run_id` is used only for runtime/session identity.
4. `feature_slug` is either removed, dual-written as a compatibility alias, or
   explicitly marked deprecated wherever it remains.
5. `Step Contract` and `Procedure` mean the same thing in doctrine docs, CLI
   help text, prompt templates, and UI copy.

## Canonical Target Vocabulary

| Term | Canonical meaning | Notes |
|---|---|---|
| `Mission Type` | Reusable workflow blueprint | Examples: `software-dev`, `research`, `documentation` |
| `Mission` | Concrete tracked item under `kitty-specs/<slug>/` | Generic tracked-item noun across all mission types |
| `Mission Run` | Runtime/session instance | Runtime-only; never a synonym for the tracked mission |
| `Work Package` | Planning/review slice inside a mission | `WPxx` artifacts and status |
| `Mission Action` | Outer lifecycle action | `specify`, `plan`, `implement`, `review`, etc. |
| `Step Contract` | Structured contract for one mission action | Internal decomposition of an action |
| `Procedure` | Reusable doctrine subworkflow | Delegated to by a step contract |
| `Feature` | Compatibility alias for a software-dev mission | Not canonical product language |
| `Workflow` | Umbrella prose only | Replace with specific nouns in technical surfaces |

## Scope by Property

This initiative covers all first-party Spec Kitty properties in the current
workspace that either expose product language or consume CLI/API/runtime
contracts.

| Property | Primary surface types | Required outcome |
|---|---|---|
| `spec-kitty` | Core CLI, runtime, events, dashboard, docs, glossary, skills | Canonical source rollout |
| `Spec-Kitty-Website` | Public website, marketing copy, docs entrypoints | Public model matches ADR |
| `spec-kitty-saas` | SaaS onboarding, UI labels, dashboards, API consumers | UI and product text align with core |
| `spec-kitty-hub` | Shared UI and integration surfaces | Shared terminology model |
| `spec-kitty-tracker` | Tracker-facing UX and status copy | Mission terminology, compat where needed |
| `spec-kitty-orchestrator` | Provider-side orchestration UX and API usage | Contract names/versioning aligned |
| `spec-kitty-runtime` | Runtime library and typed models | `mission run` reserved for runtime |
| `spec-kitty-events` | Event schemas, projections, event docs | Canonical field naming and alias strategy |
| `spec-kitty-mobile*` | Mobile onboarding/help surfaces | Public language matches core |
| `spec-kitty-end-to-end-testing`, `spec-kitty-plain-english-tests` | Fixtures, transcripts, golden outputs | Regression coverage updated |

## Workstreams

### 1. Policy and Glossary Lock

Goal: make the ADR and glossary the uncontested source of truth before any code
rename proceeds.

Tasks:
- Update `docs/context/orchestration.md` to match the ADR exactly.
- Update `glossary/historical-terms.md` so `Feature` is marked as a
  compatibility alias, not a co-equal current term.
- Add or update glossary entries for `Mission Type`, `Mission Action`,
  `Step Contract`, and `Procedure` where needed.
- Add one short glossary note that `workflow` is generic prose, not a primary
  domain object.
- Update architecture and explanation docs that currently mix
  `Mission`, `Feature`, and `Mission Run`.

Representative files:
- `docs/context/orchestration.md`
- `docs/context/charter.md`
- `docs/context/identity.md`
- `glossary/historical-terms.md`
- `docs/2x/runtime-and-missions.md`
- `docs/architecture/mission-system.md`

Acceptance gate:
- No glossary entry defines `Mission Run` as the tracked item.
- No canonical doc uses `Mission` to mean reusable blueprint without the word
  `Type`.

### 2. Core CLI Taxonomy

Goal: make flags, command groups, help text, error messages, and examples obey
the ADR.

Canonical selector policy:
- `--mission-type` = reusable blueprint selector
- `--mission` = tracked mission selector
- `--mission-run` = runtime/session selector only
- `--feature` = compatibility alias for `--mission` on software-dev legacy
  surfaces

Tasks:
- Audit command groups that currently use `mission-run` for tracked missions.
- Introduce canonical tracked-mission help text and examples.
- Mark legacy `feature` wrappers and legacy `mission-run` tracked-item wrappers
  as compatibility surfaces.
- Update autogenerated or hand-authored CLI docs to stop teaching the wrong
  nouns.
- Decide whether `agent workflow` remains a command name as compatibility
  veneer or is replaced by a more precise surface such as `agent mission`.

Representative files:
- `src/specify_cli/cli/commands/agent/mission_run.py`
- `src/specify_cli/cli/commands/agent/feature.py`
- `src/specify_cli/cli/commands/agent/workflow.py`
- `src/specify_cli/cli/commands/mission_type.py`
- `src/specify_cli/cli/commands/implement.py`
- `docs/api/cli-commands.md`
- `docs/api/agent-subcommands.md`

Acceptance gate:
- No canonical help text says `--mission-run` selects `kitty-specs/<slug>/`.
- `--mission-type` is the documented primary selector for blueprint choice.

### 3. Runtime, Events, and API Contracts

Goal: separate tracked mission identity from runtime/session identity in every
machine-facing contract.

Tasks:
- Inventory every public JSON field carrying tracked-item identity.
- Introduce `mission_slug` as the canonical tracked-item field where absent.
- Dual-write `feature_slug` only where needed for compatibility.
- Reserve `mission_run_id` for runtime/session state only.
- Decide whether orchestrator API commands and payloads need versioned aliases
  (`mission-state`, `accept-mission`, `merge-mission`) or a staged
  deprecation layer.
- Update event-envelope and state-contract docs to explain the alias window.

Representative files:
- `src/specify_cli/next/runtime_bridge.py`
- `src/specify_cli/context/models.py`
- `src/specify_cli/state_contract.py`
- `src/specify_cli/orchestrator_api/commands.py`
- `docs/api/orchestrator-api.md`
- `docs/api/event-envelope.md`
- `docs/status-model.md`

Acceptance gate:
- `mission_run_id` never aliases a mission slug.
- Every public payload that identifies a tracked mission documents
  `mission_slug` as canonical.

### 4. Dashboard and Product UI Surfaces

Goal: make user-visible UI labels, navigation, badges, filters, empty states,
and notifications use the canonical terminology.

Tasks:
- Audit dashboard labels such as `currentFeature`, feature tabs, accept/merge
  flows, and activity log strings.
- Update mission-type selectors in onboarding and creation flows.
- Ensure software-dev specific surfaces can still say `feature` where that is
  domain-natural, but only as a subtype/example of mission.
- Review screenshots, onboarding callouts, and empty-state guidance so public
  language matches the model.

Representative surfaces:
- `src/specify_cli/dashboard/static/dashboard/dashboard.js`
- SaaS dashboards and onboarding in `spec-kitty-saas`
- Tracker and hub surfaces in `spec-kitty-tracker` and `spec-kitty-hub`

Acceptance gate:
- Generic UI copy says `Mission` unless the context is explicitly
  software-delivery-specific.
- No dashboard label uses `Mission Run` for the tracked item.

### 5. Docs, Skills, Prompt Templates, and Tutorials

Goal: fix the highest-volume repetition surfaces that currently teach the wrong
model back to users and agents.

Tasks:
- Update all docs that explain the hierarchy.
- Update skills under `.agents/`, `.claude/`, and `src/doctrine/skills/`.
- Update command templates under `src/doctrine/missions/*/command-templates/`.
- Update public tutorials, how-to guides, and quickstart snippets.
- Add a terminology migration note to the docs site so users understand what is
  canonical vs compatibility.

Representative files:
- `src/doctrine/skills/spec-kitty-mission-system/SKILL.md`
- `src/doctrine/skills/spec-kitty-runtime-next/SKILL.md`
- `src/doctrine/skills/spec-kitty-charter-doctrine/SKILL.md`
- `docs/api/missions.md`
- `docs/architecture/runtime-loop.md`
- `docs/guides/*`
- `.agents/skills/**`
- `.claude/skills/**`

Acceptance gate:
- Mission-system docs, runtime docs, and glossary all describe the same
  hierarchy.
- No tutorial teaches `mission run` as the tracked item.

### 6. Public Website and Marketing Language

Goal: make the public story match the product model without sacrificing plain
English clarity.

Rules:
- Use `Mission` as the generic product noun.
- Use `Mission Type` when describing reusable workflows.
- Use `Feature` only as an example outcome within `software-dev`.
- Avoid `Mission Run` in marketing except where explaining runtime/session
  internals for technical audiences.

Tasks:
- Update homepage/product pages/feature lists.
- Update diagrams, screenshots, captions, alt text, and hero copy.
- Update docs entry copy and SEO meta descriptions where terminology currently
  implies `Feature` is the generic tracked item.

Primary property:
- `Spec-Kitty-Website`

Acceptance gate:
- A new reader can understand the model from the website without reading the
  glossary.

### 7. Sister Repo Reconciliation

Goal: align non-core repositories that parse, render, or echo Spec Kitty terms.

Tasks by repo category:
- `spec-kitty-runtime`, `spec-kitty-events`: field names, schema comments,
  event docs, generated clients.
- `spec-kitty-orchestrator`: provider-side command invocation, contract docs,
  CLI examples, dashboard strings.
- `spec-kitty-saas`, `spec-kitty-hub`, `spec-kitty-tracker`: onboarding,
  workflow copy, labels, filters, analytics dimensions.
- `spec-kitty-mobile*`: mobile help text, onboarding, and glossary snippets.
- Test repos: golden transcripts, plain-English expectations, fixture slugs,
  and E2E assertions.

Acceptance gate:
- No first-party property teaches a contradictory hierarchy.

### 8. Compatibility, Deprecation, and Release Management

Goal: sequence the migration without causing silent breakage.

Tasks:
- Publish an explicit compatibility matrix for flags, fields, and command
  groups.
- Add deprecation warnings where legacy selectors remain accepted.
- Define removal criteria for `feature` primary surfaces and
  `mission-run` tracked-item selectors.
- Version public API changes where payload field names change.
- Add regression tests for legacy aliases during the deprecation window.

Acceptance gate:
- Users can follow canonical docs immediately.
- Legacy automation receives explicit warnings, not silent behavior changes.

## Rollout Sequence

### Phase 0: Freeze the Lexicon

Deliverables:
- ADR accepted
- Initiative published
- Search inventory captured

No code/API renames should proceed before this phase is merged.

### Phase 1: Canonical Docs and Glossary

Deliverables:
- Glossary and architecture docs updated
- `spec-kitty` docs site updated
- Skills and doctrine docs updated

This phase changes the language people read first.

### Phase 2: Core CLI and Runtime Contracts

Deliverables:
- Canonical selectors and help text updated
- Runtime/session naming separated from tracked-item naming
- Event/API alias strategy implemented

This phase changes what developers and automation call.

### Phase 3: UI and Dashboard Surfaces

Deliverables:
- Core dashboard copy updated
- SaaS/hub/tracker product UIs updated
- Screenshots and support text refreshed

This phase changes what users see while operating the product.

### Phase 4: External Properties and Public Website

Deliverables:
- Public website copy updated
- Marketing diagrams updated
- Orchestrator/provider docs updated

This phase changes what prospects and integrators learn.

### Phase 5: Deprecation Burn-Down

Deliverables:
- Legacy aliases reduced to a documented allowlist
- Removal plan published
- Metrics collected on legacy command/field usage

This phase retires the old language safely.

## Search and Audit Checklist

Use this checklist in every property before editing:

- Search for `mission run` used to mean tracked item.
- Search for `--mission-run` used to select `kitty-specs/<slug>/`.
- Search for `--mission` used to mean mission type without a compatibility note.
- Search for `feature_slug` in public payloads and docs.
- Search for `feature-state`, `accept-feature`, `merge-feature`, and related
  command docs.
- Search for `workflow` where a more specific term should be used.
- Search for hierarchy diagrams that still say `Mission -> Feature` or
  `Mission -> Mission Run` incorrectly.

Suggested starting commands in each repo:

```bash
rg -n "mission run|mission-run|feature_slug|feature-state|accept-feature|merge-feature|--feature\\b|--mission\\b|--mission-run\\b|workflow"
```

## Done Definition

This initiative is complete when:

1. The glossary, ADRs, docs, and website all teach the same model.
2. The core CLI and APIs use canonical selectors/field names with explicit
   compatibility aliases.
3. No first-party property uses `Mission Run` to mean the tracked mission.
4. `Feature` appears only in software-dev-specific or explicitly deprecated
   contexts.
5. The remaining compatibility exceptions are documented in one allowlist with
   owners and removal dates.
