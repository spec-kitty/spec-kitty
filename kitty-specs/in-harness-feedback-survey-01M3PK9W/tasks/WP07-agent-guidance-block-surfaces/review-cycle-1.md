---
affected_files: []
cycle_number: 1
mission_slug: in-harness-feedback-survey-01M3PK9W
reproduction_command:
reviewed_at: '2026-10-01T07:52:40Z'
reviewer_agent: cursor:claude:reviewer-renata:reviewer
wp_id: WP07
---

# WP07 review feedback (cycle 1) — REQUEST_CHANGES

Reviewer: reviewer-renata (independent). Scope reviewed: base `9e7c7c2e6..HEAD` in lane-g.

Everything else in WP07 checks out (see verdict summary); two defects are blocking because
they make the *agent-facing instructions* wrong against the spec / unsafe to follow literally.

## Blocking

### B1 — op_close guidance ignores the done|failed-only rule (FR-006, research R-09)

FR-006: the survey is offered after an Op is closed with outcome `done` or `failed`, **not**
`abandoned`. WP06's CLI hook honours that, but the two *agent-facing* op_close surfaces tell the
agent to run the check after closing, whatever the outcome, and `--agent-check` has no outcome
input to filter on:

- `op_close_guidance_line()` (`src/specify_cli/feedback/agent_block.py`): "…after closing the Op run: spec-kitty feedback --agent-check --trigger op_close …"
- `src/charter/offering/skills/spec-kitty/SKILL.md` "After closing": "run the Feedback Survey Check once after the Op is closed".

An agent that closes an Op `--outcome abandoned` will therefore run the check and ask the human
to rate a mis-dispatched Op.

Fix: say "after closing the Op with outcome `done` or `failed` (never `abandoned`)" in both places;
add a unit assertion on the phrase for the dispatch line and a content assertion for the SKILL.md
paragraph (see N3).

### B2 — `--comment "<text>"` teaches the agent a shell-unsafe invocation

The block shows `[--comment "<text>"]` and nothing about quoting. The human's free text is
interpolated by an LLM into a shell command inside **double quotes**. Reproduced against the real
CLI (loopback server, isolated HOME):

    spec-kitty feedback --agent-submit --trigger op_close --agent cursor --rating 3 \
      --comment "see `echo BACKTICK` and $(echo SUBST) and $HOME" --consent yes --json

submitted `comment: "see BACKTICK and SUBST and /tmp/rev-replay/home2"` — i.e. the backtick and
`$()` commands were **executed** and `$HOME` expanded into the submission (local path leak into a
payload the human consented to send as typed). An embedded `"` or a newline breaks parsing of the
command entirely. The CLI only accepts the comment via argv (no stdin form), so the instruction text
is the only mitigation.

Fix (block text, both the Python source and the two pack copies, so the drift test stays green):
tell the agent to pass the comment as a single-quoted shell argument (`'…'`, every embedded `'`
written as `'\''`), never in double quotes, and to collapse newlines to spaces; same sentence for
`--email`. Add a test pinning the sentence in `render_feedback_survey_block`. (A stdin form for the
comment is a worthwhile WP05 follow-up but out of WP07 scope.)

## Non-blocking

- N1 `tasks/prompt.md`: the block sits *after* Step 10 (the "Implementation Handoff Offer"
  question, "Do NOT skip the question"). An agent that asks the handoff question and waits will
  either skip the survey or ask two questions at once; and if the user says yes it launches a long
  implementation run first. Consider placing the block before Step 10 (still inside the markers).
- N2 Commit `1ae62c44c` is titled "red-first once-per-session, no-endpoint, real-flag" but only
  `test_block_limits_itself_to_one_ask_per_session` was RED before `b4ab89e4a`; the no-endpoint-URL
  and real-flag tests were already green (they are fine regression guards, not red-first). The
  once-per-session test is a bare substring check (`"once per session" in block`).
- N3 No test pins the SKILL.md "After closing" paragraph (surface tests cover installer, shims,
  runtime prompt, asset generator, dispatch capsule only).
- N4 "pack copies regenerated in lockstep" is a hand edit of three files; there is no regeneration
  helper, so the drift test is the only guard (verified RED under mutation of either side).
- N5 The block is ~21 lines / ~1.6 KB on every trigger surface, and for CLI-driven surfaces the
  `SPEC_KITTY_NON_INTERACTIVE=1` sentence ("Run the command above…") appears *after* the command it
  refers to. Spec-prescribed wording, so not blocking; worth tightening in a later pass.
