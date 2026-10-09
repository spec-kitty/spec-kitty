"""Characterization tests for ``_presence_filenames_for`` (WP02, #3770, T007).

Mission expected-artifacts-loader-unification-01M1C9VQ, WP02 (FR-005):
``runtime.next.runtime_bridge_io._presence_filenames_for`` used to duplicate
the org->built-in precedence + ``model_validate`` load logic locally. It now
delegates the whole manifest load to
:func:`charter.activation.manifest_loader.load_manifest` (WP01's relocated,
cached authority) and keeps ONLY the
:func:`~charter.offering.missions.step_projection.project_artifact_name_set`
-> ``frozenset`` projection step.

This WP is all characterization (green-stays-green) -- nothing here carries
``@pytest.mark.regression``. Two things are pinned:

1. Absent manifest -> ``frozenset()``, never ``None`` -- this is the
   projection's own absence output, distinct from the
   ``blocking_artifact_names`` ``None``-vs-``frozenset()`` tri-state
   :func:`runtime.next.runtime_bridge_io._expected_artifacts_manifest_resolves`
   governs (C-002, untouched by this WP).
2. A malformed (YAML-syntax-broken) BUILT-IN manifest still propagates
   ``MalformedManifestError`` unchanged -- this behavior already shipped
   (``1763bf2ae3``) before this WP; the delegate must not re-swallow it. The
   analogous ORG-tier fail-loud widening is WP03/#3412, a distinct,
   not-yet-landed work package -- not characterized here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Absent manifest -> frozenset(), never None (the projection's own absence
# output; NOT the blocking_artifact_names tri-state).
# ---------------------------------------------------------------------------


class TestPresenceFilenamesAbsentManifest:
    def test_unregistered_family_projects_to_empty_frozenset(self) -> None:
        from runtime.next.runtime_bridge_io import _presence_filenames_for

        result = _presence_filenames_for("totally-unregistered-family")

        assert result == frozenset()
        assert result is not None

    def test_repo_root_given_but_no_manifest_anywhere_still_projects_to_empty_frozenset(self, tmp_path: Path) -> None:
        """``repo_root`` supplied, resolves no org roots (no ``.kittify/config.yaml``
        at all) -- the org-tier consult's "no match" path must fall through
        cleanly to the built-in tier, which also has nothing for this family."""
        from runtime.next.runtime_bridge_io import _presence_filenames_for

        project_root = tmp_path / "project-no-config"
        project_root.mkdir()

        result = _presence_filenames_for("totally-unregistered-family", repo_root=project_root)

        assert result == frozenset()


# ---------------------------------------------------------------------------
# Malformed (YAML-syntax-broken) built-in manifest -> MalformedManifestError
# propagates BEFORE the projection is ever reached (already-shipped
# built-in-tier behavior, 1763bf2ae3; this delegate must not re-swallow it).
# ---------------------------------------------------------------------------

_MALFORMED_MISSION_TYPE = "malformed-presence-manifest"


class TestPresenceFilenamesMalformedManifestPropagates:
    def test_malformed_builtin_manifest_propagates_malformed_manifest_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import charter.activation.manifest_loader as manifest_loader_module
        from charter.offering.missions.repository import MalformedManifestError
        from runtime.next.runtime_bridge_io import _presence_filenames_for

        offending_path = Path("/fake/doctrine") / _MALFORMED_MISSION_TYPE / "expected-artifacts.yaml"

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> None:
                raise MalformedManifestError(offending_path, ValueError("bad indentation"))

        monkeypatch.setattr(manifest_loader_module, "_offering_template_repository", lambda: _FakeRepository())

        with pytest.raises(MalformedManifestError) as exc_info:
            _presence_filenames_for(_MALFORMED_MISSION_TYPE)

        assert exc_info.value.path == offending_path


# ---------------------------------------------------------------------------
# T009 -- routes through the authority: proves the delegation is live, not
# an inert local copy that happens to agree with the authority today.
# ---------------------------------------------------------------------------


class TestPresenceFilenamesRoutesThroughAuthority:
    def test_delegates_to_manifest_loader_load_manifest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import charter.activation.manifest_loader as manifest_loader_module
        from runtime.next.runtime_bridge_io import _presence_filenames_for

        calls: list[tuple[str, Path | None]] = []
        original_load_manifest = manifest_loader_module.load_manifest

        def _tracking_load_manifest(mission_type: str, repo_root: Path | None = None) -> object:
            calls.append((mission_type, repo_root))
            return original_load_manifest(mission_type, repo_root=repo_root)

        monkeypatch.setattr(manifest_loader_module, "load_manifest", _tracking_load_manifest)

        _presence_filenames_for("software-dev")

        assert calls == [("software-dev", None)]


# ---------------------------------------------------------------------------
# #3847: characterize the `blocking_artifact_names` None-vs-frozenset
# tri-state (C-002, #3729) through the REAL entry point
# `gather_artifact_presence`, for every input class the planned dedup of
# `_expected_artifacts_manifest_resolves` (reuse the cached `load_manifest`
# authority instead of its own uncached `_resolve_org_manifest_mapping` +
# bare built-in read) must preserve byte-exact. Characterization
# (green-stays-green before AND after the dedup) -- not a regression pin for
# a bug, per the module docstring's framing.
# ---------------------------------------------------------------------------

_TRISTATE_VALID_FAMILY = "tristate-valid-family"
_TRISTATE_VALID_STEP = "tristate-step"
_TRISTATE_VALID_YAML = f"""\
schema_version: "1.0"
mission_type: "{_TRISTATE_VALID_FAMILY}"
manifest_version: "1"
required_always: []
required_by_step:
  {_TRISTATE_VALID_STEP}:
    - artifact_key: "output.tristate.main"
      artifact_class: "output"
      path_pattern: "tristate-artifact.md"
      blocking: true
