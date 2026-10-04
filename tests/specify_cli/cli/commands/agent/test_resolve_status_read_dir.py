"""Unit tests for ``_resolve_status_read_dir`` (#5573 tidy-first, T001).

``_resolve_status_read_dir`` is the single coordination-aware recipe for
"where does finalize read this mission's status from", extracted verbatim from
``_execution_has_begun``. It applies no failure policy: resolver errors
propagate and each caller decides. ``_execution_has_begun`` keeps its
fail-open "not begun" answer on exactly those errors.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import mission_runtime
from mission_runtime import MissionArtifactKind, OwnedCheckout
from specify_cli.cli.commands.agent import mission_finalize_planning_pin as planning_pin
from specify_cli.coordination import surface_resolver

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "demo-mission"


class _FakeSeam:
    def __init__(self, read_dir: Path, seen: list[MissionArtifactKind]) -> None:
        self._read_dir = read_dir
        self._seen = seen

    def read_dir(self, kind: MissionArtifactKind) -> Path:
        self._seen.append(kind)
        return self._read_dir


def _fail_surface(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("the non-owned resolver must not run for an owned checkout")


def test_owned_branch_reads_the_placement_seam_status_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seam_dir = tmp_path / "owned" / "status"
    seen_kinds: list[MissionArtifactKind] = []
    seam_calls: list[tuple[Path, str, object]] = []
    owned = cast(OwnedCheckout, SimpleNamespace(repository_root=tmp_path / "owned"))

    def _fake_seam(repository_root: Path, mission_slug: str, *, owned: object) -> _FakeSeam:
        seam_calls.append((repository_root, mission_slug, owned))
        return _FakeSeam(seam_dir, seen_kinds)

    monkeypatch.setattr(mission_runtime, "placement_seam", _fake_seam)
    monkeypatch.setattr(surface_resolver, "resolve_status_surface_with_anchor", _fail_surface)

    result = planning_pin._resolve_status_read_dir(tmp_path, _SLUG, owned=owned)

    assert result == seam_dir
    assert seam_calls == [(tmp_path / "owned", _SLUG, owned)]
    assert seen_kinds == [MissionArtifactKind.STATUS_STATE]


def test_non_owned_branch_returns_the_anchored_surface_read_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    surface_dir = tmp_path / "coord" / "kitty-specs" / _SLUG
    calls: list[tuple[Path, str]] = []

    def _fake_resolve(repo_root: Path, mission_slug: str) -> SimpleNamespace:
        calls.append((repo_root, mission_slug))
        return SimpleNamespace(read_dir=surface_dir)

    monkeypatch.setattr(surface_resolver, "resolve_status_surface_with_anchor", _fake_resolve)

    assert planning_pin._resolve_status_read_dir(tmp_path, _SLUG) == surface_dir
    assert calls == [(tmp_path, _SLUG)]


def _status_read_path_not_found(root: Path) -> Exception:
    error: Exception = surface_resolver.StatusReadPathNotFound(
        repo_root=root,
        mission_slug=_SLUG,
        mid8="01ABCDEF",
        coord_candidate=root / "coord",
        primary_candidate=root / "primary",
    )
    return error


def _coordination_branch_deleted(root: Path) -> Exception:
    error: Exception = surface_resolver.CoordinationBranchDeleted(
        repo_root=root,
        mission_slug=_SLUG,
        mid8="01ABCDEF",
        coordination_branch="kitty/mission-demo-01ABCDEF",
        coord_candidate=root / "coord",
        primary_candidate=root / "primary",
    )
    return error


@pytest.mark.parametrize(
    "make_error",
    [
        lambda _root: FileNotFoundError("no meta.json"),
        lambda _root: ValueError("malformed meta.json"),
        _status_read_path_not_found,
        _coordination_branch_deleted,
    ],
    ids=["file-not-found", "value-error", "status-read-path-not-found", "coordination-branch-deleted"],
)
def test_resolver_errors_propagate_and_execution_has_begun_still_fails_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, make_error: Callable[[Path], Exception]
) -> None:
    error = make_error(tmp_path)

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise error

    monkeypatch.setattr(surface_resolver, "resolve_status_surface_with_anchor", _raise)

    with pytest.raises(type(error)) as excinfo:
        planning_pin._resolve_status_read_dir(tmp_path, _SLUG)
    assert excinfo.value is error

    assert planning_pin._execution_has_begun(tmp_path, _SLUG) is False
