"""Coverage-focused regression tests for CI mission 080 follow-ups."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.consolidation.config import MergeStrategy, load_merge_config
from specify_cli.consolidation.conflict_resolver import _merge_event_logs

pytestmark = pytest.mark.fast


def test_load_merge_config_parses_strategy_from_yaml(tmp_path: Path) -> None:
    """Exercise the ruamel import path used by load_merge_config()."""
    config_dir = tmp_path / ".kittify"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("merge:\n  strategy: merge\n", encoding="utf-8")

    config = load_merge_config(tmp_path)

    assert config.strategy is MergeStrategy.MERGE


def test_merge_event_logs_accepts_mixed_timestamp_types() -> None:
    """Mixed JSON scalar types in `at` must not make sorting crash."""
    ours = json.dumps({"event_id": "evt-1", "at": 1, "lane": "doing"}) + "\n"
    theirs = json.dumps({"event_id": "evt-2", "at": "2", "lane": "done"}) + "\n"

    merged = _merge_event_logs(ours, theirs)
    merged_events = [json.loads(line) for line in merged.splitlines()]

    assert [event["event_id"] for event in merged_events] == ["evt-1", "evt-2"]
