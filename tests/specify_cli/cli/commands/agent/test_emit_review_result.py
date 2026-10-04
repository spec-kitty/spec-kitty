"""Regression: ``agent status emit`` must carry a structured review verdict.

Pins issues #3547 / #1734 (FR-010/FR-012/FR-013). Before WP09, ``agent status
emit`` exposed no ``--review-result-json`` option, so a WP could not exit
``in_review`` through the emit surface with a structured verdict -- only the
``orchestrator-api transition`` surface could. These tests prove the emit-only
lifecycle walk reaches ``done`` via a structured verdict, that the misleading
``--help`` verdict example is gone, and that both surfaces validate the verdict
through the SAME hoisted parser (no duplicate validator drift).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api.commands import app as orchestrator_app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.ansi import strip_ansi
from tests.status.conftest import seed_wp_to_planned

pytestmark = pytest.mark.fast

runner = CliRunner()

MISSION_SLUG = "034-test-feature"


def _extract_json(output: str) -> dict:
    """Return the first line of ``output`` that parses as a JSON object."""
    for line in output.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No valid JSON found in output:\n{output}")


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """Minimal mission dir with a minted identity and a checked-off WP01."""
    fd = tmp_path / "kitty-specs" / MISSION_SLUG
    fd.mkdir(parents=True)
    (fd / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008",
                "mid8": "01KNXQS9",
                "mission_slug": MISSION_SLUG,
            }
        ),
        encoding="utf-8",
    )
    tasks_dir = fd / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-test-task.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Test Task\nsubtasks: []\n---\n\n# WP01\n",
        encoding="utf-8",
    )
    # The in_progress -> for_review gate requires provably-complete subtasks.
    (fd / "tasks.md").write_text(
        "# Tasks: 034-test-feature\n\n"
        "## WP01 — Verdict emit plumbing\n\n"
        "- [x] T026 Red-first emit review-result test\n"
        "- [x] T027 Thread review_result into TransitionRequest\n"
        "- [x] T028 Correct the --help verdict example\n"
        "- [x] T029 Admit ReviewResult on in_review->approved\n",
        encoding="utf-8",
    )
    return fd


def _patches(tmp_path: Path):
    return (
        patch(
            "specify_cli.cli.commands.agent.status.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.status.get_main_repo_root",
            return_value=tmp_path,
        ),
        patch("specify_cli.status.emit._saas_fan_out"),
    )


def _emit(tmp_path: Path, *args: str):
    locate, main_root, fan_out = _patches(tmp_path)
    with locate, main_root, fan_out:
        return runner.invoke(
            app,
            ["emit", "WP01", *args, "--actor", "test-agent", "--mission", MISSION_SLUG],
        )


def _walk_to_in_review(tmp_path: Path, feature_dir: Path) -> None:
    seed_wp_to_planned(feature_dir, "WP01", slug=MISSION_SLUG)
    for lane in ("claimed", "in_progress", "for_review", "in_review"):
        result = _emit(tmp_path, "--to", lane)
        assert result.exit_code == 0, f"walk failed at {lane}: {result.output}"


@pytest.mark.regression
def test_emit_only_lifecycle_reaches_approved_with_verdict(tmp_path: Path, feature_dir: Path) -> None:
    """#3547/#1734: emit alone advances in_review -> approved via a verdict.

    On base this is RED: ``emit`` has no ``--review-result-json`` option, so the
    verdict cannot be supplied and the in_review guard blocks the exit.
    """
    _walk_to_in_review(tmp_path, feature_dir)

    verdict = json.dumps({"reviewer": "alice", "verdict": "approved", "reference": "PR#1"})
    result = _emit(tmp_path, "--to", "approved", "--review-result-json", verdict, "--json")

    assert result.exit_code == 0, f"stdout: {result.output}"
    data = _extract_json(result.output)
    assert data["to_lane"] == "approved"


@pytest.mark.regression
def test_emit_only_lifecycle_reaches_done(tmp_path: Path, feature_dir: Path) -> None:
    """The full emit-only walk in_progress -> ... -> approved -> done succeeds."""
    _walk_to_in_review(tmp_path, feature_dir)

    verdict = json.dumps({"reviewer": "alice", "verdict": "approved", "reference": "PR#1"})
    approved = _emit(tmp_path, "--to", "approved", "--review-result-json", verdict, "--json")
    assert approved.exit_code == 0, f"approved failed: {approved.output}"

    evidence = json.dumps({"review": {"reviewer": "alice", "verdict": "approved", "reference": "PR#1"}})
    done = _emit(tmp_path, "--to", "done", "--evidence-json", evidence, "--json")
    assert done.exit_code == 0, f"done failed: {done.output}"
    assert _extract_json(done.output)["to_lane"] == "done"


def test_emit_rejects_malformed_review_result_json(tmp_path: Path, feature_dir: Path) -> None:
    """A malformed verdict is rejected via the hoisted parser's error shape."""
    _walk_to_in_review(tmp_path, feature_dir)

    result = _emit(tmp_path, "--to", "approved", "--review-result-json", "{not json")
    assert result.exit_code == 1, f"stdout: {result.output}"
    assert "--review-result-json" in result.output


