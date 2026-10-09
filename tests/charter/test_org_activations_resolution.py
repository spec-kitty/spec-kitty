"""SC-002/SC-003 — org∪project activation union, dedup, and validation.

Covers the resolve-time union semantics FR-001/FR-002/FR-004 add on top
of the FR-005 durable invariant proven in
``test_org_activations_reach_context.py``:

* SC-002 — the org∪project union dedupes exact 4-tuple-identity
  duplicates to one rendered entry; distinct project and org entries are
  both present; project first-seen order is preserved (org entries
  appended after).
* SC-003 — a structurally malformed ``activations:`` entry in a
  *present* org pack raises a clear, pack-named error propagated out of
  ``build_charter_context`` (NOT swallowed by the renderer's defensive
  ``except``); a pack whose ``org-charter.yaml`` is absent (no file, but
  the pack directory itself exists and is registered) is skipped rather
  than raising.

Per NFR-001, every claim here is proven through the real
``build_charter_context(...).text`` bootstrap entry point (no stub of
the org-charter rescan) — never through ``render_activation_stanza``,
``resolve_for_context``, or a direct ``ActivationEntry`` list.
"""

from __future__ import annotations

import textwrap
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.context import CharterContextResult, build_charter_context
from charter.offering.drg.models import DRGGraph

pytestmark = pytest.mark.fast


_PROJECT_ARTIFACT_ID = "project-first-seen-artifact-2365"
_ORG_ONLY_ARTIFACT_ID = "org-only-tactic-2365"
_ORG_PACK_NAME = "orgzilla-governance-pack"

_CHARTER_MD = textwrap.dedent(
    """\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
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


def _governance_yaml_with_activation() -> str:
    return textwrap.dedent(
        f"""\
        doctrine:
          template_set: software-dev-default
          selected_paradigms: []
          selected_directives: []
          available_tools: []
        activations:
          - activation_context:
              mission_type: software-dev
              action: implement
            charter_pack_id: project
            artifact_id: {_PROJECT_ARTIFACT_ID}
            artifact_kind: styleguides
        """
    )


def _write_project_fixture(repo_root: Path, *, governance_yaml: str) -> None:
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(governance_yaml, encoding="utf-8")


def _register_org_pack(repo_root: Path, pack_root: Path, *, name: str = _ORG_PACK_NAME) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(
            {
                # WP04 (C-A1): PackContext.from_config fail-closes without
                # this key. Every test in this module resolves the
                # "software-dev" mission type, unrelated to the org∪project
                # activation-union semantics under test.
                "mission_type_activations": ["software-dev"],
                "charter_packs": {"org": {"packs": [{"name": name, "local_path": str(pack_root)}]}},
            },
            fh,
        )


def _load_mock_graph() -> DRGGraph:
    yaml = YAML(typ="safe")
    return DRGGraph.model_validate(yaml.load(StringIO(_MINIMAL_GRAPH_YAML)))


def _build_bootstrap_context(repo_root: Path) -> CharterContextResult:
    mock_graph = _load_mock_graph()
    with (
        patch("charter.activation._drg_helpers.load_validated_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_offering_root", return_value=repo_root),
        patch("charter.offering.drg.validator.assert_valid"),
        patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None),
    ):
        return build_charter_context(
            repo_root, action="implement", depth=2, mark_loaded=False,
            mission_type="software-dev",
        )


class TestOrgProjectActivationUnion:
    """SC-002: 4-tuple dedup, distinct-entry preservation, project-first order."""

    def test_exact_duplicate_across_org_and_project_dedupes_to_one_render(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "consumer"
        repo.mkdir()
        _write_project_fixture(repo, governance_yaml=_governance_yaml_with_activation())

        org_pack = repo / "org-packs" / _ORG_PACK_NAME
        org_pack.mkdir(parents=True)
        (org_pack / "org-charter.yaml").write_text(
            textwrap.dedent(
                f"""\
                activations:
                  - activation_context:
                      mission_type: software-dev
                      action: implement
                    charter_pack_id: project
                    artifact_id: {_PROJECT_ARTIFACT_ID}
                    artifact_kind: styleguides
                  - activation_context:
                      mission_type: software-dev
                      action: implement
                    charter_pack_id: {_ORG_PACK_NAME}
                    artifact_id: {_ORG_ONLY_ARTIFACT_ID}
                    artifact_kind: tactics
                """
            ),
            encoding="utf-8",
        )
        _register_org_pack(repo, org_pack)

        result = _build_bootstrap_context(repo)
        text = str(result.text)

        assert result.mode == "bootstrap"
        # The exact-duplicate 4-tuple entry renders exactly once.
        assert text.count(_PROJECT_ARTIFACT_ID) == 1, (
            "the org-declared exact duplicate of the project entry rendered "
            "a second time — SC-002 dedup did not fire"
        )
        # The distinct org-only entry is present too.
        assert _ORG_ONLY_ARTIFACT_ID in text
        # Project first-seen order preserved: project entry precedes the
        # org-appended distinct entry in the rendered stanza.
        assert text.index(_PROJECT_ARTIFACT_ID) < text.index(_ORG_ONLY_ARTIFACT_ID)


class TestOrgActivationValidationAndSkip:
    """SC-003: malformed present-pack entry raises; missing pack is skipped."""

    def test_malformed_entry_in_present_org_pack_raises(self, tmp_path: Path) -> None:
        repo = tmp_path / "consumer"
        repo.mkdir()
        _write_project_fixture(
            repo,
            governance_yaml=textwrap.dedent(
                """\
                doctrine:
                  template_set: software-dev-default
                  selected_paradigms: []
                  selected_directives: []
                  available_tools: []
                """
            ),
        )

        org_pack = repo / "org-packs" / _ORG_PACK_NAME
        org_pack.mkdir(parents=True)
        (org_pack / "org-charter.yaml").write_text(
            textwrap.dedent(
                """\
                activations:
                  - activation_context:
                      mission_type: not-a-real-mission-type
                      action: implement
                    charter_pack_id: orgzilla-governance-pack
                    artifact_id: broken-entry
                    artifact_kind: styleguides
                """
            ),
            encoding="utf-8",
        )
        _register_org_pack(repo, org_pack)

        with pytest.raises(ValueError) as exc_info:
            _build_bootstrap_context(repo)

        message = str(exc_info.value)
        assert _ORG_PACK_NAME in message, (
            "the raised error must name the offending pack (SC-003: "
            "'clear, pack-named error')"
        )

    def test_org_pack_with_no_org_charter_yaml_is_skipped_not_raised(
        self, tmp_path: Path
    ) -> None:
        """A registered pack whose directory exists but has no
        ``org-charter.yaml`` at all is the 'missing pack' case — skipped
        silently (diagnostic handled upstream by
        ``_missing_pack_diagnostic``, which only fires when the
        *directory* itself is absent, not exercised here)."""
        repo = tmp_path / "consumer"
        repo.mkdir()
        _write_project_fixture(
            repo,
            governance_yaml=textwrap.dedent(
                """\
                doctrine:
                  template_set: software-dev-default
                  selected_paradigms: []
                  selected_directives: []
                  available_tools: []
                """
            ),
        )

        org_pack = repo / "org-packs" / _ORG_PACK_NAME
        org_pack.mkdir(parents=True)
        # Deliberately no org-charter.yaml written.
        _register_org_pack(repo, org_pack)

        result = _build_bootstrap_context(repo)

        assert result.mode == "bootstrap"
        assert "Selected activations:" not in result.text
