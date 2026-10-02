"""#2453 — ``BookkeepingTransaction`` write-side routing, characterization-first.

Characterization gate (WP06 T029a) for ``_is_legacy_mission`` +
``_resolve_legacy_lane_destination`` / ``_acquire_locked``'s routing decision,
written BEFORE the #2453 fix and kept as the permanent regression pin
afterwards. Pins the THREE topology shapes that can reach
``BookkeepingTransaction.acquire()``'s legacy branch (``_is_legacy_mission`` is
``True`` for both of the first two — it only keys on ``coordination_branch``
absence):

(a) **genuinely-legacy** — ``meta.json`` has NO stored ``topology`` (pre-SSOT
    mission). Routing MUST stay cwd-derived (``_resolve_legacy_lane_destination``
    walks up from ``Path.cwd()`` to the nearest ``.git`` worktree) — there is no
    other reliable write target for a mission that predates the
    coordination-branch topology. This is a permanent invariant, unchanged by
    the #2453 fix.

(b) **modern coordination-less** — ``meta.json`` carries a stored
    ``topology: single_branch``/``lanes`` (or ``flattened: true``), but still
    no ``coordination_branch``. BEFORE the #2453 fix this was misrouted through
    the same cwd-derivation as (a) — the #2647 taint (a lane worktree forked
    before later status events land on the primary reads a stale local
    snapshot). AFTER the fix it routes to the canonical mission surface:
    ``repo_root`` on the caller-supplied (already CWD-invariant, per
    ``status_transition._resolve_write_target``) ``destination_ref`` —
    regardless of the operator's cwd.

(c) **coordination topology** — ``meta.json`` carries a real
    ``coordination_branch``. ``_is_legacy_mission`` is ``False`` and the whole
    legacy branch (and this WP's fix) is never entered; routing is the
    pre-existing ``CoordinationWorkspace.resolve(...)`` coord-worktree path,
    unaffected by this change.

Fixture pattern mirrors the production-shaped real-git-repo + real-worktree
recipe this mission's sibling ``test_tasks_move_task_cwd.py`` and
``tests/integration/test_legacy_mission_fallback.py`` already use — no
monkey-patched ``Path.cwd()`` shims, a genuine ``git worktree add`` gitdir
pointer.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination.transaction import (
    BookkeepingTransaction,
    _is_legacy_mission,
    _resolve_legacy_lane_destination,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@example.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "seed")


def _make_mission(
    repo_root: Path,
    *,
    mission_slug: str,
    mission_id: str,
    topology: str | None = None,
    flattened: bool = False,
    coordination_branch: str | None = None,
) -> dict[str, Any]:
    """Build a real, on-disk mission with the given coordination-less shape.

    Mirrors ``tests/integration/test_legacy_mission_fallback.py``'s
    ``_make_legacy_mission`` recipe: a committed ``meta.json`` + a lane branch
    forked off ``main`` with a REAL linked worktree (a genuine gitdir-pointer
    file, not a fabricated marker).
    """
    mid8 = mission_id[:8]
    feature_dir = repo_root / "kitty-specs" / f"{mission_slug}-{mid8}"
    feature_dir.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "mid8": mid8,
        "mission_type": "research",  # sidesteps the software-dev currency guard
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "friendly_name": "T029a routing characterization mission",
    }
    if topology is not None:
        meta["topology"] = topology
    if flattened:
        meta["flattened"] = True
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo_root, "add", "kitty-specs")
    _git(repo_root, "commit", "-q", "-m", f"seed {mission_slug} mission scaffold")

    lane_branch = f"kitty/mission-{mission_slug}-{mid8}-lane-a"
    _git(repo_root, "branch", lane_branch, "main")
    lane_worktree = repo_root / ".worktrees" / f"{mission_slug}-{mid8}-lane-a"
    lane_worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "worktree", "add", str(lane_worktree), lane_branch)
    assert (lane_worktree / ".git").is_file(), (
        "git worktree add must produce a real gitdir-pointer file"
    )

    return {
        "feature_dir": feature_dir,
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "lane_branch": lane_branch,
        "lane_worktree": lane_worktree,
    }


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    _init_repo(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# (a) genuinely-legacy — cwd-derived routing, PERMANENT invariant.
# ---------------------------------------------------------------------------


def test_genuinely_legacy_is_legacy_mission_true(repo_root: Path) -> None:
    mission = _make_mission(
        repo_root,
        mission_slug="routing-genuine-legacy",
        mission_id="01KROUTEA1ZZZZZZZZZZZZZZZZ",
    )
    assert _is_legacy_mission(repo_root, mission["mission_slug"], mission["mid8"]) is True


def test_genuinely_legacy_resolve_legacy_lane_destination_is_cwd_derived(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_resolve_legacy_lane_destination`` itself stays a pure cwd walk.

    Unchanged by the #2453 fix — the fix only changes WHICH classification
    reaches this function, never its own behavior.
    """
    mission = _make_mission(
        repo_root,
        mission_slug="routing-genuine-legacy-2",
        mission_id="01KROUTEA2ZZZZZZZZZZZZZZZZ",
    )
    monkeypatch.chdir(mission["lane_worktree"])
    worktree_root, branch = _resolve_legacy_lane_destination(repo_root)
    assert worktree_root == mission["lane_worktree"]
    assert branch == mission["lane_branch"]


