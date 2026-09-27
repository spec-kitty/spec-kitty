"""#4971 (FR-007/FR-014/FR-015): ``spec-kitty moments drain on|off|status`` —
the operator surface for the two-scope live-drain posture.

Covers: writing the personal (runtime-root ``config.toml``) and repository
(``.kittify/config.yaml``) scopes without clobbering unrelated keys, the D7
fail-closed refusal on an unparseable personal config, the ``status`` /
``status --json`` reporting of effective posture + per-scope provenance +
narrowers + all four hosted-posture file paths, the ledger posture line, and
the help text stating the two-scopes-both-on / no-env-can-enable rules
(R-1). ``@pytest.mark.real_drain_posture`` is required on every test that
asserts the real, file-based effective posture -- the root autouse fixture
otherwise pins drain on for every other test in the suite.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.core import hosted_posture
from specify_cli.paths import get_runtime_root
from specify_cli.cli.commands.moments import moments_app

pytestmark = [pytest.mark.fast, pytest.mark.real_drain_posture]

runner = CliRunner()


def _checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "checkout"
    (root / ".kittify").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


# --- drain on / off — personal (default) scope --------------------------------


def test_drain_on_writes_the_runtime_root_config_toml(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(moments_app, ["drain", "on"])
    assert result.exit_code == 0
    expected_path = get_runtime_root().base / "config.toml"
    assert str(expected_path) in result.stdout
    with expected_path.open("rb") as fh:
        document = tomllib.load(fh)
    assert document["hosted"]["drain"] is True


def test_drain_on_preserves_other_keys_in_the_runtime_root_config(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = get_runtime_root().base / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('[sync]\nserver_url = "https://spec-kitty-dev.example.internal"\n')

    result = runner.invoke(moments_app, ["drain", "on"])

    assert result.exit_code == 0
    with config_path.open("rb") as fh:
        document = tomllib.load(fh)
    assert document["sync"]["server_url"] == "https://spec-kitty-dev.example.internal"
    assert document["hosted"]["drain"] is True


def test_drain_off_writes_false_to_the_runtime_root_config(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(moments_app, ["drain", "on"])
    result = runner.invoke(moments_app, ["drain", "off"])
    assert result.exit_code == 0
    config_path = get_runtime_root().base / "config.toml"
    with config_path.open("rb") as fh:
        document = tomllib.load(fh)
    assert document["hosted"]["drain"] is False


def test_drain_on_over_unparseable_config_exits_one_and_leaves_file_unchanged(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = get_runtime_root().base / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = b"not [ valid toml"
    config_path.write_bytes(original_bytes)

    result = runner.invoke(moments_app, ["drain", "on"])

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    assert str(config_path) in result.stdout
    assert config_path.read_bytes() == original_bytes
    # Review issue 3b: markup=False on a string containing the literal tag
    # text prints the tag itself instead of styling it -- assert the tag
    # never leaks into the rendered line.
    assert "[red]Error:[/red]" not in result.stdout
    assert "left" in result.stdout and "unchanged" in result.stdout


# --- drain on / off — repo scope ------------------------------------------------


def test_drain_on_repo_writes_hosted_drain_to_kittify_config_yaml(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    result = runner.invoke(moments_app, ["drain", "on", "--repo"])
    assert result.exit_code == 0
    config_path = root / ".kittify" / "config.yaml"
    assert config_path.exists()
    assert str(config_path) in result.stdout
    from ruamel.yaml import YAML

    document = YAML(typ="safe").load(config_path)
    assert document["hosted"]["drain"] is True


def test_drain_on_repo_preserves_other_top_level_keys(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    config_path = root / ".kittify" / "config.yaml"
    config_path.write_text("env_file: ${SPEC_KITTY_HOME}/.kitty.env\n")

    result = runner.invoke(moments_app, ["drain", "on", "--repo"])

    assert result.exit_code == 0
    from ruamel.yaml import YAML

    document = YAML(typ="safe").load(config_path)
    assert document["env_file"] == "${SPEC_KITTY_HOME}/.kitty.env"
    assert document["hosted"]["drain"] is True


def test_drain_off_repo_writes_false(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on", "--repo"])
    result = runner.invoke(moments_app, ["drain", "off", "--repo"])
    assert result.exit_code == 0
    from ruamel.yaml import YAML

    document = YAML(typ="safe").load(root / ".kittify" / "config.yaml")
    assert document["hosted"]["drain"] is False


def test_drain_on_repo_over_malformed_config_yaml_exits_one_and_leaves_file_unchanged(
    canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review issue 3a: a malformed repo ``.kittify/config.yaml`` must refuse
    with one line and exit 1, never a Rich traceback, and leave the file's
    bytes exactly as they were."""
    root = _checkout(tmp_path, monkeypatch)
    config_path = root / ".kittify" / "config.yaml"
    original_bytes = b"key: [unclosed"
    config_path.write_bytes(original_bytes)

    result = runner.invoke(moments_app, ["drain", "on", "--repo"])

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    assert str(config_path) in result.stdout
    assert config_path.read_bytes() == original_bytes
    assert "[red]Error:[/red]" not in result.stdout


