"""Org-tier fail-loud coverage for ``expected-artifacts.yaml`` (WP03, #3412).

FR-007/FR-008/FR-012/NFR-005, C-004/C-006. Complements the pre-existing
``tests/charter/test_org_expected_artifacts.py`` (which now asserts the
POST-fix fail-loud behaviour for the malformed-file class instead of the
old warn-and-swallow one -- see that file's ``TestResolveOrgExpectedArtifactsMalformedFile``).

This module drives the sibling-error model end to end at the org-tier
reader (:func:`resolve_org_expected_artifacts` / ``_read_yaml_mapping``):

- Present-but-broken (YAML-syntax, non-mapping, unreadable) -> raises
  :class:`MalformedManifestError` (charter,
  ``charter.offering.missions.repository``). NEVER
  :class:`~charter.activation.manifest_loader.ManifestSchemaError` -- that
  sibling is reserved for schema/``extra=forbid`` faults (D2).
- Genuinely absent -> ``None`` (Invariant I1), unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.manifest_loader import clear_cache, load_manifest
from charter.activation.org_expected_artifacts import resolve_org_expected_artifacts
from charter.offering.missions.repository import MalformedManifestError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Write ``<repo_root>/.kittify/config.yaml`` with a ``doctrine.org.packs``
    registry, mirroring ``tests/dossier/test_manifest.py``'s helper of the
    same shape (duplicated here rather than imported across test modules).
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if packs:
        lines += ["charter_packs:", "  org:", "    packs:"]
        for name, local_path in packs:
            lines.append(f"      - name: {name}")
            lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestOrgTierBrokenManifestRegression:
    """T010 [RED-first]: US1-AC1 (broken YAML) + US1-AC5 (non-mapping),
    #3412. Both scenarios were RED on the pre-WP03 code through the
    pre-existing entry point (``resolve_org_expected_artifacts`` ->
    ``_read_yaml_mapping`` warned and returned ``None`` for either case,
    laundering "present-but-broken" into byte-identical "not found") and
    are GREEN after WP03's fail-loud widening (T011).
    """

    @pytest.mark.regression
    def test_broken_yaml_syntax_raises_malformed_manifest_error(self, tmp_path: Path) -> None:
        """#3412 US1-AC1: a REAL YAML-syntax fault (unterminated flow
        sequence -- not a typo'd key, a genuine parse error) in a PRESENT
        org override must raise ``MalformedManifestError``, not degrade to
        ``None``. Was RED on pre-WP03 ``org_expected_artifacts.py``
        (warned + returned ``None``); GREEN after T011.
        """
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        bad_file = target_dir / "expected-artifacts.yaml"
        bad_file.write_text("schema_version: [unterminated flow seq\n", encoding="utf-8")

        with pytest.raises(MalformedManifestError) as excinfo:
            resolve_org_expected_artifacts([org_root], "software-dev")

        assert excinfo.value.path == bad_file
        assert str(bad_file) in str(excinfo.value)

    @pytest.mark.regression
    def test_non_mapping_yaml_raises_malformed_manifest_error(self, tmp_path: Path) -> None:
        """#3412 US1-AC5: a PRESENT org override that parses to a
        non-mapping (a top-level YAML sequence, where a mapping is
        required) must also raise ``MalformedManifestError``. Was RED on
        pre-WP03 code (warned + returned ``None``); GREEN after T011.
        """
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        bad_file = target_dir / "expected-artifacts.yaml"
        bad_file.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(MalformedManifestError) as excinfo:
            resolve_org_expected_artifacts([org_root], "software-dev")

        assert excinfo.value.path == bad_file
        assert str(bad_file) in str(excinfo.value)


class TestOrgTierUnreadablePresentCharacterization:
    """FR-012's org-tier mirror of the built-in-tier widening (T013):
    present-but-unreadable (``OSError``/``UnicodeDecodeError``) also fails
    loud on the org tier, not only YAML-syntax/non-mapping. Not
    separately RED-pinned as a T010/T012-style regression -- it is the
    same ``_read_yaml_mapping`` except-branch T011 widens, exercised here
    as an after-fix characterization (green-stays-green once T011/T013
    land together in this WP).
    """

    def test_unreadable_present_manifest_raises_malformed_manifest_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        manifest_path = target_dir / "expected-artifacts.yaml"
        manifest_path.write_text("schema_version: '1.0'\n", encoding="utf-8")

        original_read_text = Path.read_text

        def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
            if self == manifest_path:
                raise OSError("simulated unreadable file")
            return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        with pytest.raises(MalformedManifestError) as excinfo:
            resolve_org_expected_artifacts([org_root], "software-dev")

        assert excinfo.value.path == manifest_path


class TestOrgTierDistinctnessAfterFix:
    """T014: absent-vs-malformed stay distinct on the org tier after the
    fix (Invariant I1), and the raised error names both the file and the
    underlying cause without exception-note inspection (NFR-005 / I2).
    """

    def test_genuine_absence_still_returns_none(self, tmp_path: Path) -> None:
        """Contrast control: no org override at all for this mission type
        still degrades gracefully to ``None`` -- only PRESENCE-with-fault
        raises (I1).
        """
        org_root = tmp_path / "org-pack"
        org_root.mkdir()
        assert resolve_org_expected_artifacts([org_root], "software-dev") is None

    def test_malformed_yaml_error_names_file_and_cause(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        bad_file = target_dir / "expected-artifacts.yaml"
        bad_file.write_text("schema_version: [unterminated flow seq\n", encoding="utf-8")

        with pytest.raises(MalformedManifestError) as excinfo:
            resolve_org_expected_artifacts([org_root], "software-dev")

        message = str(excinfo.value)
        assert str(bad_file) in message
        assert str(excinfo.value.cause) in message

    def test_non_mapping_error_names_file_and_shape(self, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        bad_file = target_dir / "expected-artifacts.yaml"
        bad_file.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(MalformedManifestError) as excinfo:
            resolve_org_expected_artifacts([org_root], "software-dev")

        message = str(excinfo.value)
        assert str(bad_file) in message
        # The cause names the offending shape ("list") so the operator does
        # not have to inspect exception notes to know what went wrong.
        assert "list" in message


class TestCorruptOrgOverrideRegisteredBuiltinFamilyHardBlocks:
    """C-006 acceptance: a corrupt org override for a REGISTERED built-in
    family (``software-dev``) makes manifest resolution hard-raise at
    GATHER time, through the canonical loader
    (``charter.activation.manifest_loader.load_manifest``) -- even though
    the guard-table short-circuit (``cores.py:721-723``) would later never
    reach ``blocking_artifact_names`` for a registered family. The raise
    fires before that short-circuit is even relevant: this proves the
    gather-time raise, not the ``composition.py:504`` launder seam (that
    integration proof is WP04's).
    """

    def setup_method(self) -> None:
        clear_cache()

    def teardown_method(self) -> None:
        clear_cache()

    def test_corrupt_org_override_for_software_dev_raises_at_gather(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        target_dir = org_root / "missions" / "software-dev"
        target_dir.mkdir(parents=True)
        (target_dir / "expected-artifacts.yaml").write_text("schema_version: [unterminated flow seq\n", encoding="utf-8")
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        with pytest.raises(MalformedManifestError):
            load_manifest("software-dev", repo_root=project_root)
