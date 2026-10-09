"""Integration tests for WP07: provenance, doctor charter-packs, and lint advisories.

Covers T037 of mission ``layered-doctrine-org-layer-01KRNPEE``.

These tests exercise the full org-layer flow end-to-end:

* `charter context --json` surfaces ``source`` provenance per artifact and an
  ``org_charter`` block.
* `spec-kitty doctor charter-packs` reports configured packs, version, and counts.
* `charter lint` registers org-layer advisory checkers and surfaces a finding
  when an org pack overrides a shipped artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.charter_runtime.lint import LintEngine
from specify_cli.charter_runtime.lint.engine import _ALL_CHECKS, _CHECK_MAP
from tests._support.org_pack_config import write_org_packs
from charter.activation.org_charter_loader import load_org_charter_json_block

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _directive(directive_id: str, title: str) -> dict:
    return {
        "schema_version": "1.0",
        "id": directive_id,
        "title": title,
        "intent": f"Intent for {directive_id}",
        "enforcement": "required",
    }


# ---------------------------------------------------------------------------
# Test surfaces
# ---------------------------------------------------------------------------


class TestProvenanceServiceIntegration:
    """End-to-end provenance via the shared ``CharterOfferingService`` factory."""

    def test_org_overrides_builtin_provenance_resolves_to_org(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An org pack that ships the same directive ID as built-in surfaces ``source=org``."""
        # Built-in (shipped) layer -- an isolated flat packs/built-in/ tree,
        # injected via SPEC_KITTY_PACKS_ROOT (the built_in_root= param is retired).
        packs_root = tmp_path / "packs"
        _write_yaml(
            packs_root / "built-in" / "directives" / "DIRECTIVE_001.directive.yaml",
            _directive("DIRECTIVE_001", "Built-in Title"),
        )
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        # Org layer overrides DIRECTIVE_001 + adds ORG-001
        org_root = tmp_path / "org"
        _write_yaml(
            org_root / "directives" / "001.directive.yaml",
            _directive("DIRECTIVE_001", "Org Override"),
        )
        _write_yaml(
            org_root / "directives" / "org-001.directive.yaml",
            _directive("ORG-001", "Org-only Directive"),
        )

        from charter.offering.service import CharterOfferingService

        service = CharterOfferingService(org_roots=[org_root])

        assert service.directives.get_provenance("DIRECTIVE_001") == "org"
        assert service.directives.get_provenance("ORG-001") == "org"
        assert service.directives.get("DIRECTIVE_001").title == "Org Override"


class TestOrgCharterJsonBlock:
    """`load_org_charter_json_block` degrades gracefully when WP09 is absent."""

    def test_no_org_roots_returns_empty_block(self) -> None:
        block = load_org_charter_json_block(None)
        assert block == {"present": False, "packs": []}

    def test_no_charter_file_returns_empty_block(self, tmp_path: Path) -> None:
        # Org root exists but no org-charter.yaml present.
        org_root = tmp_path / "org"
        org_root.mkdir()
        block = load_org_charter_json_block([org_root])
        assert block["present"] is False
        assert block["packs"] == []


class TestDoctorCharterPacksCommand:
    """`spec-kitty doctor charter-packs` reports configured packs."""

    def test_no_org_configured(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.doctor import (
            _count_pack_artifacts,
            _resolve_pack_version,
        )

        # A non-git, no-manifest pack returns unknown version.
        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()
        version, fetched_at, is_git = _resolve_pack_version(snapshot)
        assert version == "unknown"
        assert fetched_at is None
        assert is_git is False
        assert _count_pack_artifacts(snapshot) == {}

    def test_pack_version_from_manifest(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.doctor import _resolve_pack_version

        snapshot = tmp_path / "snapshot"
        snapshot.mkdir()
        _write_yaml(
            snapshot / "pack-manifest.yaml",
            {"pack_version": "2.1.0", "fetched_at": "2026-05-15T12:00:00Z"},
        )
        version, fetched_at, is_git = _resolve_pack_version(snapshot)
        assert version == "2.1.0"
        assert fetched_at == "2026-05-15T12:00:00Z"
        assert is_git is False

    def test_artifact_counts(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.doctor import _count_pack_artifacts

        snapshot = tmp_path / "snapshot"
        _write_yaml(
            snapshot / "directives" / "a.yaml",
            _directive("DIR_001", "x"),
        )
        _write_yaml(
            snapshot / "directives" / "b.yaml",
            _directive("DIR_002", "y"),
        )
        _write_yaml(snapshot / "tactics" / "t.yaml", {"id": "T1"})
        counts = _count_pack_artifacts(snapshot)
        assert counts["directives"] == 2
        assert counts["tactics"] == 1


class TestLintOrgOverridesAdvisory:
    """`charter lint` registers the org-layer advisory checkers."""

    def test_lint_engine_registers_org_layer_checks(self) -> None:
        assert "org_overrides_builtin" in _ALL_CHECKS
        assert "org_charter_deviation" in _ALL_CHECKS
        assert "org_overrides_builtin" in _CHECK_MAP
        assert "org_charter_deviation" in _CHECK_MAP

    def test_org_overrides_checker_emits_advisory(self, tmp_path: Path, monkeypatch) -> None:
        """Patch ``CharterOfferingService`` factories to point at controllable directories."""
        # Build the shipped + org snapshots used by both services.
        built_in_root = tmp_path / "built-in"
        _write_yaml(
            built_in_root / "directives" / "built-in" / "DIRECTIVE_001.directive.yaml",
            _directive("DIRECTIVE_001", "Built-in Title"),
        )
        org_root = tmp_path / "org"
        _write_yaml(
            org_root / "directives" / "001.directive.yaml",
            _directive("DIRECTIVE_001", "Org Override"),
        )
        # Configure the registry on the synthetic repo root.
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        write_org_packs(repo_root, [{"name": "acme", "local_path": org_root}])

        # Patch the lazy ``CharterOfferingService`` builders inside the checker so
        # they consume the synthetic shipped/project roots.  We swap the
        # underlying resolver before invoking ``checker.run``.
        from specify_cli.charter_runtime.lint.checks import org_layer

        def _fake_resolve_offering_root() -> Path:
            return built_in_root

        def _fake_resolve_project_root(_root: Path) -> Path | None:
            return None

        monkeypatch.setattr(
            "charter.activation.catalog.resolve_offering_root", _fake_resolve_offering_root
        )
        monkeypatch.setattr(
            "charter.activation._project_root_candidates.resolve_project_root", _fake_resolve_project_root
        )

        checker = org_layer.OrgOverridesBuiltinChecker(repo_root=repo_root)
        findings = checker.run(drg=None)
        # We should detect the org override of DIRECTIVE_001.
        override_findings = [
            f for f in findings if f.type == "org_overrides_builtin"
        ]
        assert override_findings, "expected at least one org_overrides_builtin advisory"
        first = override_findings[0]
        assert first.severity == "low"
        assert first.category == "org_layer"
        assert "DIRECTIVE_001" in first.id


class TestLintEngineWithOrgChecksOnly:
    """LintEngine accepts the new check names without raising."""

    def test_engine_run_with_org_check_subset(self, tmp_path: Path) -> None:
        # Empty repo: no DRG → checker returns empty report, but no crash.
        engine = LintEngine(tmp_path)
        report = engine.run(checks={"org_overrides_builtin"})
        assert report.findings == [] or all(
            f.category == "org_layer" for f in report.findings
        )
