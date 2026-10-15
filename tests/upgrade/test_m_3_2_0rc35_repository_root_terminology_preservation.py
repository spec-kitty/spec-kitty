"""#6247 fold: the repository-root terminology migration preserves user commands.

``m_3_2_0rc35_repository_root_checkout_terminology`` rewrites stale wording in
generated ``spec-kitty.*.md`` command files in place. A ``spec-kitty.*`` name
plus a matched phrase is not proof of package ownership, so a user-authored
custom command that merely mentions e.g. "main repo" must NOT have its bytes
rewritten (charter "User Customization Preservation"). Only a file whose version
marker proves it is package-generated is updated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_2_0rc35_repository_root_checkout_terminology import (
    RepositoryRootCheckoutTerminologyMigration,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MARKER = "<!-- spec-kitty-command-version: 2.1.0 -->\n"
_STALE_PHRASE = "Planning happens in the main repository root for all missions.\n"


def _project(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text("agents:\n  available:\n  - claude\n", encoding="utf-8")
    cmd = tmp_path / ".claude" / "commands"
    cmd.mkdir(parents=True, exist_ok=True)
    return cmd


def test_generated_file_with_marker_is_updated(tmp_path: Path) -> None:
    cmd = _project(tmp_path)
    generated = cmd / "spec-kitty.specify.md"
    generated.write_text(_MARKER + _STALE_PHRASE, encoding="utf-8")

    result = RepositoryRootCheckoutTerminologyMigration().apply(tmp_path)

    assert result.success
    updated = generated.read_text(encoding="utf-8")
    assert "main repository root" not in updated, "stale terminology must be rewritten in a generated file"
    assert "repository root checkout" in updated
    assert any("spec-kitty.specify.md" in p for p in result.changes_made)


def test_unmarked_user_command_is_preserved(tmp_path: Path) -> None:
    cmd = _project(tmp_path)
    custom = cmd / "spec-kitty.custom.md"
    body = "# my own command\nI run things in the main repo by hand.\n"  # mentions a matched phrase, no marker
    custom.write_text(body, encoding="utf-8")

    result = RepositoryRootCheckoutTerminologyMigration().apply(tmp_path)

    assert result.success
    assert custom.read_text(encoding="utf-8") == body, "a user-authored command's bytes must not be rewritten"
    assert any("spec-kitty.custom.md" in p for p in result.preserved_paths)
    assert not any("spec-kitty.custom.md" in p for p in result.changes_made)
