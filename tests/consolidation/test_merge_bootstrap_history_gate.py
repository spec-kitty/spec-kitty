"""Merge gate: refuse missions whose canonical status log is bootstrap-only.

Regression coverage for issue #1069: a mission whose
``status.events.jsonl`` contains nothing but forced ``planned -> planned``
events cannot be merged, even when WP frontmatter or the dashboard
looks done, because TeamSpace replay would silently collapse every WP
back to planned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import typer

from specify_cli.cli.commands.consolidate import _enforce_canonical_status_history


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n",
        encoding="utf-8",
    )


def test_gate_blocks_bootstrap_only_history(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    log = feature_dir / "status.events.jsonl"
    _write_jsonl(
        log,
        [
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": None,
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
                "mission_slug": "demo-mission",
            },
        ],
    )

    with pytest.raises(typer.Exit):
        _enforce_canonical_status_history(
            feature_dir=feature_dir,
            mission_slug="demo-mission",
            wp_ids=["WP01"],
        )


def test_gate_allows_real_lane_transition(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    log = feature_dir / "status.events.jsonl"
    _write_jsonl(
        log,
        [
            {
                "wp_id": "WP01",
                "from_lane": None,
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
            },
            {
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "claimed",
                "force": False,
                "actor": "claude",
            },
        ],
    )

    # Should NOT raise — real transition present.
    _enforce_canonical_status_history(
        feature_dir=feature_dir,
        mission_slug="demo-mission",
        wp_ids=["WP01"],
    )


def test_gate_blocks_lifecycle_events_plus_bootstrap_only_status(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "demo-mission"
    feature_dir.mkdir(parents=True)
    log = feature_dir / "status.events.jsonl"
    _write_jsonl(
        log,
        [
            {
                "event_id": "lifecycle-1",
                "event_type": "WPCreated",
                "aggregate_id": "WP01",
                "aggregate_type": "WorkPackage",
                "payload": {
                    "mission_slug": "demo-mission",
                    "wp_id": "WP01",
                    "wp_title": "Demo",
                    "depends_on": [],
                    "actor": "finalize-tasks",
                },
            },
            {
                "event_id": "status-1",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
                "mission_slug": "demo-mission",
            },
        ],
    )

    with pytest.raises(typer.Exit):
        _enforce_canonical_status_history(
            feature_dir=feature_dir,
            mission_slug="demo-mission",
            wp_ids=["WP01"],
        )


def test_gate_skips_when_no_wp_ids(tmp_path: Path) -> None:
    """A mission with no WPs has nothing that must have advanced past planned.

    The log is the bootstrap-only one the gate refuses for a mission WITH work
    packages, so only the empty-``wp_ids`` early return keeps this a no-op
    (an absent log would short-circuit on the log-exists guard instead).
    """
    feature_dir = tmp_path / "kitty-specs" / "empty-mission"
    feature_dir.mkdir(parents=True)
    _write_jsonl(
        feature_dir / "status.events.jsonl",
        [
            {
                "event_id": "01H1",
                "wp_id": "WP01",
                "from_lane": None,
                "to_lane": "planned",
                "force": True,
                "actor": "finalize-tasks",
                "mission_slug": "empty-mission",
            },
        ],
    )
    _enforce_canonical_status_history(
        feature_dir=feature_dir,
        mission_slug="empty-mission",
        wp_ids=[],
    )
