"""Unit tests for ``resolve_org_dirs`` (WP01, FR-003).

Covers T002/T003 from the WP01 task specification: the shared, declaration-order,
existing-path-filtered ``org_dirs`` resolution helper that FR-001, FR-004, FR-005
and FR-006/FR-006a will later import rather than each re-implementing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import resolve_org_dirs, resolve_org_roots

_LOGGER_NAME = "charter.offering.drg.org_pack_config"

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_SUBDIR = "mission_step_contracts"


def _write_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    """Write a canonical ``doctrine.org.packs`` config.yaml with *packs* in order.

    Each entry is ``(name, local_path)``, written in the given declaration order
    so ordering/precedence tests can rely on the YAML list order matching the
    call argument order.
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    if not packs:
        lines = ["charter_packs:", "  org:", "    packs: []"]
    else:
        lines = ["charter_packs:", "  org:", "    packs:"]
        for name, local_path in packs:
            lines.append(f"      - name: {name}")
            lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# T002 — empty config and single pack
# ---------------------------------------------------------------------------


class TestEmptyAndSinglePack:
    def test_no_org_packs_returns_empty_list(self, tmp_path: Path) -> None:
        """No .kittify/config.yaml at all -> no org contribution."""
        assert resolve_org_dirs(tmp_path, _SUBDIR) == []

    def test_no_org_packs_entries_returns_empty_list(self, tmp_path: Path) -> None:
        """config.yaml exists but declares no doctrine.org.packs entries."""
        _write_config(tmp_path, [])
        assert resolve_org_dirs(tmp_path, _SUBDIR) == []

    def test_single_pack_returns_one_joined_path(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        org_root.mkdir()
        _write_config(tmp_path, [("acme", org_root)])

        result = resolve_org_dirs(tmp_path, _SUBDIR)

        assert result == [org_root.resolve(strict=False) / _SUBDIR]

    def test_invariant_matches_resolve_org_roots_composition(self, tmp_path: Path) -> None:
        """C-1 invariant: resolve_org_dirs is exactly the join-then-filter of
        resolve_org_roots, for a fixture with one existing and one missing root."""
        existing_root = tmp_path / "existing-pack"
        existing_root.mkdir()
        missing_root = tmp_path / "missing-pack"
        # Deliberately not created on disk.
        _write_config(
            tmp_path,
            [("existing", existing_root), ("missing", missing_root)],
        )

        expected = [root / _SUBDIR for root in resolve_org_roots(tmp_path) if root.exists()]
        assert resolve_org_dirs(tmp_path, _SUBDIR) == expected
        # The invariant is only meaningful proof if it isn't vacuously []==[].
        assert expected != []


# ---------------------------------------------------------------------------
# T003 — multi-pack precedence and stale-path filtering
# ---------------------------------------------------------------------------


class TestPrecedenceAndFiltering:
    def test_two_packs_preserve_declaration_order(self, tmp_path: Path) -> None:
        """NFR-003: declared order is preserved, not sorted/reversed."""
        first_root = tmp_path / "z-pack"
        first_root.mkdir()
        second_root = tmp_path / "a-pack"
        second_root.mkdir()
        # Declaration order deliberately does not match lexical order, so a
        # sort-based bug would be caught.
        _write_config(tmp_path, [("z-pack", first_root), ("a-pack", second_root)])

        result = resolve_org_dirs(tmp_path, _SUBDIR)

        assert result == [
            first_root.resolve(strict=False) / _SUBDIR,
            second_root.resolve(strict=False) / _SUBDIR,
        ]

    def test_nonexistent_org_root_is_filtered_not_raised(self, tmp_path: Path) -> None:
        """NFR-002: a stale local_path degrades to "no contribution from that
        pack", proven distinguishably from "no org pack was ever configured"
        via a mixed fixture — one valid pack survives, one stale pack does not,
        and neither raises.
        """
        valid_root = tmp_path / "valid-pack"
        valid_root.mkdir()
        stale_root = tmp_path / "stale-pack-never-fetched"
        # Deliberately not created on disk — simulates a stale local_path entry.
        _write_config(tmp_path, [("valid-pack", valid_root), ("stale-pack", stale_root)])

        result = resolve_org_dirs(tmp_path, _SUBDIR)

        # Distinguishing signal: exactly the valid pack's directory is present,
        # and the stale pack's directory is specifically absent — not an empty
        # result that would be indistinguishable from "no org packs configured".
        assert result == [valid_root.resolve(strict=False) / _SUBDIR]
        assert stale_root.resolve(strict=False) / _SUBDIR not in result

    def test_all_org_roots_nonexistent_returns_empty_list(self, tmp_path: Path) -> None:
        """Edge case: every configured pack is stale -> [] without raising."""
        stale_root = tmp_path / "stale-pack"
        _write_config(tmp_path, [("stale-pack", stale_root)])

        assert resolve_org_dirs(tmp_path, _SUBDIR) == []

    def test_all_missing_is_distinguishable_from_nothing_configured_via_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """NFR-002: the realistic typo'd/never-fetched scenario — EVERY configured
        pack's root is missing — must not be silently indistinguishable from "no
        org pack was ever configured". Both return ``[]``; the WARNING is the
        signal that tells them apart. Companion negative case:
        ``test_no_org_packs_configured_emits_no_warning`` below proves the
        warning does not fire unconditionally.
        """
        stale_root = tmp_path / "stale-pack-never-fetched"
        _write_config(tmp_path, [("stale-pack", stale_root)])

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = resolve_org_dirs(tmp_path, _SUBDIR)

        assert result == []
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert str(stale_root.resolve(strict=False)) in message
        assert _SUBDIR in message

    def test_no_org_packs_configured_emits_no_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Negative case for the distinguishability proof above: genuinely
        nothing configured must NOT log a warning — only a dropped, configured
        root should."""
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = resolve_org_dirs(tmp_path, _SUBDIR)

        assert result == []
        assert not any(r.levelno == logging.WARNING for r in caplog.records)
