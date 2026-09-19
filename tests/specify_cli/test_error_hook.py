"""Global CLI error-presentation hook (mission cli-error-surface-seam-01M2WJD2,
WP01/T006).

Exercises the hook via a throwaway multi-command Typer sub-app (mirrors the
real top-level app's shape closely enough that ``app()`` behaves identically:
a raised domain exception propagates out of the click invocation rather than
being absorbed as a ``SystemExit``, and a usage error still raises
``SystemExit(2)`` from inside ``app()`` itself, before the hook's own
``except`` clause is ever reached). Asserts the four-row behavior table and
all four invariants from ``contracts/error-envelope.md``.
"""

from __future__ import annotations

import json

import pytest
import typer

from kernel.errors import GuardedReadError
from specify_cli import _run_app_with_error_hook


def _make_app() -> typer.Typer:
    app = typer.Typer()

    @app.command()
    def read_it() -> None:
        raise GuardedReadError(path="bad.yaml", reason="workflow file is not valid")

    @app.command()
    def custom_kind() -> None:
        class _WorkflowFileError(GuardedReadError):
            pass

        raise _WorkflowFileError(path="other.yaml", reason="also not valid")

    @app.command()
    def crash() -> None:
        raise RuntimeError("a genuine bug, not a domain error")

    @app.command()
    def needs_arg(value: str) -> None:
        print(value)

    @app.command()
    def ok() -> None:
        print("fine")

    return app


def test_guarded_read_error_renders_text_line_on_stderr_and_exits_1(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "read-it"])
    app = _make_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "Error: workflow file is not valid"


def test_guarded_read_error_renders_json_envelope_on_stdout_and_exits_1(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "read-it"])
    app = _make_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=True)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload == {
        "error": "workflow file is not valid",
        "kind": "GuardedReadError",
        "path": "bad.yaml",
    }


def test_guarded_read_subclass_reports_its_own_kind_in_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "custom-kind"])
    app = _make_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=True)

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "_WorkflowFileError"
    assert payload["path"] == "other.yaml"


def test_json_mode_emits_nothing_but_the_json_object_on_stdout(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """INV-1: no in-scope error path emits non-JSON prose on stdout under --json."""
    monkeypatch.setattr("sys.argv", ["prog", "read-it"])
    app = _make_app()

    with pytest.raises(SystemExit):
        _run_app_with_error_hook(app, json_mode=True)

    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    json.loads(lines[0])  # exactly one JSON object, nothing else


def test_typer_usage_error_keeps_exit_2_unconverted(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """INV-2: a Typer usage error is never intercepted or converted to exit 1."""
    monkeypatch.setattr("sys.argv", ["prog", "needs-arg"])
    app = _make_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)

    assert exc_info.value.code == 2


def test_non_domain_exception_propagates_as_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INV-3: a non-GuardedReadError exception re-raises untouched."""
    monkeypatch.setattr("sys.argv", ["prog", "crash"])
    app = _make_app()

    with pytest.raises(RuntimeError, match="a genuine bug"):
        _run_app_with_error_hook(app, json_mode=False)


def test_successful_command_exits_0_unaffected_by_the_hook(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "ok"])
    app = _make_app()

    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=False)

    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "fine"


def test_hook_is_registered_on_the_real_top_level_app() -> None:
    """FR-011 gate precursor: the hook wraps the actual assembled app in main()."""
    import inspect

    from specify_cli import main

    source = inspect.getsource(main)
    assert "_run_app_with_error_hook" in source
