"""Unit tests for the 3-class portable-provenance normalizer (T016, C-PRV-6).

``charter.offering.provenance.to_portable_source_path`` is the single seam both
provenance carriers (charter catalog + agent-profile projection manifest)
route through. This module tests the normalizer in isolation, against a
synthetic ``SPEC_KITTY_PACKS_ROOT`` (mirroring the established
``tests/charter/test_builtin_reader_relocation.py`` fixture pattern) rather
than the real installed/editable ``packs/built-in`` tree, so the matrix is
deterministic regardless of where this checkout happens to live on disk.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

import charter.offering.provenance as provenance_module
from charter.offering.provenance import is_built_in_pack_path, to_portable_source_path
from kernel.sibling_paths import SiblingPathNotFound

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


@pytest.fixture
def packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic ``packs/`` tree with a real ``built-in/`` child on disk."""
    root = tmp_path / "packs"
    (root / "built-in").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


class TestBuiltInPackClass:
    """Class (a): a path under the built-in pack root normalizes to a token."""

    def test_nested_file_becomes_token(self, packs_root: Path, tmp_path: Path) -> None:
        source = packs_root / "built-in" / "paradigms" / "atomic-design.paradigm.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: atomic-design\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=tmp_path)

        assert result == "${SPEC_KITTY_PACKS_ROOT}/built-in/paradigms/atomic-design.paradigm.yaml"

    def test_deeply_nested_file_preserves_full_rest(self, packs_root: Path, tmp_path: Path) -> None:
        source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("name: software-dev\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=tmp_path)

        assert result == "${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml"

    def test_built_in_root_itself_has_no_trailing_slash(self, packs_root: Path, tmp_path: Path) -> None:
        result = to_portable_source_path(packs_root / "built-in", project_root=tmp_path)

        assert result == "${SPEC_KITTY_PACKS_ROOT}/built-in"

    def test_string_input_accepted(self, packs_root: Path, tmp_path: Path) -> None:
        source = packs_root / "built-in" / "directives" / "example.directive.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: example\n", encoding="utf-8")

        result = to_portable_source_path(str(source), project_root=tmp_path)

        assert result == "${SPEC_KITTY_PACKS_ROOT}/built-in/directives/example.directive.yaml"

    def test_is_built_in_pack_path_true_for_nested_file(self, packs_root: Path) -> None:
        source = packs_root / "built-in" / "tactics" / "example.tactic.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: example\n", encoding="utf-8")

        assert is_built_in_pack_path(source) is True

    def test_never_hand_typed_segment_matches_kernel_pattern(self, packs_root: Path) -> None:
        """The 'built-in' token segment must come from the owned kernel constant."""
        from kernel.paths import BUILT_IN_PACK_SIBLING_PATTERN

        source = packs_root / "built-in" / "styleguides" / "example.styleguide.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: example\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=None)

        assert f"/{BUILT_IN_PACK_SIBLING_PATTERN.name}/" in result


