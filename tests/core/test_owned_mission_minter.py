"""Unit tests for ``specify_cli.core.owned_mission`` (WP02, sole ownership minter).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, work package WP02.
Real temporary git repositories / worktrees (``tmp_path`` + real ``git``
subprocess calls), mirroring the house pattern in
``tests/integration/test_explicit_checkout_commands.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, MissionTopology, OwnedCheckout
from specify_cli.core.owned_mission import (
    LIFECYCLE_OWNED_TOPOLOGIES,
    NEXT_OWNED_TOPOLOGIES,
    OwnedCreateRoot,
    resolve_owned_create_root,
    resolve_owned_mission,
)

pytestmark = [pytest.mark.git_repo]

SLUG = "owned-minter-01M2A900"
MID = "01M2A900000000000000000001"
TARGET = "codex/owned"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _write_meta(mission_dir: Path, *, topology: str, coordination_branch: str | None = None, branch: str = TARGET) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mission_id": MID,
        "mission_slug": SLUG,
        "slug": SLUG,
        "mission_type": "software-dev",
        "topology": topology,
        "target_branch": branch,
        "flattened": False,
    }
    if coordination_branch is not None:
        payload["coordination_branch"] = coordination_branch
    (mission_dir / "meta.json").write_text(json.dumps(payload), encoding="utf-8")


def _owned_pair(
    tmp_path: Path,
    *,
    topology: str = "single_branch",
    coordination_branch: str | None = None,
    slug: str = SLUG,
    branch: str = TARGET,
) -> tuple[Path, Path]:
    """Build a primary R and a linked owned checkout P with one mission committed in P."""
    r_root = tmp_path / "primary"
    r_root.mkdir()
    git(r_root, "init", "-q", "-b", "main")
    git(r_root, "config", "user.name", "Test")
    git(r_root, "config", "user.email", "test@example.invalid")
    git(r_root, "config", "commit.gpgsign", "false")
    (r_root / "README.md").write_text("seed\n", encoding="utf-8")
    git(r_root, "add", ".")
    git(r_root, "commit", "-qm", "seed")

    p_root = tmp_path / "owned"
    git(r_root, "worktree", "add", "-qb", branch, str(p_root))
    mission_dir = p_root / "kitty-specs" / slug
    _write_meta(mission_dir, topology=topology, coordination_branch=coordination_branch)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")
    return r_root, p_root


def test_returns_validated_fact(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    fact = resolve_owned_mission(r_root, p_root, SLUG)
    assert isinstance(fact, OwnedCheckout)
    assert fact.topology is MissionTopology.SINGLE_BRANCH
    assert fact.owned_root == p_root.resolve()
    assert fact.mission_dir == p_root.resolve() / "kitty-specs" / SLUG


@pytest.mark.parametrize("handle_kind", ["slug", "mid8", "mission_id"])
def test_returns_validated_fact_for_every_handle_kind(tmp_path: Path, handle_kind: str) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    handle = {"slug": SLUG, "mid8": MID[:8], "mission_id": MID}[handle_kind]
    fact = resolve_owned_mission(r_root, p_root, handle)
    assert isinstance(fact, OwnedCheckout)
    assert fact.mission_slug == SLUG


def test_next_topologies_accept_lanes_with_coord(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path, topology="lanes_with_coord", coordination_branch=f"{TARGET}-coord")
    fact = resolve_owned_mission(r_root, p_root, SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    assert fact.topology is MissionTopology.LANES_WITH_COORD


def test_lifecycle_default_refuses_lanes_with_coord(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path, topology="lanes_with_coord", coordination_branch=f"{TARGET}-coord")
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG)
    assert excinfo.value.code == "OWNED_TOPOLOGY_UNSUPPORTED"


def test_next_topologies_accept_lanes(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path, topology="lanes")
    fact = resolve_owned_mission(r_root, p_root, SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    assert fact.topology is MissionTopology.LANES


def test_lifecycle_default_refuses_lanes(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path, topology="lanes")
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG)
    assert excinfo.value.code == "OWNED_TOPOLOGY_UNSUPPORTED"


def test_mismatched_branch_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    git(p_root, "checkout", "-qb", "codex/other")
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG)
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


def test_detached_head_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    head = git(p_root, "rev-parse", "HEAD")
    git(p_root, "checkout", "-q", head)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG)
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


def test_target_override_mismatch_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG, target_override="codex/other")
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


def test_protected_target_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    (p_root / ".kittify").mkdir(exist_ok=True)
    (p_root / ".kittify" / "config.yaml").write_text(f"protection:\n  protected_branches: [{TARGET}]\n", encoding="utf-8")
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, p_root, SLUG)
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


# ---------------------------------------------------------------------------
# T007: OWNED_CHECKOUT_IS_REPOSITORY_ROOT and the U2 pins
# ---------------------------------------------------------------------------


def test_repository_root_is_refused(tmp_path: Path) -> None:
    r_root = tmp_path / "primary"
    r_root.mkdir()
    git(r_root, "init", "-q", "-b", TARGET)
    git(r_root, "config", "user.name", "Test")
    git(r_root, "config", "user.email", "test@example.invalid")
    git(r_root, "config", "commit.gpgsign", "false")
    mission_dir = r_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, topology="single_branch")
    git(r_root, "add", ".")
    git(r_root, "commit", "-qm", "seed")

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, r_root, SLUG)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"

    # Control: a valid linked P is still accepted on the same fixture shape.
    p_root = tmp_path / "owned"
    git(r_root, "worktree", "add", "-qb", "codex/owned-p", str(p_root))
    mission_dir_p = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir_p, topology="single_branch", branch="codex/owned-p")
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")
    fact = resolve_owned_mission(r_root, p_root, SLUG)
    assert isinstance(fact, OwnedCheckout)


def test_repository_root_via_symlink_is_refused(tmp_path: Path) -> None:
    """T007 edge case: a symlink to R must still refuse (paths are resolved)."""
    r_root, _p_root = _owned_pair(tmp_path)
    link = tmp_path / "link-to-primary"
    link.symlink_to(r_root, target_is_directory=True)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, link, SLUG)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"


def test_missing_path_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, tmp_path / "does-not-exist", SLUG)
    assert excinfo.value.code == "OWNERSHIP_BROKEN_POINTER"


def test_non_worktree_directory_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    (r_root / "docs").mkdir()
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, r_root / "docs", SLUG)
    assert excinfo.value.code == "OWNERSHIP_NESTED"


def test_directory_outside_any_repository_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    plain_dir = tmp_path / "plain-dir"
    plain_dir.mkdir()
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, plain_dir, SLUG)
    assert excinfo.value.code == "OWNERSHIP_BROKEN_POINTER"


# ---------------------------------------------------------------------------
# T008: resolve_owned_create_root
# ---------------------------------------------------------------------------


def test_resolve_owned_create_root_returns_typed_value(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    result = resolve_owned_create_root(r_root, p_root)
    assert isinstance(result, OwnedCreateRoot)
    assert result.repository_root == r_root.resolve()
    assert result.checkout == p_root.resolve()


def test_resolve_owned_create_root_refuses_repository_root(tmp_path: Path) -> None:
    r_root, _p_root = _owned_pair(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, r_root)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"


def test_resolve_owned_create_root_refuses_nested(tmp_path: Path) -> None:
    r_root, _p_root = _owned_pair(tmp_path)
    (r_root / "docs").mkdir()
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, r_root / "docs")
    assert excinfo.value.code == "OWNERSHIP_NESTED"


def test_resolve_owned_create_root_refuses_broken_pointer(tmp_path: Path) -> None:
    r_root, _p_root = _owned_pair(tmp_path)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, tmp_path / "does-not-exist")
    assert excinfo.value.code == "OWNERSHIP_BROKEN_POINTER"


def test_resolve_owned_create_root_refuses_foreign(tmp_path: Path) -> None:
    r_root, _p_root = _owned_pair(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    git(foreign, "init", "-q", "-b", "main")
    git(foreign, "config", "user.name", "Test")
    git(foreign, "config", "user.email", "test@example.invalid")
    git(foreign, "config", "commit.gpgsign", "false")
    (foreign / "seed.txt").write_text("x\n", encoding="utf-8")
    git(foreign, "add", ".")
    git(foreign, "commit", "-qm", "foreign seed")
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, foreign)
    assert excinfo.value.code == "OWNERSHIP_FOREIGN"


def test_resolve_owned_create_root_resolves_symlinked_checkout(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    link = tmp_path / "link-to-owned"
    link.symlink_to(p_root, target_is_directory=True)
    result = resolve_owned_create_root(r_root, link)
    assert result.checkout == p_root.resolve()
    assert result.repository_root == r_root.resolve()


def test_owned_create_root_is_frozen(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    result = resolve_owned_create_root(r_root, p_root)
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        result.checkout = p_root  # type: ignore[misc]


def test_owned_create_root_direct_construction_refused(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        OwnedCreateRoot(repository_root=tmp_path, checkout=tmp_path)


def test_resolve_owned_create_root_one_claim_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    calls = []
    import specify_cli.core.checkout_ownership as checkout_ownership_mod

    original = checkout_ownership_mod.resolve_ownership_claim

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(checkout_ownership_mod, "resolve_ownership_claim", counting)
    resolve_owned_create_root(r_root, p_root)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# T009 step 3a: OWNED_CHECKOUT_IS_MISSION_WORKTREE (explicit path)
# ---------------------------------------------------------------------------


def test_lane_worktree_of_mission_is_refused(tmp_path: Path) -> None:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    r_root, p_root = _owned_pair(tmp_path)
    # The lane-worktree check needs the mission's lanes.json to be resolvable
    # from the repository root -- realistic for a lanes/coord-carrying primary
    # checkout (the same shape ``stale_root_copy`` builds in T011).
    mission_dir = r_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, topology="single_branch")
    manifest = LanesManifest(
        version=1,
        mission_slug=SLUG,
        mission_id=MID,
        mission_branch=f"kitty/mission-{SLUG}",
        target_branch=TARGET,
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(mission_dir, manifest)
    git(r_root, "add", ".")
    git(r_root, "commit", "-qm", "lanes")

    lane_path, lane_branch = predict_lane_worktree(r_root, SLUG, "lane-a")
    git(r_root, "worktree", "add", "-qb", lane_branch, str(lane_path))

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, lane_path, SLUG)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"

    # Control: the valid P under R/.worktrees/ is still accepted (the
    # LANE_WORKTREE-classification trap, not a lane in lanes.json).
    p_under_worktrees = r_root / ".worktrees" / "owned-under-worktrees"
    git(r_root, "worktree", "add", "-qb", "codex/owned-uw", str(p_under_worktrees))
    mission_dir_uw = p_under_worktrees / "kitty-specs" / SLUG
    _write_meta(mission_dir_uw, topology="single_branch", branch="codex/owned-uw")
    git(p_under_worktrees, "add", ".")
    git(p_under_worktrees, "commit", "-qm", "owned mission")
    fact = resolve_owned_mission(r_root, p_under_worktrees, SLUG)
    assert isinstance(fact, OwnedCheckout)


def test_coordination_worktree_is_refused(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    coord_path = r_root / ".worktrees" / f"{SLUG}-coord"
    git(r_root, "worktree", "add", "-qb", "codex/coord", str(coord_path))
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_mission(r_root, coord_path, SLUG)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"


def test_lifecycle_owned_topologies_is_single_branch_only() -> None:
    assert frozenset({MissionTopology.SINGLE_BRANCH}) == LIFECYCLE_OWNED_TOPOLOGIES


def test_next_owned_topologies_covers_all_owned_shapes() -> None:
    assert (
        frozenset(
            {
                MissionTopology.SINGLE_BRANCH,
                MissionTopology.LANES,
                MissionTopology.LANES_WITH_COORD,
                MissionTopology.COORD,
            }
        )
        == NEXT_OWNED_TOPOLOGIES
    )
