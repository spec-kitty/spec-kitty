"""Set-equality guard + end-to-end drift regression (WP05 / T019, T032).

Two independent hand-restated copies of the flat charter activation-key
vocabulary used to drift from the single derived authority
(``charter.activation.pack_manager.ACTIVATION_YAML_KEYS`` -- ``("activated_kinds",
*YAML_KEY_MAP.values())``, itself derived from
``charter.offering.artifact_kinds.CHARTER_KIND_TOKENS``, mission
``doctrine-built-in-seam-consolidation-01KYW3TX`` WP01):

* ``charter.activation.charter_yaml_io._ACTIVATION_KEYS`` (the ``charter.yaml``
  write-section vocabulary), and
* ``specify_cli.upgrade.migrations.m_unify_charter_activation_finalize.
  ACTIVATION_KEYS`` (the finalize migration's relocation vocabulary) -- this
  one was MISSING ``activated_glossary_packs`` (10 vs 11 keys), so the
  finalize migration silently DROPPED an activated glossary pack's
  activation on migration (FR-010 / SC-005 -- a live data-loss drift).

T019 (``test_*_set_equal_to_authority`` / ``test_activated_glossary_packs_
present_in_both_vocabularies``) pins set-equality of BOTH vocabularies
against the single authority so this can never silently re-drift again.

T032 (``test_finalize_migration_carries_activated_glossary_packs_end_to_
end``) goes beyond the key-list proxy and proves the BEHAVIOURAL effect
end-to-end: an activated glossary pack must survive onto the written
``charter.yaml`` when the finalize migration runs over a project fixture
that has one activated pre-migration -- the exact regression the set-equality
guard alone would not catch (a key-list check can pass while the actual
relocation loops still hand-drift independently).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _authority() -> frozenset[str]:
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS

    return frozenset(ACTIVATION_YAML_KEYS)


# ---------------------------------------------------------------------------
# T019 -- set-equality guard
# ---------------------------------------------------------------------------


def test_charter_yaml_io_activation_keys_set_equal_to_authority() -> None:
    """``charter_yaml_io._ACTIVATION_KEYS`` must be set-equal to the authority."""
    from charter.activation.charter_yaml_io import _ACTIVATION_KEYS

    assert frozenset(_ACTIVATION_KEYS) == _authority()


def test_migration_activation_keys_set_equal_to_authority() -> None:
    """The finalize migration's ``ACTIVATION_KEYS`` must be set-equal to the authority.

    This is the guard that would have caught the drift: before T017, this
    migration's ``ACTIVATION_KEYS`` was a 10-key literal missing
    ``activated_glossary_packs`` from the 11-key authority.
    """
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        ACTIVATION_KEYS,
    )

    assert frozenset(ACTIVATION_KEYS) == _authority()


def test_activated_glossary_packs_present_in_both_vocabularies() -> None:
    """The exact drift T017 fixes: ``activated_glossary_packs`` must be in both.

    A narrower, explicit regression on top of the two set-equality tests
    above -- pins the specific key so a future reader immediately sees which
    key previously drifted, without having to diff the full authority set.
    """
    from charter.activation.charter_yaml_io import _ACTIVATION_KEYS
    from charter.activation.compiler import _legacy_activation_keys
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        ACTIVATION_KEYS,
    )

    assert "activated_glossary_packs" in _ACTIVATION_KEYS
    assert "activated_glossary_packs" in ACTIVATION_KEYS
    assert "activated_glossary_packs" in _legacy_activation_keys()


def test_compiler_legacy_activation_keys_set_equal_to_authority() -> None:
    """``compiler._legacy_activation_keys()`` must be set-equal to the authority.

    The third activation-vocabulary copy: the READ off the legacy
    ``config.yaml`` during ``charter.yaml`` bootstrap. Before it was derived,
    it was a 10-key literal missing ``activated_glossary_packs`` -- so a
    pre-WP02 project with an activated glossary pack silently lost it on the
    first charter compile (the same FR-010/SC-005 drift the WRITE-side copies
    already guard against).
    """
    from charter.activation.compiler import _legacy_activation_keys

    assert frozenset(_legacy_activation_keys()) == _authority()


# ---------------------------------------------------------------------------
# T032 -- end-to-end finalize-migration regression for the glossary-pack drift
# ---------------------------------------------------------------------------

_GOVERNANCE_YAML = """\
testing:
  min_coverage: 90
  tdd_required: true
  framework: pytest
  type_checking: mypy --strict
quality:
  linting: ruff
  pr_approvals: 2
  pre_commit_hooks: true
commits:
  convention: conventional
performance:
  cli_timeout_seconds: 2.0
  dashboard_max_wps: 100
branch_strategy:
  main_branch: main
  dev_branch: null
  rules: []
charter:
  selected_paradigms: []
  selected_directives: []
  available_tools:
  - pytest
  - ruff
  template_set: software-dev-default
