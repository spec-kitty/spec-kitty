"""Unit tests for CharterOfferingService three-layer (shipped/org/project) resolution.

Covers T015 of WP03 in mission ``layered-doctrine-org-layer-01KRNPEE``.

Tests:
- test_no_org_root: org_roots=[] → _org_dir returns None for all repositories
- test_single_org_root: org_roots=[tmp] → _org_dir("directives") resolves correctly
- test_org_root_missing_on_disk: non-existent path → repositories load without error
- test_org_root_artifacts_resolved: org dir with valid directive → service.directives finds it
- test_determinism: same inputs produce identical resolved sets on two calls
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_yaml(path: Path, data: dict) -> None:
    """Write *data* as YAML to *path*, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _directive_yaml(
    directive_id: str = "DIRECTIVE_001",
    title: str = "Test Directive",
    intent: str = "Test intent.",
    enforcement: str = "required",
) -> dict:
    return {
        "schema_version": "1.0",
        "id": directive_id,
        "title": title,
        "intent": intent,
        "enforcement": enforcement,
    }


def _packs_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point ``SPEC_KITTY_PACKS_ROOT`` at an isolated flat ``<tmp>/packs/built-in/`` tree.

    Replaces the retired ``CharterOfferingService(built_in_root=...)`` param (C-007):
    the built-in tier is now injected via the env override instead of a
    constructor kwarg, and the on-disk layout is FLAT (``packs/built-in/<kind>/``),
    not the old nested ``<root>/<kind>/built-in/`` shape.
    """
    packs_root = tmp_path / "packs"
    (packs_root / "built-in").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return packs_root


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestNoOrgRoot:
    """When org_roots is empty, _org_dirs returns [] for all artifact types."""

    def test_org_dirs_empty_when_org_roots_empty(self) -> None:
        service = CharterOfferingService(org_roots=[])
        for artifact in (
            "directives",
            "tactics",
            "styleguides",
            "toolguides",
            "paradigms",
            "procedures",
            "mission_step_contracts",
            "agent_profiles",
        ):
            assert service._org_dirs(artifact) == []

    def test_org_dirs_empty_when_org_roots_not_provided(self) -> None:
        """Default (None passed for org_roots) is equivalent to empty list."""
        service = CharterOfferingService()
        assert service._org_dirs("directives") == []
        assert service._org_roots == []

    def test_repositories_load_without_error_when_no_org_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Service with no org roots and empty shipped dir loads cleanly."""
        # Use an isolated (empty) packs root so we don't pick up the real
        # shipped directives.
        _packs_root(monkeypatch, tmp_path)
        service = CharterOfferingService(org_roots=[])
        # Accessing the repository must not raise
        repo = service.directives
        assert repo is not None
        assert repo.list_all() == []


class TestSingleOrgRoot:
    """When one org root is configured, _org_dirs points into that root."""

    def test_org_dirs_returns_correct_path(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org"
        service = CharterOfferingService(org_roots=[org_root])

        assert service._org_dirs("directives") == [org_root / "directives"]
        assert service._org_dirs("tactics") == [org_root / "tactics"]
        assert service._org_dirs("agent_profiles") == [org_root / "agent_profiles"]

    def test_org_roots_internal_list(self, tmp_path: Path) -> None:
        """org_roots stores the provided paths verbatim."""
        org_root = tmp_path / "org"
        service = CharterOfferingService(org_roots=[org_root])
        assert service._org_roots == [org_root]

    def test_all_org_roots_returned_in_declaration_order(self, tmp_path: Path) -> None:
        """_org_dirs returns every configured org root in declaration order (FR-006, C-004)."""
        first = tmp_path / "org-first"
        second = tmp_path / "org-second"
        third = tmp_path / "org-third"
        service = CharterOfferingService(org_roots=[first, second, third])

        assert service._org_dirs("directives") == [
            first / "directives",
            second / "directives",
            third / "directives",
        ]

    def test_org_dirs_empty_when_no_org_roots(self) -> None:
        """_org_dirs returns an empty list when no org roots are configured."""
        service = CharterOfferingService()
        assert service._org_dirs("directives") == []


class TestOrgRootMissingOnDisk:
    """A configured org root that does not exist on disk causes no error."""

    def test_nonexistent_org_dir_does_not_raise(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "no-such-org"
        assert not nonexistent.exists()

        service = CharterOfferingService(org_roots=[nonexistent])
        # _org_dirs still returns the path (existence check is repo's responsibility)
        assert service._org_dirs("directives") == [nonexistent / "directives"]

    def test_repository_loads_without_error_for_nonexistent_org_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DirectiveRepository handles a non-existent org_dir gracefully."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001"),
        )

        nonexistent_org = tmp_path / "no-such-org"
        service = CharterOfferingService(org_roots=[nonexistent_org])

        # Must not raise; shipped artifact is still accessible
        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None

    def test_shipped_artifacts_accessible_when_org_dir_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shipped items load normally even when org dir does not exist on disk."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped Only"),
        )

        service = CharterOfferingService(org_roots=[tmp_path / "nonexistent"])

        assert service.directives.get("DIRECTIVE_001") is not None
        assert service.directives.get_provenance("DIRECTIVE_001") == "builtin"


