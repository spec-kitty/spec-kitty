"""#5406: the missing-lanes remedy and the coordination rematerialization follow the stored topology.

A ``single_branch`` Mission whose files live only on its minted branch keeps the
``git checkout <branch>`` remedy. A coordination-topology Mission's holder branch is
its coordination branch: it is never checked out in the repository root checkout;
``consolidate`` rematerializes the coordination worktree from it instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.consolidation import entry_preflight
from specify_cli.consolidation.entry_preflight import (
    _require_lanes_json_naming_mission_branch,
    rematerialize_coordination_surface,
)
from specify_cli.coordination import surface_resolver
from specify_cli.lanes.persistence import MissingLanesError

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "remedy-5406-01M75QCY"
_MID8 = "01M75QCY"
_HOLDER = f"kitty/mission-{_SLUG}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _repo(tmp_path: Path, *, topology: str | None, coordination_branch: str | None = _HOLDER, holder: bool = True) -> Path:
    """A repository on ``main`` with the Mission's files committed only on *_HOLDER* (when *holder*)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@x")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "init")
    if not holder:
        return repo
    _git(repo, "checkout", "-qb", _HOLDER)
    mission = repo / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    meta: dict[str, Any] = {"mission_slug": _SLUG, "mission_id": f"{_MID8}AAAAAAAAAAAAAAAAAA", "mid8": _MID8}
    if topology is not None:
        meta["topology"] = topology
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
        meta["mission_branch"] = coordination_branch
    (mission / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (mission / "lanes.json").write_text("{}", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "mission")
    _git(repo, "checkout", "-q", "main")
    return repo


def _remedy(repo: Path) -> str:
    with pytest.raises(MissingLanesError) as info:
        _require_lanes_json_naming_mission_branch(repo, repo / "kitty-specs" / _SLUG)
    return str(info.value)


def _spy_materializer(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake(repo_root: Path, mission_slug: str, **kwargs: Any) -> None:
        calls.append({"repo_root": repo_root, "mission_slug": mission_slug, **kwargs})

    monkeypatch.setattr(surface_resolver, "materialize_coord_surface_for_write", fake)
    return calls


# ---------------------------------------------------------------------------
# T014: the missing-lanes remedy by stored topology
# ---------------------------------------------------------------------------


def test_coordination_holder_remedy_never_says_check_it_out(tmp_path: Path) -> None:
    message = _remedy(_repo(tmp_path, topology="lanes_with_coord"))
    assert "git checkout" not in message
    assert "coordination branch" in message
    assert "rematerializes the coordination worktree" in message
    assert f"fetch or create the local branch {_HOLDER!r}" in message
    assert "re-run `spec-kitty consolidate`" in message


def test_single_branch_holder_remedy_is_unchanged(tmp_path: Path) -> None:
    message = _remedy(_repo(tmp_path, topology="single_branch", coordination_branch=None))
    assert message == (
        f"lanes.json is not on the current checkout, but branch {_HOLDER!r} carries this mission "
        f"(a protected single_branch mission lives on its mission branch). Run `git checkout {_HOLDER}` "
        "and re-run `spec-kitty consolidate` from there."
    )


def test_coordination_topology_naming_another_branch_keeps_the_checkout_remedy(tmp_path: Path) -> None:
    message = _remedy(_repo(tmp_path, topology="lanes_with_coord", coordination_branch="kitty/elsewhere"))
    assert f"Run `git checkout {_HOLDER}`" in message


# ---------------------------------------------------------------------------
# T013: the rematerialization helper
# ---------------------------------------------------------------------------


def test_rematerializes_from_the_coordination_holder_with_explicit_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, topology="lanes_with_coord")
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is True
    assert calls == [{"repo_root": repo, "mission_slug": _SLUG, "coordination_branch": _HOLDER, "mid8": _MID8}]


def test_noop_when_meta_json_is_at_the_seam_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, topology="lanes_with_coord")
    _git(repo, "checkout", "-q", _HOLDER)  # the root checkout now carries meta.json
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is False
    assert calls == []


def test_noop_when_no_branch_holds_the_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, topology=None, holder=False)
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is False
    assert calls == []


@pytest.mark.parametrize("topology", ["single_branch", "lanes", None])
def test_noop_when_the_holder_topology_is_not_a_coordination_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str | None) -> None:
    repo = _repo(tmp_path, topology=topology)
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is False
    assert calls == []


def test_noop_when_the_coordination_branch_is_not_the_holder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, topology="lanes_with_coord", coordination_branch="kitty/elsewhere")
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is False
    assert calls == []


def test_unreadable_holder_meta_is_a_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path, topology="lanes_with_coord")
    _git(repo, "checkout", "-q", _HOLDER)
    (repo / "kitty-specs" / _SLUG / "meta.json").write_text("{not json", encoding="utf-8")
    _git(repo, "commit", "-qam", "corrupt")
    _git(repo, "checkout", "-q", "main")
    calls = _spy_materializer(monkeypatch)
    assert rematerialize_coordination_surface(repo, _SLUG) is False
    assert calls == []


def test_materializer_refusal_exits_without_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path, topology="lanes_with_coord")

    def refuse(repo_root: Path, mission_slug: str, **kwargs: Any) -> None:
        raise surface_resolver.CoordinationWorktreeUnmaterialized.for_mission(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=_MID8,
            coordination_branch=_HOLDER,
            primary_candidate=repo_root / "kitty-specs" / mission_slug,
        )

    monkeypatch.setattr(surface_resolver, "materialize_coord_surface_for_write", refuse)
    monkeypatch.setattr(entry_preflight.console, "width", 400)
    with pytest.raises(typer.Exit) as info:
        rematerialize_coordination_surface(repo, _SLUG)
    assert info.value.exit_code == 1
    out = capsys.readouterr().out
    assert "unmaterialized" in out
    assert _HOLDER in out
    assert "Merge aborted before any state change" in out
