"""Black-box CLI tests for ``spec-kitty charter list --all`` (WP16, FR-025).

DIRECTIVE_036: these exercise the live CLI surface end-to-end via
``CliRunner`` — no internal mocking of the catalog. They prove that ``--all``:

* surfaces available-but-not-activated artifacts across the built-in, org, and
  project layers, each annotated by its source layer;
* derives the kind ordering from the canonical kind universe (no re-declared
  list); and
* appends the mission-scoped ``template`` kind with mission-qualified IDs
  discovered through WP18.

The fixtures build a real on-disk org pack and a project doctrine layer so the
roots (resolved in ``specify_cli``, passed as data — C-008) are honoured by the
lower layers.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.resolution import ResolutionTier
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter.list_cmd import _template_tier_roots

runner = CliRunner()

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_directive(directory: Path, stem: str, artifact_id: str) -> None:
    """Write a minimal directive artifact carrying a declared ``id:`` (R-011-D)."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{stem}.directive.yaml").write_text(
        textwrap.dedent(
            f"""\
            id: {artifact_id}
            type: directive
            title: {artifact_id}
            """
        ),
        encoding="utf-8",
    )


def _write_template(missions_root: Path, mission: str, name: str, body: str) -> None:
    """Write a mission-scoped template (WP18 discovery surface)."""
    tpl_dir = missions_root / mission / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)
    (tpl_dir / name).write_text(body, encoding="utf-8")


