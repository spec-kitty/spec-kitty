---
title: 'ADR: GitHub App Installation Identity Is Provider-Authoritative; Nango Is Secondary'
description: Accepted ADR making GitHub App installation identity provider-authoritative and Nango secondary for connector binding and resource-mapping decisions.
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-06'
related:
- adr/3.x/2026-04-06-2-connector-auth-binding-separation
---
# ADR: GitHub App Installation Identity Is Provider-Authoritative; Nango Is Secondary

**Status**: Accepted
**Date**: 2026-03-10
**Author**: Spec Kitty team + Codex
**Related ADR**: [Connector Installation, User Link, and Resource Mapping Separation](2026-04-06-2-connector-auth-binding-separation.md)

## Context

The connector hard-cutover introduces installation-first integrations across providers. During planning, one ambiguity kept recurring:

- should Spec-Kitty treat a Nango `connection_id` as the canonical identity for a GitHub App installation?
- or should Spec-Kitty treat GitHub's own installation identifier as the source of truth and only use Nango as an optional credential helper?

This distinction matters because GitHub Apps are not shaped like ordinary workspace OAuth connections.

GitHub's provider-native model is:

1. One GitHub App registration has one webhook configuration
2. Each customer install creates a GitHub **installation**
3. Webhook payloads for GitHub App events include the **installation** object
4. Installation access tokens are minted **for a specific installation ID**
5. Optional user-to-server tokens are separate from the shared installation and only apply when the app needs to act on behalf of a user

That means GitHub itself recognizes installation identity and webhook authenticity independently of any Nango-side connection naming.

If Spec-Kitty incorrectly treats the Nango `connection_id` as the primary authority, agents will keep making the same design mistakes:

- routing inbound webhooks through Nango identifiers instead of GitHub installation identity
- storing GitHub install state as if it were generic OAuth workspace state
- coupling app-level webhook verification to team-level or mapping-level secrets
- designing future migrations around renaming Nango connections instead of persisting provider-native identifiers

## Decision

For GitHub App integrations, **GitHub provider identity is authoritative**.

Spec-Kitty must model GitHub App installations as follows:

1. `provider_installation_id` is the canonical external identity of a GitHub installation
2. GitHub webhook verification uses the **app-level webhook secret** configured on the GitHub App registration
3. Inbound webhook routing resolves from the payload's `installation.id` and repository identity to a local installation plus repo mapping
4. `control_plane_connection_id` is optional and secondary; if Nango is used, it is an implementation detail for outbound credential retrieval, not the canonical installation key
5. Optional user-level GitHub authorization is a separate concern from the shared installation and should be modeled like a user link, not as the installation itself

## Rules For Agents

When working on GitHub App design or implementation, agents must follow these rules:

1. Never use Nango `connection_id` as the sole or primary identifier for a GitHub App installation
2. Always persist GitHub's installation identity on the installation record
3. Treat webhook URL and webhook secret as **app-level** configuration, not per-team or per-mapping state
4. Route GitHub events by `installation.id` plus repository identity, then resolve explicit repo mapping
5. Treat repo mappings as the routing authority; Git metadata may suggest mappings but does not replace them
6. Keep user-to-server tokens separate from installation-to-server auth

## Implementation Consequences

### Data model

- `TeamServiceInstallation.provider_installation_id` is required for GitHub
- `TeamServiceInstallation.control_plane_connection_id` must be nullable
- repo access and explicit repo mappings live beneath the installation

### Webhooks

- GitHub App ingress should be an app-level endpoint, not a binding-specific or team-specific endpoint
- signature validation uses the app webhook secret
- payload handling must extract `installation.id` and repository identity before local routing

### Outbound GitHub API calls

- the default authority chain is:
  - app private key / app auth
  - GitHub `installation_id`
  - installation access token minted for that installation
- if Nango is used, it may help acquire or manage outbound credentials, but it does not replace the provider installation identifier in Spec-Kitty's domain model

### User links

- user links are only needed for user-attributed operations
- user links must not replace shared installation state

## Alternatives Considered

### Treat Nango `connection_id` as the canonical GitHub installation identity

Rejected.

This hides the provider-native installation boundary and makes inbound routing dependent on an internal control-plane key that GitHub does not send on webhook payloads.

### Treat GitHub App install as ordinary workspace OAuth

Rejected.

GitHub App auth and webhook flow are installation-based, not simple workspace-token based.

### Put webhook secret on each repo mapping

Rejected for GitHub App.

GitHub App webhook verification is configured at the app registration boundary. Repo mappings are downstream routing state, not webhook-auth boundaries.

## Operational Guidance

- Forced reconnect or reinstall flows must preserve the distinction between:
  - GitHub installation identity
  - optional Nango connection identifiers
  - optional user authorization
- Migration planning must assume that old Nango connection naming can change without redefining what the GitHub installation is
- Observability should log both local installation UUID and `provider_installation_id` for GitHub events

## References

- [GitHub Docs: Registering a GitHub App](https://docs.github.com/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [GitHub Docs: Authenticating as a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app)
- [GitHub Docs: Generating an installation access token for a GitHub App](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [GitHub Docs: Generating a user access token for a GitHub App](https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [GitHub Docs: Webhook events and payloads](https://docs.github.com/enterprise-cloud%40latest/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
- [Nango Docs: GitHub App](https://docs.nango.dev/integrations/all/github-app)
