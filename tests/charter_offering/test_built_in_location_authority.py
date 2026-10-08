"""T004 — the two built-in location authorities (WP01, contract C1.1-C1.6).

Covers :func:`charter.offering.pack_paths.built_in_root` and
:func:`charter.offering.pack_paths.built_in_dir`: positive resolution for a shipped
content-dir kind, the derived 3-kind carve-out raise, and proof that the
carve-out is *computed* from :attr:`~charter.offering.artifact_kinds.ArtifactKind.
has_built_in_content_dir` rather than hand-listed in ``pack_paths.py``
(FR-001 / FR-001b / FR-005 / NFR-005).

Also pins the two caller-tier slices this WP routes through the authorities:
the 9 doctrine-repository defaults (``built_in_dir``) and the 2 DRG root
callers (``built_in_root``) -- both must resolve identically to a direct call
to the authority, proving no residual hand-composed
``resolve_pack_root("built-in") / ...`` join remains outside ``pack_paths.py``.
"""

from __future__ import annotations

import pytest

from charter.offering import artifact_kinds, pack_paths
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import (
    BuiltInContentDirNotAvailable,
    built_in_dir,
    built_in_root,
    resolve_pack_root,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]

#: The 9 shipped content-dir kinds (mirrors the WP01 SSOT in artifact_kinds.py).
_CONTENT_DIR_KINDS = (
    ArtifactKind.AGENT_PROFILE,
    ArtifactKind.ASSET,
    ArtifactKind.DIRECTIVE,
    ArtifactKind.GLOSSARY_PACK,
    ArtifactKind.PARADIGM,
    ArtifactKind.PROCEDURE,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TACTIC,
    ArtifactKind.TOOLGUIDE,
)

#: The derived 3-kind carve-out (C1.4) -- kinds with NO built-in content dir.
_CARVE_OUT_KINDS = (
    ArtifactKind.MISSION_STEP_CONTRACT,
    ArtifactKind.TEMPLATE,
    ArtifactKind.ANTI_PATTERN,
)


class TestBuiltInRoot:
    def test_returns_the_built_in_pack_root(self) -> None:
        # C1.6: built_in_root() is exactly resolve_pack_root("built-in").
        assert built_in_root() == resolve_pack_root("built-in")

    def test_root_exists_on_disk(self) -> None:
        assert built_in_root().is_dir()


class TestBuiltInDirPositive:
    @pytest.mark.parametrize("kind", _CONTENT_DIR_KINDS)
    def test_shipped_kind_resolves_under_the_pack_root(self, kind: ArtifactKind) -> None:
        # C1.1/C3.2: asserted through resolve_pack_root(...), not a raw
        # repo-relative .exists() (cf. #3036).
        expected = resolve_pack_root("built-in") / kind.plural
        resolved = built_in_dir(kind)
        assert resolved == expected
        assert resolved.is_dir()

    def test_agent_profiles_set_is_non_empty(self) -> None:
        # C3.3 anti-vacuity: a stale/empty root must fail loudly, not pass vacuously.
        profiles_dir = built_in_dir(ArtifactKind.AGENT_PROFILE)
        assert any(profiles_dir.glob("*.agent.yaml"))


class TestBuiltInDirCarveOut:
    @pytest.mark.parametrize("kind", _CARVE_OUT_KINDS)
    def test_carve_out_kind_raises_named_error(self, kind: ArtifactKind) -> None:
        # C1.4: named error, no silent join to a non-existent directory.
        with pytest.raises(BuiltInContentDirNotAvailable) as excinfo:
            built_in_dir(kind)
        assert excinfo.value.kind is kind
        assert kind.name in str(excinfo.value)

    def test_carve_out_is_exactly_the_three_documented_kinds(self) -> None:
        assert frozenset(_CARVE_OUT_KINDS) == frozenset(
            {ArtifactKind.MISSION_STEP_CONTRACT, ArtifactKind.TEMPLATE, ArtifactKind.ANTI_PATTERN}
        )


