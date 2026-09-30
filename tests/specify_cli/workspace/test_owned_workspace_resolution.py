"""owned-checkout-lifecycle-authority WP05 (T022-T025).

Gives workspace resolution an owned arm, per-checkout WP-metadata caches, and
an identity-guard arm. The red-first pair (T022) reproduces, through
pre-existing entry points, that owned WP workspace resolution folds to the
repository root checkout (FR-006/FR-011) and that the process-local WP
metadata caches collide across checkouts sharing one mission slug (FR-019).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from mission_runtime.checkout_identity import CheckoutIdentityError
from mission_runtime.owned_checkout import OwnedCheckout
from mission_runtime.resolution import resolve_action_context
from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.workspace.context import (
    _FEATURE_WP_METADATA_CACHE,
    _FEATURE_WP_METADATA_ERROR_CACHE,
    _FEATURE_WP_METADATA_SNAPSHOT_CACHE,
    WorkspaceContext,
    build_normalized_wp_index,
    clear_workspace_resolution_caches,
    get_normalized_wp,
    resolve_workspace_for_wp,
    save_context,
)

_SLUG = "owned-wp05-01M3M2ZB"
_TARGET = "codex/owned"


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    clear_workspace_resolution_caches()


# ---------------------------------------------------------------------------
# --- builders ---
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _wp_frontmatter(wp_id: str, title: str, *, execution_mode: str = "code_change") -> str:
    return (
        f"---\nwork_package_id: {wp_id}\ntitle: {title}\ndependencies: []\n"
        "requirement_refs: []\nsubtasks: []\nowned_files: []\n"
        f"authoritative_surface: app.py\nexecution_mode: {execution_mode}\n---\n\n# Task\n"
    )


def _write_mission(
    root: Path,
    *,
    slug: str = _SLUG,
    topology: str = "single_branch",
    titles: dict[str, str] | None = None,
) -> Path:
    """Write ``kitty-specs/<slug>`` (meta.json + tasks/ + lanes.json) into ``root``."""
    titles = titles if titles is not None else {"WP01": "WP01 title", "WP02": "WP02 title"}
    mission = root / "kitty-specs" / slug
    (mission / "tasks").mkdir(parents=True, exist_ok=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3M2ZB0000000000000WP05",
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "topology": topology,
                "target_branch": _TARGET,
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    for wp_id, title in titles.items():
        (mission / "tasks" / f"{wp_id}-a.md").write_text(_wp_frontmatter(wp_id, title), encoding="utf-8")
    write_lanes_json(
        mission,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=f"mission-{slug}",
            mission_branch=f"kitty/mission-{slug}",
            target_branch=_TARGET,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=tuple(titles.keys()),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-09-28T00:00:00Z",
            computed_from="test",
        ),
    )
    return mission


def _owned_repo(
    tmp_path: Path,
    *,
    topology: str = "single_branch",
    stale_root_copy: bool = False,
    slug: str = _SLUG,
) -> tuple[Path, Path]:
    """Build ``R`` (a plain git repo) and ``P`` (a linked worktree of ``R``).

    ``P`` carries the real mission (WP01, WP02 titled ``"P WP.. title"``); an
    optional stale copy is ALSO written into ``R`` with **different** titles
    (and extra WPs), so a test can assert the seam never reads it.
    """
    r = tmp_path / "R"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "owned-wp05@example.test")
    _git(r, "config", "user.name", "Owned WP05")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("seed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")

    p = tmp_path / "P"
    _git(r, "worktree", "add", "-qb", _TARGET, str(p))
    _write_mission(p, slug=slug, topology=topology, titles={"WP01": "P WP01 title", "WP02": "P WP02 title"})
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "owned mission")

    if stale_root_copy:
        _write_mission(
            r,
            slug=slug,
            topology=topology,
            titles={
                "WP01": "R WP01 title (stale)",
                "WP02": "R WP02 title (stale)",
                "WP03": "R WP03 title (stale, absent from P)",
            },
        )
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "stale copy of the mission")

    return r, p


def _mint_plain(
    repo_root: Path,
    owned_root: Path,
    mission_slug: str,
    *,
    topology: MissionTopology = MissionTopology.SINGLE_BRANCH,
    target_branch: str = _TARGET,
) -> OwnedCheckout:
    """A validated fact over plain (non-git) directories, for pure-path tests."""
    return OwnedCheckout._mint(
        repository_root=repo_root,
        owned_root=owned_root,
        mission_dir=owned_root / "kitty-specs" / mission_slug,
        mission_slug=mission_slug,
        topology=topology,
        write_branch=target_branch,
    )


# ---------------------------------------------------------------------------
# --- T022 red-first (owned kind, cache isolation) ---
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_owned_workspace_is_owned_checkout(tmp_path: Path) -> None:
    """FR-006/FR-011: an owned WP's workspace is P itself, never a lane worktree under R.

    Pre-existing entry point: ``resolve_action_context``, no stub, now that
    WP04 fixed the ``wp_file`` leg. On base (before this WP's fix), the
    workspace leg still folded to R (lane worktree under R/.worktrees, or a
    ValueError from R's WP index) regardless of the call shape -- this test
    was red before the fix commit. It is called with the real minter's
    ``owned=`` fact -- only a validated fact produces the ``owned_checkout``
    kind (T023).
    """
    r, p = _owned_repo(tmp_path)
    fact = resolve_owned_mission(r, p, _SLUG)

    ctx = resolve_action_context(r, action="implement", feature=_SLUG, wp_id="WP01", owned=fact)

    assert ctx.workspace_path == str(p.resolve())
    assert ctx.resolution_kind == "owned_checkout"
    assert ctx.lane_id is None
    assert not Path(ctx.workspace_path).is_relative_to(r) or r == p


@pytest.mark.git_repo
def test_same_slug_cache_isolated_per_checkout(tmp_path: Path) -> None:
    """FR-019 (#5009 edaa9cd83 carry): the WP-metadata cache never collides
    across two checkouts sharing one mission slug, in either direction.

    The P-side lookup is minted through the real minter (``owned=``): a bare
    ``get_normalized_wp(P, ...)`` with no keyword folds through
    ``get_main_repo_root`` to R (P is a linked worktree of R) regardless of
    this WP's cache-key fix -- that fold is correct behaviour for an
    unconverted caller, and is exactly why FR-019 needs the ``owned=`` fact
    to reach P at all.
    """
    r, p = _owned_repo(tmp_path, stale_root_copy=True)
    fact = resolve_owned_mission(r, p, _SLUG)

    first = get_normalized_wp(r, _SLUG, "WP01")
    second = get_normalized_wp(r, _SLUG, "WP01", owned=fact)
    third = get_normalized_wp(r, _SLUG, "WP01")

    assert first.metadata.title == "R WP01 title (stale)"
    assert second.metadata.title == "P WP01 title"
    assert third.metadata.title == "R WP01 title (stale)"


# ---------------------------------------------------------------------------
# --- T023 owned arm / coordination-topology characterisation ---
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
def test_owned_arm_raises_on_mission_slug_mismatch(tmp_path: Path) -> None:
    fact = _mint_plain(tmp_path / "R", tmp_path / "P", _SLUG)
    with pytest.raises(ValueError, match="other-slug"):
        resolve_workspace_for_wp(tmp_path / "R", "other-slug", "WP01", owned=fact)


@pytest.mark.unit
@pytest.mark.fast
def test_owned_single_branch_workspace_fields(tmp_path: Path) -> None:
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(p)
    fact = _mint_plain(r, p, _SLUG)

    resolved = resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact)

    assert resolved.resolution_kind == "owned_checkout"
    assert resolved.worktree_path == fact.owned_root
    assert resolved.lane_id is None
    assert resolved.lane_wp_ids == []
    assert resolved.branch_name == _TARGET
    assert resolved.workspace_name == fact.owned_root.name
    assert resolved.runs_in_checkout_root is True


@pytest.mark.unit
@pytest.mark.fast
def test_owned_arm_covers_planning_artifact_wps_too(tmp_path: Path) -> None:
    """The mission's own planning surface IS the owned checkout (FR-006)."""
    r = tmp_path / "R"
    p = tmp_path / "P"
    mission = p / "kitty-specs" / _SLUG
    (mission / "tasks").mkdir(parents=True)
    (mission / "tasks" / "WP03-a.md").write_text(_wp_frontmatter("WP03", "Docs", execution_mode="planning_artifact"), encoding="utf-8")
    fact = _mint_plain(r, p, _SLUG)

    resolved = resolve_workspace_for_wp(r, _SLUG, "WP03", owned=fact)

    assert resolved.resolution_kind == "owned_checkout"
    assert resolved.execution_mode == "planning_artifact"
    assert resolved.worktree_path == p.resolve()


@pytest.mark.unit
@pytest.mark.fast
def test_owned_single_branch_arm_makes_no_subprocess_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: owned resolution is file reads only."""
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(p)
    fact = _mint_plain(r, p, _SLUG)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess.run must not be called on the owned single_branch arm")

    monkeypatch.setattr(subprocess, "run", _raise)

    resolved = resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact)
    assert resolved.resolution_kind == "owned_checkout"


@pytest.mark.unit
@pytest.mark.fast
def test_owned_arm_missing_wp_names_owned_tasks_dir(tmp_path: Path) -> None:
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(p)
    fact = _mint_plain(r, p, _SLUG)

    with pytest.raises(ValueError, match="Work package WP99 was not found under") as excinfo:
        resolve_workspace_for_wp(r, _SLUG, "WP99", owned=fact)

    message = str(excinfo.value)
    assert str(p) in message
    assert str(r) not in message


@pytest.mark.git_repo
@pytest.mark.parametrize("caller_repo_root", ["r", "p"])
def test_owned_coordination_topology_anchors_lanes_on_repository_root(tmp_path: Path, caller_repo_root: str) -> None:
    """LANES_WITH_COORD / COORD are reachable only through ``next``: they keep
    the lane arm, reading lanes.json/WP metadata through the owned checkout
    (plan IC-03), but every filesystem path they compose anchors on the fact,
    never on whatever ``repo_root`` the caller passes (review cycle 1,
    HIGH-1). ``next`` passes ``P`` (``next_cmd.py:176``); this test proves the
    lane worktree resolves under ``R`` regardless -- the fact is the single
    internal representation, not the caller's argument.
    """
    r, p = _owned_repo(tmp_path, topology="lanes_with_coord")
    fact = resolve_owned_mission(r, p, _SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    caller_root = {"r": r, "p": p}[caller_repo_root]

    resolved = resolve_workspace_for_wp(caller_root, _SLUG, "WP01", owned=fact)

    assert resolved.resolution_kind == "lane_workspace"
    assert resolved.lane_id == "lane-a"
    assert resolved.worktree_path == r / ".worktrees" / f"{_SLUG}-lane-a"
    assert not resolved.worktree_path.is_relative_to(p)


@pytest.mark.git_repo
@pytest.mark.parametrize("caller_repo_root", ["r", "p"])
def test_owned_coordination_topology_planning_artifact_anchors_on_owned_root(tmp_path: Path, caller_repo_root: str) -> None:
    """A ``planning_artifact`` WP in an owned coordination-topology mission
    resolves to the owned checkout ``P`` -- the mission's planning surface --
    regardless of the caller's ``repo_root`` (review cycle 1, HIGH-1).
    """
    r, p = _owned_repo(tmp_path, topology="lanes_with_coord")
    mission = p / "kitty-specs" / _SLUG
    (mission / "tasks" / "WP03-a.md").write_text(_wp_frontmatter("WP03", "Docs", execution_mode="planning_artifact"), encoding="utf-8")
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "add planning_artifact WP")
    fact = resolve_owned_mission(r, p, _SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    caller_root = {"r": r, "p": p}[caller_repo_root]

    resolved = resolve_workspace_for_wp(caller_root, _SLUG, "WP03", owned=fact)

    assert resolved.resolution_kind == "repo_root"
    assert resolved.execution_mode == "planning_artifact"
    assert resolved.worktree_path == p.resolve()


@pytest.mark.git_repo
@pytest.mark.parametrize("caller_repo_root", ["r", "p"])
def test_owned_coordination_topology_context_anchors_on_repository_root(tmp_path: Path, caller_repo_root: str) -> None:
    """An existing lane workspace context (``.kittify/workspaces``) lives under
    the repository root, never the owned checkout; the context-backed arm
    joins ``context.worktree_path`` there regardless of the caller's
    ``repo_root`` (review cycle 1, HIGH-1).

    Asserts ``resolved.context is not None`` and a ``branch_name`` that
    differs from ``code_lane_branch_name(slug, "lane-a")`` (review cycle 2,
    MEDIUM-1b): without this, a mutant that reverts the dispatcher's
    ``find_context_for_wp`` lookup to the raw ``repo_root`` (missing the
    context at P, falling through to the lanes.json arm) still composes the
    identical ``R/.worktrees/<slug>-lane-a`` path by coincidence and the
    weaker assertions below cannot tell the two arms apart.
    """
    from specify_cli.lanes.branch_naming import code_lane_branch_name

    r, p = _owned_repo(tmp_path, topology="lanes_with_coord")
    fact = resolve_owned_mission(r, p, _SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    context_branch_name = "custom/context-branch-for-wp01"
    assert context_branch_name != code_lane_branch_name(_SLUG, "lane-a")
    save_context(
        r,
        WorkspaceContext(
            wp_id="WP01",
            mission_slug=_SLUG,
            worktree_path=f".worktrees/{_SLUG}-lane-a",
            branch_name=context_branch_name,
            base_branch=_TARGET,
            base_commit="abc123",
            dependencies=[],
            created_at="2026-09-28T00:00:00Z",
            created_by="test",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP01", "WP02"],
            current_wp="WP01",
        ),
    )
    caller_root = {"r": r, "p": p}[caller_repo_root]

    resolved = resolve_workspace_for_wp(caller_root, _SLUG, "WP01", owned=fact)

    assert resolved.resolution_kind == "lane_workspace"
    assert resolved.worktree_path == r / ".worktrees" / f"{_SLUG}-lane-a"
    assert not resolved.worktree_path.is_relative_to(p)
    assert resolved.context is not None
    assert resolved.branch_name == context_branch_name


@pytest.mark.git_repo
@pytest.mark.parametrize("caller_repo_root", ["r", "p"])
def test_owned_coordination_topology_planning_lane_code_change_anchors_on_owned_root(tmp_path: Path, caller_repo_root: str) -> None:
    """A ``code_change`` WP assigned to the canonical ``lane-planning`` lane in
    an owned coordination-topology mission's ``lanes.json`` resolves to the
    owned checkout ``P`` -- the mission's planning surface -- regardless of
    the caller's ``repo_root`` (review cycle 2, MEDIUM-1a).

    Distinct from ``test_owned_coordination_topology_planning_artifact_anchors_on_owned_root``:
    that test's WP has ``execution_mode: planning_artifact`` and is resolved
    by ``_owned_checkout_workspace``/``_planning_artifact_workspace`` -- it
    never reaches ``_lanes_manifest_workspace``'s planning-lane sub-arm at
    all, so it cannot pin that sub-arm's own anchor.
    """
    r, p = _owned_repo(tmp_path, topology="lanes_with_coord")
    mission = p / "kitty-specs" / _SLUG
    (mission / "tasks" / "WP04-a.md").write_text(_wp_frontmatter("WP04", "Planning-lane WP", execution_mode="code_change"), encoding="utf-8")
    write_lanes_json(
        mission,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=f"mission-{_SLUG}",
            mission_branch=f"kitty/mission-{_SLUG}",
            target_branch=_TARGET,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01", "WP02"),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
                ExecutionLane(
                    lane_id="lane-planning",
                    wp_ids=("WP04",),
                    write_scope=("kitty-specs/**",),
                    predicted_surfaces=("planning",),
                    depends_on_lanes=(),
                    parallel_group=0,
                ),
            ],
            computed_at="2026-09-28T00:00:00Z",
            computed_from="test",
        ),
    )
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "add lane-planning WP")
    fact = resolve_owned_mission(r, p, _SLUG, allowed_topologies=NEXT_OWNED_TOPOLOGIES)
    caller_root = {"r": r, "p": p}[caller_repo_root]

    resolved = resolve_workspace_for_wp(caller_root, _SLUG, "WP04", owned=fact)

    assert resolved.resolution_kind == "repo_root"
    assert resolved.lane_id == "lane-planning"
    assert resolved.worktree_path == p.resolve()


# ---------------------------------------------------------------------------
# --- T024 cache keys ---
# ---------------------------------------------------------------------------


# Mutation-testing proof (review cycle 1, HIGH-2; corrected in review cycle
# 2), recorded in the Activity Log: reverting the two
# ``_normalized_feature_cache_key(tasks_dir, ...)`` call sites in
# ``src/specify_cli/workspace/context.py`` to key on ``repo_root`` instead
# turns exactly 3 of the T024 tests below red in a detached scratch worktree
# -- test_editing_p_does_not_invalidate_r_cache_entry,
# test_r_and_p_collide_on_identical_filename_and_mtime_but_not_on_key, and
# test_error_cache_identical_snapshot_malformed_p_valid_r. The remaining
# T024 tests stay green under that mutant: their R/P snapshots differ in
# mtime, so the pre-existing snapshot-invalidation check masks the key
# collision for them, which is exactly why the two collision tests above
# exist.


@pytest.mark.unit
@pytest.mark.fast
def test_cache_survives_r_then_p_then_r_via_build_index(tmp_path: Path) -> None:
    """R and P share one mission slug; the P-side lookup must be minted
    through ``owned=`` (review cycle 1, HIGH-2) -- a bare ``repo_root=P`` call
    on a plain directory pair already differs from ``repo_root=R`` regardless
    of the cache-key fix, so it cannot exercise FR-019 at all.
    """
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p, titles={"WP01": "P title"})
    fact = _mint_plain(r, p, _SLUG)

    r_index = build_normalized_wp_index(r, _SLUG)
    p_index = build_normalized_wp_index(r, _SLUG, owned=fact)
    r_index_again = build_normalized_wp_index(r, _SLUG)

    assert r_index["WP01"].metadata.title == "R title"
    assert p_index["WP01"].metadata.title == "P title"
    assert r_index_again["WP01"].metadata.title == "R title"


@pytest.mark.unit
@pytest.mark.fast
def test_editing_p_does_not_invalidate_r_cache_entry(tmp_path: Path) -> None:
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p, titles={"WP01": "P title v1"})
    fact = _mint_plain(r, p, _SLUG)

    r_first = get_normalized_wp(r, _SLUG, "WP01")
    get_normalized_wp(r, _SLUG, "WP01", owned=fact)

    (p / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md").write_text(_wp_frontmatter("WP01", "P title v2"), encoding="utf-8")

    r_second = get_normalized_wp(r, _SLUG, "WP01")
    p_second = get_normalized_wp(r, _SLUG, "WP01", owned=fact)

    assert r_second is r_first
    assert p_second.metadata.title == "P title v2"


@pytest.mark.unit
@pytest.mark.fast
def test_r_and_p_collide_on_identical_filename_and_mtime_but_not_on_key(tmp_path: Path) -> None:
    """The strongest FR-019 proof: R and P have the SAME WP filename and the
    SAME ``st_mtime_ns`` (forced with ``os.utime``), so the mtime-keyed
    snapshot check alone cannot distinguish them -- only the tasks_dir-keyed
    cache key does (review cycle 1, HIGH-2).
    """
    import os

    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p, titles={"WP01": "P title"})
    fact = _mint_plain(r, p, _SLUG)

    r_wp_file = r / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md"
    p_wp_file = p / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md"
    pinned_ns = 1_700_000_000_000_000_000
    os.utime(r_wp_file, ns=(pinned_ns, pinned_ns))
    os.utime(p_wp_file, ns=(pinned_ns, pinned_ns))
    assert r_wp_file.stat().st_mtime_ns == p_wp_file.stat().st_mtime_ns == pinned_ns

    r_first = get_normalized_wp(r, _SLUG, "WP01")
    p_first = get_normalized_wp(r, _SLUG, "WP01", owned=fact)
    r_second = get_normalized_wp(r, _SLUG, "WP01")

    assert r_first.metadata.title == "R title"
    assert p_first.metadata.title == "P title"
    assert r_second.metadata.title == "R title"


@pytest.mark.unit
@pytest.mark.fast
def test_error_cache_identical_snapshot_malformed_p_valid_r(tmp_path: Path) -> None:
    """Same identical-snapshot trap as the collision test above, but for the
    error cache: P's WP is malformed while R's same-named, same-mtime WP is
    valid (review cycle 1, HIGH-2).
    """
    import os

    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p, titles={"WP01": "P title"})
    (p / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md").write_text("not frontmatter at all\n", encoding="utf-8")
    fact = _mint_plain(r, p, _SLUG)

    r_wp_file = r / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md"
    p_wp_file = p / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md"
    pinned_ns = 1_700_000_000_000_000_000
    os.utime(r_wp_file, ns=(pinned_ns, pinned_ns))
    os.utime(p_wp_file, ns=(pinned_ns, pinned_ns))

    r_wp = get_normalized_wp(r, _SLUG, "WP01")
    assert r_wp.metadata.title == "R title"

    with pytest.raises(ValueError, match="Could not read work package metadata for WP01"):
        get_normalized_wp(r, _SLUG, "WP01", owned=fact)

    # R's entry must still resolve correctly after P's error-cache write.
    assert get_normalized_wp(r, _SLUG, "WP01").metadata.title == "R title"


@pytest.mark.unit
@pytest.mark.fast
def test_clear_workspace_resolution_caches_empties_owned_wp_caches(tmp_path: Path) -> None:
    r = tmp_path / "R"
    _write_mission(r)

    build_normalized_wp_index(r, _SLUG)
    assert _FEATURE_WP_METADATA_CACHE

    clear_workspace_resolution_caches()

    assert _FEATURE_WP_METADATA_CACHE == {}
    assert _FEATURE_WP_METADATA_ERROR_CACHE == {}
    assert _FEATURE_WP_METADATA_SNAPSHOT_CACHE == {}


@pytest.mark.unit
@pytest.mark.fast
def test_malformed_wp_error_scoped_to_its_own_checkout(tmp_path: Path) -> None:
    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p, titles={"WP01": "P title"})
    (p / "kitty-specs" / _SLUG / "tasks" / "WP01-a.md").write_text("not frontmatter at all\n", encoding="utf-8")
    fact = _mint_plain(r, p, _SLUG)

    r_wp = get_normalized_wp(r, _SLUG, "WP01")
    assert r_wp.metadata.title == "R title"

    with pytest.raises(ValueError, match="Could not read work package metadata for WP01"):
        get_normalized_wp(r, _SLUG, "WP01", owned=fact)


@pytest.mark.unit
@pytest.mark.fast
def test_symlinked_checkout_hits_the_same_cache_key(tmp_path: Path) -> None:
    real = tmp_path / "real"
    _write_mission(real, titles={"WP01": "Real title"})
    link = tmp_path / "link"
    link.symlink_to(real)

    via_real = get_normalized_wp(real, _SLUG, "WP01")
    via_link = get_normalized_wp(link, _SLUG, "WP01")

    assert via_real is via_link


@pytest.mark.unit
@pytest.mark.fast
def test_three_checkouts_cycle_without_cross_contamination(tmp_path: Path) -> None:
    r = tmp_path / "R"
    p1 = tmp_path / "P1"
    p2 = tmp_path / "P2"
    _write_mission(r, titles={"WP01": "R title"})
    _write_mission(p1, titles={"WP01": "P1 title"})
    _write_mission(p2, titles={"WP01": "P2 title"})
    fact1 = _mint_plain(r, p1, _SLUG)
    fact2 = _mint_plain(r, p2, _SLUG)

    assert get_normalized_wp(r, _SLUG, "WP01").metadata.title == "R title"
    assert get_normalized_wp(r, _SLUG, "WP01", owned=fact1).metadata.title == "P1 title"
    assert get_normalized_wp(r, _SLUG, "WP01", owned=fact2).metadata.title == "P2 title"
    assert get_normalized_wp(r, _SLUG, "WP01", owned=fact1).metadata.title == "P1 title"
    assert get_normalized_wp(r, _SLUG, "WP01").metadata.title == "R title"


# ---------------------------------------------------------------------------
# --- T025 identity guard ---
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
class TestOwnedIdentityGuard:
    def _fact(self, tmp_path: Path) -> tuple[Path, Path, OwnedCheckout]:
        r = tmp_path / "R"
        p = tmp_path / "P"
        _write_mission(p)
        return r, p, _mint_plain(r, p, _SLUG)

    def test_cwd_inside_owned_checkout_passes(self, tmp_path: Path) -> None:
        r, p, fact = self._fact(tmp_path)
        resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=p)

    def test_cwd_subdirectory_of_owned_checkout_passes(self, tmp_path: Path) -> None:
        r, p, fact = self._fact(tmp_path)
        sub = p / "kitty-specs"
        resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=sub)

    def test_cwd_repository_root_is_refused_for_owned(self, tmp_path: Path) -> None:
        r, p, fact = self._fact(tmp_path)
        with pytest.raises(CheckoutIdentityError) as excinfo:
            resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=r)
        assert excinfo.value.expected == fact.owned_root

    def test_cwd_sibling_checkout_is_refused(self, tmp_path: Path) -> None:
        r, p, fact = self._fact(tmp_path)
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        with pytest.raises(CheckoutIdentityError):
            resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=sibling)

    def test_cwd_lane_worktree_under_r_is_refused(self, tmp_path: Path) -> None:
        r, p, fact = self._fact(tmp_path)
        lane_worktree = r / ".worktrees" / "some-other-mission-lane-a"
        lane_worktree.mkdir(parents=True)
        with pytest.raises(CheckoutIdentityError):
            resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=lane_worktree)


@pytest.mark.unit
@pytest.mark.fast
def test_lane_kind_identity_guard_control_unchanged(tmp_path: Path) -> None:
    """The pre-existing lane-workspace guard semantics are untouched: cwd=R passes."""
    r = tmp_path / "R"
    _write_mission(r)

    resolve_workspace_for_wp(r, _SLUG, "WP01", write_intent=True, current_cwd=r)


@pytest.mark.unit
@pytest.mark.fast
def test_enforce_checkout_identity_exempts_repo_root_kind_directly(tmp_path: Path) -> None:
    """T025 step 5: a ``repo_root`` kind is always exempt, even from a foreign
    cwd -- planning-lane / planning_artifact / single-branch resolutions are
    CWD-invariant (R3) and must proceed unconditionally.
    """
    from mission_runtime.checkout_identity import enforce_checkout_identity

    primary = tmp_path / "R"
    foreign = tmp_path / "foreign"
    foreign.mkdir(parents=True)

    enforce_checkout_identity(
        current_cwd=foreign,
        workspace_path=primary,
        primary_root=primary,
        resolution_kind="repo_root",
        mission_slug=_SLUG,
        wp_id="WP01",
    )


@pytest.mark.unit
@pytest.mark.fast
def test_owned_identity_gate_never_calls_get_main_repo_root_or_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin (review cycle 1, MEDIUM-4): the owned identity gate uses
    ``owned.repository_root`` directly and never falls back to
    ``get_main_repo_root`` (which itself may shell out, NFR-002). Forcing
    either to raise must NOT break a legitimate owned write from inside the
    owned checkout.
    """
    from specify_cli.core import paths as core_paths

    r = tmp_path / "R"
    p = tmp_path / "P"
    _write_mission(p)
    fact = _mint_plain(r, p, _SLUG)

    def _raise_get_main_repo_root(*_a: object, **_k: object) -> Path:
        raise AssertionError("get_main_repo_root must not be called on the owned identity gate")

    def _raise_subprocess_run(*_a: object, **_k: object) -> None:
        raise AssertionError("subprocess.run must not be called on the owned identity gate")

    monkeypatch.setattr(core_paths, "get_main_repo_root", _raise_get_main_repo_root)
    monkeypatch.setattr(subprocess, "run", _raise_subprocess_run)

    resolve_workspace_for_wp(r, _SLUG, "WP01", owned=fact, write_intent=True, current_cwd=p)
