"""WP06: charter-cascade exhaustiveness for the ``template``/``asset`` kinds.

WP01 added ``ArtifactKind.TEMPLATE`` and ``ArtifactKind.ASSET`` plus the
canonical ``_NON_AUGMENTATION_ELIGIBLE_KINDS`` exclusion set. This module
asserts every owned charter-layer surface handles both new members without
raising ``KeyError`` (or any other crash) and without silently dropping
behaviour it shouldn't. It also carries the **direct** regression test for
``charter/context.py:500`` — a bare-probe comprehension the totality guard
(WP07) cannot see because it filters via a comprehension, not a lookup table.

Covered surfaces (one test class per owned module):
- ``charter.activation.context._render_generic_artifact_include`` (T022, headline)
- ``charter.activation.pack_manager`` (``YAML_KEY_MAP``, ``_PROJECT_KIND_DIRS``,
  ``_ID_FIELD_BY_KIND``) (T023)
- ``charter.activation.kind_vocabulary`` (``_PROJECT_KIND_DIRS``, ``_ID_FIELD_BY_KIND``,
  ``resolve_artifact_urn`` / ``resolve_config_id``) (T023)
- ``charter.activation.synthesizer.project_drg`` (``_node_kind_for``,
  ``emit_project_layer``) (T024)
- ``charter.activation.consistency_check`` (re-exported ``YAML_KEY_MAP``) (T024)
- ``charter.activation._activation_render`` (``_singular_kind``, ``_infer_kind``) (T024)
- ``specify_cli.cli.commands.charter.list_cmd`` (``_KIND_ORDER``) (T025)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import charter.activation.context as context_mod
from charter.activation._activation_render import _infer_kind, _singular_kind
from charter.activation.context_renderers import template_include as template_include_mod
from charter.activation.consistency_check import YAML_KEY_MAP as CONSISTENCY_YAML_KEY_MAP
from charter.activation.kind_vocabulary import (
    UnknownArtifactIdError,
    _ID_FIELD_BY_KIND as KV_ID_FIELD_BY_KIND,
    _PROJECT_KIND_DIRS as KV_PROJECT_KIND_DIRS,
    resolve_artifact_urn,
    resolve_config_id,
)
from charter.activation.pack_manager import (
    YAML_KEY_MAP,
    _ID_FIELD_BY_KIND as PM_ID_FIELD_BY_KIND,
    _PROJECT_KIND_DIRS as PM_PROJECT_KIND_DIRS,
)
from charter.activation.cascade import CascadeScope, cascade_activation_targets
from charter.activation.synthesizer.project_drg import _node_kind_for, emit_project_layer
from charter.activation.synthesizer.request import SynthesisTarget
from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_KINDS,
    ArtifactKind,
    _NON_AUGMENTATION_ELIGIBLE_KINDS,
)
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from specify_cli.cli.commands.charter.list_cmd import _KIND_ORDER

pytestmark = [pytest.mark.unit]

_NEW_KINDS = (ArtifactKind.TEMPLATE, ArtifactKind.ASSET)
_NEW_KIND_TOKENS = tuple(kind.operator_token for kind in _NEW_KINDS)


# ---------------------------------------------------------------------------
# T022 (headline): context.py:500 bare-probe filter excludes ASSET + TEMPLATE
# ---------------------------------------------------------------------------


class TestContextGenericArtifactIncludeExcludesNonBareProbeableKinds:
    """Direct test for the comprehension at ``charter/context.py:500``.

    This is a comprehension filter, not a lookup-table crash — the WP07
    totality guard cannot see it. It must exclude every member of
    :data:`charter.offering.artifact_kinds._NON_AUGMENTATION_ELIGIBLE_KINDS`
    (currently ``TEMPLATE`` and ``ASSET``), not just a private
    ``is not ArtifactKind.TEMPLATE`` check.
    """

    def test_asset_and_template_never_bare_probed(self, monkeypatch):
        queried_kinds: list[str] = []

        def _fake_directive_include(service, identifier, selector):
            queried_kinds.append("directive")
            raise ValueError("no directive")

        def _fake_tactic_include(service, identifier, selector):
            queried_kinds.append("tactic")
            raise ValueError("no tactic")

        def _fake_doctrine_artifact_include(service, kind, identifier):
            queried_kinds.append(kind)
            return None

        # WP05 (#2532): ``_render_generic_artifact_include`` relocated to
        # ``context_renderers/template_include.py``; it resolves its three
        # collaborators through ITS OWN module globals (bare name
        # references), so the patch target must follow the code, not stay
        # on ``charter.activation.context`` (which merely re-exports these names for
        # FR-009 test-import preservation and the orchestrator's own calls).
        monkeypatch.setattr(
            template_include_mod, "_render_directive_include", _fake_directive_include
        )
        monkeypatch.setattr(
            template_include_mod, "_render_tactic_include", _fake_tactic_include
        )
        monkeypatch.setattr(
            template_include_mod,
            "_render_doctrine_artifact_include",
            _fake_doctrine_artifact_include,
        )

        # Stub service exposing the `.directives`/`.tactics` repositories the
        # probe reads at the call site. (doctrine-delivery-activation WP04
        # narrowed _render_directive_include/_render_tactic_include to take the
        # repository directly, so `service.directives`/`service.tactics` is now
        # evaluated at the call site — before the monkeypatched includes — so a
        # bare `object()` no longer suffices. The fakes ignore the value;
        # production always passes a full ActiveCharterService.)
        _probe_service = SimpleNamespace(directives=object(), tactics=object())
        with pytest.raises(ValueError, match="No artifact found"):
            context_mod._render_generic_artifact_include(_probe_service, "some-id")

        queried = set(queried_kinds)
        assert "template" not in queried
        assert "asset" not in queried

        # The candidate set queried is EXACTLY the canonical
        # non-excluded universe — proves the filter routes through
        # _NON_AUGMENTATION_ELIGIBLE_KINDS, not a private single-member check.
        expected = {
            member.value
            for member in ArtifactKind
            if member not in _NON_AUGMENTATION_ELIGIBLE_KINDS
        }
        assert queried == expected
        assert ArtifactKind.TEMPLATE.value not in expected  # sanity
        assert ArtifactKind.ASSET.value not in expected  # sanity


# ---------------------------------------------------------------------------
# T023: pack_manager.py + kind_vocabulary.py partials stay None-safe
# ---------------------------------------------------------------------------


class TestPackManagerHandlesNewKinds:
    def test_yaml_key_map_excludes_template_and_asset(self):
        for token in _NEW_KIND_TOKENS:
            assert token not in YAML_KEY_MAP

    @pytest.mark.parametrize("kind", _NEW_KINDS)
    def test_project_kind_dirs_get_is_none_safe(self, kind):
        # No raising access: .get with a fallback never raises for an
        # unregistered ArtifactKind member.
        assert PM_PROJECT_KIND_DIRS.get(kind, kind.plural) == kind.plural

    @pytest.mark.parametrize("kind", _NEW_KINDS)
    def test_id_field_by_kind_get_is_none_safe(self, kind):
        assert PM_ID_FIELD_BY_KIND.get(kind, "id") == "id"


class TestKindVocabularyHandlesNewKinds:
    @pytest.mark.parametrize("kind", _NEW_KINDS)
    def test_project_kind_dirs_get_is_none_safe(self, kind):
        assert KV_PROJECT_KIND_DIRS.get(kind, kind.plural) == kind.plural

    @pytest.mark.parametrize("kind", _NEW_KINDS)
    def test_id_field_by_kind_get_is_none_safe(self, kind):
        assert KV_ID_FIELD_BY_KIND.get(kind, "id") == "id"

    @pytest.mark.parametrize("kind", _NEW_KINDS)
    def test_resolve_artifact_urn_raises_documented_error_not_a_crash(
        self, kind, tmp_path: Path
    ):
        # No artifacts exist under the empty doctrine_root; the resolver must
        # surface the documented UnknownArtifactIdError, never a raw KeyError
        # or AttributeError.
        with pytest.raises(UnknownArtifactIdError):
            resolve_artifact_urn(kind, "some-config-id", doctrine_root=tmp_path)

    def test_resolve_config_id_handles_asset_urn_without_crash(self, tmp_path: Path):
        with pytest.raises(UnknownArtifactIdError):
            resolve_config_id("asset:some-id", doctrine_root=tmp_path)

    def test_resolve_config_id_handles_template_urn_without_crash(
        self, tmp_path: Path
    ):
        with pytest.raises(UnknownArtifactIdError):
            resolve_config_id("template:some-id", doctrine_root=tmp_path)


# ---------------------------------------------------------------------------
# T024: project_drg._KIND_TO_NODE_KIND is .get-based; consistency_check /
# _activation_render don't crash or drop for template/asset.
# ---------------------------------------------------------------------------


class TestProjectDrgNodeKindForIsGetBased:
    @pytest.mark.parametrize("token", _NEW_KIND_TOKENS)
    def test_unsupported_kind_resolves_to_none_not_raise(self, token):
        assert _node_kind_for(token) is None

    @pytest.mark.parametrize("token", _NEW_KIND_TOKENS)
    def test_emit_project_layer_skips_unsupported_kind_target(self, token):
        target = SynthesisTarget(
            kind=token,
            slug=f"project-{token}-example",
            title=f"Example {token}",
            artifact_id=f"example-{token}",
            source_section="testing_philosophy",
        )
        shipped = DRGGraph(
            schema_version="1.0",
            generated_at="2026-07-09T00:00:00+00:00",
            generated_by="test-shipped-layer",
            nodes=[],
            edges=[],
        )

        # Must not raise: an unsupported target kind is skipped, not a crash.
        graph = emit_project_layer([target], "0.1.0", shipped)

        assert graph.nodes == []
        assert graph.edges == []


class TestConsistencyCheckExcludesNewKinds:
    def test_yaml_key_map_reexport_excludes_template_and_asset(self):
        for token in _NEW_KIND_TOKENS:
            assert token not in CONSISTENCY_YAML_KEY_MAP


class TestActivationRenderHandlesNewKinds:
    @pytest.mark.parametrize("plural", ["templates", "assets"])
    def test_singular_kind_unknown_plural_returned_unchanged(self, plural):
        # Documented behaviour: unknown plurals fall through unchanged so a
        # future kind addition doesn't crash the renderer.
        assert _singular_kind(plural) == plural

    def test_infer_kind_does_not_crash_when_service_lacks_new_kind_repos(self):
        class _FakeService:
            """A service exposing only the eight canonical repositories."""

            directives = None
            tactics = None
            styleguides = None
            toolguides = None
            paradigms = None
            procedures = None
            agent_profiles = None
            mission_step_contracts = None

        # No repo claims the id; must return None, not raise.
        assert _infer_kind("some-template-or-asset-id", _FakeService()) is None


# ---------------------------------------------------------------------------
# T025: list_cmd._KIND_ORDER excludes template/asset
# ---------------------------------------------------------------------------


class TestListCmdKindOrderExcludesNewKinds:
    def test_kind_order_excludes_template_and_asset(self):
        for token in _NEW_KIND_TOKENS:
            assert token not in _KIND_ORDER


# ---------------------------------------------------------------------------
# T004 (WP01, #2829): the cascade candidate filter is driven by the canonical
# CHARTER_ACTIVATABLE_KINDS set — template/asset never flow through as cascade
# candidates while every activatable kind does. ADR 2026-08-20-1.
# ---------------------------------------------------------------------------


def _one_of_each_kind_graph(source_urn: str, relation: Relation) -> DRGGraph:
    """A source referencing exactly one node of every ArtifactKind via *relation*.

    Each ``ArtifactKind`` member shares its value with the matching ``NodeKind``
    member, so a well-formed ``<kind>:ex-<kind>`` URN node exists for each. The
    cascade must admit exactly the ``CHARTER_ACTIVATABLE_KINDS`` and drop the two
    non-activatable kinds (``template``, ``asset``).
    """
    nodes = [DRGNode(urn=source_urn, kind=NodeKind.AGENT_PROFILE)]
    edges: list[DRGEdge] = []
    for kind in ArtifactKind:
        target = f"{kind.value}:ex-{kind.value}"
        nodes.append(DRGNode(urn=target, kind=NodeKind(kind.value)))
        edges.append(DRGEdge(source=source_urn, target=target, relation=relation))
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-08-20T00:00:00+00:00",
        generated_by="test-kind-complete-filter",
        nodes=nodes,
        edges=edges,
    )


class TestCascadeCandidateFilterIsCharterActivatableDriven:
    """The cascade candidate filter is ``kind in CHARTER_ACTIVATABLE_KINDS``.

    A self-mutation-style guard: a source references one node of *every*
    ``ArtifactKind`` through a followed relation; the activated buckets must equal
    exactly the ``CHARTER_ACTIVATABLE_KINDS`` value set — proving ``template`` and
    ``asset`` (the two non-activatable kinds) never flow through while every
    activatable kind does. Driven by the canonical set, not a per-kind literal.
    """

    def test_requires_edges_admit_exactly_the_activatable_kinds(self) -> None:
        graph = _one_of_each_kind_graph("agent_profile:filter-src", Relation.REQUIRES)
        result = cascade_activation_targets(
            graph, "agent_profile:filter-src", CascadeScope.all()
        )
        assert set(result.activated) == {kind.value for kind in CHARTER_ACTIVATABLE_KINDS}
        assert ArtifactKind.TEMPLATE.value not in result.activated
        assert ArtifactKind.ASSET.value not in result.activated
        # Every activatable kind flows through (no silent drop).
        for kind in CHARTER_ACTIVATABLE_KINDS:
            assert kind.value in result.activated

    def test_scope_edges_are_followed_and_filtered_identically(self) -> None:
        # SCOPE joined the followed set (T002); candidacy is filtered by the same
        # canonical membership test regardless of which followed relation reached
        # the node.
        graph = _one_of_each_kind_graph("agent_profile:scope-src", Relation.SCOPE)
        result = cascade_activation_targets(
            graph, "agent_profile:scope-src", CascadeScope.all()
        )
        assert set(result.activated) == {kind.value for kind in CHARTER_ACTIVATABLE_KINDS}
        assert ArtifactKind.TEMPLATE.value not in result.activated
        assert ArtifactKind.ASSET.value not in result.activated
