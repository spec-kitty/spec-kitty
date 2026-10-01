"""FIX 1 regression test — legacy check_version_compatibility no longer blocks.

A project with a stale semver ``spec_kitty.version`` field but a compatible
``spec_kitty.schema_version`` must NOT produce "CLI newer than project" errors.
The compat.planner (schema-version authority) is now the single authority per
C-008; the legacy semver checker is no longer invoked from command handlers.

Concretely this test checks that check_schema_version does NOT raise SystemExit
for a safe command against a project whose metadata.yaml has a very old
spec_kitty.version but a compatible schema.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.migration.gate import check_schema_version


pytestmark = [pytest.mark.integration]

@pytest.fixture()
def fixture_project_old_semver_compat_schema(tmp_path: Path) -> Path:
    """Project with stale spec_kitty.version semver but compatible schema_version."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    # Very old semver (what the legacy checker compared), but schema_version 3 = compatible.
    (kittify / "metadata.yaml").write_text(
        "spec_kitty:\n  version: '0.1.0'\n  schema_version: 3\n",
        encoding="utf-8",
    )
    return tmp_path


def test_doctor_not_blocked_by_old_semver_field(
    fixture_project_old_semver_compat_schema: Path,
) -> None:
    """doctor with old spec_kitty.version but compatible schema_version exits 0.

    Regression: legacy check_version_compatibility compared the semver field and
    could hard-block with 'CLI newer than project' even when schema was compatible.
    After FIX 1 that checker is no longer called from the schema gate.
    """
    # Must not raise SystemExit — the gate should ALLOW this command.
    check_schema_version(
        fixture_project_old_semver_compat_schema,
        invoked_subcommand="doctor",
    )


