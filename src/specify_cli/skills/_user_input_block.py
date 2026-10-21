"""User-Input block identification and rewrite helpers.

The User-Input block in every Spec Kitty command template contains a literal
``$ARGUMENTS`` placeholder that is substituted by the command-file rendering
pipeline before an agent sees the prompt.  Skills-layer agents (Codex, Vibe)
do not perform that substitution, so the renderer replaces the block with
:data:`REPLACEMENT_BLOCK` — a natural-language instruction that directs the
model to treat the invocation turn's free-form content as the User Input.

The exact text of :data:`REPLACEMENT_BLOCK` is load-bearing and locked by a
snapshot test.  Any change to it is a deliberate version bump, not a drift.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPLACEMENT_BLOCK = (
    "## User Input\n\n"
    "The content of the user's message that invoked this skill "
    "(everything after the skill invocation token, e.g. after "
    "`/spec-kitty-<command>` or `$spec-kitty-<command>`) is the User Input "
    "referenced elsewhere in these instructions.\n\n"
    "You **MUST** consider this user input before proceeding (if not empty).\n\n"
)

# Matches the "## User Input" heading (level-2 only, optional trailing space).
_RE_USER_INPUT_START = re.compile(r"^## +User Input\s*$", re.MULTILINE)

# Matches any heading at level 1 or 2 that could terminate the block.
_RE_TERMINATING_HEADING = re.compile(r"^#{1,2} +\S", re.MULTILINE)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def identify(body: str) -> tuple[int, int] | None:
    """Return the ``(start_byte, end_byte)`` span of the User-Input block.

    The span starts at the beginning of the ``## User Input`` heading line and
    ends at (exclusive) the start of the next ``#`` or ``##`` heading.  The
    newline that precedes the next heading is **included** in the span so that
    the replacement leaves tidy spacing.

    Returns ``None`` when no ``## User Input`` heading is present.
    """
    start_match = _RE_USER_INPUT_START.search(body)
    if start_match is None:
        return None

    start = start_match.start()

    # Search for a terminating heading that starts *after* the User-Input line.
    search_from = start_match.end()
    term_match = _RE_TERMINATING_HEADING.search(body, search_from)
    end = len(body) if term_match is None else term_match.start()

    return (start, end)


def rewrite(body: str) -> str:
    """Replace the User-Input block with :data:`REPLACEMENT_BLOCK`.

    Raises :class:`specify_cli.skills.command_renderer.SkillRenderError` with
    code ``"user_input_block_missing"`` if no ``## User Input`` heading is
    found in *body*.
    """
    # Import here to avoid a circular dependency at module load time.
    from specify_cli.skills.command_renderer import SkillRenderError  # noqa: PLC0415

    span = identify(body)
    if span is None:
        raise SkillRenderError("user_input_block_missing")

    start, end = span
    return body[:start] + REPLACEMENT_BLOCK + body[end:]
