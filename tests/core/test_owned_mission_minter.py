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

from specify_cli.core._ownership_claim_scope import owned_claim_scope

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


def test_claim_scope_restores_nested_errors_and_expires_at_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.core import checkout_ownership

    root, checkout = _owned_pair(tmp_path)

    def unavailable(*args: object, **kwargs: object) -> None:
        raise RuntimeError("fresh ownership discovery required")

    with owned_claim_scope():
        assert resolve_owned_create_root(root, checkout).checkout == checkout.resolve()
        monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", unavailable)
        with pytest.raises(RuntimeError, match="fresh ownership"), owned_claim_scope():
            resolve_owned_create_root(root, checkout)
        assert resolve_owned_create_root(root, checkout).checkout == checkout.resolve()
    with pytest.raises(RuntimeError, match="fresh ownership"):
        resolve_owned_create_root(root, checkout)


def test_cached_basic_claim_does_not_cache_write_branch_authority(tmp_path: Path) -> None:
    root, checkout = _owned_pair(tmp_path)
    with owned_claim_scope():
        resolve_owned_create_root(root, checkout)
        git(checkout, "switch", "-c", "other-branch")
        with pytest.raises(ActionContextError) as refused:
            resolve_owned_mission(root, checkout, SLUG)
        assert refused.value.code == "OWNED_BRANCH_REFUSED"


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
# #6956: the create claim refuses a registered Mission worktree
# ---------------------------------------------------------------------------


def test_create_root_refuses_a_registered_coordination_worktree(tmp_path: Path) -> None:
    r_root, p_root = _owned_pair(tmp_path)
    coord = r_root / ".worktrees" / f"{SLUG}-coord"
    git(r_root, "worktree", "add", "-qb", "codex/coord", str(coord))

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, coord)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"

    # Positive control, same fixture: the ordinary owned checkout is still admitted.
    assert resolve_owned_create_root(r_root, p_root).checkout == p_root.resolve()


def test_create_root_refuses_a_registered_lane_worktree(tmp_path: Path) -> None:
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    r_root, _p_root = _owned_pair(tmp_path)
    lane_path, lane_branch = predict_lane_worktree(r_root, SLUG, "lane-a")
    git(r_root, "worktree", "add", "-qb", lane_branch, str(lane_path))

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, lane_path)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"


def test_create_root_admits_a_worktrees_owned_checkout_that_is_not_lane_shaped(tmp_path: Path) -> None:
    """The carrier-contract trap: a registered non-coord ``.worktrees`` checkout
    classifies as LANE_WORKTREE, so the lane leg must also require the canonical
    lane-worktree directory grammar."""
    r_root, _p_root = _owned_pair(tmp_path)
    owned = r_root / ".worktrees" / "owned-under-worktrees"
    git(r_root, "worktree", "add", "-qb", "codex/owned-uw", str(owned))

    assert resolve_owned_create_root(r_root, owned).checkout == owned.resolve()


def test_create_root_refuses_when_the_worktree_registry_is_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: a claim that needs the registry fails CLOSED when it cannot be read.

    The claim must live under ``.worktrees`` for the registry to be consulted at
    all -- a checkout outside that segment classifies PRIMARY with no registry
    read, which is why the ordinary owned checkout stays admitted (below).
    """
    import specify_cli.coordination.surface_resolver as resolver

    r_root, _p_root = _owned_pair(tmp_path)
    under = r_root / ".worktrees" / "owned-under-worktrees"
    git(r_root, "worktree", "add", "-qb", "codex/owned-uw", str(under))

    def unavailable(*args: object, **kwargs: object) -> object:
        raise resolver.WorktreeRegistryUnavailable(repo_root=r_root, detail="registry unreadable")

    monkeypatch.setattr(resolver, "read_worktree_registry", unavailable)
    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, under)
    assert excinfo.value.code == resolver.WorktreeRegistryUnavailable.error_code


def test_create_root_guard_adds_one_registry_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: the guard's two legs share ONE `git worktree list` read.

    The claim is an admitted ``.worktrees``-housed, non-lane-named checkout, so
    BOTH legs evaluate (a coordination claim would raise on the first leg and
    hide a per-leg re-read). Scope note: ``checkout_ownership.resolve_ownership_claim``
    spends its own registry read through its own module-level import, which this
    patch does not touch -- it is not this guard's budget.
    """
    import specify_cli.coordination.surface_resolver as resolver

    r_root, _p_root = _owned_pair(tmp_path)
    owned = r_root / ".worktrees" / "owned-under-worktrees"
    git(r_root, "worktree", "add", "-qb", "codex/owned-uw", str(owned))

    calls: list[int] = []
    original = resolver.read_worktree_registry

    def counting(*args: object, **kwargs: object) -> frozenset[Path]:
        calls.append(1)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(resolver, "read_worktree_registry", counting)
    assert resolve_owned_create_root(r_root, owned).checkout == owned.resolve()
    assert len(calls) == 1, f"the guard must classify once for both legs, saw {len(calls)} reads"


def test_create_root_reserves_the_lane_worktree_directory_name(tmp_path: Path) -> None:
    """A name in the lane-worktree grammar is refused even without a Mission (a create-seam policy).

    ``<slug>-lane-<id>`` is the allocator's directory grammar. At create time no
    Mission is bound, so shape is the only signal this seam has; it refuses
    rather than guessing whether a Mission backs the name, and the refusal
    message names the reserved lane-worktree shape and tells the operator to
    rename or relocate the checkout. This is this seam's policy, not a
    reservation some other component already guarantees.
    """
    r_root, _p_root = _owned_pair(tmp_path)
    reserved = r_root / ".worktrees" / "customer-lane-a"
    git(r_root, "worktree", "add", "-qb", "codex/customer", str(reserved))

    with pytest.raises(ActionContextError) as excinfo:
        resolve_owned_create_root(r_root, reserved)
    assert excinfo.value.code == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"
    assert "reserved lane-worktree shape" in str(excinfo.value)
    # Positive control: MOVE the very same checkout out of the reserved name, so
    # the only variable left is the directory name the guard reads.
    renamed = r_root / ".worktrees" / "customer-owned"
    git(r_root, "worktree", "move", str(reserved), str(renamed))
    assert resolve_owned_create_root(r_root, renamed).checkout == renamed.resolve()


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
