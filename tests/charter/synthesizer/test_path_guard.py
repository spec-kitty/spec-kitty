"""Tests for PathGuard (FR-016, NFR-008, US-7, R-10, T008).

Verifies:
1. Write under .kittify/charter-packs/ succeeds (allowed).
2. Write under .kittify/charter/ succeeds (allowed).
3. Write under src/charter/offering/ raises PathGuardViolation BEFORE touching filesystem.
4. Write under repo_root directly (not in allowlist) raises PathGuardViolation.
5. Path traversal (../) cannot bypass the guard.
6. Lint-style grep: no direct write primitives outside path_guard.py in
   src/charter/synthesizer/.

The lint test (test_no_direct_writes_in_synthesizer) is the R-10 mitigation.
It fails CI immediately if a new module uses Path.write_text etc. directly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.activation.synthesizer.errors import PathGuardViolation
from charter.activation.synthesizer.path_guard import PathGuard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit]

def _make_guard(repo_root: Path, extra: tuple[str, ...] = ()) -> PathGuard:
    """Create a PathGuard with the default allowlist (+ optional extras)."""
    return PathGuard(repo_root=repo_root, extra_allowed_prefixes=extra)


# ---------------------------------------------------------------------------
# 1. Allowed writes succeed
# ---------------------------------------------------------------------------


class TestAllowedWrites:
    def test_write_text_under_kittify_doctrine_succeeds(self, tmp_path: Path) -> None:
        """write_text under .kittify/charter-packs/ is allowed by default."""
        guard = _make_guard(tmp_path)
        target_dir = tmp_path / ".kittify" / "charter-packs" / "directive"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "001-test.directive.yaml"

        guard.write_text(target_file, "id: PROJECT_001\n")
        assert target_file.read_text() == "id: PROJECT_001\n"

    def test_write_text_under_kittify_charter_succeeds(self, tmp_path: Path) -> None:
        """write_text under .kittify/charter/ is allowed by default."""
        guard = _make_guard(tmp_path)
        target_dir = tmp_path / ".kittify" / "charter" / "provenance"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "directive-test.yaml"

        guard.write_text(target_file, "artifact_urn: directive:PROJECT_001\n")
        assert target_file.exists()

    def test_write_bytes_under_kittify_doctrine_succeeds(self, tmp_path: Path) -> None:
        """write_bytes under .kittify/charter-packs/ is allowed."""
        guard = _make_guard(tmp_path)
        target_dir = tmp_path / ".kittify" / "charter-packs" / "tactic"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "test.tactic.yaml"

        guard.write_bytes(target_file, b"id: test-tactic\n")
        assert target_file.read_bytes() == b"id: test-tactic\n"

    def test_mkdir_under_kittify_charter_succeeds(self, tmp_path: Path) -> None:
        """mkdir under .kittify/charter/ is allowed."""
        guard = _make_guard(tmp_path)
        new_dir = tmp_path / ".kittify" / "charter" / ".staging" / "01TESTRUN"
        guard.mkdir(new_dir)
        assert new_dir.is_dir()

    def test_replace_between_allowed_paths_succeeds(self, tmp_path: Path) -> None:
        """replace between two allowed paths succeeds (atomic promote)."""
        guard = _make_guard(tmp_path)
        staging_dir = tmp_path / ".kittify" / "charter" / ".staging" / "run1" / "charter-packs"
        staging_dir.mkdir(parents=True)
        src = staging_dir / "test.directive.yaml"
        src.write_text("body: ok")

        live_dir = tmp_path / ".kittify" / "charter-packs" / "directive"
        live_dir.mkdir(parents=True)
        dst = live_dir / "001-test.directive.yaml"

        guard.replace(src, dst)
        assert dst.exists()
        assert not src.exists()


# ---------------------------------------------------------------------------
# 2. Forbidden writes raise PathGuardViolation BEFORE touching filesystem
# ---------------------------------------------------------------------------


class TestForbiddenWrites:
    def test_write_text_under_src_doctrine_raises(self, tmp_path: Path) -> None:
        """Write targeting src/charter/offering/ raises PathGuardViolation before touching fs."""
        guard = _make_guard(tmp_path)
        forbidden_dir = tmp_path / "src" / "charter" / "offering" / "directives"
        forbidden_dir.mkdir(parents=True)
        forbidden_file = forbidden_dir / "hacked.directive.yaml"

        with pytest.raises(PathGuardViolation) as exc_info:
            guard.write_text(forbidden_file, "malicious content")

        # File must NOT exist — guard fired before any write
        assert not forbidden_file.exists()
        assert "src" in exc_info.value.attempted_path or "doctrine" in exc_info.value.attempted_path

    def test_write_text_at_repo_root_raises(self, tmp_path: Path) -> None:
        """Write at repo root (not under any allowed prefix) raises PathGuardViolation."""
        guard = _make_guard(tmp_path)
        forbidden = tmp_path / "not-allowed.yaml"

        with pytest.raises(PathGuardViolation):
            guard.write_text(forbidden, "not allowed")

        assert not forbidden.exists()

    def test_write_bytes_under_forbidden_path_raises(self, tmp_path: Path) -> None:
        """write_bytes raises PathGuardViolation for forbidden paths."""
        guard = _make_guard(tmp_path)
        forbidden = tmp_path / "some" / "other" / "path.yaml"

        with pytest.raises(PathGuardViolation):
            guard.write_bytes(forbidden, b"data")

        assert not forbidden.exists()

    def test_mkdir_under_forbidden_path_raises(self, tmp_path: Path) -> None:
        """mkdir raises PathGuardViolation for forbidden paths."""
        guard = _make_guard(tmp_path)
        forbidden = tmp_path / "src" / "charter" / "offering" / "new-dir"

        with pytest.raises(PathGuardViolation):
            guard.mkdir(forbidden)

        assert not forbidden.exists()

    def test_replace_with_forbidden_dst_raises(self, tmp_path: Path) -> None:
        """replace raises PathGuardViolation when dst is outside allowlist."""
        guard = _make_guard(tmp_path)
        # src is allowed (staging)
        staging = tmp_path / ".kittify" / "charter" / ".staging" / "r1"
        staging.mkdir(parents=True)
        src = staging / "file.yaml"
        src.write_text("ok")

        # dst is forbidden
        forbidden_dst = tmp_path / "src" / "charter" / "offering" / "file.yaml"
        forbidden_dst.parent.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathGuardViolation):
            guard.replace(src, forbidden_dst)

        assert not forbidden_dst.exists()
        assert src.exists()  # src not consumed because guard fired first

    def test_path_traversal_is_blocked(self, tmp_path: Path) -> None:
        """Path traversal (../) cannot bypass the guard."""
        guard = _make_guard(tmp_path)
        # Attempt: .kittify/charter-packs/../../src/charter/offering/evil.yaml
        # After resolution this lands outside the allowlist.

        traversal = tmp_path / ".kittify" / "charter-packs" / ".." / ".." / "src" / "charter" / "offering" / "evil.yaml"
        # The guard resolves paths via Path.resolve() before comparison.
        traversal.parent.mkdir(parents=True, exist_ok=True)

        with pytest.raises(PathGuardViolation):
            guard.write_text(traversal, "evil")

        resolved = traversal.resolve()
        assert not resolved.exists()


# ---------------------------------------------------------------------------
# 3. Extra allowed prefixes work (used by tests)
# ---------------------------------------------------------------------------


class TestExtraAllowedPrefixes:
    def test_extra_prefix_allows_writes(self, tmp_path: Path) -> None:
        """extra_allowed_prefixes extends the allowlist."""
        extra_dir = tmp_path / "test_output"
        extra_dir.mkdir()
        guard = PathGuard(repo_root=tmp_path, extra_allowed_prefixes=[extra_dir])
        target = extra_dir / "result.yaml"
        guard.write_text(target, "ok")
        assert target.read_text() == "ok"


# ---------------------------------------------------------------------------
# 4. Lint-style grep: no direct writes in synthesizer modules (R-10)
# ---------------------------------------------------------------------------


class TestNoDirectWritesInSynthesizer:
    """Lint-style test: grep src/charter/synthesizer/ for direct write primitives.

    Any hit outside path_guard.py fails this test. This is the R-10 mitigation
    that runs in CI to catch future bypass regressions.
    """

    # Patterns that indicate a direct write bypassing PathGuard.
    # Uses negative lookbehind (?<!guard) to exclude PathGuard method calls
    # (e.g. guard.write_text, guard.write_bytes, guard.rename) which ARE the
    # sanctioned write seam and must not be flagged (R-10, WP03 addition).
    _FORBIDDEN_PATTERNS = [
        r"open\s*\(.*['\"]w['\"]",                    # open(..., 'w') or open(..., "w")
        r"open\s*\(.*['\"]wb['\"]",                   # open(..., 'wb')
        r"open\s*\(.*['\"]a['\"]",                    # open(..., 'a')
        r"(?<!guard)(?<!self\.guard)\.write_text\s*\(",   # Path.write_text( (not guard.write_text)
        r"(?<!guard)(?<!self\.guard)\.write_bytes\s*\(",  # Path.write_bytes( (not guard.write_bytes)
        r"shutil\.move\s*\(",                         # shutil.move(
        r"shutil\.copy\s*\(",                         # shutil.copy(
        r"shutil\.copy2\s*\(",                        # shutil.copy2(
        r"os\.replace\s*\(",                          # os.replace(
        r"os\.rename\s*\(",                           # os.rename(
        r"(?<!guard)(?<!self\.guard)\.rename\s*\(",       # Path.rename( (not guard.rename)
    ]

    # Modules exempt from the check (path_guard.py IS the write seam)
    _EXEMPT_FILES = {"path_guard.py"}

    def _find_synthesizer_dir(self) -> Path:
        """Locate src/charter/activation/synthesizer/ relative to this test file.

        Relocated by mission charter-activation-split-01M16ZSE (MAP-A MOVE).
        """
        repo_root = Path(__file__).parent.parent.parent.parent
        return repo_root / "src" / "charter" / "activation" / "synthesizer"

    # Patterns that indicate a call is delegating through a PathGuard variable
    # rather than writing directly.  A line that already contains a PathGuard
    # method call (e.g. ``guard.write_text(...)``) is NOT a bypass — the guard
    # enforces allowlist checking internally (WP04 extension).
    _PATHGUARD_DELEGATION_PREFIXES = (
        "guard.",
        "self._guard.",
        "_guard.",
        "path_guard.",
        "pg.",
    )

    def _is_pathguard_delegation(self, line: str) -> bool:
        """Return True if the line calls a method through a PathGuard variable."""
        stripped = line.strip()
        return any(stripped.startswith(prefix) for prefix in self._PATHGUARD_DELEGATION_PREFIXES)

    def test_no_direct_writes_outside_path_guard(self) -> None:
        """No direct write primitives in src/charter/synthesizer/ outside path_guard.py."""
        synth_dir = self._find_synthesizer_dir()
        assert synth_dir.exists(), f"Synthesizer dir not found at {synth_dir}"

        violations: list[str] = []
        for py_file in sorted(synth_dir.glob("*.py")):
            if py_file.name in self._EXEMPT_FILES:
                continue
            source = py_file.read_text(encoding="utf-8")
            lines = source.splitlines()
            for i, line in enumerate(lines, 1):
                # Skip comment lines
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                # Skip lines that delegate through a PathGuard variable — these
                # ARE the approved write path, not a bypass (WP04 extension).
                if self._is_pathguard_delegation(line):
                    continue
                for pattern in self._FORBIDDEN_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(
                            f"{py_file.name}:{i}: matches pattern '{pattern}': {line.rstrip()}"
                        )

        assert not violations, (
            "Direct write primitives found outside path_guard.py — "
            "all synthesizer writes must go through PathGuard methods (R-10):\n"
            + "\n".join(f"  {v}" for v in violations)
        )
