"""Characterization tests for the artifact-filename seam (FR-009/FR-010, #3599).

Mission rc3-charter-gate-predicate-inversion-01M0GGT1, WP04a: a GREEN
refactor. ``resolve_configured_artifact_name`` / ``required_artifacts_for``
(``specify_cli.runtime.resolver``) and ``project_artifact_name_set``
(``doctrine.missions.step_projection``) build ``artifact_kind -> filename``
from the single per-type authority -- ``expected-artifacts.yaml``'s
``path_pattern`` -- twinning the existing template seam
(``resolve_configured_template``). NFR-003 requires byte-compatible output
for the four built-in mission types; nothing here changes runtime behavior.

AC-9 (load-bearing): patching the per-type ``path_pattern`` source must
change the output of EVERY converted call site -- proving each hardcoded
literal was actually replaced by the seam, not shadowed by an unused one.
AC-12 (pin-and-defer): the two THIRD-KIND boundary raises in
``_substantive.py`` and ``mission_feature_resolution.py`` stay exactly as
they are today (those files are read-only in WP04).
"""

from __future__ import annotations

import copy
import importlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from charter.offering.missions import MissionTemplateRepository
from charter.offering.missions import (
    ArtifactClassEnum,
    ConfigResult,
    ExpectedArtifactManifest,
    ExpectedArtifactSpec,
)
from charter.offering.missions.step_projection import project_artifact_name_set
from specify_cli.runtime.resolver import (
    ArtifactNameConfigurationError,
    required_artifacts_for,
    resolve_configured_artifact_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BUILT_IN_TYPES = ("software-dev", "documentation", "research", "plan")


@pytest.mark.parametrize(
    ("module_name", "attribute"),
    [
        ("specify_cli.acceptance", "SPEC_FILE"),
        ("specify_cli.analysis_report", "_HASH_INPUTS"),
    ],
)
def test_malformed_artifact_manifest_fails_on_first_use_not_import(module_name: str, attribute: str) -> None:
    """#3622: an import survives; the first lazy constant read fails loudly."""
    script = f"""
import importlib
import specify_cli.runtime.resolver as resolver

def fail(_key: str) -> str:
    raise RuntimeError('poisoned expected-artifacts manifest')

resolver.resolve_configured_artifact_name = fail
module = importlib.import_module({module_name!r})
print('IMPORT_OK')
try:
    getattr(module, {attribute!r})
except RuntimeError as exc:
    print(f'FIRST_USE_ERROR={{exc}}')
else:
    raise AssertionError('lazy constant unexpectedly resolved')
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "IMPORT_OK",
        "FIRST_USE_ERROR=poisoned expected-artifacts manifest",
    ]


# The 10 built-in filename "tags" referenced by AC-9 / FR-011 (the
# _PRESENCE_FILE_TAGS 10-tuple, WP05 scope for the *conversion*; WP04 audits
# that the seam can resolve every one of them for at least one built-in
# (mission_type, artifact_key) pair).
_TEN_TAGS_TO_SOURCE_PAIR: dict[str, tuple[str, str]] = {
    "spec.md": ("software-dev", "input.spec.main"),
    "plan.md": ("software-dev", "output.plan.main"),
    "tasks.md": ("software-dev", "output.tasks.list"),
    "source-register.csv": ("research", "evidence.source-register"),
    "findings.md": ("research", "output.findings.main"),
    "report.md": ("research", "output.report.publication"),
    "gap-analysis.md": ("documentation", "evidence.gap-analysis"),
    "audit-report.md": ("documentation", "evidence.audit-report"),
    "release.md": ("documentation", "output.release.main"),
    "research.md": ("software-dev", "evidence.research"),
}


# ---------------------------------------------------------------------------
# AC-9 -- built-in name sets byte-compatible (NFR-003)
# ---------------------------------------------------------------------------


class TestResolveConfiguredArtifactNameBuiltins:
    """All four built-ins resolve their canonical filenames through the seam."""

    @pytest.mark.parametrize(
        ("mission_type", "artifact_key", "expected_filename"),
        [
            ("software-dev", "input.spec.main", "spec.md"),
            ("software-dev", "output.plan.main", "plan.md"),
            ("software-dev", "output.tasks.list", "tasks.md"),
            ("software-dev", "output.tasks.per_wp", "tasks/WP*.md"),
            ("software-dev", "evidence.research", "research.md"),
            ("software-dev", "evidence.gap-analysis", "gap-analysis.md"),
            ("documentation", "input.spec.documentation", "spec.md"),
            ("documentation", "evidence.gap-analysis", "gap-analysis.md"),
            ("documentation", "workflow.plan.documentation", "plan.md"),
            ("documentation", "evidence.audit-report", "audit-report.md"),
            ("documentation", "output.release.main", "release.md"),
            ("research", "input.spec.research", "spec.md"),
            ("research", "workflow.plan.methodology", "plan.md"),
            ("research", "evidence.source-register", "source-register.csv"),
            ("research", "output.findings.main", "findings.md"),
            ("research", "output.report.publication", "report.md"),
            ("plan", "output.goals.main", "goals.md"),
            ("plan", "evidence.research", "research.md"),
            ("plan", "output.plan.main", "plan.md"),
        ],
    )
    def test_resolves_todays_built_in_filename(self, mission_type: str, artifact_key: str, expected_filename: str) -> None:
        assert resolve_configured_artifact_name(artifact_key, mission_type) == expected_filename

    @pytest.mark.parametrize("mission_type", _BUILT_IN_TYPES)
    def test_every_built_in_type_has_a_resolvable_manifest(self, mission_type: str) -> None:
        """Every built-in resolves at least one artifact key (manifest is non-empty)."""
        manifest = MissionTemplateRepository.default().get_expected_artifacts(mission_type)
        assert manifest is not None, f"{mission_type} has no expected-artifacts.yaml"

    @pytest.mark.parametrize(("tag", "source"), sorted(_TEN_TAGS_TO_SOURCE_PAIR.items()))
    def test_all_ten_built_in_tags_resolve(self, tag: str, source: tuple[str, str]) -> None:
        """FR-011 audit: every one of the 10 built-in filename tags is reachable via the seam."""
        mission_type, artifact_key = source
        assert resolve_configured_artifact_name(artifact_key, mission_type) == tag

    def test_ten_tags_constant_has_exactly_ten_members(self) -> None:
        assert set(_TEN_TAGS_TO_SOURCE_PAIR) == {
            "spec.md",
            "plan.md",
            "tasks.md",
            "source-register.csv",
            "findings.md",
            "report.md",
            "gap-analysis.md",
            "audit-report.md",
            "release.md",
            "research.md",
        }


class TestResolveConfiguredArtifactNameErrors:
    """Failure modes mirror ``resolve_configured_template``'s (twin seam)."""

    def test_unknown_artifact_key_raises(self) -> None:
        with pytest.raises(ArtifactNameConfigurationError) as exc_info:
            resolve_configured_artifact_name("no.such.key", "software-dev")
        error = exc_info.value
        assert error.mission_type == "software-dev"
        assert error.artifact_key == "no.such.key"
        assert "missing the requested mapping key" in str(error)

    def test_unregistered_mission_type_raises(self) -> None:
        with pytest.raises(ArtifactNameConfigurationError) as exc_info:
            resolve_configured_artifact_name("input.spec.main", "totally-unregistered-type")
        assert "no expected-artifacts manifest" in str(exc_info.value)

    @pytest.mark.parametrize(
        "mission_type",
        ["", "../..", "/absolute/type", "nested/type"],
    )
    def test_unsafe_mission_type_raises_before_lookup(self, mission_type: str) -> None:
        with pytest.raises(ArtifactNameConfigurationError) as exc_info:
            resolve_configured_artifact_name("input.spec.main", mission_type)
        assert "unsafe mission type" in str(exc_info.value)


# ---------------------------------------------------------------------------
# required_artifacts_for -- direct coverage (Sonar: every new helper needs tests)
# ---------------------------------------------------------------------------


class TestRequiredArtifactsFor:
    def test_returns_blocking_filenames_for_a_step(self) -> None:
        assert required_artifacts_for("specify", "software-dev") == ["spec.md"]
        assert required_artifacts_for("plan", "software-dev") == ["plan.md"]
        assert required_artifacts_for("tasks_outline", "software-dev") == ["tasks.md"]

    def test_step_with_no_requirements_returns_empty(self) -> None:
        assert required_artifacts_for("discovery", "software-dev") == []
        assert required_artifacts_for("done", "software-dev") == []

    def test_unregistered_mission_type_returns_empty(self) -> None:
        assert required_artifacts_for("specify", "totally-unregistered-type") == []

    def test_unknown_step_returns_empty(self) -> None:
        assert required_artifacts_for("no-such-step", "software-dev") == []


# ---------------------------------------------------------------------------
# project_artifact_name_set -- direct doctrine-layer coverage
# ---------------------------------------------------------------------------


class TestProjectArtifactNameSet:
    def test_flattens_required_always_by_step_and_optional(self) -> None:
        manifest = ExpectedArtifactManifest(
            mission_type="fixture",
            required_always=[
                ExpectedArtifactSpec(
                    artifact_key="input.spec.main",
                    artifact_class=ArtifactClassEnum.INPUT,
                    path_pattern="spec.md",
                    blocking=True,
                )
            ],
            required_by_step={
                "plan": [
                    ExpectedArtifactSpec(
                        artifact_key="output.plan.main",
                        artifact_class=ArtifactClassEnum.OUTPUT,
                        path_pattern="plan.md",
                        blocking=True,
                    )
                ]
            },
            optional_always=[
                ExpectedArtifactSpec(
                    artifact_key="evidence.research",
                    artifact_class=ArtifactClassEnum.EVIDENCE,
                    path_pattern="research.md",
                    blocking=False,
                )
            ],
        )

        name_set = project_artifact_name_set(manifest)

        assert name_set == {
            "input.spec.main": "spec.md",
            "output.plan.main": "plan.md",
            "evidence.research": "research.md",
        }

    def test_empty_manifest_projects_to_none(self) -> None:
        manifest = ExpectedArtifactManifest(mission_type="empty-fixture")
        assert project_artifact_name_set(manifest) is None

    def test_duplicate_artifact_key_last_occurrence_wins(self) -> None:
        """Mirrors software-dev's real ``output.tasks.per_wp`` (2 steps, same path)."""
        spec_a = ExpectedArtifactSpec(
            artifact_key="output.tasks.per_wp",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="tasks/WP*.md",
            blocking=True,
        )
        spec_b = ExpectedArtifactSpec(
            artifact_key="output.tasks.per_wp",
            artifact_class=ArtifactClassEnum.OUTPUT,
            path_pattern="tasks/replaced-*.md",
            blocking=True,
        )
        manifest = ExpectedArtifactManifest(
            mission_type="fixture",
            required_by_step={"tasks_packages": [spec_a], "tasks_finalize": [spec_b]},
        )

        name_set = project_artifact_name_set(manifest)

        assert name_set == {"output.tasks.per_wp": "tasks/replaced-*.md"}


# ---------------------------------------------------------------------------
# AC-9 load-bearing: patching path_pattern changes EVERY converted call site
# ---------------------------------------------------------------------------


_SENTINEL_SPEC_FILENAME = "AC9-LOAD-BEARING-spec.md"

#: Captured BEFORE any test monkeypatches the class attribute -- the patched
#: replacement below calls this saved reference (never
#: ``MissionTemplateRepository.get_expected_artifacts`` again), otherwise it
#: would recurse into itself once installed as the class attribute.
_ORIGINAL_GET_EXPECTED_ARTIFACTS: Callable[[MissionTemplateRepository, str], ConfigResult | None] = MissionTemplateRepository.get_expected_artifacts


def _patched_get_expected_artifacts(self: MissionTemplateRepository, mission: str) -> ConfigResult | None:
    """Return software-dev's real manifest with ``input.spec.main`` renamed.

    Patches the actual ``path_pattern`` SOURCE (``get_expected_artifacts``,
    ``doctrine/missions/repository.py:362``) rather than any downstream
    seam, so this proves the whole chain -- repository -> manifest ->
    projection -> resolver -> each of the three converted call sites --
    is live, not that one link happens to echo a hardcoded value.
    """
    original = _ORIGINAL_GET_EXPECTED_ARTIFACTS(self, mission)
    if original is None or mission != "software-dev":
        return original
    # ``ConfigResult.parsed`` is typed ``dict[str, Any] | list[Any]``; every
    # real expected-artifacts.yaml parses to a top-level mapping (asserted by
    # the software-dev guard above), so this narrowing cast is safe here.
    parsed = cast("dict[str, object]", copy.deepcopy(original.parsed))
    required_by_step = cast("dict[str, list[dict[str, object]]]", parsed["required_by_step"])
    required_by_step["specify"][0]["path_pattern"] = _SENTINEL_SPEC_FILENAME
    return ConfigResult(content=original.content, origin=original.origin, parsed=parsed)


class TestLoadBearingPathPatternPropagation:
    """AC-9: patching the path_pattern source changes every converted call site.

    WP02 (#3770): ``resolve_configured_artifact_name`` now reaches its
    manifest through ``charter.activation.manifest_loader.load_manifest``'s
    process-global, cached authority (rather than the previously-uncached
    resolver-local mirror) -- so a real ``software-dev`` load by an earlier
    test class in this module (``TestResolveConfiguredArtifactNameBuiltins``)
    would otherwise populate the ``("software-dev", ())`` cache entry BEFORE
    this class's ``get_expected_artifacts`` monkeypatch ever runs, making
    every test below silently observe the stale pre-patch content instead of
    the patch. Clear the shared cache before AND after each test here,
    mirroring ``tests/dossier/test_manifest.py``'s own
    ``setup_method``/``teardown_method`` convention for the same cache.
    """

    def setup_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    def teardown_method(self) -> None:
        from charter.activation.manifest_loader import clear_cache

        clear_cache()

    def test_resolver_reflects_the_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(MissionTemplateRepository, "get_expected_artifacts", _patched_get_expected_artifacts)

        assert resolve_configured_artifact_name("input.spec.main") == _SENTINEL_SPEC_FILENAME

    def test_analysis_report_hash_inputs_reflects_the_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.analysis_report as analysis_report_module
        from charter.activation.manifest_loader import clear_cache

        # WP02 (#3770): this "before" read populates the shared authority
        # cache with the REAL manifest under key ("software-dev", ()) --
        # `clear_cache()` below (between the monkeypatch and the "after"
        # read) forces a fresh, patched load rather than silently replaying
        # this cached value (see the class docstring).
        original_hash_inputs = analysis_report_module._HASH_INPUTS
        monkeypatch.setattr(MissionTemplateRepository, "get_expected_artifacts", _patched_get_expected_artifacts)
        clear_cache()
        try:
            importlib.reload(analysis_report_module)
            assert analysis_report_module._HASH_INPUTS[0] == _SENTINEL_SPEC_FILENAME
            assert analysis_report_module._HASH_INPUTS[1:] == original_hash_inputs[1:]
        finally:
            monkeypatch.undo()
            clear_cache()
            importlib.reload(analysis_report_module)
            assert original_hash_inputs == analysis_report_module._HASH_INPUTS

    def test_acceptance_spec_file_reflects_the_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.acceptance as acceptance_module
        from charter.activation.manifest_loader import clear_cache

        # Acceptance resolves these compatibility attributes lazily through
        # module ``__getattr__``. Exercise that call-time seam directly: an
        # in-process reload would replace public exception classes and strand
        # already-imported CLI handlers with stale class identities.
        original_spec_file = acceptance_module.SPEC_FILE
        original_plan_file = acceptance_module.PLAN_FILE
        monkeypatch.setattr(MissionTemplateRepository, "get_expected_artifacts", _patched_get_expected_artifacts)
        clear_cache()
        try:
            assert acceptance_module.SPEC_FILE == _SENTINEL_SPEC_FILENAME
            # PLAN_FILE is untouched by the patch -- proves the seam resolves
            # each artifact_key independently, not a single frozen tuple.
            assert original_plan_file == acceptance_module.PLAN_FILE
        finally:
            monkeypatch.undo()
            clear_cache()
            assert original_spec_file == acceptance_module.SPEC_FILE

    def test_retrospect_precondition_reflects_the_patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No reload needed -- the retrospect helper is call-time evaluated."""
        from specify_cli.cli.commands.agent_retrospect import (
            _required_planning_artifact_filenames,
        )

        monkeypatch.setattr(MissionTemplateRepository, "get_expected_artifacts", _patched_get_expected_artifacts)

        spec_name, plan_name, tasks_name = _required_planning_artifact_filenames()

        assert spec_name == _SENTINEL_SPEC_FILENAME
        assert plan_name == "plan.md"
        assert tasks_name == "tasks.md"


# ---------------------------------------------------------------------------
# AC-12 -- third-kind boundary pins (pin-and-defer; these two files are
# read-only in WP04 -- see plan.md fork (f))
# ---------------------------------------------------------------------------


class TestThirdKindBoundaryPins:
    """Characterization pins for the two named third-kind raises (AC-12).

    Neither ``_substantive.py`` nor ``mission_feature_resolution.py`` is
    touched by WP04 -- these tests pin TODAY's exact exception type and
    message fragment so a future silent-default reintroduction reds them.
    """

    def test_is_substantive_raises_value_error_for_unmapped_kind(self, tmp_path: Path) -> None:
        from specify_cli.missions._substantive import Kind, is_substantive

        target = tmp_path / "tasks.md"
        target.write_text("irrelevant content", encoding="utf-8")

        with pytest.raises(ValueError, match=r"Unknown kind: 'tasks'"):
            is_substantive(target, cast(Kind, "tasks"))

    def test_kind_for_artifact_raises_key_error_for_unmapped_type(self) -> None:
        from specify_cli.cli.commands.agent.mission_feature_resolution import (
            _kind_for_artifact,
        )

        with pytest.raises(KeyError, match="no silent default"):
            _kind_for_artifact("docs")


# ---------------------------------------------------------------------------
# WP02 T008/T009b -- org-tier ``repo_root`` awareness (FR-008) for
# ``required_artifacts_for`` / ``_load_expected_artifact_manifest``, plus the
# ANALYZE-ARCH-001 fix round's schema-error handling (FR-010). Mirrors
# ``ManifestRegistry.load_manifest``'s own FR-008/WP05 test shape
# (``tests/dossier/test_manifest.py::TestManifestRegistryOrgTier``).
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Write ``<repo_root>/.kittify/config.yaml`` with a ``doctrine.org.packs``
    registry only -- mirrors ``tests/dossier/test_manifest.py``'s helper of the
    same name/shape (the org-tier resolution path this WP threads through
    ``specify_cli.runtime.resolver`` reads org packs the same way).
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


def _write_org_manifest(org_root: Path, mission_type: str, data: dict) -> None:
    """Write ``<org_root>/missions/<mission_type>/expected-artifacts.yaml``."""
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.default_flow_style = False
    with (target_dir / "expected-artifacts.yaml").open("w") as fh:
        yaml.dump(data, fh)


class TestRequiredArtifactsForOrgTier:
    """T008/T009 (WP02, FR-008): ``required_artifacts_for``'s ``repo_root``
    parameter resolves an org-tier ``expected-artifacts.yaml`` in preference
    to the built-in manifest for the same mission type, whole-file (never
    field-merged).
    """

    def test_org_override_resolves_in_preference_to_built_in(self, tmp_path: Path) -> None:
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(
            org_root,
            "software-dev",
            {
                "schema_version": "1.0",
                "mission_type": "software-dev",
                "manifest_version": "org-1",
                "required_by_step": {
                    "specify": [
                        {
                            "artifact_key": "input.spec.main",
                            "artifact_class": "input",
                            "path_pattern": "org-spec.md",
                            "blocking": True,
                        }
                    ]
                },
            },
        )
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        result = required_artifacts_for("specify", "software-dev", repo_root=project_root)

        assert result == ["org-spec.md"]
        # The built-in tier's own filename must not leak in -- whole-file
        # replacement, never a field-merge.
        assert "spec.md" not in result

    def test_repo_root_with_no_org_pack_falls_through_to_built_in_unchanged(self, tmp_path: Path) -> None:
        """TASKS-VERIFY-003 fix: ``repo_root`` given but no
        ``missions/<type>/expected-artifacts.yaml`` exists under it --
        the org-tier consult's "no match" path must fall through cleanly to
        the built-in manifest, identical to the ``repo_root=None`` result.
        """
        project_root = tmp_path / "project-no-org-pack"
        project_root.mkdir()

        with_repo_root = required_artifacts_for("specify", "software-dev", repo_root=project_root)
        without_repo_root = required_artifacts_for("specify", "software-dev")

        assert with_repo_root == without_repo_root == ["spec.md"]

    def test_no_repo_root_argument_is_byte_identical_to_pre_wp_behavior(self) -> None:
        """The optional ``repo_root`` parameter defaults to ``None`` -- no
        call-site with no ``repo_root`` in scope is affected by this WP."""
        assert required_artifacts_for("specify", "software-dev") == ["spec.md"]
        assert required_artifacts_for("specify", "software-dev", repo_root=None) == ["spec.md"]


class TestManifestSchemaErrorPerTier:
    """T009b (WP02, ANALYZE-ARCH-001 fix round): a manifest that parses as
    YAML but fails ``ExpectedArtifactManifest`` schema validation
    (``extra="forbid"``) raises ``ManifestSchemaError`` -- not a bare
    ``pydantic.ValidationError`` -- for BOTH the built-in and org tiers.
    """

    _BROKEN_MISSION_TYPE = "broken-builtin-schema"

    @pytest.fixture
    def broken_builtin_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Point ``MissionTemplateRepository.default()`` at a temp missions
        root shipping a mission type whose manifest fails schema validation
        (an ``extra="forbid"``-rejected key)."""
        missions_root = tmp_path / "missions-root"
        broken_dir = missions_root / self._BROKEN_MISSION_TYPE
        broken_dir.mkdir(parents=True)
        (broken_dir / "expected-artifacts.yaml").write_text(
            f"schema_version: '1.0'\nmission_type: '{self._BROKEN_MISSION_TYPE}'\nmanifest_version: '1'\nnot_a_real_field: true\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            MissionTemplateRepository,
            "default",
            classmethod(lambda cls: MissionTemplateRepository(missions_root)),
        )

    def test_built_in_schema_invalid_manifest_raises_manifest_schema_error(self, broken_builtin_repo: None) -> None:
        from specify_cli.dossier.manifest import ManifestSchemaError

        with pytest.raises(ManifestSchemaError) as exc_info:
            required_artifacts_for("specify", self._BROKEN_MISSION_TYPE)

        exc = exc_info.value
        assert exc.mission_type == self._BROKEN_MISSION_TYPE
        # Built-in branch: ``config.origin`` is a real, reachable attribute
        # here (mirrors ``ManifestRegistry.load_manifest``'s own built-in
        # except-block, manifest.py:326-340).
        assert self._BROKEN_MISSION_TYPE in exc.origin

    def test_org_tier_schema_invalid_manifest_raises_manifest_schema_error(self, tmp_path: Path) -> None:
        """ANALYZE-FRESH-001: the org-tier branch has no ``config`` variable
        of type ``ConfigResult`` in scope, so ``.origin`` must NOT be read
        off it (that raises ``AttributeError``, not ``ManifestSchemaError``,
        defeating this fix on exactly the org-tier path FR-010 exists to
        cover). The origin must instead be a synthesized, descriptive
        string naming the org tier and the mission type.
        """
        from specify_cli.dossier.manifest import ManifestSchemaError

        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(
            org_root,
            "software-dev",
            # Missing required `mission_type` field -> pydantic ValidationError.
            {"schema_version": "1.0", "manifest_version": "broken"},
        )
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        with pytest.raises(ManifestSchemaError) as exc_info:
            required_artifacts_for("specify", "software-dev", repo_root=project_root)

        exc = exc_info.value
        assert exc.mission_type == "software-dev"
        # Descriptive org-tier origin -- never the unreachable built-in
        # `config.origin` expression (would raise `AttributeError` if used
        # by mistake in this branch).
        assert "org-tier" in exc.origin
        assert "software-dev" in exc.origin


# ---------------------------------------------------------------------------
# WP02 T009 (#3770): resolver.py's mirror now delegates to the authority --
# proves the delegation is live, not an inert local copy that happens to
# agree with the authority today.
# ---------------------------------------------------------------------------


class TestResolverRoutesThroughAuthority:
    def test_delegates_to_manifest_loader_load_manifest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import charter.activation.manifest_loader as manifest_loader_module

        calls: list[tuple[str, Path | None]] = []
        original_load_manifest = manifest_loader_module.load_manifest

        def _tracking_load_manifest(mission_type: str, repo_root: Path | None = None) -> object:
            calls.append((mission_type, repo_root))
            return original_load_manifest(mission_type, repo_root=repo_root)

        monkeypatch.setattr(manifest_loader_module, "load_manifest", _tracking_load_manifest)

        resolve_configured_artifact_name("input.spec.main", "software-dev")

        assert calls == [("software-dev", None)]
