"""Coverage for ``kind_vocabulary._scan_roots``' fail-soft built-in branch.

The built-in doctrine relocation (mission
doctrine-built-in-seam-consolidation-01KYW3TX) routed ``_scan_roots`` through the
shared :func:`charter.offering.pack_paths.built_in_dir` seam and wrapped it in a
best-effort ``try/except``: if the built-in root cannot be resolved
(:class:`~charter.offering.pack_paths.PackRootNotFound`) or the kind has no shipped
content dir (:class:`~charter.offering.pack_paths.BuiltInContentDirNotAvailable`), the
charter-catalog *render* path degrades to the org/project roots instead of
raising. (The authoritative *load* path in ``charter.offering.base`` fails closed on
``PackRootNotFound`` instead -- see ``tests/doctrine/test_loader_fail_closed.py``;
this render path is intentionally the softer sibling.)

This pins that fail-soft branch, which is otherwise only exercised on a broken
install and so was invisible to the rest of the suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import kind_vocabulary
from charter.activation.kind_vocabulary import (
    _built_in_scan_dir,
    _layer_candidate_dir,
    _layer_scan_dirs,
    _org_scan_dirs,
    _scan_roots,
    resolve_artifact_urn,
)
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import BuiltInContentDirNotAvailable, PackRootNotFound

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    "exc",
    [
        PackRootNotFound("built-in"),
        BuiltInContentDirNotAvailable(ArtifactKind.TACTIC),
    ],
    ids=["pack-root-not-found", "no-content-dir"],
)
def test_scan_roots_degrades_when_built_in_dir_unresolvable(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    """``built_in_dir`` raising must be swallowed, not propagated.

    With no org/layer roots supplied, the result is empty -- the built-in dir
    was dropped rather than crashing the render path.
    """

    def _raise(_kind: ArtifactKind) -> Path:
        raise exc

    monkeypatch.setattr(kind_vocabulary, "built_in_dir", _raise)

    result = _scan_roots(
        ArtifactKind.TACTIC,
        _offering_root=Path("/nonexistent"),
        org_roots=None,
        layer_roots=None,
    )

    assert result == []


def test_scan_roots_still_returns_org_root_when_built_in_unresolvable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Fail-soft on built-in must not discard a legitimate org root."""

    def _raise(_kind: ArtifactKind) -> Path:
        raise PackRootNotFound("built-in")

    monkeypatch.setattr(kind_vocabulary, "built_in_dir", _raise)

    org_built_in = tmp_path / ArtifactKind.TACTIC.plural / "built-in"
    org_built_in.mkdir(parents=True)

    result = _scan_roots(
        ArtifactKind.TACTIC,
        _offering_root=Path("/nonexistent"),
        org_roots=[tmp_path],
        layer_roots=None,
    )

    assert (org_built_in, True) in result


# ---------------------------------------------------------------------------
# Direct coverage for the helpers extracted from ``_scan_roots`` during Sonar
# S3776 cognitive-complexity remediation (WP03).
# ---------------------------------------------------------------------------


class TestBuiltInScanDirHelper:
    def test_returns_none_when_built_in_dir_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(_kind: ArtifactKind) -> Path:
            raise PackRootNotFound("built-in")

        monkeypatch.setattr(kind_vocabulary, "built_in_dir", _raise)
        assert _built_in_scan_dir(ArtifactKind.TACTIC) is None

    def test_returns_none_when_resolved_dir_does_not_exist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist"
        monkeypatch.setattr(kind_vocabulary, "built_in_dir", lambda _kind: missing)
        assert _built_in_scan_dir(ArtifactKind.TACTIC) is None

    def test_returns_recursive_pair_when_dir_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        present = tmp_path / "built-in"
        present.mkdir()
        monkeypatch.setattr(kind_vocabulary, "built_in_dir", lambda _kind: present)
        assert _built_in_scan_dir(ArtifactKind.TACTIC) == (present, True)


