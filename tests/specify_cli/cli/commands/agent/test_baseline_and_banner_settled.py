"""The ``for_review`` baseline artifact on a settled default Mission (#7551, FR-005).

A default Mission settled ``lanes_with_coord`` at its first ``finalize-tasks`` keeps its PRIMARY
partition on the Mission topic branch, held by the coordination worktree, while the repository root
checkout returns to ``create_return_branch``. ``tasks/<WP>/baseline-tests.json`` is written into that
coordination copy, so the "does it need a commit" probe and the commit itself must run in the checkout
that holds it. Probed from the repository root checkout, ``git status`` saw a path under the ignored
``.worktrees/`` and reported nothing; the commit was silently skipped and the file stayed untracked.

The end-to-end case drives the real CLI in a subprocess from an unprotected root (``dev``) on a
Mission built by the real ``agent mission create`` core and ``finalize-tasks``.

The same settled Mission also pins #7595: the target-branch helpers behind the ``implement`` /
``move-task`` banner read the declared ``target_branch`` from the coordination copy of ``meta.json``
instead of falling back to the checked-out primary branch.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    REPO_ROOT,
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_ANALYSIS_REPORT = "# Analysis\n\nNo critical issues.\n"
_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_BASELINE = "baseline-tests.json"
_WP01_DIR = "WP01-work"
_CLEAN_JUNIT = '<testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite>'


def _spec_kitty(root: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SPEC_KITTY_NON_INTERACTIVE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=root,
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _configure_review_test_command(root: Path) -> None:
    """A real ``review.test_command`` that writes a clean one-test JUnit report to ``{output_file}``."""
    config_path = root / ".kittify" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config = config or {}
    config["review"] = {"test_command": f"printf '%s' '{_CLEAN_JUNIT}' > {{output_file}}"}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    git(root, "add", str(config_path))
    git(root, "commit", "-qm", "review test command")


@pytest.fixture(autouse=True)
def _isolated_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    # Vacuity guard: with the operator hatch set, no protected-branch check would ever refuse.
    monkeypatch.delenv(_HATCH, raising=False)
    # The in-process ``finalize-tasks`` runs from the source tree and fans out no status event.
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.fixture
def settled_on_dev(tmp_path: Path) -> DefaultMission:
    """A finalized three-lane default Mission, settled ``lanes_with_coord``, the root checkout on ``dev``."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="dev")
    (mission.root_mission_dir / "plan.md").write_text("# Plan\n\nDo it.\n", encoding="utf-8")
    git(mission.root, "add", "kitty-specs")
    git(mission.root, "commit", "-qm", "plan")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    recorded = _spec_kitty(
        mission.root, "agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", "-", "--agent", "claude", stdin=_ANALYSIS_REPORT
    )
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert git(mission.root, "branch", "--show-current") == "dev"
    assert mission.coord_mission_dir.is_dir()
    # Before settlement the root checkout holds the topic branch; configure once it is back on ``dev``.
    _configure_review_test_command(mission.root)
    return mission


def _lane_worktree(mission: DefaultMission) -> Path:
    lanes = sorted(p for p in (mission.root / ".worktrees").iterdir() if "-lane-" in p.name)
    assert lanes, list((mission.root / ".worktrees").iterdir())
    return lanes[0]


