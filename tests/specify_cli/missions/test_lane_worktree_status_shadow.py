"""A lane worktree root is never the status surface (#6466).

A mission's work-package lane state has exactly one authority: the resolved status surface —
the coordination husk on a coordination-routed mission, the primary/mission-branch copy on a
branch-flat (`lanes`) mission. A lane worktree carries a fork-time *copy* of
``kitty-specs/<slug>/`` (``status.events.jsonl``, and ``status.json`` once the fork post-dates
the first snapshot). Before this guard, a status read anchored at the lane worktree root answered
from that copy: the work package read as ``planned`` while the authority already said
``in_progress``, so the routine ``planned -> for_review`` transition was not a legal edge and the
operator's only escape was the ``--force`` hatch reserved for genuine process exceptions.

These tests build a real registered lane worktree through the orchestrator-api surface (the same
blueprint as ``tests/specify_cli/lanes/test_for_review_gate_parity.py``) and pin four things:

* the authoritative read (primary anchor) reports the post-fork lane — the fixture is real;
* a read anchored at the lane worktree root reports the SAME lane, not the fork-time shadow;
* a coordination-routed mission anchored at its lane worktree root still resolves the
  coordination husk (the authority is not displaced);
* an independent clone (not a linked worktree) still answers from its own checkout.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.missions._read_path_resolver import (
    resolve_feature_dir_for_mission,
    resolve_handle_to_read_path,
)
from specify_cli.orchestrator_api.commands import app
from specify_cli.status import wp_snapshot_state
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

SLUG = "shadow"
MID8 = "01KSHAD0"
MISSION_ID = "01KSHAD00000000000000000000"
MISSION_DIRNAME = f"{SLUG}-{MID8}"
MISSION_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
COORD_BRANCH = MISSION_BRANCH
TOPIC_BRANCH = "fixture-topic"

_WP_FILE = "---\nwork_package_id: WP01\ntitle: Shadow WP01\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _valid_policy_json() -> str:
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


def _manifest(*, mission_branch: str, target_branch: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_DIRNAME,
        mission_id=MISSION_ID,
        mission_branch=mission_branch,
        target_branch=target_branch,
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


def _seed_event() -> StatusEvent:
    return StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-06-19T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


def _seed_planned_on_coord(repo: Path) -> None:
    """Coord topology: the status log is seeded on the coordination branch."""
    from specify_cli.coordination.status_service import (
        EventLogWriteContract,
        append_event_stream_log,
    )

    worktree = repo / ".worktrees" / "seed-coord"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    append_event_stream_log(
        EventLogWriteContract.coordination_transaction_append(worktree / "kitty-specs" / MISSION_DIRNAME),
        [_seed_event()],
    )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))


def _seed_planned_on_primary(repo: Path) -> None:
    """Branch-flat topology: the status log is committed on the mission branch."""
    from specify_cli.coordination.status_service import (
        EventLogWriteContract,
        append_event_stream_log,
    )

    append_event_stream_log(
        EventLogWriteContract.primary_checkout_append(repo / "kitty-specs" / MISSION_DIRNAME),
        [_seed_event()],
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed genesis->planned")


def _build_mission(root: Path, *, coordination: bool) -> Path:
    """Materialize a mission with a lanes manifest at ``root``.

    ``coordination=False`` is the branch-flat ``lanes`` shape: the mission dir and its status
    log are committed on the mission branch, which is also the target branch.
    ``coordination=True`` is the ``lanes_with_coord`` shape: the primary checkout sits on a
    non-protected topic branch and the status log lives on the coordination branch.
    """
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "root commit")
    landing_branch = TOPIC_BRANCH if coordination else MISSION_BRANCH
    _git(root, "checkout", "-q", "-b", landing_branch)

    feature_dir = root / "kitty-specs" / MISSION_DIRNAME
    (feature_dir / "tasks").mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "target_branch": landing_branch,
        "mission_branch": MISSION_BRANCH,
    }
    if coordination:
        meta["coordination_branch"] = COORD_BRANCH
        meta["topology"] = "lanes_with_coord"
    else:
        meta["topology"] = "lanes"
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (feature_dir / "tasks" / "WP01.md").write_text(_WP_FILE, encoding="utf-8")
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 Shadow WP01\n\n- [x] T001 subtask for WP01\n- [x] T002 subtask for WP01\n",
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        _manifest(mission_branch=MISSION_BRANCH, target_branch=landing_branch),
    )
    _git(root, "add", "kitty-specs")
    _git(root, "commit", "-q", "-m", "seed mission")
    if coordination:
        _git(root, "branch", COORD_BRANCH)
        _seed_planned_on_coord(root)
    else:
        _seed_planned_on_primary(root)
    return root


def _start_implementation(repo: Path) -> Path:
    """Allocate the lane worktree (planned->in_progress) and return its path."""
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo,
    ):
        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                MISSION_DIRNAME,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )
    assert result.exit_code == 0, result.output
    return Path(json.loads(result.output)["data"]["workspace_path"])


def _lane_of(feature_dir: Path) -> str | None:
    state = wp_snapshot_state(feature_dir, "WP01") or {}
    lane = state.get("lane")
    return str(lane) if lane is not None else None


def _lane_read_from_root(root: Path) -> str | None:
    """The lane a caller sees when the resolution is anchored at ``root``."""
    return _lane_of(resolve_feature_dir_for_mission(root, MISSION_DIRNAME, cwd=root))


def test_authoritative_read_reports_the_post_fork_lane(tmp_path: Path) -> None:
    """Control: the fixture really moves the WP after the lane worktree exists."""
    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)

    assert lane_worktree.is_dir()
    # The lane worktree's own copy is the fork-time shadow: it never saw the transition.
    lane_copy = lane_worktree / "kitty-specs" / MISSION_DIRNAME
    assert _lane_of(lane_copy) == "planned"
    # The authority (primary / mission branch) does hold the transition.
    assert _lane_read_from_root(repo) == "in_progress"


def test_lane_worktree_root_reads_the_authoritative_lane(tmp_path: Path) -> None:
    """A lane worktree root can never answer a status read from its stale copy (#6466)."""
    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)

    resolved = resolve_feature_dir_for_mission(lane_worktree, MISSION_DIRNAME, cwd=lane_worktree)
    assert resolved.name == MISSION_DIRNAME
    assert resolved != lane_worktree / "kitty-specs" / MISSION_DIRNAME, "a status read anchored at a lane worktree root resolved the lane worktree's fork-time copy"
    assert _lane_read_from_root(lane_worktree) == "in_progress"


