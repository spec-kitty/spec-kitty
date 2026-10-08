"""Live per-type presence gate + stray-spec.md delete (FR-011/012, #3597).

Mission rc3-charter-gate-predicate-inversion-01M0GGT1, WP05 (plan.md §WP04b).
Depends on WP04's artifact-filename seam
(``specify_cli.runtime.resolver.required_artifacts_for`` /
``resolve_configured_artifact_name``, #3599): ``gather_artifact_presence``
(``runtime.next.runtime_bridge_io``) now consults the resolved per-type
``path_pattern`` set for the (mission_family, step_id) pair instead of the
previously-closed ``_PRESENCE_FILE_TAGS`` 10-tuple.

AC-10 (fail-closed both directions): a custom mission family gates on its
OWN filename -- present -> passes, absent -> blocks -- as long as it ships
an ``expected-artifacts.yaml`` with a blocking ``path_pattern`` entry at the
step being gathered for. Both directions are asserted here (a present-only
test would permit a fail-open gate, the exact defect this mission kills).

The ``evaluate_guards_strict`` ``UnregisteredMissionFamilyError`` strict-raise
is a DISTINCT, retained concern (guard-table *dispatch* for a genuinely
unregistered family) -- not removed by this change; see the ADR
(``docs/adr/3.x/2026-08-21-1-charter-gate-predicate-inversion.md``,
"Custom-family gate mechanism").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.missions import MissionTemplateRepository
from runtime.next.runtime_bridge_cores import (
    UnregisteredMissionFamilyError,
    evaluate_guards_strict,
)
from runtime.next.runtime_bridge_io import gather_artifact_presence

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CUSTOM_MISSION_TYPE = "custom-family"
_CUSTOM_STEP_ID = "custom-step"
_CUSTOM_FILENAME = "custom-artifact.md"

_CUSTOM_EXPECTED_ARTIFACTS_YAML = f"""\
schema_version: "1.0"
mission_type: "{_CUSTOM_MISSION_TYPE}"
manifest_version: "1"
required_always: []
required_by_step:
  {_CUSTOM_STEP_ID}:
    - artifact_key: "output.custom.main"
      artifact_class: "output"
      path_pattern: "{_CUSTOM_FILENAME}"
      blocking: true
optional_always: []
"""


@pytest.fixture
def custom_mission_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ``MissionTemplateRepository.default()`` at a temp missions root
    shipping a custom mission type's own ``expected-artifacts.yaml`` -- the
    ADR's data-driven custom-family gate mechanism (no ``_GUARD_TABLES``
    code registration)."""
    missions_root = tmp_path / "missions-root"
    custom_dir = missions_root / _CUSTOM_MISSION_TYPE
    custom_dir.mkdir(parents=True)
    (custom_dir / "expected-artifacts.yaml").write_text(_CUSTOM_EXPECTED_ARTIFACTS_YAML, encoding="utf-8")

    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


# AC-9 (WP01, #3704 Part 1): two-family distinguishability fixture -- a
# family that DOES ship an ``expected-artifacts.yaml`` but whose manifest
# resolves an empty blocking set for the step under test
# (``blocking_artifact_names == frozenset()``), contrasted against a
# genuinely typeless family with no manifest at any tier
# (``blocking_artifact_names is None``). Both produce an empty
# ``required_artifacts_for`` result, but must NOT be treated identically --
# collapsing this distinction via bare falsiness is exactly the
# SPEC-FRESH-001 defect this mission restores.
_QA_MISSION_TYPE = "qa"
_QA_STEP_ID = "check"

_QA_EXPECTED_ARTIFACTS_YAML = f"""\
schema_version: "1.0"
mission_type: "{_QA_MISSION_TYPE}"
manifest_version: "1"
required_always: []
required_by_step: {{}}
optional_always: []
"""


