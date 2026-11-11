"""An advancing ``next`` reports the coordination worktree its bootstrap materialized (WP06).

Mission ``runtime-status-read-door-01M73HHB`` (FR-003, FR-004, SC-003; operator ruling DM-2,
contract ``contracts/next-materialization-report.md``).

The decision-log wrap in ``next`` bootstrap calls the status write seam, which materializes an
unmaterialized coordination worktree and restores an empty one. When that happened, the decision
carries ``remediation = {"kind": "materialized_coordination_worktree", "path": <worktree>}``
(``--json``) and the human output gains one line before the decision text. Nothing is reported
for an already materialized worktree, query mode (which never materializes), a deleted
coordination branch, or a Mission without coordination topology.

Fixture: the #7507 Mission (WP01 ``planned``, WP02 ``for_review`` committed on the coordination
branch) from ``test_board_query_read_door_7507``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology, OwnedRefusalCode
from runtime.next.runtime_bridge import decide_next_via_runtime
from tests._factories import provision_test_charter
from tests.runtime._next_mission_scaffold import analysis_is_current, scaffold_coord_software_dev, scaffold_software_dev
from tests.runtime.next.test_board_query_read_door_7507 import COORD_TOPOLOGIES, _owned_coordination_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MATERIALIZED = "materialized"
EMPTY = "empty"
UNMATERIALIZED = "unmaterialized"
DELETED = "deleted"

_REMEDIATION_KIND = "materialized_coordination_worktree"
_LINE_PREFIX = "Materialized the coordination worktree for "

runner = CliRunner()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=True, text=True).stdout


def _coord_mission(tmp_path: Path, cell: str) -> tuple[Path, str, Path]:
    """The #7507 coordination Mission with its worktree in *cell*. Returns ``(repo, slug, coord_root)``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, coord_mission_dir = scaffold_coord_software_dev(
        repo,
        f"report-{cell}",
        MissionTopology.COORD,
        wps={"WP01": "planned", "WP02": "for_review"},
    )
    coord_root = coord_mission_dir.parent.parent
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-q", "-m", "seed coordination log")
    if cell == EMPTY:
        shutil.rmtree(coord_mission_dir)
    elif cell in (UNMATERIALIZED, DELETED):
        coordination_branch = _git(coord_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
        _git(repo, "worktree", "remove", "--force", str(coord_root))
        if cell == DELETED:
            _git(repo, "branch", "-D", coordination_branch)
    return repo, feature_dir.name, coord_root


def _remediation(decision: Any) -> object:
    return decision.to_dict().get("remediation")


def _same_path(reported: object, expected: Path) -> bool:
    return isinstance(reported, str) and Path(reported).resolve() == expected.resolve()


def _run_cli(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, str]:
    from specify_cli import app as cli_app

    provision_test_charter(repo)
    monkeypatch.chdir(repo)
    result = runner.invoke(cli_app, ["next", "--agent", "pedro", *args])
    return result.exit_code, result.stdout


# ---------------------------------------------------------------------------
# T030 (FR-003): the bootstrap materialization is reported
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cell", [EMPTY, UNMATERIALIZED])
def test_advancing_decision_reports_the_materialized_worktree(tmp_path: Path, cell: str) -> None:
    repo, slug, coord_root = _coord_mission(tmp_path, cell)

    decision = decide_next_via_runtime("pedro", slug, "success", repo, analysis_currency=analysis_is_current)

    remediation = _remediation(decision)
    assert isinstance(remediation, dict), (decision.kind, decision.reason)
    assert remediation["kind"] == _REMEDIATION_KIND
    assert _same_path(remediation["path"], coord_root), remediation
    assert (coord_root / "kitty-specs").is_dir()


def test_cli_json_carries_the_remediation_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, coord_root = _coord_mission(tmp_path, UNMATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--result", "success", "--json")

    payload = json.loads(stdout)
    assert set(payload["remediation"]) == {"kind", "path"}, payload.get("remediation")
    assert payload["remediation"]["kind"] == _REMEDIATION_KIND
    assert _same_path(payload["remediation"]["path"], coord_root)


def test_cli_human_output_prints_one_line_before_the_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, coord_root = _coord_mission(tmp_path, UNMATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--result", "success")

    lines = stdout.splitlines()
    reports = [line for line in lines if line.startswith(_LINE_PREFIX)]
    assert len(reports) == 1, stdout
    prefix = f"{_LINE_PREFIX}{slug} at "
    assert reports[0].startswith(prefix) and reports[0].endswith("."), reports[0]
    assert _same_path(reports[0][len(prefix) : -1], coord_root)
    decision_line = next(i for i, line in enumerate(lines) if line.startswith("["))
    assert lines.index(reports[0]) < decision_line, stdout


# ---------------------------------------------------------------------------
# T033 (FR-004): no report without a materialization
# ---------------------------------------------------------------------------


def test_already_materialized_worktree_is_not_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, _coord_root = _coord_mission(tmp_path, MATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--result", "success", "--json")

    assert "remediation" not in json.loads(stdout)


def test_already_materialized_worktree_prints_no_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, _coord_root = _coord_mission(tmp_path, MATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--result", "success")

    assert _LINE_PREFIX not in stdout


def test_query_mode_neither_materializes_nor_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, coord_root = _coord_mission(tmp_path, UNMATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--json")

    assert "remediation" not in json.loads(stdout)
    assert not coord_root.exists()


def test_query_mode_human_output_prints_no_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug, coord_root = _coord_mission(tmp_path, UNMATERIALIZED)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug)

    assert _LINE_PREFIX not in stdout
    assert not coord_root.exists()


def test_deleted_coordination_branch_materializes_nothing(tmp_path: Path) -> None:
    """Today's refusal is kept and nothing is materialized, so there is nothing to report."""
    from runtime.next.runtime_bridge import DecisionGitLogUnavailable

    repo, slug, coord_root = _coord_mission(tmp_path, DELETED)

    with pytest.raises(DecisionGitLogUnavailable, match="COORDINATION_BRANCH_DELETED"):
        decide_next_via_runtime("pedro", slug, "success", repo, analysis_currency=analysis_is_current)

    assert not coord_root.exists()


def test_single_branch_mission_is_not_reported(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    scaffold_software_dev(repo, "report-single-branch", wps={"WP01": "planned"})

    decision = decide_next_via_runtime("pedro", "report-single-branch", "success", repo, analysis_currency=analysis_is_current)

    assert _remediation(decision) is None


# ---------------------------------------------------------------------------
# Review cycle 2 (SC-003): the two advancing early returns before the decision-log wrap
# ---------------------------------------------------------------------------

SHORT_CIRCUIT = "merged_short_circuit"
COMPLETED_PRIMARY = "completed_primary_terminal"


def _landed_coord_mission(tmp_path: Path, arm: str, cell: str) -> tuple[Path, str, Path, Path]:
    """A landed coordination Mission whose coordination branch was retained.

    *arm* picks the early return: ``SHORT_CIRCUIT`` seeds every WP ``done`` on the PRIMARY log,
    so the committed-authority pre-check answers ``terminal``; ``COMPLETED_PRIMARY`` leaves the
    PRIMARY log without WP events, so the bootstrap's completed-primary arm answers. *cell* is
    ``UNMATERIALIZED`` (worktree removed) or ``EMPTY`` (Mission directory gone from it).
    Returns ``(repo, slug, coord_root, coord_mission_dir)``.
    """
    from tests.runtime._next_mission_scaffold import seed_wp_lane

    repo, slug, coord_root = _coord_mission(tmp_path, cell)
    primary_dir = repo / "kitty-specs" / slug
    meta = json.loads((primary_dir / "meta.json").read_text(encoding="utf-8"))
    meta["merged_at"] = "2026-01-02T00:00:00+00:00"
    (primary_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if arm == SHORT_CIRCUIT:
        for wp_id in ("WP01", "WP02"):
            seed_wp_lane(primary_dir, slug, wp_id, "done")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "record the landing")
    return repo, slug, coord_root, coord_root / "kitty-specs" / slug


@pytest.mark.parametrize("cell", [UNMATERIALIZED, EMPTY])
@pytest.mark.parametrize("arm", [SHORT_CIRCUIT, COMPLETED_PRIMARY])
def test_landed_mission_terminal_neither_materializes_nor_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arm: str, cell: str) -> None:
    """A landed Mission's terminal run leaves its coordination worktree alone (FR-004, SC-003).

    Its status home is the consolidated target (the read door's ``CONSOLIDATED_TARGET``), so
    the ``MissionNextInvoked`` row must not materialize or restore the coordination worktree,
    and with nothing materialized there is nothing to report.
    """
    repo, slug, coord_root, coord_mission_dir = _landed_coord_mission(tmp_path, arm, cell)

    _exit, stdout = _run_cli(repo, monkeypatch, "--mission", slug, "--result", "success", "--json")

    payload = json.loads(stdout)
    assert payload["kind"] == "terminal", payload
    assert "remediation" not in payload
    if cell == UNMATERIALIZED:
        assert not coord_root.exists(), "a landed Mission's coordination worktree was materialized"
    else:
        assert not coord_mission_dir.exists(), "a landed Mission's empty coordination worktree was restored"
    row_log = repo / "kitty-specs" / slug / "mission-events.jsonl"
    rows = [json.loads(line) for line in row_log.read_text(encoding="utf-8").splitlines()] if row_log.is_file() else []
    assert any(row.get("type") == "MissionNextInvoked" for row in rows), "the MissionNextInvoked row was dropped"


# ---------------------------------------------------------------------------
# Review cycle 2 (FR-006): an owned coordination Mission keeps today's outcome; the report follows it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_empty_coordination_worktree_refuses_without_a_report(tmp_path: Path, topology: MissionTopology) -> None:
    """The owned context build refuses before the wrap, so nothing is materialized or reported."""
    repo, fact = _owned_coordination_mission(tmp_path, topology, EMPTY)

    decision = decide_next_via_runtime("pedro", fact.mission_slug, "success", repo, owned=fact)

    assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value
    assert _remediation(decision) is None


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES, ids=lambda t: t.value)
def test_owned_unmaterialized_coordination_worktree_proceeds_and_reports(tmp_path: Path, topology: MissionTopology) -> None:
    """The wrap materializes the owned Mission's coordination worktree and dispatch proceeds, so it is reported."""
    from tests.status.test_read_surface_owned_coordination import _coord_worktree

    repo, fact = _owned_coordination_mission(tmp_path, topology, UNMATERIALIZED)

    decision = decide_next_via_runtime("pedro", fact.mission_slug, "success", repo, owned=fact)

    assert str(decision.kind) == "step", decision.reason
    remediation = _remediation(decision)
    assert isinstance(remediation, dict), remediation
    assert remediation["kind"] == _REMEDIATION_KIND
    assert _same_path(remediation["path"], _coord_worktree(repo)), remediation