class TestInTreeProjectClass:
    """Class (b): an in-tree, non-built-in path normalizes to repo-relative POSIX."""

    def test_nested_project_file_becomes_relative(self, packs_root: Path, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        source = project_root / ".kittify" / "doctrine" / "local.directive.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: local\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=project_root)

        assert result == ".kittify/doctrine/local.directive.yaml"

    def test_result_is_forward_slashed(self, packs_root: Path, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        source = project_root / "a" / "b" / "c.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("x: 1\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=project_root)

        assert "\\" not in result
        assert result == "a/b/c.yaml"


class TestOutOfTreeClass:
    """Class (c): neither built-in nor in-tree -- absolute path is preserved."""

    def test_out_of_tree_path_stays_absolute(self, packs_root: Path, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        elsewhere = tmp_path / "elsewhere" / "external.yaml"
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text("x: 1\n", encoding="utf-8")

        result = to_portable_source_path(elsewhere, project_root=project_root)

        assert result == str(elsewhere.resolve())

    def test_no_project_root_falls_through_to_absolute(self, packs_root: Path, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere" / "external.yaml"
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text("x: 1\n", encoding="utf-8")

        result = to_portable_source_path(elsewhere, project_root=None)

        assert result == str(elsewhere.resolve())

    def test_is_built_in_pack_path_false_for_out_of_tree(self, packs_root: Path, tmp_path: Path) -> None:
        elsewhere = tmp_path / "elsewhere" / "external.yaml"
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text("x: 1\n", encoding="utf-8")

        assert is_built_in_pack_path(elsewhere) is False


class TestEmptyInput:
    """Empty input returns empty output, mirroring ``_trim_source_path``."""

    def test_empty_string_returns_empty_string(self, packs_root: Path, tmp_path: Path) -> None:
        assert to_portable_source_path("", project_root=tmp_path) == ""

    def test_is_built_in_pack_path_false_for_empty(self) -> None:
        assert is_built_in_pack_path("") is False


class TestReBakeGate:
    """C-PRV-2: setting SPEC_KITTY_PACKS_ROOT to a DIFFERENT absolute path than
    the one the source path was originally under must not change the token --
    only the built-in-relative REST matters, never the resolved absolute root.
    """

    def test_token_is_identical_regardless_of_which_env_value_resolved_the_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root_a = tmp_path / "packs_a"
        (root_a / "built-in" / "paradigms").mkdir(parents=True)
        source_a = root_a / "built-in" / "paradigms" / "example.paradigm.yaml"
        source_a.write_text("id: example\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root_a))
        result_a = to_portable_source_path(source_a, project_root=tmp_path)

        root_b = tmp_path / "packs_b"
        (root_b / "built-in" / "paradigms").mkdir(parents=True)
        source_b = root_b / "built-in" / "paradigms" / "example.paradigm.yaml"
        source_b.write_text("id: example\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root_b))
        result_b = to_portable_source_path(source_b, project_root=tmp_path)

        assert result_a == result_b == "${SPEC_KITTY_PACKS_ROOT}/built-in/paradigms/example.paradigm.yaml"


class TestUnavailableBuiltInInstall:
    """``_resolve_built_in_root`` must tolerate a genuinely unresolvable
    built-in pack root -- e.g. a doctrine-layer caller (a test fixture, a
    stripped-down deployment) with no packaged ``packs/built-in`` sibling
    reachable from ``kernel.paths``' anchor. Classes (b)/(c) still have to
    work when ``get_built_in_pack_root`` raises ``SiblingPathNotFound``
    (the fail-closed kernel error) instead of resolving -- this is the
    ``except SiblingPathNotFound: return None`` fallthrough documented on
    ``_resolve_built_in_root``.
    """

    @staticmethod
    def _raise_sibling_not_found() -> Path:
        raise SiblingPathNotFound(
            PurePosixPath("packs", "built-in"),
            Path("/opt/spec-kitty-cli/src/kernel/paths.py"),
        )

    def test_falls_through_to_repo_relative_when_root_unresolvable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            provenance_module, "get_built_in_pack_root", self._raise_sibling_not_found
        )

        project_root = tmp_path / "operator-config-ergonomics"
        source = project_root / ".kittify" / "doctrine" / "local.directive.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: local\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=project_root)

        assert result == ".kittify/doctrine/local.directive.yaml"

    def test_falls_through_to_absolute_without_project_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            provenance_module, "get_built_in_pack_root", self._raise_sibling_not_found
        )

        source = tmp_path / "org-packs" / "acme-directives" / "release-gate.directive.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: release-gate\n", encoding="utf-8")

        result = to_portable_source_path(source, project_root=None)

        assert result == str(source.resolve())

    def test_is_built_in_pack_path_false_when_root_unresolvable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            provenance_module, "get_built_in_pack_root", self._raise_sibling_not_found
        )

        source = tmp_path / "org-packs" / "acme-directives" / "release-gate.directive.yaml"
        source.parent.mkdir(parents=True)
        source.write_text("id: release-gate\n", encoding="utf-8")

        assert is_built_in_pack_path(source) is False
