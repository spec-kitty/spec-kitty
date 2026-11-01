---
title: 'Gap Analysis: Migrating Spec-Kitty to the Installation-Link-Mapping-Override Connector Model'
description: Draft gap analysis for migrating spec-kitty and spec-kitty-saas to the installation-link-mapping-override connector model, scoped against the separation ADR.
doc_status: superseded
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/adr/3.x/2026-04-06-2-connector-auth-binding-separation.md
---
# Gap Analysis: Migrating Spec-Kitty to the Installation-Link-Mapping-Override Connector Model

> **Point-in-time record (2026-03-10).** Kept for history; not maintained. It measures
> gaps against the pre-convergence code, including the `sync` tree that has since been
> deleted. The decisions it fed are the two connector ADRs:
> [auth/binding separation](../../adr/3.x/2026-04-06-2-connector-auth-binding-separation.md)
> and [GitHub App installation authority](../../adr/3.x/2026-04-06-3-github-app-installation-authority.md).

**Status**: Draft
**Date**: 2026-03-10
**Scope**: `spec-kitty-saas`, `spec-kitty` CLI
**Related ADR**: [Connector Installation, User Link, and Resource Mapping Separation](../../adr/3.x/2026-04-06-2-connector-auth-binding-separation.md)
**Related PRD**: `prd-connector-auth-first-team-binding-v1.md` in the planning repo

## Executive Summary

Spec-Kitty does **not** currently implement a connector model that can be cleanly re-skinned into "workspace installation first" with minor UI changes. The existing software is structurally centered on **project-scoped bindings**.

The current system has two partially overlapping connector architectures:

1. `ConnectorBinding`: legacy webhook/OAuth connector model with secrets and OAuth credentials stored directly on a project binding
2. `IssueTrackerBinding` + `UserProviderConnection`: newer tracker model that separates per-user auth somewhat, but still anchors auth and routing to a project binding

The largest migration gaps are:

1. There is no workspace-level installation root object
2. Webhook routing is addressed by `binding_uuid`, not by installation plus resource mapping
3. Nango connection IDs and auth webhooks are keyed to project binding identity
4. Tracker ingest and egress APIs auto-create or resolve `IssueTrackerBinding` directly
5. The CLI already emits `repo_slug`, but the SaaS does not materialize repo identity into build read models that can power Git repo auto-mapping

The good news is that some foundations are reusable:

1. `Team` already works as the v1 workspace boundary
2. Invite and membership flows are already usable for workspace onboarding
3. `PreAuthSession` is conceptually reusable if retargeted from "binding creation" to "installation/link completion"
4. The CLI already emits the key Git correlation signals needed for repo auto-suggestion

## Target Model Recap

The target connector model is:

1. `TeamServiceInstallation`
   Workspace-level provider installation or admin-authorized connection
2. `UserServiceLink`
   Optional member-level identity link to an installation
3. `ServiceResourceMapping`
   Explicit mapping from external resource to project or feed
4. `ProjectServicePolicyOverride`
   Optional project-level doctrine and routing exceptions

GitHub and GitLab may auto-suggest mappings from Git signals, but the source of truth remains the explicit mapping record.

## Current Software Snapshot

### 1. Tenancy and membership

Current state:

- `Team` is the only tenant container in the SaaS
- users join via membership and invitation flows
- default-team creation already exists for first-time signup

Relevant code:

- `spec-kitty-saas/apps/teams/models.py`
- `spec-kitty-saas/apps/teams/helpers.py`
- `spec-kitty-saas/apps/teams/forms.py`

Assessment:

- This is compatible with the proposed v1 model
- "workspace" can map to the existing `Team` object without structural change
- No squad/sub-team hierarchy exists yet, so installation and mapping must live on `Team` for now

Gap severity: Low

### 2. Connector domain model

Current state:

- `ConnectorBinding` is explicitly defined as a project-scoped external connector binding
- it stores webhook secret, OAuth tokens, provider account metadata, lifecycle state, and health on the same project record
- `IssueTrackerBinding` is also project-scoped
- `UserProviderConnection` is per-user, but only in relation to one tracker binding
- `PreAuthSession` is user/team-scoped but still points to `IssueTrackerBinding`

Relevant code:

- `spec-kitty-saas/apps/connectors/models.py`

Assessment:

- The current data model does not have a stable root object equivalent to `TeamServiceInstallation`
- auth state, routing state, and project policy are still collapsed into binding-centric records
- most downstream tracker records point at `IssueTrackerBinding`, which means the binding abstraction is pervasive

Gap severity: Critical