@pytest.fixture
def qa_family_manifest_with_no_blocking_artifacts_at_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A family with a manifest present (built-in-tier-shaped, per this
    story's own Independent Test framing) whose ``required_by_step`` has no
    entry for ``_QA_STEP_ID`` -- so ``blocking_artifact_names`` resolves to
    a real, empty ``frozenset``, not ``None``."""
    missions_root = tmp_path / "missions-root-qa"
    qa_dir = missions_root / _QA_MISSION_TYPE
    qa_dir.mkdir(parents=True)
    (qa_dir / "expected-artifacts.yaml").write_text(_QA_EXPECTED_ARTIFACTS_YAML, encoding="utf-8")

    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


class TestCustomFamilyPresenceGateFailsClosedBothDirections:
    """AC-10: ``gather_artifact_presence`` -- the named entry point -- gates
    a custom family on its own filename, both directions."""

    def test_present_filename_is_detected(self, tmp_path: Path, custom_mission_repo: None) -> None:
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()
        (feature_dir / _CUSTOM_FILENAME).write_text("# custom\n", encoding="utf-8")

        snapshot = gather_artifact_presence(feature_dir, mission_family=_CUSTOM_MISSION_TYPE, step_id=_CUSTOM_STEP_ID)

        assert _CUSTOM_FILENAME in snapshot.present_artifacts

    def test_absent_filename_is_not_detected(self, tmp_path: Path, custom_mission_repo: None) -> None:
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()
        # _CUSTOM_FILENAME deliberately NOT created.

        snapshot = gather_artifact_presence(feature_dir, mission_family=_CUSTOM_MISSION_TYPE, step_id=_CUSTOM_STEP_ID)

        assert _CUSTOM_FILENAME not in snapshot.present_artifacts

    def test_unrelated_builtin_filename_never_leaks_into_custom_family(self, tmp_path: Path, custom_mission_repo: None) -> None:
        """A custom family's presence set is genuinely per-type -- a
        built-in filename that happens to also exist on disk (e.g.
        ``spec.md``) is not spuriously reported present for a custom
        family/step that never declared it."""
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

        snapshot = gather_artifact_presence(feature_dir, mission_family=_CUSTOM_MISSION_TYPE, step_id=_CUSTOM_STEP_ID)

        assert snapshot.present_artifacts == frozenset()

    def test_manifest_present_empty_blocking_set_evaluates_genuinely_not_raise(
        self, tmp_path: Path, qa_family_manifest_with_no_blocking_artifacts_at_step: None
    ) -> None:
        """AC-9 family (a): a manifest IS present but resolves an empty
        blocking set for this step (``blocking_artifact_names ==
        frozenset()``) -- genuinely evaluated via ``evaluate_guards_strict``,
        does NOT raise, returns ``[]``."""
        feature_dir = tmp_path / "feature-qa"
        feature_dir.mkdir()

        snapshot = gather_artifact_presence(feature_dir, mission_family=_QA_MISSION_TYPE, step_id=_QA_STEP_ID)

        assert snapshot.blocking_artifact_names == frozenset()
        assert evaluate_guards_strict(snapshot) == []

    def test_no_manifest_at_any_tier_still_raises_despite_same_empty_required_artifacts(self, tmp_path: Path) -> None:
        """AC-9 family (b): a genuinely typeless family with NO manifest at
        any tier (``blocking_artifact_names is None``) still raises --
        distinguishing it from family (a) above even though both would
        report an empty ``required_artifacts_for`` result for their step.
        This IS the whole point of the None-vs-frozenset() distinction."""
        feature_dir = tmp_path / "feature-typeless"
        feature_dir.mkdir()

        snapshot = gather_artifact_presence(feature_dir, mission_family="totally-unregistered-family", step_id="whatever")

        assert snapshot.blocking_artifact_names is None
        with pytest.raises(UnregisteredMissionFamilyError):
            evaluate_guards_strict(snapshot)


def test_unregistered_family_guard_dispatch_strict_raise_is_retained(
    tmp_path: Path,
) -> None:
    """The ``evaluate_guards_strict`` ``UnregisteredMissionFamilyError``
    strict-raise stays for guard-table *dispatch* of a genuinely
    unregistered family -- a distinct concern from presence gathering
    (per the ADR); this WP must not remove it. No custom manifest is
    installed here, so ``gather_artifact_presence`` itself degrades
    gracefully (empty presence set), and the raise happens one layer up,
    at guard-table lookup."""
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()

    snapshot = gather_artifact_presence(feature_dir, mission_family="totally-unregistered-family", step_id="whatever")

    with pytest.raises(UnregisteredMissionFamilyError):
        evaluate_guards_strict(snapshot)


# ---------------------------------------------------------------------------
# WP02 T009 (FR-004/FR-005/FR-007/FR-008, AC-4/AC-5/AC-6): org-tier awareness
# + whole-file-replacement precedence, threaded through
# ``gather_artifact_presence``'s new ``repo_root`` parameter.
# ---------------------------------------------------------------------------

_ORG_PRESENCE_FAMILY = "org-presence-family"
_ORG_STEP_ONE = "step-one"
_ORG_STEP_TWO = "step-two"

_ORG_PRESENCE_BUILTIN_YAML = f"""\
schema_version: "1.0"
mission_type: "{_ORG_PRESENCE_FAMILY}"
manifest_version: "1"
required_always: []
required_by_step:
  {_ORG_STEP_ONE}:
    - artifact_key: "output.builtin.one"
      artifact_class: "output"
      path_pattern: "builtin-one.md"
      blocking: true
  {_ORG_STEP_TWO}:
    - artifact_key: "output.builtin.two"
      artifact_class: "output"
      path_pattern: "builtin-two.md"
      blocking: true
optional_always: []
"""


@pytest.fixture
def org_presence_family_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Built-in-tier control manifest for ``_ORG_PRESENCE_FAMILY`` -- present
    so the org-tier override test can prove the org file wins WHOLE-FILE
    (never field-merged) rather than merely "the only manifest that exists"."""
    missions_root = tmp_path / "missions-root-org-presence"
    family_dir = missions_root / _ORG_PRESENCE_FAMILY
    family_dir.mkdir(parents=True)
    (family_dir / "expected-artifacts.yaml").write_text(_ORG_PRESENCE_BUILTIN_YAML, encoding="utf-8")

    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


def _write_org_presence_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if packs:
        lines += ["charter_packs:", "  org:", "    packs:"]
        for name, local_path in packs:
            lines.append(f"      - name: {name}")
            lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_presence_manifest(org_root: Path, mission_type: str, yaml_text: str) -> None:
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "expected-artifacts.yaml").write_text(yaml_text, encoding="utf-8")