class TestCarveOutIsComputedNotHandListed:
    """NFR-005: the complement in ``built_in_dir`` must be *derived* from
    :attr:`ArtifactKind.has_built_in_content_dir`, never a literal ``{...}``
    set living in ``pack_paths.py``. Proven by flipping the backing SSOT for
    one kind and observing ``built_in_dir``'s outcome change accordingly --
    a hand-listed complement in ``pack_paths.py`` could not react to this.
    """

    def test_flipping_template_to_true_stops_the_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(artifact_kinds._HAS_BUILT_IN_CONTENT_DIR, "template", True)
        # No raise now -- proves built_in_dir reads the live attribute, not a
        # separately hand-listed set in pack_paths.py.
        resolved = built_in_dir(ArtifactKind.TEMPLATE)
        assert resolved == resolve_pack_root("built-in") / ArtifactKind.TEMPLATE.plural

    def test_flipping_directive_to_false_starts_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(artifact_kinds._HAS_BUILT_IN_CONTENT_DIR, "directive", False)
        with pytest.raises(BuiltInContentDirNotAvailable):
            built_in_dir(ArtifactKind.DIRECTIVE)

    def test_pack_paths_source_has_no_literal_carve_out_set(self) -> None:
        """Belt-and-braces AST check: no ``{...}``/``frozenset({...})`` literal
        in ``pack_paths.py`` names any :class:`ArtifactKind` member. Only the
        *code* is scanned (comments/docstrings are prose, not a hand-listed
        set, so they are irrelevant to this guard).
        """
        import ast

        source_path = pack_paths.__file__
        assert source_path is not None
        with open(source_path, encoding="utf-8") as fh:  # noqa: PTH123 - reading own module source
            tree = ast.parse(fh.read())

        kind_names = {kind.name for kind in ArtifactKind}
        offending_literals: list[ast.Set] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Set):
                continue
            for element in node.elts:
                if isinstance(element, ast.Attribute) and element.attr in kind_names:
                    offending_literals.append(node)
                    break

        assert not offending_literals, (
            "pack_paths.py must not hand-list ArtifactKind members in a set "
            "literal -- the carve-out must be derived from "
            "ArtifactKind.has_built_in_content_dir (NFR-005)."
        )


class TestRepositoryDefaultsRouteThroughAuthority:
    """T002: all 9 repository defaults call ``built_in_dir(kind)`` -- proven by
    equality with a direct authority call, not by re-deriving the join.
    """

    @pytest.mark.parametrize(
        ("repo_cls_path", "kind"),
        [
            ("charter.offering.agent_profiles.repository.AgentProfileRepository", ArtifactKind.AGENT_PROFILE),
            ("charter.offering.assets.repository.AssetRepository", ArtifactKind.ASSET),
            ("charter.offering.directives.repository.DirectiveRepository", ArtifactKind.DIRECTIVE),
            ("charter.offering.glossary_packs.repository.GlossaryPackRepository", ArtifactKind.GLOSSARY_PACK),
            ("charter.offering.paradigms.repository.ParadigmRepository", ArtifactKind.PARADIGM),
            ("charter.offering.procedures.repository.ProcedureRepository", ArtifactKind.PROCEDURE),
            ("charter.offering.styleguides.repository.StyleguideRepository", ArtifactKind.STYLEGUIDE),
            ("charter.offering.tactics.repository.TacticRepository", ArtifactKind.TACTIC),
            ("charter.offering.toolguides.repository.ToolguideRepository", ArtifactKind.TOOLGUIDE),
        ],
    )
    def test_default_built_in_dir_matches_authority(self, repo_cls_path: str, kind: ArtifactKind) -> None:
        module_path, _, cls_name = repo_cls_path.rpartition(".")
        import importlib

        module = importlib.import_module(module_path)
        repo_cls = getattr(module, cls_name)
        assert repo_cls._default_built_in_dir() == built_in_dir(kind)


class TestDRGRootCallersRouteThroughAuthority:
    """T003: the 2 DRG root callers resolve via ``built_in_root()``."""

    def test_loader_built_in_graph_source_matches_authority(self) -> None:
        from charter.offering.drg.loader import built_in_graph_source

        assert built_in_graph_source() == built_in_root()

    def test_extractor_artifacts_root_matches_authority_for_package_root(self) -> None:
        from charter.offering.drg.migration.extractor import _artifacts_root
        from charter.offering.pack_paths import offering_package_dir

        doctrine_pkg_dir = offering_package_dir()
        assert doctrine_pkg_dir is not None
        assert _artifacts_root(doctrine_pkg_dir) == built_in_root()

    def test_extractor_uses_the_shared_offering_package_dir_function(self) -> None:
        """The extractor imports :func:`charter.offering.pack_paths.offering_package_dir`
        rather than carrying its own byte-identical copy (FOLD 5 dedup,
        mission ``doctrine-built-in-seam-consolidation-01KYW3TX``).

        Asserts the bound name in the extractor module IS (identity, not just
        equal-valued) the ``pack_paths`` function -- the strongest proof the
        duplicate definition was deleted rather than merely made to agree.
        """
        from charter.offering.drg.migration import extractor
        from charter.offering.pack_paths import offering_package_dir

        assert extractor.offering_package_dir is offering_package_dir
        assert not hasattr(extractor, "_doctrine_package_dir")
