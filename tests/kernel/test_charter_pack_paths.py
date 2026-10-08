"""``kernel.charter_pack_paths``: the project pack root and pack-relative paths (FR-016).

Covers every public constant and helper. There is no legacy read fallback
(FR-011): the retired ``.kittify/doctrine/`` root is never resolved.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel import charter_pack_paths as paths

pytestmark = [pytest.mark.fast]


class TestConstants:
    def test_root_constants(self) -> None:
        assert paths.KITTIFY_DIRNAME == ".kittify"
        assert paths.PROJECT_PACK_DIRNAME == "charter-packs"
        assert Path(".kittify", "charter-packs") == paths.PROJECT_PACK_ROOT
        assert paths.PROJECT_PACK_ROOT_POSIX == ".kittify/charter-packs"

    def test_pack_relative_constants(self) -> None:
        assert paths.DRG_DIRNAME == "drg"
        assert Path("drg", "fragment.yaml") == paths.DRG_FRAGMENT
        assert paths.ORG_CHARTER_FILENAME == "org-charter.yaml"
        assert paths.PRESETS_DIRNAME == "presets"
        assert paths.PROJECT_GRAPH_FILENAME == "graph.yaml"

    def test_all_names_every_public_symbol(self) -> None:
        public = {n for n in vars(paths) if not n.startswith("_") and n not in {"annotations", "Path"}}
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

    def test_the_retired_root_is_never_resolved(self, tmp_path: Path) -> None:
        """A project that still has ``.kittify/doctrine/`` resolves to the project pack root anyway."""
        (tmp_path / ".kittify" / "doctrine").mkdir(parents=True)
        assert paths.project_pack_root(tmp_path) == tmp_path / ".kittify" / "charter-packs"
        assert not {"LEGACY_PROJECT_PACK_DIRNAME", "LegacyDoctrineRootWarning", "resolve_project_pack_read_root"} & set(vars(paths))
