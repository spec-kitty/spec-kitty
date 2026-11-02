---
work_package_id: WP02
title: dispatch --brief replaces the embedded payload with a reference
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- SC-001
- SC-003
planning_base_branch: issue-6990-dispatch-brief-governance-payload
merge_target_branch: issue-6990-dispatch-brief-governance-payload
branch_strategy: Planning artifacts for this mission were generated on issue-6990-dispatch-brief-governance-payload. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6990-dispatch-brief-governance-payload unless the human explicitly redirects the landing branch.
subtasks:
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-11-01T15:21:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/dispatch.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/dispatch.py
- tests/specify_cli/invocation/cli/test_dispatch.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – `dispatch --brief` replaces the embedded payload with a reference

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission dispatch-brief-governance-payload-01M6BV2S`) and address every item before handing back.

## Objectives & Success Criteria

- `spec-kitty dispatch --brief` keeps every routing and orientation field and
  replaces the re-embedded governance text with a digest plus an exact fetch
  command — in `--json` and in console output, on the real (Op-opening) path and
  on `--dry-run`. Spec FR-001, FR-002.
- `dispatch` without `--brief` is byte-identical to today, in both output modes.
  Spec FR-004, SC-003.
- Brief JSON stays under 10% of the measured 24,983-byte baseline envelope and
  contains no governance text characters. Spec NFR-001, SC-001.
- No gate, no Op record field and no executor behaviour changes.

## Context

`src/specify_cli/cli/commands/dispatch.py` renders the payload twice:

- `_render_payload_capsule()` → `console.print(Panel(payload.governance_context_text, title="Governance Context", ...))`
- `typer.echo(json.dumps(payload.to_dict(), indent=2))` for the real path and
  `payload.to_dry_run_dict()` for `--dry-run`.

The executor has already assembled the full text by then
(`ProfileInvocationExecutor._resolve_routing_and_context`), and it still will:
`--brief` saves prompt tokens, not compute. The substitution is a rendering
concern, so it belongs in this command module — do **not** change
`InvocationPayload`, `_serialize_slots()` or the executor.

Measured facts from `research.md` (D3/D4):

- The payload's `action` is derived from the request (`generate`, not
  `implement`, for "implement the login handler" with `--profile python-pedro`).
  The fetch command must print the payload's own `action`, never a re-derivation.
- The exact fetch command is `spec-kitty charter context --action <action>
  --profile <profile_id>` (WP01 supplies `--profile`).

## Subtask T003 — Failing tests first

Add to `tests/specify_cli/invocation/cli/test_dispatch.py` (it already patches
`build_charter_context` with `_COMPACT_CTX` whose text is
`"compact governance context"`, 24 bytes / 1 line — good for exact assertions).
Run them before the implementation; they must fail.

1. `test_dispatch_brief_json_replaces_text_with_reference` — `dispatch "<req>"
   --profile implementer-fixture --json --brief`:
   - exit 0, `governance_context_text is None`
   - `governance_context_reference` == `{"digest": envelope["governance_context_hash"],
     "bytes": 24, "lines": 1, "fetch_command": "spec-kitty charter context
     --action implement --profile implementer-fixture"}`
   - every other field still present and equal to the non-brief run on the same
     fixture (`profile_id`, `action`, `router_confidence`, `recommendation`,
     `governance_context_hash`, `governance_context_available`, `status`,
     `close_contract`)
2. `test_dispatch_brief_console_prints_digest_and_fetch_command` — console mode:
   the digest line and the fetch command appear; `"compact governance context"`
   does **not**; the `This Op is OPEN` close hint still appears.
3. `test_dispatch_brief_composes_with_dry_run` — `--dry-run --json --brief`:
   `status == "dry_run"`, text null, reference populated, no Op record written.
4. `test_dispatch_without_brief_still_embeds_full_text` — the ratchet: on the same
   fixture the non-brief envelope still carries `governance_context_text` and has
   **no** `governance_context_reference` key. (This is the same-fixture positive
   control for the null assertions above.)
5. `test_dispatch_brief_leaves_ambiguous_dry_run_payload_untouched` — the
   `ROUTER_AMBIGUOUS` dry-run payload (no governance text) is unchanged by
   `--brief`.

## Subtask T004 — Implement

In `src/specify_cli/cli/commands/dispatch.py`:

- Add `brief: bool = typer.Option(False, "--brief", help=...)` to the `dispatch`
  command and pass it through `_dispatch_impl(...)`. Keep the help text honest:
  routing/orientation only, full text at the printed fetch command, default
  unchanged.
- One helper builds the reference from the payload, e.g.

  ```python
  def _governance_reference(payload: InvocationPayload) -> dict[str, object]:
      text = payload.governance_context_text or ""
      return {
          "digest": payload.governance_context_hash,
          "bytes": len(text.encode()),
          "lines": len(text.splitlines()),
          "fetch_command": f"spec-kitty charter context --action {payload.action} --profile {payload.profile_id}",
      }
  ```

  Guard it with the spec's C-002: only substitute when
  `payload.governance_context_available` and the text is non-empty; otherwise
  leave the payload exactly as today (the "Governance context unavailable"
  signal).
- JSON: build the envelope (`to_dict()` / `to_dry_run_dict()`), then set
  `envelope["governance_context_text"] = None` and add
  `envelope["governance_context_reference"]`. Do not mutate the payload.
- Console: replace the governance `Panel` with one digest line plus an indented
  fetch-command line, e.g.

  ```text
  Governance context: digest <hash> (24 bytes, 1 line) — not re-embedded (--brief)
    Fetch the full text: spec-kitty charter context --action implement --profile implementer-fixture
  ```

  Keep `_render_payload_capsule()`'s other output identical. Prefer a keyword
  (`brief=`) on the shared capsule renderer over a second copy of the body.
- Do not touch the Op write, glossary scan, recommendation or router code.

## Subtask T005 — Prove SC-002 end to end

Add a test that, on **one** fixture, compares the governance text
`dispatch --profile <id>` embeds with the text rendered by the printed fetch
command's flags through `build_charter_context` (same profile, same action,
`mark_loaded=False`). If wiring `charter context` through Typer is impractical in
the unit fixture, drive `build_charter_context` with exactly the flags the
command passes and assert equality with the dispatch text; state the choice in
your notes. The assertion must fail if `--profile` is dropped from the fetch
command (the profile block would be missing).

## Test strategy

- `uv run pytest tests/specify_cli/invocation/cli/test_dispatch.py -q`
- `uv run pytest tests/specify_cli/invocation -q` (bounded module sweep)
- Re-run the reproduction from the issue and record the new envelope size:
  `uv run spec-kitty dispatch "implement the login handler" --profile python-pedro --dry-run --json --brief | wc -c`

## Definition of Done

- Every new test failed before the implementation and passes after it.
- The non-brief output is unchanged, proven on the same fixture.
- No new state file, no session detection, no automatic suppression (spec C-001).
- `ruff check` clean for the touched files; diff-cover on changed lines ≥ 90%.

## Risks

- Emitting `null` text when the fetch command cannot reproduce it would hide
  governance; the C-002 guard prevents that.
- A second render body would drift from the capsule; keep one shared renderer.

## Reviewer guidance

- Confirm the brief console output still shows the open-Op close hint.
- Confirm the reference uses `payload.action` (e.g. `generate`), not the verb in
  the request text.
- Confirm no test asserts against a hand-written fetch string that the code could
  drift from without failing.
