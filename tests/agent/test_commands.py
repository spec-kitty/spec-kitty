"""Scope: commands unit tests — no real git or subprocesses."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli import app as cli_app
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = pytest.mark.fast

accept_module = importlib.import_module("specify_cli.cli.commands.accept")
dashboard_module = importlib.import_module("specify_cli.cli.commands.dashboard")
merge_module = importlib.import_module("specify_cli.cli.commands.merge")
# Mission #2057 relocated target-branch validation into the merge ``preflight``
# seam; ``_validate_target_branch`` resolves ``run_command`` from that module's
# namespace, so the dry-run tests patch the seam (the merge shim re-exports
# ``run_command`` for patch-target stability, but the live call resolves here).
merge_preflight_module = importlib.import_module("specify_cli.merge.preflight")
research_module = importlib.import_module("specify_cli.cli.commands.research")
lifecycle_module = importlib.import_module("specify_cli.cli.commands.lifecycle")
verify_module = importlib.import_module("specify_cli.cli.commands.verify")


runner = CliRunner()


@pytest.fixture(autouse=True)
def _compatible_project_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Run full-app command tests from a schema-compatible project root."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "metadata.yaml").write_text("spec_kitty:\n  schema_version: 3\n", encoding="utf-8")
    (kittify / "config.yaml").write_text("project:\n  name: test\n", encoding="utf-8")
    (tmp_path / "kitty-specs").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)


def _load_json_from_output(output: str) -> dict[str, object]:
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AssertionError(f"JSON payload not found in output: {output!r}")
    return json.loads(output[start : end + 1])


def test_cli_help_lists_extracted_commands() -> None:
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    for name in [
        "research",
        "dashboard",
        "accept",
        "merge",
        "verify-setup",
        "specify",
        "plan",
        "tasks",
    ]:
        assert name in result.stdout


@pytest.mark.parametrize("command", ["-".join(["list", "legacy", "features"]), "repair"])
def test_trimmed_commands_removed_from_root_cli(command: str) -> None:
    result = runner.invoke(cli_app, [command])

    assert result.exit_code != 0
    assert "No such command" in result.output


def test_cli_help_simple_mode_avoids_rich_tables(monkeypatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_SIMPLE_HELP", "1")
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "Commands:" in result.stdout
    assert "╭" not in result.stdout


def test_verify_setup_command_runs(monkeypatch, tmp_path: Path) -> None:
    """Test that verify-setup renders the tool-checking section."""
    monkeypatch.setattr(verify_module, "check_tool_for_tracker", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(verify_module, "find_repo_root", lambda: tmp_path)
    json_modes: list[bool] = []

    def fake_project_root(repo_root: Path, *, json_output: bool = False) -> Path:
        json_modes.append(json_output)
        return repo_root

    monkeypatch.setattr(verify_module, "get_project_root_or_exit", fake_project_root)
    monkeypatch.setattr(verify_module, "run_enhanced_verify", lambda **_kwargs: {})

    result = runner.invoke(cli_app, ["verify-setup"])

    assert result.exit_code == 0
    assert json_modes == [False]
    assert "Check Available Tools" in result.stdout or "Checking for installed tools" in result.stdout


def test_specify_command_delegates_to_agent_lifecycle(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_mission(
        mission_slug: str,
        mission=None,
        mission_type=None,
        json_output: bool = False,
        topology=None,
    ):
        captured["mission_slug"] = mission_slug
        captured["mission"] = mission
        captured["mission_type"] = mission_type
        captured["json_output"] = json_output
        captured["topology"] = topology

    monkeypatch.setattr(lifecycle_module.agent_feature, "create_mission", fake_create_mission)
    monkeypatch.setattr(lifecycle_module, "assert_initialized", lambda **_kwargs: None)

    result = runner.invoke(cli_app, ["specify", "My Great Feature"])
    assert result.exit_code == 0
    assert captured["mission_slug"] == "my-great-feature"
    assert captured["mission"] is None
    assert captured["mission_type"] is None
    assert captured["json_output"] is False


def test_plan_and_tasks_delegate_to_agent_lifecycle(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_setup_plan(feature=None, json_output: bool = False):
        captured["plan_feature"] = feature
        captured["plan_json"] = json_output

    def fake_finalize_tasks(feature=None, json_output: bool = False):
        captured["tasks_feature"] = feature
        captured["tasks_json"] = json_output

    monkeypatch.setattr(lifecycle_module.agent_feature, "setup_plan", fake_setup_plan)
    monkeypatch.setattr(lifecycle_module.agent_feature, "finalize_tasks", fake_finalize_tasks)
    monkeypatch.setattr(lifecycle_module, "assert_initialized", lambda **_kwargs: None)

    plan_result = runner.invoke(cli_app, ["plan", "--mission", "001-demo", "--json"])
    tasks_result = runner.invoke(cli_app, ["tasks", "--mission", "001-demo", "--json"])

    assert plan_result.exit_code == 0
    assert tasks_result.exit_code == 0
    assert captured["plan_feature"] == "001-demo"
    assert captured["plan_json"] is True
    assert captured["tasks_feature"] == "001-demo"
    assert captured["tasks_json"] is True


def test_dashboard_kill_stops_instance(monkeypatch, tmp_path: Path) -> None:
    call_record: dict[str, Path] = {}
    json_modes: list[bool] = []

    def fake_project_root(*, json_output: bool = False) -> Path:
        json_modes.append(json_output)
        return tmp_path

    monkeypatch.setattr(dashboard_module, "get_project_root_or_exit", fake_project_root)

    def fake_stop(project_root: Path) -> tuple[bool, str]:
        call_record["root"] = project_root
        return True, "Dashboard stopped"

    monkeypatch.setattr(dashboard_module, "stop_dashboard", fake_stop)

    result = runner.invoke(cli_app, ["dashboard", "--kill"])
    assert result.exit_code == 0
    assert json_modes == [False]
    assert call_record["root"] == tmp_path
    assert "Dashboard stopped" in result.stdout


def test_research_creates_artifacts(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / ".kittify" / "missions" / "software-dev" / "templates").mkdir(parents=True)
    feature_dir = project_root / "kitty-specs" / "001-demo-feature"

    monkeypatch.setattr(research_module, "find_repo_root", lambda: project_root)
    monkeypatch.setattr(research_module, "get_mission_type", lambda *_args, **_kwargs: "software-dev")

    # WP09/FR-001: research.py routed the kind-blind slug resolver onto the
    # seam. 2026-07-27 re-pin: the read-surface migration finished the job —
    # ALL three resolutions (mission dir, planning/scaffold dir, plan read dir)
    # now go through ``placement_seam(...).read_dir(<MissionArtifactKind>)``,
    # so the kind-blind ``resolve_planning_read_dir`` stub is gone. Stubbing the
    # single seam constructor converges every kind on the test's ``feature_dir``
    # — the same coverage the two-stub form gave, at one boundary.
    class _SeamStub:
        def read_dir(self, *_a: object, **_k: object) -> Path:
            return feature_dir

    monkeypatch.setattr(research_module, "placement_seam", lambda *_a, **_k: _SeamStub())
    monkeypatch.setattr(research_module, "resolve_template_path", lambda *_args, **_kwargs: None)

    result = runner.invoke(cli_app, ["research", "--mission", "001-demo-feature", "--force"])
    assert result.exit_code == 0

    assert (feature_dir / "research.md").exists()
    assert (feature_dir / "data-model.md").exists()
    assert (feature_dir / "research" / "evidence-log.csv").exists()


def test_accept_checklist_json_output(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    feature_dir = repo_root / "kitty-specs" / "001-demo-feature"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008",
                "mission_slug": "001-demo-feature",
                "slug": "001-demo-feature",
                "friendly_name": "Demo Feature",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-04-12T00:00:00+00:00",
                "mission_number": 1,
            }
        ),
        encoding="utf-8",
    )

    class DummySummary:
        ok = True
        lanes = {"done": ["WP01"]}
        optional_missing: list[str] = []
        feature = "001-demo-feature"

        def outstanding(self) -> dict[str, list[str]]:
            return {}

        def to_dict(self) -> dict[str, object]:
            return {
                "mission_slug": self.feature,
                "mission_number": "001",
                "mission_type": "software-dev",
                "lanes": self.lanes,
            }

    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)
    # After WP02 removed heuristic detection, detect_mission_slug no longer exists.
    # All callers must pass --feature explicitly.
    monkeypatch.setattr(accept_module, "choose_mode", lambda mode, _repo_root: mode)
    monkeypatch.setattr(accept_module, "collect_feature_summary", lambda *args, **kwargs: DummySummary())

    result = runner.invoke(
        cli_app,
        ["accept", "--mode", "checklist", "--json", "--mission", "001-demo-feature", "--allow-fail"],
    )
    assert result.exit_code == 0
    assert result.stdout.lstrip().startswith("{")
    data = _load_json_from_output(result.stdout)
    assert data["mission_slug"] == "001-demo-feature"
    assert data["mission_number"] == "001"
    assert data["mission_type"] == "software-dev"


def test_accept_requires_explicit_feature_flag(monkeypatch, tmp_path: Path) -> None:
    """After heuristic detection removal, accept without --mission exits non-zero.

    The old test_accept_json_suppresses_fallback_announcement was testing that
    detect_mission_slug auto-detection worked.  Now that auto-detection is gone,
    accept without --mission is an explicit error (exits 2 per typer convention).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr(accept_module, "find_repo_root", lambda: repo_root)

    result = runner.invoke(
        cli_app,
        ["accept", "--mode", "checklist", "--json", "--allow-fail"],
    )

    # Must fail because --mission is required (exit 2 = typer error for missing param)
    assert result.exit_code != 0
    output = result.stdout
    assert "error" in output.lower() or "mission" in output.lower(), (
        f"Expected error about missing mission, got: {output}"
    )


