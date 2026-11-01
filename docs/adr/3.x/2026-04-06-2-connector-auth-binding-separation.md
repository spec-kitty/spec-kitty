---
title: 'ADR: Connector Installation, User Link, and Resource Mapping Separation'
description: Accepted ADR separating connector installation, user link, and resource mapping, replacing the per-binding OAuth-token storage in ConnectorBinding.
status: Accepted
date: '2026-04-06'
doc_status: active
kind: ADR
updated: '2026-04-06T00:00:00Z'
---
# ADR: Connector Installation, User Link, and Resource Mapping Separation

**Status**: Accepted
**Date**: 2026-03-10
**Author**: Spec Kitty team + Claude + Codex
**Supersedes**: Implicit design in `ConnectorBinding` where OAuth tokens are stored per-binding

## Context

The current connector models conflate multiple concerns into one record:

1. **Provider installation / workspace connection**: the act of connecting Spec-Kitty to a provider boundary such as a GitHub organization install, Jira site, Linear workspace, or Slack workspace
2. **User account linkage**: the optional association of an individual member with that provider for identity mapping, acting-as-user flows, or personal automations
3. **Resource routing**: the mapping of external resources such as repos, Jira projects, Linear teams, or Slack channels to Spec-Kitty projects or feeds
4. **Project-specific policy**: doctrine and routing overrides that only matter for exceptional projects

`ConnectorBinding` stores OAuth credentials directly on a project-scoped binding. This forces users to pick a project before they have even connected the service, which is a UX antipattern and a domain mismatch.

More importantly, the model is not provider-native:

- GitHub Apps are installed on a personal account or organization and may be scoped to selected repositories.
- Slack apps are installed to a workspace, then often configured per-channel.
- Jira and Linear integrations are typically authorized at a site/workspace boundary, then configured for projects or teams underneath that.
- Some member-specific behaviors still require per-user links after the workspace installation exists.

The project selector on the connector creation page is therefore a symptom of a deeper problem: Spec-Kitty treats all integrations as user-level OAuth credentials when the dominant industry pattern is to separate installation, optional user linking, resource mapping, and project policy.

## Decision

**Workspace installation is the primary connector boundary. User links are optional. Resource mappings are explicit. Project overrides are exceptional.**

In current product terms, "workspace" maps to the existing `Team` model.

### Four-layer model

```
Layer 1: Team Service Installation (workspace-level)
  "Spec-Kitty workspace Acme Engineering is connected to GitHub / Jira / Slack / Linear"
  - Owns the provider installation or admin-authorized workspace/site connection
  - Created from the Connectors page
  - No project selection during installation
  - Scoped to the current Team model

Layer 2: User Service Link (optional, user-level)
  "Bob has linked his GitHub / Jira account to the existing workspace installation"
  - Used for identity mapping, assignee sync, acting-as-user flows, and personal automations
  - Not required for baseline webhook routing or shared workspace setup
  - Multiple users can link to the same workspace installation

Layer 3: Service Resource Mapping (team-level)
  "Repo acme/backend maps to project acme-backend"
  "Jira project ACME maps to project acme-backend"
  "Slack channel #frontend-alerts maps to project acme-frontend"
  - Routes provider resources into Spec-Kitty
  - Can target a project or another workspace-level feed, depending on provider
  - Created explicitly, even when auto-suggested

Layer 4: Project Service Policy Override (project-level, optional)
  "Project acme-frontend uses split_ownership for Jira"
  - Overrides workspace defaults only when needed
  - Holds doctrine and provider-specific exception policy
  - Most projects should inherit defaults
```

### Service-specific routing model

| Service | Primary installation scope | User link needed? | Resource mapping | Notes |
|---------|-----------------------------|-------------------|------------------|-------|
| GitHub | Team/workspace installation, ideally GitHub App or org-level connection | Optional | Repo → Spec-Kitty project | Auto-suggest from commit graph and git remotes, manual fallback |
| GitLab | Team/workspace installation | Optional | Repo/group resource → Spec-Kitty project | Same as GitHub |
| Jira | Team/workspace installation for site/workspace | Optional | Jira project → Spec-Kitty project | Manual mapping required |
| Linear | Team/workspace installation for workspace | Optional | Linear team/project → Spec-Kitty project | Manual mapping required |
| Slack | Team/workspace installation for workspace | Optional | Channel → project/team feed/incident stream | Channel routing is first-class |

### Git-native mapping is an auto-suggestion, not the sole source of truth

For GitHub and GitLab, Spec-Kitty already has strong signals from the CLI sync:

1. Local git remotes observed from CLI usage
2. Commit SHAs present in synced builds
3. Branch names and `feature_slug` values in namespaces