_ORG_PRESENCE_ORG_YAML = f"""\
schema_version: "1.0"
mission_type: "{_ORG_PRESENCE_FAMILY}"
manifest_version: "org-1"
required_always: []
required_by_step:
  {_ORG_STEP_ONE}:
    - artifact_key: "output.org.one-required"
      artifact_class: "output"
      path_pattern: "org-one-required.md"
      blocking: true
    - artifact_key: "output.org.one-optional"
      artifact_class: "output"
      path_pattern: "org-one-optional.md"
      blocking: false
  {_ORG_STEP_TWO}:
    - artifact_key: "output.org.two-required"
      artifact_class: "output"
      path_pattern: "org-two-required.md"
      blocking: true
optional_always: []
"""


class TestGatherArtifactPresenceOrgTier:
    """AC-4/AC-5/AC-6: org file wins whole-file; only ``blocking: true``
    absences surface in ``blocking_artifact_names``."""

    def test_org_manifest_wins_whole_file_over_built_in_control(self, tmp_path: Path, org_presence_family_repo: None) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_presence_manifest(org_root, _ORG_PRESENCE_FAMILY, _ORG_PRESENCE_ORG_YAML)
        _write_org_presence_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        snapshot = gather_artifact_presence(
            feature_dir,
            mission_family=_ORG_PRESENCE_FAMILY,
            step_id=_ORG_STEP_ONE,
            repo_root=project_root,
        )

        # AC-6: whole-file replacement -- the built-in control's filename
        # must NOT leak into the org-resolved blocking set.
        assert snapshot.blocking_artifact_names == frozenset({"org-one-required.md"})

    def test_blocking_false_absence_never_surfaces_at_any_declared_step(self, tmp_path: Path, org_presence_family_repo: None) -> None:
        """AC-5: a ``blocking: false`` entry's absence never produces a
        guard failure, at every step it's declared for."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_presence_manifest(org_root, _ORG_PRESENCE_FAMILY, _ORG_PRESENCE_ORG_YAML)
        _write_org_presence_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        snapshot_step_one = gather_artifact_presence(
            feature_dir,
            mission_family=_ORG_PRESENCE_FAMILY,
            step_id=_ORG_STEP_ONE,
            repo_root=project_root,
        )
        snapshot_step_two = gather_artifact_presence(
            feature_dir,
            mission_family=_ORG_PRESENCE_FAMILY,
            step_id=_ORG_STEP_TWO,
            repo_root=project_root,
        )

        assert "org-one-optional.md" not in snapshot_step_one.blocking_artifact_names
        assert snapshot_step_two.blocking_artifact_names == frozenset({"org-two-required.md"})

    def test_repo_root_with_no_org_pack_falls_through_to_built_in_control_unchanged(self, tmp_path: Path, org_presence_family_repo: None) -> None:
        """TASKS-VERIFY-003 fix: ``repo_root`` supplied but no org pack
        resolves for it -- the org-tier consult's "no match" path must fall
        through cleanly to the built-in-tier manifest, distinct from the
        ``repo_root=None``-never-invokes-org-tier-at-all case."""
        project_root = tmp_path / "project-no-org-pack"
        project_root.mkdir()
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        with_repo_root = gather_artifact_presence(
            feature_dir,
            mission_family=_ORG_PRESENCE_FAMILY,
            step_id=_ORG_STEP_ONE,
            repo_root=project_root,
        )
        without_repo_root = gather_artifact_presence(
            feature_dir,
            mission_family=_ORG_PRESENCE_FAMILY,
            step_id=_ORG_STEP_ONE,
        )

        assert with_repo_root.blocking_artifact_names == without_repo_root.blocking_artifact_names == frozenset({"builtin-one.md"})


# ---------------------------------------------------------------------------
# #3704 pr-merged-001 (red-first): FR-010's ManifestSchemaError guard must
# hold on the ACTUAL production call path. gather_artifact_presence calls
# the unguarded _presence_filenames_for FIRST (runtime_bridge_io.py:1051),
# before required_artifacts_for is ever reached (:1114-1122). A
# schema-invalid-but-syntactically-valid manifest previously escaped
# _presence_filenames_for's two model_validate() calls (org-tier :904,
# built-in :909) as a bare pydantic_core.ValidationError, through both
# unconditional production guard entry points
# (runtime_bridge.py::_check_cli_guards,
# runtime_bridge_composition.py::_check_composed_action_guard) --
# undetected by TestManifestSchemaErrorPerTier
# (tests/specify_cli/runtime/test_configured_artifact_name.py:524-593),
# which exercises required_artifacts_for in isolation and never drives
# gather_artifact_presence. This class drives gather_artifact_presence
# itself, at each tier, so the same gap cannot recur silently.
# ---------------------------------------------------------------------------

_BROKEN_SCHEMA_MISSION_TYPE = "broken-presence-schema"

_BROKEN_SCHEMA_BUILTIN_YAML = f"""\
schema_version: "1.0"
mission_type: "{_BROKEN_SCHEMA_MISSION_TYPE}"
manifest_version: "1"
not_a_real_field: true
"""

# Missing the required `mission_type` field -> pydantic ValidationError,
# mirroring TestManifestSchemaErrorPerTier's own org-tier fixture shape.
_BROKEN_SCHEMA_ORG_YAML = """\
schema_version: "1.0"
manifest_version: "broken"
"""


@pytest.fixture
def broken_schema_builtin_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A built-in-tier manifest that parses as YAML but fails
    ``ExpectedArtifactManifest`` schema validation (``extra="forbid"``
    rejects ``not_a_real_field``)."""
    missions_root = tmp_path / "missions-root-broken-schema"
    broken_dir = missions_root / _BROKEN_SCHEMA_MISSION_TYPE
    broken_dir.mkdir(parents=True)
    (broken_dir / "expected-artifacts.yaml").write_text(_BROKEN_SCHEMA_BUILTIN_YAML, encoding="utf-8")
    monkeypatch.setattr(
        MissionTemplateRepository,
        "default",
        classmethod(lambda cls: MissionTemplateRepository(missions_root)),
    )


