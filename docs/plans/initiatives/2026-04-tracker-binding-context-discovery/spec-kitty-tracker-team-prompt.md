---
title: 'Prompt: `spec-kitty-tracker` Team'
description: Ready-to-run /spec-kitty.specify input prompt for the spec-kitty-tracker team's slice of the tracker-binding-context-discovery work.
doc_status: deprecated
updated: '2026-09-30'
---
# Prompt: `spec-kitty-tracker` Team

Use this file as the input to `/spec-kitty.specify` in the
`spec-kitty-tracker` repo.

## Prompt

Architect and implement the tracker-library contract changes required by the
accepted ADR
`2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md`.

Problem:

The tracker library already supports workspace discovery and resource discovery,
but the current discovery contract is too lossy. It collapses provider-native
machine identity into generic `resource_id` and `resource_label` values, which
forces downstream hosts to re-infer or manually ask for routing metadata such as
Linear team keys, Jira project keys, GitHub repo coordinates, or GitLab project
paths. The library should expose bindable resource descriptors rich enough for
hosts to build connectors and mappings without asking users for raw metadata.

Scope this feature to the `spec-kitty-tracker` repo only.

Required behavior:

1. Expand the discovery contract so a discovered bindable resource can carry:
   1. stable machine identity,
   2. human display identity,
   3. provider-native connector parameters,
   4. provider-specific routing metadata.
2. Preserve provider-native metadata that is currently discarded. At minimum:
   1. Linear: team id, key, name
   2. Jira: project key, name, site/base URL context
   3. GitLab: project id, path-with-namespace, web URL if available
   4. GitHub: implement repo resource discovery under organizations and expose
      repo id, owner, repo, full name, and useful display/web metadata
3. Keep the contract generic enough that Azure DevOps and future providers can
   adopt it without changing the architecture again.
4. If helpful, provide a helper or translation layer that turns a discovered
   resource descriptor into the provider-specific hosted connector params needed
   by hosts.
5. Update provider discovery docs and tests to reflect the richer contract.

Relevant current code:

* `src/spec_kitty_tracker/workspace_discovery.py`
* `src/spec_kitty_tracker/resource_discovery.py`
* `src/spec_kitty_tracker/hosted.py`
* `src/spec_kitty_tracker/connectors/linear.py`
* `src/spec_kitty_tracker/connectors/jira.py`
* `src/spec_kitty_tracker/connectors/github.py`
* `src/spec_kitty_tracker/connectors/gitlab.py`
* `docs/provider-matrix.md`

Non-goals:

1. Do not implement SaaS mapping resolution or CLI UX in this repo.
2. Do not hard-code Spec Kitty SaaS model assumptions into the tracker library.
3. Do not reduce discovery back to provider-specific ad hoc dicts with no shared
   structure.

Acceptance criteria:

1. Discovery returns enough metadata that hosts do not need to ask users for raw
   tracker-native project/team/repo identifiers in the normal path.
2. GitHub resource discovery is implemented and documented.
3. Linear, Jira, GitHub, and GitLab all expose a coherent bindable-resource
   contract with tests.
4. The new contract is explicit about which fields are stable identifiers versus
   display metadata versus connector parameters.
5. The resulting API is clean enough that a host can build a resolved binding
   flow without provider-specific reverse engineering.
