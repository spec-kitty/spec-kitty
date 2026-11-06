"""S7 settlement at the first ``finalize-tasks`` (#7282, FR-053..FR-058, ADR 2026-11-06-3).

A Mission created without ``--topology`` is provisional (``topology_source: default``,
``topology_settled: false``) and its write checkout holds the Mission topic branch. Its
first ``finalize-tasks`` settles the topology once, by size: ``single_branch`` for at most
two non-canceled WPs or at most one code lane, else ``lanes_with_coord`` with the topic
branch as the coordination branch, on every target. Every test drives the real
``agent mission create`` core and the real ``finalize-tasks`` command on a real git
repository; refusals are paired with accepting controls.
"""

from __future__ import annotations

import ast
import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

REPO_ROOT = Path(__file__).resolve().parents[5]
SPEC = (
    "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n"
    "| --- | --- | --- | --- |\n| FR-001 | Requirement | Test passes. | proposed |\n"
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@dataclass(frozen=True)
class DefaultMission:
    root: Path
    slug: str
    topic: str
    return_branch: str
    root_mission_dir: Path

    @property
    def coord_mission_dir(self) -> Path:
        return self.root / ".worktrees" / f"{self.slug}-coord" / "kitty-specs" / self.slug


def init_repo(tmp_path: Path, *, standing_on: str = "main") -> Path:
    from tests.integration.test_placement_partition_golden_path import _init_git_repo

    root = tmp_path / "repo"
    root.mkdir()
    _init_git_repo(root)
    (root / ".gitignore").write_text(".worktrees/\n.kittify/derived/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "config")
    if standing_on != "main":
        git(root, "checkout", "-q", "-b", standing_on)
    return root


def _write_wps(mission_dir: Path, owned: Sequence[str], *, planning: Sequence[int] = ()) -> None:
    (mission_dir / "spec.md").write_text(SPEC, encoding="utf-8")
    (mission_dir / "tasks").mkdir(exist_ok=True)
    ids = [f"WP{index:02d}" for index in range(1, len(owned) + 1)]
    (mission_dir / "tasks.md").write_text("# Tasks\n\n" + "".join(f"## {wp}\n\nNo dependencies.\n\n" for wp in ids), encoding="utf-8")
    for index, (wp_id, path) in enumerate(zip(ids, owned, strict=True), start=1):
        mode = "planning_artifact" if index in planning else "code_change"
        (mission_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Work {wp_id}\ndependencies: []\nrequirement_refs: [FR-001]\nsubtasks: []\n"
            f"owned_files: [{path}]\nauthoritative_surface: {path}\nexecution_mode: {mode}\n"
            f"create_intent:\n  - {path}\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )


def make_default_mission(
    tmp_path: Path,
    owned: Sequence[str],
    *,
    standing_on: str = "main",
    planning: Sequence[int] = (),
    explicit: str | None = None,
) -> DefaultMission:
    """A Mission created with no ``--topology`` (or *explicit*), with its WPs committed and ready to finalize."""
    from mission_runtime import MissionTopology
    from specify_cli.core.mission_creation import create_mission_core
    from specify_cli.meta_keys import TopologySource

    root = init_repo(tmp_path, standing_on=standing_on)
    source = TopologySource.EXPLICIT if explicit else TopologySource.DEFAULT
    result = create_mission_core(
        root,
        "probe",
        allow_worktree_context=True,
        friendly_name="Probe",
        purpose_tldr="Deliver the probe for the settlement tests.",
        purpose_context="This mission exercises the S7 settlement at the first finalize end to end.",
        topology=MissionTopology(explicit) if explicit else MissionTopology.SINGLE_BRANCH,
        topology_source=source,
    )
    _write_wps(result.feature_dir, owned, planning=planning)
    git(root, "add", "kitty-specs")
    git(root, "commit", "-qm", "tasks")
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    return DefaultMission(
        root=root,
        slug=result.mission_slug,
        topic=str(meta.get("mission_branch") or ""),
        return_branch=str(meta.get("create_return_branch") or standing_on),
        root_mission_dir=result.feature_dir,
    )


def run_finalize(mission: DefaultMission, *extra: str) -> tuple[int, dict[str, object]]:
    """The real ``finalize-tasks --json``; returns ``(exit_code, last JSON object)``."""
    from specify_cli.cli.commands.agent.mission import app
    from specify_cli.core.checkout_identity import CheckoutIdentity

    root = mission.root
    with (
        patch(
            "specify_cli.cli.commands.agent.mission_finalize.resolve_checkout_identity",
            side_effect=lambda _cwd, intent: CheckoutIdentity(invoking_root=root, canonical_target=root, is_owner=True, intent=intent),
        ),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=root),
        patch("specify_cli.cli.commands.agent.mission.run_git_preflight", return_value=type("P", (), {"passed": True})()),
    ):
        result = CliRunner().invoke(app, ["finalize-tasks", "--mission", mission.slug, "--json", *extra], catch_exceptions=False)
    payloads = [json.loads(line) for line in result.output.splitlines() if line.startswith("{")]
    return result.exit_code, (payloads[-1] if payloads else {"raw": result.output})


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def branch_tips(root: Path) -> str:
    return git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")


def current_branch(root: Path) -> str:
    return git(root, "branch", "--show-current")


def meta_at(root: Path, ref: str, slug: str) -> dict[str, object]:
    data: dict[str, object] = json.loads(git(root, "show", f"{ref}:kitty-specs/{slug}/meta.json"))
    return data


THREE_LANES = ("src/one.py", "src/two.py", "src/three.py")


# ---------------------------------------------------------------------------
# T083 settlement scenarios
# ---------------------------------------------------------------------------


def test_two_wp_settles_single_branch_events_readable(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert decision["settled_this_run"] is True and decision["rule"] == "wp_count_le_2"
    assert decision["settled_topology"] == "single_branch"
    assert current_branch(mission.root) == mission.topic
    assert not mission.coord_mission_dir.exists()
    meta = json.loads((mission.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology_settled"] is True and meta["topology"] == "single_branch"
    events = (mission.root_mission_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert '"WP01"' in events and '"WP02"' in events


def _assert_lanes_with_coord(mission: DefaultMission, payload: dict[str, object]) -> None:
    decision = payload["topology_decision"]
    assert isinstance(decision, dict)
    assert decision["settled_this_run"] is True and decision["rule"] == "lanes_with_coord"
    assert decision["code_lane_count"] == 3
    assert current_branch(mission.root) == mission.return_branch
    assert git(mission.coord_mission_dir.parents[1], "branch", "--show-current") == mission.topic
    meta = meta_at(mission.root, mission.topic, mission.slug)
    assert meta["coordination_branch"] == mission.topic == meta["mission_branch"]
    assert meta["topology"] == "lanes_with_coord" and meta["topology_settled"] is True
    lanes = json.loads(git(mission.root, "show", f"{mission.topic}:kitty-specs/{mission.slug}/lanes.json"))
    assert len([lane for lane in lanes["lanes"] if lane["lane_id"] != "lane-planning"]) == 3
    assert not git(mission.root, "for-each-ref", "--format=%(refname)", f"refs/heads/{mission.topic}-lane-*")
    events = git(mission.root, "show", f"{mission.topic}:kitty-specs/{mission.slug}/status.events.jsonl")
    assert all(f'"WP0{index}"' in events for index in (1, 2, 3))


def test_three_lanes_protected_settles_lanes_with_coord_topic_is_coord(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    main_before = git(mission.root, "rev-parse", "main")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    _assert_lanes_with_coord(mission, payload)
    assert git(mission.root, "rev-parse", "main") == main_before, "no planning commit lands on the target"


def test_three_lanes_unprotected_settles_lanes_with_coord_topic_is_coord(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="work")
    work_before = git(mission.root, "rev-parse", "work")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    _assert_lanes_with_coord(mission, payload)
    assert mission.return_branch == "work"
    assert git(mission.root, "rev-parse", "work") == work_before, "no planning commit lands on the target"


def test_settlement_moves_root_checkout_before_coord_worktree(tmp_path: Path) -> None:
    from specify_cli.lanes import topology_settlement

    order: list[str] = []
    real = topology_settlement.run_settlement_plan

    def _record(steps: list[topology_settlement.SettlementStep], *, remedy: str) -> list[topology_settlement.SettlementStep]:
        order.extend(step.name for step in steps)
        return real(steps, remedy=remedy)

    mission = make_default_mission(tmp_path, THREE_LANES)
    with patch.object(topology_settlement, "run_settlement_plan", _record):
        code, payload = run_finalize(mission)
    assert code == 0, payload
    assert order == ["commit", "root_checkout_move", "coord_worktree_materialize", "meta_restamp", "lanes_json_write"]


@pytest.mark.parametrize("busy", [False, True], ids=["missing", "checked_out_elsewhere"])
def test_settlement_refuses_missing_or_busy_return_branch(tmp_path: Path, busy: bool) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    if busy:
        git(mission.root, "worktree", "add", "-q", str(tmp_path / "elsewhere"), "main")
    else:
        git(mission.root, "branch", "-D", "main")
    tips = branch_tips(mission.root)
    meta_bytes = (mission.root_mission_dir / "meta.json").read_bytes()
    code, payload = run_finalize(mission)
    assert code == 1
    assert payload["error_code"] == "TOPOLOGY_SETTLEMENT_REFUSED"
    assert "main" in str(payload["error"])
    assert branch_tips(mission.root) == tips
    assert (mission.root_mission_dir / "meta.json").read_bytes() == meta_bytes
    assert current_branch(mission.root) == mission.topic and not mission.coord_mission_dir.exists()


def test_explicit_lanes_and_coord_still_materialize_at_create(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, explicit="lanes_with_coord", standing_on="work")
    meta = json.loads((mission.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["topology_source"] == "explicit" and meta.get("coordination_branch")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["settled_this_run"] is False


def test_five_wp_one_code_lane_settles_single_branch(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, ("docs/a.md", "docs/b.md", "docs/c.md", "docs/d.md", "src/one.py"), planning=(1, 2, 3, 4))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["rule"] == "code_lanes_le_1"
    assert current_branch(mission.root) == mission.topic


def test_explicit_topology_wins(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES, explicit="single_branch", standing_on="work")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["settled_this_run"] is False
    assert json.loads((mission.root_mission_dir / "meta.json").read_text(encoding="utf-8"))["topology"] == "single_branch"


def test_refinalize_never_redecides(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    assert run_finalize(mission)[0] == 0
    decision_before = meta_at(mission.root, mission.topic, mission.slug)["topology_decision"]
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["settled_this_run"] is False
    assert meta_at(mission.root, mission.topic, mission.slug)["topology_decision"] == decision_before


def test_legacy_mission_without_source_never_changes() -> None:
    from specify_cli.lanes.topology_settlement import decide_topology_by_size

    sizes = {"wp_count": 9, "code_lane_count": 5, "target_protected": True}
    assert decide_topology_by_size({"topology": "single_branch"}, **sizes) is None
    assert decide_topology_by_size({"topology_source": "default", "topology_settled": True}, **sizes) is None
    provisional = decide_topology_by_size({"topology_source": "default", "topology_settled": False, "topology": "single_branch"}, **sizes)
    assert provisional is not None and provisional.to_topology == "lanes_with_coord"


def test_canceled_wps_not_counted_planning_wps_counted(tmp_path: Path) -> None:
    from specify_cli.lanes.topology_settlement import decide_topology_by_size

    provisional = {"topology_source": "default", "topology_settled": False}
    # Ties settle single_branch: two WPs, or two code lanes.
    tie = decide_topology_by_size(provisional, wp_count=2, code_lane_count=2, target_protected=False)
    assert tie is not None and tie.to_topology == "single_branch"
    zero = decide_topology_by_size(provisional, wp_count=4, code_lane_count=0, target_protected=False)
    assert zero is not None and zero.to_topology == "single_branch"
    # A planning-artifact WP counts toward the WP count: three WPs, two code lanes -> lanes_with_coord.
    mission = make_default_mission(tmp_path, ("docs/plan.md", "src/one.py", "src/two.py"), planning=(1,))
    code, payload = run_finalize(mission, "--validate-only")
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert decision["wp_count"] == 3 and decision["code_lane_count"] == 2 and decision["settled_topology"] == "lanes_with_coord"


# ---------------------------------------------------------------------------
# T084 preview, report, refusal
# ---------------------------------------------------------------------------


def test_validate_only_previews_and_writes_nothing(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    tips = branch_tips(mission.root)
    status = git(mission.root, "status", "--porcelain", "--untracked-files=all")
    code, payload = run_finalize(mission, "--validate-only")
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert decision["preview"] is True and decision["settled_this_run"] is False
    assert decision["settled_topology"] == "lanes_with_coord"
    assert branch_tips(mission.root) == tips
    assert git(mission.root, "status", "--porcelain", "--untracked-files=all") == status
    assert current_branch(mission.root) == mission.topic and not mission.coord_mission_dir.exists()


def test_finalize_json_reports_decision(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert payload["result"] == "success"
    assert set(payload["topology_decision"]) == {
        "settled_this_run",
        "topology_source",
        "provisional_topology",
        "settled_topology",
        "rule",
        "wp_count",
        "code_lane_count",
        "target_protected",
        "preview",
    }


def test_settlement_refuses_occupied_or_dirty_write_checkout(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    (mission.root / "stray.txt").write_text("operator work\n", encoding="utf-8")
    tips = branch_tips(mission.root)
    code, payload = run_finalize(mission)
    assert code == 1
    assert payload["error_code"] == "WRITE_CHECKOUT_DIRTY"
    assert branch_tips(mission.root) == tips and current_branch(mission.root) == mission.topic
    # Control: once the stray file is gone the same Mission settles.
    (mission.root / "stray.txt").unlink()
    assert run_finalize(mission)[0] == 0


def test_settlement_refuses_occupied_write_checkout(tmp_path: Path) -> None:
    from specify_cli.lanes import topology_settlement

    mission = make_default_mission(tmp_path, THREE_LANES)
    tips = branch_tips(mission.root)
    with patch("specify_cli.lanes.checkout_occupancy.in_progress_wps_in_write_checkout", return_value=[("other-mission", "WP09")]):
        code, payload = run_finalize(mission)
    assert payload.get("error_code") != topology_settlement.TOPOLOGY_SETTLEMENT_REFUSED
    assert code == 1 and payload["error_code"] == "WRITE_CHECKOUT_OCCUPIED"
    assert branch_tips(mission.root) == tips and current_branch(mission.root) == mission.topic


# ---------------------------------------------------------------------------
# T089 no-redecide pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative",
    ["src/specify_cli/cli/commands/agent/tasks_finalize.py", "src/specify_cli/migration/mission_state.py"],
)
def test_repair_paths_never_settle(relative: str) -> None:
    """FR-054 / C-011: the legacy repair finalize and the doctor rebuild never call the size decision."""
    tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    forbidden = {"decide_topology_by_size", "_decide_topology_by_size", "settle_topology", "_apply_topology_settlement"}
    assert not (names | imported) & forbidden