These signals should be used to **suggest** or **auto-create** repo mappings in the common case. They should not replace explicit installation and mapping records.

Webhook routing order:

1. Use explicit `ServiceResourceMapping` if present
2. Fall back to commit-graph and remote heuristics for unmatched git events
3. Queue unmatched events for review when the system cannot resolve confidently

This preserves the low-friction Git experience without pretending that commit metadata alone is a complete connector model.

### Slack is not a special case that avoids mapping

Slack does not map naturally to a single Spec-Kitty project, but it still needs resource routing. The routing unit is usually a **channel**, not a workspace:

- Workspace install happens once
- Channels can then be mapped to project notifications, team-wide feeds, or incident streams

This matches the natural Slack mental model better than "team-level only, no project mapping."

## Consequences

### Positive

- **Provider-native design**: matches how GitHub Apps, Slack apps, Jira, and Linear are actually installed and configured
- **Unblocked onboarding**: the first user can install services before project-by-project setup exists
- **Cleaner admin model**: workspace installations belong to the workspace, not to a single person's project-scoped token
- **Cleaner member onboarding**: new members can use existing installations immediately and only link their account if needed
- **Cleaner offboarding**: deactivating one member's user links does not tear down the shared workspace installation
- **Explicit routing**: repo/project/channel mappings become first-class state instead of hidden assumptions
- **Better Slack model**: channel mapping becomes a supported concept instead of an awkward exception

### Negative

- **More connector concepts**: installation, user link, resource mapping, and override are more precise but more numerous than a single binding record
- **Provider-specific UX**: the install flow will differ across providers because the providers differ
- **Migration required**: existing binding records with embedded OAuth credentials must be split across the new layers
- **More routing records**: GitHub/GitLab repo mappings become explicit records even when discovered automatically

### Neutral

- `IssueTrackerBinding` and `UserProviderConnection` already hint at the right separation, but they still attach the user credential too closely to a project binding
- Commit-graph routing remains valuable, but as an inference tool and fallback, not as the primary authority

## Alternatives Considered

### Option A: Purely user → service, no routing layer

Rejected. Non-git providers need resource routing, and even git providers benefit from explicit repo mappings for auditability and recovery.

### Option B: User-level auth, project-level binding

Rejected as the primary model. It matches deploy tools like Vercel and Netlify for single-project git flows, but it does not generalize to Slack workspace installs, GitHub App installation scope, or shared Jira/Linear workspace setup.

Retained as the override mechanism for exceptional project-specific policy.

### Option C: Team-level binding only, no user links

Rejected as the sole model. Member-specific capabilities such as identity mapping, acting-as-user, and personal automation need an optional user-level association.

### Option D: Commit graph as the only routing authority for git services

Rejected. Commit data is an excellent signal but an incomplete authority. Brand-new repos, mono-repos, and provider permission boundaries still require explicit installation and mapping state.

## Industry precedents

- **Vercel / Netlify**: user connects a git provider, then links a specific repository to a specific project. Good precedent for Git-native project linking, but too narrow as a universal connector model.
- **Sentry**: installs integrations at the organization level, then configures project-level alerting, code mappings, and issue creation beneath that.
- **Linear**: separates organization connection, account connection, and team workflow automation in its GitHub integration.
- **Slack + PagerDuty**: workspace installation first, then channel/service linking, plus optional user account linking.
- **GitHub Apps**: installation happens on a user or organization boundary and can be restricted to selected repositories.

These products converge on the same pattern: installation scope first, user links when needed, resource mapping second, project policy last.

## Related

- Companion planning artifact: `prd-connector-auth-first-team-binding-v1.md` in the planning repo
- Existing tracker interface PRD: `prd-universal-task-tracker-interface-and-doctrine-sot-v1.md`
- Current models: `apps/connectors/models.py` in `spec-kitty-saas`

## Reference links

- [Vercel Git integration docs](https://vercel.com/docs/git/vercel-for-github)
- [Netlify import existing project](https://docs.netlify.com/start/add-new-project/)
- [Sentry Jira integration docs](https://docs.sentry.io/organization/integrations/issue-tracking/jira/)
- [Sentry Microsoft Teams integration docs](https://docs.sentry.io/organization/integrations/notification-incidents/msteams/)
- [Linear GitHub integration docs](https://linear.app/docs/github-integration)
- [Slack app lifecycle and distribution docs](https://docs.slack.dev/app-management/distribution/)
- [PagerDuty Slack integration guide](https://support.pagerduty.com/main/docs/slack-integration-guide)
- [GitHub App installation docs](https://docs.github.com/en/apps/using-github-apps/installing-your-own-github-app)
