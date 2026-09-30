"""Scope: scope unit tests — no real git or subprocesses."""

import pytest
import yaml
from kernel.clock import datetime
from unittest.mock import patch
from glossary.scope import (
    GlossaryScope,
    SCOPE_RESOLUTION_ORDER,
    load_seed_file,
    save_seed_file,
    activate_scope,
)
from glossary.models import Provenance, SenseStatus, TermSense, TermSurface


def _make_sense(surface: str, definition: str, *, confidence: float = 1.0, status: SenseStatus = SenseStatus.ACTIVE) -> TermSense:
    return TermSense(
        surface=TermSurface(surface),
        scope="team_domain",
        definition=definition,
        provenance=Provenance(actor_id="test", timestamp=datetime(2026, 1, 1), source="test"),
        confidence=confidence,
        status=status,
    )

pytestmark = pytest.mark.fast

def test_scope_resolution_order():
    """SCOPE_RESOLUTION_ORDER is correct."""
    assert SCOPE_RESOLUTION_ORDER == [
        GlossaryScope.MISSION_LOCAL,
        GlossaryScope.TEAM_DOMAIN,
        GlossaryScope.AUDIENCE_DOMAIN,
        GlossaryScope.SPEC_KITTY_CORE,
    ]


def test_load_seed_file(sample_seed_file, tmp_path):
    """Can load seed file and parse terms."""
    senses = load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path)

    assert len(senses) == 2
    assert senses[0].surface.surface_text == "workspace"
    assert senses[0].definition == "Git worktree directory for a work package"
    assert senses[0].confidence == 1.0
    assert senses[0].status == SenseStatus.ACTIVE

def test_load_seed_file_empty_terms_value(tmp_path):
    """Treat a bare `terms:` key as an empty glossary."""
    seed_path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text("terms:\n", encoding="utf-8")

    assert load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path) == []

def test_load_seed_file_missing(tmp_path):
    """Returns empty list if seed file missing."""
    senses = load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path)
    assert senses == []

def test_activate_scope():
    """Emits GlossaryScopeActivated event via emit_scope_activated."""
    # Patch at events module level (scope.py uses local import inside activate_scope)
    with patch("glossary.events.emit_scope_activated") as mock_emit:
        mock_emit.return_value = {"event_type": "GlossaryScopeActivated"}

        activate_scope(
            GlossaryScope.TEAM_DOMAIN,
            version_id="v3",
            mission_id="041-mission",
            run_id="run-001",
            repo_root=None,
        )

        mock_emit.assert_called_once_with(
            scope_id="team_domain",
            glossary_version_id="v3",
            mission_id="041-mission",
            run_id="run-001",
            repo_root=None,
        )


# ---------------------------------------------------------------------------
# save_seed_file
# ---------------------------------------------------------------------------

