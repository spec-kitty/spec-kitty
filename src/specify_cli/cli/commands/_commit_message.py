"""Commit-message assembly for the ``-m/--message`` option (#5647).

``spec-kitty safe-commit`` and ``spec-kitty spec-commit`` accept ``-m`` more
than once and join the values the way ``git commit -m a -m b`` does: each
value is one paragraph, separated by a blank line. A subject, a body and a
trailer can therefore be passed as three ``-m`` values without losing any.
"""

from __future__ import annotations

from collections.abc import Sequence

MESSAGE_OPTION_HELP = "Commit message. Repeat -m to add paragraphs (joined by a blank line, the same way git does)."


def join_message_paragraphs(paragraphs: Sequence[str]) -> str:
    """Join repeated ``-m`` values into one commit message, git-style.

    Values that are empty after stripping are dropped, as git drops them.

    Raises:
        ValueError: no non-empty paragraph was given.
    """
    kept = [p.strip() for p in paragraphs if p.strip()]
    if not kept:
        raise ValueError("Commit message is empty.")
    return "\n\n".join(kept)
