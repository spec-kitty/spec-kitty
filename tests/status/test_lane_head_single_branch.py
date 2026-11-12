"""S8 stamp (#7283, FR-070): a ``single_branch`` Mission's transitions carry its write-branch head.

ADR ``2026-10-04-5`` Amendment 2026-11-06: every lifecycle transition of a work package in a
Mission whose STORED topology is ``single_branch`` is stamped with the head of the Mission write
branch (``refs/heads/<meta.mission_branch>``) as ``policy_metadata.lane_head``. The decision is
keyed on the stored topology, never on ``is_planning_lane`` or ``execution_mode: direct_repo``:
a ``lanes`` Mission's planning-lane work package stays unstamped (positive control), and a
commit-to-target Mission (write branch == target) stamps the target head (#7578; it stays
unbounded in consolidation, FR-078).

The probe tests build their Missions by hand in a real git repository, so they hold whatever
shape the shared flat fixture of ``tests/integration/coord_topology_fixture.py`` takes. The CLI
test drives the real ``agent mission create`` / ``finalize-tasks`` / ``move-task`` commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.consolidation import approved_bound
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.single_branch_landing import (
    expected_consolidate_checkout,
    is_single_branch_mission,
    minted_branch_from_meta,
    minted_write_branch,
    write_branch_for,
)
from specify_cli.status.lane_head import LANE_HEAD_KEY, read_lane_head

pytestmark = [pytest.mark.git_repo]

_TARGET = "main"
_SB_SLUG = "sb-fixture-01SBFIXT"
_SB_BRANCH = "kitty/mission-sb-fixture-01SBFIXT"
_LANES_SLUG = "lanes-fixture-01LNFIXT"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _write_mission(repo: Path, slug: str, *, topology: str, mission_branch: str | None) -> None:
    """``meta.json`` and a one-lane ``lane-planning`` ``lanes.json`` holding WP01, as finalize writes them."""
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": f"{slug[-8:]}000000000000000000",
        "mission_slug": slug,
        "slug": slug,
        "mission_type": "software-dev",
        "target_branch": _TARGET,
        "vcs": "git",
        "topology": topology,
    }
    if mission_branch is not None:
        meta["mission_branch"] = mission_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    lanes = {
        "version": 1,
        "mission_slug": slug,
        "mission_id": meta["mission_id"],
        "mission_branch": mission_branch or _TARGET,
        "target_branch": _TARGET,
        "lanes": [
            {
                "lane_id": "lane-planning",
                "wp_ids": ["WP01"],
                "write_scope": ["src/**"],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-11-06T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes, indent=2), encoding="utf-8")


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def two_missions(tmp_path: Path) -> Path:
    """One repository holding a minted ``single_branch`` Mission and a ``lanes`` Mission.

    Both put WP01 in ``lane-planning``. The write checkout sits on the minted Mission branch,
    which carries one implementation commit beyond ``main``, so its head differs from the target's.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _write_mission(repo, _SB_SLUG, topology="single_branch", mission_branch=_SB_BRANCH)
    _write_mission(repo, _LANES_SLUG, topology="lanes", mission_branch=f"kitty/mission-{_LANES_SLUG}")
    _commit(repo, "seed.txt", "seed\n", "seed: two missions")
    _git(repo, "checkout", "-qb", _SB_BRANCH)
    _commit(repo, "src/impl.py", "VALUE = 1\n", "feat(WP01): implement")
    return repo