def test_genuinely_legacy_acquire_routes_to_lane_worktree(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: ``.acquire()`` still resolves to the operator's lane cwd.

    A permanent regression guard (both BEFORE and AFTER the #2453 fix) — a
    genuinely-legacy (pre-SSOT, no stored topology) mission has no other
    reliable write target.
    """
    mission = _make_mission(
        repo_root,
        mission_slug="routing-genuine-legacy-3",
        mission_id="01KROUTEA3ZZZZZZZZZZZZZZZZ",
    )
    monkeypatch.chdir(mission["lane_worktree"])
    with BookkeepingTransaction.acquire(
        repo_root=repo_root,
        mission_id=mission["mission_id"],
        mission_slug=mission["mission_slug"],
        mid8=mission["mid8"],
        # Caller-supplied ref is IGNORED for genuine-legacy — overridden by
        # the actual lane HEAD. A dummy value pins that discarding.
        destination_ref="kitty/x",
        operation="t029a-genuine-legacy",
    ) as txn:
        assert txn.worktree_root == mission["lane_worktree"]
        assert txn.destination_ref == mission["lane_branch"]
        assert txn._legacy_mode is True


# ---------------------------------------------------------------------------
# (b) modern coordination-less — routes to repo_root + the caller-supplied
# (already CWD-invariant) destination_ref. THE #2453/#2647 FIX.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("topology", "flattened"),
    [
        pytest.param("single_branch", False, id="single_branch"),
        pytest.param("lanes", False, id="lanes"),
        pytest.param(None, True, id="flattened"),
    ],
)
def test_modern_coordinationless_is_legacy_mission_true(
    repo_root: Path, topology: str | None, flattened: bool
) -> None:
    """``_is_legacy_mission`` alone does NOT distinguish (a) from (b) — by
    design (C-005): it keys ONLY on ``coordination_branch`` absence. The
    routing split lives in ``_acquire_locked``, not this predicate.
    """
    mission = _make_mission(
        repo_root,
        mission_slug=f"routing-modern-{topology or 'flat'}",
        mission_id="01KROUTEB1ZZZZZZZZZZZZZZZZ",
        topology=topology,
        flattened=flattened,
    )
    assert _is_legacy_mission(repo_root, mission["mission_slug"], mission["mid8"]) is True


@pytest.mark.parametrize(
    ("topology", "flattened"),
    [
        pytest.param("single_branch", False, id="single_branch"),
        pytest.param("lanes", False, id="lanes"),
        pytest.param(None, True, id="flattened"),
    ],
)
def test_modern_coordinationless_acquire_routes_to_repo_root_not_cwd(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, topology: str | None, flattened: bool
) -> None:
    """THE FIX: routing no longer follows ``Path.cwd()`` for a mission whose
    coordination-less shape was CHOSEN (stored topology) or is ``flattened``.

    Before #2453 this asserted ``txn.worktree_root == mission["lane_worktree"]``
    (the bug) — the operator's stale lane cwd. After the fix it must resolve to
    the canonical mission surface (``repo_root``) regardless of cwd, on the
    caller-supplied ``destination_ref`` (unchanged — the caller already
    resolves it CWD-invariantly, mirroring
    ``status_transition._resolve_write_target``'s flat-topology arm).
    """
    mission = _make_mission(
        repo_root,
        mission_slug=f"routing-modernacq-{topology or 'flat'}",
        mission_id="01KROUTEB2ZZZZZZZZZZZZZZZZ",
        topology=topology,
        flattened=flattened,
    )
    # A real, existing, non-protected target branch — the shape a canonical
    # caller (e.g. status_transition._resolve_write_target's flat arm) would
    # already have resolved before calling .acquire().
    target_branch = "mission/t029a-target"
    _git(repo_root, "branch", target_branch, "main")

    # The operator's shell sits in the STALE lane worktree — genuinely
    # tripping is_worktree_context, exactly the #2647 repro shape.
    monkeypatch.chdir(mission["lane_worktree"])

    with BookkeepingTransaction.acquire(
        repo_root=repo_root,
        mission_id=mission["mission_id"],
        mission_slug=mission["mission_slug"],
        mid8=mission["mid8"],
        destination_ref=target_branch,
        operation="t029a-modern-coordinationless",
    ) as txn:
        assert txn.worktree_root == repo_root, (
            "modern coordination-less routing must land on repo_root, not the "
            f"operator's cwd lane worktree {mission['lane_worktree']}"
        )
        assert txn.destination_ref == target_branch, (
            "the caller-supplied destination_ref must NOT be overridden by a "
            "cwd-derived branch for a modern coordination-less mission"
        )
        # Still classified _is_legacy_mission=True (coordination_branch is
        # absent) -- only the ROUTING differs from the genuine-legacy arm.
        assert txn._legacy_mode is True


# ---------------------------------------------------------------------------
# (c) coordination topology — unaffected; never enters the legacy branch.
# ---------------------------------------------------------------------------


def test_coordination_topology_is_legacy_mission_false(repo_root: Path) -> None:
    mission_slug = "routing-coord"
    mid8 = "01KROUTEC"
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    _make_mission(
        repo_root,
        mission_slug=mission_slug,
        mission_id=f"{mid8}ZZZZZZZZZZZZZZZZZ",
        coordination_branch=coord_branch,
    )
    assert _is_legacy_mission(repo_root, mission_slug, mid8) is False


def test_coordination_topology_acquire_routes_to_coord_worktree(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coord-topology routing is untouched by the #2453 fix.

    ``_is_legacy_mission`` is ``False``, so ``_acquire_locked`` never enters
    the (genuine-legacy / modern-coordination-less) split at all — it resolves
    via the pre-existing ``CoordinationWorkspace.resolve(...)`` path.
    """
    mission_slug = "routing-coord-acquire"
    # Exactly 8 chars (the mid8 contract) -- must equal mission_id[:8], which
    # is also what ``_make_mission``/``resolve_declared_mid8`` derive from
    # meta.json (WP07: the coordination arm now resolves its write location
    # through meta.json's declared identity rather than trusting a
    # caller-supplied mid8 verbatim, so a mismatched longer literal here
    # would silently diverge from the worktree the fixture's own meta.json
    # declares).
    mid8 = "01KROUTE"
    mission_id = f"{mid8}ZZZZZZZZZZZZZZZZZ"
    coord_branch = f"kitty/mission-{mission_slug}-{mid8}"
    mission = _make_mission(
        repo_root,
        mission_slug=mission_slug,
        mission_id=mission_id,
        coordination_branch=coord_branch,
    )
    # A real branch for CoordinationWorkspace.resolve() to attach its worktree
    # to (mirrors tests/specify_cli/cli/commands/agent/test_issue_1602.py's
    # coord-branch recipe).
    _git(repo_root, "branch", coord_branch)

    # Operator cwd sits in the mission's OWN lane worktree -- must have no
    # bearing on coord routing.
    monkeypatch.chdir(mission["lane_worktree"])

    expected_coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8)
    with BookkeepingTransaction.acquire(
        repo_root=repo_root,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mid8=mid8,
        destination_ref=coord_branch,
        operation="t029a-coordination-topology",
    ) as txn:
        assert txn.worktree_root == expected_coord_worktree
        assert txn.worktree_root != mission["lane_worktree"]
        assert txn.worktree_root != repo_root
        assert txn._legacy_mode is False
