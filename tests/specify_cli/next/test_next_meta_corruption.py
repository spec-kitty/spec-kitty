"""Regression: `spec-kitty next` must fail closed, not crash, on a corrupt
mission ``meta.json`` (#4642, WP03).

Root cause (grounded, file:line): ``next_cmd.py``'s ``:195-217`` try/except
wraps ONLY ``_resolve_mission_slug`` (mission *directory* resolution via
``PRIMARY_METADATA.read_dir`` -- it never parses ``meta.json`` content).  The
corrupt-meta decode escapes DOWNSTREAM of that guard, via
``query_current_state -> runtime_bridge -> load_meta_fail_closed``, from two
UNWRAPPED call sites: ``_run_query_mode(...)`` (query mode, no ``--result``)
and ``decide_next(...)`` (advancing mode, ``--result <value>``).
``MissionMetaReadError`` subclasses ``RuntimeError`` (not ``ValueError``), so
it also slips past the existing ``except ValueError`` arm at ``:215``.

This test drives the REAL ``spec-kitty next --mission <slug>`` CLI path via
``typer.testing.CliRunner`` against a mission whose ``meta.json`` is corrupt
(malformed JSON and a non-UTF-8 byte), asserting the command exits 1 with a
clean diagnostic -- never an uncaught traceback -- in both plain and
``--json`` output modes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

runner = CliRunner()

_MISSION_SLUG = "042-corrupt-meta-mission"


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate (verbatim pattern from
    ``tests/next/test_next_command_integration.py``): this fixture stages
    minimal mission state and does not run ``spec-kitty charter sync``, so
    the real preflight gate would otherwise block every call this test makes
    before it ever reaches the corrupt-meta code path under test.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_args, **_kwargs: result,
    )


# ---------------------------------------------------------------------------
# Fixture-mission builder -- verbatim-pattern reuse of
# ``tests/next/test_next_command_integration.py``'s ``_scaffold_project``
# (this repo's own established convention for this shape of fixture is to
# duplicate the helper into each consuming test file with an attribution
# comment, per ``tests/specify_cli/next/test_next_invocation_lifecycle_seam.py``).
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_project(tmp_path: Path, mission_slug: str = _MISSION_SLUG) -> Path:
    """Scaffold a minimal spec-kitty project with a mission carrying a valid
    ``meta.json`` -- corrupted afterwards by each test case."""
    repo_root = tmp_path / "project"
    repo_root.mkdir()
    _init_git_repo(repo_root)

    kittify = repo_root / ".kittify"
    kittify.mkdir()
    provision_test_charter(repo_root)

    from specify_cli.identity.project import ensure_identity

    ensure_identity(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "software-dev"}),
        encoding="utf-8",
    )
    return repo_root


def _meta_path(repo_root: Path, mission_slug: str = _MISSION_SLUG) -> Path:
    return repo_root / "kitty-specs" / mission_slug / "meta.json"


_TRACEBACK_MARKER = "Traceback (most recent call last)"
_DOCTOR_HINT = "spec-kitty doctor"


def _assert_clean_fail_closed(result, meta_path: Path) -> None:
    """Shared assertions: exit 1, no raw traceback, corrupt file named, doctor hint."""
    assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}; output={result.output!r}"
    assert result.exception is None or isinstance(result.exception, SystemExit), (
        f"expected a clean typer.Exit (SystemExit) or no exception, got {result.exception!r} "
        f"({type(result.exception).__name__ if result.exception else 'None'}); output={result.output!r}"
    )
    assert _TRACEBACK_MARKER not in result.output, f"raw traceback leaked into output: {result.output!r}"
    assert meta_path.name in result.output, f"expected the corrupt file to be named in output; output={result.output!r}"
    assert _DOCTOR_HINT in result.output, f"expected a '{_DOCTOR_HINT}' remediation hint; output={result.output!r}"


class TestNextMetaCorruptionFailsClosed:
    """`spec-kitty next` on a corrupt ``meta.json`` must exit 1 with a clean
    diagnostic -- never an uncaught traceback (#4642)."""

    def test_malformed_json_query_mode_plain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)
        meta_path = _meta_path(repo_root)
        meta_path.write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(cli_app, ["next", "--mission", _MISSION_SLUG])

        _assert_clean_fail_closed(result, meta_path)

    def test_non_utf8_byte_query_mode_plain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)
        meta_path = _meta_path(repo_root)
        # A lone 0xFF byte is invalid UTF-8 and cannot be decoded as text.
        meta_path.write_bytes(b'{"mission_type": "software-dev", "bad": "\xff"}')

        result = runner.invoke(cli_app, ["next", "--mission", _MISSION_SLUG])

        _assert_clean_fail_closed(result, meta_path)

    def test_malformed_json_query_mode_json_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)
        meta_path = _meta_path(repo_root)
        meta_path.write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(cli_app, ["next", "--mission", _MISSION_SLUG, "--json"])

        assert result.exit_code == 1, f"expected exit 1, got {result.exit_code}; output={result.output!r}"
        assert result.exception is None or isinstance(result.exception, SystemExit), (
            f"expected a clean typer.Exit (SystemExit) or no exception, got {result.exception!r}; output={result.output!r}"
        )
        assert _TRACEBACK_MARKER not in result.output, f"raw traceback leaked into output: {result.output!r}"
        payload = json.loads(result.stdout)
        assert payload["result"] == "error"
        rendered = json.dumps(payload)
        assert meta_path.name in rendered, f"expected the corrupt file named in the JSON payload; payload={payload!r}"
        assert _DOCTOR_HINT in rendered, f"expected a '{_DOCTOR_HINT}' remediation hint in the JSON payload; payload={payload!r}"

    def test_malformed_json_advancing_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The escape site also reaches ``decide_next`` on an advancing (``--result``) call."""
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)
        meta_path = _meta_path(repo_root)
        meta_path.write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(
            cli_app,
            ["next", "--agent", "test-agent", "--mission", _MISSION_SLUG, "--result", "success"],
        )

        _assert_clean_fail_closed(result, meta_path)
