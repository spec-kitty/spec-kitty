"""Guard `spec-kitty agent release prep` against 3 pyproject.toml failure modes.

Mission cli-error-surface-seam-01M2WJD2, WP04 (issue #4637). Proves, through the
real ``spec-kitty agent release prep`` CLI entry point (never by calling
``_read_current_version`` directly), that each of the following modes now
raises a single typed ``ReleasePyprojectError`` that the WP01 global hook
renders uniformly at exit 1 -- never a raw Python traceback:

  A. Missing ``pyproject.toml``.
  B. ``pyproject.toml`` present but missing ``[project].version`` (both the
     "no ``[project]`` table at all" and the "``[project]`` table without a
     ``version`` key" sub-cases).
  C. Malformed/unparseable TOML syntax.

Invoked via the real, production ``release`` Typer sub-app (the same
``specify_cli.cli.commands.agent.release.app`` object ``tests/release/test_release_prep.py``
already exercises for the happy path) routed through ``_run_app_with_error_hook``
-- the exact hook function ``main()`` wires onto the assembled top-level app --
with ``sys.argv`` patched. This reaches the real ``prep`` command function and
the real presentation hook without the unrelated top-level CLI bootstrap
(logging/completion/global-asset-repair) that ``main()`` also runs and that a
call to the fully-assembled root app would trigger on every invocation. A
plain ``typer.testing.CliRunner`` invocation of ``release.app`` alone (the
happy-path test's own pattern) would bypass the hook entirely -- ``CliRunner``
catches the raised exception itself -- and could not observe the clean text
line / JSON envelope the hook renders.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from specify_cli import _run_app_with_error_hook
from specify_cli.cli.commands.agent.release import app as release_app
from specify_cli.release.payload import ReleasePyprojectError

pytestmark = [pytest.mark.integration]


def _invoke(tmp_path: Path, *, json_mode: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    # `release_app` has exactly one registered command ("prep"), so Typer
    # promotes it to single-command mode -- no "prep" subcommand token.
    argv = ["spec-kitty-release", "--channel", "alpha", "--repo", str(tmp_path)]
    if json_mode:
        argv.append("--json")
    monkeypatch.setattr("sys.argv", argv)
    _run_app_with_error_hook(release_app, json_mode=json_mode)


def _write_pyproject(tmp_path: Path, body: str) -> None:
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# Scenario A -- missing pyproject.toml
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_missing_pyproject_exits_1_with_clean_text_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario A, no --json: clean `Error: <reason>` line, exit 1."""
    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=False, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().startswith("Error: ")


@pytest.mark.regression
def test_missing_pyproject_json_emits_single_error_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario A, --json: one {error,kind,path} object on stdout, exit 1."""
    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=True, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["kind"] == "ReleasePyprojectError"
    assert payload["path"] == str(tmp_path / "pyproject.toml")
    assert isinstance(payload["error"], str) and payload["error"]


# ---------------------------------------------------------------------------
# Scenario B -- present but missing [project].version
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.parametrize(
    "body",
    [
        pytest.param("", id="no-project-table-at-all"),
        pytest.param(
            dedent(
                """\
                [project]
                name = "spec-kitty-cli"
                """
            ),
            id="project-table-without-version-key",
        ),
    ],
)
def test_missing_version_key_exits_1_with_clean_text_error(tmp_path: Path, body: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario B, no --json: clean `Error: <reason>` line, exit 1."""
    _write_pyproject(tmp_path, body)

    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=False, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().startswith("Error: ")


@pytest.mark.regression
@pytest.mark.parametrize(
    "body",
    [
        pytest.param("", id="no-project-table-at-all"),
        pytest.param(
            dedent(
                """\
                [project]
                name = "spec-kitty-cli"
                """
            ),
            id="project-table-without-version-key",
        ),
    ],
)
def test_missing_version_key_json_emits_single_error_object(tmp_path: Path, body: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario B, --json: one {error,kind,path} object on stdout, exit 1."""
    _write_pyproject(tmp_path, body)

    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=True, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["kind"] == "ReleasePyprojectError"
    assert payload["path"] == str(tmp_path / "pyproject.toml")
    assert isinstance(payload["error"], str) and payload["error"]


# ---------------------------------------------------------------------------
# Scenario C -- malformed/unparseable TOML
# ---------------------------------------------------------------------------

_MALFORMED_TOML = dedent(
    """\
    [project
    name = "spec-kitty-cli"
    version = "1.0.0"
    """
)


@pytest.mark.regression
def test_malformed_toml_exits_1_with_clean_text_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario C, no --json: clean `Error: <reason>` line, exit 1."""
    _write_pyproject(tmp_path, _MALFORMED_TOML)

    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=False, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().startswith("Error: ")


@pytest.mark.regression
def test_malformed_toml_json_emits_single_error_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """#4637 Scenario C, --json: one {error,kind,path} object on stdout, exit 1."""
    _write_pyproject(tmp_path, _MALFORMED_TOML)

    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=True, monkeypatch=monkeypatch)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["kind"] == "ReleasePyprojectError"
    assert payload["path"] == str(tmp_path / "pyproject.toml")
    assert isinstance(payload["error"], str) and payload["error"]


# ---------------------------------------------------------------------------
# INV-1 -- no non-JSON prose on stdout under --json (any of the 3 modes)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_json_mode_stdout_contains_only_the_json_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """NFR-002 / INV-1: exactly one parseable JSON object, nothing else, on stdout."""
    with pytest.raises(SystemExit):
        _invoke(tmp_path, json_mode=True, monkeypatch=monkeypatch)

    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert len(lines) == 1
    json.loads(lines[0])


# ---------------------------------------------------------------------------
# Happy path -- guards against a read_guarded adoption regression
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_well_formed_pyproject_still_resolves_version_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A valid pyproject.toml still yields the correct version via the real command."""
    _write_pyproject(
        tmp_path,
        dedent(
            """\
            [project]
            name = "spec-kitty-cli"
            version = "3.1.0a7"
            """
        ),
    )
    monkeypatch.setenv("NO_COLOR", "1")

    with pytest.raises(SystemExit) as exc_info:
        _invoke(tmp_path, json_mode=True, monkeypatch=monkeypatch)

    assert exc_info.value.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["current_version"] == "3.1.0a7"


# ---------------------------------------------------------------------------
# Unit-level: the guard is wired via read_guarded / ReleasePyprojectError
# ---------------------------------------------------------------------------


def test_release_pyproject_error_is_a_guarded_read_error() -> None:
    from kernel.errors import GuardedReadError

    assert issubclass(ReleasePyprojectError, GuardedReadError)