optional_always: []
"""

# Mirrors TestGatherArtifactPresenceRaisesManifestSchemaErrorAtBothTiers's
# built-in fixture shape (tests/runtime/next/test_pertype_presence_gate.py):
# `not_a_real_field` trips `ExpectedArtifactManifest`'s `extra="forbid"`.
_TRISTATE_SCHEMA_INVALID_FAMILY = "tristate-schema-invalid-family"
_TRISTATE_SCHEMA_INVALID_YAML = f"""\
schema_version: "1.0"
mission_type: "{_TRISTATE_SCHEMA_INVALID_FAMILY}"
manifest_version: "1"
not_a_real_field: true
"""

_TRISTATE_MALFORMED_ORG_FAMILY = "tristate-malformed-org-family"
_TRISTATE_MALFORMED_ORG_YAML = "schema_version: [unterminated flow seq\n"


def _write_tristate_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Canonical ``charter_packs.org.packs`` shape (CR-04)."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_tristate_org_manifest(org_root: Path, mission_type: str, yaml_text: str) -> None:
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "expected-artifacts.yaml").write_text(yaml_text, encoding="utf-8")


@pytest.fixture
def _tristate_valid_family_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.missions import MissionTemplateRepository

    missions_root = tmp_path / "missions-root-tristate-valid"
    family_dir = missions_root / _TRISTATE_VALID_FAMILY
    family_dir.mkdir(parents=True)
    (family_dir / "expected-artifacts.yaml").write_text(_TRISTATE_VALID_YAML, encoding="utf-8")
    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


@pytest.fixture
def _tristate_schema_invalid_family_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.missions import MissionTemplateRepository

    missions_root = tmp_path / "missions-root-tristate-schema-invalid"
    family_dir = missions_root / _TRISTATE_SCHEMA_INVALID_FAMILY
    family_dir.mkdir(parents=True)
    (family_dir / "expected-artifacts.yaml").write_text(_TRISTATE_SCHEMA_INVALID_YAML, encoding="utf-8")
    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


class TestTristateCharacterizationThroughGatherArtifactPresence:
    """#3847: pin ``ArtifactPresenceSnapshot.blocking_artifact_names``'s
    None-vs-frozenset tri-state, plus the raise behavior, for all four input
    classes -- exercised through ``gather_artifact_presence`` (the real
    entry), not the helper in isolation. Must stay green both before and
    after the dedup change."""

    def setup_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    def teardown_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    def test_absent_at_both_tiers_yields_none(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge_io import gather_artifact_presence

        feature_dir = tmp_path / "feature-absent"
        feature_dir.mkdir()

        snapshot = gather_artifact_presence(
            feature_dir,
            mission_family="totally-unregistered-tristate-family",
            step_id="whatever",
        )

        assert snapshot.blocking_artifact_names is None

    def test_present_and_valid_yields_real_frozenset(self, tmp_path: Path, _tristate_valid_family_repo: None) -> None:
        from runtime.next.runtime_bridge_io import gather_artifact_presence

        feature_dir = tmp_path / "feature-valid"
        feature_dir.mkdir()

        snapshot = gather_artifact_presence(
            feature_dir,
            mission_family=_TRISTATE_VALID_FAMILY,
            step_id=_TRISTATE_VALID_STEP,
        )

        assert snapshot.blocking_artifact_names is not None
        assert isinstance(snapshot.blocking_artifact_names, frozenset)
        assert snapshot.blocking_artifact_names == frozenset({"tristate-artifact.md"})

    def test_present_and_malformed_org_manifest_raises(self, tmp_path: Path) -> None:
        from charter.offering.missions.repository import MalformedManifestError
        from runtime.next.runtime_bridge_io import gather_artifact_presence

        project_root = tmp_path / "project-malformed"
        project_root.mkdir()
        org_root = tmp_path / "org-pack-malformed"
        _write_tristate_org_manifest(org_root, _TRISTATE_MALFORMED_ORG_FAMILY, _TRISTATE_MALFORMED_ORG_YAML)
        _write_tristate_org_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = tmp_path / "feature-malformed"
        feature_dir.mkdir()

        with pytest.raises(MalformedManifestError):
            gather_artifact_presence(
                feature_dir,
                mission_family=_TRISTATE_MALFORMED_ORG_FAMILY,
                step_id="whatever",
                repo_root=project_root,
            )

    def test_present_and_schema_invalid_raises_manifest_schema_error(self, tmp_path: Path, _tristate_schema_invalid_family_repo: None) -> None:
        from charter.activation.manifest_loader import ManifestSchemaError
        from runtime.next.runtime_bridge_io import gather_artifact_presence

        feature_dir = tmp_path / "feature-schema-invalid"
        feature_dir.mkdir()

        with pytest.raises(ManifestSchemaError) as exc_info:
            gather_artifact_presence(
                feature_dir,
                mission_family=_TRISTATE_SCHEMA_INVALID_FAMILY,
                step_id="whatever",
            )

        assert exc_info.value.mission_type == _TRISTATE_SCHEMA_INVALID_FAMILY


# ---------------------------------------------------------------------------
# #3847 dedup: the org-tier manifest read must happen exactly ONCE per
# `gather_artifact_presence` call on the org happy path -- today it happens
# twice (`_presence_filenames_for` via the cached `load_manifest` authority,
# then again via `_expected_artifacts_manifest_resolves`'s own uncached
# `_resolve_org_manifest_mapping`). RED before the dedup (2 reads), GREEN
# after (1 read) -- pinned to #3847.
# ---------------------------------------------------------------------------

_DEDUP_ORG_FAMILY = "dedup-org-happy-path-family"
_DEDUP_ORG_STEP = "dedup-step"
_DEDUP_ORG_YAML = f"""\
schema_version: "1.0"
mission_type: "{_DEDUP_ORG_FAMILY}"
manifest_version: "org-1"
required_always: []
required_by_step:
  {_DEDUP_ORG_STEP}:
    - artifact_key: "output.dedup.main"
      artifact_class: "output"
      path_pattern: "dedup-artifact.md"
      blocking: true
