"""WP04 T023 integration — strict-policy skip with empty reason rejected.

Verifies the ``emit_skipped`` contract: empty skip_reason MUST raise
ValueError per the RetrospectiveSkipped invariant.

T020: ``--skip-retrospective=""`` (empty reason) is rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod


def _scaffold_minimal_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str]:
    """Create a minimal mission directory."""
    mission_id = str(_ulid_mod.ULID())
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
        }),
        encoding="utf-8",
    )
    return feature_dir, mission_id


@pytest.mark.integration
def test_emit_skipped_rejects_empty_reason(tmp_path: Path) -> None:
    """emit_skipped raises ValueError when skip_reason is empty string."""
    from specify_cli.retrospective.lifecycle_events import emit_skipped, Actor
    from specify_cli.retrospective.policy import resolve_policy

    mission_slug = "skip-empty-reason-01KQ"
    _feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    _policy, source_map = resolve_policy(tmp_path)
    actor = Actor(kind="human", id="operator@example.com")

    with pytest.raises(ValueError, match="skip_reason MUST be non-empty"):
        emit_skipped(
            mission_id=mission_id,
            mission_slug=mission_slug,
            repo_root=tmp_path,
            skip_reason="",  # empty — must be rejected
            skip_reason_source="cli_flag",
            policy_source=source_map,
            actor=actor,
        )


@pytest.mark.integration
def test_emit_skipped_rejects_whitespace_only_reason(tmp_path: Path) -> None:
    """emit_skipped raises ValueError when skip_reason is whitespace only."""
    from specify_cli.retrospective.lifecycle_events import emit_skipped, Actor
    from specify_cli.retrospective.policy import resolve_policy

    mission_slug = "skip-whitespace-reason-01KQ"
    _feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    _policy, source_map = resolve_policy(tmp_path)
    actor = Actor(kind="human", id="operator@example.com")

    with pytest.raises(ValueError, match="skip_reason MUST be non-empty"):
        emit_skipped(
            mission_id=mission_id,
            mission_slug=mission_slug,
            repo_root=tmp_path,
            skip_reason="   ",  # whitespace only — must be rejected
            skip_reason_source="cli_flag",
            policy_source=source_map,
            actor=actor,
        )
