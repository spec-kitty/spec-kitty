"""WP04 unit tests — ``render_authority_paths`` (FR-003).

These tests exercise the pure renderer in
``charter.activation.context_renderers.authority_paths`` against the six-row table
in the WP04 task spec (subtask T017).  They pin:

* default entries surface only when their directory exists on disk;
* charter-declared entries are additive, with dedup against defaults;
* the empty result suppresses the section header (no broken pointer).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.context_renderers import (
    AUTHORITY_PATHS_HEADER,
    DEFAULT_CHARTER_DECLARED_WHEN_CLAUSE,
    render_authority_paths,
)
from charter.activation.context_renderers.authority_paths import DEFAULT_AUTHORITY_PATHS
from charter.activation.schemas import GovernanceCharterConfig

pytestmark = pytest.mark.fast


def _make_dir(repo_root: Path, relative: str) -> None:
    """Materialise *relative* as a directory under *repo_root*."""

    (repo_root / relative).mkdir(parents=True, exist_ok=True)


class TestDefaultAuthorityPaths:
    """Default entries surface only when their directory exists on disk."""

    def test_default_glossary_path_surfaces_when_directory_present(
        self, tmp_path: Path
    ) -> None:
        _make_dir(tmp_path, "docs/context")
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert AUTHORITY_PATHS_HEADER in result
        assert "docs/context/" in result
        assert DEFAULT_AUTHORITY_PATHS["docs/context/"] in result

    def test_default_adr_path_surfaces_when_directory_present(
        self, tmp_path: Path
    ) -> None:
        _make_dir(tmp_path, "docs/adr/3.x")
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert AUTHORITY_PATHS_HEADER in result
        assert "docs/adr/3.x/" in result
        assert DEFAULT_AUTHORITY_PATHS["docs/adr/3.x/"] in result

    def test_default_path_skipped_when_directory_missing(self, tmp_path: Path) -> None:
        # No docs/context in tmp_path — render must not list it.
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert "docs/context/" not in result


class TestCharterDeclaredAuthorityPaths:
    """Charter-declared paths append to defaults, with dedup."""

    def test_charter_declared_path_additive(self, tmp_path: Path) -> None:
        _make_dir(tmp_path, "docs/context")
        _make_dir(tmp_path, "docs/runbooks")
        selection = GovernanceCharterConfig(authority_paths=["docs/runbooks/"])
        result = render_authority_paths(tmp_path, selection)
        assert "docs/context/" in result
        assert "docs/runbooks/" in result
        assert DEFAULT_CHARTER_DECLARED_WHEN_CLAUSE in result

    def test_charter_declared_duplicate_of_default_deduped(
        self, tmp_path: Path
    ) -> None:
        _make_dir(tmp_path, "docs/context")
        selection = GovernanceCharterConfig(authority_paths=["docs/context/"])
        result = render_authority_paths(tmp_path, selection)
        # The path appears exactly once even though both default and
        # declared lists carry it.
        assert result.count("docs/context/") == 1


class TestEmptyResult:
    """When no path qualifies, the section header is omitted."""

    def test_no_paths_no_section(self, tmp_path: Path) -> None:
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert result == ""
        assert AUTHORITY_PATHS_HEADER not in result
