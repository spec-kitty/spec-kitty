"""A git-aware ``kitty-specs/`` fixture for the walker tests of issue #6758.

Every walker covered by that issue must list a selectable Mission and skip a
read-side residue child (a child that
:func:`specify_cli.context.mission_resolver.is_selectable_mission_dir` rejects)
while reading exactly the same directory tree. Both children therefore live on
one fixture, seeded once and committed, so a test's absence assertion and its
positive control cannot drift apart.

Two shapes are seeded:

``seed_mission_and_residue``
    One Mission (``meta.json`` with a ``mission_id``) and one residue child (no
    ``meta.json``). Both carry an accepted ``WP01`` task file and an in-flight
    ``WP02`` status event, so a walker that inspects tasks or the event log —
    not just the directory name — still has something to report for either
    child. The Mission needs no git call (rule 2 of the predicate); the residue
    child is rejected before one (rule 1).

``seed_tracked_idless_missions``
    Several id-less Missions whose ``meta.json`` is git-tracked. They are
    selectable only through the git rule, so a walk over them exercises the
    per-walk ``TrackedMissionPaths`` memo (one ``git ls-files`` at most) and
    proves the routing does not hide legacy Missions.

The repository is a real one (``git init`` + commit) because file-presence mode
would call a ``meta.json``-less child a Mission; see ``is_kitty_specs_residue``
and ``is_selectable_mission_dir`` docstrings for the two modes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.context import mission_resolver
from specify_cli.status.models import Lane, StatusEvent

from tests._support.activation_cli import git, init_git_repo
from tests._support.status_seed import seed_status_event

__all__ = [
    "MISSION_ID",
    "MISSION_SLUG",
    "RESIDUE_SLUG",
    "ResidueFixture",
    "seed_mission_and_residue",
    "seed_tracked_idless_missions",
    "spy_on_tracked_paths",
]

#: The one Mission's slug and identity.
MISSION_SLUG = "001-real-mission"
MISSION_ID = "01M5Z6N5JQ1MA9ACTFX7XHWGW6"
#: The read-side residue child: a leftover folder holding a spec and tasks, no ``meta.json``.
RESIDUE_SLUG = "leftover-spec-only"

_ACCEPTED_WP = """\
---
work_package_id: WP01
title: Accepted work package
status: done
---

## WP01 — Accepted work package
"""
_INFLIGHT_WP = "WP02"


@dataclass(frozen=True)
class ResidueFixture:
    """The seeded tree: one selectable Mission beside one residue child."""

    repo_root: Path
    mission_dir: Path
    residue_dir: Path


def seed_mission_and_residue(repo_root: Path) -> ResidueFixture:
    """Seed one Mission and one residue child in *repo_root*, committed to git.

    Both children carry the same artefacts apart from ``meta.json``, so a walker
    that decides on file presence rather than on the Mission predicate reports
    both, and a walker that asks the predicate reports only the Mission.
    """
    init_git_repo(repo_root)
    specs = repo_root / "kitty-specs"
    mission_dir = _seed_child(specs, MISSION_SLUG, meta=_mission_meta())
    residue_dir = _seed_child(specs, RESIDUE_SLUG, meta=None)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "seed a Mission and a residue child")
    return ResidueFixture(repo_root=repo_root, mission_dir=mission_dir, residue_dir=residue_dir)


def seed_tracked_idless_missions(repo_root: Path, slugs: tuple[str, ...] = ("010-legacy-a", "011-legacy-b")) -> tuple[Path, ...]:
    """Seed id-less Missions whose ``meta.json`` git tracks, and commit them.

    They are selectable only through the git rule, so walking them proves the
    memo probes git once for the whole walk and that no legacy Mission is hidden.
    """
    init_git_repo(repo_root)
    specs = repo_root / "kitty-specs"
    children = tuple(_seed_child(specs, slug, meta={"mission_slug": slug, "mission_type": "software-dev"}) for slug in slugs)
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "seed tracked id-less Missions")
    return children


def spy_on_tracked_paths(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every ``git ls-files`` probe ``tracked_mission_paths`` makes, keyed by repo root.

    The walkers' per-walk :class:`~specify_cli.context.mission_resolver.TrackedMissionPaths`
    memo calls this module-level function, so patching it counts the probes a single walk
    performs without mocking git itself (NFR-001).
    """
    calls: list[Path] = []
    real = mission_resolver.tracked_paths

    def _counting(cwd: Path, **kwargs: object) -> tuple[str, ...]:
        calls.append(cwd)
        return real(cwd, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(mission_resolver, "tracked_paths", _counting)
    return calls


def _mission_meta() -> dict[str, object]:
    return {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "friendly_name": "Real Mission",
        "created_at": "2026-01-01T00:00:00+00:00",
        "topology": "single_branch",
    }


def _seed_child(specs: Path, slug: str, *, meta: dict[str, object] | None) -> Path:
    child = specs / slug
    tasks = child / "tasks"
    tasks.mkdir(parents=True)
    if meta is not None:
        (child / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (child / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    (tasks / "WP01-accepted.md").write_text(_ACCEPTED_WP, encoding="utf-8")
    seed_status_event(child, _inflight_event(slug))
    return child


def _inflight_event(slug: str) -> StatusEvent:
    return StatusEvent(
        event_id=f"evt-{slug}-wp02",
        mission_slug=slug,
        wp_id=_INFLIGHT_WP,
        from_lane=Lane.PLANNED,
        to_lane=Lane.IN_PROGRESS,
        at="2026-01-01T00:00:01+00:00",
        actor="fixture",
        force=False,
        execution_mode="worktree",
    )
