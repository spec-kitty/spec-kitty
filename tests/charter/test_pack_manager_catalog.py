"""Catalog-core tests for ``charter.activation.pack_manager`` (WP09, T043).

Covers the WP09 refactor surface:

* **Kind-table parity** — the canonically-derived ``YAML_KEY_MAP`` matches the
  previously hand-maintained mapping exactly (T039); no second kind enumeration
  is re-declared in ``pack_manager`` (CC-4).
* **``list_available`` across layers** — built-in + org + project scan with a
  fixture pack, annotated by source layer (T040/T041, FR-026).
* **id-aware availability** — files lacking a valid ``id:`` field are skipped;
  the operator-facing config-stem ID is surfaced (R-011-D).
* **Activation delegation** — ``activate``/``deactivate`` delegate to the WP10
  engine; the typed engine errors propagate (T042).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
import yaml

from charter.activation.activation_engine import (
    NoActivationRestrictionsError,
    UnknownActivationIdError,
)
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import (
    YAML_KEY_MAP,
    AvailableArtifact,
    CharterPackManager,
    _resolve_layer_candidate,
)
from charter.offering.artifact_kinds import CHARTER_KIND_TOKENS, ArtifactKind

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("# empty config\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def ctx(project_root: Path) -> ProjectContext:
    """ProjectContext built from the minimal project root.

    Uses the direct constructor rather than ``ProjectContext.from_repo`` --
    ``CharterPackManager`` only ever calls ``ctx.require_repo_root()``
    (``pack_context`` is never read), and ``from_repo`` eagerly resolves
    ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
    ``mission_type_activations`` is absent from config.yaml. These tests
    intentionally exercise a bare/near-bare config.yaml, so building the
    full pack context here would force an unrelated mission-type activation
    key onto every fixture.
    """
    return ProjectContext(repo_root=project_root)


@pytest.fixture()
def manager() -> CharterPackManager:
    return CharterPackManager()


def _write_directive(dir_path: Path, stem: str, declared_id: str) -> None:
    """Write a minimal ``<stem>.directive.yaml`` carrying an ``id:`` field."""
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{stem}.directive.yaml").write_text(
        f"id: {declared_id}\ntype: directive\ntitle: {stem}\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T039 — kind-table parity + no re-enumeration
# ---------------------------------------------------------------------------

#: The kind→config-key mapping as it existed before WP09 (hand-maintained).
#: WP09 derives the live map from the canonical resolver; this literal exists
#: only as the parity oracle.
_LEGACY_YAML_KEY_MAP: dict[str, str] = {
    "mission-type": "mission_type_activations",
    "directive": "activated_directives",
    "tactic": "activated_tactics",
    "styleguide": "activated_styleguides",
    "toolguide": "activated_toolguides",
    "paradigm": "activated_paradigms",
    "procedure": "activated_procedures",
    "agent-profile": "activated_agent_profiles",
    "mission-step-contract": "activated_mission_step_contracts",
    "glossary-pack": "activated_glossary_packs",
}


class TestKindTableParity:
    def test_yaml_key_map_matches_legacy_mapping(self) -> None:
        """Derived map is byte-for-byte identical to the legacy hand map."""
        assert YAML_KEY_MAP == _LEGACY_YAML_KEY_MAP

    def test_yaml_key_map_covers_canonical_kind_universe(self) -> None:
        """Every charter kind token (WP01) has exactly one config key."""
        assert set(YAML_KEY_MAP) == set(CHARTER_KIND_TOKENS)
        assert len(YAML_KEY_MAP) == len(CHARTER_KIND_TOKENS)

    def test_no_second_kind_enumeration_in_module(self) -> None:
        """The old ``_KIND_TO_DOCTRINE_DIR`` kind table no longer exists.

        CC-4: kind validation/derivation routes through the canonical resolver,
        not a re-declared kind set.
        """
        import charter.activation.pack_manager as pm

        assert not hasattr(pm, "_KIND_TO_DOCTRINE_DIR")

    def test_module_routes_through_canonical_resolver(self) -> None:
        """``pack_manager`` imports the canonical kind resolver (WP01)."""
        src = inspect.getsource(__import__("charter.activation.pack_manager", fromlist=["x"]))
        assert "from_operator_token" in src
        assert "CHARTER_KIND_TOKENS" in src


# ---------------------------------------------------------------------------
# T040/T041 — list_available across layers, id-aware
# ---------------------------------------------------------------------------


class TestListAvailableBuiltIn:
    def test_returns_frozenset_for_directive(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        result = manager.list_available(ctx, kind="directive")
        assert isinstance(result, frozenset)
        assert len(result) > 0

    def test_returns_config_stem_not_declared_id(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        """Built-in directives surface their config-stem ID (e.g.
        ``001-architectural-integrity-standard``), not the URN ``id:``
        (``DIRECTIVE_001``)."""
        result = manager.list_available(ctx, kind="directive")
        assert "001-architectural-integrity-standard" in result
        assert "DIRECTIVE_001" not in result

    def test_unknown_kind_raises_value_error(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        with pytest.raises(ValueError, match="Unknown activation kind"):
            manager.list_available(ctx, kind="bogus-kind")

    def test_detailed_annotates_built_in_layer(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        detailed = manager.list_available_detailed(ctx, kind="directive")
        assert detailed
        assert all(isinstance(e, AvailableArtifact) for e in detailed)
        assert {e.layer for e in detailed} == {"built-in"}


class TestListAvailableAcrossLayers:
    def test_includes_org_and_project_layers(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        """FR-026: org + project doctrine roots (passed as data) are scanned."""
        org_root = tmp_path / "org-doctrine"
        project_root = tmp_path / "project-doctrine"
        _write_directive(org_root / "doctrine" / "directives" / "org", "900-org-rule", "DIRECTIVE_900")
        _write_directive(
            project_root / "doctrine" / "directive",
            "950-project-rule",
            "DIRECTIVE_950",
        )

        layer_roots = {"org": org_root, "project": project_root}
        result = manager.list_available(ctx, kind="directive", layer_roots=layer_roots)

        assert "900-org-rule" in result
        assert "950-project-rule" in result
        # Built-in still present.
        assert "001-architectural-integrity-standard" in result

    def test_project_layer_ignores_legacy_plural_directory(
        self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path
    ) -> None:
        """Project layer scans the singular runtime layout, not plural pack dirs."""
        project_root = tmp_path / "project-doctrine"
        _write_directive(
            project_root / "doctrine" / "directive",
            "950-project-rule",
            "DIRECTIVE_950",
        )
        _write_directive(
            project_root / "doctrine" / "directives" / "project",
            "951-legacy-project-rule",
            "DIRECTIVE_951",
        )

        result = manager.list_available(
            ctx, kind="directive", layer_roots={"project": project_root}
        )

        assert "950-project-rule" in result
        assert "951-legacy-project-rule" not in result

    def test_detailed_carries_layer_per_artifact(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        org_root = tmp_path / "org-doctrine"
        _write_directive(org_root / "doctrine" / "directives" / "org", "900-org-rule", "DIRECTIVE_900")

        detailed = manager.list_available_detailed(
            ctx, kind="directive", layer_roots={"org": org_root}
        )
        by_id = {e.artifact_id: e.layer for e in detailed}
        assert by_id["900-org-rule"] == "org"
        assert by_id["001-architectural-integrity-standard"] == "built-in"

    def test_layer_roots_default_is_built_in_only(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        """Omitting layer_roots scans built-in only (backward compatible)."""
        org_root = tmp_path / "org-doctrine"
        _write_directive(org_root / "doctrine" / "directives" / "org", "900-org-rule", "DIRECTIVE_900")
        result = manager.list_available(ctx, kind="directive")
        assert "900-org-rule" not in result


class TestListAvailableIdAware:
    def test_skips_files_without_declared_id(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        """R-011-D: a file with no ``id:`` field is not a catalog artifact."""
        org_root = tmp_path / "org-doctrine"
        good_dir = org_root / "doctrine" / "directives" / "org"
        good_dir.mkdir(parents=True)
        # Valid artifact (has id:)
        (good_dir / "900-good.directive.yaml").write_text(
            "id: DIRECTIVE_900\ntype: directive\n", encoding="utf-8"
        )
        # Malformed artifact (no id:)
        (good_dir / "901-no-id.directive.yaml").write_text(
            "type: directive\ntitle: missing id\n", encoding="utf-8"
        )

        result = manager.list_available(ctx, kind="directive", layer_roots={"org": org_root})
        assert "900-good" in result
        assert "901-no-id" not in result


# ---------------------------------------------------------------------------
# T042 — activate/deactivate delegate to the engine
# ---------------------------------------------------------------------------


class TestActivationDelegation:
    def test_activate_materializes_the_effective_set_and_persists(
        self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path
    ) -> None:
        """#4253: materialization preserves what was effective, not default.yaml.

        The persisted set must therefore be wider than the default pack — that
        difference is precisely what used to be deactivated.
        """
        result = manager.activate(ctx, kind="directive", artifact_id="025-boy-scout-rule")
        assert any("already effective" in w for w in result.warnings)
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "025-boy-scout-rule" in data["activated_directives"]
        available = manager.list_available(ctx, "directive")
        assert not set(available) - set(data["activated_directives"]), (
            "activation dropped a previously effective directive"
        )

    def test_activate_accepts_org_layer_artifact(
        self,
        manager: CharterPackManager,
        ctx: ProjectContext,
        project_root: Path,
        tmp_path: Path,
    ) -> None:
        org_root = tmp_path / "org-doctrine"
        _write_directive(
            org_root / "doctrine" / "directives" / "org",
            "900-org-rule",
            "DIRECTIVE_900",
        )

        result = manager.activate(
            ctx,
            kind="directive",
            artifact_id="900-org-rule",
            layer_roots={"org": org_root},
        )

        assert "900-org-rule" in result.activated
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "900-org-rule" in data["activated_directives"]

    def test_activate_unknown_id_raises_typed_error_no_write(
        self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path
    ) -> None:
        config = project_root / ".kittify" / "config.yaml"
        before = config.read_text(encoding="utf-8")
        with pytest.raises(UnknownActivationIdError):
            manager.activate(ctx, kind="directive", artifact_id="zzz-not-real")
        # NFR-003: nothing written on a failed plan.
        assert config.read_text(encoding="utf-8") == before

    def test_deactivate_removes_via_engine(
        self, manager: CharterPackManager, project_root: Path
    ) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - keep-me\n  - drop-me\n", encoding="utf-8"
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.deactivate(ctx, kind="directive", artifact_id="drop-me")
        assert "drop-me" in result.deactivated
        data = yaml.safe_load(config.read_text())
        assert data["activated_directives"] == ["keep-me"]

    def test_deactivate_none_state_raises_typed_error_not_sysexit(
        self, manager: CharterPackManager, ctx: ProjectContext
    ) -> None:
        """T042: no sys.exit — the engine raises NoActivationRestrictionsError."""
        with pytest.raises(NoActivationRestrictionsError):
            manager.deactivate(ctx, kind="directive", artifact_id="anything")

    def test_no_sys_exit_call_in_module(self) -> None:
        """T042 validation: ``pack_manager`` makes no ``sys.exit`` call.

        Inspects the parsed AST (not the prose docstring, which legitimately
        documents the *removed* legacy ``sys.exit``).
        """
        import ast

        src = inspect.getsource(__import__("charter.activation.pack_manager", fromlist=["x"]))
        tree = ast.parse(src)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "sys"
        ]
        assert calls == []
        # The ``sys`` import is also gone (no process-state coupling).
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
        assert not any(alias.name == "sys" for imp in imports for alias in imp.names)

    def test_module_calls_activation_engine(self) -> None:
        """Integration: the WP10 engine is actually invoked (not dead code)."""
        src = inspect.getsource(__import__("charter.activation.pack_manager", fromlist=["x"]))
        assert "plan_activation(" in src
        assert "plan_deactivation(" in src
        assert "commit_plan(" in src


# ---------------------------------------------------------------------------
# _resolve_layer_candidate (S3776 decomposition of _scan_layer_dirs, WP03)
# ---------------------------------------------------------------------------


class TestResolveLayerCandidate:
    """Pins the per-``(layer, kind, layered)`` directory-layout rules that
    ``_scan_layer_dirs`` (previously a single 16-cognitive-complexity ``if``/
    ``elif`` chain) delegates to. Each branch is exercised in isolation.
    """

    def test_project_layer_layered_uses_project_kind_dir(self, tmp_path: Path) -> None:
        candidate = _resolve_layer_candidate(
            "project", tmp_path, ArtifactKind.DIRECTIVE, "doctrine/directives", layered=True
        )
        assert candidate == tmp_path / "doctrine" / "directive"

    def test_org_layer_layered_delegates_to_org_layer_resolver(self, tmp_path: Path) -> None:
        # No flat ``tmp_path/directives`` dir exists, so the org resolver's
        # nested-layout fallback applies (see ``_resolve_org_layer_dir``).
        candidate = _resolve_layer_candidate(
            "org", tmp_path, ArtifactKind.DIRECTIVE, "doctrine/directives", layered=True
        )
        assert candidate == tmp_path / "doctrine/directives" / "org"

    def test_built_in_layer_layered_delegates_to_built_in_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        sentinel = tmp_path / "sentinel-built-in"
        monkeypatch.setattr(
            "charter.activation.pack_manager.built_in_dir", lambda kind: sentinel if kind is ArtifactKind.DIRECTIVE else None
        )
        candidate = _resolve_layer_candidate(
            "built-in", tmp_path, ArtifactKind.DIRECTIVE, "doctrine/directives", layered=True
        )
        assert candidate == sentinel

    def test_layered_without_kind_falls_back_to_generic_join(self, tmp_path: Path) -> None:
        """Defensive branch: ``_scan_layout_for`` never actually returns
        ``layered=True`` with ``kind is None`` today (``kind is None`` implies
        the flat ``mission-type`` layout), but the pre-extraction code carried
        this fallback and the refactor must not silently drop it.
        """
        candidate = _resolve_layer_candidate(
            "org", tmp_path, None, "some/base/dir", layered=True
        )
        assert candidate == tmp_path / "some/base/dir" / "org"

    def test_flat_built_in_layer_uses_missions_root(self, tmp_path: Path) -> None:
        candidate = _resolve_layer_candidate(
            "built-in", tmp_path, None, "missions/mission_types", layered=False
        )
        from charter.offering.missions.repository import MissionTemplateRepository

        assert candidate == MissionTemplateRepository.default_missions_root() / "mission_types"

    def test_flat_kind_org_layer_resolves_to_pack_root_mission_types(self, tmp_path: Path) -> None:
        """FR-003: an org pack's flat mission-type roster lives at
        ``<org_pack_root>/mission_types/`` (CL-005). This supersedes the
        pre-FR-003 ``else: continue`` behaviour this test used to pin — a
        flat (``layered=False``) kind in the org layer now resolves to a real
        directory instead of ``None``. See
        ``docs/adr/3.x/2026-08-13-1-mission-type-roster-layering-seam.md``."""
        candidate = _resolve_layer_candidate(
            "org", tmp_path, None, "missions/mission_types", layered=False
        )
        assert candidate == tmp_path / "mission_types"

    def test_flat_kind_project_layer_resolves_to_kittify_missions_mission_types(
        self, tmp_path: Path
    ) -> None:
        """FR-005: a project's flat mission-type roster lives at
        ``.kittify/missions/mission_types/`` — a flat sibling of, not nested
        inside, ``.kittify/missions/<mission_name>/`` (CL-005). ``root`` here
        is already ``repo_root / ".kittify"`` (see
        ``specify_cli.cli.commands.charter._layer_roots.resolve_layer_roots``).
        This supersedes the pre-FR-003/FR-005 ``else: continue`` behaviour
        this test used to pin — a flat (``layered=False``) kind in the
        project layer now resolves to a real directory instead of ``None``."""
        candidate = _resolve_layer_candidate(
            "project", tmp_path, None, "missions/mission_types", layered=False
        )
        assert candidate == tmp_path / "missions" / "mission_types"
