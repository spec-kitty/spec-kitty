"""Tests for specify_cli.skills.vibe_config's read-side skill-path check.

Covers ``skill_path_configured`` (#4433): the ``.vibe/config.toml``
``skill_paths`` pointer is an independently missable part of the vibe
command surface, and both ``init``'s initialized-project check and
``doctor skills`` read it through this one seam.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.skills.vibe_config import skill_path_configured

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_missing_config_is_not_configured(tmp_path: Path) -> None:
    assert skill_path_configured(tmp_path) is False


def test_missing_skill_paths_entry_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text('model = "mistral"\n', encoding="utf-8")

    assert skill_path_configured(tmp_path) is False


def test_matching_string_pointer_is_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text('skill_paths = ".agents/skills"\n', encoding="utf-8")

    assert skill_path_configured(tmp_path) is True


def test_pointer_listing_shared_root_is_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text('skill_paths = [".vibe/skills", ".agents/skills"]\n', encoding="utf-8")

    assert skill_path_configured(tmp_path) is True


def test_pointer_without_shared_root_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text('skill_paths = [".vibe/skills"]\n', encoding="utf-8")

    assert skill_path_configured(tmp_path) is False


def test_wrong_typed_pointer_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text("skill_paths = 3\n", encoding="utf-8")

    assert skill_path_configured(tmp_path) is False


def test_unreadable_config_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text("skill_paths = [unterminated\n", encoding="utf-8")

    assert skill_path_configured(tmp_path) is False


def test_empty_config_is_not_configured(tmp_path: Path) -> None:
    config = tmp_path / ".vibe" / "config.toml"
    config.parent.mkdir()
    config.write_text("", encoding="utf-8")

    assert skill_path_configured(tmp_path) is False
