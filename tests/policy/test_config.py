"""Tests for policy configuration loading."""

import logging

from specify_cli.policy.config import (
    CommitGuardConfig,
    MergeGateConfig,
    PolicyConfig,
    RiskPolicyConfig,
    load_policy_config,
)


import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

class TestDefaults:
    def test_all_defaults(self):
        config = PolicyConfig()
        assert config.risk.enabled is True
        assert config.risk.mode == "warn"
        assert config.risk.threshold == 0.6
        assert config.commit_guard.enabled is True
        assert config.commit_guard.mode == "warn"
        assert config.merge_gates.enabled is True
        assert config.merge_gates.mode == "warn"

    def test_unrecognised_mode_fails_closed_to_block(self):
        r = RiskPolicyConfig(mode="invalid")
        assert r.mode == "block"
        c = CommitGuardConfig(mode="bogus")
        assert c.mode == "block"
        m = MergeGateConfig(mode="")
        assert m.mode == "block"


_LOGGER = "specify_cli.policy.config"
_SECTIONS = [
    pytest.param(RiskPolicyConfig, "risk", id="risk"),
    pytest.param(CommitGuardConfig, "commit_guard", id="commit_guard"),
    pytest.param(MergeGateConfig, "merge_gates", id="merge_gates"),
]


def _policy_warnings(caplog):
    return [r for r in caplog.records if r.name == _LOGGER and r.levelno == logging.WARNING]


class TestModeResolution:
    """#5754: modes match ignoring case/whitespace; unknown values fail closed."""

    @pytest.mark.parametrize(("cls", "section"), _SECTIONS)
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Block", "block"),
            ("BLOCK", "block"),
            ("block ", "block"),
            (" Block", "block"),
            ("Warn", "warn"),
            ("WARN", "warn"),
            ("Off", "off"),
            ("OFF", "off"),
            (" off ", "off"),
            ("warn", "warn"),
            ("block", "block"),
            ("off", "off"),
        ],
    )
    def test_recognised_spelling_resolves_without_warning(self, caplog, cls, section, raw, expected):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        assert cls(mode=raw).mode == expected
        assert _policy_warnings(caplog) == []

    @pytest.mark.parametrize(("cls", "section"), _SECTIONS)
    @pytest.mark.parametrize("raw", ["blok", "", "strict", 1, True])
    def test_unknown_mode_fails_closed_with_one_warning(self, caplog, cls, section, raw):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        assert cls(mode=raw).mode == "block"
        warnings = _policy_warnings(caplog)
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert f"policy.{section}.mode" in message
        assert repr(raw) in message
        for allowed in ("warn", "block", "off"):
            assert allowed in message

    @pytest.mark.parametrize(("cls", "section"), _SECTIONS)
    def test_none_resolves_to_warn_without_warning(self, caplog, cls, section):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        assert cls(**{"mode": None}).mode == "warn"
        assert _policy_warnings(caplog) == []


def _write_config(tmp_path, body):
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(body)


