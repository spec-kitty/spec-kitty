"""Tests for compiler._default_doctrine_service project-root candidate list (T024, R-2).

Three locked cases (R-2 / FR-009):

1. No ``.kittify/doctrine/`` directory → ``project_root`` resolves to whichever
   existing candidate resolves first (legacy 3.x behaviour, byte-identical).
2. ``.kittify/doctrine/`` present with synthesized content → ``project_root``
   points there (Phase 3 path).
3. ``.kittify/doctrine/`` present but empty → ``project_root`` points there but
   repositories resolve to empty overlays with no shipped-layer impact.

Also covers ``charter.activation._doctrine_paths.resolve_project_root`` directly and
verifies the compiler's ``_default_doctrine_service`` uses it correctly.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation._doctrine_paths import resolve_project_root, _project_root_candidates
from charter.activation.compiler import _default_doctrine_service


# ---------------------------------------------------------------------------
# Direct tests for resolve_project_root()
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit]


def _write_min_config(repo_root: Path) -> None:
    """Write a minimal ``.kittify/config.yaml`` with only
    ``mission_type_activations`` set.

    ``_default_doctrine_service``/``_build_doctrine_service`` (below) build
    an activation-aware doctrine service via ``PackContext.from_config``,
    which now hard-fails (WP04, C-A1) when ``mission_type_activations`` is
    absent -- unrelated to the project-root candidate-resolution behavior
    these tests pin. A wholly-missing ``.kittify/config.yaml`` is not itself
    under test here (unlike ``TestResolveProjectRoot`` above, which calls
    ``resolve_project_root`` directly and never touches ``PackContext``).
    """
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )


class TestResolveProjectRoot:
    """Tests for the shared _doctrine_paths.resolve_project_root() helper."""

    def test_returns_none_when_no_candidate_exists(self, tmp_path: Path) -> None:
        """Case R-2.1: no candidate directories → None (legacy behaviour)."""
        result = resolve_project_root(tmp_path)
        assert result is None

    def test_returns_kittify_doctrine_when_present(self, tmp_path: Path) -> None:
        """Case R-2.2: .kittify/doctrine/ present → resolves there."""
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        result = resolve_project_root(tmp_path)
        assert result == kittify_doctrine

    def test_kittify_doctrine_takes_priority_over_src_doctrine(
        self, tmp_path: Path
    ) -> None:
        """Phase 3 candidate outranks legacy src/charter/offering/ candidate."""
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        src_doctrine = tmp_path / "src" / "charter" / "offering"
        src_doctrine.mkdir(parents=True)
        result = resolve_project_root(tmp_path)
        assert result == kittify_doctrine

    def test_falls_back_to_src_doctrine_when_kittify_absent(
        self, tmp_path: Path
    ) -> None:
        """When .kittify/doctrine/ absent, legacy src/charter/offering/ wins."""
        src_doctrine = tmp_path / "src" / "charter" / "offering"
        src_doctrine.mkdir(parents=True)
        result = resolve_project_root(tmp_path)
        assert result == src_doctrine

    def test_falls_back_to_flat_doctrine_when_both_absent(
        self, tmp_path: Path
    ) -> None:
        """When .kittify/doctrine/ and src/charter/offering/ absent, flat doctrine/ wins."""
        flat_doctrine = tmp_path / "doctrine"
        flat_doctrine.mkdir()
        result = resolve_project_root(tmp_path)
        assert result == flat_doctrine

    def test_empty_kittify_doctrine_still_resolves(self, tmp_path: Path) -> None:
        """Case R-2.3: .kittify/doctrine/ present but empty → still resolves."""
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        # No files written inside
        result = resolve_project_root(tmp_path)
        assert result == kittify_doctrine

    def test_candidate_order_is_kittify_src_flat(self, tmp_path: Path) -> None:
        """The candidate list has the expected order: project pack root first."""
        candidates = _project_root_candidates(tmp_path)
        assert candidates[0] == tmp_path / ".kittify" / "charter-packs"
        assert candidates[1] == tmp_path / "src" / "charter" / "offering"
        assert candidates[2] == tmp_path / "doctrine"

    def test_project_pack_root_resolves_when_present(self, tmp_path: Path) -> None:
        """A migrated project resolves to ``.kittify/charter-packs/``, ahead of a stale legacy tree."""
        project_pack = tmp_path / ".kittify" / "charter-packs"
        project_pack.mkdir(parents=True)
        (tmp_path / ".kittify" / "doctrine").mkdir()
        assert resolve_project_root(tmp_path) == project_pack


# ---------------------------------------------------------------------------
# Tests for compiler._default_doctrine_service via resolve_project_root
# ---------------------------------------------------------------------------

class TestDefaultDoctrineService:
    """Tests for compiler._default_doctrine_service project-root wiring (T024)."""

    def _project_root_from_service(self, repo_root: Path) -> Path | None:
        """Call _default_doctrine_service and extract project_root from it."""
        svc = _default_doctrine_service(repo_root)
        # DoctrineService stores project_root as _project_root
        return getattr(svc, "_project_root", None)

    def test_case_r2_1_no_candidate_dirs_project_root_is_none(
        self, tmp_path: Path
    ) -> None:
        """Case R-2.1: No candidate directories → project_root is None (legacy)."""
        _write_min_config(tmp_path)
        project_root = self._project_root_from_service(tmp_path)
        assert project_root is None

    def test_case_r2_2_kittify_doctrine_present_points_there(
        self, tmp_path: Path
    ) -> None:
        """Case R-2.2: .kittify/doctrine/ present → project_root points there."""
        _write_min_config(tmp_path)
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        project_root = self._project_root_from_service(tmp_path)
        assert project_root == kittify_doctrine

    def test_case_r2_3_kittify_doctrine_empty_points_there(
        self, tmp_path: Path
    ) -> None:
        """Case R-2.3: .kittify/doctrine/ present but empty → points there, no impact."""
        _write_min_config(tmp_path)
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        # Leave the directory empty
        project_root = self._project_root_from_service(tmp_path)
        # project_root still resolves to the empty dir
        assert project_root == kittify_doctrine

    def test_repo_root_none_gives_none_project_root(self) -> None:
        """When repo_root is None, project_root is None (legacy callers)."""
        svc = _default_doctrine_service(None)
        project_root = getattr(svc, "project_root", None)
        assert project_root is None

    def test_legacy_src_doctrine_candidate_still_resolves_when_kittify_absent(
        self, tmp_path: Path
    ) -> None:
        """Legacy src/charter/offering/ candidate resolves when .kittify/doctrine/ absent."""
        _write_min_config(tmp_path)
        src_doctrine = tmp_path / "src" / "charter" / "offering"
        src_doctrine.mkdir(parents=True)
        project_root = self._project_root_from_service(tmp_path)
        assert project_root == src_doctrine

    def test_kittify_doctrine_outranks_src_doctrine(self, tmp_path: Path) -> None:
        """Phase 3 candidate beats legacy src/charter/offering/ (priority ordering)."""
        _write_min_config(tmp_path)
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        src_doctrine = tmp_path / "src" / "charter" / "offering"
        src_doctrine.mkdir(parents=True)
        project_root = self._project_root_from_service(tmp_path)
        assert project_root == kittify_doctrine


# ---------------------------------------------------------------------------
# Tests for context._build_doctrine_service (T025 mirror)
# ---------------------------------------------------------------------------

class TestContextDoctrineService:
    """The context module's _build_doctrine_service uses the same candidate list."""

    def _project_root_from_context_service(self, repo_root: Path) -> Path | None:
        from charter.activation.context import _build_doctrine_service
        svc = _build_doctrine_service(repo_root)
        return getattr(svc, "_project_root", None)

    def test_case_r2_1_no_candidate_dirs_none(self, tmp_path: Path) -> None:
        assert self._project_root_from_context_service(tmp_path) is None

    def test_case_r2_2_kittify_doctrine_present(self, tmp_path: Path) -> None:
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        result = self._project_root_from_context_service(tmp_path)
        assert result == kittify_doctrine

    def test_case_r2_3_kittify_doctrine_empty(self, tmp_path: Path) -> None:
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)
        result = self._project_root_from_context_service(tmp_path)
        assert result == kittify_doctrine

    def test_compiler_and_context_agree_on_same_candidate(
        self, tmp_path: Path
    ) -> None:
        """Both compiler and context resolve the same project_root for the same repo."""
        _write_min_config(tmp_path)
        kittify_doctrine = tmp_path / ".kittify" / "doctrine"
        kittify_doctrine.mkdir(parents=True)

        compiler_root = None
        svc = _default_doctrine_service(tmp_path)
        compiler_root = getattr(svc, "_project_root", None)

        context_root = self._project_root_from_context_service(tmp_path)
        assert compiler_root == context_root == kittify_doctrine
