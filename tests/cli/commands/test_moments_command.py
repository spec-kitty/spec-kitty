"""#190: ``spec-kitty moments off|on|status`` — the one-line switch.

Covers: the default answer when nothing is configured anywhere, both write
scopes (global ``~/.kittify/config.toml`` vs the per-repo
``<root>/.kittify/config.toml`` override), that ``status`` names WHICH file
decided the effective mode once both exist, the ``--json`` machine form,
and the refusal when ``--repo`` runs outside any Spec Kitty checkout. The
server-side consequence of ``off`` (mcp-serve exits 0 with one line) is
covered by ``tests/zeitgeist_client/test_mcp_stdio.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import tomllib
import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.moments import moments_app
from specify_cli.cli.console import console

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture()
def kittify_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated developer home: ``~/.kittify`` resolves here for the whole
    test, and the process starts OUTSIDE any Spec Kitty checkout so the
    repo-override branch of resolution stays out of the picture until a test
    deliberately walks into one."""
    home = tmp_path / "kittify-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    # SPECIFY_REPO_ROOT is an authoritative override (core/paths Tier 1); a
    # CI/worker value pointing at some real checkout would silently turn
    # every resolution here into "inside a project". Determinism: gone.
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    checkout = tmp_path / "plain-dir"
    checkout.mkdir()
    monkeypatch.chdir(checkout)
    return home


def _checkout_with_kittify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "checkout"
    (root / ".kittify").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


# --- status ------------------------------------------------------------------


def test_status_defaults_to_team_from_no_file_at_all(kittify_home: Path) -> None:
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "team" in result.stdout
    assert "source=default" in result.stdout


