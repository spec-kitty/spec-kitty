"""Keep global asset pruning proportional to the selected tree."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from specify_cli.runtime.asset_preparation import AssetPreparation
from specify_cli.tool_surface.operations import ApplyConsent, OperationRoot


class CountingInventory(dict[str, dict[str, object]]):
    def __init__(self, entries: dict[str, dict[str, object]]) -> None:
        super().__init__(entries)
        self.scans = 0

    def __iter__(self) -> Iterator[str]:
        self.scans += 1
        return super().__iter__()


def test_prune_missing_scans_prior_inventory_once_across_skill_trees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = AssetPreparation(
        "global_skills",
        OperationRoot("global_skills", "global", tmp_path),
        tmp_path / "cache",
        ".agent-skills.lock",
        ApplyConsent(),
    )
    previous = CountingInventory(
        {
            "skills/first/SKILL.md": {},
            "skills/second/SKILL.md": {},
            "skills/unrelated/SKILL.md": {},
        }
    )
    prepared.previous = previous
    prepared.selected.add(tmp_path / "skills/first/SKILL.md")
    retired: list[Path] = []
    monkeypatch.setattr(prepared, "retire", lambda path: retired.append(path))

    prepared.prune_missing(tmp_path / "skills/first")
    prepared.prune_missing(tmp_path / "skills/second")

    assert previous.scans == 1
    assert retired == [tmp_path / "skills/second/SKILL.md"]
