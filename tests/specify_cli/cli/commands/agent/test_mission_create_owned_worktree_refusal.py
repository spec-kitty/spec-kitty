"""#6956: the create-level owned claim must refuse a registered Mission worktree.

`resolve_owned_create_root` is the one create-level owned-claim minter. Before this
fix it validated only the ownership claim, so `agent mission create --owned-checkout`
admitted a **registered coordination worktree** and a **registered lane worktree**,
scaffolded the Mission inside it, and left the leaf's refusal to arrive afterwards.

These tests drive the real `agent mission create` entry point on real git
repositories (``tmp_path`` + ``git`` subprocesses), the house pattern of
``tests/specify_cli/cli/commands/agent/test_mission_create_phases.py``.

Every refusal is paired, on the same fixture family, with the positive control that
proves the refusal did not simply make the seam reject everything (spec FR-005,
tactic ``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "probe"

#: The registered coordination worktree's directory name. The ``-coord`` suffix and
#: the git worktree registry together are what make a checkout coordination
#: (``classify_worktree_topology``), not the suffix alone.
COORD_DIR = f"{SLUG}-01M6GRFM-coord"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """A provisioned spec-kitty repository root on a non-protected branch."""
    from tests._factories import provision_test_charter

    root = tmp_path / "repository_root"
    root.mkdir()
    (root / ".kittify").mkdir()
    provision_test_charter(root)
    (root / "kitty-specs").mkdir()
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    return root


def _repo_without_charter(tmp_path: Path) -> Path:
    """A bare repository root: the startup selector reads topology, never the charter."""
    root = tmp_path / "repository_root"
    root.mkdir()
    git(root, "init", "-q", "-b", "work")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    return root


def _invoke_create(repo_root: Path, claim: Path, monkeypatch: pytest.MonkeyPatch, slug: str = SLUG) -> object:
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app

    monkeypatch.chdir(repo_root)
    return CliRunner().invoke(app, ["create", slug, "--owned-checkout", str(claim), "--json"])


def _last_payload(output: str) -> dict[str, object]:
    return json.loads(output.strip().splitlines()[-1])


def _scaffolded(checkout: Path, slug: str = SLUG) -> list[str]:
    """The mission directory names this create left in *checkout* (mid8-suffixed)."""
    specs = checkout / "kitty-specs"
    if not specs.is_dir():
        return []
    return sorted(p.name for p in specs.iterdir() if p.name.startswith(slug))


def _coord_worktree(repo_root: Path) -> Path:
    path = repo_root / ".worktrees" / COORD_DIR
    git(repo_root, "worktree", "add", "-q", "-b", "codex/coord", str(path))
    return path


# ---------------------------------------------------------------------------
# T001 — a registered coordination worktree is refused, with the positive control
# ---------------------------------------------------------------------------


def test_create_refuses_a_registered_coordination_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    coord = _coord_worktree(repo_root)
    head_before = git(coord, "rev-parse", "HEAD")

    result = _invoke_create(repo_root, coord, monkeypatch)

    assert result.exit_code == 1, result.output
    payload = _last_payload(result.output)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"  # type: ignore[index]

    # Nothing was scaffolded in the coordination worktree, and it was not mutated.
    assert _scaffolded(coord) == []
    assert git(coord, "status", "--porcelain") == ""
    assert git(coord, "rev-parse", "HEAD") == head_before
    assert _scaffolded(repo_root) == []


def test_create_admits_an_ordinary_linked_owned_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same fixture family as the refusal above: the seam still admits a real owned checkout."""
    repo_root = _repo(tmp_path)
    _coord_worktree(repo_root)
    owned = tmp_path / "owned"
    git(repo_root, "worktree", "add", "-q", "-b", "codex/owned", str(owned))

    result = _invoke_create(repo_root, owned, monkeypatch)

    assert result.exit_code == 0, result.output
    assert len(_scaffolded(owned)) == 1


# ---------------------------------------------------------------------------
# T002 — a registered lane worktree is refused, with the carrier-contract control
# ---------------------------------------------------------------------------


