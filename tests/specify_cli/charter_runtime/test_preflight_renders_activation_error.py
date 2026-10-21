"""Charter preflight renders an activation error instead of a bare code or a traceback (WP14 T083).

The preflight runner reads activation through the ledger seam, which fails
closed with :class:`ActiveCharterConfigError` on a malformed ledger. ``spec-kitty
charter preflight`` used to print only ``preflight aborted:
ACTIVE_CHARTER_CONFIG_INVALID``, and :func:`run_preflight_or_abort` (``next``,
``implement``) let the error escape as a traceback. ``charter preflight`` now
renders the code and the error body. :func:`run_preflight_or_abort` adds no
advisory over an unreadable store and leaves the refusal to its consumer, whose
own read fails closed and names the file (``next`` blocks with ``kind: blocked``,
#4600), as on ``main``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

from specify_cli.charter_runtime.preflight import hook
from tests._support.activation_cli import cli, init_git_repo, unwrapped
from tests.next.test_next_command_integration import (
    _add_wp_files,
    _advance_runtime_to_step,
    _scaffold_project,
)

_LEDGER = Path(".kittify", "charter", "activation.yaml")
_BODY = f"Remediation: fix {_LEDGER.as_posix()}"


def _malformed_ledger_project(root: Path) -> Path:
    init_git_repo(root)
    (root / ".kittify" / "charter").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("agents: {}\n", encoding="utf-8")
    (root / _LEDGER).write_text("activated_directives: [unclosed\n", encoding="utf-8")
    return root


@pytest.mark.integration
@pytest.mark.git_repo
def test_charter_preflight_prints_the_error_body(tmp_path: Path) -> None:
    repo = _malformed_ledger_project(tmp_path / "project")
    result = cli(repo, "charter", "preflight")
    assert result.returncode == 2, unwrapped(result)
    assert "ACTIVE_CHARTER_CONFIG_INVALID" in unwrapped(result)
    assert _BODY in unwrapped(result)
    assert "Traceback" not in unwrapped(result)


@pytest.mark.fast
def test_run_preflight_or_abort_leaves_an_unreadable_store_to_its_consumer(tmp_path: Path) -> None:
    repo = _malformed_ledger_project(tmp_path / "project")
    stderr = io.StringIO()
    result = hook.run_preflight_or_abort(repo, consumer="implement", stderr=stderr)
    assert result.passed
    assert stderr.getvalue() == ""


@pytest.mark.integration
@pytest.mark.git_repo
def test_next_blocks_on_a_malformed_ledger_through_its_own_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``next --json`` reports a malformed ledger as ``kind: blocked`` naming the file, never the internal code (#4600)."""
    base = tmp_path / "base"
    base.mkdir()
    repo_root = _scaffold_project(base)
    feature_dir = repo_root / "kitty-specs" / "042-test-feature"
    _add_wp_files(feature_dir, {"WP01": "planned"})
    _advance_runtime_to_step(repo_root, "042-test-feature", "implement")
    (repo_root / _LEDGER).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / _LEDGER).write_text("activated_directives: [unclosed\n", encoding="utf-8")

    monkeypatch.chdir(repo_root)
    result = CliRunner().invoke(
        cli_app,
        ["next", "--agent", "test", "--mission", "042-test-feature", "--result", "success", "--json"],
    )

    assert result.exit_code == 1, result.output
    for leak in ("Traceback", "ActiveCharterConfigError", "ACTIVE_CHARTER_CONFIG_INVALID", "CHARTER_PREFLIGHT_FAILED"):
        assert leak not in result.output, result.output
    payload = json.loads(result.stdout)
    assert payload["kind"] == "blocked"
    assert "activation.yaml" in payload["reason"]
