"""Test probe: the current arbiter override for one WP, read off its reduced snapshot.

``specify_cli.review.arbiter.get_arbiter_overrides_for_wp`` was deleted when its last production
caller (``agent tasks status``) moved onto the status read door (#7431, #7335). Tests still need
to observe whether a reduced override exists, so this keeps that read in one place, composed
from the production pieces it always used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from specify_cli.review.arbiter import arbiter_overrides_from_state


def get_arbiter_overrides_for_wp(feature_dir: Path, wp_id: str) -> list[dict[str, Any]]:
    """At most one entry: the complete event-sourced override on *wp_id*'s reduced state."""
    # Looked up on the package at call time, as the deleted helper did, so tests that
    # monkeypatch ``specify_cli.status.wp_snapshot_state`` reach it.
    import specify_cli.status as status

    return arbiter_overrides_from_state(status.wp_snapshot_state(feature_dir, wp_id))
