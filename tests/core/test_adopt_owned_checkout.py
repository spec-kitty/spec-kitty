"""Unit tests for :func:`specify_cli.core.owned_mission.adopt_owned_checkout` (WP02, FR-021).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, work package WP02.
Flagless adoption validates only what :func:`resolve_owned_mission` accepts;
these tests assert the returned value AND the number of
``resolve_ownership_claim`` calls (NFR-002).

The pre-existing-entry-point red for the CLI-level O10 replacement lives in
WP08's acceptance test through ``agent context resolve``; this module covers
the new function directly (``ImportError`` red on the new name, before it
existed).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import ActionContextError, OwnedCheckout
from specify_cli.core.owned_mission import (
    LIFECYCLE_OWNED_TOPOLOGIES,
    adopt_owned_checkout,
    _branch_matches_target,
    _target_branch_from_meta_file,
    invoking_checkout_would_adopt,
)

pytestmark = [pytest.mark.git_repo]

SLUG = "owned-adopt-01M2B900"
OTHER_SLUG = "owned-adopt-other-01M2C900"
MID = "01M2B900000000000000000001"
OTHER_MID = "01M2C900000000000000000001"
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


def _write_meta(mission_dir: Path, *, slug: str, mission_id: str, branch: str) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": branch,
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def counting_claims(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    import specify_cli.core.checkout_ownership as checkout_ownership_mod

    calls: list[int] = []
    original = checkout_ownership_mod.resolve_ownership_claim

    def counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership_mod, "resolve_ownership_claim", counting)
    return calls


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r_root = tmp_path / "primary"
    r_root.mkdir()
    git(r_root, "init", "-q", "-b", "main")
    git(r_root, "config", "user.name", "Test")
    git(r_root, "config", "user.email", "test@example.invalid")
    git(r_root, "config", "commit.gpgsign", "false")
    (r_root / "README.md").write_text("seed\n", encoding="utf-8")
    git(r_root, "add", ".")
    git(r_root, "commit", "-qm", "seed")
    return r_root


def _linked_worktree(r_root: Path, name: str, branch: str) -> Path:
    path = r_root.parent / name
    git(r_root, "worktree", "add", "-qb", branch, str(path))
    return path


def test_cwd_is_repository_root_returns_none_with_zero_claims(repo: Path, counting_claims: list[int]) -> None:
    result = adopt_owned_checkout(repo, repo, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 0


def test_cwd_under_valid_owned_checkout_returns_fact_with_one_claim(repo: Path, counting_claims: list[int]) -> None:
    p_root = _linked_worktree(repo, "owned", TARGET)
    mission_dir = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch=TARGET)
    (mission_dir / "sub").mkdir()
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")
    cwd = mission_dir / "sub"

    result = adopt_owned_checkout(repo, cwd, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert isinstance(result, OwnedCheckout)
    assert result.owned_root == p_root.resolve()
    assert len(counting_claims) == 1


def test_owned_checkout_under_worktrees_is_adopted(repo: Path, counting_claims: list[int]) -> None:
    p_root = repo / ".worktrees" / "owned-a"
    git(repo, "worktree", "add", "-qb", TARGET, str(p_root))
    mission_dir = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")

    result = adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert isinstance(result, OwnedCheckout)
    assert result.owned_root == p_root.resolve()
    assert len(counting_claims) == 1


def test_registered_coordination_worktree_returns_none_with_zero_claims(repo: Path, counting_claims: list[int]) -> None:
    coord_path = repo / ".worktrees" / f"{SLUG}-coord"
    git(repo, "worktree", "add", "-qb", "codex/coord", str(coord_path))
    mission_dir = coord_path / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch="codex/coord")
    git(coord_path, "add", ".")
    git(coord_path, "commit", "-qm", "coord mission")

    result = adopt_owned_checkout(repo, coord_path, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 0


def test_unreadable_registry_fails_closed_before_any_claim(repo: Path, counting_claims: list[int], monkeypatch: pytest.MonkeyPatch) -> None:
    """review cycle 1: an unreadable worktree registry must refuse, not fall through.

    ``classify_worktree_topology`` is forced to raise
    ``WorktreeRegistryUnavailable`` for every call. Before the fail-closed
    fix, ``_is_coordination_worktree`` swallowed that into ``False`` ("not
    coordination"), which let adoption fall through toward
    ``resolve_owned_mission`` and incur a claim call. The fixed predicate
    lets the exception propagate, and ``adopt_owned_checkout`` returns
    ``None`` at the coordination check itself -- before ``resolve_mission``
    or the claim primitive ever run (0 claims is the non-vacuous half of
    this assertion: it fails under the old swallow-to-False behaviour, which
    proceeds to a claim call).
    """
    from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable

    p_root = _linked_worktree(repo, "owned", TARGET)
    mission_dir = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")

    def _raise(*_a: object, **_k: object) -> object:
        raise WorktreeRegistryUnavailable(repo_root=repo, detail="forced for test")

    monkeypatch.setattr("specify_cli.coordination.surface_resolver.classify_worktree_topology", _raise)

    result = adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 0


def test_lane_worktree_named_in_lanes_json_returns_none(repo: Path, counting_claims: list[int]) -> None:
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    mission_dir = repo / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch=TARGET)
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
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "lanes")

    lane_path, lane_branch = predict_lane_worktree(repo, SLUG, "lane-a")
    git(repo, "worktree", "add", "-qb", lane_branch, str(lane_path))
    _write_meta(lane_path / "kitty-specs" / SLUG, slug=SLUG, mission_id=MID, branch=lane_branch)
    git(lane_path, "add", ".")
    git(lane_path, "commit", "-qm", "lane copy")

    result = adopt_owned_checkout(repo, lane_path, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 0


def test_mismatched_branch_returns_none(repo: Path, counting_claims: list[int]) -> None:
    p_root = _linked_worktree(repo, "owned", "codex/other")
    mission_dir = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")

    result = adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 1


def test_foreign_repository_returns_none(repo: Path, tmp_path: Path, counting_claims: list[int]) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    git(foreign, "init", "-q", "-b", "main")
    git(foreign, "config", "user.name", "Test")
    git(foreign, "config", "user.email", "test@example.invalid")
    git(foreign, "config", "commit.gpgsign", "false")
    mission_dir = foreign / "kitty-specs" / SLUG
    _write_meta(mission_dir, slug=SLUG, mission_id=MID, branch="main")
    git(foreign, "add", ".")
    git(foreign, "commit", "-qm", "foreign seed")

    result = adopt_owned_checkout(repo, foreign, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 1


def test_mission_surface_conflict_raises_typed_error(repo: Path, counting_claims: list[int]) -> None:
    mission_dir_r = repo / "kitty-specs" / SLUG
    _write_meta(mission_dir_r, slug=SLUG, mission_id=MID, branch="main")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "R mission")

    p_root = _linked_worktree(repo, "owned", TARGET)
    mission_dir_p = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir_p, slug=SLUG, mission_id=OTHER_MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "P mission (different id, same slug)")

    with pytest.raises(ActionContextError) as excinfo:
        adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert excinfo.value.code == "MISSION_CONTEXT_CONFLICT"
    # The conflict is raised before the minter runs (T009 step 6): no claim call.
    assert len(counting_claims) == 0


def test_same_handle_same_id_stale_copy_returns_fact_for_p(repo: Path, counting_claims: list[int]) -> None:
    mission_dir_r = repo / "kitty-specs" / SLUG
    _write_meta(mission_dir_r, slug=SLUG, mission_id=MID, branch="main")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "R mission (stale copy)")

    p_root = _linked_worktree(repo, "owned", TARGET)
    mission_dir_p = p_root / "kitty-specs" / SLUG
    _write_meta(mission_dir_p, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "P mission (same id)")

    result = adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert isinstance(result, OwnedCheckout)
    assert result.owned_root == p_root.resolve()
    assert len(counting_claims) == 1


def test_empty_handle_returns_none(repo: Path, counting_claims: list[int]) -> None:
    result = adopt_owned_checkout(repo, repo, "", allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert result is None
    assert len(counting_claims) == 0


# --- invoking_checkout_would_adopt (WP09 review cycle 3, declared out-of-map) ---


def test_would_adopt_true_for_owned_checkout(repo: Path) -> None:
    p_root = _linked_worktree(repo, "owned", TARGET)
    _write_meta(p_root / "kitty-specs" / SLUG, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")
    assert invoking_checkout_would_adopt(repo, p_root) is True


def test_would_adopt_false_for_repository_root(repo: Path) -> None:
    assert invoking_checkout_would_adopt(repo, repo) is False


def test_would_adopt_false_when_checkout_has_no_specs_dir(repo: Path) -> None:
    other = _linked_worktree(repo, "plain", "plain-branch")
    assert invoking_checkout_would_adopt(repo, other) is False


def test_would_adopt_false_for_plain_linked_checkout_holding_rs_mission(repo: Path) -> None:
    _write_meta(repo / "kitty-specs" / SLUG, slug=SLUG, mission_id=MID, branch="main")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "r mission")
    hotfix = _linked_worktree(repo, "hotfix", "hotfix-branch")
    assert invoking_checkout_would_adopt(repo, hotfix) is False


def test_would_adopt_true_on_mission_surface_conflict(repo: Path) -> None:
    """Same selector, different identity in R and P: adoption raises, the checkout still claims a mission."""
    _write_meta(repo / "kitty-specs" / SLUG, slug=SLUG, mission_id=OTHER_MID, branch="main")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "r mission")
    p_root = _linked_worktree(repo, "owned", TARGET)
    _write_meta(p_root / "kitty-specs" / SLUG, slug=SLUG, mission_id=MID, branch=TARGET)
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "owned mission")
    with pytest.raises(ActionContextError):
        adopt_owned_checkout(repo, p_root, SLUG, allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    assert invoking_checkout_would_adopt(repo, p_root) is True


# --- review cycle 4: bounded pre-filter + shared branch rule ---


@pytest.mark.parametrize(
    ("current", "target", "override", "expected"),
    [
        ("codex/owned", "codex/owned", None, True),
        ("codex/owned", "codex/owned", "codex/owned", True),
        ("codex/owned", "codex/owned", "other", False),
        ("other", "codex/owned", None, False),
        (None, "codex/owned", None, False),
        ("codex/owned", "", None, False),
    ],
)
def test_branch_matches_target_rule(current: str | None, target: str, override: str | None, expected: bool) -> None:
    assert _branch_matches_target(current, target, override) is expected


def test_target_branch_from_meta_file_is_tolerant(tmp_path: Path) -> None:
    assert _target_branch_from_meta_file(tmp_path) == ""
    (tmp_path / "meta.json").write_text("not json", encoding="utf-8")
    assert _target_branch_from_meta_file(tmp_path) == ""
    (tmp_path / "meta.json").write_text("[1]", encoding="utf-8")
    assert _target_branch_from_meta_file(tmp_path) == ""
    (tmp_path / "meta.json").write_text(json.dumps({"target_branch": "codex/owned"}), encoding="utf-8")
    assert _target_branch_from_meta_file(tmp_path) == "codex/owned"


def test_would_adopt_prefilter_resolves_no_claims_when_no_mission_targets_the_branch(repo: Path, counting_claims: list[int]) -> None:
    p_root = _linked_worktree(repo, "plain", "plain-branch")
    for index in range(20):
        _write_meta(p_root / "kitty-specs" / f"m-{index}", slug=f"m-{index}", mission_id=f"01M2B9{index:020d}", branch="main")
    assert invoking_checkout_would_adopt(repo, p_root) is False
    assert counting_claims == []


def test_would_adopt_adopts_only_the_branch_matching_survivor(repo: Path, counting_claims: list[int]) -> None:
    p_root = _linked_worktree(repo, "owned", TARGET)
    _write_meta(p_root / "kitty-specs" / SLUG, slug=SLUG, mission_id=MID, branch=TARGET)
    for index in range(20):
        _write_meta(p_root / "kitty-specs" / f"m-{index}", slug=f"m-{index}", mission_id=f"01M2B9{index:020d}", branch="main")
    git(p_root, "add", ".")
    git(p_root, "commit", "-qm", "missions")
    assert invoking_checkout_would_adopt(repo, p_root) is True
    assert len(counting_claims) == 1