def test_emit_help_documents_review_result_json_not_evidence_verdict() -> None:
    """FR-012: --help documents --review-result-json, no verdict-via-evidence example."""
    # The option's PRESENCE is asserted render-independently. Rich (15.x on CI)
    # soft-wraps the long ``--review-result-json`` token across two lines under a
    # non-tty console, and the CliRunner ``COLUMNS`` override does not reliably
    # reach Rich, so a substring match on the rendered help is width-fragile (it
    # broke CI as ``--review`` / ``result-json``). A registered option with help
    # text is documented in ``--help`` by construction, so introspect that.
    emit_cmd = typer.main.get_command(app).commands["emit"]
    review_opt = next(
        (p for p in emit_cmd.params if "--review-result-json" in getattr(p, "opts", ())),
        None,
    )
    assert review_opt is not None, "emit must expose --review-result-json"
    assert review_opt.help, "--review-result-json must carry --help documentation"

    # The rendered help must show the WORKING verdict example (via
    # --review-result-json) and must NOT route a verdict through --evidence-json.
    # Match against an ANSI-stripped, whitespace-free projection so a soft wrap at
    # any point neither breaks the positive match nor false-passes the negative.
    result = runner.invoke(app, ["emit", "--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    packed = "".join(strip_ansi(result.output).split())
    assert '"verdict":"approved"' in packed  # only via the review-result-json example
    # The misleading example routed an approval verdict through --evidence-json.
    assert '--evidence-json\'{"review"' not in packed


def test_both_verdict_surfaces_share_one_parser() -> None:
    """Parity: emit and orchestrator transition reference the SAME validator."""
    from specify_cli.cli.commands.agent import status as emit_module
    from specify_cli.orchestrator_api import wp_lifecycle
    from specify_cli.status.review_result_parse import parse_review_result_json

    assert emit_module.parse_review_result_json is parse_review_result_json
    assert wp_lifecycle.parse_review_result_json is parse_review_result_json


# ---------------------------------------------------------------------------
# FR-011: the shared, topology-aware for_review commit gate must ALSO be
# enforced on `agent status emit`, not just `orchestrator-api transition`.
#
# Mirrors the real-git, real-lane-worktree topology built by
# tests/specify_cli/lanes/test_for_review_gate_parity.py -- the gate reads
# actual commit state (`git rev-list <base>..HEAD`) in the lane worktree, so
# the fake, non-git `feature_dir` fixture above cannot exercise it.
# ---------------------------------------------------------------------------

_GATE_MISSION_SLUG = "gate-emit"
_GATE_MID8 = "01KGATE00"
_GATE_MISSION_ID = "01KGATE00000000000000000000"
_GATE_MISSION_DIRNAME = f"{_GATE_MISSION_SLUG}-{_GATE_MID8}"
_GATE_COORD_BRANCH = f"kitty/mission-{_GATE_MISSION_DIRNAME}"

_GATE_WP_FILE = "---\nwork_package_id: WP01\ntitle: Test WP01\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"


def _gate_valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "test-orch",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _gate_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _gate_manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_GATE_MISSION_DIRNAME,
        mission_id=_GATE_MISSION_ID,
        mission_branch=_GATE_COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-06-20T00:00:00+00:00",
        computed_from="test",
    )


def _gate_seed_planned_on_coord(repo: Path) -> None:
    from specify_cli.coordination.status_service import (
        EventLogWriteContract,
        append_event_log,
    )

    seed = StatusEvent(
        event_id="01SEEDGENESIS0000000000002",
        mission_slug=_GATE_MISSION_SLUG,
        mission_id=_GATE_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-06-19T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-coord"
    _gate_git(repo, "worktree", "add", "-q", str(worktree), _GATE_COORD_BRANCH)
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(worktree / "kitty-specs" / _GATE_MISSION_DIRNAME),
        seed,
    )
    _gate_git(worktree, "add", "-A")
    _gate_git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _gate_git(repo, "worktree", "remove", "-f", str(worktree))


def _gate_build_mission(repo: Path) -> Path:
    """Materialize a coord-topology mission with a lanes manifest at ``repo``.

    Byte-identical topology to
    ``tests/specify_cli/lanes/test_for_review_gate_parity.py::_build_mission``
    (real git, real lanes.json, real lane worktree via ``start-implementation``)
    so the FR-011 gate -- which decides on real commit state -- has something
    real to evaluate.
    """
    repo.mkdir(parents=True)
    _gate_git(repo, "init", "-q", "-b", "main")
    _gate_git(repo, "config", "user.email", "t@example.invalid")
    _gate_git(repo, "config", "user.name", "Test")
    _gate_git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / _GATE_MISSION_DIRNAME
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _GATE_MISSION_SLUG,
                "mission_id": _GATE_MISSION_ID,
                "mid8": _GATE_MID8,
                "coordination_branch": _GATE_COORD_BRANCH,
                "target_branch": "main",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01.md").write_text(_GATE_WP_FILE, encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 Test WP01\n\n- [x] T001 subtask for WP01\n- [x] T002 subtask for WP01\n",
        encoding="utf-8",
    )
    write_lanes_json(feature_dir, _gate_manifest())
    _gate_git(repo, "add", "kitty-specs")
    _gate_git(repo, "commit", "-q", "-m", "seed mission")
    _gate_git(repo, "branch", _GATE_COORD_BRANCH)
    _gate_seed_planned_on_coord(repo)
    return repo