def _register_lane_worktree(repo_root: Path, mission_slug: str) -> Path:
    """Write a one-lane manifest and register the lane worktree it predicts."""
    from specify_cli.lanes.models import ExecutionLane, LanesManifest
    from specify_cli.lanes.persistence import write_lanes_json
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M6GRFM0000000000000000AB",
                "mission_slug": mission_slug,
                "slug": mission_slug,
                "mission_type": "software-dev",
                "topology": "lanes",
                "target_branch": "work",
                "flattened": False,
            }
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        mission_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id="01M6GRFM0000000000000000AB",
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="work",
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
            computed_at="2026-11-03T00:00:00Z",
            computed_from="test",
        ),
    )
    git(repo_root, "add", ".")
    git(repo_root, "commit", "-qm", "lane manifest")

    lane_path, lane_branch = predict_lane_worktree(repo_root, mission_slug, "lane-a")
    git(repo_root, "worktree", "add", "-q", "-b", lane_branch, str(lane_path))
    return lane_path


def test_create_refuses_a_registered_lane_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = _repo(tmp_path)
    lane_path = _register_lane_worktree(repo_root, "existing-mission")

    result = _invoke_create(repo_root, lane_path, monkeypatch)

    assert result.exit_code == 1, result.output
    payload = _last_payload(result.output)
    assert payload["error"]["code"] == "OWNED_CHECKOUT_IS_MISSION_WORKTREE"  # type: ignore[index]
    assert _scaffolded(lane_path) == []


def test_create_admits_a_worktrees_housed_checkout_whose_name_is_not_a_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The carrier-contract trap: classification alone says LANE_WORKTREE for any
    registered non-coord ``.worktrees`` checkout, so a lane leg keyed on the
    classification alone would refuse a legitimate owned checkout."""
    repo_root = _repo(tmp_path)
    _register_lane_worktree(repo_root, "existing-mission")
    owned = repo_root / ".worktrees" / "owned-under-worktrees"
    git(repo_root, "worktree", "add", "-q", "-b", "codex/owned-under-worktrees", str(owned))

    result = _invoke_create(repo_root, owned, monkeypatch)

    assert result.exit_code == 0, result.output
    assert len(_scaffolded(owned)) == 1


# ---------------------------------------------------------------------------
# FR-004 — the read-only startup gate inherits the refusal
# ---------------------------------------------------------------------------


def _selected_startup_checkout(repo_root: Path, claim: Path) -> Path:
    """What the read-only startup gates would consult for this command line."""
    import click
    import typer

    import specify_cli
    from specify_cli.cli.commands._owned_checkout import startup_project_checkout
    from specify_cli.cli.helpers import ROOT_COMMAND_ARGS_META_KEY

    ctx = click.Context(typer.main.get_command(specify_cli.app))
    ctx.meta[ROOT_COMMAND_ARGS_META_KEY] = ("agent", "mission", "create", SLUG, "--owned-checkout", str(claim))
    return startup_project_checkout(ctx, repo_root)


def test_startup_gates_keep_the_repository_root_for_a_mission_worktree(tmp_path: Path) -> None:
    """An invalid claim never redirects the read-only startup gates (#6956 / #6845).

    This needs no charter: it is the selector's own contract, and it is the leg
    a `mission create`-only test cannot see.
    """
    repo_root = _repo_without_charter(tmp_path)
    coord = repo_root / ".worktrees" / COORD_DIR
    git(repo_root, "worktree", "add", "-q", "-b", "codex/coord", str(coord))
    lane_shaped = repo_root / ".worktrees" / "existing-mission-lane-a"
    git(repo_root, "worktree", "add", "-q", "-b", "kitty/mission-existing-mission-lane-a", str(lane_shaped))
    owned = repo_root / ".worktrees" / "owned-under-worktrees"
    git(repo_root, "worktree", "add", "-q", "-b", "codex/owned-uw", str(owned))

    assert _selected_startup_checkout(repo_root, coord) == repo_root.resolve()
    assert _selected_startup_checkout(repo_root, lane_shaped) == repo_root.resolve()
    # Positive control on the same fixture: a legitimate claim still redirects.
    assert _selected_startup_checkout(repo_root, owned) == owned.resolve()