def _invoke(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["list", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def layered_project(tmp_path: Path) -> Path:
    """A project with an org pack + project doctrine layer + project template.

    Layout::

        <repo>/.kittify/config.yaml                 (registers the org pack)
        <repo>/.kittify/charter-packs/directive/<...>.directive.yaml
        <repo>/.kittify/charter-packs/missions/<mission>/templates/<name>
        <org-pack>/directives/<...>.directive.yaml
        <org-pack>/missions/<mission>/templates/<name>   (flat -- FR-006/WP03)
    """
    repo = tmp_path / "repo"
    kittify = repo / ".kittify"
    kittify.mkdir(parents=True)

    # Org pack on disk, registered via the doctrine.org.packs config block.
    org_pack = tmp_path / "org-pack"
    _write_directive(
        org_pack / "directives",
        "900-org-only-directive",
        "900-org-only-directive",
    )

    (kittify / "config.yaml").write_text(
        textwrap.dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: acme
                    local_path: {org_pack}
            """
        ),
        encoding="utf-8",
    )

    # Project doctrine layer directive.
    _write_directive(
        kittify / "charter-packs" / "directive",
        "950-project-only-directive",
        "950-project-only-directive",
    )

    # Project mission template (mission-qualified discovery target).
    _write_template(
        kittify / "charter-packs" / "missions",
        "acme-mission",
        "project-spec-template.md",
        "# project spec template\n",
    )

    # Org mission template, at the flat layout the resolver actually reads
    # (``<org_root>/missions/<mission>/templates/<name>`` -- WP03, FR-006).
    _write_template(
        org_pack / "missions",
        "acme-mission",
        "org-spec-template.md",
        "# org spec template\n",
    )

    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListAllLayers:
    def test_all_flag_adds_all_layers_column(self, layered_project: Path) -> None:
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "Available (all layers)" in result.output

    def test_all_supersedes_show_available_column_header(
        self, layered_project: Path
    ) -> None:
        # --all wins even when --show-available is also passed.
        result = _invoke(layered_project, "--show-available", "--all")
        assert result.exit_code == 0, result.output
        assert "Available (all layers)" in result.output
        assert "Available (not activated)" not in result.output

    def test_org_artifact_shown_with_org_layer(self, layered_project: Path) -> None:
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "900-org-only-directive" in result.output
        # Layer annotation present.
        assert "(org)" in result.output

    def test_project_artifact_shown_with_project_layer(
        self, layered_project: Path
    ) -> None:
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "950-project-only-directive" in result.output
        assert "(project)" in result.output

    def test_built_in_artifacts_annotated(self, layered_project: Path) -> None:
        """Built-in directives appear with the built-in layer tag."""
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        # The shipped built-in doctrine has directives; the layer tag must show.
        assert "(built-in)" in result.output


class TestListAllTemplateKind:
    def test_template_kind_row_present(self, layered_project: Path) -> None:
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "template" in result.output

    def test_template_mission_qualified_id_present(self, layered_project: Path) -> None:
        """The project template appears with a mission-qualified ID (WP18)."""
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "acme-mission/project-spec-template.md" in result.output

    def test_template_kind_absent_without_all(self, layered_project: Path) -> None:
        """The template row only appears in the --all (layer-aware) view."""
        result = _invoke(layered_project, "--show-available")
        assert result.exit_code == 0, result.output
        assert "acme-mission/project-spec-template.md" not in result.output


class TestKindOrderDerivedFromCanonical:
    def test_all_canonical_kinds_present(self, layered_project: Path) -> None:
        """Every canonical charter kind appears (order derived from WP01)."""
        from charter.offering.artifact_kinds import CHARTER_KIND_TOKENS

        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        for kind in CHARTER_KIND_TOKENS:
            assert kind in result.output, f"missing kind {kind!r}"


class TestListAllOrgTierReporting:
    """FR-006/SC-006: ``charter list --all`` reports the org template tier

    honestly -- as ``ResolutionTier.ORG`` at the flat ``<org_root>/missions/``
    path WP03's resolver actually reads, not the borrowed ``GLOBAL_MISSION``
    label at a nested ``<org_root>/doctrine/missions/`` path the resolver never
    consults (WP02/WP03).
    """

    def test_org_template_reported_as_org_tier(self, layered_project: Path) -> None:
        """The org-tier template is tagged ``(org)``, not ``(global_mission)``."""
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "acme-mission/org-spec-template.md (org)" in result.output
        assert "acme-mission/org-spec-template.md (global_mission)" not in result.output

    def test_org_template_id_present(self, layered_project: Path) -> None:
        """The org template appears with its mission-qualified ID (WP18)."""
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "acme-mission/org-spec-template.md" in result.output

    def test_org_template_at_nested_path_not_discovered(
        self, layered_project: Path
    ) -> None:
        """A template at the OLD nested ``<org_root>/doctrine/missions/`` path

        is not what the fixed code reads -- reinforcing that the fix moved the
        read location to the flat path WP03's resolver actually uses, not just
        the tag. Writing a second (differently-named) template at the nested
        location proves it is silently absent from the listing rather than
        being picked up and mislabeled.
        """
        org_pack = layered_project.parent / "org-pack"
        _write_template(
            org_pack / "doctrine" / "missions",
            "acme-mission",
            "org-nested-template.md",
            "# should not be discovered\n",
        )
        result = _invoke(layered_project, "--all")
        assert result.exit_code == 0, result.output
        assert "org-nested-template.md" not in result.output


class TestTemplateTierRootsOrgBranch:
    """T030: focused unit test directly on ``_template_tier_roots``'s org

    branch (NFR-006 -- this surface has no diff-coverage numeric CI backstop,
    so this is the actual regression guard per the repo's Sonar new-code
    coverage expectation).
    """

    def test_org_branch_reports_org_tier_at_flat_path(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_template(
            org_root / "missions", "acme-mission", "spec-template.md", "# tpl\n"
        )
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        tier_roots = _template_tier_roots(repo_root, {"org": org_root})

        org_roots = [tr for tr in tier_roots if tr.tier is ResolutionTier.ORG]
        assert [tr.missions_root for tr in org_roots] == [org_root / "missions"], tier_roots

    def test_org_branch_absent_when_no_org_root(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        tier_roots = _template_tier_roots(repo_root, {})

        assert all(tr.tier is not ResolutionTier.ORG for tr in tier_roots)

    def test_org_branch_absent_when_flat_missions_dir_missing(
        self, tmp_path: Path
    ) -> None:
        """An org root with no ``missions/`` dir contributes no ORG tier root."""
        org_root = tmp_path / "org-pack"
        org_root.mkdir()
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        tier_roots = _template_tier_roots(repo_root, {"org": org_root})

        assert all(tr.tier is not ResolutionTier.ORG for tr in tier_roots)
