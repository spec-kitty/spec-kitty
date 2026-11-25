"""A squash-landed ``lanes_with_coord`` Mission with its lane still in place (#7747, #7848).

Shared scaffolding of the lane landing proof tests: real repositories, no CLI. The ``landed``
fixture is registered in ``tests/lanes/conftest.py``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from specify_cli.lanes.lane_tip import is_absorbed_but_for_mission_bookkeeping

_SLUG = "demo-01ABCDEF"
_OTHER_SLUG = "other-01ABCDEF"
_MD = f"kitty-specs/{_SLUG}"
_COORD = f"kitty/mission-{_SLUG}"
_LANE = f"kitty/mission-{_SLUG}-lane-a"
_TARGET = "refs/heads/main"
_SPEC = f"{_MD}/spec.md"
_META = f"{_MD}/meta.json"
_SNAPSHOT = f"{_MD}/status.json"
_LOG = f"{_MD}/status.events.jsonl"
_WP01 = f"{_MD}/tasks/WP01-work.md"
_WP02 = f"{_MD}/tasks/WP02-work.md"
_RETRO = f"{_MD}/retrospective.yaml"
_PRODUCT = "src/lane.py"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _write(cwd: Path, files: dict[str, str | None]) -> None:
    for rel, text in files.items():
        path = cwd / rel
        if text is None:
            _git(cwd, "rm", "-q", rel)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        _git(cwd, "add", rel)


def _commit(cwd: Path, message: str, files: dict[str, str | None]) -> str:
    _write(cwd, files)
    _git(cwd, "commit", "-q", "-m", message)
    return _git(cwd, "rev-parse", "HEAD")


def _wp(wp: str, body: str, **front: str) -> str:
    fields = "".join(f"{key}: {value}\n" for key, value in front.items())
    return f"---\nwork_package_id: {wp}\n{fields}---\n# {wp}\n\n{body}\n"


def _log(*event_ids: str) -> str:
    return "".join(f'{{"event_id": "{event_id}"}}\n' for event_id in event_ids)


@dataclass(frozen=True)
class Landed:
    """A squash-landed ``lanes_with_coord`` Mission whose lane is still in place."""

    root: Path
    coord: Path
    lane: Path

    def tip(self) -> str:
        return _git(self.lane, "rev-parse", "HEAD")

    def proof(self, slug: str = _SLUG) -> bool:
        proven: bool = is_absorbed_but_for_mission_bookkeeping(self.root, self.tip(), _TARGET, slug)
        return proven


def _init(root: Path) -> None:
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(root, "init", {".gitignore": ".worktrees/\n", "README.md": "base\n"})


def _land(root: Path, coord: Path, lane: Path) -> None:
    """The squash landing: coordination tip + lane product, then the post-landing bookkeeping."""
    _git(root, "checkout", "-q", _COORD, "--", "kitty-specs")
    _git(root, "checkout", "-q", _LANE, "--", _PRODUCT)
    _git(root, "commit", "-q", "-m", "squash merge of mission")
    _commit(
        root,
        "record done transitions",
        {
            _META: '{"v": 4, "merged_at": "now"}\n',
            _SNAPSHOT: '{"v": 4}\n',
            _LOG: _log("e1", "e2", "e3", "e4"),
            _RETRO: "retro: true\n",
        },
    )


def make_landed(tmp_path: Path) -> Landed:
    """Coordination branch, a lane that synced with it once and committed its product, a squash landing."""
    root = tmp_path / "repo"
    _init(root)
    coord = root / ".worktrees" / "coord"
    _git(root, "worktree", "add", "-q", "-b", _COORD, str(coord))
    _commit(
        coord,
        "tasks",
        {
            _SPEC: "# spec\n",
            _META: '{"v": 1}\n',
            _SNAPSHOT: '{"v": 1}\n',
            _LOG: _log("e1"),
            _WP01: _wp("WP01", "Do the work."),
            _WP02: _wp("WP02", "Do the other work."),
        },
    )
    lane = root / ".worktrees" / "lane-a"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane), _COORD)
    _commit(
        coord,
        "WP01 claimed",
        {_META: '{"v": 2}\n', _SNAPSHOT: '{"v": 2}\n', _LOG: _log("e1", "e2"), _WP01: _wp("WP01", "Do the work.", agent="claude")},
    )
    _git(lane, "merge", "-q", "--no-ff", "--no-edit", _COORD)  # the implement sync
    _commit(lane, "feat(WP01)", {_PRODUCT: "x = 1\n"})
    _commit(
        coord,
        "WP02 claimed",
        {_META: '{"v": 3}\n', _SNAPSHOT: '{"v": 3}\n', _LOG: _log("e1", "e2", "e3"), _WP02: _wp("WP02", "Do the other work.", agent="claude")},
    )
    _land(root, coord, lane)
    return Landed(root=root, coord=coord, lane=lane)


__all__ = [
    "_COORD",
    "_LANE",
    "_LOG",
    "_MD",
    "_META",
    "_OTHER_SLUG",
    "_PRODUCT",
    "_RETRO",
    "_SLUG",
    "_SNAPSHOT",
    "_SPEC",
    "_TARGET",
    "_WP01",
    "_WP02",
    "Landed",
    "_commit",
    "_git",
    "_init",
    "_land",
    "_log",
    "_wp",
    "_write",
    "make_landed",
]