class TestOrgScanDirsHelper:
    def test_none_org_roots_returns_empty_list(self) -> None:
        assert _org_scan_dirs(ArtifactKind.TACTIC, None) == []

    def test_missing_org_built_in_dir_skipped(self, tmp_path: Path) -> None:
        assert _org_scan_dirs(ArtifactKind.TACTIC, [tmp_path]) == []

    def test_existing_org_built_in_dir_returned(self, tmp_path: Path) -> None:
        """Legacy shape still resolves -- unmodified behavior for the legacy
        dir itself. ``mkdir(parents=True)`` for the ``built-in`` subdirectory
        also creates its flat parent (``<root>/<plural>``), so post-fix that
        flat entry is *also* returned, ordered first -- this is the FR-001
        "both present" case (Acceptance Scenario 3), not a regression: the
        legacy dir's own presence and recursive flag are unchanged.
        """
        flat = tmp_path / ArtifactKind.TACTIC.plural
        candidate = flat / "built-in"
        candidate.mkdir(parents=True)
        # WP02: the flat org entry is now recursive (shared authority, C-001),
        # matching the loader; the legacy `built-in` entry is unchanged.
        assert _org_scan_dirs(ArtifactKind.TACTIC, [tmp_path]) == [
            (flat, True),
            (candidate, True),
        ]

    def test_flat_only_dir_returned_recursive(self, tmp_path: Path) -> None:
        """Flat-only: only ``<root>/<plural>`` exists -> one recursive entry (WP02)."""
        flat = tmp_path / ArtifactKind.TACTIC.plural
        flat.mkdir(parents=True)
        assert _org_scan_dirs(ArtifactKind.TACTIC, [tmp_path]) == [(flat, True)]

    def test_flat_only_resolves_via_resolve_artifact_urn_without_raising(
        self, tmp_path: Path
    ) -> None:
        """User Story 1 Acceptance Scenario 2: a flat-only fixture (no
        ``built-in/`` directory anywhere under the org root) resolves via
        :func:`resolve_artifact_urn` and does not raise
        :class:`UnknownArtifactIdError`.
        """
        org_root = tmp_path
        directives_dir = org_root / ArtifactKind.DIRECTIVE.plural
        directives_dir.mkdir(parents=True)
        stem = "flat-only-fixture-directive"
        (directives_dir / f"{stem}.directive.yaml").write_text(
            "id: FLAT_ONLY_FIXTURE_DIRECTIVE\n", encoding="utf-8"
        )
        offering_root = tmp_path / "doctrine-root-unused"

        urn = resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            stem,
            offering_root=offering_root,
            org_roots=[org_root],
        )

        assert urn == "directive:FLAT_ONLY_FIXTURE_DIRECTIVE"

    def test_legacy_only_dir_returned_recursive(self, tmp_path: Path) -> None:
        """Legacy-only, no artifact files of its own directly under the flat
        parent: ``<root>/<plural>/built-in`` exists (with no sibling files
        directly under ``<root>/<plural>`` itself) -> the legacy entry is
        returned, recursive -- effectively pre-existing behavior, added as
        an explicit case per FR-003's enumeration. The flat *directory*
        object necessarily also exists here (a subdirectory cannot exist
        without its parent existing on disk), so the flat entry is returned
        too, ordered first -- this is the same directory-existence contract
        the "both present" case above exercises, not a distinct return
        shape; asserted explicitly (not just "legacy dir present") to pin
        the exact order and recursive flag on both entries.
        """
        legacy = tmp_path / ArtifactKind.TACTIC.plural / "built-in"
        legacy.mkdir(parents=True)
        # WP02: flat entry now recursive (shared authority); legacy unchanged.
        assert _org_scan_dirs(ArtifactKind.TACTIC, [tmp_path]) == [
            (tmp_path / ArtifactKind.TACTIC.plural, True),
            (legacy, True),
        ]

    # PR-TESTS-001 (severity 2, pre-merge adversarial squad): a prior
    # `test_neither_dir_present_returns_empty_list` case here ("neither
    # directory exists -> []") was removed as redundant. Verified directly
    # (function-body-only revert of `_org_scan_dirs` to the pre-mission
    # single-candidate shape, `uv run pytest
    # tests/charter/test_kind_vocabulary_scan_roots.py
    # tests/charter/test_org_scan_dirs_activation_regression.py -q`): 7
    # failed, 14 passed, and the removed test was not among the 7 failures
    # -- it stayed green under both the pre-fix and post-fix implementation
    # bodies (`is_dir()` is `False` for every candidate either way), so it
    # carried no fix-specific discriminating signal. Its "nothing to scan"
    # outcome is already covered by `test_none_org_roots_returns_empty_list`
    # (`org_roots=None`) and `test_missing_org_built_in_dir_skipped`
    # (`org_roots=[<existing root with no plural subdir>]`) above.

    def test_same_config_stem_precedence_flat_wins(self, tmp_path: Path) -> None:
        """FR-001's precedence rule / Acceptance Scenario 4: a same-config-stem
        artifact file present under both the flat and legacy directories
        resolves to the flat file's URN, never the legacy file's, and never a
        result that depends on incidental scan order.
        """
        org_root = tmp_path
        stem = "same-stem-precedence-directive"
        flat_dir = org_root / ArtifactKind.DIRECTIVE.plural
        legacy_dir = flat_dir / "built-in"
        flat_dir.mkdir(parents=True)
        legacy_dir.mkdir(parents=True)
        (flat_dir / f"{stem}.directive.yaml").write_text(
            "id: DIRECTIVE_FLAT\n", encoding="utf-8"
        )
        (legacy_dir / f"{stem}.directive.yaml").write_text(
            "id: DIRECTIVE_LEGACY\n", encoding="utf-8"
        )
        offering_root = tmp_path / "doctrine-root-unused"

        urn = resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            stem,
            offering_root=offering_root,
            org_roots=[org_root],
        )

        assert urn == "directive:DIRECTIVE_FLAT"

    @pytest.mark.parametrize(
        "root_order",
        ["flat_root_first", "legacy_root_first"],
    )
    def test_multi_root_precedence_flat_wins_regardless_of_root_order(
        self, tmp_path: Path, root_order: str
    ) -> None:
        """PR-BOUNDARY-002 regression (pre-merge adversarial squad, severity 3).

        FR-001's precedence rule ("flat-layout file wins") is worded *for one
        org root*. This mission's operator ruled that scope too narrow to ship
        as-is: with >=2 org roots, ``_org_scan_dirs`` used to append entries
        per root (``flat_1, legacy_1, flat_2, legacy_2, ...``), so a
        legacy-shaped root listed *before* a flat-shaped root could still win
        a same-config-stem collision -- contradicting the documented,
        tested-at-single-root precedence guarantee. This is a deliberate,
        operator-authorized widening beyond FR-001's literal text (not
        something the spec already required): the fix groups all flat entries
        (in org-root order) before all legacy entries (in org-root order),
        globally across the whole ``org_roots`` list.

        Two org roots for the *same* colliding config stem: ``legacy_root``
        has only the legacy ``<root>/<plural>/built-in`` file, ``flat_root``
        has only the flat ``<root>/<plural>`` file. Exercised in both root
        orderings so the assertion cannot pass by ordering luck: under the
        pre-fix interleaved-per-root implementation,
        ``org_roots=[legacy_root, flat_root]`` returns
        ``[.../legacy_root/<plural> (empty), .../legacy_root/<plural>/built-in
        (matches), .../flat_root/<plural> (matches)]`` -- the legacy file's
        URN is the first match, so it wins. The reverse ordering
        (``[flat_root, legacy_root]``) happens to already return the correct
        flat-wins result under the old code (flat is listed first only
        because its root is listed first), which is exactly the "ordering
        luck" this parametrization is written to not rely on.
        """
        stem = "multi-root-precedence-directive"
        legacy_root = tmp_path / "legacy-root"
        flat_root = tmp_path / "flat-root"
        legacy_dir = legacy_root / ArtifactKind.DIRECTIVE.plural / "built-in"
        flat_dir = flat_root / ArtifactKind.DIRECTIVE.plural
        legacy_dir.mkdir(parents=True)
        flat_dir.mkdir(parents=True)
        (legacy_dir / f"{stem}.directive.yaml").write_text(
            "id: DIRECTIVE_LEGACY_A\n", encoding="utf-8"
        )
        (flat_dir / f"{stem}.directive.yaml").write_text(
            "id: DIRECTIVE_FLAT_B\n", encoding="utf-8"
        )
        org_roots = (
            [flat_root, legacy_root]
            if root_order == "flat_root_first"
            else [legacy_root, flat_root]
        )
        offering_root = tmp_path / "doctrine-root-unused"

        urn = resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            stem,
            offering_root=offering_root,
            org_roots=org_roots,
        )

        assert urn == "directive:DIRECTIVE_FLAT_B"


