"""WP04 / FR-006 -- pin the ``charter.md``-only status-collector shape.

``_collect_charter_sync_status`` (``_status_collectors.py``) resolves charter
presence primarily via ``_resolve_charter_bundle_path`` (the authoritative
``charter.yaml`` bundle, FR-005). When that resolution raises
``TaskCliError`` -- i.e. ``charter.yaml`` is absent -- the collector falls
back to the legacy ``charter.md``-only resolver (``_status_collectors.py``
``:85-87``). Per the spec (FR-006, Edge Cases, C-001) this fallback is an
**explicit, documented pre-consolidation migration-compat branch**: it
serves projects created before the ``charter.yaml`` bundle existed
(``charter.md`` present, ``charter.yaml`` absent).

This is a **characterization pin (green-first), NOT an ATDD red**. The
``charter.md``-only shape already resolves correctly today
(``_status_collectors.py:72-87``) -- this test passes on first authoring.
Its purpose is to guard the already-working behaviour so a later "scope or
remove" pass on the ``:85-87`` branch cannot silently change it without a
test noticing.

Whether the ``charter.md``-only shape should be declared *unsupported* (and
the branch flipped to an error path) is a support-scope product decision
that must be routed through the human-in-charge + issue-matrix (DIR-012 /
C-005) -- it is explicitly OUT of scope for this pin, which only asserts
today's supported behaviour.

The staleness **display** header/listing (``:74-84``, ``:103``) is
untouched by this WP (legitimate display, C-001) and is not exercised
differently here than by the existing ``test_status_json_safe.py`` suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.charter._status_collectors import (
    _collect_charter_sync_status,
)

pytestmark = [pytest.mark.fast]


def _seed_charter_md_only(repo_root: Path) -> Path:
    """Seed a pre-consolidation project: ``charter.md`` present, ``charter.yaml`` absent.

    No ``charter.yaml``, no ``metadata.yaml`` -- exactly the shape that forces
    ``_resolve_charter_bundle_path`` to raise ``TaskCliError`` and drives the
    collector into the ``:85-87`` legacy fallback.
    """
    charter_dir = repo_root / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_md_path = charter_dir / "charter.md"
    charter_md_path.write_text("# Charter\n\nLegacy pre-consolidation charter.\n", encoding="utf-8")
    return charter_md_path


@pytest.fixture()
def charter_md_only_repo(tmp_path: Path) -> Path:
    """A project root with only ``charter.md`` -- no ``charter.yaml`` bundle."""
    _seed_charter_md_only(tmp_path)
    return tmp_path


class TestLegacyCharterMdOnlyShape:
    """FR-006: pin the ``charter.md``-only status-collector resolution shape."""

    def test_resolves_available_via_legacy_md_fallback(
        self, charter_md_only_repo: Path
    ) -> None:
        """The collector reports ``available: True`` from the ``charter.md`` fallback.

        With ``charter.yaml`` absent, ``_resolve_charter_bundle_path`` raises
        and the collector must fall through to ``_resolve_charter_path``
        (the legacy ``charter.md`` resolver) rather than propagating the
        error -- this is the backward-compat contract FR-006 pins.
        """
        result = _collect_charter_sync_status(charter_md_only_repo)

        assert result["available"] is True, (
            "charter.md-only projects (pre-consolidation, no charter.yaml) "
            f"must still resolve via the legacy fallback; got {result!r}"
        )

    def test_charter_path_points_at_legacy_charter_md(
        self, charter_md_only_repo: Path
    ) -> None:
        """The resolved ``charter_path`` is the legacy ``charter.md``, not ``charter.yaml``.

        ``charter.yaml`` does not exist in this fixture, so the only
        deterministic resolution is the legacy ``charter.md`` path --
        proving the ``:85-87`` branch (not the ``charter.yaml``-bundle
        branch) is what actually resolved this collector run.
        """
        result = _collect_charter_sync_status(charter_md_only_repo)

        # A literal POSIX string, not ``str(Path(...))``: the collector reports a
        # repository-relative path POSIX on every OS (#7044), so building the
        # expectation with ``str()`` would pin the Windows separator instead.
        assert result["charter_path"] == ".kittify/charter/charter.md", result

    def test_files_info_reports_only_charter_md_present(
        self, charter_md_only_repo: Path
    ) -> None:
        """``files`` lists ``charter.yaml`` absent and ``charter.md`` present."""
        result = _collect_charter_sync_status(charter_md_only_repo)

        files_by_name = {entry["name"]: entry for entry in result["files"]}
        assert files_by_name["charter.yaml"]["exists"] is False, result
        assert files_by_name["charter.md"]["exists"] is True, result

    def test_reports_stale_with_no_charter_yaml_and_no_metadata(
        self, charter_md_only_repo: Path
    ) -> None:
        """No ``metadata.yaml`` + no ``charter.yaml`` -> reported ``stale`` (not synced).

        Mirrors the ``:94-100`` post-migration-hash-retirement branch: when
        ``metadata.yaml`` is absent, staleness is reported as the negation of
        ``charter.yaml`` presence -- which is absent in this fixture.
        """
        result = _collect_charter_sync_status(charter_md_only_repo)

        assert result["status"] == "stale", result
        assert result["current_hash"] == "", result
        assert result["stored_hash"] == "", result
        assert result["last_sync"] is None, result
