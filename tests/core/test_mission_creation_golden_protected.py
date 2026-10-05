"""Golden cells, behaviour families 2 and 4: protected targets and owned checkouts.

Golden behaviour matrix: regenerate only for an intended behaviour change
(``SPEC_KITTY_REGEN_GOLDEN=1``, serial); see ``tests/core/_mission_create_golden.py``.
Zero patches. Every cell runs ``create_mission_core`` on a real repository.

Cell ids (15):

Protected Primary Branch (``main``, also named in ``protection.protected_branches``):

* ``protected/single_branch/plain``: the mission branch is minted and checked
  out, and the scaffold commit lands on it (a create invariant).
* ``protected/single_branch/commit_to_target``: no mint; ``commit_to_target``
  is persisted.
* ``protected/single_branch/retention`` and ``protected/single_branch/pr_bound``:
  the flag cross-products on the mint path.
* ``protected/lanes/plain``, ``protected/coord/plain``,
  ``protected/lanes_with_coord/plain``: what non-minting topologies do on a
  protected target today (skipped commits included).
* ``protected/coord/retention``: the retention cross-product on the
  coordination path.

Protection decision (``bias=False`` Primary Branch resolution):

* ``primary_unconfigured/single_branch``: ``main`` with no protection
  configured is still protected, because it is the Primary Branch.
* ``primary_no_origin_head/single_branch``: the same without ``origin/HEAD``.
* ``configured_non_primary/single_branch``: a configured protected branch
  (``release``) that is not the Primary Branch, targeted from ``topic``.

Owned checkout (family 4, a real ``git worktree add`` resolved through
``resolve_owned_create_root``; FR-022 twin):

* ``owned/<topology>`` for topology in {``single_branch``, ``lanes``,
  ``coord``, ``lanes_with_coord``}.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.core.owned_mission import resolve_owned_create_root
from tests.core._mission_create_golden import (
    FLAG_VARIANTS,
    PRIMARY_BRANCH,
    assert_golden,
    build_repo,
    git,
    run_cell,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FAMILY = "protected"
_PROTECTED = (PRIMARY_BRANCH,)


def _slug(*parts: str) -> str:
    return "-".join(part.replace("_", "-") for part in ("prot", *parts))


def _create(repo: Path, slug: str, topology: MissionTopology, **kwargs: Any) -> Callable[[], MissionCreationResult]:
    return lambda: create_mission_core(repo, slug, topology=topology, allow_worktree_context=True, **kwargs)


_PROTECTED_CELLS: dict[str, tuple[MissionTopology, dict[str, Any]]] = {
    "single_branch/plain": (MissionTopology.SINGLE_BRANCH, {}),
    "single_branch/commit_to_target": (MissionTopology.SINGLE_BRANCH, {"commit_to_target": True}),
    "single_branch/retention": (MissionTopology.SINGLE_BRANCH, FLAG_VARIANTS["retention"]),
    "single_branch/pr_bound": (MissionTopology.SINGLE_BRANCH, FLAG_VARIANTS["pr_bound"]),
    "lanes/plain": (MissionTopology.LANES, {}),
    "coord/plain": (MissionTopology.COORD, {}),
    "coord/retention": (MissionTopology.COORD, FLAG_VARIANTS["retention"]),
    "lanes_with_coord/plain": (MissionTopology.LANES_WITH_COORD, {}),
}


@pytest.mark.parametrize("cell", list(_PROTECTED_CELLS))
def test_protected_primary(tmp_path: Path, cell: str) -> None:
    topology, kwargs = _PROTECTED_CELLS[cell]
    slug = _slug(*cell.split("/"))
    repo = build_repo(tmp_path, target=PRIMARY_BRANCH, protected=_PROTECTED)
    observed = run_cell(repo, tmp_path, _create(repo, slug, topology, **kwargs), slugs=[slug])
    assert_golden(_FAMILY, f"protected/{cell}", observed)


def test_primary_unconfigured(tmp_path: Path) -> None:
    slug = _slug("primary-unconfigured")
    repo = build_repo(tmp_path, target=PRIMARY_BRANCH)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "primary_unconfigured/single_branch", observed)


def test_primary_no_origin_head(tmp_path: Path) -> None:
    slug = _slug("primary-no-origin-head")
    repo = build_repo(tmp_path, target=PRIMARY_BRANCH, origin_head=False)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "primary_no_origin_head/single_branch", observed)


def test_configured_non_primary(tmp_path: Path) -> None:
    slug = _slug("configured-non-primary")
    repo = build_repo(tmp_path, protected=(PRIMARY_BRANCH, "release"))
    git(repo, "branch", "release", PRIMARY_BRANCH)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH, target_branch="release"), slugs=[slug])
    assert_golden(_FAMILY, "configured_non_primary/single_branch", observed)


_OWNED = (
    MissionTopology.SINGLE_BRANCH,
    MissionTopology.LANES,
    MissionTopology.COORD,
    MissionTopology.LANES_WITH_COORD,
)


@pytest.mark.parametrize("topology", _OWNED, ids=lambda t: t.value)
def test_owned_checkout(tmp_path: Path, topology: MissionTopology) -> None:
    slug = _slug("owned", topology.value)
    repo = build_repo(tmp_path)
    owned_path = tmp_path / "owned"
    git(repo, "worktree", "add", str(owned_path), "-b", "owned-topic")
    owned = resolve_owned_create_root(repo.resolve(), owned_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, topology, owned_create_root=owned), slugs=[slug])
    assert_golden(_FAMILY, f"owned/{topology.value}", observed)
