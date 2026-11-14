"""Tests for m_3_2_0rc35_kittify_profile_handoff migration."""

from __future__ import annotations

from pathlib import Path


from specify_cli.upgrade.migrations.m_3_2_0rc35_kittify_profile_handoff import (
    KittifyProfileHandoffMigration,
    _HANDOFF_SENTINEL,
    _PROFILE_LOAD_SENTINEL,
    _DO_THIS_FIRST_SENTINEL,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_IMPLEMENT_WITHOUT_HANDOFF = """\
---
title: /spec-kitty.implement
---

# /spec-kitty.implement - Implement Work Package

## 2. Parse WP frontmatter

Extract:
- `agent_profile`
- `role`
- `agent`
- `model`

### 2a. If `agent_profile` is empty, run spec-kitty agent profile list.

## Output

Record your changes.
"""

_REVIEW_WITHOUT_PROFILE_LOAD = """\
---
title: /spec-kitty.review
---

# /spec-kitty.review - Review Work Package

## 2. Parse WP frontmatter

### 3. Review the changes

Apply the review checklist.

## Output

Approve or reject.
"""

_TASK_PROMPT_WITHOUT_DO_THIS_FIRST = """\
---
work_package_id: WP01
title: Example Work Package
dependencies: []
---

# WP01 — Example Work Package

## Objective

Do the work.
"""


def _make_kittify_implement(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".kittify" / "missions" / "software-dev" / "command-templates" / "implement.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_kittify_review(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".kittify" / "missions" / "software-dev" / "command-templates" / "review.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_override_template(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".kittify" / "overrides" / "missions" / "software-dev" / "templates" / "task-prompt-template.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_skill(tmp_path: Path, skill_name: str, content: str) -> Path:
    p = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# T036 tests: migration module behaviour
# ---------------------------------------------------------------------------


def test_inserts_handoff_section_in_implement_when_absent(tmp_path: Path) -> None:
    p = _make_kittify_implement(tmp_path, _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    content = p.read_text(encoding="utf-8")
    assert _HANDOFF_SENTINEL in content


def test_does_not_duplicate_handoff_section_when_present(tmp_path: Path) -> None:
    p = _make_kittify_implement(tmp_path, _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    migration.apply(tmp_path)
    content_after_first = p.read_text(encoding="utf-8")
    migration.apply(tmp_path)
    content_after_second = p.read_text(encoding="utf-8")
    assert content_after_first == content_after_second, "Migration is not idempotent"


def test_inserts_profile_load_section_in_review_when_absent(tmp_path: Path) -> None:
    p = _make_kittify_review(tmp_path, _REVIEW_WITHOUT_PROFILE_LOAD)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    content = p.read_text(encoding="utf-8")
    assert _PROFILE_LOAD_SENTINEL in content


def test_fixes_stale_field_names_in_implement(tmp_path: Path) -> None:
    stale_content = """\
## 2. Parse WP frontmatter

- `profile`
- `tool`

### 2a. If `profile` is empty, skip.

## Output
"""
    p = _make_kittify_implement(tmp_path, stale_content)
    migration = KittifyProfileHandoffMigration()
    migration.apply(tmp_path)
    content = p.read_text(encoding="utf-8")
    assert "- `agent_profile`" in content
    assert "- `agent`" in content
    assert "If `agent_profile` is empty" in content
    assert "- `profile`" not in content
    assert "- `tool`" not in content


def test_updates_skill_implement_skill_md(tmp_path: Path) -> None:
    p = _make_skill(tmp_path, "spec-kitty.implement", _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    content = p.read_text(encoding="utf-8")
    assert _HANDOFF_SENTINEL in content


def test_updates_skill_review_skill_md(tmp_path: Path) -> None:
    p = _make_skill(tmp_path, "spec-kitty.review", _REVIEW_WITHOUT_PROFILE_LOAD)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    content = p.read_text(encoding="utf-8")
    assert _PROFILE_LOAD_SENTINEL in content


def test_updates_task_prompt_template_override(tmp_path: Path) -> None:
    p = _make_override_template(tmp_path, _TASK_PROMPT_WITHOUT_DO_THIS_FIRST)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    content = p.read_text(encoding="utf-8")
    assert _DO_THIS_FIRST_SENTINEL in content
    assert "agent_profile:" in content
    assert "role:" in content


@pytest.mark.parametrize(
    "heading",
    [
        pytest.param("## ⚡ Do This First: Load Agent Profile", id="old-emoji"),
        pytest.param("## Do This First: Load Agent Profile", id="new-ascii"),
    ],
)
def test_does_not_duplicate_profile_load_section_for_old_or_new_template(
    tmp_path: Path, heading: str
) -> None:
    content = _TASK_PROMPT_WITHOUT_DO_THIS_FIRST.replace(
        "dependencies: []",
        'dependencies: []\nagent_profile: "implementer"\nrole: "implementer"',
    ).replace(
        "## Objective",
        f"{heading}\n\nLoad the profile before continuing.\n\n## Objective",
    )
    p = _make_override_template(tmp_path, content)

    result = KittifyProfileHandoffMigration().apply(tmp_path)

    assert result.success is True
    assert result.changes_made == []
    assert p.read_text(encoding="utf-8") == content
    assert content.count("Do This First: Load Agent Profile") == 1


def test_skips_if_kittify_dir_missing(tmp_path: Path) -> None:
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    assert result.errors == []


def test_skips_if_agents_skills_missing(tmp_path: Path) -> None:
    _make_kittify_implement(tmp_path, _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    result = migration.apply(tmp_path)
    assert result.success is True
    assert result.errors == []


# ---------------------------------------------------------------------------
# T037 tests: registry
# ---------------------------------------------------------------------------


def test_migration_is_in_registry() -> None:
    from specify_cli.upgrade.registry import MigrationRegistry
    migration_ids = [m.migration_id for m in MigrationRegistry.get_all()]
    assert "3.2.0rc35_kittify_profile_handoff" in migration_ids


# ---------------------------------------------------------------------------
# T038: detect
# ---------------------------------------------------------------------------


def test_detect_returns_true_when_handoff_missing(tmp_path: Path) -> None:
    _make_kittify_implement(tmp_path, _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    assert migration.detect(tmp_path) is True


def test_detect_returns_false_when_already_applied(tmp_path: Path) -> None:
    _make_kittify_implement(tmp_path, _IMPLEMENT_WITHOUT_HANDOFF)
    migration = KittifyProfileHandoffMigration()
    migration.apply(tmp_path)
    assert migration.detect(tmp_path) is False


def test_detect_returns_false_when_no_files(tmp_path: Path) -> None:
    migration = KittifyProfileHandoffMigration()
    assert migration.detect(tmp_path) is False


def test_inserts_profile_load_section_when_only_an_unrelated_do_this_first_heading_exists(
    tmp_path: Path,
) -> None:
    content = _TASK_PROMPT_WITHOUT_DO_THIS_FIRST.replace(
        "## Objective",
        "## Do This First: Something Else\n\nUnrelated setup.\n\n## Objective",
    )
    p = _make_override_template(tmp_path, content)

    result = KittifyProfileHandoffMigration().apply(tmp_path)

    assert result.success is True
    assert result.changes_made
    assert "Do This First: Load Agent Profile" in p.read_text(encoding="utf-8")