class TestOrgRootArtifactsResolved:
    """When the org dir contains valid artifacts they are merged above shipped."""

    def test_org_directive_visible_via_service(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = _packs_root(monkeypatch, tmp_path)
        org_root = tmp_path / "org-root"

        # Shipped baseline
        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped Title"),
        )
        # Org adds a new directive
        _write_yaml(
            org_root / "directives" / "org-new.directive.yaml",
            _directive_yaml("DIRECTIVE_ORG", title="Org Title"),
        )

        service = CharterOfferingService(org_roots=[org_root])

        org_directive = service.directives.get("DIRECTIVE_ORG")
        assert org_directive is not None
        assert org_directive.title == "Org Title"
        assert service.directives.get_provenance("DIRECTIVE_ORG") == "org"

    def test_org_overrides_built_in_directive(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = _packs_root(monkeypatch, tmp_path)
        org_root = tmp_path / "org-root"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped Title"),
        )
        _write_yaml(
            org_root / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Org Override"),
        )

        service = CharterOfferingService(org_roots=[org_root])

        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Org Override"
        assert service.directives.get_provenance("DIRECTIVE_001") == "org"

    def test_project_overrides_org(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = _packs_root(monkeypatch, tmp_path)
        org_root = tmp_path / "org-root"
        project_root = tmp_path / "project-root"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            org_root / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Org Override"),
        )
        _write_yaml(
            project_root / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Project Override"),
        )

        service = CharterOfferingService(org_roots=[org_root], project_root=project_root)

        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Project Override"
        assert service.directives.get_provenance("DIRECTIVE_001") == "project"

    def test_cache_is_invalidated_between_service_instances(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two separate service instances with the same paths produce independent caches."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        org_root = tmp_path / "org-root"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001"),
        )
        _write_yaml(
            org_root / "directives" / "org.directive.yaml",
            _directive_yaml("DIRECTIVE_ORG"),
        )

        svc_a = CharterOfferingService(org_roots=[org_root])
        svc_b = CharterOfferingService(org_roots=[org_root])

        assert svc_a.directives is not svc_b.directives