def test_drain_off_repo_over_malformed_config_yaml_exits_one_and_leaves_file_unchanged(
    canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _checkout(tmp_path, monkeypatch)
    config_path = root / ".kittify" / "config.yaml"
    original_bytes = b"{not: valid: yaml: at: all"
    config_path.write_bytes(original_bytes)

    result = runner.invoke(moments_app, ["drain", "off", "--repo"])

    assert result.exit_code == 1
    assert "Traceback" not in result.stdout
    assert config_path.read_bytes() == original_bytes


def test_drain_repo_scope_outside_checkout_refuses(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "plain-dir"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    result = runner.invoke(moments_app, ["drain", "on", "--repo"])
    assert result.exit_code == 1
    assert "--repo needs a Spec Kitty checkout" in result.stdout


# --- drain status ----------------------------------------------------------------


def test_drain_status_reports_off_by_default(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(moments_app, ["drain", "status"])
    assert result.exit_code == 0
    assert "effective: off" in result.stdout


def test_drain_status_reports_on_when_both_scopes_are_on(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])
    runner.invoke(moments_app, ["drain", "on", "--repo"])

    result = runner.invoke(moments_app, ["drain", "status"])

    assert result.exit_code == 0
    assert "effective: on" in result.stdout
    assert str(root / ".kittify" / "config.yaml") in result.stdout


def test_drain_status_reports_both_scopes_values_and_sources(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])

    result = runner.invoke(moments_app, ["drain", "status"])

    assert result.exit_code == 0
    assert "repository:" in result.stdout
    assert "personal:" in result.stdout
    assert str(get_runtime_root().base / "config.toml") in result.stdout
    assert str(root / ".kittify" / "config.yaml") in result.stdout


def test_drain_status_reports_all_four_hosted_posture_files_even_when_absent(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(moments_app, ["drain", "status"])
    assert result.exit_code == 0
    runtime_root = get_runtime_root().base
    assert str(runtime_root / "config.toml") in result.stdout
    from specify_cli.zeitgeist_client import moments as _moments

    assert str(_moments.global_config_path()) in result.stdout


def test_drain_status_json_files_map_has_all_four_labelled_entries(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills mutation M7: removing the ``"personal (hosted.drain)"`` entry
    from ``_drain_posture_files`` still left the earlier "all four files"
    test passing, because it only substring-checked 2 of the 4 paths and
    never inspected the labelled ``files`` map itself. Assert every one of
    the four keys and their exact, resolved paths through ``--json``,
    including the repo-scoped path that only exists inside a checkout and
    the "absent" placeholder outside one."""
    from specify_cli.zeitgeist_client import moments as _moments

    runtime_root = get_runtime_root().base

    # Outside any checkout: repo-scoped paths read as "absent" placeholders.
    monkeypatch.chdir(tmp_path)
    result_outside = runner.invoke(moments_app, ["drain", "status", "--json"])
    assert result_outside.exit_code == 0
    files_outside = json.loads(result_outside.stdout)["files"]
    assert set(files_outside) == {
        "repository (hosted.drain)",
        "repository ([moments])",
        "global ([moments])",
        "personal (hosted.drain)",
    }
    assert files_outside["personal (hosted.drain)"] == str(runtime_root / "config.toml")
    assert files_outside["global ([moments])"] == str(_moments.global_config_path())
    assert files_outside["repository ([moments])"] == "(no repository checkout found)"

    # Inside a checkout: both repo-scoped entries resolve to real paths.
    root = _checkout(tmp_path, monkeypatch)
    result_inside = runner.invoke(moments_app, ["drain", "status", "--json"])
    assert result_inside.exit_code == 0
    files_inside = json.loads(result_inside.stdout)["files"]
    assert files_inside["repository (hosted.drain)"] == str(root / ".kittify" / "config.yaml")
    assert files_inside["repository ([moments])"] == str(root / ".kittify" / "config.toml")
    assert files_inside["personal (hosted.drain)"] == str(runtime_root / "config.toml")


def test_drain_status_reports_the_no_moment_handlers_narrower(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])
    runner.invoke(moments_app, ["drain", "on", "--repo"])
    monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")

    result = runner.invoke(moments_app, ["drain", "status"])

    assert result.exit_code == 0
    assert "effective: off" in result.stdout
    assert "SPEC_KITTY_NO_MOMENT_HANDLERS" in result.stdout
    assert root  # keeps the checkout fixture referenced for clarity


def test_drain_status_json_narrowers_list_contains_the_env_narrower(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills mutation M1: removing ``narrowers.append(posture.narrowed_by)``
    from ``_drain_narrowers`` still left the earlier assertion passing,
    because the env-var name also appears in the ``reason`` string. Assert
    the structured ``payload["narrowers"]`` list directly, independent of
    ``reason``."""
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])
    runner.invoke(moments_app, ["drain", "on", "--repo"])
    monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")

    result = runner.invoke(moments_app, ["drain", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert any("SPEC_KITTY_NO_MOMENT_HANDLERS" in narrower for narrower in payload["narrowers"])
    assert root


def test_drain_status_reports_the_moments_agents_off_narrower(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])
    runner.invoke(moments_app, ["drain", "on", "--repo"])
    runner.invoke(moments_app, ["off"])  # [moments] agents = "off", global scope

    result = runner.invoke(moments_app, ["drain", "status"])

    assert result.exit_code == 0
    assert 'agents = "off"' in result.stdout
    assert root  # checkout fixture used for the repo-scoped drain write above


def test_drain_status_json_emits_a_plain_json_object(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    runner.invoke(moments_app, ["drain", "on"])
    runner.invoke(moments_app, ["drain", "on", "--repo"])

    result = runner.invoke(moments_app, ["drain", "status", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["effective"] is True
    assert payload["repository"]["value"] is True
    assert payload["personal"]["value"] is True
    assert isinstance(payload["narrowers"], list)
    assert "ledger" in payload
    assert payload["ledger"]["enabled"] is True
    assert "files" in payload
    assert str(root / ".kittify" / "config.yaml") in payload["files"].values()


def test_drain_status_reports_ledger_posture(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _checkout(tmp_path, monkeypatch)
    (root / ".kittify" / "config.yaml").write_text("ledger:\n  projection: false\n")

    result = runner.invoke(moments_app, ["drain", "status"])

    assert result.exit_code == 0
    assert "ledger: off" in result.stdout


def test_drain_status_shows_the_exact_guidance_line_when_off(canonical_home: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(moments_app, ["drain", "status"])
    assert result.exit_code == 0
    assert "Live drain is off (" in result.stdout
    assert "spec-kitty moments drain on [--repo]" in result.stdout
    assert hosted_posture.DRAIN_GUIDANCE_LINE.split("{reason}")[0] in result.stdout


# --- help text ---------------------------------------------------------------


def test_drain_help_states_both_scopes_and_no_env_var(canonical_home: None) -> None:
    result = runner.invoke(moments_app, ["drain", "--help"])
    assert result.exit_code == 0
    lowered = result.stdout.lower()
    assert "both" in lowered
    assert "environment variable" in lowered
    # Review issue 2: Rich markup must not swallow the literal `[hosted]`
    # table name -- an unescaped `[hosted]` in Typer's rich-rendered --help
    # is parsed as a (nonexistent) style tag and disappears from the output.
    assert "[hosted] drain" in result.stdout


def test_drain_on_help_states_both_scopes_and_no_env_var(canonical_home: None) -> None:
    result = runner.invoke(moments_app, ["drain", "on", "--help"])
    assert result.exit_code == 0
    lowered = result.stdout.lower()
    assert "both" in lowered
    assert "environment variable" in lowered
    assert "[hosted] drain" in result.stdout


def test_drain_on_repo_help_describes_config_yaml_not_the_moments_files(canonical_home: None) -> None:
    """Review issue 1: `drain on --help` reused the generic moments
    `--repo`/global-scope help, which names the WRONG files for drain
    (`.kittify/config.toml` and "the global home .kittify config"). The
    drain-specific option help must name drain's own two files."""
    result = runner.invoke(moments_app, ["drain", "on", "--help"])
    assert result.exit_code == 0
    assert "config.yaml" in result.stdout
    assert "hosted.drain" in result.stdout
    # The wrong, moments-mode file name must not appear as the --repo target.
    assert "config.toml) instead of the global home" not in result.stdout


def test_drain_off_repo_help_describes_config_yaml_not_the_moments_files(canonical_home: None) -> None:
    result = runner.invoke(moments_app, ["drain", "off", "--help"])
    assert result.exit_code == 0
    assert "config.yaml" in result.stdout
    assert "hosted.drain" in result.stdout


def test_drain_on_help_names_the_full_config_path_and_the_hosted_drain_key(canonical_home: None) -> None:
    """Mutation M9: the two existing config.yaml/hosted.drain checks above
    would still pass if the help text named some OTHER ``config.yaml`` (e.g.
    a bare filename with no directory) and ``hosted.drain`` in unrelated
    sentences. Pin the exact, load-bearing substrings so ``spec-kitty
    moments drain on --help`` genuinely tells the operator which file and
    which key it writes."""
    result = runner.invoke(moments_app, ["drain", "on", "--help"])
    assert result.exit_code == 0
    assert ".kittify/config.yaml" in result.stdout
    assert "hosted.drain" in result.stdout
