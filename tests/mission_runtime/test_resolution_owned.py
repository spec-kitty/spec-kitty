"""owned-checkout-lifecycle-authority WP04 (T016) — owned WP fields, stale copy.

Reproduced O3/O4 through the **pre-existing** entry point
``resolve_action_context`` before any fix (C-007), proving the defect lived in
``_resolve_wp_bearing_fields`` (it called
``locate_work_package(repo_root, mission_slug, normalized_wp_id)`` with no
ownership argument forwarded, even when the caller threaded one all the way
through ``resolve_action_context``), not only in a CLI-level wrapper. WP18
retired the legacy bare-root twins of these tests together with the keyword;
the ``owned=`` versions keep the same names and assertions.

The WP-leg is isolated from the workspace-leg (WP05's surface) via the
``workspace_stub`` fixture: WP05 replaces this stub with the real owned arm of
``resolve_workspace_for_wp``. This file's stub stays here permanently.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_runtime import ActionContextError, OwnedRefusalCode
from mission_runtime.resolution import resolve_action_context
from specify_cli.core.owned_mission import resolve_owned_mission
from specify_cli.task_utils.support import locate_work_package

pytestmark = [pytest.mark.git_repo]

_SLUG = "owned-01M1A900"
_TARGET = "codex/owned"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _wp_frontmatter(wp_id: str, title: str) -> str:
    return (
        f"---\nwork_package_id: {wp_id}\ntitle: {title}\ndependencies: []\n"
        "requirement_refs: []\nsubtasks: []\nowned_files: []\n"
        "authoritative_surface: app.py\nexecution_mode: code_change\n---\n\n# Task\n"
    )


def _write_mission(root: Path, wp_ids: list[str]) -> Path:
    mission = root / "kitty-specs" / _SLUG
    (mission / "tasks").mkdir(parents=True, exist_ok=True)
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M1A900000000000000000001",
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
                "target_branch": _TARGET,
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    for wp_id in wp_ids:
        (mission / "tasks" / f"{wp_id}-task.md").write_text(_wp_frontmatter(wp_id, f"{wp_id} task"), encoding="utf-8")
    return mission


def _owned_repo(tmp_path: Path, *, stale_root_wps: list[str] | None = None) -> tuple[Path, Path]:
    """Build ``R`` (a plain git repo) and ``P`` (a linked worktree of ``R``).

    ``P`` carries the real mission (WP01, WP02); an optional stale copy is
    ALSO written into ``R`` with a different (larger) WP set, so a test can
    assert the seam never reads it.
    """
    r = tmp_path / "R"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "owned-wp04@example.test")
    _git(r, "config", "user.name", "Owned WP04")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "README.md").write_text("seed\n", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")

    p = tmp_path / "P"
    _git(r, "worktree", "add", "-qb", _TARGET, str(p))
    _write_mission(p, ["WP01", "WP02"])
    _git(p, "add", "-A")
    _git(p, "commit", "-qm", "owned mission")

    if stale_root_wps is not None:
        _write_mission(r, stale_root_wps)
        _git(r, "add", "-A")
        _git(r, "commit", "-qm", "stale copy of the mission")

    return r, p


@pytest.fixture
def workspace_stub(monkeypatch: pytest.MonkeyPatch):
    """WP04's shared recording stub — isolates the WP-bearing leg from
    ``resolve_workspace_for_wp`` (WP05's own surface). Stays in this file
    permanently: WP05 cannot edit this WP's test files, and proves the real
    owned workspace leg end-to-end in
    ``tests/specify_cli/workspace/test_owned_workspace_resolution.py``.
    """
    calls: list[tuple[Path, str, str, dict[str, object]]] = []

    def _stub(repo_root: Path, mission_slug: str, wp_id: str, **kwargs: object) -> SimpleNamespace:
        calls.append((repo_root, mission_slug, wp_id, kwargs))
        return SimpleNamespace(
            lane_id=None,
            branch_name=None,
            execution_mode="code_change",
            resolution_kind="stub",
            worktree_path=repo_root,
        )

    monkeypatch.setattr("specify_cli.workspace.context.resolve_workspace_for_wp", _stub)
    return calls


# ===========================================================================
# Owned WP-bearing tests (pre-existing entry point, C-007)
# ===========================================================================


def test_owned_wp_file_under_owned_checkout(tmp_path: Path, workspace_stub: list) -> None:
    """Same as above, minted through the real minter (``owned=``)."""
    r, p = _owned_repo(tmp_path)
    fact = resolve_owned_mission(r, p, _SLUG)

    ctx = resolve_action_context(r, action="implement", feature=_SLUG, wp_id="WP01", owned=fact)

    wp_file = Path(ctx.wp_file)
    assert wp_file.is_relative_to(p)
    assert not wp_file.is_relative_to(r) or r == p
    assert len(workspace_stub) == 1


def test_stale_root_copy_never_wins_wp_file(tmp_path: Path, workspace_stub: list) -> None:
    r, p = _owned_repo(tmp_path, stale_root_wps=["WP01", "WP02", "WP03", "WP04", "WP05"])
    fact = resolve_owned_mission(r, p, _SLUG)

    ctx = resolve_action_context(r, action="implement", feature=_SLUG, wp_id="WP01", owned=fact)

    wp_file = Path(ctx.wp_file)
    assert wp_file.is_relative_to(p)
    assert wp_file.parent.parent == p / "kitty-specs" / _SLUG
    assert not wp_file.is_relative_to(r) or r == p


def test_missing_wp_scoped_to_owned_checkout(tmp_path: Path) -> None:
    r, p = _owned_repo(tmp_path, stale_root_wps=["WP01", "WP02", "WP03", "WP04", "WP05"])
    fact = resolve_owned_mission(r, p, _SLUG)

    with pytest.raises(ActionContextError) as excinfo:
        resolve_action_context(r, action="implement", feature=_SLUG, wp_id="WP05", owned=fact)
    assert excinfo.value.code == OwnedRefusalCode.WORK_PACKAGE_UNRESOLVED
    message = str(excinfo.value)
    assert str(r) not in message
    assert str(p) in message


# ===========================================================================
# Mission-level ratchets (already green on base; must stay green)
# ===========================================================================


def test_tasks_outline_feature_dir_under_owned_checkout_ratchet(tmp_path: Path) -> None:
    r, p = _owned_repo(tmp_path, stale_root_wps=["WP01"])
    fact = resolve_owned_mission(r, p, _SLUG)

    ctx = resolve_action_context(r, action="tasks_outline", feature=_SLUG, owned=fact)

    assert Path(ctx.feature_dir).is_relative_to(p)


# ===========================================================================
# T020 — locate_work_package(owned=) directly
# ===========================================================================


def test_locate_owned_missing_wp_names_owned_dir(tmp_path: Path) -> None:
    """The ``TaskCliError`` for a WP absent from P names P's resolved tasks
    root, not merely the display-facing ``kitty-specs/<slug>/tasks`` shorthand."""
    from specify_cli.task_utils.support import TaskCliError

    r, p = _owned_repo(tmp_path, stale_root_wps=["WP01", "WP05"])
    fact = resolve_owned_mission(r, p, _SLUG)

    with pytest.raises(TaskCliError) as excinfo:
        locate_work_package(r, _SLUG, "WP05", owned=fact)
    message = str(excinfo.value)
    assert str(p) in message
    assert str(r) not in message


def test_placement_seam_refuses_mismatched_slug(tmp_path: Path) -> None:
    from mission_runtime import placement_seam

    r, p = _owned_repo(tmp_path)
    fact = resolve_owned_mission(r, p, _SLUG)
    with pytest.raises(ActionContextError) as excinfo:
        placement_seam(r, "some-other-mission-slug", owned=fact)
    assert excinfo.value.code == "FEATURE_CONTEXT_UNRESOLVED"


# ===========================================================================
# F4 (review cycle 1) — the owned= happy path over slug, mid8 and mission id.
# ===========================================================================


@pytest.mark.parametrize("handle_kind", ["slug", "mid8", "mission_id"])
def test_owned_kw_accepts_slug_mid8_and_mission_id_handles(tmp_path: Path, workspace_stub: list, handle_kind: str) -> None:
    """T016 edge case: the fact is minted once (against the real slug); the
    *call* to ``resolve_action_context`` may then use any of the three
    canonical handle forms and must resolve the identical WP file."""
    r, p = _owned_repo(tmp_path)
    fact = resolve_owned_mission(r, p, _SLUG)
    handle = {"slug": _SLUG, "mid8": "01M1A900", "mission_id": "01M1A900000000000000000001"}[handle_kind]

    ctx = resolve_action_context(r, action="implement", feature=handle, wp_id="WP01", owned=fact)

    wp_file = Path(ctx.wp_file)
    assert wp_file.is_relative_to(p)
    assert wp_file.parent.parent == p / "kitty-specs" / _SLUG


# ===========================================================================
# R1 (review cycle 2) — zero-fold pins for locate_work_package and
# resolve_action_context, with a real WP-bearing owned checkout.
# ===========================================================================


def _patch_zero_fold_spies(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(name: str):
        def _raise(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(f"{name} must not be called on the owned arm (R1)")

        return _raise

    monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _boom("get_main_repo_root"))
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.candidate_feature_dir_for_mission",
        _boom("candidate_feature_dir_for_mission"),
    )
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
        _boom("resolve_handle_to_read_path"),
    )


def test_locate_work_package_owned_is_zero_fold_found_and_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1: ``locate_work_package(owned=)`` makes zero folds/walks whether the
    WP is found or missing."""
    r, p = _owned_repo(tmp_path, stale_root_wps=["WP01", "WP05"])
    fact = resolve_owned_mission(r, p, _SLUG)
    _patch_zero_fold_spies(monkeypatch)

    wp = locate_work_package(r, _SLUG, "WP01", owned=fact)
    assert Path(wp.path).is_relative_to(p)

    from specify_cli.task_utils.support import TaskCliError

    with pytest.raises(TaskCliError):
        locate_work_package(r, _SLUG, "WP05", owned=fact)


def test_resolve_action_context_owned_is_zero_fold_implement_and_tasks_outline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, workspace_stub: list) -> None:
    """R1: ``resolve_action_context(owned=)`` makes zero folds/walks for both
    a WP-bearing action (implement, with a mid8 handle) and a mission-level
    action (tasks_outline)."""
    r, p = _owned_repo(tmp_path)
    fact = resolve_owned_mission(r, p, _SLUG)
    _patch_zero_fold_spies(monkeypatch)

    ctx = resolve_action_context(r, action="implement", feature="01M1A900", wp_id="WP01", owned=fact)
    assert Path(ctx.wp_file).is_relative_to(p)

    ctx2 = resolve_action_context(r, action="tasks_outline", feature=_SLUG, owned=fact)
    assert Path(ctx2.feature_dir).is_relative_to(p)
