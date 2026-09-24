"""Shared mock-free harness for the terminus-integrity red-first repros (WP01, #5001).

Every helper here builds a REAL on-disk git coordination mission and drives the
REAL ``spec-kitty`` CLI through ``subprocess`` -- ``_run_git`` / ``subprocess``
is NEVER mocked, so each repro exercises ``git/ref_advance.py``'s real
``update-ref`` argv (contract §"Property test"). Approved commit SHAs are ALWAYS
read from lane-branch git tips, never from ``status.events.jsonl`` rows (RN-Q3 /
contract Preconditions -- forbids the vacuous ``_assert_merged_wps_done_on_target``
pattern).

The harness is intentionally O(#WPs), not O(repo history) (NFR-003): reachability
is probed with ``git merge-base --is-ancestor`` and patch-id equivalence over the
small ``pre-merge-target..post-merge-target`` window, never a full history walk.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _now_iso() -> str:
    """UTC ISO-8601 timestamp (stdlib -- keeps fixture building import-light)."""
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Real-CLI wiring: run THIS worktree's ``src`` via ``python -m specify_cli`` so
# the subprocess exercises the pre-fix (and, after the fix WPs, post-fix) code.
# No installed-wheel dependency, no ``_run_git`` / subprocess seam patched.
# ---------------------------------------------------------------------------

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SRC = _WORKTREE_ROOT / "src"

# Fixture construction imports ``specify_cli`` / ``kernel`` from THIS worktree's
# ``src`` so the builders match the CLI-under-test exactly, regardless of how the
# venv / editable install resolves those packages.
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_MISSION_TYPE = "software-dev"
_STATUS_EVENTS_FILENAME = "status.events.jsonl"

# The canonical 9-lane happy path a WP walks to become merge-ready.
_APPROVE_CHAIN: tuple[tuple[str, str], ...] = (
    ("planned", "claimed"),
    ("claimed", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
)


# ---------------------------------------------------------------------------
# Low-level git helpers (real git, real subprocess)
# ---------------------------------------------------------------------------


def _run(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _git_out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.strip()


def git_rev(repo: Path, ref: str) -> str:
    """Resolve *ref* to a commit SHA (``""`` when the ref does not exist)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def commits_between(repo: Path, base: str, tip: str) -> list[str]:
    """Return the SHAs reachable from *tip* but not *base* (``git rev-list base..tip``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-list", f"{base}..{tip}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def patch_id(repo: Path, sha: str) -> str:
    """Return the stable patch-id of *sha* (identity of the change, not the commit).

    Patch-id equivalence lets the excluded-commit check catch cherry-picked,
    rebased, or re-lettered copies of canceled code -- the same diff under a new
    SHA (contract postcondition 1 / #4945 / #4977).
    """
    show = subprocess.run(
        ["git", "-C", str(repo), "show", sha],
        capture_output=True,
        text=True,
        check=False,
    )
    pid = subprocess.run(
        ["git", "-C", str(repo), "patch-id", "--stable"],
        input=show.stdout,
        capture_output=True,
        text=True,
        check=False,
    )
    first = pid.stdout.split()
    return first[0] if first else ""


def sha_reachable(repo: Path, sha: str, ref: str) -> bool:
    """True iff *sha* is an ancestor of (reachable from) *ref*."""
    if not sha:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def patch_ids_in_window(repo: Path, base: str, tip: str) -> set[str]:
    """Patch-ids of every commit in ``base..tip`` (the small post-merge window)."""
    ids: set[str] = set()
    for sha in commits_between(repo, base, tip):
        pid = patch_id(repo, sha)
        if pid:
            ids.add(pid)
    return ids


# ---------------------------------------------------------------------------
# Coordination-mission fixture (real repo, coord topology, materialized worktree)
# ---------------------------------------------------------------------------


@dataclass
class CoordMission:
    """A real on-disk coord-topology mission the terminus commands operate on."""

    repo: Path
    home: Path
    feature_dir: Path
    slug: str
    mission_id: str
    mid8: str
    coord_branch: str
    target_branch: str
    lane_branches: dict[str, str] = field(default_factory=dict)
    canceled_wps: set[str] = field(default_factory=set)
    _event_seq: int = 0

    # -- git conveniences -------------------------------------------------

    def rev(self, ref: str) -> str:
        return git_rev(self.repo, ref)

    def lane_branch(self, wp_id: str) -> str:
        return self.lane_branches[wp_id]

    def approved_shas_from_lane_tips(self, wp_ids: Iterable[str]) -> dict[str, list[str]]:
        """Approved commit SHAs, read from lane-branch git tips ONLY (RN-Q3).

        Never consults ``status.events.jsonl``; the claim the property/repro
        assertions compare against is the set of commits a lane tip carries
        beyond the coordination base.
        """
        out: dict[str, list[str]] = {}
        for wp_id in wp_ids:
            branch = self.lane_branches[wp_id]
            out[wp_id] = commits_between(self.repo, self.coord_branch, branch)
        return out


def _write_meta(mission: CoordMission) -> None:
    meta = {
        "mission_slug": mission.slug,
        "mission_id": mission.mission_id,
        "mid8": mission.mid8,
        "mission_number": None,
        "mission_type": _MISSION_TYPE,
        "target_branch": mission.target_branch,
        "coordination_branch": mission.coord_branch,
        "purpose_tldr": "#5001 terminus-integrity red-first harness",
        "purpose_context": "every approved WP reachable from target, nothing excluded is",
    }
    (mission.feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(mission: CoordMission, wp_ids: Sequence[str]) -> None:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json

    lanes = [
        ExecutionLane(
            lane_id=f"lane-{chr(ord('a') + idx)}",
            wp_ids=(wp_id,),
            write_scope=(f"src/pkg/{wp_id.lower()}.py",),
            predicted_surfaces=("code",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for idx, wp_id in enumerate(wp_ids)
    ]
    manifest = LanesManifest(
        version=1,
        mission_slug=mission.slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=lanes,
        computed_at=_now_iso(),
        computed_from="terminus-red-first-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)


def _write_wp_file(mission: CoordMission, wp_id: str) -> None:
    (mission.feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: {wp_id} work\nagent: implementer-ivan\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _event(mission: CoordMission, wp_id: str, from_lane: str, to_lane: str) -> dict[str, object]:
    mission._event_seq += 1
    return {
        "actor": "reviewer-renata" if to_lane == "approved" else "implementer-ivan",
        "at": _now_iso(),
        "event_id": f"01HXYZ5001{mission._event_seq:016d}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission.slug,
        "force": False,
        "from_lane": from_lane,
        "reason": None,
        "review_ref": f"review-{wp_id}" if to_lane == "approved" else None,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _approve_events(mission: CoordMission, wp_id: str) -> list[dict[str, object]]:
    return [_event(mission, wp_id, frm, to) for frm, to in _APPROVE_CHAIN]


def build_coord_mission(
    tmp_path: Path,
    *,
    wps: Sequence[str] = ("WP01",),
    target_branch: str = "main",
    mid8: str = "01M5001A",
) -> CoordMission:
    """Materialize a real coord-topology mission with every WP approved.

    Returns a :class:`CoordMission`. Each WP gets its own lane branch carrying a
    real code commit beyond the coordination base; the status log walks each WP to
    ``approved`` so the terminus commands' merge-ready precondition is satisfied
    and control reaches the terminus phase where the bug lives (not an unrelated
    early gate).

    ``mid8`` is an uppercase ULID-style disambiguator; the slug ends with it so the
    coordination branch is ``kitty/mission-<slug>`` (the production 083+ layout
    ``CoordinationWorkspace.branch_name`` reconstructs verbatim).
    """
    mid8 = mid8.upper()
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"terminus-{mid8}"
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_branch = CoordinationWorkspace.branch_name(slug, mid8)

    mission = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=coord_branch,
        target_branch=target_branch,
    )

    # -- base repo ---------------------------------------------------------
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", target_branch, str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Terminus Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")

    # -- planning artifacts + approved status log --------------------------
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    _write_manifest(mission, wps)
    events: list[dict[str, object]] = []
    for wp_id in wps:
        _write_wp_file(mission, wp_id)
        events.extend(_approve_events(mission, wp_id))
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text(
        "".join(json.dumps(ev, sort_keys=True) + "\n" for ev in events),
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"chore({slug}): bootstrap coord mission")

    # -- coordination branch at the bootstrap tip --------------------------
    _git(repo, "branch", coord_branch)

    # -- one lane branch per WP, each carrying real approved code ----------
    for idx, wp_id in enumerate(wps):
        lane_id = f"lane-{chr(ord('a') + idx)}"
        lane_branch = f"kitty/mission-{slug}-{lane_id}"
        _git(repo, "branch", lane_branch, coord_branch)
        _git(repo, "checkout", "-q", lane_branch)
        code = repo / "src" / "pkg" / f"{wp_id.lower()}.py"
        code.parent.mkdir(parents=True, exist_ok=True)
        code.write_text(f"def {wp_id.lower()}() -> int:\n    return {idx}\n", encoding="utf-8")
        _git(repo, "add", str(code))
        _git(repo, "commit", "-qm", f"feat({slug}): {wp_id} approved code")
        _git(repo, "checkout", "-q", target_branch)
        mission.lane_branches[wp_id] = lane_branch

    # -- materialize the coordination worktree (production topology) -------
    from specify_cli.coordination.workspace import CoordinationWorkspace

    CoordinationWorkspace.resolve(repo, slug, mid8)
    return mission


def plant_canceled_commit(
    mission: CoordMission,
    *,
    canceled_wp: str,
    carrier_wp: str,
) -> tuple[str, str]:
    """Plant a canceled/removed WP's commit so it rides a dependent lane's history.

    Mirrors the #4977 / #4945 mechanism: a WP whose code was CANCELED/removed still
    has a real commit that a *dependent* (carrier) lane merged in, so the removed
    diff travels into the carrier's history and — absent an excluded-commit gate —
    into the target at merge. The planted commit is NOT in ``lanes.json`` (it is
    removed work, not an approved lane), so the mission stays merge-ready and the
    "derived canceled set" the gate would compute from status is empty — exactly
    the non-vacuous case (contract postcondition 3).

    Returns ``(canceled_sha, canceled_patch_id)`` — a real target the
    excluded-commit check must fire on. Use ``--strategy merge`` so the planted
    commit stays a distinct, patch-id-identifiable node after consolidation.
    """
    repo = mission.repo
    slug = mission.slug
    cancel_branch = f"kitty/mission-{slug}-lane-canceled"

    # A real commit that must NEVER reach the target.
    _git(repo, "branch", cancel_branch, mission.coord_branch)
    _git(repo, "checkout", "-q", cancel_branch)
    canceled_code = repo / "src" / "pkg" / f"{canceled_wp.lower()}_removed.py"
    canceled_code.parent.mkdir(parents=True, exist_ok=True)
    canceled_code.write_text(
        f'# CANCELED {canceled_wp} -- must not ship\ndef {canceled_wp.lower()}_removed() -> str:\n    return "leaked"\n',
        encoding="utf-8",
    )
    _git(repo, "add", str(canceled_code))
    _git(repo, "commit", "-qm", f"feat({slug}): {canceled_wp} code (later CANCELED)")
    canceled_sha = git_rev(repo, cancel_branch)
    canceled_pid = patch_id(repo, canceled_sha)

    # Carrier lane merges the canceled commit in -> it now rides carrier history.
    carrier_branch = mission.lane_branches[carrier_wp]
    _git(repo, "checkout", "-q", carrier_branch)
    _git(repo, "merge", "-q", "--no-edit", cancel_branch)
    _git(repo, "checkout", "-q", mission.target_branch)
    _git(repo, "branch", "-qD", cancel_branch)

    mission.canceled_wps.add(canceled_wp)
    return canceled_sha, canceled_pid


# ---------------------------------------------------------------------------
# Real terminus command driver (subprocess -- nothing mocked)
# ---------------------------------------------------------------------------


def run_terminus(mission: CoordMission, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the REAL ``spec-kitty`` CLI in *mission*'s repo (no mocking).

    Runs ``python -m specify_cli <args>`` against this worktree's ``src`` with an
    isolated ``HOME`` so the whole terminus stack -- including
    ``git/ref_advance.py``'s ``update-ref`` argv -- executes for real.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC)
    env["HOME"] = str(mission.home)
    env["SPEC_KITTY_NO_UPGRADE_CHECK"] = "1"
    env.pop("VIRTUAL_ENV", None)
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=str(mission.repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def coord_mission(tmp_path: Path) -> CoordMission:
    """A single-WP, approved, merge-ready coord mission."""
    return build_coord_mission(tmp_path, wps=("WP01",))


@pytest.fixture
def terminus_env() -> dict[str, object]:
    """Expose the harness helpers to tests that prefer explicit imports-by-fixture."""
    return {
        "build_coord_mission": build_coord_mission,
        "plant_canceled_commit": plant_canceled_commit,
        "run_terminus": run_terminus,
    }
