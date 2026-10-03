"""Canonical Feedback Survey Check block for agent-facing surfaces.

Prompt-backed pack sources cannot import this module (layer rule:
``kernel <- charter <- {runtime, …} <- specify_cli``), so they carry an exact
rendered copy between :data:`PACK_BLOCK_BEGIN` / :data:`PACK_BLOCK_END`. A drift
test keeps the copies equal to :func:`render_feedback_survey_block`.
"""

from __future__ import annotations

from collections.abc import Mapping

from specify_cli.feedback.models import SurveyTrigger

__all__ = [
    "BLOCK_HEADING",
    "PACK_BLOCK_BEGIN",
    "PACK_BLOCK_END",
    "TRIGGER_BY_COMMAND",
    "append_feedback_survey_check",
    "op_close_guidance_line",
    "render_feedback_survey_block",
]

BLOCK_HEADING = "## Feedback Survey Check"

PACK_BLOCK_BEGIN = "<!-- spec-kitty:feedback-survey-check:begin -->"
PACK_BLOCK_END = "<!-- spec-kitty:feedback-survey-check:end -->"

TRIGGER_BY_COMMAND: Mapping[str, SurveyTrigger] = {
    "tasks": SurveyTrigger.PLANNING_COMPLETE,
    "tasks-finalize": SurveyTrigger.PLANNING_COMPLETE,
    "consolidate": SurveyTrigger.MISSION_END,
}

_CLI_DRIVEN_PREFIX = "Run the command above with `SPEC_KITTY_NON_INTERACTIVE=1` so it never waits for terminal input."

# Contract literal assembled from short source lines so ruff E501 stays clean;
# adjacent-string concatenation must match the pack-prompt copy byte-for-byte.
_BLOCK_BODY = (
    "## Feedback Survey Check\n"
    "\n"
    "Run this once per session, only after the command above has succeeded, and only when "
    "a human is in the loop (skip it entirely in unattended or automated runs):\n"
    "\n"
    "```bash\n"
    "spec-kitty feedback --agent-check --trigger {trigger} "
    "--agent <your-agent-key> --json\n"
    "```\n"
    "\n"
    "If JSON `action` is `none`, continue silently; do not mention the survey.\n"
    "If `action` is `prompt`, ask the human using your host-native question UI "
    "(plain text if you have none), with the exact wording from the JSON "
    "`survey` object: the rating (1-5), the optional comment, and the optional "
    'email. Then ask the consent question "Send feedback?". Offer "Skip" and '
    "\"Don't ask again\" at the first question. Never answer on the human's "
    "behalf and never pre-fill answers. If the comment is longer than "
    "`comment_max_length`, tell the human it will be cut before asking for "
    "consent.\n"
    "\n"
    "Record exactly one result:\n"
    "\n"
    "```bash\n"
    "spec-kitty feedback --agent-submit --trigger {trigger} "
    "--agent <your-agent-key> --rating <1-5> [--comment '<text>'] "
    "[--email '<address>'] --consent yes --json\n"
    "spec-kitty feedback --agent-choice skip --trigger {trigger} --json"
    "    # human skipped or declined\n"
    "spec-kitty feedback --agent-choice never --trigger {trigger} --json"
    '   # human chose "Don\'t ask again"\n'
    "```\n"
    "\n"
    "Pass `<text>` and `<address>` as single-quoted shell arguments, writing each `'` inside "
    "them as `'\\''`, and collapse newlines to spaces; never put the human's words in double "
    "quotes (`$(...)` and backticks would run).\n"
    "\n"
    "Show the returned `message` if present, then continue. Never report "
    "delivery problems: sending is fire-and-forget.\n"
)


def render_feedback_survey_block(trigger: SurveyTrigger, *, cli_driven: bool) -> str:
    """Return the canonical Feedback Survey Check block for *trigger*."""
    body = _BLOCK_BODY.format(trigger=trigger.value).rstrip() + "\n"
    if not cli_driven:
        return body
    # Insert the non-interactive sentence immediately after the heading.
    heading, _, rest = body.partition("\n")
    return f"{heading}\n\n{_CLI_DRIVEN_PREFIX}\n{rest}"


def append_feedback_survey_check(body: str, command: str, *, cli_driven: bool) -> str:
    """Append the survey-check block for trigger *command*, idempotently."""
    trigger = TRIGGER_BY_COMMAND.get(command)
    if trigger is None:
        return body
    if BLOCK_HEADING in body:
        return body
    block = render_feedback_survey_block(trigger, cli_driven=cli_driven)
    if not body:
        return block
    return f"{body.rstrip()}\n\n{block}"


def op_close_guidance_line() -> str:
    """One-line guidance for the dispatch capsule after closing an Op."""
    return (
        "When a human is in the loop, only after closing the Op with outcome `done` or `failed` "
        "(never `abandoned`) run: "
        "spec-kitty feedback --agent-check --trigger op_close "
        "--agent <your-agent-key> --json "
        "(skip silently if action is none; never answer on the human's behalf; "
        'if action is prompt, ask "Send feedback?" and submit with --consent yes).'
    )
