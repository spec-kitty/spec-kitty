---
title: Tracker Binding Context Is Discovered, Not User-Supplied
description: 'Tracker discovery returns bindable resource descriptors and the hosted service owns resolution, so operators stop hand-typing project slugs at bind time.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-04'
---

## Context and Problem Statement

Spec Kitty already models tracker routing as:

1. a team-level installation,
2. optional user links,
3. an explicit resource mapping from an external resource to a Spec Kitty
   project,
4. runtime resolution from local project context to the mapped external resource.

That architecture is sound, but the current bind and discovery surfaces are too
lossy.

Today:

1. the CLI still asks for bind-time metadata such as `project_slug`,
2. the tracker discovery layer collapses provider-native machine identity into
   generic `resource_id` and `resource_label` fields,
3. provider-specific connector construction still depends on raw identifiers such
   as Linear `team_id`, Jira `project_key`, GitHub `owner/repo`, and GitLab
   `project_id`,
4. the user experience therefore drifts toward asking humans for tracker-native
   metadata that the system can usually discover itself.

This is the wrong architectural seam.

For SaaS-backed providers, users should connect an installation and then bind a
local Spec Kitty project to one of the resources discoverable under that
installation. They should not need to know or type machine metadata such as
team keys, project keys, repo paths, numeric IDs, or future Azure DevOps
coordinates.

## Decision Drivers

* **No raw metadata prompts in the normal path** — the system should not ask the
  user for tracker-native identifiers it can enumerate itself.
* **Provider-native routing** — discovered resources must preserve the machine
  identity needed to build hosted connectors correctly.
* **Cross-provider consistency** — Jira, Linear, GitHub, GitLab, and future
  providers should follow one binding model, not bespoke per-provider rituals.
* **Host-owned routing boundary** — binding and mapping resolution belong in the
  host control plane, not in prompt folklore or user memory.
* **Extensibility** — Azure DevOps and other trackers should fit the same
  discovery and binding contract without redefining the architecture.

## Considered Options

* **Option 1:** Continue requiring manual provider metadata during bind
* **Option 2:** Implement separate bind contracts for each provider
* **Option 3:** Standardize on discovered binding context with host-resolved binding

## Decision Outcome

**Chosen option: Option 3**, because the system already has the right routing
model and now needs a single authoritative way to discover, preserve, and
resolve tracker resource identity.

### Core Decision

1. Tracker discovery MUST return bindable resource descriptors that preserve:
   1. a stable resource reference,
   2. human display labels,
   3. provider-native connector parameters,
   4. provider-specific routing metadata.
2. `spec-kitty-saas` MUST be authoritative for:
   1. installation inventory,
   2. resource inventory within an installation,
   3. resolution from local Spec Kitty project identity to an existing mapping or
      candidate bind target.
3. `spec-kitty` CLI MUST derive local project identity and bind through resolved
   host context rather than requiring manual raw provider metadata in the normal
   SaaS bind path.
4. Local tracker config SHOULD persist a stable binding reference returned by the
   host control plane. Human-readable slugs may be cached for display or
   backward compatibility, but they are not the primary binding primitive.
5. `ServiceResourceMapping.routing_metadata` or its successor MUST be treated as
   the canonical place for provider-specific routing metadata that is needed
   after binding.
6. When binding is ambiguous, the user MAY choose among discovered labeled
   resources. The system MUST NOT ask the user to type raw tracker-native machine
   metadata unless discovery is unavailable and the workflow is explicitly in a
   repair/admin fallback mode.

### Provider Interpretation Rule

Different providers expose different routing units:

1. Jira: project under site
2. Linear: team or project-like routing unit under workspace
3. GitHub: repository under organization/account installation
4. GitLab: project under group/namespace
5. Azure DevOps: project and possibly team under organization

This ADR does not force identical provider nouns. It forces a shared contract:
every provider must expose a bindable resource descriptor with enough data to
route correctly without asking the user for hidden machine identity.

## Consequences

### Positive

* Binding becomes a discovery and selection workflow instead of a memory test.
* Runtime connector construction can rely on stored provider metadata instead of
  reconstructing it from brittle assumptions.
* New providers can plug into one model.
* Existing SaaS mapping architecture becomes usable from the CLI without leaking
  provider internals to the user.

### Negative

* Discovery contracts in `spec-kitty-tracker` become richer and more opinionated.
* `spec-kitty-saas` must expose new API surfaces for resource inventory and bind
  resolution.
* `spec-kitty` must support config migration or backward-compatible dual-read for
  older `project_slug`-only bindings.

### Neutral

* Users may still need to choose among multiple discovered resources, but that
  choice is made from labeled options rather than typed metadata.
* Raw provider metadata still exists internally; it is simply moved behind
  discovery, mapping, and routing contracts.

### Confirmation

This decision is validated when:

1. a normal SaaS-backed `tracker bind` flow can complete without the user typing
   a tracker-native key, prefix, repo path, or numeric ID,
2. each supported provider exposes enough discovered metadata to construct its
   hosted connector without secondary human input,
3. existing mappings can be enumerated and selected before a local bind exists,
4. the same binding contract can accommodate a newly added provider such as
   Azure DevOps without reopening the architectural question.

## Pros and Cons of the Options

### Option 1: Continue manual provider metadata

Keep the current model where bind-time CLI or dashboard flows ask for project
keys, team identifiers, repo coordinates, or similar raw metadata.

**Pros:**

* Lowest short-term implementation cost.
* Minimal change to current contracts.

**Cons:**

* Makes the user do discovery work the system can already do.
* Produces provider-specific UX leakage.
* Does not scale cleanly to more providers.

### Option 2: Separate bind contracts per provider

Create a custom bind flow for each tracker with its own payloads and local config
shape.

**Pros:**

* Can optimize each provider independently.
* Easy to ship tactical fixes quickly.

**Cons:**

* Fragments the architecture.
* Forces repeated logic across CLI, SaaS, and tracker library layers.
* Makes future providers slower and riskier to add.

### Option 3: Discovered binding context with host resolution

Use a shared discovery contract, preserve provider-native machine identity, and
let the host resolve local project identity into mappings or bind candidates.

**Pros:**

* Aligns with existing installation/link/mapping architecture.
* Eliminates most raw metadata prompts.
* Creates one reusable seam for all current and future providers.

**Cons:**

* Requires coordinated changes across three repositories.
* Needs disciplined contract design so the generic model does not become vague.

## More Information

**Related ADRs:**

* `2026-02-11-5-task-tracker-agnostic-connector-architecture.md`
* `2026-02-27-2-host-owned-tracker-persistence-boundary.md`
* `2026-02-27-3-saas-tracker-integration-via-existing-connectors-journey.md`
* `architecture/adrs/2026-03-09-1-prompts-do-not-discover-context-commands-do.md`

**Current seams this ADR is intended to tighten:**

* `spec-kitty-tracker/src/spec_kitty_tracker/resource_discovery.py`
* `spec-kitty-tracker/src/spec_kitty_tracker/workspace_discovery.py`
* `spec-kitty/src/specify_cli/tracker/config.py`
* `spec-kitty/src/specify_cli/tracker/saas_client.py`
* `spec-kitty/src/specify_cli/cli/commands/tracker.py`
* `spec-kitty-saas/apps/connectors/models.py`
* `spec-kitty-saas/apps/connectors/tracker_views.py`
* `spec-kitty-saas/apps/connectors/runtime_policy.py`
