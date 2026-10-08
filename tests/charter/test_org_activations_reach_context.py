"""FR-005 durable regression invariant — org-pack activations reach the
charter-context bootstrap text stanza (WP01, closes #2365).

This is the anti-recurrence guard for the "merged-but-never-rendered"
class (#1465, #1242, #2365): ``OrgCharterPolicy.activations`` is parsed,
schema-validated, and folded across the ``extends:`` chain by
``_fold_policies`` — and then historically discarded, because no runtime
consumer read the folded list. This test exercises the REAL,
pre-existing bootstrap entry point end-to-end, in bootstrap mode, with a
real org pack on disk — the forbidden red-first seams
(``render_activation_stanza`` / ``resolve_for_context`` / any direct
``ActivationEntry``-list construction, and the compact/``advise``
dispatch path) are never touched (NFR-001).

Harness note (post-tasks squad fold #4): reuse ONLY ``_write_config``
from ``tests.charter.test_context_org_governance`` — its sibling
``_write_org_pack`` writes an *agent-profile* pack and cannot carry
``activations:``, so this module writes its own ``org-charter.yaml``.
"""

from __future__ import annotations

import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.context import build_charter_context
from charter.offering.drg.models import DRGGraph
from tests.charter.test_context_org_governance import _write_config

pytestmark = pytest.mark.fast


# A distinctive artifact id that can only have reached the stanza via the
# org pack's ``activations:`` block (no project-local activations exist).
_ORG_ACTIVATION_ARTIFACT_ID = "orgzilla-caveman-comments-2365"
_ORG_ACTIVATION_PACK_ID = "orgzilla-governance-pack"

_ORG_CHARTER_WITH_ACTIVATIONS = textwrap.dedent(
    f"""\
    activations:
      - activation_context:
          mission_type: software-dev
          action: implement
        charter_pack_id: {_ORG_ACTIVATION_PACK_ID}
        artifact_id: {_ORG_ACTIVATION_ARTIFACT_ID}
        artifact_kind: styleguides
    """
)

_CHARTER_MD = textwrap.dedent(
    """\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    """
)

# No project-local ``activations:`` block — the org entry must reach the
# stanza purely through the resolve-time union (SC-001).
_GOVERNANCE_YAML = textwrap.dedent(
    """\
    doctrine:
      template_set: software-dev-default
      selected_paradigms: []
      selected_directives: []
      available_tools: []
    """
)

_MINIMAL_GRAPH_YAML = textwrap.dedent(
    """\
    schema_version: "1.0"
    generated_at: "2026-04-13T10:00:00+00:00"
    generated_by: "test"
    nodes:
      - urn: "action:software-dev/implement"
        kind: action
        label: implement
    edges: []
    """
)


def _write_project_fixture(repo_root: Path) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")


def _write_org_pack_with_activations(repo_root: Path) -> Path:
    pack_root = repo_root / "org-packs" / _ORG_ACTIVATION_PACK_ID
    pack_root.mkdir(parents=True, exist_ok=True)
    (pack_root / "org-charter.yaml").write_text(
        _ORG_CHARTER_WITH_ACTIVATIONS, encoding="utf-8"
    )
    return pack_root


def _bootstrap_text(repo_root: Path) -> str:
    """Resolve ``build_charter_context(...).text`` in forced BOOTSTRAP mode.

    Bootstrap mode requires: an action in ``BOOTSTRAP_ACTIONS`` (we use
    ``implement``), no cached ``context-state.json`` (a fresh ``tmp_path``
    guarantees this), and ``depth >= 2`` (passed explicitly). ``mark_loaded``
    is left ``False`` so the call never writes a state cache — this is
    explicitly NOT the ``_governance_text``/``_DISPATCH_ACTION="advise"``
    compact path (that path renders no activation stanza at all).
    """
    yaml = YAML(typ="safe")
    mock_graph = _load_mock_graph(yaml)

    with (
        patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_offering_root", return_value=repo_root),
        patch("charter.offering.drg.validator.assert_valid"),
        patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None),
    ):
        result = build_charter_context(
            repo_root, action="implement", depth=2, mark_loaded=False,
            mission_type="software-dev",
        )
    assert result.mode == "bootstrap", (
        f"expected bootstrap mode, got {result.mode!r} — the entry point "
        "must be forced into bootstrap for NFR-001 to hold"
    )
    return str(result.text)


def _load_mock_graph(yaml: YAML) -> DRGGraph:
    return DRGGraph.model_validate(yaml.load(StringIO(_MINIMAL_GRAPH_YAML)))


class TestOrgActivationsReachBootstrapContext:
    """SC-001 / FR-005: org-declared activations reach the text stanza."""

    def test_org_declared_activation_appears_in_selected_activations_stanza(
        self, tmp_path: Path
    ) -> None:
        """Given an org pack activation and NO project-local activations,
        the org entry appears in the ``Selected activations:`` stanza of
        ``build_charter_context(...).text`` resolved in bootstrap mode."""
        repo = tmp_path / "consumer"
        repo.mkdir()
        _write_project_fixture(repo)
        pack_root = _write_org_pack_with_activations(repo)
        _write_config(repo, pack_root, activated=None)

        text = _bootstrap_text(repo)

        assert "Selected activations:" in text, (
            "no activation stanza rendered at all — the org union never "
            "reached _render_activation_block"
        )
        assert _ORG_ACTIVATION_ARTIFACT_ID in text, (
            "the org pack's activations: entry did not surface in the "
            "rendered stanza (the merged-but-never-rendered class, "
            "#1465/#1242/#2365)"
        )
        assert f"styleguide:{_ORG_ACTIVATION_ARTIFACT_ID}" in text
