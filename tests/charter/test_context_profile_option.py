"""``spec-kitty charter context --profile <id>`` renders profile-cited doctrine (#6990, FR-003).

``spec-kitty dispatch`` embeds ``build_charter_context(..., profile=<id>)`` and on
this repository most of that payload is the profile-cited directive block (188 of
308 rendered lines). ``charter context`` had no way to render those sections, so
the brief dispatch payload's fetch command could not reproduce the text it omits.

These tests drive the real CLI command (not ``build_charter_context`` directly),
so a missing ``--profile`` *wiring* fails even when the library already supports
the keyword. Each positive assertion is paired with the same-fixture negative
control the acceptance-criteria-non-vacuity tactic requires: the same fixture,
the same action, once with ``--profile`` and once without.

Fixture shape mirrors ``tests/charter/test_context_profile.py`` (minimal
``.kittify/charter`` layout + a patched two-node DRG graph); ``python-pedro`` is a
shipped built-in profile that cites ``DIRECTIVE_010``.
"""

from __future__ import annotations

import json
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.profile_resolution import _reset_agent_profile_cache

pytestmark = pytest.mark.fast

_PROFILE = "python-pedro"
_PROFILE_HEADER = f"Profile-Cited Directives ({_PROFILE})"

_MINIMAL_GRAPH_YAML = textwrap.dedent("""\
    schema_version: "1.0"
    generated_at: "2026-04-13T10:00:00+00:00"
    generated_by: "test"
    nodes:
      - urn: "action:software-dev/implement"
        kind: action
        label: implement
      - urn: "directive:DIRECTIVE_001"
        kind: directive
        label: Architectural Integrity Standard
    edges:
      - source: "action:software-dev/implement"
        target: "directive:DIRECTIVE_001"
        relation: scope
""")

_CHARTER_MD = textwrap.dedent("""\
    # Project Charter

    ## Policy Summary

    - Intent: deterministic delivery
    - Testing: pytest + coverage
""")

_GOVERNANCE_YAML = textwrap.dedent("""\
    doctrine:
      template_set: software-dev-default
      selected_paradigms: []
      selected_directives: []
      available_tools: []
""")

_REFERENCES_YAML = textwrap.dedent("""\
    schema_version: "1.0.0"
    references: []
""")


def _write_project(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text(_CHARTER_MD, encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    (charter_dir / "references.yaml").write_text(_REFERENCES_YAML, encoding="utf-8")
    (repo_root / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    return repo_root


def _invoke(tmp_path: Path, *args: str):
    """Run the real ``spec-kitty charter context`` command on the fixture."""
    import specify_cli.cli.commands.charter as charter_pkg
    from charter.offering.drg.models import DRGGraph
    from specify_cli.cli.commands.charter import charter_app

    repo_root = _write_project(tmp_path)

    graph_data = YAML(typ="safe").load(StringIO(_MINIMAL_GRAPH_YAML))
    mock_graph = DRGGraph.model_validate(graph_data)

    # Fresh profile repository per test: the shipped built-in tree is what
    # resolves ``python-pedro``, and its cache is module-global.
    _reset_agent_profile_cache()

    with (
        patch.object(charter_pkg, "find_repo_root", return_value=repo_root),
        patch("charter.offering.drg.loader.load_graph", return_value=mock_graph),
        patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        return CliRunner().invoke(charter_app, list(args))


def _json_payload(result: Any) -> dict[str, Any]:  # noqa: ANN401 - typer CliRunner result
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_profile_option_renders_profile_cited_directives(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "context", "--action", "implement", "--profile", _PROFILE)

    assert result.exit_code == 0, result.output
    assert _PROFILE_HEADER in result.output


def test_without_profile_option_omits_profile_cited_directives(tmp_path: Path) -> None:
    """Same-fixture negative control: the probe can see the block when it is there."""
    result = _invoke(tmp_path, "context", "--action", "implement")

    assert result.exit_code == 0, result.output
    assert _PROFILE_HEADER not in result.output


def test_json_text_carries_profile_sections_and_structured_blocks_unchanged(tmp_path: Path) -> None:
    with_profile = _json_payload(_invoke(tmp_path, "context", "--action", "implement", "--profile", _PROFILE, "--json"))
    without_profile = _json_payload(_invoke(tmp_path, "context", "--action", "implement", "--json"))

    assert _PROFILE_HEADER in with_profile["text"]
    assert _PROFILE_HEADER in with_profile["context"]
    assert _PROFILE_HEADER not in without_profile["text"]
    # The structured blocks are DRG projections, not profile-cited prose.
    assert with_profile["directives"] == without_profile["directives"]


def test_unknown_profile_warns_on_stderr_and_omits_profile_sections(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "context", "--action", "implement", "--profile", "not-a-profile")

    assert result.exit_code == 0, result.output
    assert "Profile-Cited Directives" not in result.stdout
    assert "profile 'not-a-profile' not found" in result.stderr
    # Control: a resolvable profile emits no such warning.
    known = _invoke(tmp_path, "context", "--action", "implement", "--profile", _PROFILE)
    assert "not found" not in known.stderr


def test_unknown_profile_warning_keeps_json_stdout_clean(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "context", "--action", "implement", "--profile", "not-a-profile", "--json")

    assert result.exit_code == 0, result.output
    assert "profile 'not-a-profile' not found" in result.stderr
    assert json.loads(result.stdout)["success"] is True
