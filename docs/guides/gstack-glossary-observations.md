---
title: Render Glossary Observations from InvocationPayload (gstack / host agents)
description: How gstack-compatible host agents should interpret and display the glossary_observations field returned by the Spec Kitty invocation executor.
doc_status: active
updated: '2026-06-03'
type: reference
audience: docs/context/audience/internal/ai-collaboration-agent.md
related:
- docs/guides/how-to/harnesses/setup-codex-spec-kitty-launcher.md
---
# Render Glossary Observations from InvocationPayload

When Spec Kitty's invocation executor processes a request it runs a fast inline
glossary conflict scan (the *glossary chokepoint*) and attaches the result to
`InvocationPayload` as `glossary_observations`. Host agents — including gstack
and any custom orchestrator — must implement the rendering contract described
below.

## Payload Structure

`InvocationPayload.to_dict()` returns a dict that includes `"glossary_observations"`:

```json
{
  "invocation_id": "01HXYZ...",
  "profile_id": "implementer",
  "action": "implement",
  "governance_context_text": "...",
  "governance_context_hash": "a3f1b2c4",
  "governance_context_available": true,
  "router_confidence": null,
  "glossary_observations": {
    "matched_urns": ["glossary:d93244e7"],
    "high_severity": [],
    "all_conflicts": [],
    "tokens_checked": 12,
    "duration_ms": 3.2,
    "error_msg": null
  }
}
```

The `glossary_observations` dict is produced by
`GlossaryObservationBundle.to_dict()`.

## Rendering Contract

### Clean invocation (`all_conflicts` empty, `error_msg` null)

No glossary notice is needed. Deliver governance context to the model as normal.

### Low-severity conflicts only (`all_conflicts` non-empty, `high_severity` empty)

Optionally surface a low-priority advisory notice. No blocking is required.
Example (surfaced below the governance context):

```
[GLOSSARY ADVISORY] Minor terminology ambiguity detected. Review if relevant.
```

### High-severity conflicts (`high_severity` non-empty)

Prepend an inline warning **before** the governance context delivered to the
model. This ensures the model receives the warning in its context window before
acting.

Example format:

```
[GLOSSARY WARNING] The following terms carry HIGH-severity semantic conflicts:
  • lane (glossary:d93244e7) — ambiguous_scope
    Candidate senses: "execution lane (WP routing)" | "git branch lane (worktree)"

Review these terms carefully before proceeding.
---
[Governance context follows]
```

### Error during scan (`error_msg` non-null)

Log the warning internally. Do **not** block the invocation. The glossary scan
degraded gracefully and the rest of the payload is valid.

Example log line:

```
[WARN] glossary chokepoint error for invocation 01HXYZ...: <error_msg value>
```

## Trail Behaviour

A `glossary_checked` event is appended to the Tier 1 JSONL trail **only** when
`all_conflicts` is non-empty OR `error_msg` is non-null. Clean invocations
produce no `glossary_checked` line.

Readers that encounter `"event": "glossary_checked"` in a trail file and do not
recognise the event type may safely skip it.

See [Trail Model — Glossary Check Event](https://github.com/spec-kitty/spec-kitty/blob/main/docs/trail-model.md#glossary-check-event-conditional-tier-1)
for the full event schema.

## See Also

- [Set Up a Codex Launcher for Spec Kitty](how-to/harnesses/setup-codex-spec-kitty-launcher.md)
- [Trail Model](https://github.com/spec-kitty/spec-kitty/blob/main/docs/trail-model.md)
- [CLI Commands](../api/cli-commands.md)
