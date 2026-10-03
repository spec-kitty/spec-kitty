"""Interactive terminal Feedback Survey form.

Reusable by the on-demand ``spec-kitty feedback`` command (WP05) and by
inline trigger offers (WP06). At most four interactions (NFR-008): rating,
comment, email, consent. Never raises ``KeyboardInterrupt`` / ``EOFError`` /
``typer.Abort`` to the caller — those become outcome ``aborted``.
"""

from __future__ import annotations

import select
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TextIO

import typer

from specify_cli.feedback.models import Rating, SurveyAnswers
from specify_cli.feedback.payload import normalize_comment, parse_email, parse_rating
from specify_cli.feedback import wording

__all__ = [
    "FormResult",
    "run_form",
]

_FormOutcome = Literal["submitted", "declined", "skipped", "never", "aborted"]
_Ask = Callable[[str], str]

_SKIP_TOKENS = frozenset({"", "s"})
# Survey "don't ask again" token — not a credential (bandit S105 false positive on name).
_STOP_ASKING_TOKEN = "never"  # noqa: S105
_CONSENT_YES = frozenset({"y", "yes"})
_WINDOWS_POLL_S = 0.05
# typer.prompt raises typer.Abort (click.exceptions.Abort) on EOF/Ctrl-C — not EOFError.
_ABORT_EXCEPTIONS = (KeyboardInterrupt, EOFError, typer.Abort)


@dataclass(frozen=True)
class FormResult:
    """Outcome of one terminal form run."""

    outcome: _FormOutcome
    answers: SurveyAnswers | None
    comment_truncated: bool = False


def run_form(
    *,
    allow_never: bool,
    first_question_timeout_s: float | None = None,
    ask: _Ask | None = None,
) -> FormResult:
    """Run the four-step Feedback Survey form. Never raises to the caller."""
    prompt = ask if ask is not None else _default_ask
    try:
        return _run_form_body(
            allow_never=allow_never,
            first_question_timeout_s=first_question_timeout_s,
            ask=prompt,
        )
    except _ABORT_EXCEPTIONS:
        return FormResult(outcome="aborted", answers=None)


def _run_form_body(
    *,
    allow_never: bool,
    first_question_timeout_s: float | None,
    ask: _Ask,
) -> FormResult:
    rating = _ask_rating(
        allow_never=allow_never,
        first_question_timeout_s=first_question_timeout_s,
        ask=ask,
    )
    if isinstance(rating, FormResult):
        return rating

    comment_raw = ask(wording.comment_question())
    comment, truncated = normalize_comment(comment_raw)
    if truncated:
        typer.echo(wording.comment_truncated_notice())

    email = _ask_email(ask)
    consent_raw = ask(f"{wording.CONSENT_QUESTION} [y/N]").strip().casefold()
    if consent_raw not in _CONSENT_YES:
        return FormResult(outcome="declined", answers=None, comment_truncated=truncated)

    return FormResult(
        outcome="submitted",
        answers=SurveyAnswers(rating=rating, comment=comment, email=email),
        comment_truncated=truncated,
    )


def _ask_rating(
    *,
    allow_never: bool,
    first_question_timeout_s: float | None,
    ask: _Ask,
) -> Rating | FormResult:
    prompt_text = wording.RATING_QUESTION
    if allow_never:
        prompt_text = f"{prompt_text} ({wording.RATING_TERMINAL_HINT})"

    first = True
    while True:
        if first and first_question_timeout_s is not None:
            raw = _read_line_with_timeout(prompt_text, first_question_timeout_s)
            if raw is None:
                return FormResult(outcome="skipped", answers=None)
        else:
            raw = ask(prompt_text)
        first = False

        token = raw.strip()
        folded = token.casefold()
        if folded in _SKIP_TOKENS:
            return FormResult(outcome="skipped", answers=None)
        if folded == _STOP_ASKING_TOKEN:
            if allow_never:
                return FormResult(outcome="never", answers=None)
            # Invalid when never is not allowed — re-ask.
            continue
        parsed = parse_rating(token)
        if parsed is not None:
            return parsed
        # Invalid rating — re-ask (untimed).


def _ask_email(ask: _Ask) -> str | None:
    raw = ask(wording.EMAIL_QUESTION)
    value, ok = parse_email(raw)
    if ok:
        return value
    typer.echo(wording.EMAIL_MALFORMED_NOTICE)
    raw2 = ask(wording.EMAIL_QUESTION)
    value2, ok2 = parse_email(raw2)
    return value2 if ok2 else None


def _default_ask(prompt: str) -> str:
    return str(typer.prompt(prompt, default="", show_default=False))


def _read_line_with_timeout(prompt: str, timeout_s: float) -> str | None:
    """Read one line with a wall-clock timeout; ``None`` on timeout.

    Platform branch is isolated here so unit tests can monkeypatch either
    the POSIX ``select`` path or the Windows ``msvcrt`` path.
    """
    typer.echo(prompt, nl=False)
    typer.echo(" ", nl=False)
    if sys.platform.startswith("win"):
        return _read_line_windows(timeout_s, sys.stdin)
    return _read_line_posix(timeout_s, sys.stdin)


def _read_line_posix(timeout_s: float, stdin: TextIO) -> str | None:
    ready, _w, _x = select.select([stdin], [], [], timeout_s)
    if not ready:
        typer.echo("")
        return None
    line = stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n\r")


def _read_line_windows(timeout_s: float, stdin: TextIO) -> str | None:
    # Lazy import via importlib so POSIX hosts never need the module present;
    # tests inject a fake ``msvcrt`` into ``sys.modules`` before calling this.
    import importlib
    from collections.abc import Callable
    from typing import cast

    msvcrt = importlib.import_module("msvcrt")
    kbhit = cast(Callable[[], bool], msvcrt.kbhit)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if kbhit():
            line = stdin.readline()
            if line == "":
                raise EOFError
            return line.rstrip("\n\r")
        time.sleep(_WINDOWS_POLL_S)
    typer.echo("")
    return None
