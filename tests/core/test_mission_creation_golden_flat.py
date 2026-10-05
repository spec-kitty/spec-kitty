"""Golden cells, behaviour family 1: branch-flat create on an unprotected target.

Golden behaviour matrix: regenerate only for an intended behaviour change
(``SPEC_KITTY_REGEN_GOLDEN=1``, serial); see ``tests/core/_mission_create_golden.py``.
Zero patches. Every cell runs ``create_mission_core`` on a real repository whose
write checkout sits on the unprotected branch ``topic`` and records the
normalised outcome and repository state in ``golden/mission_create_flat.json``.

Cell ids (15):

* ``<topology>/<variant>`` for topology in {``single_branch``, ``lanes``} and
  variant in {``plain``, ``pr_bound``, ``retention``, ``documentation``,
  ``summary``} (10 cells). ``summary`` passes a non-default friendly name,
  purpose TL;DR and purpose context.
* ``single_branch/commit_to_target``: the override on an unprotected target
  (no mint either way; the flag is persisted).
* ``lanes/abandoned_prior_recreate``: a genesis-only prior with the same slug
  and type is abandoned, so a second create succeeds as a second mission.
* ``lanes/same_slug_other_type``: a live prior of another mission type is not a
  duplicate.
* ``<topology>/target_not_checked_out``: ``target_branch`` names an existing
  branch other than the checked-out one (the scaffold commit is a disclosed
  bootstrap skip), for both flat topologies.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from tests.core._mission_create_golden import (
    FLAG_VARIANTS,
    SUMMARY_VARIANT,
    assert_golden,
    await_fresh_mid8_bucket,
    await_mid8_bucket_after,
    build_repo,
    commit_spec,
    git,
    run_cell,
    variant_kwargs,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FAMILY = "flat"
_FLAT = (MissionTopology.SINGLE_BRANCH, MissionTopology.LANES)


def _slug(topology: MissionTopology, variant: str) -> str:
    return f"flat-{topology.value.replace('_', '-')}-{variant.replace('_', '-')}"


def _create(repo: Path, slug: str, topology: MissionTopology, **kwargs: Any) -> Callable[[], MissionCreationResult]:
    return lambda: create_mission_core(repo, slug, topology=topology, allow_worktree_context=True, **kwargs)


@pytest.mark.parametrize("topology", _FLAT, ids=lambda t: t.value)
@pytest.mark.parametrize("variant", [*FLAG_VARIANTS, SUMMARY_VARIANT])
def test_flat_create(tmp_path: Path, topology: MissionTopology, variant: str) -> None:
    slug = _slug(topology, variant)
    kwargs = variant_kwargs(slug, variant)
    repo = build_repo(tmp_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, topology, **kwargs), slugs=[slug])
    assert_golden(_FAMILY, f"{topology.value}/{variant}", observed)


def test_single_branch_commit_to_target_unprotected(tmp_path: Path) -> None:
    slug = "flat-single-branch-commit-to-target"
    repo = build_repo(tmp_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH, commit_to_target=True), slugs=[slug])
    assert_golden(_FAMILY, "single_branch/commit_to_target", observed)


def test_abandoned_prior_recreate(tmp_path: Path) -> None:
    """A genesis-only prior (spec never committed) is abandoned: re-create succeeds."""
    slug = "flat-abandoned-prior"
    repo = build_repo(tmp_path)
    await_fresh_mid8_bucket()
    first = create_mission_core(repo, slug, topology=MissionTopology.LANES, allow_worktree_context=True)
    first_mid8 = first.meta["mid8"]
    # Wait out the first create's bucket so the second create mints a different mid8.
    await_mid8_bucket_after(first_mid8)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "lanes/abandoned_prior_recreate", observed)


def test_same_slug_other_type(tmp_path: Path) -> None:
    """A LIVE prior of another mission type does not trip the duplicate guard."""
    slug = "flat-same-slug-other-type"
    repo = build_repo(tmp_path)
    await_fresh_mid8_bucket()
    first = create_mission_core(repo, slug, topology=MissionTopology.LANES, mission="research", allow_worktree_context=True)
    commit_spec(repo, first.feature_dir)
    await_mid8_bucket_after(first.meta["mid8"])
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "lanes/same_slug_other_type", observed)


@pytest.mark.parametrize("topology", _FLAT, ids=lambda t: t.value)
def test_target_not_checked_out(tmp_path: Path, topology: MissionTopology) -> None:
    slug = _slug(topology, "elsewhere")
    repo = build_repo(tmp_path)
    git(repo, "branch", "elsewhere")
    observed = run_cell(repo, tmp_path, _create(repo, slug, topology, target_branch="elsewhere"), slugs=[slug])
    assert_golden(_FAMILY, f"{topology.value}/target_not_checked_out", observed)
