"""CLI-boundary reject-not-drop coverage for #2529/#2530 (squad NIT, Fix D).

``_resolve_config_activated_ids`` (``charter.activation.compiler``) raises
:class:`~charter.activation.kind_vocabulary.UnknownArtifactIdError` (a ``ValueError``
subclass) for a ``config.activated_*`` stem that cannot be resolved to a
canonical doctrine artifact -- reject, not silently drop (C-006). This module
pins that the two CLI entry points that reach that resolution path
(``spec-kitty charter generate`` and ``spec-kitty charter synthesize``) turn
that exception into a clean, actionable, non-zero exit -- never a raw Python
traceback on stdout -- for both the plain-console and ``--json`` output modes:

- ``generate.py`` catches ``(FileExistsError, TaskCliError, ValueError,
  RuntimeError)``; ``UnknownArtifactIdError`` is a ``ValueError``, so it lands
  in that branch (``_emit_error``, not the "Unexpected error" branch).
- ``synthesize.py`` has no explicit ``ValueError``/``UnknownArtifactIdError``
  handler; the error falls through to its final generic ``except Exception``
  branch, which still emits a single parseable JSON failure envelope (or a
  clean console line) -- never an uncaught traceback.
"""

from __future__ import annotations

import json
from collections.abc import Callable
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from charter.activation.kind_vocabulary import UnknownArtifactIdError
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True, capture_output=True)


def _write_stale_activation_config(repo: Path) -> None:
    """A ``.kittify/config.yaml`` activating a directive stem that does not exist.

    ``mission_type_activations`` is provisioned here too -- unrelated to the
    stale-directive-stem rejection this module pins, but WP04 (C-A1) made it a
    hard construction precondition for ``PackContext.from_config``; without it
    the CLI would reject on the missing key before ever reaching the
    stale-stem resolution path this test exercises.
    """
    config_dir = repo / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\nactivated_directives:\n  - does-not-exist-directive-stem\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# `spec-kitty charter generate`: real end-to-end (no mocking) -- the config
# reader, the compiler, and the CLI error boundary are all exercised for real.
# --------------------------------------------------------------------------- #


def test_generate_json_rejects_stale_config_stem_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init(tmp_path)
    _write_stale_activation_config(tmp_path)

    monkeypatch.chdir(tmp_path)
    # catch_exceptions=False: if the CLI ever stops catching this error
    # class, this test fails on the raw traceback instead of silently
    # passing on a swallowed assertion -- proving "caught", not "dodged".
    result = runner.invoke(
        charter_app,
        ["generate", "--no-from-interview", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0, f"generate must reject a stale activated stem; got exit 0: {result.output!r}"
    assert "Traceback" not in result.output

    payload = json.loads(result.stdout)
    assert payload["result"] == "error"
    assert payload["success"] is False
    error_message = payload["error"]
    assert "does-not-exist-directive-stem" in error_message
    assert "activated_directives" in error_message
    assert ".kittify/config.yaml" in error_message

    # Reject-not-drop: no charter bundle was materialized from the invalid run.
    assert not (tmp_path / ".kittify" / "charter" / "charter.md").exists()


def test_generate_console_rejects_stale_config_stem_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init(tmp_path)
    _write_stale_activation_config(tmp_path)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        ["generate", "--no-from-interview"],
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "does-not-exist-directive-stem" in result.output
    assert "activated_directives" in result.output
    assert "Error:" in result.output


# --------------------------------------------------------------------------- #
# `spec-kitty charter synthesize`: the fresh-project short-circuit only
# triggers when `.kittify/charter/charter.md` exists, so a bare tmp_path
# without it reaches the real synthesis-request build path. That path pulls
# doctrine-authoring fixtures well beyond this WP's scope, so the resolver
# failure is injected directly at its call site (`_build_synthesis_request`)
# -- exercising the real, unmodified `synthesize.py` exception boundary
# against the exact exception class `compile_charter`'s config-sourced
# derivation raises.
# --------------------------------------------------------------------------- #


def test_synthesize_json_surfaces_unknown_artifact_id_without_traceback(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    stale_stem_error = UnknownArtifactIdError(
        "No directive artifact with config ID 'does-not-exist-directive-stem' found under "
        "doctrine root /fake/doctrine. Check `.kittify/config.yaml` activated_directives for "
        "a stale or misspelled entry, or run `spec-kitty doctor charter-packs` to verify the "
        "doctrine corpus (including any org packs) is intact."
    )

    charter_cwd_isolation()
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=type("_Evidence", (), {"warnings": [], "bundle": object()})(),
        ),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            side_effect=stale_stem_error,
        ),
    ):
        result = runner.invoke(
            charter_app,
            ["synthesize", "--json"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "Traceback" not in result.output

    payload = json.loads(result.stdout)
    assert payload["result"] == "failure"
    warnings = payload["warnings"]
    assert any("does-not-exist-directive-stem" in w for w in warnings)
    assert any("activated_directives" in w for w in warnings)


def test_synthesize_console_surfaces_unknown_artifact_id_without_traceback(tmp_path: Path, charter_cwd_isolation: Callable[..., Path]) -> None:
    stale_stem_error = UnknownArtifactIdError(
        "No directive artifact with config ID 'does-not-exist-directive-stem' found under "
        "doctrine root /fake/doctrine. Check `.kittify/config.yaml` activated_directives for "
        "a stale or misspelled entry, or run `spec-kitty doctor charter-packs` to verify the "
        "doctrine corpus (including any org packs) is intact."
    )

    charter_cwd_isolation()
    with (
        patch("specify_cli.cli.commands.charter.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.charter._collect_evidence_result",
            return_value=type("_Evidence", (), {"warnings": [], "bundle": object()})(),
        ),
        patch(
            "specify_cli.cli.commands.charter._build_synthesis_request",
            side_effect=stale_stem_error,
        ),
    ):
        result = runner.invoke(
            charter_app,
            ["synthesize"],
            catch_exceptions=False,
        )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "does-not-exist-directive-stem" in result.output
    assert "activated_directives" in result.output
