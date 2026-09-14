"""Falsifiable coverage for the ``context-sources`` -> ``*-references``
consolidation (mission ``doctrine-drg-silent-drop-boundary-01M0PE7E``, WP02,
#3629 p1).

The 25 shipped profiles are **green-by-construction**: every id they authored on
``context-sources.{directives,tactics,toolguides,styleguides}`` was already
present on the matching ``*-references`` field, so for them the migration is
pure deletion. That means the migration's *data-moving* branch (set-merging an id
that is absent from ``*-references``) is exercised ONLY by the divergent
user-profile fixture here -- not by any shipped profile. This module pins:

1. the data-moving branch (divergent fixture) — ids absent from ``*-references``
   land there post-migration;
2. no shipped reference id is lost by the removal (frozen pre-migration
   snapshot);
3. the shipped profiles no longer author ``context-sources`` at all, and
   authoring it fails to load (the fail-loud boundary, FR-006);
4. **C-006**: the per-``agent_profile:*`` golden edge-set diff against the
   pre-consolidation graph is empty EXCEPT the deliberately-ledgered delta
   (ledger entry (21) in
   ``tests/doctrine/drg/migration/test_extractor_projection.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.offering.pack_paths import built_in_root
from charter.offering.agent_profiles import AgentProfile, AgentProfileRepository
from specify_cli.upgrade.migrations.m_3_3_1_context_sources_consolidation import (
    consolidate_profile_context_sources,
)

try:  # pragma: no cover - exercised via CI import
    from ruamel.yaml import YAML
except ImportError:  # pragma: no cover
    YAML = None  # type: ignore[assignment,misc]

# Reads the real shipped ``packs/built-in/agent_profiles`` corpus via
# ``built_in_root()`` -> corpus-marked so the fast-tests-corpus data-path
# trigger re-runs it when the shipped profiles change; ``fast`` places it in
# the doctrine fast shard (matching the sibling agent_profiles corpus tests).
pytestmark = [pytest.mark.fast, pytest.mark.corpus]

_FIXTURES = Path(__file__).parent / "fixtures"
_BEFORE_EDGES = _FIXTURES / "agent_profile_edges_before_consolidation.json"
_PRE_MIGRATION_CS = _FIXTURES / "shipped_context_sources_pre_migration.json"

#: Ledgered golden deltas from the frozen pre-consolidation graph. The first
#: three additions are migration ledger entry (21). The minutes profile entries
#: record its later rename plus the two new directive references and direct
#: styleguide relationship, while preserving the historical fixture unchanged.
#:
#: Ledger entry (22) (mission ``drupal-dries-profile-01M28X69``, WP07):
#: the new ``agent_profile:drupalling-dries`` node mints its own
#: ``specializes_from`` lineage edge plus the ``requires`` edges minted from
#: its ``directive-references``/``tactic-references`` — 11 edges in total, none
#: of which touch any pre-existing profile's edge set.
_LEDGERED_ADDED: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("agent_profile:python-pedro", "directive:DIRECTIVE_034", "requires"),
        ("agent_profile:diagram-daisy", "toolguide:mermaid-diagramming", "suggests"),
        ("agent_profile:diagram-daisy", "toolguide:plantuml-diagramming", "suggests"),
        ("agent_profile:minutes-mahad", "directive:ACTION_ITEM_ATTRIBUTION", "requires"),
        ("agent_profile:minutes-mahad", "directive:DIRECTIVE_003", "requires"),
        ("agent_profile:minutes-mahad", "directive:DIRECTIVE_047", "requires"),
        ("agent_profile:minutes-mahad", "directive:DIRECTIVE_049", "requires"),
        ("agent_profile:minutes-mahad", "directive:DIRECTIVE_050", "requires"),
        ("agent_profile:minutes-mahad", "directive:MINUTES_STAND_ALONE", "requires"),
        ("agent_profile:minutes-mahad", "procedure:meeting-minutes-pipeline", "requires"),
        ("agent_profile:minutes-mahad", "styleguide:meeting-minutes-format", "suggests"),
        ("agent_profile:drupalling-dries", "agent_profile:implementer-ivan", "specializes_from"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_010", "requires"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_024", "requires"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_025", "requires"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_030", "requires"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_034", "requires"),
        ("agent_profile:drupalling-dries", "directive:DIRECTIVE_051", "requires"),
        ("agent_profile:drupalling-dries", "tactic:bug-fixing-checklist", "requires"),
        ("agent_profile:drupalling-dries", "tactic:dependency-hygiene", "requires"),
        ("agent_profile:drupalling-dries", "tactic:supply-chain-install-safety", "requires"),
        ("agent_profile:drupalling-dries", "tactic:tdd-red-green-refactor", "requires"),
    }
)
_LEDGERED_REMOVED: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("agent_profile:minutes-maker-mahad", "directive:DIRECTIVE_003", "requires"),
        ("agent_profile:minutes-maker-mahad", "directive:DIRECTIVE_047", "requires"),
        ("agent_profile:minutes-maker-mahad", "directive:DIRECTIVE_049", "requires"),
        ("agent_profile:minutes-maker-mahad", "directive:DIRECTIVE_050", "requires"),
        ("agent_profile:minutes-maker-mahad", "procedure:meeting-minutes-pipeline", "requires"),
    }
)

_PROFILE_RENAMES = {"minutes-maker-mahad": "minutes-mahad"}

#: ``context-sources`` key -> (canonical ``*-references`` field, id attribute on
#: the resolved model). Directive refs key on ``code``; the rest on ``id``.
_REFERENCE_ATTR = {
    "directives": ("directive_references", "code"),
    "tactics": ("tactic_references", "id"),
    "toolguides": ("toolguide_references", "id"),
    "styleguides": ("styleguide_references", "id"),
}


def _profile_edges(graph_path: Path) -> set[tuple[str, str, str]]:
    assert YAML is not None
    data = YAML(typ="safe").load(graph_path.read_text(encoding="utf-8"))
    return {(e["source"], e["target"], e["relation"]) for e in (data.get("edges") or []) if str(e.get("source", "")).startswith("agent_profile:")}


class TestMigrationDataMovingBranch:
    """The set-merge branch — only a divergent profile reaches it."""

    def _divergent_profile(self) -> dict[str, object]:
        # ``context-sources`` carries ids ABSENT from the ``*-references`` twins
        # (the divergence the shipped set never has) plus one duplicate to prove
        # the set-merge dedups rather than appends.
        return {
            "profile-id": "divergent-user",
            "name": "Divergent User",
            "purpose": "exercise the migration data-moving branch",
            "roles": ["implementer"],
            "specialization": {"primary-focus": "testing"},
            "directive-references": [
                {"code": "010", "name": "Spec Fidelity", "rationale": "already present"},
            ],
            "tactic-references": [
                {"id": "dependency-hygiene", "rationale": "already present"},
            ],
            "context-sources": {
                "directives": ["010", "099"],  # 010 dup, 099 net-new
                "tactics": ["orphan-tactic"],  # net-new
                "toolguides": ["orphan-toolguide"],  # net-new (no toolguide-references yet)
                "styleguides": ["orphan-styleguide"],  # net-new (no styleguide-references yet)
                "doctrine-layers": ["directives", "tactics"],  # dropped (no edge shape)
                "additional": ["free-text-note"],  # dropped (no edge shape)
            },
        }

    def test_absent_ids_move_onto_references(self) -> None:
        data = self._divergent_profile()
        outcome = consolidate_profile_context_sources(data)

        assert outcome.changed
        assert "context-sources" not in data

        directive_codes = [r["code"] for r in data["directive-references"]]
        assert "099" in directive_codes, "net-new directive id must move onto directive-references"
        assert directive_codes.count("010") == 1, "duplicate id must be deduped, not appended"

        tactic_ids = [r["id"] for r in data["tactic-references"]]
        assert "orphan-tactic" in tactic_ids
        assert "orphan-toolguide" in [r["id"] for r in data["toolguide-references"]]
        assert "orphan-styleguide" in [r["id"] for r in data["styleguide-references"]]

    def test_non_edge_keys_dropped_with_a_note(self) -> None:
        data = self._divergent_profile()
        outcome = consolidate_profile_context_sources(data)

        assert "doctrine-layers:directives" in outcome.dropped
        assert "additional:free-text-note" in outcome.dropped
        # The merge report names exactly the fields that gained a net-new id.
        assert set(outcome.merged) == {
            "directive-references",
            "tactic-references",
            "toolguide-references",
            "styleguide-references",
        }

    def test_merged_profile_loads_and_projects(self) -> None:
        """The consolidated profile validates against the model with the moved
        ids now on the canonical surface (proving the migration output is
        loadable — the whole point of the atomic removal↔migration triad)."""
        data = self._divergent_profile()
        consolidate_profile_context_sources(data)
        profile = AgentProfile.model_validate(data)
        assert "099" in {r.code for r in profile.directive_references}
        assert "orphan-tactic" in {r.id for r in profile.tactic_references}

    def test_profile_without_context_sources_is_untouched(self) -> None:
        data = {"profile-id": "x", "name": "X", "purpose": "p", "roles": ["reviewer"]}
        outcome = consolidate_profile_context_sources(data)
        assert outcome.changed is False


class TestNoReferenceIdLost:
    """Frozen pre-migration snapshot — the removal drops no authored id."""

    def test_every_pre_migration_id_survives_on_references(self) -> None:
        snapshot = json.loads(_PRE_MIGRATION_CS.read_text(encoding="utf-8"))
        assert snapshot, "pre-migration context-sources snapshot is empty"
        repo = AgentProfileRepository()

        losses: list[str] = []
        for profile_id, per_kind in snapshot.items():
            current_profile_id = _PROFILE_RENAMES.get(profile_id, profile_id)
            profile = repo.get(current_profile_id)
            assert profile is not None, profile_id
            for cs_key, ids in per_kind.items():
                attr, id_attr = _REFERENCE_ATTR[cs_key]
                present = {getattr(ref, id_attr) for ref in getattr(profile, attr)}
                for ref_id in ids:
                    if ref_id not in present:
                        losses.append(f"{profile_id}.{cs_key}:{ref_id}")
        assert losses == [], f"context-sources ids lost after consolidation: {losses}"


class TestShippedProfilesFailLoud:
    """The removal is complete and the boundary is fail-loud."""

    def test_no_shipped_profile_authors_context_sources(self) -> None:
        profiles_dir = built_in_root() / "agent_profiles"
        offenders = [path.name for path in sorted(profiles_dir.glob("*.agent.yaml")) if "context-sources" in path.read_text(encoding="utf-8")]
        assert offenders == [], f"profiles still authoring context-sources: {offenders}"

    def test_authoring_context_sources_is_rejected(self) -> None:
        data = {
            "profile-id": "still-authoring",
            "name": "Still Authoring",
            "purpose": "p",
            "roles": ["reviewer"],
            "specialization": {"primary-focus": "testing"},
            "context-sources": {"directives": ["001"]},
        }
        with pytest.raises(ValidationError, match="context-sources"):
            AgentProfile.model_validate(data)


class TestGoldenDiffIsOnlyTheLedgeredDelta:
    """C-006 — the golden per-``agent_profile:*`` edge diff is exactly the
    ledgered delta.

    Compares the committed golden against the frozen pre-consolidation edge set.
    Byte-freshness of the committed golden (committed == a fresh regeneration) is
    guaranteed by
    ``tests/doctrine/drg/migration/test_extractor_projection.py::...
    test_shipped_graph_is_fresh_and_byte_identical``; this test pins the
    *content* of the intended change.
    """

    def test_diff_matches_ledger(self) -> None:
        before = {tuple(edge) for edge in json.loads(_BEFORE_EDGES.read_text(encoding="utf-8"))}
        after = _profile_edges(built_in_root() / "agent_profile.graph.yaml")

        added = after - before
        removed = before - after
        assert added == _LEDGERED_ADDED, (
            f"unledgered agent_profile edge(s) appeared in the golden — either a real regression or a missing ledger entry: {added ^ _LEDGERED_ADDED}"
        )
        assert removed == _LEDGERED_REMOVED, f"agent_profile edge(s) unexpectedly removed from the golden: {removed}"
