"""FR-006 shared org-charter document reader (``_iter_org_charter_docs``).

Two jobs live in this module (T003):

1. A **characterization test** pinning the CURRENT (pre-refactor)
   behavior of ``_read_org_required_selections`` / the org-union branch
   of ``_load_doctrine_selection`` (``charter/context.py:795-813``) —
   this branch had ZERO existing coverage before WP01 (the sibling
   ``test_org_charter_union.py`` covers a *different* function,
   ``charter.activation.org_charter.apply_org_charter_to_interview``).
   This test is authored and passes GREEN against pre-refactor code; it
   is the safety net that makes the T005 extraction of
   ``_iter_org_charter_docs`` provably behavior-preserving — it MUST
   stay green, unmodified in intent, through that refactor.
2. Direct unit tests of the extracted ``_iter_org_charter_docs(repo_root)``
   reader itself (added once T005 lands), so the shared reader has its
   own focused coverage independent of the two callers that consume it
   (``_read_org_required_selections`` for ``required_<kind>``,
   ``_read_org_activations`` for ``activations:``).
"""

from __future__ import annotations

import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.context import build_charter_context

pytestmark = pytest.mark.fast


_CHARTER_MD = textwrap.dedent(
    """\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    """
)

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
      - urn: "directive:DIRECTIVE_039"
        kind: directive
        label: Lynn Cole Engineering Culture
    edges: []
    """
)


def _write_project_fixture(repo_root: Path) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")


def _register_org_pack(repo_root: Path, pack_root: Path, *, name: str = "security") -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(
            {
                # WP04 (C-A1): PackContext.from_config fail-closes without
                # this key; unrelated to the org-pack union this fixture
                # exercises, so no other activation key is written.
                "mission_type_activations": ["software-dev"],
                "charter_packs": {"org": {"packs": [{"name": name, "local_path": str(pack_root)}]}},
            },
            fh,
        )


def _load_mock_graph() -> object:
    from charter.offering.drg.models import DRGGraph

    yaml = YAML(typ="safe")
    return DRGGraph.model_validate(yaml.load(StringIO(_MINIMAL_GRAPH_YAML)))


class TestRequiredKindUnionCharacterization:
    """Safety net for T005: pins the pre-refactor ``required_<kind>`` org union."""

    def test_org_required_directives_reach_selected_directives_stanza(
        self, tmp_path: Path
    ) -> None:
        """Golden-master: an org pack's ``required_directives:`` entry
        already surfaces in the ``Selected directives:`` stanza via the
        ``_read_org_required_selections`` -> ``_load_doctrine_selection``
        union, with NO project-local mirroring. This must stay green,
        unchanged, through the T005 ``_iter_org_charter_docs``
        extraction (pure move, no semantic change)."""
        repo = tmp_path / "consumer"
        repo.mkdir()
        _write_project_fixture(repo)

        org_pack = repo / "org-pack"
        org_pack.mkdir()
        (org_pack / "org-charter.yaml").write_text(
            "required_directives:\n  - DIRECTIVE_039\n",
            encoding="utf-8",
        )
        _register_org_pack(repo, org_pack)

        mock_graph = _load_mock_graph()
        with (
            patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
            patch("charter.activation.catalog.resolve_doctrine_root", return_value=repo),
            patch("charter.offering.drg.validator.assert_valid"),
            patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None),
        ):
            result = build_charter_context(repo, action="implement", depth=2, mark_loaded=False)

        assert result.mode == "bootstrap"
        assert "Selected directives:" in result.text
        assert "DIRECTIVE_039" in result.text