### 3. URL and endpoint structure

Current state:

- connector URLs are binding-oriented:
  - `/<connector_type>/create/`
  - `/<connector_type>/oauth/start/`
  - `/<connector_type>/<binding_uuid>/...`
- tracker URLs are binding-oriented:
  - `/trackers/create/`
  - `/trackers/<binding_id>/...`
- GitHub webhook entrypoint is `/api/v1/webhooks/github/<binding_uuid>/`

Relevant code:

- `spec-kitty-saas/apps/connectors/urls.py`

Assessment:

- there is no installation detail page, resource mapping page, or override surface
- the external webhook contract itself assumes "webhook URL equals project binding"

Gap severity: High

### 4. OAuth onboarding flow

Current state:

- generic OAuth start requires `project`
- GitHub OAuth start also requires `repo_full_name`
- callback consumes state with `team_id`, `project_id`, and `repo_full_name`
- callback creates or updates a `ConnectorBinding`
- OAuth credentials are persisted directly on that binding

Relevant code:

- `spec-kitty-saas/apps/connectors/views.py`

Assessment:

- this is the opposite of installation-first onboarding
- the first act of consent creates project routing and auth state simultaneously
- reauth is also binding-specific instead of installation-specific

Gap severity: Critical

### 5. Tracker onboarding flow

Current state:

- issue tracker creation starts by choosing a project and provider
- OAuth providers require a `PreAuthSession`
- final submission creates `IssueTrackerBinding`
- if OAuth was used, it also creates `UserProviderConnection(binding, user)`
- wizard steps are `Select -> Authenticate -> Workspace -> Configure`, but "Select" means project first

Relevant code:

- `spec-kitty-saas/apps/connectors/views.py`
- `spec-kitty-saas/templates/web/connectors/tracker_binding_create.html`
- `spec-kitty-saas/templates/web/connectors/components/binding_step_project.html`

Assessment:

- the tracker system has useful ideas, but the root is still wrong
- workspace discovery exists, but the discovered workspace is immediately bound to a project rather than to a workspace installation
- user auth is still modeled as a property of one binding, not of the installation

Gap severity: Critical

### 6. Nango control plane identity

Current state:

- Nango per-user connection IDs are built from:
  - `team_id`
  - `project_uuid`
  - `provider`
  - `binding_id`
  - `user_id`
- pre-auth IDs are generated per team/provider/user and later attached to a binding
- tracker OAuth session creation ensures a `UserProviderConnection` exists for a specific binding

Relevant code:

- `spec-kitty-saas/apps/connectors/nango.py`
- `spec-kitty-saas/apps/connectors/views.py`

Assessment:

- connection identity is binding-centric all the way down
- the current control-plane identifier scheme cannot express "this user linked to the workspace installation" without inventing a fake binding
- any migration will need a new Nango connection ID contract and compatibility plan for old connections

Gap severity: Critical

### 7. Webhook routing and event emission

Current state:

- GitHub webhook requests resolve exactly one `ConnectorBinding` by `binding_uuid`
- the request is HMAC-validated with that binding's secret
- payload repository must exactly equal `binding.repo_full_name`
- handlers emit project events directly from `binding.project`

Relevant code:

- `spec-kitty-saas/apps/connectors/views.py`
- `spec-kitty-saas/apps/connectors/handlers.py`

Assessment:

- webhook routing is currently "pre-routed" by URL plus one repo equality check
- there is no lookup path for "installation sees repo X, mapping routes repo X to project Y"
- GitHub/GitLab cannot move to installation-first without redesigning webhook endpoints, secrets, replay, idempotency, and event payload conventions

Gap severity: Critical

### 8. Tracker ingest and egress APIs

Current state:

- tracker snapshot ingest resolves a project first
- the payload must include `provider` and `workspace`
- the API `update_or_create`s an `IssueTrackerBinding`
- tracker status egress also resolves by `(team, project, provider, workspace)`
- downstream records such as `WorkPackageTrackerLink`, `TrackerSyncRun`, `TrackerDrift`, `TrackerSnapshotReceipt`, `ConnectorOperationLog`, and `ConnectorDeadLetterItem` all refer to a binding

Relevant code:

- `spec-kitty-saas/apps/connectors/views.py`
- `spec-kitty-saas/apps/connectors/models.py`

Assessment:

- tracker synchronization is deeply bound to project binding identity
- the current ingest path treats tracker binding creation as a side effect of receiving snapshot data
- this is incompatible with explicit installation and mapping records being authoritative

Gap severity: Critical

### 9. Git signal persistence and repo auto-suggestion

