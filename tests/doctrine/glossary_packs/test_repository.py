"""Unit tests for GlossaryPackRepository (T008/T010, FR-004, FR-005, C-004)."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.base import BaseDoctrineRepository
from charter.offering.glossary_packs.repository import GlossaryPackRepository
from charter.offering.service import DoctrineService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


class TestGlossaryPackRepository:
    def test_inherits_base_doctrine_repository(self) -> None:
        """The reviewer-called-out invariant: no re-implemented glob/merge logic."""
        assert issubclass(GlossaryPackRepository, BaseDoctrineRepository)

    def test_list_all_from_shipped(self, tmp_glossary_pack_dir: Path) -> None:
        repo = GlossaryPackRepository(built_in_dir=tmp_glossary_pack_dir)
        packs = repo.list_all()
        assert {p.id for p in packs} == {"spec-kitty-core"}

    def test_get_by_id(self, tmp_glossary_pack_dir: Path) -> None:
        repo = GlossaryPackRepository(built_in_dir=tmp_glossary_pack_dir)
        pack = repo.get("spec-kitty-core")
        assert pack is not None
        assert len(pack.terms) == 2

    def test_get_returns_none_for_unknown(self, tmp_glossary_pack_dir: Path) -> None:
        repo = GlossaryPackRepository(built_in_dir=tmp_glossary_pack_dir)
        assert repo.get("nonexistent-pack") is None

    def test_enforcement_fields_round_trip_unchanged(
        self, tmp_glossary_pack_dir: Path, full_term_data: dict
    ) -> None:
        """aliases/banned_synonyms survive a full load→get cycle unchanged.

        Forward-compat for Mission B (C-004): the fields are carried but no
        gate consumes them in Mission A.
        """
        repo = GlossaryPackRepository(built_in_dir=tmp_glossary_pack_dir)
        pack = repo.get("spec-kitty-core")
        assert pack is not None

        term = next(t for t in pack.terms if t.surface == full_term_data["surface"])
        assert term.aliases == full_term_data["aliases"]
        assert term.banned_synonyms == full_term_data["banned_synonyms"]

    def test_duplicate_surface_pack_raises_on_load(self, tmp_path: Path) -> None:
        """A synthetic pack with two identical surfaces fails validation on load.

        The real seed has no duplicates, so this uses a synthetic fixture per
        the task instructions.
        """
        pack_dir = tmp_path / "glossary_packs"
        pack_dir.mkdir()

        duplicate_term = {
            "surface": "work package",
            "definition": "A unit of implementable work.",
            "confidence": 0.9,
            "status": "active",
        }
        data = {
            "id": "dup-pack",
            "provenance": "built-in",
            "terms": [duplicate_term, dict(duplicate_term)],
        }

        yaml = YAML()
        yaml.default_flow_style = False
        with (pack_dir / "dup-pack.glossary-pack.yaml").open("w") as f:
            yaml.dump(data, f)

        with pytest.warns(UserWarning, match="Skipping invalid built-in"):
            repo = GlossaryPackRepository(built_in_dir=pack_dir)

        assert repo.get("dup-pack") is None

    def test_malformed_yaml_skipped_with_warning(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        bad_file = shipped / "bad.glossary-pack.yaml"
        bad_file.write_text("not: valid: yaml: [")

        with pytest.warns(UserWarning, match="Skipping invalid"):
            repo = GlossaryPackRepository(built_in_dir=shipped)

        assert repo.list_all() == []

    def test_field_level_merge_with_project_override(self, tmp_path: Path) -> None:
        shipped = tmp_path / "built-in"
        shipped.mkdir()
        project = tmp_path / "project"
        project.mkdir()

        yaml = YAML()
        yaml.default_flow_style = False

        base_term = {
            "surface": "mission",
            "definition": "Base definition.",
            "confidence": 0.9,
            "status": "active",
        }
        base = {
            "id": "merge-test",
            "provenance": "built-in",
            "description": "Base description",
            "terms": [base_term],
        }
        override = {
            "id": "merge-test",
            "provenance": "built-in",
            "description": "Overridden description",
            "terms": [base_term],
        }

        with (shipped / "merge-test.glossary-pack.yaml").open("w") as f:
            yaml.dump(base, f)
        with (project / "merge-test.glossary-pack.yaml").open("w") as f:
            yaml.dump(override, f)

        repo = GlossaryPackRepository(built_in_dir=shipped, project_dir=project)
        pack = repo.get("merge-test")
        assert pack is not None
        assert pack.description == "Overridden description"


class TestDoctrineServiceGlossaryPacksAccessor:
    """T009 liveness proof: DoctrineService.glossary_packs is really wired.

    Constructs the service with a built-in root that ships a fixture pack
    under ``glossary_packs/built-in/`` and confirms the accessor resolves
    ``_built_in_dir("glossary_packs")`` into a real ``GlossaryPackRepository``
    that loads it — not a dead/unreachable property.
    """

    def test_service_loads_glossary_pack_from_built_in_default_dir(
        self, tmp_path: Path, sample_pack_data: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = tmp_path / "packs"
        pack_dir = packs_root / "built-in" / "glossary_packs"
        pack_dir.mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        yaml = YAML()
        yaml.default_flow_style = False
        with (pack_dir / "spec-kitty-core.glossary-pack.yaml").open("w") as f:
            yaml.dump(sample_pack_data, f)

        service = DoctrineService()
        repo = service.glossary_packs

        assert isinstance(repo, GlossaryPackRepository)
        pack = repo.get("spec-kitty-core")
        assert pack is not None
        assert len(pack.terms) == 2

    def test_service_caches_glossary_packs_repository(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = tmp_path / "packs"
        (packs_root / "built-in").mkdir(parents=True)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        service = DoctrineService()
        assert "glossary_packs" not in service._cache

        first = service.glossary_packs
        assert "glossary_packs" in service._cache

        second = service.glossary_packs
        assert first is second