def test_merge_dry_run_outputs_lane_payload(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    feature_dir = repo_root / "kitty-specs" / "010-test-feature"
    feature_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"), target_branch="main")

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        merge_module,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(merge_module, "run_command", fake_run_command)
    monkeypatch.setattr(merge_preflight_module, "run_command", fake_run_command)

    result = runner.invoke(
        cli_app,
        ["merge", "--json", "--dry-run", "--mission", "010-test-feature", "--target", "main"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["mission_slug"] == "010-test-feature"
    assert payload["mission_branch"] == "kitty/mission-010-test-feature"
    assert payload["target_branch"] == "main"
    assert payload["lanes"] == [
        {
            "lane_id": "lane-a",
            "wp_ids": ["WP01", "WP02"],
            "write_scope": ["src/**"],
            "predicted_surfaces": ["test"],
            "depends_on_lanes": [],
            "parallel_group": 0,
        }
    ]


def test_merge_json_dry_run_requires_lane_manifest(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    # Mission dir MUST exist (without a lane manifest) so the flow reaches the
    # forecast's MissingLanesError JSON path instead of tripping the earlier
    # mission-not-found gate (#4855: the not-found gate now emits JSON too, so
    # a missing mission dir here would wrongly satisfy this test's assertion
    # for the wrong reason).
    feature_dir = repo_root / "kitty-specs" / "010-test-feature"
    feature_dir.mkdir(parents=True)

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        merge_module,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(merge_module, "run_command", fake_run_command)
    monkeypatch.setattr(merge_preflight_module, "run_command", fake_run_command)

    result = runner.invoke(
        cli_app,
        ["merge", "--json", "--dry-run", "--mission", "010-test-feature", "--target", "main"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip())
    assert "lanes.json is required" in payload["error"]


def test_merge_json_not_found_mission_emits_json_error(monkeypatch, tmp_path: Path) -> None:
    """#4855: an unknown ``--mission`` handle under ``--json`` must emit JSON,
    not human ``console.print`` text, so a ``json.loads(stdout)`` consumer
    never crashes on the not-found gate.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    # Deliberately NO kitty-specs/010-test-feature dir -- the handle is unknown.

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        merge_module,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(merge_module, "run_command", fake_run_command)
    monkeypatch.setattr(merge_preflight_module, "run_command", fake_run_command)

    result = runner.invoke(
        cli_app,
        ["merge", "--json", "--mission", "010-test-feature", "--target", "main"],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip())
    assert "not found" in payload["error"].lower()
    assert payload["spec_kitty_version"]


def test_merge_git_preflight_json_payload_includes_cli_version(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    # ``_enforce_git_preflight`` lives in ``specify_cli.merge.preflight`` (mission
    # #2057 decomposition) and resolves ``run_git_preflight`` /
    # ``build_git_preflight_failure_payload`` in *that* module's namespace, so the
    # stubs must be installed there — patching the ``merge`` shim is dead (mirrors
    # the sibling dry-run tests that patch ``merge_preflight_module``).
    monkeypatch.setattr(
        merge_preflight_module,
        "run_git_preflight",
        lambda *_args, **_kwargs: type("Preflight", (), {"passed": False})(),
    )
    monkeypatch.setattr(
        merge_preflight_module,
        "build_git_preflight_failure_payload",
        lambda *_args, **_kwargs: {
            "error_code": "GIT_PREFLIGHT_FAILED",
            "error": "Git preflight checks failed before merge.",
            "remediation": ["git config --global --add safe.directory /repo"],
        },
    )

    with pytest.raises(typer.Exit):
        merge_module._enforce_git_preflight(repo_root, json_output=True)

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error_code"] == "GIT_PREFLIGHT_FAILED"
    assert "spec_kitty_version" in payload


def test_merge_json_dry_run_requires_feature_resolution(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return 0, "main", ""
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        merge_module,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(merge_module, "run_command", fake_run_command)
    monkeypatch.setattr(merge_preflight_module, "run_command", fake_run_command)

    result = runner.invoke(
        cli_app,
        ["merge", "--json", "--dry-run", "--target", "main"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip())
    assert payload["error"] == "Mission slug could not be resolved. Use --mission <slug>."


def test_merge_json_dry_run_honors_keep_flags(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    feature_dir = repo_root / "kitty-specs" / "010-test-feature"
    feature_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, target_branch="main")

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        merge_module,
        "_enforce_target_branch_sync_preflight",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(merge_module, "run_command", fake_run_command)
    monkeypatch.setattr(merge_preflight_module, "run_command", fake_run_command)
    result = runner.invoke(
        cli_app,
        [
            "merge",
            "--json",
            "--dry-run",
            "--mission",
            "010-test-feature",
            "--target",
            "main",
            "--keep-worktree",
            "--keep-branch",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["delete_branch"] is False
    assert payload["remove_worktree"] is False


def test_merge_resume_without_state_errors(monkeypatch, tmp_path: Path) -> None:
    """Resume with no existing merge state should error (not crash)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    monkeypatch.setattr(merge_module, "find_repo_root", lambda: repo_root)
    monkeypatch.setattr(merge_module, "_enforce_git_preflight", lambda *_args, **_kwargs: None)
    result = runner.invoke(cli_app, ["merge", "--resume"])
    # Resume without existing state should fail (but no longer with old "removed" error)
    assert result.exit_code == 1
    assert "Resume/abort merge flows were removed" not in result.stdout


def test_verify_setup_json_output(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "workspace"
    repo_root.mkdir()

    monkeypatch.setattr(verify_module, "find_repo_root", lambda: repo_root)
    json_modes: list[bool] = []

    def fake_project_root(_repo: Path | None = None, *, json_output: bool = False) -> Path:
        json_modes.append(json_output)
        return repo_root

    monkeypatch.setattr(verify_module, "get_project_root_or_exit", fake_project_root)

    def fake_verify(*_args, **_kwargs):
        return {
            "status": "ok",
            "feature_detection": {
                "detected": True,
                "mission_slug": "001-demo-feature",
                "mission_number": "001",
                "mission_type": "software-dev",
            },
        }

    monkeypatch.setattr(verify_module, "run_enhanced_verify", fake_verify)

    result = runner.invoke(cli_app, ["verify-setup", "--json", "--mission", "001-demo-feature"])
    assert result.exit_code == 0
    assert json_modes == [True]
    payload = _load_json_from_output(result.stdout)
    assert payload["status"] == "ok"
    assert payload["feature_detection"]["mission_slug"] == "001-demo-feature"
    assert payload["feature_detection"]["mission_number"] == "001"
    assert payload["feature_detection"]["mission_type"] == "software-dev"
