"""Tests for the run-index absolute-path heal migration (mission
runindex-feature-runs-port, #5390)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.next import run_index
from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_run_index_paths import (
    HealRunIndexPathsMigration,
    describe_leaks,
)

pytestmark = [pytest.mark.fast]


def _write_index(repo: Path, index: dict) -> None:
    path = run_index.feature_runs_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")


def _read_index(repo: Path) -> dict:
    return json.loads(run_index.feature_runs_path(repo).read_text(encoding="utf-8"))


def test_detect_true_for_absolute_and_false_for_relative(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_index(repo, {"01A": {"run_id": "r1", "run_dir": "/orig/.kittify/runtime/runs/r1", "mission_id": "01A"}})
    assert HealRunIndexPathsMigration().detect(repo) is True

    _write_index(repo, {"01A": {"run_id": "r1", "run_dir": ".kittify/runtime/runs/r1", "mission_id": "01A"}})
    assert HealRunIndexPathsMigration().detect(repo) is False


def test_detect_false_when_no_index(tmp_path: Path) -> None:
    assert HealRunIndexPathsMigration().detect(tmp_path / "repo") is False


def test_apply_reanchors_absolute_and_leaves_relative_untouched(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_index(
        repo,
        {
            "01A": {"run_id": "r1", "run_dir": "/original/proj/.kittify/runtime/runs/r1", "mission_id": "01A"},
            "01B": {"run_id": "r2", "run_dir": ".kittify/runtime/runs/r2", "mission_id": "01B"},
        },
    )
    result = HealRunIndexPathsMigration().apply(repo)
    assert result.success
    assert len(result.changes_made) == 1

    healed = _read_index(repo)
    assert healed["01A"]["run_dir"] == ".kittify/runtime/runs/r1"  # re-anchored by run id
    assert healed["01B"]["run_dir"] == ".kittify/runtime/runs/r2"  # untouched
    # other fields preserved
    assert healed["01A"]["run_id"] == "r1" and healed["01A"]["mission_id"] == "01A"


def test_apply_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_index(repo, {"01A": {"run_id": "r1", "run_dir": "/x/.kittify/runtime/runs/r1", "mission_id": "01A"}})
    migration = HealRunIndexPathsMigration()
    migration.apply(repo)
    assert migration.detect(repo) is False
    second = migration.apply(repo)
    assert second.changes_made == []


def test_apply_dry_run_reports_without_writing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_index(repo, {"01A": {"run_id": "r1", "run_dir": "/x/.kittify/runtime/runs/r1", "mission_id": "01A"}})
    before = run_index.feature_runs_path(repo).read_bytes()
    result = HealRunIndexPathsMigration().apply(repo, dry_run=True)
    assert result.changes_made
    assert run_index.feature_runs_path(repo).read_bytes() == before


def test_describe_leaks_matches_detect(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_index(repo, {"01A": {"run_id": "r1", "run_dir": "/x/.kittify/runtime/runs/r1", "mission_id": "01A"}})
    leaks = describe_leaks(repo)
    assert len(leaks) == 1
    assert "01A" in leaks[0] and "absolute" in leaks[0]
    HealRunIndexPathsMigration().apply(repo)
    assert describe_leaks(repo) == []
