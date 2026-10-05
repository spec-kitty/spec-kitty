# WP07 review feedback (cycle 1) — REQUEST_CHANGES

Reviewer: cursor:claude:reviewer-renata:reviewer. Everything else in WP07 checks out
(see "Verified OK" below); one defect is blocking.

## Blocking

### B1. The submit instruction tells the agent to put the human's free text inside double quotes — shell command injection and silent mangling

The canonical block (`src/specify_cli/feedback/agent_block.py::_BLOCK_BODY`, and its byte-identical
copies in `packs/built-in/missions/mission-steps/software-dev/{tasks,tasks-finalize}/prompt.md`) says:

```
spec-kitty feedback --agent-submit ... --rating <1-5> [--comment "<text>"] [--email "<address>"] --consent yes --json
```

There is no stdin/file alternative on the CLI (`--comment`/`--email` are argv only), so an agent
that follows this literally builds a double-quoted shell string from the human's words.
Reproduced against the real CLI with a loopback server and isolated config dir
(`/tmp/wp07_replay.py`, step 5), running the line exactly as the block shows it:

- `--comment "nice $(touch X) \`touch X2\` it's"` -> **both `touch` commands executed** (marker files created)
  and the comment was delivered as `"nice   it's"` (text silently destroyed).
- `--comment "she said "hi""` -> exit 0, handed off, quote content silently mangled.

Developers routinely write backticked command names ("the `tasks` step is slow") in free-text feedback;
those would be executed in the human's shell. This ships to every consumer via `packs/built-in/`.

Required fix (wording only; stays inside WP07's owned files — no CLI change needed):
1. In `_BLOCK_BODY`, show the optional values single-quoted: `[--comment '<text>'] [--email '<address>']`.
2. Add one short sentence right under that code block, e.g.:
   "Pass `<text>` and `<address>` as single-quoted shell arguments, writing each `'` inside them as `'\''`; never put the human's words in double quotes (`$(...)` and backticks would run)."
3. Update both pack prompts to the identical rendered text (the drift test must stay green; regenerate by
   copying the rendered block, then re-run `spec-kitty doctrine regenerate-graph` — expected no manifest change).
4. Add a test in `test_agent_block.py` that asserts the rendered block (both `cli_driven` values, every trigger)
   contains no `--comment "` / `--email "` and does contain the single-quote instruction; confirm it is red first.
5. Re-run the `tests/specify_cli/feedback` suite, the regression/skills/shims/tool_surface groups, and the
   pack-manifest regen byte-identity check; record counts.

(If you prefer to fix it at the CLI by adding a stdin option for the comment, that is WP05 scope and needs a
mission-level decision; the wording fix above is sufficient and smaller.)

## Non-blocking (may fold in the same cycle, or follow up)

N1. `tasks/prompt.md`: the block sits directly after the "Do NOT skip the question" implement-handoff ask, so an agent
may ask the survey in the same turn as (or after the user's reply to) the handoff question. Consider adding
"after the handoff question has been answered" or moving the block before the handoff.
N2. `SKILL.md` "After closing" and the dispatch capsule line do not mention the consent step / `--consent yes` (the JSON
`survey.consent_question` carries "Send feedback?" but `--agent-submit` without `--consent yes` just returns `not_sent`).
Add three words ("then ask Send feedback?; submit with `--consent yes`") to the SKILL paragraph.
N3. New hunk in `tests/architectural/test_docs_cli_reference_parity.py` (the `pack_feedback = {...}` set comprehension) is not
ruff-format-clean (file is in the formatter-debt ratchet so the gate is not tripped); format the new lines.
N4. Of the 1ae62c44c "red-first" tests only `test_block_limits_itself_to_one_ask_per_session` was genuinely red (1 failed / 12 passed);
the no-endpoint and real-flag tests were green on arrival, i.e. regression guards rather than red-first. Fine as guards; just do not
describe them as red-first.

## Verified OK (no action)

Real-CLI replay (loopback, isolated config): no endpoint -> `action none`, nothing written; submit -> exactly 1 POST;
skip -> 0 POSTs; never -> `prompts_off` persisted, later checks `none`; submit without consent -> 0 POSTs, `not_sent`;
second check same week -> `throttled`. All flags/values in the block exist on `spec-kitty feedback` (`test_block_flags_are_real_feedback_options`
+ replay). Drift test, T041 gate (retired glob replaced; floor + zero-match control + pack-scan control; mutated
glob -> RED), parity-test edit (net +29 lines, no weakening, collateral reformat fully undone), mypy --strict, ruff check,
pack manifest regeneration byte-identical, no generated agent dirs edited, dispatch JSON unchanged.
