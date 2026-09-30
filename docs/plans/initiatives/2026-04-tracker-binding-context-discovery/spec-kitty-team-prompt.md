---
title: 'Prompt: `spec-kitty` Team'
description: Ready-to-run /spec-kitty.specify input prompt for the spec-kitty team's slice of the tracker-binding-context-discovery work.
doc_status: deprecated
updated: '2026-09-30'
---
# Prompt: `spec-kitty` Team

Use this file as the input to `/spec-kitty.specify` in the `spec-kitty` repo.

## Prompt

Architect and implement the `spec-kitty` CLI side of the accepted ADR
`2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md`.

Problem:

The current SaaS-backed tracker bind flow still asks for `--project-slug` and
stores only `provider + project_slug` locally. That is the wrong local binding
primitive. For SaaS-backed providers, the CLI should derive local project
identity, ask the host control plane for existing mapping or bind candidates,
and persist a stable binding reference rather than asking the user for raw
tracker-native metadata or relying only on `project_slug`.

Scope this feature to the `spec-kitty` repo only.

Required behavior:

1. `spec-kitty tracker bind --provider <saas-provider>` should no longer require
   manual raw tracker metadata in the normal path.
2. The CLI should derive local project identity from the repo and existing
   `.kittify` project data.
3. The CLI should call new or expanded SaaS APIs to:
   1. inspect installation-wide tracker state before a local bind exists,
   2. resolve local project identity to existing mapping candidates or bindable
      resource candidates,
   3. persist the binding returned by the host.
4. If there is exactly one confident candidate, bind automatically.
5. If there are multiple candidates, present human-labeled choices instead of
   asking for raw keys, prefixes, repo names, or IDs.
6. Local tracker config should evolve to store a stable binding reference plus
   optional cached display metadata. Backward compatibility with existing
   `project_slug`-based config must be preserved.
7. `tracker status` and tracker mapping-inspection flows should support
   installation-wide introspection where the SaaS API allows it, instead of
   assuming a pre-existing local bind.

Relevant current code:

* `src/specify_cli/cli/commands/tracker.py`
* `src/specify_cli/tracker/saas_client.py`
* `src/specify_cli/tracker/saas_service.py`
* `src/specify_cli/tracker/config.py`
* `src/specify_cli/sync/project_identity.py`

Non-goals:

1. Do not implement provider discovery logic locally; that belongs in
   `spec-kitty-tracker` and `spec-kitty-saas`.
2. Do not design a bespoke bind UX per provider.
3. Do not reintroduce direct provider credentials for SaaS-backed providers.

Acceptance criteria:

1. A normal SaaS-backed bind can complete without the user typing a tracker
   prefix, project key, repo path, or numeric external resource ID.
2. The config model has a migration or compatibility strategy for older local
   tracker bindings.
3. The CLI can represent zero, one, or many host-returned bind candidates
   cleanly.
4. Tests cover auto-bind, ambiguous selection, no-candidate, and backward
   compatibility cases.
5. The final design remains aligned with the accepted ADR and the existing
   host-owned tracker persistence boundary.
