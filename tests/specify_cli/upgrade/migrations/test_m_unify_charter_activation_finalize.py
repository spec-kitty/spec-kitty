"""Scope: B4 borderline (WP08/T023) — the charter-bundle finalizer's legacy-file
retirement must not silently lose a bundle that DIVERGES from an already-present
``charter.yaml`` (NFR-006).

Evidence / decision (ROUTE, not allowlist): in the ``charter_already_present``
branch the migration relocates activation keys but deliberately does NOT re-fold
the legacy bundle into the pre-existing (authoritative) ``charter.yaml`` before
unlinking it — so a bundle whose content is NOT represented in ``charter.yaml``
is content-loss on the raw ``unlink``. This probe seeds exactly that divergence
through the real ``apply()`` entry point and asserts the divergent bytes survive.

RED on base ``32cfc272ee`` (raw ``path.unlink()`` deletes the divergent bundle
with no copy); GREEN once the removal is routed through the asset-preservation
guard with an external ``backup_parent`` (preserve-when-unprovable archives the
bytes verbatim before removal).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
    ConsolidateCharterBundleMigration,
)

pytestmark = pytest.mark.unit

#: Content present ONLY in the legacy bundle, absent from the authoritative
#: charter.yaml — its survival (or loss) is the probe's discriminator.
_DIVERGENT_MARKER = "CUSTOM_DIVERGENT_DIRECTIVE_ONLY_IN_LEGACY_BUNDLE"


def _archived_copies(project: Path, filename: str) -> list[Path]:
    """Every copy of ``filename`` living under a guard ``.backup-*`` archive dir."""
    return [candidate for candidate in project.rglob(filename) if any(part.startswith(".backup-") for part in candidate.parts)]


def test_divergent_legacy_bundle_is_preserved_not_lost_on_finalize(
    tmp_path: Path,
) -> None:
    """A legacy governance.yaml that diverges from an already-present charter.yaml
    is retired from the charter dir but archived verbatim first — never lost."""
    # Arrange
    project = tmp_path / "project"
    charter_dir = project / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)

    # An already-present, authoritative charter.yaml. This migration does NOT
    # re-fold the legacy bundle into it (a hand-authored charter.yaml wins), so
    # its content diverges from the legacy governance.yaml below.
    (charter_dir / "charter.yaml").write_text(
        "governance:\n  selection:\n    directives: []\n",
        encoding="utf-8",
    )
    # Legacy governance.yaml carrying content NOT represented in charter.yaml.
    (charter_dir / "governance.yaml").write_text(
        f"selection:\n  directives:\n    - {_DIVERGENT_MARKER}\n",
        encoding="utf-8",
    )

    # Minimal config.yaml with NO embedded activation, so apply() takes the
    # charter-already-present branch without exercising activation-schema I/O.
    (project / ".kittify" / "config.yaml").write_text("agents: {}\n", encoding="utf-8")

    migration = ConsolidateCharterBundleMigration()

    # Assumption check: the legacy bundle presence is what drives detect().
    assert migration.detect(project) is True

    # Act
    result = migration.apply(project, dry_run=False)

    # Assert
    assert result.success, result.errors
    # The legacy file is retired from the charter dir ...
    assert not (charter_dir / "governance.yaml").exists()
    # ... but its divergent bytes are preserved verbatim, not silently deleted.
    archived = _archived_copies(project, "governance.yaml")
    assert archived, "divergent legacy bundle must be preserved before removal, not lost"
    assert _DIVERGENT_MARKER in archived[0].read_text(encoding="utf-8")


#: Content present ONLY in the legacy directives.yaml bundle — its survival in
#: the composed charter.yaml (not merely the file's existence) is this test's
#: discriminator.
_FOLDED_DIRECTIVE_MARKER = "CUSTOM_FOLDED_DIRECTIVE_MARKER_ONLY_IN_LEGACY_BUNDLE"


def test_fresh_compose_retires_bundle_without_content_loss(
    tmp_path: Path,
) -> None:
    """When charter.yaml does NOT pre-exist, apply() composes it FROM the bundle
    and then retires the legacy files; the folded content actually lives on in
    charter.yaml (read back and checked for a marker seeded only in the legacy
    bundle, not merely asserted to exist), and the legacy files are gone from
    the charter dir."""
    # Arrange
    project = tmp_path / "project"
    charter_dir = project / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "governance.yaml").write_text("selection:\n  directives: []\n", encoding="utf-8")
    (charter_dir / "directives.yaml").write_text(
        "directives:\n"
        "  - id: DIRECTIVE_TEST_MARKER\n"
        f"    title: {_FOLDED_DIRECTIVE_MARKER}\n"
        "    description: seeded only in the legacy bundle\n"
        "    severity: warn\n",
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text(
        "mission: demo\ntemplate_set: software-dev-default\nlanguages: []\nreferences: []\n",
        encoding="utf-8",
    )
    (project / ".kittify" / "config.yaml").write_text("agents: {}\n", encoding="utf-8")

    migration = ConsolidateCharterBundleMigration()

    # Act
    result = migration.apply(project, dry_run=False)

    # Assert
    assert result.success, result.errors
    charter_yaml_path = charter_dir / "charter.yaml"
    assert charter_yaml_path.exists()
    assert not (charter_dir / "governance.yaml").exists()
    assert not (charter_dir / "directives.yaml").exists()
    assert not (charter_dir / "references.yaml").exists()
    # The folded content genuinely lives on -- not just the file's existence.
    composed = charter_yaml_path.read_text(encoding="utf-8")
    assert _FOLDED_DIRECTIVE_MARKER in composed, "the legacy directives.yaml bundle's content was not folded into the composed charter.yaml"
