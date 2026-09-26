"""#2478: the 0.13.5 migration reads ``.kittify/meta.json`` via ``load_meta``.

Pins the historical "warn and fall back to both missions" contract for a
malformed project-level meta.json, and that a valid one selects its
``mission_name``. These are characterization tests: the pre-routing inline
read already behaved this way, and the migration runner never reaches
``apply()`` (``detect()`` is False and ``can_apply()`` refuses since WP10).
The mission selection is observed through the "Template not found" warnings,
which rely on the packaged command templates being gone (also WP10).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_0_13_5_add_commit_workflow_to_templates import (
    AddCommitWorkflowToTemplatesMigration,
)

pytestmark = pytest.mark.fast

_FALLBACK_MISSIONS = ("software-dev", "documentation")


def _project(tmp_path: Path, raw: bytes | None) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    if raw is not None:
        (kittify / "meta.json").write_bytes(raw)
    return tmp_path


def _template_warnings(warnings: list[str]) -> set[str]:
    prefix = "Template not found for mission: "
    return {w.removeprefix(prefix) for w in warnings if w.startswith(prefix)}


@pytest.mark.parametrize(
    "raw",
    [b"{invalid json", b"[1, 2]", b"\xff\xfe{"],
    ids=["syntax-error", "non-object", "undecodable"],
)
def test_malformed_meta_warns_and_falls_back(tmp_path: Path, raw: bytes) -> None:
    result = AddCommitWorkflowToTemplatesMigration().apply(_project(tmp_path, raw))

    assert any(w.startswith("Cannot parse meta.json: ") for w in result.warnings)
    assert _template_warnings(result.warnings) == set(_FALLBACK_MISSIONS)
    assert result.errors == []


def test_missing_meta_warns_and_falls_back(tmp_path: Path) -> None:
    result = AddCommitWorkflowToTemplatesMigration().apply(_project(tmp_path, None))

    assert "No meta.json found - cannot determine mission type" in result.warnings
    assert _template_warnings(result.warnings) == set(_FALLBACK_MISSIONS)


def test_valid_meta_selects_its_mission(tmp_path: Path) -> None:
    result = AddCommitWorkflowToTemplatesMigration().apply(_project(tmp_path, b'{"mission_name": "research"}'))

    assert not any(w.startswith("Cannot parse meta.json") for w in result.warnings)
    assert _template_warnings(result.warnings) == {"research"}


def test_meta_vanishing_after_exists_check_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A meta.json removed between exists() and the read keeps the both-missions fallback."""
    from specify_cli.upgrade.migrations import m_0_13_5_add_commit_workflow_to_templates as mod

    monkeypatch.setattr(mod, "load_meta_fail_closed", lambda _dir: None)

    result = AddCommitWorkflowToTemplatesMigration().apply(_project(tmp_path, b'{"mission_name": "research"}'))

    assert any(w.startswith("Cannot parse meta.json: ") for w in result.warnings)
    assert _template_warnings(result.warnings) == set(_FALLBACK_MISSIONS)