class TestModeResolutionFromYaml:
    def test_spellings_load_as_canonical_modes(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        _write_config(
            tmp_path,
            'policy:\n  merge_gates:\n    mode: Block\n  risk:\n    mode: BLOCK\n  commit_guard:\n    mode: "block "\n',
        )
        config = load_policy_config(tmp_path)
        assert config.merge_gates.mode == "block"
        assert config.risk.mode == "block"
        assert config.commit_guard.mode == "block"
        assert _policy_warnings(caplog) == []

    def test_capitalised_off_loads_as_off(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        _write_config(tmp_path, "policy:\n  commit_guard:\n    mode: Off\n")
        assert load_policy_config(tmp_path).commit_guard.mode == "off"
        assert _policy_warnings(caplog) == []

    def test_null_and_absent_mode_are_warn_beside_an_unknown_sibling(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        # risk.mode: (null), commit_guard.mode omitted, merge_gates.mode: blok (paired control)
        _write_config(
            tmp_path,
            "policy:\n  risk:\n    mode:\n  commit_guard:\n    enabled: true\n  merge_gates:\n    mode: blok\n",
        )
        config = load_policy_config(tmp_path)
        assert config.risk.mode == "warn"
        assert config.commit_guard.mode == "warn"
        assert config.merge_gates.mode == "block"
        warnings = _policy_warnings(caplog)
        assert len(warnings) == 1
        assert "policy.merge_gates.mode" in warnings[0].getMessage()

    @pytest.mark.parametrize(
        ("null_section", "sibling"),
        [("risk", "merge_gates"), ("commit_guard", "risk"), ("merge_gates", "commit_guard")],
    )
    def test_yaml_null_mode_is_warn_in_every_section(self, tmp_path, caplog, null_section, sibling):
        # A bare `mode:` is YAML null. The parser must hand None through (not "None") so it
        # resolves to warn with no warning; the `blok` sibling proves the warning count (FR-004).
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        _write_config(
            tmp_path,
            f"policy:\n  {null_section}:\n    mode:\n  {sibling}:\n    mode: blok\n",
        )
        config = load_policy_config(tmp_path)
        assert getattr(config, null_section).mode == "warn"
        assert getattr(config, sibling).mode == "block"
        warnings = _policy_warnings(caplog)
        assert len(warnings) == 1
        assert f"policy.{sibling}.mode" in warnings[0].getMessage()

    def test_sections_resolve_independently(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        _write_config(
            tmp_path,
            "policy:\n  risk:\n    mode: blok\n  merge_gates:\n    mode: warn\n  commit_guard:\n    mode: off\n",
        )
        config = load_policy_config(tmp_path)
        assert (config.risk.mode, config.merge_gates.mode, config.commit_guard.mode) == ("block", "warn", "off")
        warnings = _policy_warnings(caplog)
        assert len(warnings) == 1
        assert "policy.risk.mode" in warnings[0].getMessage()

    @pytest.mark.parametrize("section", ["risk", "commit_guard", "merge_gates"])
    @pytest.mark.parametrize("written", ['""', "false", "0"])
    def test_falsy_yaml_mode_fails_closed(self, tmp_path, caplog, section, written):
        # A present but falsy value is not "absent": only YAML null keeps the warn default.
        # Guards the parsers against an `or "warn"` fallback that would weaken these to warn.
        caplog.set_level(logging.WARNING, logger=_LOGGER)
        _write_config(tmp_path, f"policy:\n  {section}:\n    mode: {written}\n")
        assert getattr(load_policy_config(tmp_path), section).mode == "block"
        warnings = _policy_warnings(caplog)
        assert len(warnings) == 1
        assert f"policy.{section}.mode" in warnings[0].getMessage()


class TestLoadFromYaml:
    def test_missing_file_returns_defaults(self, tmp_path):
        config = load_policy_config(tmp_path)
        assert config.risk.mode == "warn"
        assert config.commit_guard.mode == "warn"
        assert config.merge_gates.mode == "warn"

    def test_missing_policy_section_returns_defaults(self, tmp_path):
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text("agents:\n  available: [claude]\n")
        config = load_policy_config(tmp_path)
        assert config.risk.mode == "warn"

    def test_full_policy_section(self, tmp_path):
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "policy:\n"
            "  risk:\n"
            "    enabled: true\n"
            "    mode: block\n"
            "    threshold: 0.8\n"
            "  commit_guard:\n"
            "    enabled: false\n"
            "    mode: off\n"
            "  merge_gates:\n"
            "    mode: block\n"
            "    require_review_approval: false\n"
        )
        config = load_policy_config(tmp_path)
        assert config.risk.mode == "block"
        assert config.risk.threshold == 0.8
        assert config.commit_guard.enabled is False
        assert config.commit_guard.mode == "off"
        assert config.merge_gates.mode == "block"
        assert config.merge_gates.require_review_approval is False

    def test_partial_policy_section(self, tmp_path):
        (tmp_path / ".kittify").mkdir()
        (tmp_path / ".kittify" / "config.yaml").write_text(
            "policy:\n"
            "  risk:\n"
            "    mode: block\n"
        )
        config = load_policy_config(tmp_path)
        assert config.risk.mode == "block"
        # Unspecified sections get defaults
        assert config.commit_guard.mode == "warn"
        assert config.merge_gates.mode == "warn"