def test_guarded_read_seam_also_re_anchors_a_lane_worktree_root(tmp_path: Path) -> None:
    """The single guarded read seam gives the same answer as the action-context resolver."""
    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)

    resolved = resolve_handle_to_read_path(lane_worktree, MISSION_DIRNAME)
    assert _lane_of(resolved) == "in_progress"


def test_coordination_husk_keeps_its_authority_from_a_lane_worktree_root(tmp_path: Path) -> None:
    """FR-002: the re-anchor never displaces a coordination mission's authority."""
    repo = _build_mission(tmp_path / "repo", coordination=True)
    lane_worktree = _start_implementation(repo)

    resolved = resolve_handle_to_read_path(lane_worktree, MISSION_DIRNAME)
    assert ".worktrees" in resolved.parts
    assert any(part.endswith("-coord") for part in resolved.parts), resolved
    assert _lane_of(resolved) == "in_progress"


def test_an_independent_clone_still_answers_from_its_own_checkout(tmp_path: Path) -> None:
    """A clone is not a linked worktree of the mission's repository: its copy stays authoritative."""
    repo = _build_mission(tmp_path / "repo", coordination=False)
    _start_implementation(repo)
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", str(repo), str(clone)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(clone, "checkout", "-q", MISSION_BRANCH)

    resolved = resolve_handle_to_read_path(clone, MISSION_DIRNAME)
    assert clone.resolve() in resolved.parents or resolved.parent == clone.resolve(), resolved
    assert _lane_of(resolved) == "in_progress"


