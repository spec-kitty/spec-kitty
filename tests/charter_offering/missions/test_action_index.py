"""Tests for charter.offering.missions.action_index.load_action_index.

Targets mutation-prone areas:
- Path construction (mission / "actions" / action / "index.yaml")
- Fallback behavior (missing file only — the sole silent path)
- Fail-loud behavior (present-but-malformed index raises ActionIndexError)
- Per-field list extraction (_str_list helper)

Contract (operator DD-4, #2667): present ⇒ well-formed; absent ⇒ empty. A
present-but-malformed index file must raise ActionIndexError rather than
silently degrading to an empty grain.

Patterns: Boundary Pair (file present/absent), Non-Identity Inputs (distinct
field values), Bi-Directional Logic (fallback vs. populated ActionIndex vs.
raise).
"""

from pathlib import Path

import pytest

from charter.offering.missions.action_index import ActionIndex, ActionIndexError, load_action_index

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _write_index(root: Path, mission: str, action: str, text: str) -> Path:
    d = root / mission / "actions" / action
    d.mkdir(parents=True, exist_ok=True)
    p = d / "index.yaml"
    p.write_text(text)
    return p


# ── Fallback behavior — the SOLE silent path is a genuinely-missing file ───────


class TestLoadActionIndexFallback:
    """Fallback ActionIndex returned ONLY when the index file is absent."""

    def test_missing_file_returns_fallback(self, tmp_path: Path):
        result = load_action_index(tmp_path, "software-dev", "implement")
        assert isinstance(result, ActionIndex)
        assert result.action == "implement"
        assert result.directives == []
        assert result.tactics == []

    def test_fallback_action_name_matches_argument(self, tmp_path: Path):
        result = load_action_index(tmp_path, "any-mission", "review")
        assert result.action == "review"


# ── Present, well-formed, empty content — NO raise ─────────────────────────────


class TestLoadActionIndexEmptyButWellFormed:
    """A present index that is well-formed but declares no doctrine is empty
    content, not an error — distinct from a genuinely-missing file."""

    def test_action_only_key_returns_empty_content(self, tmp_path: Path):
        _write_index(tmp_path, "m", "act", "action: implement\n")
        result = load_action_index(tmp_path, "m", "act")
        assert result.action == "implement"
        assert result.directives == []
        assert result.tactics == []
        assert result.paradigms == []
        assert result.styleguides == []
        assert result.toolguides == []
        assert result.procedures == []
        assert result.agent_profiles == []

    def test_all_empty_lists_returns_empty_content(self, tmp_path: Path):
        yaml = (
            "action: plan\n"
            "directives: []\n"
            "tactics: []\n"
            "paradigms: []\n"
            "styleguides: []\n"
            "toolguides: []\n"
            "procedures: []\n"
            "agent_profiles: []\n"
        )
        _write_index(tmp_path, "m", "act", yaml)
        result = load_action_index(tmp_path, "m", "act")
        assert result.action == "plan"
        assert result.directives == []


# ── Fail-loud behavior — present-but-malformed raises ActionIndexError ─────────


class TestLoadActionIndexFailLoud:
    """A present index that is not a well-formed ActionIndex raises loudly
    instead of silently degrading to an empty grain (#2667)."""

    def test_non_mapping_root_list_raises(self, tmp_path: Path):
        _write_index(tmp_path, "m", "act", "- item1\n- item2\n")
        with pytest.raises(ActionIndexError):
            load_action_index(tmp_path, "m", "act")

    def test_non_mapping_root_empty_file_raises(self, tmp_path: Path):
        _write_index(tmp_path, "m", "act", "")
        with pytest.raises(ActionIndexError):
            load_action_index(tmp_path, "m", "act")

    def test_non_list_field_value_raises(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "directives: not-a-list\n")
        with pytest.raises(ActionIndexError):
            load_action_index(tmp_path, "m", "a")

    def test_unparseable_yaml_raises(self, tmp_path: Path):
        _write_index(tmp_path, "m", "act", "bad: yaml: {")
        with pytest.raises(ActionIndexError):
            load_action_index(tmp_path, "m", "act")

    def test_error_message_names_path_and_type(self, tmp_path: Path):
        index_path = _write_index(tmp_path, "m", "act", "- item1\n- item2\n")
        with pytest.raises(ActionIndexError) as excinfo:
            load_action_index(tmp_path, "m", "act")
        message = str(excinfo.value)
        assert str(index_path) in message
        assert "list" in message


# ── Happy path — path construction ────────────────────────────────────────────


class TestLoadActionIndexPathConstruction:
    """Verify the path used is mission/actions/action/index.yaml."""

    def test_reads_from_correct_path(self, tmp_path: Path):
        # Only the exact path should be found
        yaml = "directives:\n  - DIR-001\n"
        _write_index(tmp_path, "software-dev", "implement", yaml)
        result = load_action_index(tmp_path, "software-dev", "implement")
        assert result.directives == ["DIR-001"]

    def test_wrong_action_name_yields_fallback(self, tmp_path: Path):
        _write_index(tmp_path, "software-dev", "implement", "directives:\n  - DIR-001\n")
        result = load_action_index(tmp_path, "software-dev", "review")
        assert result.directives == []

    def test_wrong_mission_name_yields_fallback(self, tmp_path: Path):
        _write_index(tmp_path, "software-dev", "implement", "directives:\n  - DIR-001\n")
        result = load_action_index(tmp_path, "other-mission", "implement")
        assert result.directives == []


# ── Field extraction ───────────────────────────────────────────────────────────


class TestLoadActionIndexFields:
    """Each field populated from YAML independently."""

    def test_directives_populated(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "directives:\n  - DIR-001\n  - DIR-002\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.directives == ["DIR-001", "DIR-002"]

    def test_tactics_populated(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "tactics:\n  - tactic-alpha\n  - tactic-beta\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.tactics == ["tactic-alpha", "tactic-beta"]

    def test_styleguides_populated(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "styleguides:\n  - style-x\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.styleguides == ["style-x"]

    def test_toolguides_populated(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "toolguides:\n  - tool-y\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.toolguides == ["tool-y"]

    def test_procedures_populated(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "procedures:\n  - proc-z\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.procedures == ["proc-z"]

    def test_all_fields_populated(self, tmp_path: Path):
        yaml = (
            "action: custom-action\n"
            "directives:\n  - DIR-001\n"
            "tactics:\n  - tactic-a\n"
            "paradigms:\n  - paradigm-b\n"
            "styleguides:\n  - style-b\n"
            "toolguides:\n  - tool-c\n"
            "procedures:\n  - proc-d\n"
        )
        _write_index(tmp_path, "m", "act", yaml)
        result = load_action_index(tmp_path, "m", "act")
        assert result.action == "custom-action"
        assert result.directives == ["DIR-001"]
        assert result.tactics == ["tactic-a"]
        assert result.paradigms == ["paradigm-b"]
        assert result.styleguides == ["style-b"]
        assert result.toolguides == ["tool-c"]
        assert result.procedures == ["proc-d"]

    def test_missing_field_defaults_to_empty_list(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "directives:\n  - DIR-001\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.tactics == []
        assert result.paradigms == []
        assert result.styleguides == []
        assert result.toolguides == []
        assert result.procedures == []

    def test_action_field_overrides_argument(self, tmp_path: Path):
        _write_index(tmp_path, "m", "a", "action: renamed-action\n")
        result = load_action_index(tmp_path, "m", "a")
        assert result.action == "renamed-action"
