# Discovery Findings — #6990 dispatch `--brief` governance payload

**Mission**: `dispatch-brief-governance-payload-01M6BV2S`
**Grounded on**: `main` @ `287a226cfe` (2026-11-01), in `/home/exedev/work/sk-6990`
**Issue**: spec-kitty/spec-kitty#6990 (open, unassigned before this mission, claimed by this run)

## D1 — The issue still reproduces on current `main`

Measured with the installed CLI (4.0.0rc8, built from this `main`) and re-measured
with `uv run --frozen spec-kitty` from this checkout (identical result):

```text
$ spec-kitty dispatch "implement the login handler" --profile python-pedro --dry-run --json | wc -c
24983

envelope field sizes:
  governance_context_text     23668   <- 95% of the envelope
  glossary_observations         ~500
  recommendation                ~300
  everything else               <100
```

`governance_context_text` is 308 lines. The payload content is correct: the
charter, the directive IDs, the profile-cited directive bodies with their
`Run: spec-kitty charter context --include directive:...` fetch hints, and the
diagnostics block. Only the delivery is wasteful.

**Was it superseded?** No. `git log -S"--brief" -- src/specify_cli/cli/commands/`
returns nothing, no open PR references #6990
(`gh pr list --search "6990 in:body"` → empty), and the changelog has no entry
about a brief or reference mode. The nearest merged work is
`dispatch-dry-run-route-only` (the `--dry-run` flag), which changed nothing about
the payload volume.

## D2 — Where the volume is produced, and why the render is not the fix

`ProfileInvocationExecutor._resolve_routing_and_context()` calls
`build_charter_context(..., mark_loaded=False)` and puts `ctx_result.text` on the
payload verbatim (`src/specify_cli/invocation/executor.py`). The text is then
re-embedded by `_render_payload_capsule()` in the console path and by
`InvocationPayload.to_dict()` in the `--json` path
(`src/specify_cli/cli/commands/dispatch.py`).

Two candidate fixes were in the issue:

1. *Embed-by-reference after the first read per session/profile.* Rejected as the
   mechanism. "First read per session" needs session identity that `dispatch`
   does not have (it is a one-shot process) and would have to be guessed from
   environment variables or a TTL state file. That makes a governance-loading
   surface stateful and non-deterministic — and it silently stops loading
   governance when the guess is wrong. C-001 in the spec forbids it.
2. *A `--brief` flag.* Chosen. It is deterministic, caller-controlled, and leaves
   the default byte-identical.

The reference mode still carries the embed-by-reference idea, at the caller's
request: the brief payload prints a payload digest plus a fetch command.

## D3 — The fetch command must name the profile, because profile-cited doctrine is most of the payload

`dispatch` calls `build_charter_context(repo_root, profile=<id>, action=<a>,
mark_loaded=False)`. For the same project/action, the profile-cited sections are
121→308 of the 308 rendered lines (≈18.7 KB of the 23.7 KB).

```text
action=generate, no profile    → compact render, 4,903 bytes
action=generate, profile=pedro → compact render, 23,642 bytes  (identical to dispatch's text)
```

`spec-kitty charter context` today has no `--profile` option
(`src/specify_cli/cli/commands/charter/context.py`), so the obvious fetch command
`spec-kitty charter context --action <a>` fetches barely a fifth of the omitted
text and silently drops the profile-cited directives. That would turn an
ergonomics change into a governance-faithfulness bug. Hence FR-003: add
`--profile` to `charter context`, and make the brief fetch command
`spec-kitty charter context --action <a> --profile <id>`.

Byte-comparison check performed in-process:

```python
build_charter_context(root, action="generate", profile="python-pedro", mark_loaded=False).text
  == executor.dry_run("implement the login handler", profile_hint="python-pedro").governance_context_text
```

## D4 — The action is derived from the request, not from the profile's role name

A trap for anyone writing the fetch command by hand: with `--profile
python-pedro` and the request "implement the login handler", the payload's
`action` is `generate` (role-default-verb derivation), not `implement`. The
brief payload must print the **payload's own** `action`, never a re-derivation
from the request text, or the printed fetch command would render a different
grain than the one that was omitted.

## D5 — Brief mode belongs in the command layer, not the executor

The executor assembles governance context on every call, brief or not (the
saving is prompt tokens, not compute; NFR-002/C-002 keep it that way). The
substitution is a rendering concern, so `--brief` is implemented in
`src/specify_cli/cli/commands/dispatch.py` over the existing payload:

- JSON: `governance_context_text` becomes `null`; a
  `governance_context_reference` object carries `digest`, `bytes`, `lines`,
  `fetch_command`. The rest of the envelope is untouched (C-003).
- Console: the "Governance Context" panel is replaced by one digest line plus
  the fetch command; the open-Op close hint still prints.

No slot is added to `InvocationPayload`, so `_serialize_slots()` and every other
payload consumer are untouched.

## Open questions left to plan/tasks

- Whether the `charter context --json` payload should also gain a `profile`
  field; the text field is profile-aware either way. (Lean: no — the structured
  blocks are DRG projections, not profile-cited prose.)
- Whether `--brief` should be refused together with `--dry-run`. (Lean: no —
  they compose; a dry run is exactly when a harness probes routing cheaply.)