def test_an_unregistered_worktree_shaped_directory_keeps_its_own_root(tmp_path: Path) -> None:
    """NFR-002 boundary: a husk (under ``.worktrees``, not registered) is not re-anchored."""
    repo = _build_mission(tmp_path / "repo", coordination=False)
    _start_implementation(repo)
    husk = repo / ".worktrees" / "not-a-worktree"
    (husk / "kitty-specs" / MISSION_DIRNAME).mkdir(parents=True)
    (husk / "kitty-specs" / MISSION_DIRNAME / "meta.json").write_text(
        (repo / "kitty-specs" / MISSION_DIRNAME / "meta.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    resolved = resolve_handle_to_read_path(husk, MISSION_DIRNAME)

    assert resolved == husk / "kitty-specs" / MISSION_DIRNAME


def test_an_unreadable_worktree_registry_keeps_the_callers_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: when the registry cannot be consulted the root is returned untouched.

    The helper must never guess a root: the pre-existing surfaces keep their own fail-closed
    behaviour, so a lane-rooted read behaves exactly as it did before this guard.
    """
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)
    lane_copy = lane_worktree / "kitty-specs" / MISSION_DIRNAME

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise WorktreeRegistryUnavailable(repo_root=repo, detail="registry unavailable")

    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.classify_worktree_topology",
        _boom,
    )

    assert resolve_handle_to_read_path(lane_worktree, MISSION_DIRNAME) == lane_copy


def test_a_primary_rooted_read_spends_no_worktree_registry_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard costs nothing on the common path: a repository root never consults git.

    NFR-001: a repository-rooted status read is the overwhelmingly common case, so the guard
    answers from ``get_main_repo_root`` and the ``.worktrees`` shape alone. Proven by making the
    registry classifier explode: a primary-rooted read must still resolve, and a lane-rooted read
    must fall back to the caller's root instead of raising.
    """
    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)

    calls: list[Path] = []

    def _explode(path: Path, **_kwargs: object) -> None:
        calls.append(path)
        raise AssertionError("the worktree registry was consulted for a non-negative case")

    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.classify_worktree_topology",
        _explode,
    )

    assert _lane_of(resolve_handle_to_read_path(repo, MISSION_DIRNAME)) == "in_progress"
    assert calls == []

    # A lane-rooted read does consult the classifier, and a registry failure keeps the caller's
    # root untouched (NFR-002) rather than raising out of the read seam.
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    def _unavailable(path: Path, **_kwargs: object) -> None:
        raise WorktreeRegistryUnavailable(repo_root=path, detail="registry unavailable")

    monkeypatch.setattr(
        "specify_cli.coordination.surface_resolver.classify_worktree_topology",
        _unavailable,
    )

    assert resolve_handle_to_read_path(lane_worktree, MISSION_DIRNAME) == (lane_worktree / "kitty-specs" / MISSION_DIRNAME)


def test_a_relative_lane_worktree_root_is_re_anchored_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller standing in the lane worktree hands in a relative root (``Path(".")``).

    The guard judges shape and git ancestry on the resolved path, so ``.`` from inside the lane
    worktree is still normalised instead of silently answering from the copy in the current
    directory.
    """
    repo = _build_mission(tmp_path / "repo", coordination=False)
    lane_worktree = _start_implementation(repo)

    monkeypatch.chdir(lane_worktree)

    resolved = resolve_handle_to_read_path(Path("."), MISSION_DIRNAME)

    assert lane_worktree.resolve() not in resolved.parents, resolved
    assert _lane_of(resolved) == "in_progress"
