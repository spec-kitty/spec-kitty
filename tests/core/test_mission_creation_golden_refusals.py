"""Golden cells, behaviour family 5: create-time refusals and the residue they leave.

Golden behaviour matrix: regenerate only for an intended behaviour change
(``SPEC_KITTY_REGEN_GOLDEN=1``, serial); see ``tests/core/_mission_create_golden.py``.
Zero patches (``monkeypatch.chdir`` in cell 10 changes the working directory; it
patches nothing). Each cell records the repository state before (``pre``) and
after (``post``) the refused call plus the refusal's kind, message and error
code. Where a refusal raises before any write, ``post == pre`` is part of the
snapshot: that equality is the pinned rollback behaviour.

Cell ids (17 = the 13 named refusal cells, 2 malformed-configuration cells
and 2 failed-create restore cells):

1. ``live_duplicate``: a same-slug, same-type prior whose ``spec.md`` is committed.
2. ``mission_branch_exists``: ``kitty/mission-<slug>-<mid8>`` is planted before
   a protected ``single_branch`` create (predict-then-plant).
3. ``dirty_checkout_protected_mint``: an untracked ``stray.txt`` under the
   protected mint.
4. ``protected_target_without_commit``: a configured protected target
   (``release``) with no commit.
5. ``invalid_slug``.
6. ``empty_friendly_name``.
7. ``commit_to_target_without_single_branch``.
8. ``unborn_head``.
9. ``detached_head``.
10. ``worktree_context_without_allow_flag``: the process cwd is a real linked
    worktree and ``allow_worktree_context=False``.
11. ``owned_root_mismatch``: ``repo_root`` names a different repository than
    the validated owned checkout's. The other repository's state (porcelain,
    branches, missions, working tree) is captured too, under ``watched``.
12. ``protected_recreate``: a protected ``single_branch`` create re-run into
    its own existing scaffold (predict-then-plant).
13. ``refused_mint_orphan_retry``: cell 3's refused mint leaves no scaffold, so
    the retry after ``stray.txt`` is removed succeeds (#5704).
14. ``malformed_config_invalid_yaml``: ``.kittify/config.yaml`` is not YAML.
15. ``malformed_config_protection_shape``: well-formed YAML whose
    ``protection.protected_branches`` is not a list.
16. ``failed_create_restore/protected_mint``: a real failing ``pre-commit``
    hook makes the scaffold commit fail AFTER the protected mint checked out
    the mission branch, so the rollback (checkout first, then the orphan
    branch) runs (a create invariant).
17. ``failed_create_restore/coord``: the same hook makes the coordination
    creation-events commit fail, so the coordination rollback (Mission dir,
    worktree, branch) runs (a create invariant).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core.mission_creation import MissionCreationResult, create_mission_core
from specify_cli.core.owned_mission import resolve_owned_create_root
from tests._factories import provision_test_charter
from tests.core._mission_create_golden import (
    PRIMARY_BRANCH,
    assert_golden,
    build_repo,
    commit_kittify,
    commit_spec,
    git,
    outcome_of,
    run_cell,
    run_cell_in_one_mid8_bucket,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FAMILY = "refusals"
_PROTECTED = (PRIMARY_BRANCH,)
_STRAY = "stray.txt"


def _create(repo: Path, slug: str, topology: MissionTopology, **kwargs: Any) -> Callable[[], MissionCreationResult]:
    kwargs.setdefault("allow_worktree_context", True)
    return lambda: create_mission_core(repo, slug, topology=topology, **kwargs)


def _protected_main(root: Path) -> Path:
    return build_repo(root, target=PRIMARY_BRANCH, protected=_PROTECTED)


def test_live_duplicate(tmp_path: Path) -> None:
    slug = "ref-live-duplicate"
    repo = build_repo(tmp_path)
    first = create_mission_core(repo, slug, topology=MissionTopology.LANES, allow_worktree_context=True)
    commit_spec(repo, first.feature_dir)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "live_duplicate", observed)


def test_mission_branch_exists(tmp_path: Path) -> None:
    slug = "ref-branch-exists"

    def plant(repo: Path, mid8: str) -> Callable[[], MissionCreationResult]:
        git(repo, "branch", f"kitty/mission-{slug}-{mid8}", PRIMARY_BRANCH)
        return _create(repo, slug, MissionTopology.SINGLE_BRANCH)

    observed = run_cell_in_one_mid8_bucket(tmp_path, _protected_main, plant, slugs=[slug])
    assert_golden(_FAMILY, "mission_branch_exists", observed)


def test_dirty_checkout_protected_mint(tmp_path: Path) -> None:
    slug = "ref-dirty-mint"
    repo = _protected_main(tmp_path)
    (repo / _STRAY).write_text("operator work\n", encoding="utf-8")
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "dirty_checkout_protected_mint", observed)


def test_protected_target_without_commit(tmp_path: Path) -> None:
    slug = "ref-target-no-commit"
    repo = build_repo(tmp_path, protected=(PRIMARY_BRANCH, "release"))
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH, target_branch="release"), slugs=[slug])
    assert_golden(_FAMILY, "protected_target_without_commit", observed)


def test_invalid_slug(tmp_path: Path) -> None:
    slug = "Not_Kebab"
    repo = build_repo(tmp_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "invalid_slug", observed)


def test_empty_friendly_name(tmp_path: Path) -> None:
    slug = "ref-empty-friendly-name"
    repo = build_repo(tmp_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES, friendly_name="   "), slugs=[slug])
    assert_golden(_FAMILY, "empty_friendly_name", observed)


def test_commit_to_target_without_single_branch(tmp_path: Path) -> None:
    slug = "ref-commit-to-target-lanes"
    repo = build_repo(tmp_path)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES, commit_to_target=True), slugs=[slug])
    assert_golden(_FAMILY, "commit_to_target_without_single_branch", observed)


def test_unborn_head(tmp_path: Path) -> None:
    slug = "ref-unborn-head"
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", PRIMARY_BRANCH)
    provision_test_charter(repo)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "unborn_head", observed)


def test_detached_head(tmp_path: Path) -> None:
    slug = "ref-detached-head"
    repo = build_repo(tmp_path)
    git(repo, "checkout", "--detach")
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES), slugs=[slug])
    assert_golden(_FAMILY, "detached_head", observed)


def test_worktree_context_without_allow_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slug = "ref-worktree-context"
    repo = build_repo(tmp_path)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", str(linked), "-b", "linked-topic")
    monkeypatch.chdir(linked)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.LANES, allow_worktree_context=False), slugs=[slug])
    assert_golden(_FAMILY, "worktree_context_without_allow_flag", observed)


def test_owned_root_mismatch(tmp_path: Path) -> None:
    slug = "ref-owned-mismatch"
    repo = build_repo(tmp_path)
    owned_path = tmp_path / "owned"
    git(repo, "worktree", "add", str(owned_path), "-b", "owned-topic")
    owned = resolve_owned_create_root(repo.resolve(), owned_path)
    other = build_repo(tmp_path / "other")
    observed = run_cell(
        repo,
        tmp_path,
        _create(other, slug, MissionTopology.SINGLE_BRANCH, owned_create_root=owned),
        slugs=[slug],
        watch={"other": other},
    )
    assert_golden(_FAMILY, "owned_root_mismatch", observed)


def test_protected_recreate(tmp_path: Path) -> None:
    slug = "ref-protected-recreate"
    kwargs: dict[str, Any] = {"target_branch": PRIMARY_BRANCH}

    def plant(repo: Path, _mid8: str) -> Callable[[], MissionCreationResult]:
        create_mission_core(
            repo,
            slug,
            topology=MissionTopology.SINGLE_BRANCH,
            allow_worktree_context=True,
            allow_duplicate=True,
            **kwargs,
        )
        return _create(repo, slug, MissionTopology.SINGLE_BRANCH, **kwargs)

    observed = run_cell_in_one_mid8_bucket(tmp_path, _protected_main, plant, slugs=[slug])
    assert_golden(_FAMILY, "protected_recreate", observed)


def test_refused_mint_orphan_retry(tmp_path: Path) -> None:
    """#5704: the refused mint leaves no orphan scaffold, so the retry creates the mission."""
    slug = "ref-orphan-retry"
    repo = _protected_main(tmp_path)
    stray = repo / _STRAY
    stray.write_text("operator work\n", encoding="utf-8")
    # The refused mint itself is pinned by cell 3; ``pre`` records that it left no residue.
    outcome_of(_create(repo, slug, MissionTopology.SINGLE_BRANCH))
    stray.unlink()
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "refused_mint_orphan_retry", observed)