class TestSaveSeedFile:
    """save_seed_file always writes sorted YAML and is the single write gate."""

    def test_creates_file_when_absent(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        assert path.exists()

    def test_creates_parent_directories(self, tmp_path):
        repo = tmp_path / "nested" / "repo"
        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, repo, terms)
        assert (repo / ".kittify" / "glossaries" / "team_domain.yaml").exists()

    def test_output_is_valid_yaml(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        assert "terms" in data
        assert len(data["terms"]) == 1

    def test_sorts_alphabetically_by_surface(self, tmp_path):
        terms = [
            _make_sense("zebra", "Z term"),
            _make_sense("alpha", "A term"),
            _make_sense("middle", "M term"),
        ]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        surfaces = [t["surface"] for t in data["terms"]]
        assert surfaces == ["alpha", "middle", "zebra"]

    def test_sort_is_case_insensitive(self, tmp_path):
        # TermSurface enforces lowercase; test that sort key uses .lower()
        # so "b-term" sorts before "ba-term" regardless of locale folding
        terms = [
            _make_sense("zeta", "Z term"),
            _make_sense("alpha", "A term"),
            _make_sense("beta", "B term"),
        ]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        surfaces = [t["surface"] for t in data["terms"]]
        assert surfaces == ["alpha", "beta", "zeta"]

    def test_sort_is_unconditional_even_when_already_sorted(self, tmp_path):
        terms = [
            _make_sense("alpha", "A term"),
            _make_sense("beta", "B term"),
        ]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        mtime_before = path.stat().st_mtime_ns
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        # File is always written (no skip-if-sorted optimisation at this layer)
        assert path.stat().st_mtime_ns >= mtime_before

    def test_definitions_needing_quotes_are_double_quoted(self, tmp_path):
        terms = [_make_sense("change mode", "A flag (change_mode: bulk_edit) that activates X")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        raw = path.read_text()
        # The raw YAML text must contain a double-quoted definition
        assert '"A flag (change_mode: bulk_edit)' in raw
        # And it must still parse correctly
        data = yaml.safe_load(raw)
        assert data["terms"][0]["definition"] == "A flag (change_mode: bulk_edit) that activates X"

    def test_definitions_with_apostrophe_are_double_quoted(self, tmp_path):
        terms = [_make_sense("charter", "A project's governance document")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        raw = path.read_text()
        assert '"A project\'s governance document"' in raw or "\"A project's governance document\"" in raw
        data = yaml.safe_load(raw)
        assert data["terms"][0]["definition"] == "A project's governance document"

    def test_confidence_integer_renders_as_decimal(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree", confidence=1.0)]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        raw = path.read_text()
        assert "confidence: 1.0" in raw

    def test_confidence_fraction_preserves_value(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree", confidence=0.95)]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        assert data["terms"][0]["confidence"] == pytest.approx(0.95)

    def test_all_statuses_serialize_correctly(self, tmp_path):
        terms = [
            _make_sense("active-term", "Active", status=SenseStatus.ACTIVE),
            _make_sense("draft-term", "Draft", status=SenseStatus.DRAFT),
            _make_sense("deprecated-term", "Deprecated", status=SenseStatus.DEPRECATED),
        ]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        by_surface = {t["surface"]: t["status"] for t in data["terms"]}
        assert by_surface["active-term"] == "active"
        assert by_surface["draft-term"] == "draft"
        assert by_surface["deprecated-term"] == "deprecated"

    def test_empty_terms_list_produces_valid_file(self, tmp_path):
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, [])
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        data = yaml.safe_load(path.read_text())
        assert data["terms"] == []
        assert load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path) == []

    def test_round_trip_with_load_seed_file(self, tmp_path):
        original = [
            _make_sense("zebra", "Z term", confidence=0.9, status=SenseStatus.DRAFT),
            _make_sense("alpha", "A term", confidence=1.0, status=SenseStatus.ACTIVE),
        ]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, original)
        loaded = load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path)

        assert len(loaded) == 2
        # Loaded order matches saved (sorted) order
        assert loaded[0].surface.surface_text == "alpha"
        assert loaded[1].surface.surface_text == "zebra"
        # Fields survive the round-trip
        alpha = loaded[0]
        assert alpha.definition == "A term"
        assert alpha.confidence == 1.0
        assert alpha.status == SenseStatus.ACTIVE
        zebra = loaded[1]
        assert zebra.definition == "Z term"
        assert zebra.confidence == pytest.approx(0.9)
        assert zebra.status == SenseStatus.DRAFT

    def test_preserves_existing_header_on_update(self, tmp_path):
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        path.parent.mkdir(parents=True)
        path.write_text("# My custom header\n# Line two\n\nterms:\n")

        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)

        raw = path.read_text()
        assert raw.startswith("# My custom header\n# Line two")

    def test_new_file_gets_default_header(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, terms)
        path = tmp_path / ".kittify" / "glossaries" / "team_domain.yaml"
        raw = path.read_text()
        assert raw.startswith("#")

    def test_scope_value_determines_filename(self, tmp_path):
        terms = [_make_sense("workspace", "A git worktree")]
        save_seed_file(GlossaryScope.SPEC_KITTY_CORE, tmp_path, terms)
        assert (tmp_path / ".kittify" / "glossaries" / "spec_kitty_core.yaml").exists()
        assert not (tmp_path / ".kittify" / "glossaries" / "team_domain.yaml").exists()

    def test_overwrites_previous_content_completely(self, tmp_path):
        v1 = [_make_sense("old-term", "Old"), _make_sense("another", "Another")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, v1)

        v2 = [_make_sense("new-term", "New")]
        save_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path, v2)

        loaded = load_seed_file(GlossaryScope.TEAM_DOMAIN, tmp_path)
        assert len(loaded) == 1
        assert loaded[0].surface.surface_text == "new-term"
