"""Unit tests for the terminal Feedback Survey form (WP05 / T029)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import pytest

from specify_cli.feedback import wording
from specify_cli.feedback.payload import COMMENT_MAX_LENGTH
from specify_cli.feedback.terminal_form import FormResult, run_form

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _sequence(*answers: str) -> Callable[[str], str]:
    pending = list(answers)

    def _ask(prompt: str) -> str:
        assert pending, f"unexpected prompt with empty queue: {prompt!r}"
        return pending.pop(0)

    return _ask


def test_happy_path_asks_exactly_four_questions() -> None:
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        mapping = {
            wording.RATING_QUESTION: "4",
            wording.comment_question(): "faster",
            wording.EMAIL_QUESTION: "",
            f"{wording.CONSENT_QUESTION} [y/N]": "y",
        }
        return mapping[prompt]

    result = run_form(allow_never=False, ask=ask)
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert int(result.answers.rating) == 4
    assert result.answers.comment == "faster"
    assert result.answers.email is None
    assert len(prompts) == 4


def test_declined_consent() -> None:
    result = run_form(
        allow_never=False,
        ask=_sequence("3", "", "", "n"),
    )
    assert result == FormResult(outcome="declined", answers=None)


def test_skip_empty_rating() -> None:
    result = run_form(allow_never=False, ask=_sequence(""))
    assert result.outcome == "skipped"


def test_skip_with_s() -> None:
    result = run_form(allow_never=False, ask=_sequence("s"))
    assert result.outcome == "skipped"


def test_never_when_allowed() -> None:
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return "never"

    result = run_form(allow_never=True, ask=ask)
    assert result.outcome == "never"
    assert wording.RATING_TERMINAL_HINT in prompts[0]


def test_never_invalid_when_not_allowed_then_submit() -> None:
    result = run_form(
        allow_never=False,
        ask=_sequence("never", "5", "", "", "y"),
    )
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert int(result.answers.rating) == 5


def test_reask_on_bad_rating() -> None:
    result = run_form(
        allow_never=False,
        ask=_sequence("9", "2", "note", "", "yes"),
    )
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert int(result.answers.rating) == 2
    assert result.answers.comment == "note"


def test_comment_truncation_notice_before_consent(capsys: pytest.CaptureFixture[str]) -> None:
    long = "x" * (COMMENT_MAX_LENGTH + 50)
    result = run_form(
        allow_never=False,
        ask=_sequence("1", long, "", "y"),
    )
    assert result.outcome == "submitted"
    assert result.comment_truncated is True
    assert result.answers is not None
    assert result.answers.comment is not None
    assert len(result.answers.comment) == COMMENT_MAX_LENGTH
    captured = capsys.readouterr().out
    assert wording.comment_truncated_notice() in captured


def test_comment_prompt_states_limit_before_input() -> None:
    prompts: list[str] = []
    answers = iter(["4", "", "", "n"])

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    run_form(allow_never=False, ask=ask)
    comment_prompt = prompts[1]
    assert f"up to {COMMENT_MAX_LENGTH} characters" in comment_prompt
    assert comment_prompt == wording.comment_question()


def test_email_reask_once(capsys: pytest.CaptureFixture[str]) -> None:
    result = run_form(
        allow_never=False,
        ask=_sequence("3", "", "not-an-email", "ok@example.test", "y"),
    )
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert result.answers.email == "ok@example.test"
    assert wording.EMAIL_MALFORMED_NOTICE in capsys.readouterr().out


def test_aborted_on_keyboard_interrupt() -> None:
    def ask(_prompt: str) -> str:
        raise KeyboardInterrupt

    assert run_form(allow_never=False, ask=ask).outcome == "aborted"


def test_aborted_on_eof() -> None:
    def ask(_prompt: str) -> str:
        raise EOFError

    assert run_form(allow_never=False, ask=ask).outcome == "aborted"


def test_aborted_on_click_abort() -> None:
    """typer.prompt raises typer.Abort on EOF — must become aborted."""
    import typer

    def ask(_prompt: str) -> str:
        raise typer.Abort()

    assert run_form(allow_never=False, ask=ask).outcome == "aborted"


def test_first_question_timeout_posix_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    monkeypatch.setattr(tf.sys, "platform", "linux")
    monkeypatch.setattr(tf, "_read_line_posix", lambda _t, _s: None)
    result = run_form(
        allow_never=True,
        first_question_timeout_s=0.01,
        ask=_sequence("should-not-run"),
    )
    assert result.outcome == "skipped"


def test_first_question_timeout_posix_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    monkeypatch.setattr(tf.sys, "platform", "linux")
    monkeypatch.setattr(tf, "_read_line_posix", lambda _t, _s: "4")
    result = run_form(
        allow_never=True,
        first_question_timeout_s=1.0,
        ask=_sequence("", "", "y"),
    )
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert int(result.answers.rating) == 4


def test_first_question_timeout_windows_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    monkeypatch.setattr(tf.sys, "platform", "win32")
    monkeypatch.setattr(tf, "_read_line_windows", lambda _t, _s: None)
    result = run_form(
        allow_never=True,
        first_question_timeout_s=0.01,
        ask=_sequence("nope"),
    )
    assert result.outcome == "skipped"


def test_first_question_timeout_windows_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    monkeypatch.setattr(tf.sys, "platform", "win32")
    monkeypatch.setattr(tf, "_read_line_windows", lambda _t, _s: "2")
    result = run_form(
        allow_never=True,
        first_question_timeout_s=1.0,
        ask=_sequence("", "", "y"),
    )
    assert result.outcome == "submitted"
    assert result.answers is not None
    assert int(result.answers.rating) == 2


def test_posix_select_timeout_and_input(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    class _FakeStdin:
        def readline(self) -> str:
            return "3\n"

    monkeypatch.setattr(tf.select, "select", lambda *_a, **_k: ([], [], []))
    assert tf._read_line_posix(0.01, _FakeStdin()) is None  # type: ignore[arg-type]

    monkeypatch.setattr(tf.select, "select", lambda *_a, **_k: ([object()], [], []))
    assert tf._read_line_posix(1.0, _FakeStdin()) == "3"  # type: ignore[arg-type]


def test_windows_msvcrt_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    hits: Iterator[bool] = iter([False, False, True])
    fake_msvcrt = MagicMock()
    fake_msvcrt.kbhit = lambda: next(hits)

    class _FakeStdin:
        def readline(self) -> str:
            return "5\n"

    monkeypatch.setitem(__import__("sys").modules, "msvcrt", fake_msvcrt)
    monkeypatch.setattr(tf.time, "sleep", lambda _s: None)
    # Force import path to see our fake module.
    monkeypatch.setattr(tf.time, "monotonic", MagicMock(side_effect=[0.0, 0.01, 0.02, 0.03]))
    assert tf._read_line_windows(1.0, _FakeStdin()) == "5"  # type: ignore[arg-type]

    # Timeout path: never hits keyboard before deadline.
    fake_msvcrt.kbhit = lambda: False
    monkeypatch.setattr(tf.time, "monotonic", MagicMock(side_effect=[0.0, 0.5, 1.1]))
    assert tf._read_line_windows(1.0, _FakeStdin()) is None  # type: ignore[arg-type]


def test_timed_readers_raise_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.feedback.terminal_form as tf

    class _EmptyStdin:
        def readline(self) -> str:
            return ""

    monkeypatch.setattr(tf.select, "select", lambda *_a, **_k: ([object()], [], []))
    with pytest.raises(EOFError):
        tf._read_line_posix(1.0, _EmptyStdin())  # type: ignore[arg-type]

    fake_msvcrt = MagicMock()
    fake_msvcrt.kbhit = lambda: True
    monkeypatch.setitem(__import__("sys").modules, "msvcrt", fake_msvcrt)
    monkeypatch.setattr(tf.time, "monotonic", MagicMock(side_effect=[0.0, 0.01]))
    with pytest.raises(EOFError):
        tf._read_line_windows(1.0, _EmptyStdin())  # type: ignore[arg-type]
