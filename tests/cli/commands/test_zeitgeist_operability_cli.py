"""O1-C: ``spec-kitty zeitgeist operability`` — the thin CLI adapter over
``zeitgeist_client.operability``'s payload-free signals and local drills.

Mirrors ``test_zeitgeist_command.py``'s own patterns: no
``--relay-url``/``--token`` option on any subcommand (the credential comes
solely from ``credentials.py``'s existing store, same as ``status``/
``watch``), ``--json`` emits the dataclass verbatim via the canonical
console seam, and the drill commands never touch a real relay or a real
controlling terminal.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.zeitgeist import app
from specify_cli.zeitgeist_client import credentials, outbox_approval

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture()
def state_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "spec-kitty-home"))
    return tmp_path / "spec-kitty-home"


@pytest.fixture()
def no_git_ancestry_inside_tmp_path(tmp_path: Path) -> None:
    """Pin the ancestor-origin-leak boundary (#441/#589's shape; the same
    boundary is pinned separately in ``tests/zeitgeist_client/test_mcp_stdio.py``
    and ``test_resolution.py``): without this, a test that ``chdir``s into a
    repo-less ``tmp_path`` subdirectory and asserts resolution fails closed
    can instead walk upward past ``tmp_path`` into whatever git checkout the
    pytest ``--basetemp`` happens to sit inside (e.g. this repo's own
    working tree on an exe.dev VM) and mint THAT checkout's identity instead
    of failing.

    A real, originless ``git init`` at ``tmp_path`` stops the walk there —
    for BOTH resolution paths ``store_key_for_checkout`` consults: the real
    ``git`` subprocess ``repo_identity.Deadline.run`` shells out to (which
    requires a genuine repository, not merely a ``.git``-shaped directory,
    to treat a directory as a discovery boundary) and the no-subprocess
    ``_git_dir_from_filesystem`` filesystem reader (which stops at the
    first ``.git`` directory it finds, real or not). No ``origin`` remote
    is configured, so both still resolve to "no identity here"."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True, text=True)


# --- no runtime URL/credential option on any operability subcommand ---------


