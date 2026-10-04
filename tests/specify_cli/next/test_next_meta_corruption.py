"""CLI smoke: `spec-kitty next` fails closed, not crashes, on a corrupt
mission ``meta.json`` (#4642 -- fixed; this is a permanent guard).

The per-mode guard lives in ``test_next_cmd_meta_dispatch.py``: stub-level units
for ``_dispatch_query_mode`` and ``_dispatch_advancing_mode`` (plain and
``--json``), with the function that raises stubbed.  This file keeps ONE
end-to-end smoke through the real entry point, run once per mode.  Advancing mode
(``--result``) also exercises the lifecycle-pairing step that runs before
``decide_next``, which the unit seams stub out.  Query mode is the path the
original #4642 crash took, and only this smoke reads a really corrupt file on it.

Root cause (history): the corrupt-meta decode escaped DOWNSTREAM of the
slug-resolution guard in ``next_cmd.py`` via
``query_current_state -> runtime_bridge -> load_meta_fail_closed``.
``MissionMetaReadError`` subclasses ``RuntimeError`` (not ``ValueError``), so it
also slipped past the existing ``except ValueError`` arm.

The smoke drives the REAL ``spec-kitty next --mission <slug> [--agent <a> --result success] --json`` path via
``typer.testing.CliRunner`` against a mission whose ``meta.json`` is malformed,
asserting exit 1 with a clean JSON diagnostic -- never an uncaught traceback.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

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
        "specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only",
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


class TestNextMetaCorruptionFailsClosed:
    """`spec-kitty next` on a corrupt ``meta.json`` must exit 1 with a clean
    diagnostic -- never an uncaught traceback (#4642)."""

    @pytest.mark.parametrize(
        "mode_args",
        [pytest.param([], id="query"), pytest.param(["--agent", "test-agent", "--result", "success"], id="advancing")],
    )
    def test_malformed_json_fails_closed_with_json_output(self, mode_args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = _scaffold_project(tmp_path)
        monkeypatch.chdir(repo_root)
        meta_path = _meta_path(repo_root)
        meta_path.write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(cli_app, ["next", "--mission", _MISSION_SLUG, *mode_args, "--json"])

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
