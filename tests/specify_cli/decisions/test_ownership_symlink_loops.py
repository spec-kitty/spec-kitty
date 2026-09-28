"""Symlink-loop guard tests for decisions.ownership (#3189, WP03/T011).

CPython 3.11/3.12's non-strict ``Path.resolve()`` raises ``RuntimeError`` when it
encounters a symlink loop, which is not one of ``_mission_dirs``'s or
``_read_ledger``'s ``except OSError`` handlers, so a loop mission directory or
ledger crashed the decision-ownership scan on those interpreters instead of
being classified ABSENT / UNREADABLE like every other kind of unreachable path.
Routing the candidate through ``kernel.resolution.resolve_rejecting_loops``
restores the single, interpreter-invariant verdict the existing ``except
OSError`` handlers already encode.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from specify_cli.decisions.ownership import _mission_dirs, _read_ledger


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_mission_dirs_treats_loop_mission_dir_as_absent(tmp_path: Path) -> None:
    repo_root = tmp_path
    specs_root = repo_root / "kitty-specs"
    specs_root.mkdir()
    loop = specs_root / "001-loop-mission"
    loop.symlink_to(loop)

    normal = specs_root / "002-normal-mission"
    normal.mkdir()

    scan = _mission_dirs(repo_root, None)

    assert all(d.name != "001-loop-mission" for d in scan.mission_dirs)
    assert "001-loop-mission" not in scan.unreadable
    assert normal.resolve() in scan.mission_dirs


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_read_ledger_reports_unreadable_for_loop_ledger(tmp_path: Path) -> None:
    acting_root = tmp_path
    mission_dir = acting_root / "001-mission"
    decisions_dir = mission_dir / "decisions"
    decisions_dir.mkdir(parents=True)
    index_file = decisions_dir / "index.json"
    index_file.symlink_to(index_file)

    result = _read_ledger(mission_dir, acting_root)

    assert result.unreadable is True
    assert result.index is None


def test_read_ledger_reads_normal_mission(tmp_path: Path) -> None:
    acting_root = tmp_path
    mission_dir = acting_root / "001-mission"
    decisions_dir = mission_dir / "decisions"
    decisions_dir.mkdir(parents=True)
    index_file = decisions_dir / "index.json"
    index_file.write_text(json.dumps({"version": 1, "mission_id": "01ABC", "entries": []}), encoding="utf-8")

    result = _read_ledger(mission_dir, acting_root)

    assert result.unreadable is False
