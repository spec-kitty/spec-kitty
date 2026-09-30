---
title: Understanding Governed Profile Invocation
description: 'How standalone dispatch works under governance: route, inject context, open an Op, do work, close the trail.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/context/charter-overview.md
---
# Understanding Governed Profile Invocation

This document explains governed profile invocation. For how to run a governed
mission, see [How to Run a Governed Mission](../guides/how-to/governance/run-governed-mission.md).
For the CLI reference, see
[Profile Invocation Reference](../api/profile-invocation.md).

---

## The Governed Invocation Primitive

Standalone governed work in Spec Kitty is a triple:

1. **Profile**: the resolved agent profile used to select the right governance
   context. Users normally do not need to choose this; the router does it. A
   caller can pass `--profile <profile-id>` when they intentionally want a
   specific profile.
2. **Action**: the action token resolved for the request, such as `implement`,
   `review`, or `plan`.
3. **Governance context**: the Charter bundle context injected at invocation
   time. This is the DRG-derived, action-scoped set of directives, tactics, and
   glossary terms that the agent receives.

When `spec-kitty next` prepares a prompt for the current mission step, it
resolves the action and renders governance context into the prompt file returned
to the calling agent. For standalone work, `spec-kitty dispatch "<request>"`
does the same governance-context loading and records an Op trail.

---

## Standalone Dispatch

Use standalone dispatch when the user wants Spec Kitty involved but is not
asking for a full mission:

```bash
uv run spec-kitty dispatch "Review this approach" --json
uv run spec-kitty dispatch "Implement token validation" --profile implementer-ivan --json
```

The command returns `governance_context_text`, `invocation_id`, and a
`close_contract`. The host agent must read `governance_context_text`, treat it
as binding context, do the work, then close the Op.

---

## Invocation Lifecycle

Every standalone dispatch follows the same append-only lifecycle:

1. **Opened**: A `started` event is written to
   `kitty-ops/{invocation_id}.jsonl` before the executor returns. This write is
   unconditional: it happens regardless of SaaS connectivity or charter state.
2. **Work happens outside the CLI**: The CLI has returned the context payload.
   The caller or agent performs the work.
3. **Completed**: When execution finishes, `spec-kitty profile-invocation
   complete` closes the trail. This appends a `completed` event to the same
   JSONL file. `--artifact` and `--commit` append separate correlation events
   after the completed event.

```bash
uv run spec-kitty profile-invocation complete \
  --invocation-id <ULID> \
  --outcome done \
  --artifact path/to/produced/file.md \
  --commit <git-sha>
```

Options for `profile-invocation complete`:

- `--outcome`: `done`, `failed`, or `abandoned`
- `--artifact`: path to an artifact produced by this invocation (repeatable)
- `--commit`: the primary git commit SHA produced by this invocation (singular)
- `--evidence`: promote a file to a Tier 2 evidence artifact when the record is
  evidence-eligible

---

## The Invocation Trail

The invocation trail is the local audit record written by every governed
invocation. It provides:

1. **Local accountability**: operators can reconstruct what happened on any
   checkout without SaaS connectivity.
2. **SaaS coherence**: the dashboard timeline shows the same history as the
   local audit log.
3. **Governance provenance**: retrospective and doctrine work can reference
   specific invocations.

Trail files live at `kitty-ops/{invocation_id}.jsonl`: one JSONL file per
invocation. Each line is an event (`started`, `completed`, `glossary_checked`,
`artifact_link`, `commit_link`, or future additive events).

Key fields on the `started` event:

| Field | Type | Description |
|---|---|---|
| `profile_id` | string | Resolved profile identifier |
| `action` | string | Resolved action token |
| `request_text` | string | Request supplied to `dispatch` |
| `governance_context_hash` | string | Hash of the rendered Charter context |
| `governance_context_available` | boolean | Whether Charter context was available |
| `started_at` | ISO timestamp | When the invocation was opened |
| `mode_of_work` | string | Work mode used for trail policy |

Key fields on the `completed` event:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | ULID | Matches the `started` event |
| `outcome` | string | `done`, `failed`, or `abandoned` |
| `completed_at` | ISO timestamp | When `profile-invocation complete` was called |
| `closed_by` | string | `agent` or `doctor_sweep` |
| `evidence_ref` | string/null | Evidence path or text supplied with `--evidence` |

---

## Evidence and Artifact Correlation

Artifacts produced during an invocation are linked back to the trail record via
separate `artifact_link` and `commit_link` events appended by the `--artifact`
and `--commit` options on `profile-invocation complete`. This correlation
provides:

- A local audit link from an invocation to the artifacts or commit it produced
- Governance provenance context for humans and future automated consumers

Evidence files promoted via `--evidence` receive Tier 2 status in the trail.

---

## See Also

- [How Charter Works](../context/charter-overview.md)
- [How to Run a Governed Mission](../guides/how-to/governance/run-governed-mission.md)
- [Profile Invocation Reference](../api/profile-invocation.md)