def test_status_json_is_plain_machine_json(kittify_home: Path) -> None:
    result = runner.invoke(moments_app, ["status", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agents"] == "team"
    assert payload["agents_source"] == "default"
    assert payload["rate_per_minute"] > 0


def test_status_names_the_global_file_that_decided(kittify_home: Path) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nagents = "off"\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "off" in result.stdout
    assert str(kittify_home / "config.toml") in result.stdout


def test_status_keeps_hidden_bridge_command_out_of_user_output(kittify_home: Path) -> None:
    """A public status response must not teach users a hidden command path."""
    (kittify_home / "config.toml").write_text('[moments]\nagents = "off"\n')

    result = runner.invoke(moments_app, ["status"])

    assert result.exit_code == 0
    assert "agent-context bridge refuses to start" in result.stdout
    assert "mcp-serve" not in result.stdout


def test_status_reports_a_malformed_filter_as_invalid_not_as_no_filter(kittify_home: Path) -> None:
    """#201 squad follow-up: a typo'd `teammates` value must not read as
    "(no filter)" — that phrasing is what a developer expects for an unset
    filter (no restriction), not for one that failed closed to nothing."""
    (kittify_home / "config.toml").write_text('[moments]\nagents = "team"\nteammates = "lynn"\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "teammates: " in result.stdout
    assert "invalid" in result.stdout
    assert "no filter" not in result.stdout.split("teammates:")[1].split("\n")[0]


def _assert_literal_config_status(stdout: str) -> None:
    assert "invalid value '[/]'; failing closed to off" in " ".join(stdout.split())
    assert "teammates: [/]" in stdout


@pytest.mark.parametrize("home_name", ["home", "h" * 132], ids=["short-path", "wrapped-path"])
def test_status_prints_config_values_as_literal_text(kittify_home: Path, monkeypatch: pytest.MonkeyPatch, home_name: str) -> None:
    """PR #201 MAJOR: Rich markup in config must not crash status."""
    # Relative config provenance makes wrapping independent of the host temp path.
    monkeypatch.chdir(kittify_home)
    kittify_home = Path(home_name)
    kittify_home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", home_name)
    monkeypatch.setattr(console, "size", (80, 25))
    (kittify_home / "config.toml").write_text('[moments]\nagents = "[/]"\nteammates = ["[/]"]\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    _assert_literal_config_status(result.stdout)

    # Corrupt real rendered output: whitespace tolerance must not hide lost content.
    for original, replacement in (
        ("invalid", ""),
        ("value", ""),
        ("invalid", "in valid"),
        ("'[/]'", "''"),
        ("teammates: [/]", "teammates: "),
        ("[/]", ""),
    ):
        damaged = result.stdout.replace(original, replacement)
        assert damaged != result.stdout
        with pytest.raises(AssertionError):
            _assert_literal_config_status(damaged)


def test_status_json_reports_invalid_filters_as_a_sorted_list(kittify_home: Path) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nagents = "team"\nteammates = "lynn"\n')
    result = runner.invoke(moments_app, ["status", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["invalid_filters"] == ["teammates"]


def test_status_warns_on_a_kinds_entry_that_is_not_a_known_family_name(kittify_home: Path) -> None:
    """#210: #190's own examples spell ``kinds`` dotted (``wp.move``); the
    real wire vocabulary is the family name (``WPStatusChanged``). A
    developer who copies that spelling must see why it will never match,
    not just a quiet, seemingly-active filter."""
    (kittify_home / "config.toml").write_text('[moments]\nkinds = ["wp.move"]\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "kinds: wp.move" in result.stdout
    assert "wp.move" in result.stdout.split("kinds:")[1].split("\n")[1]
    assert "not a known event-kind name" in result.stdout


def test_status_json_reports_unknown_kinds(kittify_home: Path) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nkinds = ["wp.move"]\n')
    result = runner.invoke(moments_app, ["status", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["kinds_unknown"] == ["wp.move"]


def test_status_does_not_warn_on_a_known_family_name(kittify_home: Path) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nkinds = ["WPStatusChanged"]\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "kinds: WPStatusChanged" in result.stdout
    assert "not a known event-kind name" not in result.stdout


def test_status_reports_a_repo_override_over_the_global_value(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both files present: repo wins AND status says so — "quiet in THIS
    checkout only" must be visible as exactly that."""
    (kittify_home / "config.toml").write_text('[moments]\nagents = "team"\nkinds = ["WPStatusChanged"]\n')
    root = _checkout_with_kittify(tmp_path, monkeypatch)
    (root / ".kittify" / "config.toml").write_text('[moments]\nagents = "off"\n')

    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "off" in result.stdout
    assert str(root / ".kittify" / "config.toml") in result.stdout
    assert "kinds: WPStatusChanged" in result.stdout  # unoverridden keys still come through


def test_status_reports_global_off_not_widened_by_repo_team(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nagents = "off"\n')
    root = _checkout_with_kittify(tmp_path, monkeypatch)
    (root / ".kittify" / "config.toml").write_text('[moments]\nagents = "team"\n')

    result = runner.invoke(moments_app, ["status"])

    assert result.exit_code == 0
    assert result.stdout.splitlines()[0] == f"off  source={kittify_home / 'config.toml'}"


# --- off / on ----------------------------------------------------------------


def test_off_writes_the_global_config_and_reports_effective_mode(kittify_home: Path) -> None:
    result = runner.invoke(moments_app, ["off"])
    assert result.exit_code == 0
    assert "off" in result.stdout
    with (kittify_home / "config.toml").open("rb") as fh:
        stored = tomllib.load(fh)
    assert stored == {"moments": {"agents": "off"}}
    assert "effective: off" in result.stdout.replace("**", "")


def test_on_restores_the_documented_default_after_an_off(kittify_home: Path) -> None:
    runner.invoke(moments_app, ["off"])
    result = runner.invoke(moments_app, ["on"])
    assert result.exit_code == 0
    with (kittify_home / "config.toml").open("rb") as fh:
        stored = tomllib.load(fh)
    assert stored["moments"]["agents"] == "team"
    assert "effective: team" in result.stdout.replace("**", "")


def test_on_reports_honestly_when_a_repo_override_still_decides(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``on`` written globally cannot beat a repo override saying off — the
    command re-reads and prints the truth instead of the intent."""
    (kittify_home / "config.toml").write_text('[moments]\nagents = "mine"\n')
    root = _checkout_with_kittify(tmp_path, monkeypatch)
    (root / ".kittify" / "config.toml").write_text('[moments]\nagents = "off"\n')

    result = runner.invoke(moments_app, ["on"])
    assert result.exit_code == 0
    assert "effective: off" in result.stdout.replace("**", "")


def test_off_with_repo_scope_writes_the_checkout_override(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout_with_kittify(tmp_path, monkeypatch)
    result = runner.invoke(moments_app, ["off", "--repo"])
    assert result.exit_code == 0
    override = root / ".kittify" / "config.toml"
    assert override.exists()
    with override.open("rb") as fh:
        assert tomllib.load(fh)["moments"]["agents"] == "off"
    assert not (kittify_home / "config.toml").exists(), "global scope stayed untouched"


def test_repo_scope_outside_any_checkout_refuses(kittify_home: Path) -> None:
    result = runner.invoke(moments_app, ["off", "--repo"])
    assert result.exit_code == 1
    assert "--repo needs a Spec Kitty checkout" in result.stdout


def test_repo_scope_inside_git_checkout_without_kittify_refuses(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = tmp_path / "git-checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.chdir(checkout)

    result = runner.invoke(moments_app, ["off", "--repo"])

    assert result.exit_code == 1
    assert "--repo needs a Spec Kitty checkout" in result.stdout


def test_off_preserves_unrelated_keys_in_an_existing_config(kittify_home: Path) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nkinds = ["MissionCreated"]\n[other]\nkeep = "yes"\n')
    result = runner.invoke(moments_app, ["off"])
    assert result.exit_code == 0
    with (kittify_home / "config.toml").open("rb") as fh:
        document = tomllib.load(fh)
    assert document["moments"] == {"kinds": ["MissionCreated"], "agents": "off"}
    assert document["other"] == {"keep": "yes"}


def test_status_reports_disjoint_allowlists(kittify_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (kittify_home / "config.toml").write_text('[moments]\nteammates = ["alice"]\n')
    root = _checkout_with_kittify(tmp_path, monkeypatch)
    (root / ".kittify" / "config.toml").write_text('[moments]\nteammates = ["bob"]\n')
    result = runner.invoke(moments_app, ["status"])
    assert result.exit_code == 0
    assert "allowlists do not overlap" in result.stdout
    result = runner.invoke(moments_app, ["status", "--json"])
    assert json.loads(result.stdout)["blocked_filters"] == ["teammates"]
