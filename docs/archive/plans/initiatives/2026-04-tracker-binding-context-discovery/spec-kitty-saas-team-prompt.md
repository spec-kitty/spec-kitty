---
title: 'Prompt: `spec-kitty-saas` Team'
description: Ready-to-run /spec-kitty.specify input prompt for the spec-kitty-saas team's slice of the tracker-binding-context-discovery work.
doc_status: deprecated
updated: '2026-09-30'
---
# Prompt: `spec-kitty-saas` Team

Use this file as the input to `/spec-kitty.specify` in the `spec-kitty-saas`
repo.

## Prompt

Architect and implement the `spec-kitty-saas` control-plane and dashboard work
required by the accepted ADR
`2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md`.

Problem:

The current SaaS architecture already resolves `project_slug -> Project ->
ServiceResourceMapping -> external resource`, but the API and mapping UX do not
yet expose enough inventory and resolution behavior for the CLI to bind without
asking the user for hidden tracker metadata. The host should be authoritative
for installation inventory, bindable resource inventory, mapping resolution, and
the persistence of provider-specific routing metadata.

Scope this feature to the `spec-kitty-saas` repo only.

Required behavior:

1. Add or expand control-plane APIs so clients can:
   1. inspect tracker installation state without an existing local bind,
   2. list bindable resources under an installation,
   3. resolve local Spec Kitty project identity into:
      1. an existing mapping,
      2. candidate mappings,
      3. candidate bindable resources when no mapping exists.
2. Ensure `ServiceResourceMapping` stores enough provider-specific
   `routing_metadata` to reconstruct hosted connector params and display useful
   labels later.
3. Update mapping creation/edit flows for supported SaaS-backed providers so
   admins select from discovered resources instead of typing free-form external
   IDs in the normal case.
4. Make installation-wide status and mapping reads available where appropriate
   so the CLI can inspect state before a bind exists.
5. Define a stable binding reference that the CLI can persist locally after
   resolution.
6. Preserve the existing runtime policy model where mapped project context is
   the authority for push/run/search behavior.

Relevant current code:

* `apps/connectors/models.py`
* `apps/connectors/forms.py`
* `apps/connectors/installation_views.py`
* `apps/connectors/tracker_views.py`
* `apps/connectors/runtime_policy.py`
* `apps/connectors/mission_origin_search.py`

Non-goals:

1. Do not move tracker discovery into the SaaS app; consume the richer discovery
   contract from `spec-kitty-tracker`.
2. Do not keep free-text raw ID entry as the primary happy path for Jira,
   Linear, GitHub, or GitLab mappings.
3. Do not redesign runtime doctrine or authority policy in this feature.

Acceptance criteria:

1. The CLI can bind to an existing mapping or a newly chosen discovered resource
   without asking the user for raw tracker-native metadata.
2. The new API contract can represent zero, one, or many candidate resolutions,
   with enough metadata for the CLI to display good labels and choose safely.
3. Mapping persistence preserves provider-native routing metadata in a stable and
   testable way.
4. Jira, Linear, GitHub, and GitLab are all covered by the new contract shape,
   even if some provider-specific UX details vary.
5. Tests cover resolution, ambiguity, mapping persistence, and dashboard mapping
   creation from discovered resources.
