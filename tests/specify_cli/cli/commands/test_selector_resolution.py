"""Selector resolution helper and command integration tests."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import patch

import click
import pytest

from tests.mocked_env import setup_mocked_env
import typer
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.cli import selector_resolution
from specify_cli.cli.commands.agent.mission import app as agent_mission_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.cli.commands.lifecycle import tasks as lifecycle_tasks
from specify_cli.cli.commands.mission import app as mission_app
from specify_cli.cli.commands.next_cmd import next_step
from specify_cli.cli.selector_resolution import resolve_selector
from runtime.next.runtime_bridge import MissionNotFoundError

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]  # non_sandbox: warning assertion fails in sandbox
runner = CliRunner()


def _build_top_level_lifecycle_app() -> typer.Typer:
    """Build a fresh local app for top-level lifecycle command tests."""
    app = typer.Typer()
    app.command(name="tasks")(lifecycle_tasks)

    @app.command(name="noop")
    def _noop() -> None:
        """Force Typer to exercise subcommand parsing in this local test app."""

    return app


@pytest.fixture(autouse=True)
def _reset_selector_resolution_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset warning state and env vars between tests."""
    selector_resolution._warned.clear()
    monkeypatch.delenv("SPEC_KITTY_SUPPRESS_FEATURE_DEPRECATION", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION", raising=False)
    yield
    selector_resolution._warned.clear()


@pytest.fixture()
def warning_stream(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Capture rendered warning output without terminal wrapping."""
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=False, color_system=None, width=200)
    monkeypatch.setattr(selector_resolution, "_err_console", console)
    return stream


def _build_task_repo(tmp_path: Path, mission_slug: str = "077-demo-mission") -> Path:
    """Create a minimal repo structure for agent task status tests."""
    repo_root = tmp_path
    (repo_root / ".kittify").mkdir()
    feature_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "WP01-demo.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Demo WP\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        "  - src/demo/**\n"
        "authoritative_surface: src/demo/\n"
        "---\n\n"
        "# WP01 Demo\n\n"
        "## Activity Log\n",
        encoding="utf-8",
    )
    return repo_root


def _extract_json(output: str) -> dict:
    """Extract the first JSON object from mixed stdout output."""
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No valid JSON found in output:\n{output}")


def test_canonical_only_returns_value(warning_stream: io.StringIO) -> None:
    result = resolve_selector(
        canonical_value="software-dev",
        canonical_flag="--mission-type",
        alias_value=None,
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.canonical_value == "software-dev"
    assert result.alias_used is False
    assert result.alias_flag is None
    assert result.warning_emitted is False
    assert warning_stream.getvalue() == ""


def test_alias_only_returns_canonical_value(warning_stream: io.StringIO) -> None:
    result = resolve_selector(
        canonical_value=None,
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.canonical_value == "software-dev"
    assert result.alias_used is True
    assert result.alias_flag == "--mission"
    assert result.warning_emitted is True
    assert "Warning: --mission is deprecated; use --mission-type." in warning_stream.getvalue()


def test_both_equal_returns_value_with_warning(warning_stream: io.StringIO) -> None:
    result = resolve_selector(
        canonical_value="software-dev",
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.canonical_value == "software-dev"
    assert result.alias_used is True
    assert result.warning_emitted is True
    assert warning_stream.getvalue().count("Warning:") == 1


def test_both_different_raises_bad_parameter() -> None:
    with pytest.raises(typer.BadParameter, match="Conflicting selectors"):
        resolve_selector(
            canonical_value="software-dev",
            canonical_flag="--mission-type",
            alias_value="research",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
        )


def test_neither_raises_bad_parameter() -> None:
    with pytest.raises(typer.BadParameter, match="--mission <slug>"):
        resolve_selector(
            canonical_value=None,
            canonical_flag="--mission-type",
            alias_value=None,
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
            command_hint="--mission <slug>",
        )


def test_both_empty_strings_raise_bad_parameter() -> None:
    with pytest.raises(typer.BadParameter, match="--mission <slug>"):
        resolve_selector(
            canonical_value="",
            canonical_flag="--mission-type",
            alias_value="",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
            command_hint="--mission <slug>",
        )


def test_canonical_whitespace_only_treated_as_none(warning_stream: io.StringIO) -> None:
    result = resolve_selector(
        canonical_value="   ",
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.canonical_value == "software-dev"
    assert result.alias_used is True
    assert result.warning_emitted is True
    assert "Warning:" in warning_stream.getvalue()


def test_warning_emitted_for_each_direct_call_without_click_context(warning_stream: io.StringIO) -> None:
    first = resolve_selector(
        canonical_value=None,
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )
    second = resolve_selector(
        canonical_value=None,
        canonical_flag="--mission-type",
        alias_value="research",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert first.warning_emitted is True
    assert second.warning_emitted is True
    assert warning_stream.getvalue().count("Warning:") == 2


def test_warning_emitted_only_once_within_click_invocation(warning_stream: io.StringIO) -> None:
    command = click.Command("dummy")
    with click.Context(command):
        first = resolve_selector(
            canonical_value=None,
            canonical_flag="--mission-type",
            alias_value="software-dev",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
        )
        second = resolve_selector(
            canonical_value=None,
            canonical_flag="--mission-type",
            alias_value="research",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
        )

    assert first.warning_emitted is True
    assert second.warning_emitted is False
    assert warning_stream.getvalue().count("Warning:") == 1


def test_warning_emitted_again_for_different_pair_in_same_click_invocation(
    warning_stream: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Dedup is keyed on (invocation, canonical_flag, alias_flag): two *distinct*
    # pairs both warn within one invocation. Only one canonical/alias pair
    # (--mission -> --mission-type) survives in production now, so stub the
    # doc-path lookup to exercise the generic key-composition contract with a
    # second synthetic pair instead of coupling to the production flag registry.
    monkeypatch.setattr(selector_resolution, "_doc_path_for", lambda _flag: "docs/migrations/x.md")
    command = click.Command("dummy")
    with click.Context(command):
        resolve_selector(
            canonical_value=None,
            canonical_flag="--mission-type",
            alias_value="software-dev",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
        )
        resolve_selector(
            canonical_value=None,
            canonical_flag="--legacy-canonical",
            alias_value="legacy-value",
            alias_flag="--legacy-alias",
            suppress_env_var="SPEC_KITTY_SUPPRESS_LEGACY_DEPRECATION",
        )

    assert warning_stream.getvalue().count("Warning:") == 2


def test_warning_emitted_again_for_different_pair(
    warning_stream: io.StringIO,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # See sibling test: two distinct (canonical, alias) pairs warn separately.
    monkeypatch.setattr(selector_resolution, "_doc_path_for", lambda _flag: "docs/migrations/x.md")
    resolve_selector(
        canonical_value=None,
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )
    resolve_selector(
        canonical_value=None,
        canonical_flag="--legacy-canonical",
        alias_value="legacy-value",
        alias_flag="--legacy-alias",
        suppress_env_var="SPEC_KITTY_SUPPRESS_LEGACY_DEPRECATION",
    )

    assert warning_stream.getvalue().count("Warning:") == 2


def test_suppression_env_var_skips_warning(
    monkeypatch: pytest.MonkeyPatch,
    warning_stream: io.StringIO,
) -> None:
    monkeypatch.setenv("SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION", "1")
    result = resolve_selector(
        canonical_value=None,
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.alias_used is True
    assert result.warning_emitted is False
    assert warning_stream.getvalue() == ""


def test_inverse_direction_works_identically(warning_stream: io.StringIO) -> None:
    result = resolve_selector(
        canonical_value="software-dev",
        canonical_flag="--mission-type",
        alias_value="software-dev",
        alias_flag="--mission",
        suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
    )

    assert result.canonical_value == "software-dev"
    assert result.alias_used is True
    assert result.alias_flag == "--mission"
    assert result.warning_emitted is True
    assert "Warning: --mission is deprecated; use --mission-type." in warning_stream.getvalue()


def test_conflict_error_format() -> None:
    with pytest.raises(typer.BadParameter) as exc_info:
        resolve_selector(
            canonical_value="software-dev",
            canonical_flag="--mission-type",
            alias_value="research",
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
        )

    assert (
        str(exc_info.value)
        == "Conflicting selectors: --mission-type='software-dev' and --mission='research' were both provided with different values. --mission is a hidden deprecated alias for --mission-type; pass only --mission-type."
    )


def test_mission_current_canonical_succeeds(tmp_path: Path) -> None:
    mission_slug = "077-demo-mission"
    (tmp_path / "kitty-specs" / mission_slug).mkdir(parents=True)

    with (
        patch("specify_cli.cli.commands.mission_type.get_project_root_or_exit", return_value=tmp_path),
        patch("specify_cli.cli.commands.mission_type.get_mission_for_feature", return_value=SimpleNamespace(name="software-dev")),
        patch("specify_cli.cli.commands.mission_type._mission_details_lines", return_value=["ok"]),
    ):
        result = runner.invoke(mission_app, ["current", "--mission", mission_slug])

    assert result.exit_code == 0, result.output
    assert "Warning:" not in result.output
    assert mission_slug in result.output


def test_mission_current_feature_flag_rejected(tmp_path: Path) -> None:
    """``--feature`` has been removed from ``mission current``; parser rejects it (exit 2).

    Previously the flag was a hidden alias for ``--mission``; WP03 (#1060) removed it.
    Supplying ``--feature`` now produces "No such option" from the argument parser.
    """
    with (
        patch("specify_cli.cli.commands.mission_type.get_project_root_or_exit", return_value=tmp_path),
    ):
        result = runner.invoke(mission_app, ["current", "--feature", "077-demo-mission"])

    assert result.exit_code == 2, result.output
    assert "no such option" in result.output.lower()


def test_mission_current_feature_with_mission_rejected(tmp_path: Path) -> None:
    """Supplying both ``--mission`` and ``--feature`` to ``mission current`` is rejected
    by the parser (exit 2 / unknown option) now that ``--feature`` is removed (WP03).
    """
    with (
        patch("specify_cli.cli.commands.mission_type.get_project_root_or_exit", return_value=tmp_path),
    ):
        result = runner.invoke(mission_app, ["current", "--mission", "077-a", "--feature", "077-b"])

    assert result.exit_code == 2, result.output
    assert "no such option" in result.output.lower()


def test_agent_mission_create_canonical_succeeds(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "new-thing"
    feature_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    def _fake_create_mission_core(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            mission_slug="new-thing",
            mission_number="077",
            meta={
                "mission_type": "software-dev",
                "slug": "new-thing",
                "friendly_name": "New Thing",
                "created_at": "2026-04-08T00:00:00Z",
            },
            feature_dir=feature_dir,
            target_branch="main",
            current_branch="main",
            origin_binding_attempted=False,
            origin_binding_succeeded=False,
            origin_binding_error=None,
            owned_checkout=None,
            created_files=[],
            uncommitted_files=[],
        )

    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.core.mission_creation.create_mission_core", side_effect=_fake_create_mission_core),
    ):
        result = runner.invoke(agent_mission_app, ["create", "new-thing", "--mission-type", "software-dev", "--json"])

    assert result.exit_code == 0, result.output
    assert captured["mission"] == "software-dev"
    payload = _extract_json(result.output)
    assert payload["mission_type"] == "software-dev"
    assert "Warning:" not in result.output


def test_agent_mission_create_alias_succeeds_with_warning(
    tmp_path: Path,
    warning_stream: io.StringIO,
) -> None:
    feature_dir = tmp_path / "kitty-specs" / "new-thing"
    feature_dir.mkdir(parents=True)
    captured: dict[str, object] = {}

    def _fake_create_mission_core(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            mission_slug="new-thing",
            mission_number="077",
            meta={
                "mission_type": "software-dev",
                "slug": "new-thing",
                "friendly_name": "New Thing",
                "created_at": "2026-04-08T00:00:00Z",
            },
            feature_dir=feature_dir,
            target_branch="main",
            current_branch="main",
            origin_binding_attempted=False,
            origin_binding_succeeded=False,
            origin_binding_error=None,
            owned_checkout=None,
            created_files=[],
            uncommitted_files=[],
        )

    with (
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path),
        patch("specify_cli.core.mission_creation.create_mission_core", side_effect=_fake_create_mission_core),
    ):
        result = runner.invoke(agent_mission_app, ["create", "new-thing", "--mission", "software-dev", "--json"])

    assert result.exit_code == 0, result.output
    assert captured["mission"] == "software-dev"
    assert "--mission is deprecated; use --mission-type" in warning_stream.getvalue()


def test_agent_mission_create_dual_flag_conflict_fails(tmp_path: Path) -> None:
    with patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=tmp_path):
        result = runner.invoke(
            agent_mission_app,
            ["create", "new-thing", "--mission-type", "software-dev", "--mission", "research", "--json"],
        )

    assert result.exit_code != 0
    assert "Conflicting selectors" in result.output


def test_next_step_canonical_selector_passes_mission_slug(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _fake_query(agent: str, mission_slug: str, repo_root: Path, **_kwargs: object):
        captured.update({"agent": agent, "mission_slug": mission_slug, "repo_root": repo_root})
        return SimpleNamespace(
            to_dict=lambda: {"kind": "query", "mission": mission_slug},
            is_query=True,
            mission=mission_slug,
            mission_state="planned",
            progress=None,
            run_id=None,
        )

    fake_runtime_bridge = ModuleType("runtime.next.runtime_bridge")
    fake_runtime_bridge.query_current_state = _fake_query
    fake_runtime_bridge.QueryModeValidationError = RuntimeError
    # The fake now shadows the canonical key, so it must expose every attribute
    # the command reads from ``runtime.next.runtime_bridge`` — including the real
    # ``MissionNotFoundError`` referenced by the query error path.
    fake_runtime_bridge.MissionNotFoundError = MissionNotFoundError

    # Swap the seam with ``monkeypatch.setitem``, not ``patch.dict(sys.modules,
    # ...)``: patch.dict restores the snapshot taken at entry, so any module
    # first-imported inside the window (here: charter_runtime.preflight.hook,
    # lazily loaded by next_step) is evicted from sys.modules on exit while its
    # parent package keeps the stale attribute — splitting module identity so a
    # later ``from ...preflight import hook`` patches a different object than
    # the one production code resolves (spec-kitty#89).
    monkeypatch.setitem(sys.modules, "runtime.next.runtime_bridge", fake_runtime_bridge)
    with patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path):
        next_step(
            agent="codex",
            mission="077-demo-mission",
            json_output=True,
            result=None,
            answer=None,
            decision_id=None,
        )

    out = capsys.readouterr()
    assert captured["mission_slug"] == "077-demo-mission"
    assert json.loads(out.out)["mission"] == "077-demo-mission"


def test_next_step_alias_selector_warns_and_passes_mission_slug(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--mission`` is the sole selector for ``next`` after alias removal (#1060-A).

    The ``--feature`` alias was hard-removed from ``next`` in WP02; this test
    verifies that passing ``--mission`` directly routes the slug correctly and
    emits no deprecation warning.  The test name is preserved (NFR-001) with
    an updated docstring reflecting the ``--mission``-only reality.
    """
    captured: dict[str, object] = {}

    def _fake_query(agent: str, mission_slug: str, repo_root: Path, **_kwargs: object):
        captured.update({"agent": agent, "mission_slug": mission_slug, "repo_root": repo_root})
        return SimpleNamespace(
            to_dict=lambda: {"kind": "query", "mission": mission_slug},
            is_query=True,
            mission=mission_slug,
            mission_state="planned",
            progress=None,
            run_id=None,
        )

    fake_runtime_bridge = ModuleType("runtime.next.runtime_bridge")
    fake_runtime_bridge.query_current_state = _fake_query
    fake_runtime_bridge.QueryModeValidationError = RuntimeError
    # The fake now shadows the canonical key, so it must expose every attribute
    # the command reads from ``runtime.next.runtime_bridge`` — including the real
    # ``MissionNotFoundError`` referenced by the query error path.
    fake_runtime_bridge.MissionNotFoundError = MissionNotFoundError

    # Same seam-swap discipline as the canonical test above: single-key
    # monkeypatch.setitem, never a snapshot-restoring patch.dict over
    # sys.modules (spec-kitty#89).
    monkeypatch.setitem(sys.modules, "runtime.next.runtime_bridge", fake_runtime_bridge)
    with patch("specify_cli.cli.commands.next_cmd.locate_project_root", return_value=tmp_path):
        next_step(
            agent="codex",
            mission="077-demo-mission",
            json_output=True,
            result=None,
            answer=None,
            decision_id=None,
        )

    out = capsys.readouterr()
    assert captured["mission_slug"] == "077-demo-mission"
    # No deprecation warning: --feature alias is fully removed, --mission is canonical.
    assert "--feature is deprecated" not in out.err


def test_next_step_dual_flag_conflict_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``next --feature`` is rejected at the CLI level after alias removal (#1060-A).

    The ``--feature`` alias was hard-removed from ``next`` in WP02, so the
    dual-flag conflict scenario no longer exists at the function level.  This
    test verifies the parser-level rejection: ``next --feature <slug>`` must
    produce exit 2 / "No such option".  The test name is preserved (NFR-001)
    with an updated docstring and assertion reflecting the ``--mission``-only
    reality.
    """
    from specify_cli import app as main_app

    result = runner.invoke(main_app, ["next", "--agent", "codex", "--feature", "077-b"])
    assert result.exit_code == 2, result.output
    assert "No such option" in result.output


def test_agent_tasks_status_canonical_selector_succeeds(tmp_path: Path) -> None:
    repo_root = _build_task_repo(tmp_path)

    with setup_mocked_env(repo_root, auto_commit_default=True):
        result = runner.invoke(tasks_app, ["status", "--mission", "077-demo-mission", "--json"])

    assert result.exit_code == 0, result.output
    payload = _extract_json(result.output)
    assert payload["total_wps"] == 1
    assert payload["work_packages"][0]["id"] == "WP01"


def test_agent_tasks_status_feature_alias_removed(tmp_path: Path) -> None:
    """`agent tasks status` no longer accepts `--feature` (#1060-A).

    The hidden alias was retired from the internal/agent cluster; the parser now
    rejects it with exit code 2 ("No such option"). (Previously the alias
    resolved with a deprecation warning.)
    """
    repo_root = _build_task_repo(tmp_path)

    with setup_mocked_env(repo_root, auto_commit_default=True):
        result = runner.invoke(tasks_app, ["status", "--feature", "077-demo-mission", "--json"])

    assert result.exit_code == 2, result.output
    assert "No such option" in result.output


def test_agent_tasks_status_rejects_feature_even_with_mission(tmp_path: Path) -> None:
    """Supplying `--feature` to `agent tasks status` is rejected outright now
    (#1060-A), so the old `--mission`+`--feature` conflict path no longer exists.
    """
    repo_root = _build_task_repo(tmp_path)

    with setup_mocked_env(repo_root):
        result = runner.invoke(tasks_app, ["status", "--mission", "077-a", "--feature", "077-b", "--json"])

    assert result.exit_code == 2, result.output
    assert "No such option" in result.output


def test_top_level_tasks_mission_selector_forwards_to_finalize_tasks() -> None:
    captured: dict[str, object] = {}

    def fake_finalize_tasks(*, feature: str | None = None, json_output: bool = False) -> None:
        captured["feature"] = feature
        captured["json_output"] = json_output

    with (
        patch("specify_cli.cli.commands.lifecycle._enforce_initialized"),
        patch("specify_cli.cli.commands.lifecycle.agent_feature.finalize_tasks", side_effect=fake_finalize_tasks),
    ):
        result = runner.invoke(
            _build_top_level_lifecycle_app(),
            ["tasks", "--mission", "077-demo-mission", "--json"],
        )

    assert result.exit_code == 0, result.output
    assert captured == {"feature": "077-demo-mission", "json_output": True}


def test_top_level_tasks_feature_flag_rejected() -> None:
    """``--feature`` has been removed from ``lifecycle tasks``; parser rejects it (exit 2).

    Previously the flag was a hidden alias for ``--mission``; WP03 (#1060) removed it.
    Supplying ``--feature`` (alone or combined with ``--mission``) now produces
    "No such option" from the argument parser.
    """
    with patch("specify_cli.cli.commands.lifecycle._enforce_initialized"):
        result = runner.invoke(
            _build_top_level_lifecycle_app(),
            ["tasks", "--mission", "077-a", "--feature", "077-b", "--json"],
        )

    assert result.exit_code == 2, result.output
    assert "no such option" in result.output.lower()


def test_top_level_tasks_without_selector_exits_2(
    tmp_path: Path,
) -> None:
    """Omitting ``--mission`` from ``lifecycle tasks`` exits with code 2 (BadParameter).

    WP03 (#1060) replaced the no-selector disambiguation guidance path with an
    inline guard that raises ``typer.BadParameter`` (→ exit 2) when ``--mission``
    is absent or blank. Previously the command exited 1 with a JSON error payload
    listing available missions; after WP03 the parser-level error is preferred.
    """
    with (
        patch("specify_cli.cli.commands.lifecycle._enforce_initialized"),
    ):
        result = runner.invoke(_build_top_level_lifecycle_app(), ["tasks", "--json"])

    assert result.exit_code == 2, result.output
    assert not isinstance(result.exception, TypeError)