class TestGatherArtifactPresenceRaisesManifestSchemaErrorAtBothTiers:
    """pr-merged-001 (#3704, severity 4, confirmed): a schema-invalid
    manifest must surface as the domain ``ManifestSchemaError`` -- not a
    bare ``pydantic_core.ValidationError`` -- when reached through
    ``gather_artifact_presence``, at both the built-in and org tiers.
    """

    def test_built_in_tier_schema_invalid_manifest_raises_via_gather_artifact_presence(self, tmp_path: Path, broken_schema_builtin_repo: None) -> None:
        from specify_cli.dossier.manifest import ManifestSchemaError

        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        with pytest.raises(ManifestSchemaError) as exc_info:
            gather_artifact_presence(
                feature_dir,
                mission_family=_BROKEN_SCHEMA_MISSION_TYPE,
                step_id="specify",
            )

        exc = exc_info.value
        assert exc.mission_type == _BROKEN_SCHEMA_MISSION_TYPE
        # Built-in branch: `config.origin` is a real, reachable attribute.
        assert _BROKEN_SCHEMA_MISSION_TYPE in exc.origin

    def test_org_tier_schema_invalid_manifest_raises_via_gather_artifact_presence(self, tmp_path: Path) -> None:
        from specify_cli.dossier.manifest import ManifestSchemaError

        project_root = tmp_path / "project-broken-org-schema"
        project_root.mkdir()
        org_root = tmp_path / "org-pack-broken-schema"
        _write_org_presence_manifest(org_root, "software-dev", _BROKEN_SCHEMA_ORG_YAML)
        _write_org_presence_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        with pytest.raises(ManifestSchemaError) as exc_info:
            gather_artifact_presence(
                feature_dir,
                mission_family="software-dev",
                step_id="specify",
                repo_root=project_root,
            )

        exc = exc_info.value
        assert exc.mission_type == "software-dev"
        # Org-tier branch: no `ConfigResult` of type `config` is in scope,
        # so `.origin` cannot be read off one -- it must be a synthesized,
        # descriptive string naming the org tier and mission type instead.
        assert "org-tier" in exc.origin
        assert "software-dev" in exc.origin
