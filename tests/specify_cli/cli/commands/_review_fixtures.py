"""Shared mission fixtures for the ``spec-kitty review`` CLI test split.

``test_review.py`` (``fast``) and ``test_review_git_baseline.py``
(``integration`` + ``git_repo``) are two halves of one subject. They were split
so the ``fast`` lane keeps its no-subprocess contract — see
``tests/architectural/test_pytest_marker_correctness.py`` Rule 2 and
``docs/context/testing-taxonomy.md`` under "Fast". The fixture builders both
halves need live here rather than being duplicated (and allowed to drift)
across the two modules.

:func:`setup_fixture` is deliberately **pure**: it writes ``meta.json`` and
status events and nothing else. The real ``git`` repository construction that
earns a genuine dead-code diff baseline lives only in the ``git_repo``-marked
module, so a future test added to the ``fast`` half cannot silently acquire a
process spawn by passing a baseline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

if TYPE_CHECKING:
    import typer

MISSION_SLUG = "test-review-mission-01KQTEST0"
MISSION_ID = "01KQTEST000000000000000000"
MISSING_BASELINE = object()


def write_meta(
    feature_dir: Path,
    *,
    baseline_merge_commit: str | None | object = MISSING_BASELINE,
) -> None:
    """Write a minimal meta.json to feature_dir."""
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "friendly_name": "Test Review Mission",
        "mission_type": "software-dev",
        "mission_number": None,
    }
    if baseline_merge_commit is not MISSING_BASELINE:
        meta["baseline_merge_commit"] = baseline_merge_commit
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def seed_wp_event(
    feature_dir: Path,
    wp_id: str,
    to_lane: str,
    event_id: str,
) -> None:
    """Append a single status event taking a WP directly to *to_lane*."""
    from_lane = "planned" if to_lane != "planned" else "planned"
    event = StatusEvent(
        event_id=event_id,
        mission_slug=MISSION_SLUG,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-04-30T12:00:00+00:00",
        actor="test-agent",
        force=False,
        execution_mode="worktree",
    )
    seed_status_event(feature_dir, event)


def build_cli_app() -> typer.Typer:
    """Return a Typer app with the review command as the default command."""
    import typer

    from specify_cli.cli.commands.review import review_mission

    app = typer.Typer()
    # Register as the default (unnamed) command so runner.invoke(app, ["--mission", ...]) works
    app.command()(review_mission)
    return app


def setup_fixture(
    tmp_path: Path,
    wp_lanes: dict[str, str],
    *,
    baseline_merge_commit: str | None | object = MISSING_BASELINE,
) -> tuple[Path, Path]:
    """Create a minimal mission fixture.

    Pure: no git, no subprocess. ``baseline_merge_commit`` is written through to
    ``meta.json`` exactly as given. Callers that need a *real* diff baseline use
    the ``git_repo``-marked module's wrapper, which mints one from a real
    repository before delegating here.

    Returns (repo_root, feature_dir).
    """
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / MISSION_SLUG

    write_meta(feature_dir, baseline_merge_commit=baseline_merge_commit)

    for idx, (wp_id, lane) in enumerate(wp_lanes.items()):
        event_id = f"01KQTEST{idx:018d}"
        seed_wp_event(feature_dir, wp_id, lane, event_id)

    return repo_root, feature_dir


def make_mock_resolved(feature_dir: Path) -> object:
    """Return a minimal ResolvedMission-like object for monkeypatching."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _MockResolved:
        mission_id: str
        mission_slug: str
        feature_dir: Path
        mid8: str

    return _MockResolved(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        feature_dir=feature_dir,
        mid8=MISSION_ID[:8],
    )