def test_for_review_commits_the_baseline_on_the_topic_branch_in_its_holder(settled_on_dev: DefaultMission) -> None:
    """FR-005: the baseline is committed on the topic branch; nothing is left untracked in the holder."""
    mission = settled_on_dev
    implement = _spec_kitty(mission.root, "agent", "action", "implement", "WP01", "--mission", mission.slug, "--agent", "claude")
    assert implement.returncode == 0, implement.stdout + implement.stderr

    lane = _lane_worktree(mission)
    (lane / "src").mkdir(exist_ok=True)
    (lane / "src" / "one.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(lane, "add", "src/one.py")
    git(lane, "commit", "-qm", "feat: one")

    moved = _spec_kitty(
        mission.root, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission.slug, "--agent", "claude", "--note", "Ready"
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr

    artifact = mission.coord_mission_dir / "tasks" / _WP01_DIR / _BASELINE
    assert artifact.is_file(), "the baseline was never captured; the end-to-end case is vacuous"
    committed = subprocess.run(
        ["git", "show", f"{mission.topic}:kitty-specs/{mission.slug}/tasks/{_WP01_DIR}/{_BASELINE}"],
        cwd=mission.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    holder = mission.coord_mission_dir.parents[1]
    assert git(holder, "status", "--porcelain", "--untracked-files=all", "--", f"kitty-specs/{mission.slug}/tasks/{_WP01_DIR}/{_BASELINE}") == ""


def test_the_baseline_commit_checkout_is_the_coordination_worktree_after_settlement(settled_on_dev: DefaultMission) -> None:
    """The probe/commit checkout is the holder of the topic branch, not the repository root checkout."""
    from specify_cli.cli.commands.agent.workflow_executor import _baseline_commit_checkout

    holder = _baseline_commit_checkout(settled_on_dev.root, settled_on_dev.slug, None)

    assert holder.resolve() == settled_on_dev.coord_mission_dir.parents[1].resolve()
    assert git(holder, "branch", "--show-current") == settled_on_dev.topic


def test_an_artifact_inside_the_checkout_raises_no_warning(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_executor import _baseline_outside_checkout_warning

    artifact = tmp_path / "kitty-specs" / "m" / "tasks" / _WP01_DIR / _BASELINE

    assert _baseline_outside_checkout_warning(artifact, tmp_path) is None


def test_an_artifact_outside_the_checkout_is_named_with_the_checkout(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_executor import _baseline_outside_checkout_warning

    checkout = tmp_path / "root"
    artifact = tmp_path / "elsewhere" / _BASELINE

    warning = _baseline_outside_checkout_warning(artifact, checkout)

    assert warning is not None
    assert str(artifact) in warning and str(checkout) in warning


@pytest.mark.parametrize("quiet", [True, False])
def test_an_uncommitted_baseline_is_never_silent(quiet: bool, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """FR-005: the warning reaches the module logger in every mode and the console unless ``--json`` (quiet)."""
    import specify_cli.cli.console as console_module
    from specify_cli.cli.commands.agent.workflow_executor import _warn_baseline_not_committed

    printed: list[str] = []
    monkeypatch.setattr(console_module.console, "print", lambda text, *a, **k: printed.append(str(text)))

    with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow_executor"):
        _warn_baseline_not_committed("Baseline artifact X lies outside the checkout Y.", quiet=quiet)

    assert "Baseline artifact X lies outside the checkout Y." in caplog.text
    assert (printed == []) is quiet


def test_capture_skips_and_warns_when_the_artifact_is_outside_its_commit_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning arm of ``capture_and_commit_baseline``: no probe, no commit, a logged warning."""
    import specify_cli.review.baseline as baseline_module
    import specify_cli.review.scope_source as scope_source_module
    from specify_cli.cli.commands.agent import workflow_executor
    from specify_cli.review.baseline import BaselineTestResult

    feature_dir = tmp_path / "coord" / "kitty-specs" / "m"
    artifact = feature_dir / "tasks" / _WP01_DIR / _BASELINE
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    result = BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-11-12T00:00:00+00:00",
        base_branch="dev",
        base_commit="abcdef1",
        test_runner="custom",
        total=1,
        passed=1,
        failed=0,
        skipped=0,
    )
    monkeypatch.setattr(baseline_module, "capture_baseline", lambda **_k: result)
    monkeypatch.setattr(scope_source_module, "resolve_scope_source", lambda _root: None)
    monkeypatch.setattr(workflow_executor, "_baseline_commit_checkout", lambda *_a: tmp_path / "root")

    def _no_probe(*_a: object) -> bool:
        raise AssertionError("the needs-commit probe must not run outside the holding checkout")

    monkeypatch.setattr(workflow_executor, "_baseline_artifact_needs_commit", _no_probe)

    with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow_executor"):
        workflow_executor.capture_and_commit_baseline(
            workspace_path=tmp_path,
            target_branch="dev",
            normalized_wp_id="WP01",
            mission_slug="m",
            feature_dir=feature_dir,
            wp_slug=_WP01_DIR,
            main_repo_root=tmp_path / "root",
            quiet=True,
            test_timeout=60,
        )

    assert f"Baseline artifact {artifact}" in caplog.text
    assert "Baseline capture error" not in caplog.text


@pytest.mark.parametrize("quiet", [True, False])
def test_capture_warns_when_the_commit_checkout_does_not_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, quiet: bool
) -> None:
    """A seam failure naming the holding checkout reaches the baseline warning, not only the generic logger line."""
    import specify_cli.cli.console as console_module
    import specify_cli.review.baseline as baseline_module
    import specify_cli.review.scope_source as scope_source_module
    from specify_cli.cli.commands.agent import workflow_executor
    from specify_cli.review.baseline import BaselineTestResult

    feature_dir = tmp_path / "kitty-specs" / "m"
    artifact = feature_dir / "tasks" / _WP01_DIR / _BASELINE
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    result = BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-11-12T00:00:00+00:00",
        base_branch="dev",
        base_commit="abcdef1",
        test_runner="custom",
        total=1,
        passed=1,
        failed=0,
        skipped=0,
    )
    monkeypatch.setattr(baseline_module, "capture_baseline", lambda **_k: result)
    monkeypatch.setattr(scope_source_module, "resolve_scope_source", lambda _root: None)

    def _unresolvable(*_a: object) -> Path:
        raise RuntimeError("coordination worktree missing")

    monkeypatch.setattr(workflow_executor, "_baseline_commit_checkout", _unresolvable)
    printed: list[str] = []
    monkeypatch.setattr(console_module.console, "print", lambda text, *a, **k: printed.append(str(text)))

    with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow_executor"):
        workflow_executor.capture_and_commit_baseline(
            workspace_path=tmp_path,
            target_branch="dev",
            normalized_wp_id="WP01",
            mission_slug="m",
            feature_dir=feature_dir,
            wp_slug=_WP01_DIR,
            main_repo_root=tmp_path,
            quiet=quiet,
            test_timeout=60,
        )

    assert f"Baseline artifact {artifact} was not committed" in caplog.text
    assert "coordination worktree missing" in caplog.text
    assert "Baseline capture error" not in caplog.text
    assert any("was not committed" in line for line in printed) is not quiet


# ---------------------------------------------------------------------------
# #7595: the target-branch helpers read the Mission's meta.json through the seam's reader.
# ---------------------------------------------------------------------------


@pytest.fixture
def settled_root_on_main(settled_on_dev: DefaultMission) -> DefaultMission:
    """The settled Mission (declared target ``dev``) with the repository root checkout moved to ``main``.

    The primary-branch fallback follows the checked-out branch, so standing on ``main`` makes a
    fallback distinguishable from the declared ``dev`` target.
    """
    git(settled_on_dev.root, "checkout", "-q", "main")
    meta = (settled_on_dev.coord_mission_dir / "meta.json").read_text(encoding="utf-8")
    assert '"target_branch": "dev"' in meta
    assert not (settled_on_dev.root / "kitty-specs" / settled_on_dev.slug / "meta.json").exists()
    return settled_on_dev


def test_the_target_banner_reads_the_declared_target_after_settlement(settled_root_on_main: DefaultMission) -> None:
    """#7595: both helpers return the declared ``dev``, never the ``main`` fallback."""
    from specify_cli.core.git_ops import resolve_target_branch
    from specify_cli.core.paths import get_feature_target_branch

    mission = settled_root_on_main

    assert get_feature_target_branch(mission.root, mission.slug) == "dev"
    resolution = resolve_target_branch(mission.slug, mission.root, current_branch="main")
    assert resolution.target == "dev"
    assert resolution.should_notify is True


def test_the_write_side_reads_the_declared_target_after_settlement(settled_root_on_main: DefaultMission) -> None:
    """Blast radius: the composition root's target is ``dev``; writes still commit on the topic branch."""
    from mission_runtime import MissionArtifactKind, placement_seam
    from mission_runtime.lifecycle_phase import LifecyclePhase, resolve_lifecycle_phase
    from mission_runtime.resolution import resolve_action_context
    from specify_cli.core.paths import resolve_merge_target_branch

    mission = settled_root_on_main
    seam = placement_seam(mission.root, mission.slug)

    assert seam.write_target(MissionArtifactKind.TRACER_FILE).ref == mission.topic
    assert seam.write_target(MissionArtifactKind.WORK_PACKAGE_TASK).ref == mission.topic
    assert resolve_action_context(mission.root, action="tasks", feature=mission.slug).target_branch == "dev"
    # ``consolidate`` / ``orchestrator-api`` resolve the landing branch through this helper: it must agree.
    assert resolve_merge_target_branch(mission.root, mission.slug, None) == ("dev", "meta.json")
    # The phase probe still reads the root checkout, which is sound only because the landing alone records
    # ``baseline_merge_commit``: a settled, unlanded Mission is PRE_CONSOLIDATION.
    assert resolve_lifecycle_phase(mission.slug, mission.root) is LifecyclePhase.PRE_CONSOLIDATION


def test_the_target_read_of_a_consolidated_mission_does_not_re_enter_itself(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: with ``baseline_merge_commit`` set, the meta read must not recurse back into the helper.

    ``PlacementSeam.read_dir`` resolves the lifecycle phase, which reads the target branch of a
    consolidated Mission; reading ``meta.json`` through it would re-enter this helper without end.
    """
    import specify_cli.core.paths as paths_module

    mission = make_default_mission(tmp_path, THREE_LANES)
    meta_path = mission.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["baseline_merge_commit"] = git(mission.root, "rev-parse", "HEAD")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    real = paths_module.get_feature_target_branch
    entries: list[str] = []

    def _spy(repo_root: Path, mission_slug: str) -> str:
        entries.append(mission_slug)
        return real(repo_root, mission_slug)

    monkeypatch.setattr(paths_module, "get_feature_target_branch", _spy)

    assert paths_module.get_feature_target_branch(mission.root, mission.slug) == meta["target_branch"]
    assert entries == [mission.slug]
