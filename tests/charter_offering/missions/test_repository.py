"""Behavioral tests for MissionTemplateRepository and value objects.

Targets mutation-prone areas in charter.offering.missions.repository:
- list_missions: root-dir guard, mission.yaml existence filter, sorted output
- get_command_template / get_content_template: path construction, None on absent
- list_command_templates / list_content_templates: extension filtering, README exclusion
- get_action_index / get_mission_config / get_expected_artifacts: content + origin assertions
- TemplateResult / ConfigResult value objects: content/origin/parsed properties

Patterns: Boundary Pair (present/absent file), Non-Identity Inputs (distinct
mission/action names), Bi-Directional Logic (found vs. None returns).
"""

from pathlib import Path

import pytest

from charter.offering.missions.repository import (
    MalformedManifestError,
    MissionTemplateRepository,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_mission(root: Path, name: str, *, with_yaml: bool = True) -> Path:
    mission_dir = root / name
    mission_dir.mkdir(parents=True, exist_ok=True)
    if with_yaml:
        (mission_dir / "mission.yaml").write_text(f"key: {name}\n")
    return mission_dir


# ── list_missions ─────────────────────────────────────────────────────────────


class TestListMissions:
    """Boundary pairs on root-dir guard and mission.yaml presence filter."""

    def test_non_existent_root_returns_empty_list(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path / "no-such-dir")
        assert repo.list_missions() == []

    def test_empty_root_returns_empty_list(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_missions() == []

    def test_mission_without_yaml_not_listed(self, tmp_path: Path):
        _make_mission(tmp_path, "no-yaml", with_yaml=False)
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_missions() == []

    def test_mission_with_yaml_is_listed(self, tmp_path: Path):
        _make_mission(tmp_path, "software-dev")
        repo = MissionTemplateRepository(tmp_path)
        assert "software-dev" in repo.list_missions()

    def test_only_directories_with_yaml_included(self, tmp_path: Path):
        _make_mission(tmp_path, "has-yaml")
        _make_mission(tmp_path, "no-yaml", with_yaml=False)
        # A plain file at the root should also not appear
        (tmp_path / "orphan.yaml").write_text("key: orphan\n")
        result = repo = MissionTemplateRepository(tmp_path)
        result = repo.list_missions()
        assert result == ["has-yaml"]

    def test_list_missions_returns_sorted_names(self, tmp_path: Path):
        for name in ["zebra", "alpha", "mid"]:
            _make_mission(tmp_path, name)
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_missions() == ["alpha", "mid", "zebra"]

    def test_multiple_missions_all_listed(self, tmp_path: Path):
        for name in ["doc-mission", "software-dev", "custom"]:
            _make_mission(tmp_path, name)
        repo = MissionTemplateRepository(tmp_path)
        result = repo.list_missions()
        assert len(result) == 3
        assert "software-dev" in result
        assert "doc-mission" in result


# ── get_command_template ──────────────────────────────────────────────────────


class TestGetCommandTemplate:
    """Boundary pairs on command-template presence and origin string."""

    def _write_command_template(self, root: Path, mission: str, name: str, text: str) -> None:
        d = root / mission / "command-templates"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(text)

    def test_returns_none_when_template_absent(self, tmp_path: Path):
        _make_mission(tmp_path, "software-dev")
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_command_template("software-dev", "nonexistent") is None

    def test_returns_none_when_mission_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_command_template("missing-mission", "implement") is None

    def test_returns_content_when_template_present(self, tmp_path: Path):
        self._write_command_template(tmp_path, "software-dev", "implement", "# Implement\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_command_template("software-dev", "implement")
        assert result is not None
        assert result.content == "# Implement\n"

    def test_origin_contains_mission_and_name(self, tmp_path: Path):
        self._write_command_template(tmp_path, "my-mission", "specify", "content")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_command_template("my-mission", "specify")
        assert result is not None
        assert "my-mission" in result.origin
        assert "specify" in result.origin

    def test_origin_format_matches_builtin_path(self, tmp_path: Path):
        self._write_command_template(tmp_path, "software-dev", "plan", "content")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_command_template("software-dev", "plan")
        assert result is not None
        assert result.origin == "built-in/software-dev/command-templates/plan.md"

    def test_content_is_non_none(self, tmp_path: Path):
        self._write_command_template(tmp_path, "software-dev", "review", "review text")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_command_template("software-dev", "review")
        assert result is not None
        assert result.content is not None
        assert result.origin is not None


# ── get_content_template ──────────────────────────────────────────────────────


class TestGetContentTemplate:
    """Boundary pairs on content-template presence."""

    def _write_content_template(self, root: Path, mission: str, name: str, text: str) -> None:
        d = root / mission / "templates"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text)

    def test_returns_none_when_template_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_content_template("software-dev", "spec-template.md") is None

    def test_returns_content_when_template_present(self, tmp_path: Path):
        self._write_content_template(tmp_path, "software-dev", "spec-template.md", "# Spec\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_content_template("software-dev", "spec-template.md")
        assert result is not None
        assert result.content == "# Spec\n"

    def test_origin_contains_mission_and_filename(self, tmp_path: Path):
        self._write_content_template(tmp_path, "my-mission", "plan-template.md", "text")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_content_template("my-mission", "plan-template.md")
        assert result is not None
        assert "my-mission" in result.origin
        assert "plan-template.md" in result.origin

    def test_origin_format(self, tmp_path: Path):
        self._write_content_template(tmp_path, "software-dev", "spec-template.md", "text")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_content_template("software-dev", "spec-template.md")
        assert result is not None
        assert result.origin == "built-in/software-dev/templates/spec-template.md"


# ── list_command_templates ────────────────────────────────────────────────────


class TestListCommandTemplates:
    """Extension filtering, README exclusion, sorted output."""

    def _write_cmd(self, root: Path, mission: str, names: list[str]) -> None:
        d = root / mission / "command-templates"
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / n).write_text("content")

    def test_returns_empty_when_no_dir(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_command_templates("nonexistent") == []

    def test_returns_stems_without_extension(self, tmp_path: Path):
        self._write_cmd(tmp_path, "m", ["implement.md", "review.md"])
        repo = MissionTemplateRepository(tmp_path)
        result = repo.list_command_templates("m")
        assert "implement" in result
        assert "review" in result
        assert "implement.md" not in result

    def test_excludes_readme(self, tmp_path: Path):
        self._write_cmd(tmp_path, "m", ["implement.md", "README.md"])
        repo = MissionTemplateRepository(tmp_path)
        assert "README" not in repo.list_command_templates("m")

    def test_non_md_files_excluded(self, tmp_path: Path):
        self._write_cmd(tmp_path, "m", ["implement.md", "config.yaml"])
        repo = MissionTemplateRepository(tmp_path)
        result = repo.list_command_templates("m")
        assert "implement" in result
        assert "config" not in result

    def test_returns_sorted_names(self, tmp_path: Path):
        self._write_cmd(tmp_path, "m", ["tasks.md", "implement.md", "plan.md"])
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_command_templates("m") == ["implement", "plan", "tasks"]


# ── list_content_templates ────────────────────────────────────────────────────


class TestListContentTemplates:
    """Filename preservation (with extension), README exclusion."""

    def _write_tpl(self, root: Path, mission: str, names: list[str]) -> None:
        d = root / mission / "templates"
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / n).write_text("content")

    def test_returns_empty_when_no_dir(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_content_templates("nonexistent") == []

    def test_filenames_include_extension(self, tmp_path: Path):
        self._write_tpl(tmp_path, "m", ["spec-template.md", "plan-template.md"])
        repo = MissionTemplateRepository(tmp_path)
        result = repo.list_content_templates("m")
        assert "spec-template.md" in result
        assert "plan-template.md" in result

    def test_excludes_readme(self, tmp_path: Path):
        self._write_tpl(tmp_path, "m", ["spec-template.md", "README.md"])
        repo = MissionTemplateRepository(tmp_path)
        assert "README.md" not in repo.list_content_templates("m")

    def test_returns_sorted_names(self, tmp_path: Path):
        self._write_tpl(tmp_path, "m", ["z-template.md", "a-template.md"])
        repo = MissionTemplateRepository(tmp_path)
        assert repo.list_content_templates("m") == ["a-template.md", "z-template.md"]


# ── get_action_index ──────────────────────────────────────────────────────────


class TestGetActionIndex:
    """Content, origin, and parsed assertions for action index loading."""

    def _write_index(self, root: Path, mission: str, action: str, yaml_text: str) -> None:
        d = root / mission / "actions" / action
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.yaml").write_text(yaml_text)

    def test_returns_none_when_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_action_index("software-dev", "implement") is None

    def test_returns_result_with_content_and_origin(self, tmp_path: Path):
        yaml_text = "directives:\n  - DIR-001\n"
        self._write_index(tmp_path, "software-dev", "implement", yaml_text)
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_index("software-dev", "implement")
        assert result is not None
        assert result.content == yaml_text
        assert result.origin == "built-in/software-dev/actions/implement/index.yaml"

    def test_content_is_not_none(self, tmp_path: Path):
        self._write_index(tmp_path, "m", "act", "key: value\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_index("m", "act")
        assert result is not None
        assert result.content is not None

    def test_origin_is_not_none(self, tmp_path: Path):
        self._write_index(tmp_path, "m", "act", "key: value\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_index("m", "act")
        assert result is not None
        assert result.origin is not None

    def test_origin_contains_mission_and_action(self, tmp_path: Path):
        self._write_index(tmp_path, "my-mission", "review", "key: value\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_index("my-mission", "review")
        assert result is not None
        assert "my-mission" in result.origin
        assert "review" in result.origin

    def test_parsed_is_dict_with_expected_keys(self, tmp_path: Path):
        yaml_text = "directives:\n  - DIR-001\n  - DIR-002\ntactics:\n  - tactic-a\n"
        self._write_index(tmp_path, "m", "implement", yaml_text)
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_index("m", "implement")
        assert result is not None
        assert isinstance(result.parsed, dict)
        assert result.parsed["directives"] == ["DIR-001", "DIR-002"]
        assert result.parsed["tactics"] == ["tactic-a"]

    def test_returns_none_on_invalid_yaml(self, tmp_path: Path):
        self._write_index(tmp_path, "m", "act", "invalid: yaml: {")
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_action_index("m", "act") is None

    def test_returns_none_on_empty_yaml(self, tmp_path: Path):
        self._write_index(tmp_path, "m", "act", "")
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_action_index("m", "act") is None


# ── get_action_guidelines ─────────────────────────────────────────────────────


class TestGetActionGuidelines:
    """Boundary pairs on presence/absence of guidelines.md."""

    def _write_guidelines(self, root: Path, mission: str, action: str, text: str) -> None:
        d = root / "mission-steps" / mission / action
        d.mkdir(parents=True, exist_ok=True)
        (d / "guidelines.md").write_text(text)

    def test_returns_none_when_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_action_guidelines("software-dev", "implement") is None

    def test_returns_content_when_present(self, tmp_path: Path):
        self._write_guidelines(tmp_path, "software-dev", "implement", "# Guidelines\n")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_guidelines("software-dev", "implement")
        assert result is not None
        assert result.content == "# Guidelines\n"

    def test_origin_contains_mission_action_and_filename(self, tmp_path: Path):
        self._write_guidelines(tmp_path, "my-mission", "review", "text")
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_action_guidelines("my-mission", "review")
        assert result is not None
        assert result.origin == "built-in/mission-steps/my-mission/review/guidelines.md"


# ── get_mission_config ────────────────────────────────────────────────────────


class TestGetMissionConfig:
    """Content, origin, and parsed assertions for mission config."""

    def test_returns_none_when_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_mission_config("nonexistent") is None

    def test_returns_result_when_present(self, tmp_path: Path):
        yaml_text = "key: software-dev\nname: Software Dev\n"
        mission_dir = tmp_path / "software-dev"
        mission_dir.mkdir()
        (mission_dir / "mission.yaml").write_text(yaml_text)
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_mission_config("software-dev")
        assert result is not None
        assert result.content == yaml_text
        assert result.origin == "built-in/software-dev/mission.yaml"
        assert result.parsed["key"] == "software-dev"

    def test_returns_none_on_invalid_yaml(self, tmp_path: Path):
        mission_dir = tmp_path / "bad-mission"
        mission_dir.mkdir()
        (mission_dir / "mission.yaml").write_text("bad: yaml: {")
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_mission_config("bad-mission") is None


# ── get_expected_artifacts ────────────────────────────────────────────────────


class TestGetExpectedArtifacts:
    """Boundary pairs on expected-artifacts.yaml presence."""

    def test_returns_none_when_absent(self, tmp_path: Path):
        repo = MissionTemplateRepository(tmp_path)
        assert repo.get_expected_artifacts("nonexistent") is None

    def test_returns_result_when_present(self, tmp_path: Path):
        yaml_text = "artifacts:\n  - id: spec.md\n"
        mission_dir = tmp_path / "software-dev"
        mission_dir.mkdir()
        (mission_dir / "expected-artifacts.yaml").write_text(yaml_text)
        repo = MissionTemplateRepository(tmp_path)
        result = repo.get_expected_artifacts("software-dev")
        assert result is not None
        assert result.content == yaml_text
        assert result.origin == "built-in/software-dev/expected-artifacts.yaml"
        assert isinstance(result.parsed, dict)

    def test_malformed_manifest_fails_loud_distinct_from_absent(self, tmp_path: Path):
        """SC-005/#3412: a present-but-YAML-broken manifest must FAIL LOUD.

        The whole point of the fix is that a syntactically-corrupt manifest is
        NOT conflated with an absent one. Absence degrades to ``None``
        ("absent"); a broken-syntax file surfaces a distinct, operator-legible
        failure instead of the identical ``None``.
        """
        repo = MissionTemplateRepository(tmp_path)

        # Contrast control: an ABSENT manifest degrades to "absent" (None).
        absent_outcome = repo.get_expected_artifacts("nonexistent")

        # A PRESENT-but-YAML-broken manifest fails loud rather than masquerading
        # as "absent".
        mission_dir = tmp_path / "broken-mission"
        mission_dir.mkdir()
        manifest_path = mission_dir / "expected-artifacts.yaml"
        manifest_path.write_text("invalid: yaml: {")

        with pytest.raises(MalformedManifestError) as excinfo:
            repo.get_expected_artifacts("broken-mission")

        # The two outcomes must NOT be conflated: absence -> None; malformed ->
        # raised, distinct, operator-legible signal naming the offending file.
        assert absent_outcome is None
        assert excinfo.value.path == manifest_path

    def test_present_but_non_mapping_manifest_fails_loud(self, tmp_path: Path) -> None:
        """#3412/FR-008 symmetry: a PRESENT built-in manifest that parses to a
        non-mapping (a top-level scalar/sequence) fails loud via
        ``MalformedManifestError`` -- the SAME sibling type the org tier uses
        for this class -- distinct from absence and from a schema/extra=forbid
        violation. Before this guard the value flowed to ``model_validate`` and
        surfaced as ``ManifestSchemaError``, an asymmetry with the org tier the
        consolidation review flagged.
        """
        mission_dir = tmp_path / "list-mission"
        mission_dir.mkdir()
        manifest_path = mission_dir / "expected-artifacts.yaml"
        manifest_path.write_text("- just\n- a\n- list\n")
        repo = MissionTemplateRepository(tmp_path)

        with pytest.raises(MalformedManifestError) as excinfo:
            repo.get_expected_artifacts("list-mission")
        assert excinfo.value.path == manifest_path
        assert "list" in str(excinfo.value)

    @pytest.mark.regression
    def test_present_but_unreadable_manifest_fails_loud(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#3412 FR-012 [RED-first]: a manifest that EXISTS on disk but
        raises ``OSError``/``UnicodeDecodeError`` on read must fail loud via
        ``MalformedManifestError``, not degrade silently to ``None``.

        Was RED on pre-WP03 code -- ``get_expected_artifacts`` caught
        ``(OSError, UnicodeDecodeError)`` and returned ``None`` for a
        PRESENT file, indistinguishable from genuine absence. GREEN after
        FR-012's widening (this WP) folds that except-branch into the same
        ``MalformedManifestError`` raise as the pre-existing ``YAMLError``
        case (shipped in ``1763bf2ae3``).

        Injection: monkeypatch ``pathlib.Path.read_text`` to raise
        ``OSError`` for the target manifest path only, passing through for
        every other path (the real ``packs/built-in`` tree is read-only, so
        this is the lighter-weight alternative to an undecodable-bytes
        fixture).
        """
        mission_dir = tmp_path / "unreadable-mission"
        mission_dir.mkdir()
        manifest_path = mission_dir / "expected-artifacts.yaml"
        manifest_path.write_text("artifacts:\n  - id: spec.md\n")

        original_read_text = Path.read_text

        def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
            if self == manifest_path:
                raise OSError("simulated unreadable file")
            return original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        repo = MissionTemplateRepository(tmp_path)

        # Contrast control: an ABSENT manifest still degrades to None.
        absent_outcome = repo.get_expected_artifacts("nonexistent")

        with pytest.raises(MalformedManifestError) as excinfo:
            repo.get_expected_artifacts("unreadable-mission")

        assert absent_outcome is None
        assert excinfo.value.path == manifest_path

    def test_malformed_manifest_error_names_file_and_cause(self, tmp_path: Path) -> None:
        """T014 / NFR-005 / Invariant I2: ``str(MalformedManifestError)``
        names both the source file and the underlying cause, without
        requiring exception-note inspection.
        """
        mission_dir = tmp_path / "broken-mission"
        mission_dir.mkdir()
        manifest_path = mission_dir / "expected-artifacts.yaml"
        manifest_path.write_text("invalid: yaml: {")
        repo = MissionTemplateRepository(tmp_path)

        with pytest.raises(MalformedManifestError) as excinfo:
            repo.get_expected_artifacts("broken-mission")

        message = str(excinfo.value)
        assert str(manifest_path) in message
        assert str(excinfo.value.cause) in message
        assert "broken-mission" in str(excinfo.value)
