"""``kernel.charter_pack_paths``: the project pack root and pack-relative paths (FR-016).

Covers every public constant and helper, plus the temporary legacy read
fallback (FR-011, deleted by WP14): canonical wins, the legacy root is read
with a warn-once notice, neither resolves to the canonical root, and ``quiet``
suppresses the warning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import charter_pack_paths as paths
from kernel.charter_pack_paths import (
    LEGACY_PROJECT_PACK_DIRNAME,
    PROJECT_PACK_DIRNAME,
    LegacyDoctrineRootWarning,
    _warn_legacy_project_pack_root_once,
    resolve_project_pack_read_root,
)

pytestmark = [pytest.mark.fast]


@pytest.fixture(autouse=True)
def _reset_warn_once_gate() -> None:
    _warn_legacy_project_pack_root_once.cache_clear()


class TestNeitherRootExists:
    def test_returns_canonical_path_without_warning(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        """A fresh project with no project pack resolves to the canonical
        path: nothing to migrate, nothing to warn about."""
        result = resolve_project_pack_read_root(tmp_path)

        assert result == tmp_path / ".kittify" / PROJECT_PACK_DIRNAME
        assert not any(issubclass(w.category, LegacyDoctrineRootWarning) for w in recwarn.list)


class TestCanonicalRootExists:
    def test_canonical_wins_without_warning(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        canonical = tmp_path / ".kittify" / PROJECT_PACK_DIRNAME
        canonical.mkdir(parents=True)

        result = resolve_project_pack_read_root(tmp_path)

        assert result == canonical
        assert not any(issubclass(w.category, LegacyDoctrineRootWarning) for w in recwarn.list)

    def test_canonical_wins_even_when_legacy_also_exists(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        canonical = tmp_path / ".kittify" / PROJECT_PACK_DIRNAME
        canonical.mkdir(parents=True)
        legacy = tmp_path / ".kittify" / LEGACY_PROJECT_PACK_DIRNAME
        legacy.mkdir(parents=True)

        result = resolve_project_pack_read_root(tmp_path)

        assert result == canonical
        assert not any(issubclass(w.category, LegacyDoctrineRootWarning) for w in recwarn.list)


class TestLegacyRootOnlyExists:
    def test_old_root_read_warns_and_migrates(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        """A project that only has the legacy ``.kittify/doctrine/`` tree reads
        from it (nothing is lost), with a one-shot notice pointing at the move."""
        legacy = tmp_path / ".kittify" / LEGACY_PROJECT_PACK_DIRNAME
        legacy.mkdir(parents=True)

        result = resolve_project_pack_read_root(tmp_path)

        assert result == legacy
        assert any(issubclass(w.category, LegacyDoctrineRootWarning) for w in recwarn.list)

    def test_warns_only_once_per_process(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        legacy = tmp_path / ".kittify" / LEGACY_PROJECT_PACK_DIRNAME
        legacy.mkdir(parents=True)

        resolve_project_pack_read_root(tmp_path)
        resolve_project_pack_read_root(tmp_path)
        resolve_project_pack_read_root(tmp_path)

        warnings_seen = [w for w in recwarn.list if issubclass(w.category, LegacyDoctrineRootWarning)]
        assert len(warnings_seen) == 1

    def test_quiet_suppresses_the_warning(self, tmp_path: Path, recwarn: pytest.WarningsRecorder) -> None:
        legacy = tmp_path / ".kittify" / LEGACY_PROJECT_PACK_DIRNAME
        legacy.mkdir(parents=True)

        result = resolve_project_pack_read_root(tmp_path, quiet=True)

        assert result == legacy
        assert not any(issubclass(w.category, LegacyDoctrineRootWarning) for w in recwarn.list)


class TestConstants:
    def test_root_constants(self) -> None:
        assert paths.KITTIFY_DIRNAME == ".kittify"
        assert paths.PROJECT_PACK_DIRNAME == "charter-packs"
        assert Path(".kittify", "charter-packs") == paths.PROJECT_PACK_ROOT
        assert paths.PROJECT_PACK_ROOT_POSIX == ".kittify/charter-packs"
        assert paths.LEGACY_PROJECT_PACK_DIRNAME == "doctrine"

    def test_pack_relative_constants(self) -> None:
        assert paths.DRG_DIRNAME == "drg"
        assert Path("drg", "fragment.yaml") == paths.DRG_FRAGMENT
        assert paths.ORG_CHARTER_FILENAME == "org-charter.yaml"
        assert paths.PRESETS_DIRNAME == "presets"
        assert paths.PROJECT_GRAPH_FILENAME == "graph.yaml"

    def test_all_names_every_public_symbol(self) -> None:
        public = {n for n in vars(paths) if not n.startswith("_") and n not in {"annotations", "functools", "warnings", "Path"}}
        assert public == set(paths.__all__)


class TestHelpers:
    def test_project_pack_root(self, tmp_path: Path) -> None:
        assert paths.project_pack_root(tmp_path) == tmp_path / ".kittify" / "charter-packs"

    def test_project_pack_path_joins_parts(self, tmp_path: Path) -> None:
        assert paths.project_pack_path(tmp_path, "directive", "x.directive.yaml") == (tmp_path / ".kittify" / "charter-packs" / "directive" / "x.directive.yaml")

    def test_project_pack_path_without_parts_is_the_root(self, tmp_path: Path) -> None:
        assert paths.project_pack_path(tmp_path) == paths.project_pack_root(tmp_path)

    def test_pack_drg_fragment(self, tmp_path: Path) -> None:
        assert paths.pack_drg_fragment(tmp_path) == tmp_path / "drg" / "fragment.yaml"

    def test_pack_org_charter(self, tmp_path: Path) -> None:
        assert paths.pack_org_charter(tmp_path) == tmp_path / "org-charter.yaml"

    def test_pack_presets_dir(self, tmp_path: Path) -> None:
        assert paths.pack_presets_dir(tmp_path) == tmp_path / "presets"

    def test_a_file_named_like_the_root_is_not_a_root(self, tmp_path: Path) -> None:
        """Only a directory counts: a stray file at the legacy path is not read."""
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "doctrine").write_text("", encoding="utf-8")
        assert resolve_project_pack_read_root(tmp_path, quiet=True) == paths.project_pack_root(tmp_path)
