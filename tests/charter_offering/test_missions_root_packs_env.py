"""Regression: both mission-asset resolvers honor SPEC_KITTY_PACKS_ROOT (WP02).

Mission ``resolution-activation-foundation-01KZ9FKG``, WP02, T008. Before this
mission, ``charter.offering.missions.repository.MissionTemplateRepository.default_missions_root``
walked its own ``env_override=None`` sibling search and never consulted
``SPEC_KITTY_PACKS_ROOT`` at all -- only the door,
``kernel.paths.get_package_asset_root``, honored it. A project that set
``SPEC_KITTY_PACKS_ROOT`` to relocate its whole built-in pack (missions
included) therefore got a door that pointed at the relocated tree and a
mission-template repository that silently kept resolving the installed
package's own bundled missions -- two "single sources of truth" for the same
concept, disagreeing under the exact env override the variable exists for.

Contracts (kitty-specs/resolution-activation-foundation-01KZ9FKG/contracts):

* C-R2 -- with ``SPEC_KITTY_PACKS_ROOT=<PACKS_ROOT>`` and
  ``<PACKS_ROOT>/built-in/missions`` present, BOTH
  ``default_missions_root()`` and ``get_package_asset_root()`` resolve under
  ``<PACKS_ROOT>/built-in/missions`` -- the same tree.
* C-R3 -- with BOTH ``SPEC_KITTY_PACKS_ROOT`` and ``SPEC_KITTY_TEMPLATE_ROOT``
  set, ``SPEC_KITTY_PACKS_ROOT`` governs pack-root *location* and wins for it.

This test must fail (RED) against the pre-WP02 code: ``default_missions_root``
ignored ``SPEC_KITTY_PACKS_ROOT`` entirely and would resolve the real
installed/editable-checkout missions tree instead of the tmp-path PACKS_ROOT
below, so the ``result_repository == expected`` assertion in
``test_both_resolvers_relocate_under_packs_root`` fails first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.missions.repository import MissionTemplateRepository
from kernel.paths import get_package_asset_root

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _make_packs_root(tmp_path: Path) -> Path:
    """Create ``<tmp>/packs-root/built-in/missions`` and return the PACKS_ROOT."""
    packs_root = tmp_path / "packs-root"
    (packs_root / "built-in" / "missions").mkdir(parents=True)
    return packs_root


class TestBothResolversRelocateUnderPacksRoot:
    """C-R2: default_missions_root() and get_package_asset_root() agree."""

    def test_both_resolvers_relocate_under_packs_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Both resolvers land on the identical ``<PACKS_ROOT>/built-in/missions`` tree."""
        packs_root = _make_packs_root(tmp_path)
        expected = packs_root / "built-in" / "missions"

        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        result_repository = MissionTemplateRepository.default_missions_root()
        result_door = get_package_asset_root()

        assert result_repository == expected
        assert result_door == expected
        assert result_repository == result_door

    def test_repository_default_missions_root_alone_relocates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Isolated pin: default_missions_root() alone must not ignore PACKS_ROOT.

        Narrower than the paired assertion above -- fails on its own if a
        future regression reintroduces an env-blind ancestor walk in
        ``default_missions_root`` even while the door keeps working.
        """
        packs_root = _make_packs_root(tmp_path)
        expected = packs_root / "built-in" / "missions"

        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        assert MissionTemplateRepository.default_missions_root() == expected


class TestPacksRootWinsOverTemplateRoot:
    """C-R3: with both env vars set, SPEC_KITTY_PACKS_ROOT governs location."""

    def test_both_env_vars_set_packs_root_wins_for_both_resolvers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """PACKS_ROOT wins for pack-root location even with TEMPLATE_ROOT set."""
        packs_root = _make_packs_root(tmp_path)
        expected = packs_root / "built-in" / "missions"

        template_root = tmp_path / "template-root"
        template_templates = template_root / "software-dev" / "templates"
        template_templates.mkdir(parents=True)
        (template_templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(template_root))

        result_repository = MissionTemplateRepository.default_missions_root()
        result_door = get_package_asset_root()

        assert result_repository == expected
        assert result_door == expected
        assert result_repository != template_root