optional_always: []
"""


class TestExpectedArtifactsOrgReadDedup:
    def setup_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    def teardown_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    @pytest.mark.regression
    def test_org_manifest_read_exactly_once_per_gather_call(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import charter.activation.org_expected_artifacts as org_expected_artifacts_module
        from runtime.next.runtime_bridge_io import gather_artifact_presence

        project_root = tmp_path / "project-dedup"
        project_root.mkdir()
        org_root = tmp_path / "org-pack-dedup"
        _write_tristate_org_manifest(org_root, _DEDUP_ORG_FAMILY, _DEDUP_ORG_YAML)
        _write_tristate_org_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = tmp_path / "feature-dedup"
        feature_dir.mkdir()

        calls: list[str] = []
        original = org_expected_artifacts_module.resolve_org_expected_artifacts

        def _counting(org_roots: list[Path], mission_type: str) -> object:
            calls.append(mission_type)
            return original(org_roots, mission_type)

        monkeypatch.setattr(org_expected_artifacts_module, "resolve_org_expected_artifacts", _counting)

        snapshot = gather_artifact_presence(
            feature_dir,
            mission_family=_DEDUP_ORG_FAMILY,
            step_id=_DEDUP_ORG_STEP,
            repo_root=project_root,
        )

        assert snapshot.blocking_artifact_names == frozenset({"dedup-artifact.md"})
        assert len(calls) == 1, f"expected the org-tier manifest read exactly once per gather_artifact_presence call (#3847 dedup), got {len(calls)}"