class TestDeterminism:
    """Identical inputs produce identical resolved sets on repeated accesses."""

    def test_same_inputs_produce_identical_sets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs_root = _packs_root(monkeypatch, tmp_path)
        org_root = tmp_path / "org-root"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            org_root / "directives" / "002.directive.yaml",
            _directive_yaml("DIRECTIVE_002", title="Org"),
        )

        service_a = CharterOfferingService(org_roots=[org_root])
        service_b = CharterOfferingService(org_roots=[org_root])

        ids_a = {d.id for d in service_a.directives.list_all()}
        ids_b = {d.id for d in service_b.directives.list_all()}

        assert ids_a == ids_b
        assert "DIRECTIVE_001" in ids_a
        assert "DIRECTIVE_002" in ids_a

    def test_repeated_property_access_returns_cached_object(self, tmp_path: Path) -> None:
        """The lazy cache returns the same repository object on subsequent accesses."""
        service = CharterOfferingService(org_roots=[tmp_path / "org"])

        first = service.directives
        second = service.directives
        assert first is second

    def test_org_roots_empty_matches_no_org_roots_behavior(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """org_roots=[] is equivalent to not passing org_roots at all."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001"),
        )

        svc_explicit = CharterOfferingService(org_roots=[])
        svc_default = CharterOfferingService()

        ids_explicit = {d.id for d in svc_explicit.directives.list_all()}
        ids_default = {d.id for d in svc_default.directives.list_all()}

        assert ids_explicit == ids_default


class TestMultiplePackPrecedence:
    """Multiple org packs merge in declaration order; later packs override earlier (FR-006, C-004, Scenario 2)."""

    def test_later_pack_overrides_earlier_for_same_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When two org packs declare the same directive ID, the later pack wins."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        pack_a = tmp_path / "pack-a"
        pack_b = tmp_path / "pack-b"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            pack_a / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Pack A"),
        )
        _write_yaml(
            pack_b / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Pack B"),
        )

        service = CharterOfferingService(org_roots=[pack_a, pack_b])

        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Pack B"
        assert service.directives.get_provenance("DIRECTIVE_001") == "org"

    def test_distinct_artifacts_from_each_pack_all_visible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Distinct artifacts from each org pack are unioned into the resolved set."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        pack_security = tmp_path / "pack-security"
        pack_compliance = tmp_path / "pack-compliance"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            pack_security / "directives" / "sec.directive.yaml",
            _directive_yaml("DIRECTIVE_SEC", title="Security"),
        )
        _write_yaml(
            pack_compliance / "directives" / "comp.directive.yaml",
            _directive_yaml("DIRECTIVE_COMP", title="Compliance"),
        )

        service = CharterOfferingService(org_roots=[pack_security, pack_compliance])

        ids = {d.id for d in service.directives.list_all()}
        assert ids == {"DIRECTIVE_001", "DIRECTIVE_SEC", "DIRECTIVE_COMP"}
        assert service.directives.get_provenance("DIRECTIVE_SEC") == "org"
        assert service.directives.get_provenance("DIRECTIVE_COMP") == "org"
        assert service.directives.get_provenance("DIRECTIVE_001") == "builtin"

    def test_three_pack_chain_last_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With three packs declaring the same ID, the third pack wins (declaration order = precedence)."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        pack1 = tmp_path / "pack1"
        pack2 = tmp_path / "pack2"
        pack3 = tmp_path / "pack3"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        for pack, label in [(pack1, "First"), (pack2, "Second"), (pack3, "Third")]:
            _write_yaml(
                pack / "directives" / "001.directive.yaml",
                _directive_yaml("DIRECTIVE_001", title=label),
            )

        service = CharterOfferingService(org_roots=[pack1, pack2, pack3])

        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Third"

    def test_project_layer_still_overrides_all_org_packs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The project layer keeps full-replace precedence over every org pack."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        pack_a = tmp_path / "pack-a"
        pack_b = tmp_path / "pack-b"
        project_root = tmp_path / "project-root"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            pack_a / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Pack A"),
        )
        _write_yaml(
            pack_b / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Pack B"),
        )
        _write_yaml(
            project_root / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Project"),
        )

        service = CharterOfferingService(
            org_roots=[pack_a, pack_b],
            project_root=project_root,
        )

        directive = service.directives.get("DIRECTIVE_001")
        assert directive is not None
        assert directive.title == "Project"
        assert service.directives.get_provenance("DIRECTIVE_001") == "project"

    def test_missing_pack_on_disk_does_not_break_others(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-existent pack path is silently skipped; remaining packs still resolve."""
        packs_root = _packs_root(monkeypatch, tmp_path)
        pack_real = tmp_path / "pack-real"
        pack_missing = tmp_path / "no-such-pack"

        _write_yaml(
            packs_root / "built-in" / "directives" / "001.directive.yaml",
            _directive_yaml("DIRECTIVE_001", title="Shipped"),
        )
        _write_yaml(
            pack_real / "directives" / "real.directive.yaml",
            _directive_yaml("DIRECTIVE_REAL", title="Real"),
        )

        service = CharterOfferingService(org_roots=[pack_missing, pack_real])

        ids = {d.id for d in service.directives.list_all()}
        assert ids == {"DIRECTIVE_001", "DIRECTIVE_REAL"}
        assert service.directives.get_provenance("DIRECTIVE_REAL") == "org"