@pytest.mark.fast
def test_single_branch_probe_stamps_mission_branch_head(two_missions: Path) -> None:
    """FR-070: the stamp is ``refs/heads/<meta.mission_branch>``, never the target the planning-lane alias resolves to."""
    head = _git(two_missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")
    assert head != _git(two_missions, "rev-parse", f"refs/heads/{_TARGET}")

    assert read_lane_head(repo_root=two_missions, mission_slug=_SB_SLUG, wp_id="WP01").sha == head


@pytest.mark.fast
def test_single_branch_stamp_follows_the_mission_branch_from_another_checkout(two_missions: Path) -> None:
    """The stamp reads the branch ref, not the checkout's HEAD: it is the same from a checkout on the target."""
    head = _git(two_missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")
    _git(two_missions, "checkout", "-q", _TARGET)

    assert read_lane_head(repo_root=two_missions, mission_slug=_SB_SLUG, wp_id="WP01").sha == head


@pytest.mark.fast
def test_single_branch_stamp_needs_no_lane_map(two_missions: Path) -> None:
    """The decision is keyed on the stored topology in ``meta.json``, never on ``lanes.json``."""
    (two_missions / "kitty-specs" / _SB_SLUG / "lanes.json").unlink()
    head = _git(two_missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")

    assert read_lane_head(repo_root=two_missions, mission_slug=_SB_SLUG, wp_id="WP01").sha == head


@pytest.mark.fast
def test_lanes_planning_lane_wp_stays_unstamped(two_missions: Path) -> None:
    """Positive control, same run: a ``lanes`` Mission's planning-lane WP returns no stamp, while the ``single_branch`` one does."""
    sb_stamp = read_lane_head(repo_root=two_missions, mission_slug=_SB_SLUG, wp_id="WP01").sha
    lanes_stamp = read_lane_head(repo_root=two_missions, mission_slug=_LANES_SLUG, wp_id="WP01").sha

    assert sb_stamp == _git(two_missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")
    assert lanes_stamp is None


@pytest.mark.fast
def test_commit_to_target_single_branch_stamps_the_target_head(tmp_path: Path) -> None:
    """#7578: a ``single_branch`` Mission whose write branch is its target stamps the target head (it was unstamped before)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _write_mission(repo, _SB_SLUG, topology="single_branch", mission_branch=None)
    _commit(repo, "seed.txt", "seed\n", "seed")

    assert read_lane_head(repo_root=repo, mission_slug=_SB_SLUG, wp_id="WP01").sha == _git(repo, "rev-parse", f"refs/heads/{_TARGET}")


@pytest.mark.fast
def test_single_branch_probe_without_the_mission_branch_is_no_stamp_not_a_crash(two_missions: Path) -> None:
    """Best-effort (C-1): a recorded Mission branch that does not exist yields no stamp; the bound treats it per FR-074."""
    _git(two_missions, "checkout", "-q", _TARGET)
    _git(two_missions, "branch", "-D", _SB_BRANCH)

    assert read_lane_head(repo_root=two_missions, mission_slug=_SB_SLUG, wp_id="WP01").sha is None


# ---------------------------------------------------------------------------
# The helpers the stamp and the bound share (T062, T063, T065)
# ---------------------------------------------------------------------------


def _manifest(slug: str, mission_branch: str) -> LanesManifest:
    lane = ExecutionLane(lane_id="lane-planning", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    return LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=None,
        mission_branch=mission_branch,
        target_branch=_TARGET,
        lanes=[lane],
        computed_at="2026-11-06T00:00:00+00:00",
        computed_from="test",
    )


@pytest.mark.fast
@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"topology": "single_branch", "mission_branch": "kitty/mission-x"}, "kitty/mission-x"),
        ({"topology": "single_branch"}, _TARGET),
        ({"topology": "lanes", "mission_branch": "kitty/mission-x"}, _TARGET),
        ({"mission_branch": "kitty/mission-x"}, _TARGET),
    ],
)
def test_write_branch_for_is_the_stored_single_branch_rule(meta: dict[str, object], expected: str) -> None:
    """``meta.json`` decides, over the STORED topology; the manifest's own ``mission_branch`` copy is never read."""
    assert write_branch_for(_manifest("m", "kitty/stale-copy"), meta) == expected
    assert minted_branch_from_meta(meta, _TARGET) == (None if expected == _TARGET else expected)


@pytest.mark.fast
def test_minted_write_branch_reads_meta_without_a_manifest(two_missions: Path) -> None:
    (two_missions / "kitty-specs" / _SB_SLUG / "lanes.json").unlink()

    assert minted_write_branch(two_missions, _SB_SLUG) == _SB_BRANCH
    assert minted_write_branch(two_missions, _LANES_SLUG) is None
    assert is_single_branch_mission(two_missions, _manifest(_SB_SLUG, _SB_BRANCH))
    assert not is_single_branch_mission(two_missions, _manifest(_LANES_SLUG, _SB_BRANCH))


@pytest.mark.fast
def test_minted_write_branch_needs_a_recorded_target(two_missions: Path) -> None:
    meta_path = two_missions / "kitty-specs" / _SB_SLUG / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["target_branch"]
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    assert minted_write_branch(two_missions, _SB_SLUG) is None


@pytest.mark.fast
def test_expected_consolidate_checkout_names_the_minted_branch(two_missions: Path) -> None:
    assert expected_consolidate_checkout(two_missions, _manifest(_SB_SLUG, _SB_BRANCH), _TARGET) == _SB_BRANCH
    assert expected_consolidate_checkout(two_missions, _manifest(_LANES_SLUG, _SB_BRANCH), _TARGET) == _TARGET


@pytest.mark.fast
def test_single_branch_approval_is_bounded_and_a_lanes_planning_lane_is_not(two_missions: Path) -> None:
    """T065: the warnings speak for a minted ``single_branch`` Mission, never for a ``lanes`` planning lane or an unknown Mission."""
    assert approved_bound._approval_is_bounded(two_missions, _SB_SLUG, "WP01")
    assert not approved_bound._approval_is_bounded(two_missions, _LANES_SLUG, "WP01")
    assert not approved_bound._approval_is_bounded(two_missions / "missing", "no-such-mission", "WP01")


@pytest.mark.fast
def test_stamp_refusal_names_missing_then_off_branch_stamps(two_missions: Path) -> None:
    """T063: the stamp half of ``check_lane`` -- every missing stamp together, else the first stamp the branch does not reach."""
    on_branch = _git(two_missions, "rev-parse", f"refs/heads/{_SB_BRANCH}")
    _git(two_missions, "checkout", "-q", _TARGET)
    off_branch = _commit(two_missions, "elsewhere.txt", "x\n", "off the Mission branch")

    missing = approved_bound.stamp_refusal(two_missions, stamps={"WP01": None, "WP02": on_branch, "WP03": None}, lane_id="lane-planning", branch=_SB_BRANCH)
    assert missing is not None
    assert (missing.code, missing.wp_ids) == (approved_bound.BoundRefusalCode.APPROVAL_STAMP_MISSING, ("WP01", "WP03"))

    off = approved_bound.stamp_refusal(two_missions, stamps={"WP01": on_branch, "WP02": off_branch}, lane_id="lane-planning", branch=_SB_BRANCH)
    assert off is not None
    assert (off.code, off.wp_ids, off.stamp) == (approved_bound.BoundRefusalCode.APPROVAL_STAMP_NOT_ON_LANE, ("WP02",), off_branch)

    assert approved_bound.stamp_refusal(two_missions, stamps={"WP01": on_branch}, lane_id="lane-planning", branch=_SB_BRANCH) is None


# ---------------------------------------------------------------------------
# Through the real CLI
# ---------------------------------------------------------------------------

_CLI = [sys.executable, "-m", "specify_cli"]


def _env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(home / "home"),
        XDG_CONFIG_HOME=str(home / "xc"),
        XDG_CACHE_HOME=str(home / "xcache"),
        XDG_DATA_HOME=str(home / "xd"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
    )
    # A protected-branch override would make create skip the mint this test is about.
    env.pop("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", None)
    for key in ("home", "xc", "xcache", "xd"):
        (home / key).mkdir(parents=True, exist_ok=True)
    return env


def _sk(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run([*_CLI, *args], cwd=repo, env=env, capture_output=True, text=True, timeout=400)
    if proc.returncode != 0:
        raise AssertionError(f"spec-kitty {' '.join(args)} failed rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def _minted_single_branch_mission(tmp_path: Path) -> tuple[Path, dict[str, str], str, str]:
    """A ``single_branch`` Mission created on protected ``main``, finalized with WP01; returns (repo, env, slug, mission branch)."""
    env = _env(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", _TARGET)
    _git(repo, "config", "user.name", "QA")
    _git(repo, "config", "user.email", "qa@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    _sk(repo, env, "init", "--ai", "claude", "--non-interactive")
    _commit(repo, "src/shared.py", "A = 1\n", "init")
    created = _sk(
        repo,
        env,
        *("agent", "mission", "create", "fx", "--mission-type", "software-dev", "--topology", "single_branch"),
        *("--branch-strategy", "already-confirmed", "--target-branch", _TARGET, "--friendly-name", "fx"),
        *("--purpose-tldr", "fx", "--purpose-context", "QA fixture.", "--json"),
    )
    slug = json.loads(created.stdout)["mission_slug"]
    fd = repo / "kitty-specs" / slug
    meta = json.loads((fd / "meta.json").read_text(encoding="utf-8"))
    mission_branch = meta["mission_branch"]
    assert mission_branch != _TARGET, "fixture: create must mint a Mission branch on protected main"
    (fd / "spec.md").write_text("# Spec\n\n## Requirements\n\n- **FR-001**: things work.\n", encoding="utf-8")
    (fd / "plan.md").write_text("# Plan\n\nModules.\n", encoding="utf-8")
    (fd / "tasks").mkdir(exist_ok=True)
    (fd / "tasks.md").write_text("# Tasks\n\n## Work Package WP01: m1\n\n**Dependencies**: None\n\nRequirement refs: FR-001\n\n- [ ] T1 do m1\n", encoding="utf-8")
    (fd / "tasks" / "WP01-m1.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 m1\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "authoritative_surface: src/m1/\nowned_files:\n  - src/m1/**\nsubtasks:\n  - T1\n---\n# WP01 m1\n\n- [ ] T1 do m1\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "planning")
    _sk(repo, env, "agent", "mission", "finalize-tasks", "--mission", slug, "--json")
    return repo, env, slug, mission_branch


def _lifecycle_events(repo: Path, slug: str) -> list[dict[str, object]]:
    lines = (repo / "kitty-specs" / slug / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
    return [event for event in (json.loads(line) for line in lines if line.strip()) if "to_lane" in event]


@pytest.mark.integration
def test_move_task_approved_records_lane_head_single_branch(tmp_path: Path) -> None:
    """FR-070 end to end: the ``approved`` event ``move-task`` persists carries the Mission branch head as ``lane_head``."""
    repo, env, slug, mission_branch = _minted_single_branch_mission(tmp_path)

    _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "in_progress", "--agent", "alice", "--note", "claim", "--mission", slug)
    _commit(repo, "src/m1/real.py", "VALUE = 1\n", "feat(WP01): implement m1")
    _sk(repo, env, "agent", "tasks", "mark-status", "T1", "--status", "done", "--mission", slug)
    reviewed_head = _git(repo, "rev-parse", f"refs/heads/{mission_branch}")
    _sk(repo, env, "agent", "tasks", "move-task", "WP01", "--to", "approved", "--agent", "bob", "--note", "lgtm", "--force", "--mission", slug)

    events = [event for event in _lifecycle_events(repo, slug) if event["wp_id"] == "WP01"]
    approved = [event for event in events if event["to_lane"] == "approved"]
    assert approved, f"fixture: WP01 never reached approved; events={events}"
    metadata = approved[-1].get("policy_metadata") or {}
    assert isinstance(metadata, dict)
    stamp = metadata.get(LANE_HEAD_KEY)
    assert isinstance(stamp, str) and stamp, f"the approval must carry the Mission branch head; metadata={metadata}"
    # The stamp is the Mission branch head when the approval was persisted: the reviewed implementation
    # plus only the approval's own auto-committed bookkeeping (the review-cycle record), never the target.
    _git(repo, "merge-base", "--is-ancestor", reviewed_head, stamp)
    _git(repo, "merge-base", "--is-ancestor", stamp, f"refs/heads/{mission_branch}")
    after_review = _git(repo, "diff", "--name-only", reviewed_head, stamp).split()
    assert all(path.startswith(f"kitty-specs/{slug}/") for path in after_review), after_review
    assert stamp != _git(repo, "rev-parse", f"refs/heads/{_TARGET}")
    claimed = [event for event in events if event["to_lane"] in ("claimed", "in_progress")]
    assert claimed and all(isinstance(event.get("policy_metadata"), dict) and event["policy_metadata"].get(LANE_HEAD_KEY) for event in claimed), (
        f"every lifecycle transition is stamped, the claim included; events={claimed}"
    )