Current state:

- the CLI resolves and emits:
  - `git_branch`
  - `head_commit_sha`
  - `repo_slug`
- SaaS `Event` ingestion stores the event envelope and payload
- `Build` persists `branch` and `head_commit`
- `BuildCommitSnapshot` persists commit graph snapshots
- no build-level or commit-level read model stores `repo_slug`, remote URL identity, or a provider repo identifier

Relevant code:

- `spec-kitty/src/specify_cli/sync/git_metadata.py`
- `spec-kitty/src/specify_cli/sync/emitter.py`
- `spec-kitty-saas/apps/sync/models.py`
- `spec-kitty-saas/apps/sync/materialize.py`

Assessment:

- the CLI contract is already good enough to support repo auto-suggestion
- the SaaS currently drops the most important provider identity field for that use case
- explicit repo mappings can be introduced without changing the CLI event shape, but only after the SaaS materializes and indexes repo identity

Gap severity: High

### 10. UI and information architecture

Current state:

- the Connectors page is a binding index
- generic connector create form starts with `Project`
- issue tracker wizard starts with `Project`
- details pages are centered on a single binding
- the list is split between "Webhook / OAuth Connectors" and "Issue Trackers"

Relevant code:

- `spec-kitty-saas/templates/web/connectors/binding_list.html`
- `spec-kitty-saas/templates/web/connectors/binding_create.html`
- `spec-kitty-saas/templates/web/connectors/tracker_binding_create.html`
- `spec-kitty-saas/templates/web/connectors/binding_detail.html`
- `spec-kitty-saas/templates/web/connectors/tracker_binding_detail.html`

Assessment:

- the current information architecture teaches the wrong mental model
- the UI is not simply missing a page; it is shaped around the wrong primary object

Gap severity: High

### 11. Tests and operational assumptions

Current state:

- onboarding tests assume OAuth start requires `project`
- callback tests assert `ConnectorBinding` creation
- webhook tests assume binding-specific webhook URLs and exact repo match
- provider parity tests treat GitHub, GitLab, Slack, Jira, and Linear as the same binding shape

Relevant code:

- `spec-kitty-saas/apps/connectors/tests/test_oauth_onboarding.py`
- `spec-kitty-saas/apps/connectors/tests/test_views.py`

Assessment:

- a large portion of the test suite encodes the current domain model
- migration success will require intentionally rewriting tests, not patching them

Gap severity: High

## Gap Matrix

| Area | Current State | Target State | Gap Severity | Notes |
|------|---------------|--------------|--------------|-------|
| Team/workspace boundary | `Team` exists, invites exist | `Team` acts as workspace | Low | Reusable as-is for v1 |
| Installation root | None | `TeamServiceInstallation` | Critical | Foundational missing object |
| User link | Tied to `IssueTrackerBinding` | `UserServiceLink` tied to installation | Critical | Current auth graph is too narrow |
| Resource mapping | Implicit in bindings | Explicit `ServiceResourceMapping` | Critical | Needed for all providers |
| Project override | Stored on tracker binding | Optional `ProjectServicePolicyOverride` | High | Must split default vs exception policy |
| OAuth start/callback | Project-first, binding-creating | Installation-first, link later | Critical | Current flows create wrong object |
| Nango connection IDs | Binding/user/project keyed | Installation/user keyed | Critical | Requires compatibility strategy |
| GitHub webhooks | `binding_uuid` endpoint | Installation endpoint + mapping lookup | Critical | Biggest external contract break |
| Tracker ingest/egress | Binding auto-create/lookup | Installation + mapping + override | Critical | Deep pipeline dependency |
| Git auto-suggestion | CLI emits signals, SaaS drops repo identity | Persist repo identity and confidence | High | Good opportunity with limited CLI churn |
| Connectors UI | Binding list and binding forms | Installation hub + mapping tables | High | Product and code change |
| Tests | Binding-first assertions | Installation-first assertions | High | Rewrite expected |

## What Can Be Reused

### Reusable with minor adaptation

1. `Team`, memberships, and invitations
2. `PreAuthSession` as a temporary auth session primitive
3. parts of `UserProviderConnection` health fields and refresh telemetry
4. tracker operation logs, dead-letter handling, and sync-run telemetry patterns
5. CLI git metadata extraction and event emission

### Reusable only after retargeting foreign keys

1. `WorkPackageTrackerLink`
2. `TrackerSyncRun`
3. `TrackerDrift`
4. `TrackerSnapshotReceipt`
5. `ConnectorOperationLog`
6. `ConnectorDeadLetterItem`