enforcement: {}
"""

_DIRECTIVES_YAML = "directives: []\n"

_METADATA_YAML = """\
schema_version: 1.0.0
extracted_at: '2026-01-01T00:00:00Z'
charter_hash: sha256:deadbeef
source_path: .kittify/charter/charter.md
extraction_mode: deterministic
sections_parsed:
  structured: 0
  ai_assisted: 0
  skipped: 0
bundle_schema_version: 2
"""

_REFERENCES_YAML = """\
schema_version: 1.0.0
generated_at: '2026-01-01T00:00:00Z'
mission: software-dev
template_set: software-dev-default
languages:
- python
references: []
"""

_CONFIG_YAML_WITH_GLOSSARY_PACK = """\
agents:
  claude: {}
activated_directives: []
activated_glossary_packs:
- spec-kitty-core
"""


def _write_legacy_fixture_with_glossary_pack(project_path: Path) -> None:
    """A legacy project (four bundle files + config) with an activated glossary pack."""
    charter_dir = project_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    (charter_dir / "directives.yaml").write_text(_DIRECTIVES_YAML, encoding="utf-8")
    (charter_dir / "metadata.yaml").write_text(_METADATA_YAML, encoding="utf-8")
    (charter_dir / "references.yaml").write_text(_REFERENCES_YAML, encoding="utf-8")

    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(_CONFIG_YAML_WITH_GLOSSARY_PACK, encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    return yaml.load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_finalize_migration_carries_activated_glossary_packs_end_to_end(
    tmp_path: Path,
) -> None:
    """SC-005 regression: an activated glossary pack SURVIVES the finalize migration.

    Before T017 this would silently drop ``activated_glossary_packs`` --
    ``ACTIVATION_KEYS`` did not include it, so the relocation loop in
    ``_compose_charter_yaml_document`` never copied it onto the composed
    ``charter.yaml``, and ``_rewrite_config`` never stripped it from
    ``config.yaml`` either (a half-migrated, silently-inconsistent state:
    the pack stays "activated" per config.yaml's stale copy while
    charter.yaml -- the new activation authority -- has never heard of it).
    """
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        ConsolidateCharterBundleMigration,
    )

    _write_legacy_fixture_with_glossary_pack(tmp_path)
    migration = ConsolidateCharterBundleMigration()

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    assert result.success, result.errors

    charter_yaml = _load_yaml(tmp_path / ".kittify" / "charter" / "charter.yaml")
    assert charter_yaml["activated_glossary_packs"] == ["spec-kitty-core"], (
        "activated_glossary_packs must survive VERBATIM onto the composed "
        "charter.yaml -- this is the exact drift ACTIVATION_KEYS previously "
        "dropped (10 vs 11 keys)."
    )

    config_data = _load_yaml(tmp_path / ".kittify" / "config.yaml")
    assert "activated_glossary_packs" not in config_data, (
        "activated_glossary_packs must be relocated OFF config.yaml once "
        "folded onto charter.yaml (INV-2)."
    )


def test_finalize_migration_relocates_glossary_pack_onto_existing_charter_yaml(
    tmp_path: Path,
) -> None:
    """Same SC-005 proof on the OTHER migration branch: a pre-existing charter.yaml.

    ``_relocate_activation_onto_existing_charter_yaml`` is a second,
    independent site that iterates the activation-key vocabulary (the fold
    branch used when ``charter.yaml`` is already authoritative) -- it must
    also carry ``activated_glossary_packs`` through, not just the
    from-scratch composition path exercised above.
    """
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        ConsolidateCharterBundleMigration,
    )

    _write_legacy_fixture_with_glossary_pack(tmp_path)
    charter_dir = tmp_path / ".kittify" / "charter"
    hand_authored = (
        "schema_version: '2.0.0'\n"
        "governance:\n"
        "  testing: {}\n"
        "  quality: {}\n"
        "  commits: {}\n"
        "  performance: {}\n"
        "  branch_strategy: {}\n"
        "  doctrine: {}\n"
        "  activations: []\n"
        "  enforcement: {}\n"
        "directives:\n"
        "  directives: []\n"
        "catalog:\n"
        "  mission: software-dev\n"
        "  template_set: software-dev-default\n"
        "  languages: []\n"
        "  references: []\n"
        "metadata:\n"
        "  generated_at: '2026-01-01T00:00:00Z'\n"
        "  bundle_schema_version: 2\n"
    )
    (charter_dir / "charter.yaml").write_text(hand_authored, encoding="utf-8")

    migration = ConsolidateCharterBundleMigration()
    result = migration.apply(tmp_path)
    assert result.success, result.errors

    composed = _load_yaml(charter_dir / "charter.yaml")
    assert composed["activated_glossary_packs"] == ["spec-kitty-core"]
