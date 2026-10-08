"""Tests for the ``pack_version`` derive-else-fallback seam (WP04, T015).

IC-06 (pack-metadata-manifest-unification-01M052PT): ``pack_version`` is
relocated from the generated manifest to the authored ``pack.yaml`` for the
**built-in** pack only. Fetched/org packs keep it as genuine generated
provenance (``snapshot.py``'s writer is unchanged) because it is a required
key of ``_has_recognisable_pack_manifest``. The two real consumers this
tests pin:

* :func:`specify_cli.cli.commands._doctrine_collect._resolve_pack_version`
  (the real resolver; ``doctor.py`` only re-exports it).
* :func:`charter.offering.packs.pack_assembler._has_recognisable_pack_manifest`
  (must still recognise a fetched-pack manifest that carries the generated
  ``pack_version`` key, AND must newly recognise a built-in-shaped manifest
  that omits it in favour of a sibling authored ``pack.yaml``).

All fixtures here are synthetic (``tmp_path``) rather than the real
``packs/built-in/`` tree, so this module deliberately does NOT read the
wheel-shipped doctrine corpus and does not need ``pytest.mark.corpus``
(``tests/architectural/test_pack_manifest_no_author_edit.py`` covers the real
built-in files).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.cli.commands._doctrine_collect import _resolve_pack_version
from charter.offering.packs.pack_assembler import _has_recognisable_pack_manifest

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _fetched_pack_manifest_payload(*, pack_version: str = "9.9.9") -> dict[str, object]:
    """A minimal generated manifest payload shaped like a fetched/org pack."""
    return {
        "artifact_counts": {"directives": 3},
        "fetched_at": "2026-08-16T00:00:00+00:00",
        "pack_version": pack_version,
        "source_type": "git",
        "source_url": "https://example.invalid/org-pack.git",
    }


# ---------------------------------------------------------------------------
# _resolve_pack_version (the real resolver, _doctrine_collect.py:81)
# ---------------------------------------------------------------------------


class TestResolvePackVersionAuthoredWhenPresent:
    def test_authored_pack_yaml_wins_over_generated_manifest(self, tmp_path: Path) -> None:
        """A built-in-shaped pack: authored pack.yaml + a generated manifest
        that (correctly, per its own generator) carries no pack_version at
        all -- the resolver must still surface the authored value."""
        _write_yaml(tmp_path / "pack.yaml", {"pack_id": "01ARWG13C000000000000000FG", "pack_version": "2.3.4"})
        _write_yaml(
            tmp_path / "pack-manifest.yaml",
            {"schema_version": "1.0", "constituents": []},
        )

        version, fetched_at, is_git = _resolve_pack_version(tmp_path)

        assert version == "2.3.4"
        assert fetched_at is None
        assert is_git is False

    def test_authored_pack_yaml_wins_even_when_generated_manifest_also_has_it(
        self, tmp_path: Path
    ) -> None:
        """Authored takes priority regardless of what the generated file says."""
        _write_yaml(tmp_path / "pack.yaml", {"pack_version": "5.0.0"})
        _write_yaml(tmp_path / "pack-manifest.yaml", _fetched_pack_manifest_payload(pack_version="1.0.0"))

        version, _fetched_at, _is_git = _resolve_pack_version(tmp_path)

        assert version == "5.0.0"

    def test_pack_yaml_without_pack_version_field_falls_back(self, tmp_path: Path) -> None:
        """An authored descriptor present but missing the field is not a
        value -- falls through to the generated manifest, not 'unknown'."""
        _write_yaml(tmp_path / "pack.yaml", {"pack_id": "01ARWG13C000000000000000FG"})
        _write_yaml(tmp_path / "pack-manifest.yaml", _fetched_pack_manifest_payload(pack_version="7.7.7"))

        version, _fetched_at, _is_git = _resolve_pack_version(tmp_path)

        assert version == "7.7.7"


class TestResolvePackVersionGeneratedFallback:
    """Regression pin: no pack.yaml at all -- unchanged (fetched/org) behavior."""

    def test_no_pack_yaml_resolves_generated_manifest_value(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "pack-manifest.yaml", _fetched_pack_manifest_payload(pack_version="9.9.9"))

        version, fetched_at, is_git = _resolve_pack_version(tmp_path)

        assert version == "9.9.9"
        assert fetched_at == "2026-08-16T00:00:00+00:00"
        assert is_git is False

    def test_no_pack_yaml_and_no_manifest_resolves_unknown(self, tmp_path: Path) -> None:
        version, fetched_at, is_git = _resolve_pack_version(tmp_path)

        assert version == "unknown"
        assert fetched_at is None
        assert is_git is False

    def test_git_pack_still_takes_precedence_over_a_missing_authored_descriptor(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / ".git").mkdir()

        version, fetched_at, is_git = _resolve_pack_version(tmp_path)

        assert fetched_at is None
        assert is_git is True
        # `git describe` fails in a bare/empty repo dir; either branch of the
        # existing fallback is fine here -- the point pinned is that reaching
        # the git branch at all was not short-circuited by the new authored
        # check when there is no pack.yaml.
        assert version  # non-empty string, either real describe output or the sentinel


# ---------------------------------------------------------------------------
# _has_recognisable_pack_manifest (pack_assembler.py:377/390)
# ---------------------------------------------------------------------------


class TestHasRecognisablePackManifest:
    def test_fetched_pack_with_generated_pack_version_stays_recognisable(
        self, tmp_path: Path
    ) -> None:
        """Regression pin (unchanged behavior): the ordinary fetched/org
        shape -- pack_version present on the generated manifest, no
        pack.yaml -- must keep passing exactly as before."""
        _write_yaml(tmp_path / "pack-manifest.yaml", _fetched_pack_manifest_payload())

        assert _has_recognisable_pack_manifest(tmp_path) is True

    def test_built_in_shaped_manifest_without_pack_version_is_recognisable_via_authored_sibling(
        self, tmp_path: Path
    ) -> None:
        """New behavior: a generated manifest omitting pack_version (as the
        built-in generator does) is still recognisable when a sibling
        authored pack.yaml supplies the value."""
        _write_yaml(
            tmp_path / "pack-manifest.yaml",
            {
                "artifact_counts": {"directives": 1},
                "fetched_at": None,
                "source_type": "assemble",
                "source_url": "packs/built-in",
            },
        )
        _write_yaml(tmp_path / "pack.yaml", {"pack_id": "01ARWG13C000000000000000FG", "pack_version": "1.0.0"})

        assert _has_recognisable_pack_manifest(tmp_path) is True

    def test_manifest_without_pack_version_and_without_authored_sibling_is_unrecognisable(
        self, tmp_path: Path
    ) -> None:
        """Neither source has it -- still correctly refused (fail-closed, no
        silent widening of what counts as 'a pack')."""
        _write_yaml(
            tmp_path / "pack-manifest.yaml",
            {
                "artifact_counts": {"directives": 1},
                "fetched_at": None,
                "source_type": "assemble",
                "source_url": "packs/built-in",
            },
        )

        assert _has_recognisable_pack_manifest(tmp_path) is False

    def test_other_required_keys_are_still_hard_required(self, tmp_path: Path) -> None:
        """The derive-else-fallback change is scoped to pack_version only --
        every other required key stays a hard requirement."""
        payload = _fetched_pack_manifest_payload()
        del payload["source_url"]
        _write_yaml(tmp_path / "pack-manifest.yaml", payload)

        assert _has_recognisable_pack_manifest(tmp_path) is False