def test_malformed_config_invalid_yaml(tmp_path: Path) -> None:
    slug = "ref-malformed-yaml"
    repo = build_repo(tmp_path)
    config = repo / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "\nprotection: [unclosed\n", encoding="utf-8")
    commit_kittify(repo, "chore(fixture): break the config")
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "malformed_config_invalid_yaml", observed)


def test_malformed_config_protection_shape(tmp_path: Path) -> None:
    slug = "ref-malformed-protection"
    repo = build_repo(tmp_path, target=PRIMARY_BRANCH)
    config = repo / ".kittify" / "config.yaml"
    config.write_text(config.read_text(encoding="utf-8") + "\nprotection:\n  protected_branches: main\n", encoding="utf-8")
    commit_kittify(repo, "chore(fixture): wrong-shape protection")
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "malformed_config_protection_shape", observed)


def _install_failing_pre_commit_hook(repo: Path) -> None:
    """A real git hook (no patch): every later ``git commit`` in *repo* fails."""
    hooks = Path(git(repo, "rev-parse", "--git-path", "hooks").strip())
    hook = (hooks if hooks.is_absolute() else repo / hooks) / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text("#!/bin/sh\necho 'golden fixture: commits refused' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)


def test_failed_create_restore_protected_mint(tmp_path: Path) -> None:
    slug = "ref-restore-mint"
    repo = _protected_main(tmp_path)
    _install_failing_pre_commit_hook(repo)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.SINGLE_BRANCH), slugs=[slug])
    assert_golden(_FAMILY, "failed_create_restore/protected_mint", observed)


def test_failed_create_restore_coord(tmp_path: Path) -> None:
    slug = "ref-restore-coord"
    repo = build_repo(tmp_path)
    _install_failing_pre_commit_hook(repo)
    observed = run_cell(repo, tmp_path, _create(repo, slug, MissionTopology.COORD), slugs=[slug])
    assert_golden(_FAMILY, "failed_create_restore/coord", observed)
