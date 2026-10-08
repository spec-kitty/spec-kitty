"""Unit tests for org-layer provenance threading in charter context renderers.

Covers WP07 T035/T036: the ``_build_action_org_source_map`` helper and
``_extend_named_artifact_lines`` org_source_map wiring.

Assertions:
* When no org packs are configured (``load_org_drg`` returns ``[]``),
  ``_build_action_org_source_map`` returns ``{}`` → NFR-001 byte-stability.
* When an org pack contributes nodes, the source map contains the correct
  ``artifact_id → pack_name`` entries.
* ``_extend_named_artifact_lines`` with an org_source_map appends
  ``(source: org:<pack>)`` for org-contributed artifacts and no suffix
  for built-in artifacts.
* ``_provenance_suffix`` emits the correct suffix format.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Minimal repo with the example_org fixture pack configured."""
    pack_dest = tmp_path / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        )
    )
    return tmp_path


@pytest.fixture
def tmp_repo_without_org_pack(tmp_path: Path) -> Path:
    """Minimal repo with no org packs configured."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# _provenance_suffix tests
# ---------------------------------------------------------------------------


def test_provenance_suffix_returns_empty_for_no_map() -> None:
    """When org_source_map is None, suffix is empty (built-in artifacts unchanged)."""
    from charter.activation.context_renderers.selection_block import _provenance_suffix

    assert _provenance_suffix("some-directive", None) == ""


def test_provenance_suffix_returns_empty_for_artifact_not_in_map() -> None:
    """When artifact not in map, suffix is empty."""
    from charter.activation.context_renderers.selection_block import _provenance_suffix

    result = _provenance_suffix("built-in-directive", {"org-directive": "example-org"})
    assert result == ""


def test_provenance_suffix_returns_org_pack_suffix() -> None:
    """When artifact is in map with a pack name, suffix is '(source: org, pack: <name>)'."""
    from charter.activation.context_renderers.selection_block import _provenance_suffix

    result = _provenance_suffix("sox-controls", {"sox-controls": "acme-compliance"})
    assert result == " (source: org, pack: acme-compliance)"


def test_provenance_suffix_collapses_to_bare_org_for_empty_pack() -> None:
    """When pack name is empty string, suffix collapses to '(source: org)'."""
    from charter.activation.context_renderers.selection_block import _provenance_suffix

    result = _provenance_suffix("sox-controls", {"sox-controls": ""})
    assert result == " (source: org)"


# ---------------------------------------------------------------------------
# _build_action_org_source_map tests
# ---------------------------------------------------------------------------


def test_build_action_org_source_map_empty_when_no_org_packs(
    tmp_repo_without_org_pack: Path,
) -> None:
    """NFR-001: when no org packs are configured, source map is empty dict.

    This ensures 23 governance-contract fixtures remain byte-identical.
    """
    from charter.activation.context_renderers.selection_block import _build_action_org_source_map

    result = _build_action_org_source_map(tmp_repo_without_org_pack, ["some-directive"])
    assert result == {}


def test_build_action_org_source_map_empty_for_empty_artifact_ids(
    tmp_repo_with_org_pack: Path,
) -> None:
    """When artifact_ids is empty, source map is always {}."""
    from charter.activation.context_renderers.selection_block import _build_action_org_source_map

    result = _build_action_org_source_map(tmp_repo_with_org_pack, [])
    assert result == {}


def test_build_action_org_source_map_returns_org_entries(
    tmp_repo_with_org_pack: Path,
) -> None:
    """When an org pack contributes 'sox-controls', source map contains that entry."""
    from charter.activation.context_renderers.selection_block import _build_action_org_source_map

    result = _build_action_org_source_map(
        tmp_repo_with_org_pack, ["sox-controls", "some-other-directive"]
    )
    assert "sox-controls" in result, (
        f"expected 'sox-controls' in org source map, got: {result}"
    )
    assert result["sox-controls"] == "example-org", (
        f"expected pack name 'example-org', got: {result.get('sox-controls')!r}"
    )
    # Built-in artifacts not in map
    assert "some-other-directive" not in result


# ---------------------------------------------------------------------------
# _extend_named_artifact_lines tests
# ---------------------------------------------------------------------------


def _make_mock_repository(artifacts: dict[str, dict]) -> MagicMock:
    """Build a minimal mock repository with get() returning artifact objects."""
    repo = MagicMock()

    def _get(artifact_id: str) -> MagicMock | None:
        data = artifacts.get(artifact_id)
        if data is None:
            return None
        obj = MagicMock()
        for k, v in data.items():
            setattr(obj, k, v)
        return obj

    repo.get.side_effect = _get
    return repo


def test_extend_named_artifact_lines_no_org_source_map_no_suffix() -> None:
    """Without org_source_map, no '(source: org)' suffix is appended (NFR-001)."""
    from charter.activation.context_renderers.selection_block import _extend_named_artifact_lines

    repo = _make_mock_repository(
        {"DIRECTIVE_001": {"title": "Test Directive", "intent": "Do stuff."}}
    )
    lines: list[str] = []
    _extend_named_artifact_lines(
        lines,
        "Directives",
        ["DIRECTIVE_001"],
        repo,
        "title",
        "intent",
        org_source_map=None,
    )
    assert any("DIRECTIVE_001" in line for line in lines)
    # No source suffix when no org map
    assert not any("source: org" in line for line in lines)


def test_extend_named_artifact_lines_org_source_map_adds_suffix() -> None:
    """When artifact is in org_source_map, '(source: org, pack: <name>)' is appended."""
    from charter.activation.context_renderers.selection_block import _extend_named_artifact_lines

    repo = _make_mock_repository(
        {"sox-controls": {"title": "SOX Controls", "intent": "Audit compliance."}}
    )
    lines: list[str] = []
    _extend_named_artifact_lines(
        lines,
        "Directives",
        ["sox-controls"],
        repo,
        "title",
        "intent",
        org_source_map={"sox-controls": "example-org"},
    )
    joined = "\n".join(lines)
    assert "sox-controls" in joined
    assert "(source: org, pack: example-org)" in joined


def test_extend_named_artifact_lines_builtin_no_suffix_org_artifact_with_suffix() -> None:
    """Option B: only org artifacts get suffix; built-in artifacts unchanged."""
    from charter.activation.context_renderers.selection_block import _extend_named_artifact_lines

    repo = _make_mock_repository(
        {
            "DIRECTIVE_001": {"title": "Built-in Directive", "intent": "Built-in."},
            "sox-controls": {"title": "SOX Controls", "intent": "Org-contributed."},
        }
    )
    lines: list[str] = []
    _extend_named_artifact_lines(
        lines,
        "Directives",
        ["DIRECTIVE_001", "sox-controls"],
        repo,
        "title",
        "intent",
        org_source_map={"sox-controls": "example-org"},
    )
    joined = "\n".join(lines)
    # Org artifact has suffix
    assert "(source: org, pack: example-org)" in joined
    # Built-in artifact has no suffix
    builtin_line = next(
        (line for line in lines if "DIRECTIVE_001" in line), ""
    )
    assert "source: org" not in builtin_line
