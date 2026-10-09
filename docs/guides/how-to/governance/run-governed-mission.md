---
title: How to Run a Governed Mission
description: Run spec-kitty next with Charter context injection, read JSON output, handle composed steps and blocked decisions.
doc_status: active
updated: '2026-10-08'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/context/charter-overview.md
---
# How to Run a Governed Mission

This guide covers running a mission action under Charter governance using `spec-kitty next`.

For background on governed profile invocation, see [How Charter Works](../../../context/charter-overview.md).

---

## Before you begin

Confirm your governance is ready before running a mission:

1. Charter bundle is current: `uv run spec-kitty charter status`
2. Bundle validates: `uv run spec-kitty charter bundle validate`
3. Doctrine is synthesized: check that `.kittify/charter-packs/` is present. Fresh projects may only
   have `PROVENANCE.md`; in that state the runtime falls back to the built-in Charter Pack until
   agent-generated artifacts are promoted.

If the bundle is stale, run the synthesis flow first. See
[How to Synthesize and Maintain Doctrine](synthesize-doctrine.md).

---

## 1. Run a governed mission action

The primary loop command is `spec-kitty next`. It inspects the mission's state machine, evaluates
guards, and returns the next deterministic action with its prompt file:

```bash
uv run spec-kitty next --agent claude --mission my-feature-slug --json
```

`--agent` identifies the agent name used for the issued action. `--mission` is the mission slug
(the human-readable identifier, e.g., `my-feature-slug`).

When `--result` is omitted, `next` operates in **query mode**: it reads and returns the current
mission state without advancing it. This is safe to call repeatedly to check what step is next.

```bash
# Query mode — inspect without advancing
uv run spec-kitty next --mission my-feature-slug --json
```

Charter context is rendered automatically into the prompt file returned by `next`. The command
does not spawn the agent itself; it emits the action, state, and `prompt_file` for the caller to
read and execute. You do not need to pass governance flags manually.

---

## 2. Read the output

`spec-kitty next --json` emits a structured decision object. Key fields:

| Field | Type | Description |
|---|---|---|
| `kind` | string | Decision kind: `query`, `step`, `decision_required`, `blocked`, or `terminal` |
| `action` | string/null | The action the agent should perform (e.g., `specify`, `plan`, `implement`) |
| `mission_state` | string | Current state machine state |
| `step_id` | string/null | Runtime step identifier for the issued step |
| `prompt_file` | string/null | Absolute path to the prompt file. Non-null and resolvable for `kind: "step"` |
| `preview_step` | string/null | Next step preview in query mode |
| `decision_id` | string/null | Pending decision identifier for `decision_required` responses |
| `question` / `options` | string/list/null | Decision prompt data when input is required |
| `reason` / `guard_failures` | string/list | Explanation for blocked or guarded states |
| `progress` | object/null | Work-package progress summary when available |

A fresh-run query returns `mission_state: "not_started"` and a `preview_step` showing the first
step. Do not depend on `unknown` as the fresh-run state — that is a legacy value.

---

## 3. Advance through composed steps

To advance the mission after completing a step, report the result:

```bash
# Report success and get the next step
uv run spec-kitty next --agent claude --mission my-feature-slug --result success --json

# Report failure (mission may loop or escalate)
uv run spec-kitty next --agent claude --mission my-feature-slug --result failed --json

# Report blocked (mission pauses pending a decision)
uv run spec-kitty next --agent claude --mission my-feature-slug --result blocked --json
```

A composed mission (e.g., `software-dev`) has multiple steps: `discover`, `specify`, `plan`,
`implement`, `review`, and so on. Each call to `next --result success` advances the state machine
to the next step. The runtime returns the action and prompt file for that step.

---

## 4. Prompt resolution

`spec-kitty next` resolves which prompt template to use for the current step from the mission's
`mission-runtime.yaml` configuration. The step's `prompt_template` field points to a packaged
mission template or resolved local prompt template.

When prompt resolution succeeds, the output includes a `prompt_file` path. When it fails
(for example, the mission type is unrecognized or the step template is missing), `next` returns a
non-zero exit code with a structured error explaining the resolution failure.

If you encounter a resolution failure:
- Verify the mission type is valid: `uv run spec-kitty mission list`
- Check that the mission slug matches a real mission: `uv run spec-kitty mission current`

---

## 5. Handle blocked decisions

When a mission action encounters a question that requires a concrete answer before proceeding,
the mission opens a decision moment and blocks. `spec-kitty next` will return with
`mission_state: "blocked"` or `result: "blocked"`.

To resolve a blocked decision:

```bash
# View the decision (from the --json output, extract the decision_id)
uv run spec-kitty next --mission my-feature-slug --json

# Resolve the decision with a final answer
uv run spec-kitty agent decision resolve <decision-id> \
  --mission my-feature-slug \
  --final-answer "yes" \
  --json
```

After resolving, resume the mission:

```bash
uv run spec-kitty next --agent claude --mission my-feature-slug --result success --json
```

You can also answer a decision inline while reporting a result:

```bash
uv run spec-kitty next --agent claude --mission my-feature-slug \
  --answer "approve" \
  --decision-id "input:review" \
  --result success \
  --json
```

---

## See Also

- [How Charter Works](../../../context/charter-overview.md)
- [Understanding Governed Profile Invocation](../../../architecture/governed-profile-invocation.md)
- [Charter CLI Reference](../../../api/charter-commands.md)
- [How to Synthesize and Maintain Doctrine](synthesize-doctrine.md)
