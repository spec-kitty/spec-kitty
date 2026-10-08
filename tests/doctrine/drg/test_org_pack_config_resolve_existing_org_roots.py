"""Unit tests for ``resolve_existing_org_roots`` (#3525, Fold A).

Covers the shared, declaration-order, existing-path-filtered primitive that
:func:`charter.offering.drg.org_pack_config.resolve_org_dirs` and every runtime
"does this org root actually exist" consumer (``charter.activation.mission_type_profiles``,
``specify_cli.dossier.manifest``, ``charter.activation.active_charter_service_builder``) now
route onto, instead of each re-implementing the same filter comprehension
independently.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import (
    resolve_existing_org_roots,
    resolve_org_dirs,
    resolve_org_roots,
)

_LOGGER_NAME = "charter.offering.drg.org_pack_config"

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def _write_config(repo_root: Path, packs: list[tuple[str, Path]]) -> None:
    """Write a canonical ``doctrine.org.packs`` config.yaml with *packs* in order."""
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


class TestExistenceFiltering:
    def test_no_org_packs_returns_empty_list(self, tmp_path: Path) -> None:
        assert resolve_existing_org_roots(tmp_path) == []

    def test_filters_out_nonexistent_roots(self, tmp_path: Path) -> None:
        valid_root = tmp_path / "valid-pack"
        valid_root.mkdir()
        stale_root = tmp_path / "stale-pack-never-fetched"
        # Deliberately not created on disk.
        _write_config(tmp_path, [("valid-pack", valid_root), ("stale-pack", stale_root)])

        result = resolve_existing_org_roots(tmp_path)

        assert result == [valid_root.resolve(strict=False)]
        assert stale_root.resolve(strict=False) not in result

    def test_all_missing_returns_empty_list(self, tmp_path: Path) -> None:
        stale_root = tmp_path / "stale-pack"
        _write_config(tmp_path, [("stale-pack", stale_root)])

        assert resolve_existing_org_roots(tmp_path) == []


class TestOrderPreservation:
    def test_two_existing_roots_preserve_declaration_order(self, tmp_path: Path) -> None:
        """NFR-003: declared order is preserved, not sorted/reversed."""
        first_root = tmp_path / "z-pack"
        first_root.mkdir()
        second_root = tmp_path / "a-pack"
        second_root.mkdir()
        # Declaration order deliberately does not match lexical order, so a
        # sort-based bug would be caught.
        _write_config(tmp_path, [("z-pack", first_root), ("a-pack", second_root)])

        result = resolve_existing_org_roots(tmp_path)

        assert result == [
            first_root.resolve(strict=False),
            second_root.resolve(strict=False),
        ]

    def test_matches_resolve_org_roots_composition(self, tmp_path: Path) -> None:
        """C-1 invariant: resolve_existing_org_roots is exactly the
        existence-filter of resolve_org_roots, for a fixture with one
        existing and one missing root."""
        existing_root = tmp_path / "existing-pack"
        existing_root.mkdir()
        missing_root = tmp_path / "missing-pack"
        _write_config(
            tmp_path,
            [("existing", existing_root), ("missing", missing_root)],
        )

        expected = [root for root in resolve_org_roots(tmp_path) if root.exists()]
        assert resolve_existing_org_roots(tmp_path) == expected
        assert expected != []


class TestDropWarningLivesOnResolveOrgDirs:
    """The drop warning (NFR-002).

    ``resolve_existing_org_roots`` itself is deliberately silent (it has no
    ``subdir`` context to name in a useful message — see its docstring).
    :func:`resolve_org_dirs`, which is built on top of this primitive,
    carries the WARNING responsibility. Both halves of that contract are
    pinned here: the primitive stays quiet, and its built-atop sibling still
    emits exactly one warning naming both the dropped root and the subdir.
    """

    def test_bare_primitive_emits_no_warning_on_a_dropped_root(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        stale_root = tmp_path / "stale-pack-never-fetched"
        _write_config(tmp_path, [("stale-pack", stale_root)])

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = resolve_existing_org_roots(tmp_path)

        assert result == []
        assert not any(r.levelno == logging.WARNING for r in caplog.records)

    def test_resolve_org_dirs_built_on_the_primitive_still_warns_once(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        subdir = "mission_step_contracts"
        stale_root = tmp_path / "stale-pack-never-fetched"
        _write_config(tmp_path, [("stale-pack", stale_root)])

        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            result = resolve_org_dirs(tmp_path, subdir)

        assert result == []
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert str(stale_root.resolve(strict=False)) in message
        assert subdir in message
