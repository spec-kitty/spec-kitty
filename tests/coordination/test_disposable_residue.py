"""Context-aware disposability: ``ResidueContext`` / ``_is_disposable_residue`` / ``_checkout_role_for`` (#5965 / #5966)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import (
    CheckoutRole,
    ResidueContext,
    _checkout_role_for,
    _is_disposable_residue,
)

_SLUG = "m-01ABCDEF"
_OTHER = "other-01ZZZZZZ"
_REVIEW = f"kitty-specs/{_SLUG}/tasks/WP01/review-cycle-1.md"

# (relative path inside the Mission directory, expected disposable per role) under the COORD topology.
_OWN = {
    "tasks/WP01/review-cycle-1.md": "coord",
    "traces/notes.md": "coord",
    "acceptance-matrix.json": "coord",
    "issue-matrix.md": "coord",
    "status.events.jsonl": "status",
    "status.json": "status",
    "meta.json": "bookkeeping",
    "spec.md": "never",
}


def _expected(kind: str, role: CheckoutRole) -> bool:
    if kind == "never":
        return False
    if kind in ("bookkeeping", "status"):
        return True  # status state is this Mission's regenerated output in every role, the coordination worktree included
    return role is not CheckoutRole.COORDINATION


@pytest.mark.parametrize("role", [CheckoutRole.REPOSITORY_ROOT, CheckoutRole.COORDINATION, CheckoutRole.MISSION, CheckoutRole.LANE])
@pytest.mark.parametrize("rel", sorted(_OWN))
def test_own_mission_paths_by_role(rel: str, role: CheckoutRole) -> None:
    context = ResidueContext(role=role, mission_slug=_SLUG, topology=MissionTopology.COORD)

    assert _is_disposable_residue(f"kitty-specs/{_SLUG}/{rel}", context) is _expected(_OWN[rel], role)


def test_5965_review_cycle_in_the_coordination_worktree_is_the_only_copy() -> None:
    context = ResidueContext(CheckoutRole.COORDINATION, _SLUG, MissionTopology.COORD)

    assert _is_disposable_residue(_REVIEW, context) is False


def test_normal_path_repository_root_keeps_cleaning_its_own_stale_status_copy() -> None:
    context = ResidueContext(CheckoutRole.REPOSITORY_ROOT, _SLUG, MissionTopology.COORD)

    assert _is_disposable_residue(f"kitty-specs/{_SLUG}/status.json", context) is True
    assert _is_disposable_residue(f"kitty-specs/{_SLUG}/status.events.jsonl", context) is True


@pytest.mark.parametrize("role", [CheckoutRole.REPOSITORY_ROOT, CheckoutRole.MISSION, CheckoutRole.LANE, CheckoutRole.COORDINATION])
@pytest.mark.parametrize("rel", ["traces/n.md", "status.json", "meta.json", "tasks/WP01/review-cycle-1.md", "spec.md"])
def test_5966_another_missions_artifact_is_never_disposable(rel: str, role: CheckoutRole) -> None:
    context = ResidueContext(role, _SLUG, MissionTopology.COORD)

    assert _is_disposable_residue(f"kitty-specs/{_OTHER}/{rel}", context) is False


def test_the_composed_coordination_directory_counts_as_the_missions_own() -> None:
    composed = f"{_SLUG}-01ABCDEF"
    context = ResidueContext(CheckoutRole.REPOSITORY_ROOT, _SLUG, MissionTopology.COORD, frozenset({_SLUG, composed}))

    assert _is_disposable_residue(f"kitty-specs/{composed}/status.json", context) is True
    assert _is_disposable_residue(f"kitty-specs/{composed}/meta.json", context) is True


@pytest.mark.parametrize("topology", [MissionTopology.LANES, MissionTopology.SINGLE_BRANCH])
def test_without_coordination_topology_nothing_is_coord_residue(topology: MissionTopology) -> None:
    context = ResidueContext(CheckoutRole.REPOSITORY_ROOT, _SLUG, topology)

    assert _is_disposable_residue(f"kitty-specs/{_SLUG}/status.json", context) is False
    assert _is_disposable_residue(f"kitty-specs/{_SLUG}/meta.json", context) is True


def test_a_source_file_is_never_disposable() -> None:
    for role in (CheckoutRole.REPOSITORY_ROOT, CheckoutRole.COORDINATION, CheckoutRole.LANE):
        assert _is_disposable_residue("src/app.py", ResidueContext(role, _SLUG, MissionTopology.COORD)) is False


def test_a_tool_owned_checkout_is_disposable_throughout() -> None:
    context = ResidueContext(role=CheckoutRole.TOOL_OWNED)

    assert _is_disposable_residue("anything/at/all.py", context) is True
    assert _is_disposable_residue(f"kitty-specs/{_OTHER}/traces/n.md", context) is True
    assert context.for_checkout(Path("/r"), Path("/r/.worktrees/x")) is context


# --- construction -----------------------------------------------------------------


@pytest.mark.parametrize("role", [CheckoutRole.REPOSITORY_ROOT, CheckoutRole.COORDINATION, CheckoutRole.MISSION, CheckoutRole.LANE])
def test_a_non_tool_owned_context_requires_slug_and_topology(role: CheckoutRole) -> None:
    with pytest.raises(ValueError, match="mission_slug"):
        ResidueContext(role=role, topology=MissionTopology.COORD)
    with pytest.raises(ValueError, match="MissionTopology"):
        ResidueContext(role=role, mission_slug=_SLUG)


def _mission_repo(tmp_path: Path, meta: str | None) -> Path:
    mission_dir = tmp_path / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    if meta is not None:
        (mission_dir / "meta.json").write_text(meta, encoding="utf-8")
    return tmp_path


def test_for_mission_reads_the_stored_topology(tmp_path: Path) -> None:
    meta = json.dumps({"mission_slug": _SLUG, "mission_id": "01ABCDEFGHJKMNPQRSTVWXYZ00", "topology": "lanes"})
    repo = _mission_repo(tmp_path, meta)

    context = ResidueContext.for_mission(repo, _SLUG, CheckoutRole.LANE)

    assert context.topology is MissionTopology.LANES
    assert context.mission_slug == _SLUG
    assert _SLUG in context.mission_dir_names


def test_for_mission_refuses_an_unreadable_topology(tmp_path: Path) -> None:
    repo = _mission_repo(tmp_path, "{not json")

    with pytest.raises(Exception, match=r"(?i)meta|json|decode|read"):
        ResidueContext.for_mission(repo, _SLUG, CheckoutRole.REPOSITORY_ROOT)


def test_for_mission_without_meta_never_projects_a_topology(tmp_path: Path) -> None:
    repo = _mission_repo(tmp_path, None)

    with pytest.raises(FileNotFoundError):
        ResidueContext.for_mission(repo, _SLUG, CheckoutRole.REPOSITORY_ROOT)


def test_for_mission_tool_owned_needs_no_mission(tmp_path: Path) -> None:
    assert ResidueContext.for_mission(tmp_path, "nothing", CheckoutRole.TOOL_OWNED).role is CheckoutRole.TOOL_OWNED


# --- role resolver ---------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True)


@pytest.fixture
def repo_with_worktrees(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "base")
    _git(repo, "worktree", "add", "-q", "-b", "coordb", str(repo / ".worktrees" / f"{_SLUG}-coord"))
    _git(repo, "worktree", "add", "-q", "-b", "laneb", str(repo / ".worktrees" / f"{_SLUG}-lane-a"))
    return repo


@pytest.mark.git_repo
def test_checkout_role_resolves_each_checkout_by_the_registry(repo_with_worktrees: Path) -> None:
    repo = repo_with_worktrees

    assert _checkout_role_for(repo, repo) is CheckoutRole.REPOSITORY_ROOT
    assert _checkout_role_for(repo, repo / ".worktrees" / f"{_SLUG}-coord") is CheckoutRole.COORDINATION
    assert _checkout_role_for(repo, repo / ".worktrees" / f"{_SLUG}-lane-a") is CheckoutRole.LANE


@pytest.mark.git_repo
def test_checkout_role_fails_toward_the_strictest_role(repo_with_worktrees: Path, tmp_path: Path) -> None:
    repo = repo_with_worktrees
    husk = repo / ".worktrees" / "husk-lane-b"
    husk.mkdir()

    assert _checkout_role_for(repo, husk) is CheckoutRole.COORDINATION
    assert _checkout_role_for(repo, tmp_path / "somewhere-else") is CheckoutRole.COORDINATION


@pytest.mark.git_repo
def test_checkout_role_with_an_unreadable_registry_is_the_strictest(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    (not_a_repo / ".worktrees" / "x-lane-a").mkdir(parents=True)

    assert _checkout_role_for(not_a_repo, not_a_repo / ".worktrees" / "x-lane-a") is CheckoutRole.COORDINATION


@pytest.mark.git_repo
def test_for_checkout_retargets_the_role_and_keeps_the_mission(repo_with_worktrees: Path) -> None:
    repo = repo_with_worktrees
    root_ctx = ResidueContext(CheckoutRole.REPOSITORY_ROOT, _SLUG, MissionTopology.COORD)

    coord_ctx = root_ctx.for_checkout(repo, repo / ".worktrees" / f"{_SLUG}-coord")

    assert coord_ctx.role is CheckoutRole.COORDINATION
    assert (coord_ctx.mission_slug, coord_ctx.topology) == (_SLUG, MissionTopology.COORD)
    assert coord_ctx.is_disposable(_REVIEW) is False
    assert root_ctx.is_disposable(_REVIEW) is True


def test_coordination_role_keeps_another_missions_status_state() -> None:
    context = ResidueContext(role=CheckoutRole.COORDINATION, mission_slug=_SLUG, topology=MissionTopology.COORD)

    assert not _is_disposable_residue(f"kitty-specs/{_OTHER}/status.json", context)
    assert not _is_disposable_residue(f"kitty-specs/{_OTHER}/status.events.jsonl", context)