class TestLayerCandidateDirHelper:
    def test_project_layer_uses_project_kind_dirs_mapping(self, tmp_path: Path) -> None:
        # The project layer root is the project pack root: kind dirs join straight onto it.
        expected = tmp_path / kind_vocabulary.PROJECT_KIND_DIRS.get(
            ArtifactKind.TACTIC, ArtifactKind.TACTIC.plural
        )
        assert _layer_candidate_dir(ArtifactKind.TACTIC, "project", tmp_path) == expected

    def test_non_project_layer_has_no_candidate(self, tmp_path: Path) -> None:
        """The retired nested ``<pack>/doctrine/<plural>/<layer>`` layout is not read (FR-011)."""
        (tmp_path / "doctrine" / ArtifactKind.TACTIC.plural / "org").mkdir(parents=True)
        assert _layer_candidate_dir(ArtifactKind.TACTIC, "org", tmp_path) is None


class TestLayerScanDirsHelper:
    def test_none_layer_roots_returns_empty_list(self) -> None:
        assert _layer_scan_dirs(ArtifactKind.TACTIC, None) == []

    def test_missing_layer_dir_skipped(self, tmp_path: Path) -> None:
        assert _layer_scan_dirs(ArtifactKind.TACTIC, {"org": tmp_path}) == []

    def test_existing_layer_dir_returned_as_recursive(self, tmp_path: Path) -> None:
        """WP02: layer dirs recurse via the shared authority (C-001)."""
        candidate = _layer_candidate_dir(ArtifactKind.TACTIC, "project", tmp_path)
        assert candidate is not None
        candidate.mkdir(parents=True)
        assert _layer_scan_dirs(ArtifactKind.TACTIC, {"project": tmp_path}) == [
            (candidate, True)
        ]

    def test_a_nested_org_layer_dir_is_not_scanned(self, tmp_path: Path) -> None:
        (tmp_path / "doctrine" / ArtifactKind.TACTIC.plural / "org").mkdir(parents=True)
        assert _layer_scan_dirs(ArtifactKind.TACTIC, {"org": tmp_path}) == []