def _gate_start_implementation(repo: Path) -> Path:
    """Allocate the lane worktree (planned->in_progress) via orchestrator-api."""
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo,
    ):
        result = runner.invoke(
            orchestrator_app,
            [
                "start-implementation",
                "--mission",
                _GATE_MISSION_DIRNAME,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _gate_valid_policy_json(),
            ],
        )
    assert result.exit_code == 0, result.output
    return Path(json.loads(result.output)["data"]["workspace_path"])


def _gate_emit(repo: Path, *args: str):
    """Invoke ``agent status emit`` against a REAL git mission at ``repo``."""
    with (
        patch(
            "specify_cli.cli.commands.agent.status.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.status.get_main_repo_root",
            return_value=repo,
        ),
        patch("specify_cli.status.emit._saas_fan_out"),
    ):
        return runner.invoke(
            app,
            [
                "emit",
                "WP01",
                *args,
                "--actor",
                "claude",
                "--mission",
                _GATE_MISSION_DIRNAME,
                "--json",
            ],
        )


@pytest.mark.regression
def test_emit_rejects_for_review_without_lane_commit(tmp_path: Path) -> None:
    """FR-011: emit rejects in_progress->for_review with no lane commit.

    Red-first: before the gate is wired into ``emit()``, this transition
    succeeds (exit 0) even though the lane worktree carries zero commits
    beyond its base -- the same hole the orchestrator-api surface closed.
    """
    repo = _gate_build_mission(tmp_path / "reject")
    _gate_start_implementation(repo)

    result = _gate_emit(repo, "--to", "for_review")

    assert result.exit_code == 1, result.output
    data = _extract_json(result.output)
    assert data["lane_id"] == "lane-a"
    assert "no implementation commit" in data["error"]
    assert "WP01" in data["error"]


@pytest.mark.regression
def test_emit_force_bypasses_for_review_gate(tmp_path: Path) -> None:
    """FR-011: ``--force`` bypasses the commit gate on the emit surface."""
    repo = _gate_build_mission(tmp_path / "force")
    _gate_start_implementation(repo)

    result = _gate_emit(repo, "--to", "for_review", "--force", "--reason", "nothing to commit")

    assert result.exit_code == 0, result.output
    assert _extract_json(result.output)["to_lane"] == "for_review"


@pytest.mark.regression
def test_emit_allows_for_review_with_lane_commit(tmp_path: Path) -> None:
    """FR-011: a lane WITH a commit beyond base is allowed through emit."""
    repo = _gate_build_mission(tmp_path / "allow")
    lane_worktree = _gate_start_implementation(repo)

    (lane_worktree / "src").mkdir(exist_ok=True)
    (lane_worktree / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _gate_git(lane_worktree, "add", "-A")
    _gate_git(lane_worktree, "commit", "-q", "-m", "feat(WP01): implement")

    result = _gate_emit(repo, "--to", "for_review")

    assert result.exit_code == 0, result.output
    assert _extract_json(result.output)["to_lane"] == "for_review"
