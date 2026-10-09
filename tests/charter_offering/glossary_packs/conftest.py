"""Shared fixtures for glossary_packs tests."""

from pathlib import Path

import pytest


@pytest.fixture
def full_term_data() -> dict:
    """A GlossaryTerm fixture populating every field the seed carries.

    Mirrors the squad-verified seed shape: ``confidence`` is a float (not an
    enum/str), and ``see_also`` / ``introduced_in_mission`` / ``synonyms_to_avoid``
    are present alongside the Mission-B-forward-compat ``aliases`` /
    ``banned_synonyms`` fields (present + round-tripped, unwired in Mission A).
    """
    return {
        "surface": "work package",
        "definition": "A unit of implementable work within a mission, tracked as WP##.",
        "confidence": 0.9,
        "status": "active",
        "see_also": ["mission"],
        "introduced_in_mission": "010-documentation-mission",
        "synonyms_to_avoid": ["task", "ticket"],
        "aliases": ["WP"],
        "banned_synonyms": ["story"],
    }


@pytest.fixture
def minimal_term_data() -> dict:
    """A GlossaryTerm fixture with only the required fields.

    Used to assert that every optional field defaults to ``None`` (matching
    the runtime ``TermSense`` model), not ``[]``.
    """
    return {
        "surface": "mission",
        "definition": "A unit of Spec-Driven Development work.",
        "confidence": 0.95,
        "status": "active",
    }


@pytest.fixture
def sample_pack_data(full_term_data: dict, minimal_term_data: dict) -> dict:
    """A minimal valid GlossaryPack fixture with two terms."""
    return {
        "id": "spec-kitty-core",
        "provenance": "built-in",
        "description": "Canonical Spec Kitty terminology.",
        "terms": [full_term_data, minimal_term_data],
    }


@pytest.fixture
def tmp_glossary_pack_dir(tmp_path: Path, sample_pack_data: dict) -> Path:
    """Temp directory with a sample glossary-pack YAML file."""
    from ruamel.yaml import YAML

    pack_dir = tmp_path / "glossary_packs"
    pack_dir.mkdir()

    yaml = YAML()
    yaml.default_flow_style = False
    filepath = pack_dir / "spec-kitty-core.glossary-pack.yaml"
    with filepath.open("w") as f:
        yaml.dump(sample_pack_data, f)

    return pack_dir