@pytest.mark.parametrize(
    "args",
    [
        ["operability", "report", "--help"],
        ["operability", "drill-timeout", "--help"],
        ["operability", "drill-rotation", "--help"],
        ["operability", "drill-rollback", "--help"],
    ],
)
def test_operability_subcommand_has_no_relay_url_or_credential_option(args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    for forbidden in ("--relay-url", "--token", "--credential", "--runtime-url"):
        assert forbidden not in result.stdout


def test_operability_group_is_registered() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "operability" in result.stdout


# --- report -------------------------------------------------------------


def test_operability_report_json_offline_reports_honest_staleness(state_root: Path) -> None:
    result = runner.invoke(app, ["operability", "report", "github.com/acme/spec-kitty", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["repo"] == "github.com/acme/spec-kitty"
    assert payload["credential_checked_out"] is False
    assert payload["offer"] is None
    assert payload["lease"]["active"] is False
    assert payload["lease"]["ttl_s"] == 90


def test_operability_report_human_readable_mentions_every_signal(state_root: Path) -> None:
    result = runner.invoke(app, ["operability", "report", "github.com/acme/spec-kitty"])
    assert result.exit_code == 0
    for label in ("lease", "revoke", "mcp", "repair"):
        assert label in result.stdout


def test_operability_report_reflects_a_stored_checkout(state_root: Path) -> None:
    credentials.store(repo="github.com/acme/spec-kitty", relay_url="http://127.0.0.1:9", token="tok", token_kind="shared_team")
    result = runner.invoke(app, ["operability", "report", "github.com/acme/spec-kitty", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["credential_checked_out"] is True
    assert "tok" not in result.stdout  # never echoes the credential value


# --- drill-timeout --------------------------------------------------------


def test_operability_drill_timeout_json_passes_without_a_repo_argument(state_root: Path) -> None:
    result = runner.invoke(app, ["operability", "drill-timeout", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pass"
    assert payload["drop"]["dropped"] is True


def test_operability_drill_timeout_under_drain_off_prints_the_skip_outcome(state_root: Path, drain_off: None) -> None:
    """A clean drain-off skip renders its distinct outcome string -- see
    ``test_drill_outcome_color`` below for the colour it is never rendered
    in (CliRunner's captured stdout is markup-stripped plain text, so the
    colour itself is not observable through this seam)."""
    result = runner.invoke(app, ["operability", "drill-timeout"])
    assert result.exit_code == 0
    assert "skipped: drain off" in result.stdout


@pytest.mark.parametrize(
    ("outcome", "expected_color"),
    [("pass", "green"), ("fail", "red"), ("skipped: drain off", "yellow")],
)
def test_drill_outcome_color(outcome: str, expected_color: str) -> None:
    """#4737's own misdiagnosis class: a clean drain-off skip must render in
    neither the pass (green) nor the failure (red) colour."""
    from specify_cli.cli.commands.zeitgeist import _drill_outcome_color

    assert _drill_outcome_color(outcome) == expected_color


# --- drill-rotation --------------------------------------------------------


def test_operability_drill_rotation_json_reports_not_checked_out(state_root: Path) -> None:
    result = runner.invoke(app, ["operability", "drill-rotation", "github.com/acme/spec-kitty", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pass"
    assert payload["checked_out"] is False


# --- drill-rollback ---------------------------------------------------------


def test_operability_drill_rollback_json_blocks_before_a_human_gesture(state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom():
        raise AssertionError("CLI drill-rollback must never open the controlling terminal")

    monkeypatch.setattr(outbox_approval, "_controlling_tty", _boom)
    result = runner.invoke(app, ["operability", "drill-rollback", "github.com/acme/spec-kitty", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "pass"
    assert payload["blocked_reason"] == "not_yet_approved"


# --- repo omitted / bare name (#137: the store key is host/owner/repo) -------


def test_operability_report_with_no_repo_argument_uses_the_checkout_derived_key(state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running inside the checkout reports THAT checkout's auto-minted
    ``host/owner/repo`` entry as checked out — the #137 acceptance path,
    which a user-typed bare name could never reach after #132."""
    credentials.store(repo="github.com/acme/widget", relay_url="http://127.0.0.1:9", token="tok", token_kind="shared_team")
    monkeypatch.setattr("specify_cli.zeitgeist_client.resolution.store_key_for_checkout", lambda cwd: "github.com/acme/widget")
    result = runner.invoke(app, ["operability", "report", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["repo"] == "github.com/acme/widget"
    assert payload["credential_checked_out"] is True


def test_operability_drill_rotation_with_no_repo_argument_derives_from_checkout(state_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    credentials.store(repo="github.com/acme/widget", relay_url="http://127.0.0.1:9", token="tok", token_kind="presence")
    monkeypatch.setattr("specify_cli.zeitgeist_client.resolution.store_key_for_checkout", lambda cwd: "github.com/acme/widget")
    result = runner.invoke(app, ["operability", "drill-rotation", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["checked_out"] is True


@pytest.mark.git_repo
@pytest.mark.parametrize("command", ["report", "drill-rotation", "drill-rollback"])
def test_operability_subcommand_with_no_repo_and_no_checkout_exits_nonzero(
    state_root: Path,
    command: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_git_ancestry_inside_tmp_path: None,
) -> None:
    """Outside any resolvable checkout there is nothing to derive from; the
    command names the accepted form instead of guessing."""
    outside = tmp_path / "not-a-checkout"
    outside.mkdir()
    monkeypatch.chdir(outside)
    result = runner.invoke(app, ["operability", command, "--json"])
    assert result.exit_code == 1
    assert "host/owner/repo" in result.stdout


@pytest.mark.parametrize("command", ["report", "drill-rotation", "drill-rollback"])
def test_operability_subcommand_rejects_a_bare_repo_name(state_root: Path, command: str) -> None:
    result = runner.invoke(app, ["operability", command, "widget"])
    assert result.exit_code == 1
    assert "host/owner/repo" in result.stdout
