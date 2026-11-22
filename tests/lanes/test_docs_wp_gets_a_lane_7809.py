"""A docs work package gets its own lane in a lane topology (#7809, ADR 2026-11-06-3 Amendment 2026-11-22).

In a lane Mission a ``planning_artifact`` work package was placed on ``lane-planning``,
whose branch is the target branch, so every gate looked for its work there. The
operator rulings (Decision Moments ``specify.planning.*``, 2026-11-22):

- **Normalise kind:** in a lane topology ``finalize-tasks`` records a
  ``planning_artifact`` work package that owns any path outside ``kitty-specs/`` as
  ``execution_mode: code_change``, with a notice, so it gets its own lane.
- **Refuse, split it:** a work package that mixes ``kitty-specs/`` with other paths is
  refused ``INVALID_WP_OWNED_FILES_KITTY_SPECS`` with a split remedy.
- **Count it:** the size-based topology settlement counts such a work package as a code lane.

``single_branch`` is untouched. Every test drives the real ``agent mission create`` core
and the real ``finalize-tasks`` command on a real git repository.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = (
    "# Spec\n\n## Functional Requirements\n| ID | Requirement | Acceptance Criteria | Status |\n"
    "| --- | --- | --- | --- |\n| FR-001 | Requirement | Test passes. | proposed |\n"
)
CODE = "code_change"
PLANNING = "planning_artifact"
SPEC_DIR_TOKEN = "<mission-dir>"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@dataclass(frozen=True)
class WorkPackage:
    """One authored work package: its owned paths and its declared kind."""

    owned: tuple[str, ...]
    mode: str


@dataclass(frozen=True)
class Mission:
    root: Path
    slug: str
    topic: str
    root_mission_dir: Path

    @property
    def coord_mission_dir(self) -> Path:
        return self.root / ".worktrees" / f"{self.slug}-coord" / "kitty-specs" / self.slug


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def _init_repo(tmp_path: Path) -> Path:
    from tests.integration.test_placement_partition_golden_path import _init_git_repo

    root = tmp_path / "repo"
    root.mkdir()
    _init_git_repo(root)
    (root / ".gitignore").write_text(".worktrees/\n.kittify/derived/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "config")
    return root


def _yaml_list(values: Sequence[str]) -> str:
    return "".join(f"  - {value}\n" for value in values)


def _write_wps(mission_dir: Path, slug: str, wps: Sequence[WorkPackage]) -> None:
    (mission_dir / "spec.md").write_text(SPEC, encoding="utf-8")
    (mission_dir / "tasks").mkdir(exist_ok=True)
    ids = [f"WP{index:02d}" for index in range(1, len(wps) + 1)]
    (mission_dir / "tasks.md").write_text("# Tasks\n\n" + "".join(f"## {wp}\n\nNo dependencies.\n\n" for wp in ids), encoding="utf-8")
    for wp_id, wp in zip(ids, wps, strict=True):
        owned = [path.replace(SPEC_DIR_TOKEN, f"kitty-specs/{slug}") for path in wp.owned]
        (mission_dir / "tasks" / f"{wp_id}-work.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Work {wp_id}\ndependencies: []\nrequirement_refs: [FR-001]\nsubtasks: []\n"
            f"owned_files:\n{_yaml_list(owned)}authoritative_surface: {owned[0]}\nexecution_mode: {wp.mode}\n"
            f"create_intent:\n{_yaml_list(owned)}---\n\n# {wp_id}\n",
            encoding="utf-8",
        )


def make_mission(tmp_path: Path, wps: Sequence[WorkPackage]) -> Mission:
    """A Mission created with no ``--topology`` (provisional), its work packages committed and ready to finalize."""
    from mission_runtime import MissionTopology
    from specify_cli.core.mission_creation import create_mission_core
    from specify_cli.meta_keys import TopologySource

    root = _init_repo(tmp_path)
    result = create_mission_core(
        root,
        "probe",
        allow_worktree_context=True,
        friendly_name="Probe",
        purpose_tldr="Deliver the probe for the docs lane tests.",
        purpose_context="This mission exercises docs work package placement at the first finalize end to end.",
        topology=MissionTopology.SINGLE_BRANCH,
        topology_source=TopologySource.DEFAULT,
    )
    _write_wps(result.feature_dir, result.mission_slug, wps)
    git(root, "add", "kitty-specs")
    git(root, "commit", "-qm", "tasks")
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    return Mission(root=root, slug=result.mission_slug, topic=str(meta.get("mission_branch") or ""), root_mission_dir=result.feature_dir)


def run_finalize(mission: Mission, *extra: str, json_output: bool = True) -> tuple[int, dict[str, object], str]:
    """The real ``finalize-tasks``; returns ``(exit_code, last JSON object, whole output)``."""
    from specify_cli.cli.commands.agent.mission import app
    from specify_cli.core.checkout_identity import CheckoutIdentity

    root = mission.root
    args = ["finalize-tasks", "--mission", mission.slug, *(["--json"] if json_output else []), *extra]
    with (
        patch(
            "specify_cli.cli.commands.agent.mission_finalize.resolve_checkout_identity",
            side_effect=lambda _cwd, intent: CheckoutIdentity(invoking_root=root, canonical_target=root, is_owner=True, intent=intent),
        ),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=root),
        patch("specify_cli.cli.commands.agent.mission.run_git_preflight", return_value=type("P", (), {"passed": True})()),
    ):
        result = CliRunner().invoke(app, args, catch_exceptions=False)
    payloads = [json.loads(line) for line in result.output.splitlines() if line.startswith("{")]
    return result.exit_code, (payloads[-1] if payloads else {"raw": result.output}), result.output


def _committed(mission: Mission, relpath: str) -> str:
    return git(mission.root, "show", f"{mission.topic}:kitty-specs/{mission.slug}/{relpath}")


def _lane_of(lanes: dict[str, object], wp_id: str) -> str:
    raw_lanes = lanes["lanes"]
    assert isinstance(raw_lanes, list)
    for lane in raw_lanes:
        if wp_id in lane["wp_ids"]:
            return str(lane["lane_id"])
    raise AssertionError(f"{wp_id} is in no lane: {lanes}")


def _execution_mode(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("execution_mode:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"no execution_mode in:\n{text}")


TWO_CODE_ONE_DOCS = (
    WorkPackage(("src/a/mod.py",), CODE),
    WorkPackage(("src/b/mod.py",), CODE),
    WorkPackage(("docs/x.md",), PLANNING),
)
NOTICE = "Notice: WP03 owns paths outside kitty-specs/ (docs/x.md); recorded as code_change so it gets its own lane."


def test_docs_wp_gets_its_own_lane_and_is_recorded_code_change(tmp_path: Path) -> None:
    mission = make_mission(tmp_path, TWO_CODE_ONE_DOCS)
    code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict)
    assert decision["settled_topology"] == "lanes_with_coord"
    assert decision["code_lane_count"] == 3, "the docs work package counts as a code lane"
    assert payload["kind_normalised"] == [
        {"wp_id": "WP03", "from": PLANNING, "to": CODE, "paths_outside_kitty_specs": ["docs/x.md"]},
    ]
    lanes = json.loads(_committed(mission, "lanes.json"))
    docs_lane = _lane_of(lanes, "WP03")
    assert docs_lane != "lane-planning"
    assert docs_lane not in {_lane_of(lanes, "WP01"), _lane_of(lanes, "WP02")}
    assert _execution_mode(_committed(mission, "tasks/WP03-work.md")) == CODE
    assert _execution_mode(_committed(mission, "tasks/WP01-work.md")) == CODE


def test_docs_wp_normalisation_prints_a_notice(tmp_path: Path) -> None:
    mission = make_mission(tmp_path, TWO_CODE_ONE_DOCS)
    code, _payload, output = run_finalize(mission, json_output=False)
    assert code == 0, output
    assert NOTICE in " ".join(output.split())


def test_validate_only_reports_normalisation_and_writes_nothing(tmp_path: Path) -> None:
    mission = make_mission(tmp_path, TWO_CODE_ONE_DOCS)
    head_before = git(mission.root, "rev-parse", "HEAD")
    wp_file = mission.root_mission_dir / "tasks" / "WP03-work.md"
    text_before = wp_file.read_text(encoding="utf-8")
    code, payload, _output = run_finalize(mission, "--validate-only")
    assert code == 0, payload
    assert payload["kind_normalised"] == [
        {"wp_id": "WP03", "from": PLANNING, "to": CODE, "paths_outside_kitty_specs": ["docs/x.md"]},
    ]
    assert wp_file.read_text(encoding="utf-8") == text_before
    assert git(mission.root, "rev-parse", "HEAD") == head_before


def test_docs_wp_counts_toward_settlement(tmp_path: Path) -> None:
    mission = make_mission(
        tmp_path,
        (
            WorkPackage(("src/a/mod.py",), CODE),
            WorkPackage(("docs/x.md",), PLANNING),
            WorkPackage((f"{SPEC_DIR_TOKEN}/research.md",), PLANNING),
        ),
    )
    code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict)
    assert decision["settled_topology"] == "lanes_with_coord", decision
    assert decision["code_lane_count"] == 2
    lanes = json.loads(_committed(mission, "lanes.json"))
    assert _lane_of(lanes, "WP03") == "lane-planning", "a kitty-specs-only work package stays on the planning lane"
    assert _lane_of(lanes, "WP02") != "lane-planning"
    assert _execution_mode(_committed(mission, "tasks/WP03-work.md")) == PLANNING


def test_mixed_wp_is_refused_with_split_remedy(tmp_path: Path) -> None:
    mission = make_mission(
        tmp_path,
        (
            WorkPackage(("src/a/mod.py",), CODE),
            WorkPackage(("src/b/mod.py",), CODE),
            WorkPackage((f"{SPEC_DIR_TOKEN}/notes.md", "docs/x.md"), PLANNING),
        ),
    )
    code, payload, _output = run_finalize(mission)
    assert code == 1, payload
    assert payload["error_code"] == "INVALID_WP_OWNED_FILES_KITTY_SPECS"
    assert "split" in str(payload.get("remedy", "")).lower(), payload
    assert {"wp_id": "WP03", "path": f"kitty-specs/{mission.slug}/notes.md"} in payload["invalid_owned_files"]


def test_two_wp_mission_settles_single_branch_and_keeps_kinds(tmp_path: Path) -> None:
    mission = make_mission(
        tmp_path,
        (
            WorkPackage(("src/a/mod.py",), CODE),
            WorkPackage(("docs/x.md",), PLANNING),
        ),
    )
    code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict)
    assert decision["settled_topology"] == "single_branch"
    assert payload["kind_normalised"] == []
    wp_text = (mission.root_mission_dir / "tasks" / "WP02-work.md").read_text(encoding="utf-8")
    assert _execution_mode(wp_text) == PLANNING


def test_settled_single_branch_refinalize_never_reads_the_status_log(tmp_path: Path) -> None:
    """single_branch is untouched: a re-finalize never reads the started set, so an unreadable surface cannot refuse it (F1)."""
    mission = make_mission(
        tmp_path,
        (
            WorkPackage(("src/a/mod.py",), CODE),
            WorkPackage(("docs/x.md",), PLANNING),
        ),
    )
    code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["settled_topology"] == "single_branch"
    assert (mission.root_mission_dir / "lanes.json").exists()
    # An unreadable status surface makes the fail-closed started-set reader raise; single_branch must never call it.
    unreadable = AssertionError("status_unreadable: the started set was read for a settled single_branch Mission")
    with patch("specify_cli.cli.commands.agent.mission_finalize_lanes._read_started_wp_ids", side_effect=unreadable):
        code, payload, _output = run_finalize(mission, "--validate-only")
    assert code == 0, payload
    assert payload["kind_normalised"] == []


def test_started_docs_wp_keeps_planning_artifact_and_its_lane_on_refinalize(tmp_path: Path) -> None:
    """Frozen membership (ADR 2026-10-04-2): a history-started docs WP is never rewritten (review N1)."""
    from specify_cli.ownership.kind_normalisation import KindNormalisation
    from specify_cli.status.emit import emit_status_transition

    mission = make_mission(
        tmp_path,
        (
            WorkPackage(("src/a/mod.py",), CODE),
            WorkPackage(("src/b/mod.py",), CODE),
            WorkPackage(("src/c/mod.py",), CODE),
            WorkPackage(("docs/x.md",), PLANNING),
        ),
    )
    # A lane Mission finalized before #7809: its docs WP sits on lane-planning as planning_artifact.
    with patch(
        "specify_cli.cli.commands.agent.mission_finalize._kind_normalisation_for",
        side_effect=lambda _dir, _root, _slug, manifests, _meta, **_kw: KindNormalisation(manifests=dict(manifests), rewritten=()),
    ):
        code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    assert payload["topology_decision"]["settled_topology"] == "lanes_with_coord"
    assert _lane_of(json.loads(_committed(mission, "lanes.json")), "WP04") == "lane-planning"

    emit_status_transition(mission_dir=mission.coord_mission_dir, mission_slug=mission.slug, wp_id="WP04", to_lane="claimed", actor="test", repo_root=mission.root)

    code, payload, _output = run_finalize(mission)
    assert code == 0, payload
    assert payload["kind_normalised"] == []
    assert _lane_of(json.loads((mission.coord_mission_dir / "lanes.json").read_text(encoding="utf-8")), "WP04") == "lane-planning"
    assert _execution_mode((mission.coord_mission_dir / "tasks" / "WP04-work.md").read_text(encoding="utf-8")) == PLANNING