These likely need to point to a mapping and installation combination rather than to `IssueTrackerBinding`.

### Not reusable as the long-term root abstraction

1. `ConnectorBinding`
2. `IssueTrackerBinding`
3. binding-specific webhook URLs
4. binding-specific OAuth callback semantics

## Recommended Migration Strategy

### Wave 1: Add new canonical models without deleting old ones

Build and migrate:

1. `TeamServiceInstallation`
2. `UserServiceLink`
3. `ServiceResourceMapping`
4. `ProjectServicePolicyOverride`

Also add:

1. installation-level lifecycle and health fields
2. mapping-level routing metadata
3. installation-level provider account identity and scopes

Goal:

- create the new canonical model graph before touching old flows

### Wave 2: Persist Git provider identity in SaaS read models

Add new persisted fields or read models for:

1. `repo_slug`
2. observed provider host if needed
3. maybe normalized `provider_resource_key`

Populate from:

1. incoming event envelope fields
2. future build materialization

Goal:

- enable GitHub/GitLab mapping suggestions before webhook contract migration

### Wave 3: Introduce installation-first UI and auth flows

Build:

1. Connectors index by installation
2. installation detail page
3. explicit mapping table per installation
4. optional "Link my account" actions per member

Change auth flows so that:

1. install/create does not require project
2. callback creates or updates `TeamServiceInstallation`
3. user-link flows create `UserServiceLink`

Goal:

- establish the correct mental model in product and code

### Wave 4: Move tracker sync to installation + mapping resolution

Refactor tracker APIs to:

1. resolve installation from provider + workspace/site identity
2. resolve resource mapping from external resource to project
3. apply optional project override

Stop:

1. auto-creating `IssueTrackerBinding` from ingest traffic

Goal:

- make the non-git provider pipeline authoritative on installations and mappings

### Wave 5: Replace binding-specific webhook routing for Git providers

Introduce:

1. installation-level Git webhook endpoint
2. repo mapping lookup
3. heuristic fallback using repo slug, commit graph, and branch signals
4. unmatched event queue for low-confidence routing

Then deprecate:

1. `github/<binding_uuid>/` webhook URLs
2. `ConnectorBinding` as the webhook authority

Goal:

- move the external contract to the new model only after mapping infrastructure exists

### Wave 6: Retire old binding-first surfaces

Remove or freeze:

1. binding-first create flows
2. binding-first detail pages
3. binding-specific OAuth token storage
4. obsolete tests

Goal:

- complete the domain migration cleanly rather than supporting two mental models indefinitely

## Risks and Blocking Questions

### 1. GitHub provider mode

Open question:

- Is the intended long-term GitHub integration OAuth app, GitHub App, or both?

Why it matters:

- installation semantics, webhook ownership, and repository permissions differ materially

### 2. Multiple installations per provider per workspace

Open question:

- Should one team be allowed to connect multiple Jira sites, multiple GitHub orgs, or both GitHub.com and GitHub Enterprise?

Why it matters:

- it changes uniqueness constraints for `TeamServiceInstallation`

### 3. Mapping destination types

Open question:

- Besides project, which first-class destinations should be supported in v1 for Slack and future connectors?

Why it matters:

- mapping schema should not have to be redesigned once notifications or incident streams are introduced

### 4. Backward compatibility for existing webhook URLs

Open question:

- Do existing GitHub bindings need a migration bridge or can they be invalidated during rollout?

Why it matters:

- this affects rollout safety, support load, and migration tooling

### 5. Ownership of tracker telemetry objects

Open question:

- Should tracker telemetry point at installation, mapping, override, or a combination?

Why it matters:

- analytics and debugging should answer both "which workspace installation failed?" and "which project mapping drifted?"

## Fastest Practical Path

If the goal is to move quickly without destabilizing the current system, the best order is:

1. add the new model graph
2. persist Git repo identity in SaaS read models
3. ship installation-first UI and auth flows
4. migrate tracker APIs to the new model
5. migrate Git webhook routing last

The wrong order would be:

1. remove the project selector
2. keep storing state on bindings
3. defer webhook and tracker model changes

That would produce nicer screens while preserving the same architectural trap.

## Bottom Line

The proposed model is achievable with the current software, but it is a **real architecture migration**, not a small refactor.

The most important implementation decision is to treat `TeamServiceInstallation` and `ServiceResourceMapping` as the new source of truth before rewriting webhook or tracker behavior. Once those exist, the rest of the migration becomes a sequence of retargeting flows. Without them, the product will continue to fight the provider-native mental model even if the UI language improves.
