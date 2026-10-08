"""FR-002 red-first regression test: ``_org_scan_dirs`` must scan the real,
flat org-pack layout so that ``charter activate`` on an org pack's own
artifact actually survives ``filter_graph_by_activation`` (issue #3385).

The defect (spec.md, verified at checkout HEAD ``ab0a0b9b5``):
``charter.activation.kind_vocabulary._org_scan_dirs`` (``src/charter/activation/kind_vocabulary.py:200-209``)
scans only ``<org_root>/<plural>/built-in/`` -- a layout no real org pack
uses. A flat-layout org pack (``<org_root>/<plural>/``, no ``built-in/``
segment -- the documented, live-loader-matching layout) therefore
contributes zero scan directories, ``resolve_artifact_urn`` raises
``UnknownArtifactIdError``, and that exception is swallowed by
``_resolve_activated_urns_for_kind`` (``src/charter/drg.py:379-380``,
``except UnknownArtifactIdError: continue``) -- so the org artifact's URN
never enters the resolved-URN set and ``_node_is_activated``'s step-3 gate
(``src/charter/drg.py:467-473``) silently drops the node from the filtered
graph. ``charter activate`` reports success while quietly failing to do the
one thing the operator asked for.

This module proves the defect (and, post-fix, its closure) at the level a
real operator experiences it: the full ``activate()`` ->
``filter_graph_by_activation()`` round trip, never a direct
``resolve_artifact_urn()`` call (that unit-level shape is FR-003's job, in
``tests/charter/test_kind_vocabulary_scan_roots.py``).

Pre-fix, the primary test below (Acceptance Scenario 1) must be observed
failing with the org directive's node **absent** from
``filter_graph_by_activation``'s output -- never an ``UnknownArtifactIdError``,
because ``_resolve_activated_urns_for_kind`` swallows that exception before it
can propagate out of the round trip (see the Red-First Discipline section of
this mission's ``plan.md`` / the WP01 task file for the full argument).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation._drg_helpers import load_validated_graph
from charter.activation.activation_engine import commit_plan, plan_activation
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.pack_context import PackContext

pytestmark = pytest.mark.fast

_ORG_DIRECTIVE_STEM = "org-scan-dirs-fixture-directive"
_ORG_DIRECTIVE_ID = "ORG_SCAN_DIRS_FIXTURE_DIRECTIVE"
_ORG_DIRECTIVE_URN = f"directive:{_ORG_DIRECTIVE_ID}"
_ORG_PACK_NAME = "org-scan-dirs-fixture-pack"

#: Real, live built-in directive -- also used as a fixture anchor by
#: ``tests/charter/test_drg_activation_gate.py``. Used here as the
#: "unrelated built-in stem" in Acceptance Scenario 5's selectivity check.
_UNRELATED_BUILT_IN_STEM = "001-architectural-integrity-standard"
_UNRELATED_BUILT_IN_URN = "directive:DIRECTIVE_001"

_ACTIVATED_DIRECTIVES_KEY = "activated_directives"


def _write_org_directive_fixture(org_root: Path) -> None:
    """Build a flat-layout org pack: no ``built-in/`` segment anywhere.

    ``<org_root>/directives/<stem>.directive.yaml`` is the artifact file
    itself; ``<org_root>/<stem>.graph.yaml`` is a root-level DRG fragment
    declaring the same directive as a graph node -- test-fixture data only
    (C-002), never a change to ``_drg_helpers.py``. ``filter_graph_by_activation``
    only ever operates on nodes already present in the merged graph, and DRG
    nodes come from ``*.graph.yaml`` fragments, never synthesized from
    ``*.directive.yaml`` artifact files -- without this fragment the test
    cannot observe the node at all, fixed or not.
    """
    directives_dir = org_root / "directives"
    directives_dir.mkdir(parents=True)
    (directives_dir / f"{_ORG_DIRECTIVE_STEM}.directive.yaml").write_text(
        f"id: {_ORG_DIRECTIVE_ID}\n",
        encoding="utf-8",
    )
    (org_root / f"{_ORG_DIRECTIVE_STEM}.graph.yaml").write_text(
        textwrap.dedent(
            f"""\
            schema_version: "1.0"
            generated_at: "2026-08-13T00:00:00Z"
            generated_by: "test"
            nodes:
              - urn: "{_ORG_DIRECTIVE_URN}"
                kind: directive
            edges: []
            """
        ),
        encoding="utf-8",
    )


def _activate_stem(
    config_path: Path,
    yaml: YAML,
    stem: str,
    *,
    yaml_key: str = _ACTIVATED_DIRECTIVES_KEY,
) -> list[str]:
    """Run the programmatic ``plan_activation`` -> ``commit_plan`` round trip.

    This is the "equivalent programmatic ``plan_activation``/``commit_activation``
    call" T001 step 5 names as an alternative to driving the ``charter activate``
    CLI end-to-end: it exercises the same single-write activation seam
    ``ActiveCharterManager.activate`` (``pack_manager.py``) delegates to, without
    needing a full ``ProjectContext``. ``ActiveCharterManager.activate``'s own
    artifact-availability check (``_resolve_org_layer_dir``) is an independent
    resolution path already unaffected by this mission's ``_org_scan_dirs`` fix
    (it already tolerates the flat layout) -- a successful ``charter activate``
    call by itself would prove nothing about the defect under test here; only
    the ``filter_graph_by_activation`` assertion below does.
    """
    config_data = (
        yaml.load(config_path.read_text(encoding="utf-8"))
        if config_path.exists()
        else {}
    ) or {}
    plan = plan_activation(
        kind="directive",
        artifact_id=stem,
        yaml_key=yaml_key,
        available_ids=[stem],
        config_data=config_data,
    )

    def _save(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

    commit_plan(config_path, config_data, plan, save=_save)
    return list(plan.new_list)


def _pack_context(
    *,
    repo_root: Path,
    org_root: Path,
    activated_directives: frozenset[str],
) -> PackContext:
    """Build the ``PackContext`` reflecting a committed activation state.

    ``pack_roots[0]`` is a deliberately unused placeholder -- the resolution
    gate sources the built-in ``doctrine_root`` from
    ``charter.activation.catalog.resolve_doctrine_root()``, never ``pack_roots[0]``
    (research.md D2 install-layout guard, see
    ``charter.drg._resolve_activated_urns_by_kind``'s own docstring); only
    ``PackContext.org_roots`` (``pack_roots[1:]``) is consumed here.
    """
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset(),
        pack_roots=(Path("/unused-built-in-placeholder"), org_root),
        org_pack_names=(_ORG_PACK_NAME,),
        repo_root=repo_root,
        activated_directives=activated_directives,
    )


class TestOrgScanDirsActivationRegression:
    """FR-002: activation-filter-level round trip for a flat-layout org pack."""

    def test_flat_layout_org_directive_survives_activation_filter(
        self, tmp_path: Path
    ) -> None:
        """Acceptance Scenario 1.

        Given a flat-layout org root and a root-level ``*.graph.yaml``
        declaring the org directive as a DRG node, when
        ``charter activate directive <org-directive-stem>`` runs for the org
        directive's own config-stem (via the ``plan_activation``/
        ``commit_plan`` round trip) and the result is passed through
        ``filter_graph_by_activation()``, the org directive's node is present
        in the output graph.
        """
        org_root = tmp_path / "org-pack"
        org_root.mkdir()
        _write_org_directive_fixture(org_root)

        yaml = YAML()
        yaml.preserve_quotes = True
        config_path = tmp_path / ".kittify" / "config.yaml"
        activated = _activate_stem(config_path, yaml, _ORG_DIRECTIVE_STEM)
        assert _ORG_DIRECTIVE_STEM in activated

        pack_context = _pack_context(
            repo_root=tmp_path,
            org_root=org_root,
            activated_directives=frozenset(activated),
        )

        # Explicit org_root=: load_validated_graph's own org_root fallback
        # (_resolve_org_root) is a permanent no-op that always returns None
        # by design -- omitting this argument would silently drop the org
        # DRG node from the merged graph regardless of the _org_scan_dirs fix.
        merged_graph = load_validated_graph(tmp_path, org_root=org_root)
        filtered = filter_graph_by_activation(merged_graph, pack_context)

        surviving_urns = {n.urn for n in filtered.nodes}
        assert _ORG_DIRECTIVE_URN in surviving_urns, (
            f"org directive node {_ORG_DIRECTIVE_URN!r} missing from "
            f"filter_graph_by_activation output: {sorted(surviving_urns)}"
        )

    def test_order_independence_and_selectivity(self, tmp_path: Path) -> None:
        """Acceptance Scenario 5.

        Activating both the org stem and an unrelated built-in stem, in
        either order, both leave the org node present -- its presence
        follows from its own stem being activated, not from what else is
        activated or in which order. Activating ONLY the unrelated built-in
        stem, without ever activating the org stem itself, does NOT surface
        the org node -- the per-artifact-ID gate's by-design selectivity
        (``src/charter/drg.py:467-473``), not something this mission changes.
        """
        org_root = tmp_path / "org-pack"
        org_root.mkdir()
        _write_org_directive_fixture(org_root)
        merged_graph = load_validated_graph(tmp_path, org_root=org_root)

        def _surviving_urns(activated: frozenset[str]) -> set[str]:
            pack_context = _pack_context(
                repo_root=tmp_path,
                org_root=org_root,
                activated_directives=activated,
            )
            filtered = filter_graph_by_activation(merged_graph, pack_context)
            return {n.urn for n in filtered.nodes}

        yaml = YAML()
        yaml.preserve_quotes = True

        # Order A: org stem activated first, then the unrelated built-in stem.
        config_a = tmp_path / "order-a" / ".kittify" / "config.yaml"
        _activate_stem(config_a, yaml, _ORG_DIRECTIVE_STEM)
        activated_a = _activate_stem(config_a, yaml, _UNRELATED_BUILT_IN_STEM)
        urns_a = _surviving_urns(frozenset(activated_a))
        assert _ORG_DIRECTIVE_URN in urns_a
        assert _UNRELATED_BUILT_IN_URN in urns_a

        # Order B: unrelated built-in stem activated first, then the org stem.
        config_b = tmp_path / "order-b" / ".kittify" / "config.yaml"
        _activate_stem(config_b, yaml, _UNRELATED_BUILT_IN_STEM)
        activated_b = _activate_stem(config_b, yaml, _ORG_DIRECTIVE_STEM)
        urns_b = _surviving_urns(frozenset(activated_b))
        assert _ORG_DIRECTIVE_URN in urns_b
        assert _UNRELATED_BUILT_IN_URN in urns_b

        # Selectivity: only the unrelated built-in stem is ever activated --
        # the org stem itself never is -- so the org node must stay absent.
        config_c = tmp_path / "order-c" / ".kittify" / "config.yaml"
        activated_c = _activate_stem(config_c, yaml, _UNRELATED_BUILT_IN_STEM)
        urns_c = _surviving_urns(frozenset(activated_c))
        assert _UNRELATED_BUILT_IN_URN in urns_c
        assert _ORG_DIRECTIVE_URN not in urns_c
