---
title: Mission Type, Mission, and Mission Run Terminology Boundary
description: 'Separates three colliding nouns: Mission Type is the reusable blueprint, Mission is the tracked item under kitty-specs, Mission Run is the persisted runtime session.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-04'
---

## Context and Problem Statement

Spec Kitty currently carries multiple conflicting ontologies for the same set of
objects.

The main collisions are:

1. `Mission` sometimes means the reusable workflow blueprint (`software-dev`,
   `research`, `documentation`).
2. `Mission` sometimes means the concrete tracked item under
   `kitty-specs/<slug>/`.
3. `Mission Run` already exists in runtime/state code as the persisted
   execution/session instance under `.kittify/runtime/`, but parts of the
   ongoing rename effort also use `mission run` to mean the tracked item.
4. `Feature` is still the dominant tracked-item term in large parts of the
   CLI, API, dashboard, docs, tutorials, skills, and website language even
   though that noun only fits software delivery naturally.
5. `Workflow`, `phase`, `action`, `step contract`, and `procedure` are used
   interchangeably in places where they should describe different layers.

Issue [#241](https://github.com/Priivacy-ai/spec-kitty/issues/241) surfaced the
first concrete collision: `--feature` was proposed to become `--mission`, but
`--mission` already meant mission blueprint/type selection.

PR [#348](https://github.com/Priivacy-ai/spec-kitty/pull/348) moved the system
toward `mission type` and `mission run`, but the branch still leaves one
critical ambiguity unresolved: `mission run` is already a runtime/session term
in the codebase.

Epic [#364](https://github.com/Priivacy-ai/spec-kitty/issues/364) and design
spike [#367](https://github.com/Priivacy-ai/spec-kitty/issues/367) make the
deeper architectural requirement explicit: Spec Kitty needs one noun per layer,
not a rotating set of aliases.

## Decision Drivers

* **One noun, one layer** — each canonical term must name exactly one object
  in the domain model.
* **Support all mission types** — the core tracked-item term must work for
  software development, research, documentation, and future mission types.
* **Preserve runtime clarity** — runtime/session identity must remain distinct
  from planning/delivery identity.
* **Migration tractability** — existing `feature` and `mission-run`
  compatibility surfaces must be migratable without breaking every script at
  once.
* **API and event safety** — persisted fields and command flags must not reuse
  the same noun for different entities.

## Considered Options

* **Option 1:** Keep `Feature` as the canonical tracked item, use
  `Mission Type` for the blueprint, and reserve `Mission Run` for runtime.
* **Option 2:** Generalize `Mission` to the canonical tracked item, use
  `Mission Type` for the blueprint, reserve `Mission Run` for runtime/session
  instances, and keep `Feature` only as a compatibility alias for
  software-dev missions.
* **Option 3:** Use `Mission Run` as the canonical tracked item and rename the
  runtime/session concept to something else.

## Decision Outcome

**Chosen option: Option 2**, because it gives Spec Kitty one portable tracked
item noun across all mission types while preserving `mission run` for the
runtime/session layer where it already exists.

### Core Terminology Model

| Canonical term | Layer | Definition |
|---|---|---|
| `Mission Type` | Reusable blueprint | A reusable workflow definition that specifies lifecycle actions, guards, templates, artifacts, action indices, and default doctrine bindings. |
| `Mission` | Concrete tracked item | The concrete thing being planned, executed, reviewed, and integrated in a repository. Stored under `kitty-specs/<mission-slug>/`. |
| `Mission Run` | Runtime/session instance | One persisted runtime execution instance for a mission. Stored under `.kittify/runtime/` and identified by `mission_run_id`. |
| `Work Package` | Planning/review slice | One decomposed slice of work inside a mission. |
| `Mission Action` | Outer lifecycle node | A public lifecycle action such as `specify`, `plan`, `implement`, or `review`. |
| `Step Contract` | Action contract | A structured contract that decomposes one mission action into internal steps and delegation hooks. |
| `Procedure` | Reusable subworkflow | A doctrine-level reusable playbook that a step contract may delegate to. |
| `Tactic` | Technique | A smaller reusable technique applied within a procedure or step contract. |
| `Directive` | Constraint | A rule or policy that constrains behavior. |

### Specific Naming Rules

1. `Mission Type` is the only canonical name for the reusable blueprint layer.
   Use `mission type`, not plain `mission`, when the subject is
   `software-dev`, `research`, `documentation`, or another reusable template.
2. `Mission` is the only canonical name for the concrete tracked item currently
   represented by `kitty-specs/<slug>/`, `meta.json`, `tasks.md`, work package
   status, acceptance, and integration.
3. `Mission Run` is reserved exclusively for the runtime/session instance.
   It MUST NOT be used to name the tracked item, directory slug, or top-level
   planning scope.
4. `Feature` is not a canonical architecture noun anymore. It remains an
   allowed compatibility alias for a `Mission` whose `mission_type` is
   `software-dev`.
5. `Workflow` is an umbrella prose term only. It is not a primary tracked
   object. When precision matters, use `mission type`, `mission action`,
   `step contract`, or `procedure`.
6. `Phase` is allowed as explanatory prose for high-level lifecycle discussion,
   but technical contracts, APIs, events, docs, and help text should prefer
   `mission action` or `step` when referring to concrete runtime nodes.

### Command, API, and State Naming Rules

1. `--mission-type` is the canonical selector for the reusable blueprint.
2. `--mission` is the canonical selector for the concrete tracked mission.
3. `--mission-run` is reserved for runtime/session selectors only.
4. `--feature` is a compatibility alias for `--mission` on software-dev
   legacy surfaces during migration.
5. `feature_slug` is a compatibility field name only. The canonical tracked
   item identifier is `mission_slug`.
6. `mission_run_id` is the canonical runtime/session identifier and must never
   alias a tracked mission slug.

### Compatibility and Migration Policy

1. Existing user-facing and machine-facing surfaces may dual-read and dual-write
   legacy names during migration.
2. Canonical docs, glossary entries, architecture docs, and new APIs MUST use
   the terminology in this ADR immediately.
3. Compatibility aliases must be explicitly labeled as aliases or deprecated
   surfaces. They must not be presented as co-equal canonical terms.
4. `Feature` may remain in examples, tutorials, and public marketing copy only
   when the text is specifically about software delivery outcomes, not when
   describing the generic product model.

### Decision on Step Contracts and Procedures

1. `Mission Type` defines the outer lifecycle and the available mission
   actions.
2. `Step Contract` is the executable action contract for one mission action.
3. `Procedure` is a reusable doctrine playbook used by a step contract to
   supply structured guidance for part of an action.
4. A procedure is not a mission, not a mission action, and not a mission run.

### Decision on Existing Technical Artifact Names

`mission-runtime.yaml` remains an established technical filename for the
mission-type runtime DAG. It is not a `Mission Run` artifact and must not be
described that way in docs or code comments.

## Consequences

### Positive

* The tracked-item noun now works across software, research, documentation, and
  future mission types.
* Runtime/session identity stays cleanly separate from planning/delivery
  identity.
* Step contract and procedure language can be defined without overloading
  `workflow`.
* Public docs can explain the system without forcing every non-software use
  case into the word `feature`.

### Negative

* Some of PR #348's `mission-run` tracked-item naming will need to be reversed
  or deprecated.
* CLI, API, dashboard, tutorial, and website copy will all require coordinated
  updates.
* Event/API compatibility fields such as `feature_slug` will need a deprecation
  plan instead of an ad-hoc drift.

### Neutral

* Existing legacy files, commands, and docs may temporarily preserve old names
  as compatibility wrappers while the migration runs.
* Public marketing copy may still use ordinary English words like `feature`
  when describing software outcomes, so long as it does not redefine the
  product model.

### Confirmation

This decision is validated when all of the following are true:

1. No canonical doc or glossary entry uses `mission run` to mean the tracked
   mission under `kitty-specs/<slug>/`.
2. No canonical CLI help text or API contract uses `--mission-run` to select a
   tracked mission slug.
3. Runtime/state code uses `mission_run_id` only for execution/session identity.
4. The generic product model in docs and website copy says
   `Mission Type -> Mission -> Mission Run`, with `Feature` clearly marked as a
   software-dev compatibility alias.
5. `Step Contract` and `Procedure` are described consistently across doctrine,
   runtime, docs, skills, and public explanations.

## Pros and Cons of the Options

### Option 1: Keep `Feature` as the canonical tracked item

**Pros:**

* Lowest short-term migration cost.
* Matches current 2.x filesystem and many existing docs.

**Cons:**

* Makes research and documentation missions sound like software features.
* Keeps the product model biased toward one mission type.
* Leaves the broader terminology problem only partially solved.

### Option 2: Generalize `Mission` as the canonical tracked item

**Pros:**

* Gives one generic tracked-item noun across all mission types.
* Preserves `Mission Run` for runtime/session identity where it already exists.
* Makes issue #367's outer-lifecycle model easier to explain cleanly.

**Cons:**

* Requires a larger rename and compatibility program.
* Forces explicit migration rules for `feature` and `mission-run` legacy
  surfaces.

### Option 3: Use `Mission Run` as the canonical tracked item

**Pros:**

* Avoids renaming the tracked item back away from some of PR #348's current
  help text.

**Cons:**

* Directly collides with the existing runtime/session use of `mission run`.
* Forces a second rename for `mission_run_id`, runtime state, and run-index
  files.
* Makes the domain model less precise, not more.

## More Information

**Related Issues:**
* [#241](https://github.com/Priivacy-ai/spec-kitty/issues/241)
* [#364](https://github.com/Priivacy-ai/spec-kitty/issues/364)
* [#367](https://github.com/Priivacy-ai/spec-kitty/issues/367)

**Related Pull Request:**
* [#348](https://github.com/Priivacy-ai/spec-kitty/pull/348)

**Related ADRs:**
* `2026-02-17-1-canonical-next-command-runtime-loop.md`
* `2026-02-17-2-runtime-owned-mission-discovery-loading.md`
* `2026-04-03-1-execution-lanes-own-worktrees-and-mission-branches.md`
* `2026-04-03-3-feature-acceptance-runs-on-the-integrated-mission-branch.md`
