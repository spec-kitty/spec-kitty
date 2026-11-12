"""The path-convention message frame for a Mission held by a linked worktree (#7602, FR-010).

After settlement a default Mission's PRIMARY partition lives in the coordination worktree
(``.worktrees/<slug>-coord``), so ``accept`` validates ``contracts/`` there. A miss used to be
rendered relative to the project root -- ``.worktrees/<slug>-coord/kitty-specs/<slug>/contracts/`` --
which names the right file in the wrong frame. An artifact-tagged miss is now named relative to the
checkout that holds it (``kitty-specs/<slug>/contracts/``) together with that checkout, because a bare
``kitty-specs/<slug>/contracts/`` read from the repository root checkout would name a different,
untested directory (#3085a). Build paths (``src/``, ``tests/``) keep the project-relative frame.

The end-to-end case (C-007) drives the real ``spec-kitty accept --json --diagnose`` in a subprocess on
a default Mission settled ``lanes_with_coord`` by the real ``finalize-tasks``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.mission import get_mission_for_feature
from specify_cli.validators.paths import validate_mission_paths
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    REPO_ROOT,
    THREE_LANES,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "099-path-frame"
_COORD = f".worktrees/{_SLUG}-coord"


def _repo_with_linked_holder(tmp_path: Path) -> tuple[Path, Path]:
    """A repository whose Mission (without ``contracts/``) is also checked out in a linked worktree.

    Returns ``(project_root, holder)``; ``holder`` is the real ``git worktree add`` checkout.
    """
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", ".")
    git(root, "config", "user.email", "test@test.com")
    git(root, "config", "user.name", "Test")
    git(root, "branch", "-M", "main")
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / ".kittify").mkdir()
    for build_dir in ("src", "tests", "docs"):
        (root / build_dir).mkdir()
        (root / build_dir / ".gitkeep").write_text("", encoding="utf-8")
    mission_dir = root / "kitty-specs" / _SLUG
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "tasks" / ".gitkeep").write_text("", encoding="utf-8")
    meta = {"mission_slug": _SLUG, "slug": _SLUG, "mission_type": "software-dev", "target_branch": "main"}
    (mission_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    holder = root / _COORD
    git(root, "worktree", "add", "-q", "-b", f"kitty/mission-{_SLUG}", str(holder))
    return root, holder


def test_artifact_miss_is_named_relative_to_its_holding_checkout(tmp_path: Path) -> None:
    """FR-010: ``kitty-specs/<slug>/contracts/`` in the holder, never the ``.worktrees/...`` project frame."""
    root, holder = _repo_with_linked_holder(tmp_path)
    feature_dir = holder / "kitty-specs" / _SLUG
    mission = get_mission_for_feature(feature_dir, project_root=root)

    result = validate_mission_paths(mission, root, feature_dir=feature_dir)

    resolved_holder = holder.resolve().as_posix()
    assert result.missing_paths == [f"kitty-specs/{_SLUG}/contracts/"]
    warnings = result.format_warnings()
    assert f"path: kitty-specs/{_SLUG}/contracts/ in checkout {resolved_holder} (not found)" in warnings
    assert f"path: {_COORD}/" not in warnings
    # The remedy names the location actually tested (#3085a): runnable from any directory.
    assert f"mkdir -p {resolved_holder}/kitty-specs/{_SLUG}/contracts/" in result.suggestions
    assert f"mkdir -p {_COORD}/" not in "\n".join(result.suggestions)


def test_mission_in_the_project_root_keeps_its_message(tmp_path: Path) -> None:
    """single_branch control: a Mission under the project root renders exactly as before."""
    root, _holder = _repo_with_linked_holder(tmp_path)
    feature_dir = root / "kitty-specs" / _SLUG
    mission = get_mission_for_feature(feature_dir, project_root=root)

    result = validate_mission_paths(mission, root, feature_dir=feature_dir)

    assert result.missing_paths == [f"kitty-specs/{_SLUG}/contracts/"]
    assert f"path: kitty-specs/{_SLUG}/contracts/ (not found)" in result.format_warnings()
    assert "in checkout" not in result.format_warnings()
    assert result.suggestions == [f"mkdir -p kitty-specs/{_SLUG}/contracts/"]


def test_build_path_miss_keeps_the_project_frame(tmp_path: Path) -> None:
    """Only artifact-tagged misses change: a missing ``src/`` stays project-relative."""
    root, holder = _repo_with_linked_holder(tmp_path)
    (root / "src" / ".gitkeep").unlink()
    (root / "src").rmdir()
    feature_dir = holder / "kitty-specs" / _SLUG
    mission = get_mission_for_feature(feature_dir, project_root=root)

    result = validate_mission_paths(mission, root, feature_dir=feature_dir)

    assert "src/" in result.missing_paths
    assert "path: src/ (not found)" in result.format_warnings()


def _miss_frame(full_path: Path, project_root: Path, relative_path: str, holding_from: Path | None) -> tuple[str, Path | None]:
    from specify_cli.validators import paths

    return paths._miss_frame(full_path, project_root, relative_path, holding_from)


class TestMissFrame:
    """The frame helper: the holding checkout is named only when it is not the project root."""

    def test_holder_frame(self, tmp_path: Path) -> None:
        root, holder = _repo_with_linked_holder(tmp_path)
        full_path = holder / "kitty-specs" / _SLUG / "contracts"

        assert _miss_frame(full_path, root, "contracts/", holder / "kitty-specs" / _SLUG) == (
            f"kitty-specs/{_SLUG}/contracts/",
            holder.resolve(),
        )

    def test_root_frame_when_the_holder_is_the_project_root(self, tmp_path: Path) -> None:
        root, _holder = _repo_with_linked_holder(tmp_path)
        feature_dir = root / "kitty-specs" / _SLUG

        assert _miss_frame(feature_dir / "contracts", root, "contracts/", feature_dir) == (f"kitty-specs/{_SLUG}/contracts/", None)

    def test_build_path_is_never_reframed(self, tmp_path: Path) -> None:
        root, _holder = _repo_with_linked_holder(tmp_path)

        assert _miss_frame(root / "src", root, "src/", None) == ("src/", None)

    def test_outside_every_checkout_falls_back_to_the_absolute_path(self, tmp_path: Path) -> None:
        root, _holder = _repo_with_linked_holder(tmp_path)
        loose = tmp_path / "elsewhere" / "kitty-specs" / _SLUG
        loose.mkdir(parents=True)

        assert _miss_frame(loose / "contracts", root, "contracts/", loose) == (f"{loose / 'contracts'}/", None)


@pytest.fixture
def _isolated_finalize(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    # The in-process ``finalize-tasks`` runs from the source tree and fans out no status event.
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.mark.non_sandbox
@pytest.mark.usefixtures("_isolated_finalize")
def test_accept_on_a_settled_mission_names_contracts_in_the_coordination_checkout(tmp_path: Path) -> None:
    """C-007: the real ``spec-kitty accept`` on a Mission settled ``lanes_with_coord``."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="dev")
    (mission.root_mission_dir / "plan.md").write_text("# Plan\n\nDo it.\n", encoding="utf-8")
    git(mission.root, "add", "kitty-specs")
    git(mission.root, "commit", "-qm", "plan")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert mission.coord_mission_dir.is_dir(), "the Mission did not settle onto a coordination worktree"
    assert not (mission.coord_mission_dir / "contracts").exists()

    env = dict(os.environ)
    env["SPEC_KITTY_NON_INTERACTIVE"] = "1"
    accepted = subprocess.run(
        [sys.executable, "-m", "specify_cli", "accept", "--mission", mission.slug, "--json", "--diagnose"],
        cwd=mission.root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    violations = "\n".join(json.loads(accepted.stdout)["path_violations"])

    holder = mission.coord_mission_dir.parents[1].resolve().as_posix()
    coord_frame = f".worktrees/{mission.slug}-coord/"
    assert f"path: kitty-specs/{mission.slug}/contracts/ in checkout {holder} (not found)" in violations, violations
    assert f"path: {coord_frame}" not in violations
    assert f"mkdir -p {coord_frame}" not in violations
