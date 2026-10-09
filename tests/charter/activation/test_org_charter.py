"""Unit tests for org-charter policy composition (WP09, T050).

Covers:
- OrgCharterPolicy model + loader
- load_org_charter_policies merge semantics
- apply_org_charter_pre_fill non-destructive behaviour
- org_charter JSON block presence/absence via org_charter_loader
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.interview import apply_org_charter_pre_fill_to_answers
from charter.activation.org_charter import (
    GovernancePolicy,
    OrgCharterCycleError,
    OrgCharterExtensionError,
    OrgCharterPolicy,
    _build_pack_set,
    _fold_policies,
    _merge_chain,
    _resolve_chain,
    apply_org_charter_pre_fill,
    apply_org_charter_to_interview,
    load_org_charter_policies,
    load_org_charter_policy,
)
from charter.activation.org_charter_loader import load_org_charter_json_block


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_org_charter(pack_dir: Path, body: str) -> Path:
    """Write a YAML org-charter file at ``pack_dir/org-charter.yaml``."""
    pack_dir.mkdir(parents=True, exist_ok=True)
    path = pack_dir / "org-charter.yaml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _write_kittify_config(repo_root: Path, packs: list[dict]) -> None:
    """Write ``.kittify/config.yaml`` with ``doctrine.org.packs``."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    pack_yaml_lines = ["doctrine:", "  org:", "    packs:"]
    for pack in packs:
        pack_yaml_lines.append(f"      - name: {pack['name']}")
        pack_yaml_lines.append(f"        local_path: {pack['local_path']}")
    config_path = config_dir / "config.yaml"
    config_path.write_text("\n".join(pack_yaml_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# T050: load_org_charter_policy (single pack)
# ---------------------------------------------------------------------------


class TestLoadOrgCharterPolicy:
    def test_load_single_pack_policy(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            schema_version: "1"
            org_name: "Acme"
            interview_defaults:
              human_in_command: true
              security_review: "Required"
            required_directives:
              - sec-001
              - sec-002
            governance_policies:
              - field: "autonomous_mode"
                value: "disallowed"
                enforcement: advisory
            """,
        )

        policy = load_org_charter_policy(pack)

        assert policy is not None
        assert policy.schema_version == 1
        assert policy.org_name == "Acme"
        assert policy.interview_defaults == {
            "human_in_command": True,
            "security_review": "Required",
        }
        assert policy.required_directives == ["sec-001", "sec-002"]
        assert len(policy.governance_policies) == 1
        gp = policy.governance_policies[0]
        assert gp.field == "autonomous_mode"
        assert gp.value == "disallowed"
        assert gp.enforcement == "advisory"

    def test_load_missing_charter(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        pack.mkdir()

        assert load_org_charter_policy(pack) is None

    def test_load_empty_file(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(pack, "")

        assert load_org_charter_policy(pack) is None

    def test_load_malformed_yaml_returns_none(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        pack.mkdir()
        (pack / "org-charter.yaml").write_text("::: not valid yaml :::", encoding="utf-8")

        assert load_org_charter_policy(pack) is None


# ---------------------------------------------------------------------------
# T050: load_org_charter_policies (multi-pack merge)
# ---------------------------------------------------------------------------


class TestLoadOrgCharterPolicies:
    def test_load_org_charter_policies_empty(self, tmp_path: Path) -> None:
        """Zero configured packs -> empty policy, not None, no error."""
        policy = load_org_charter_policies(tmp_path)

        assert isinstance(policy, OrgCharterPolicy)
        assert policy.interview_defaults == {}
        assert policy.required_directives == []
        assert policy.governance_policies == []

    def test_load_packs_without_charter_returns_empty(self, tmp_path: Path) -> None:
        """Packs configured but none ship org-charter.yaml -> empty policy."""
        pack_a = tmp_path / "packs" / "a"
        pack_a.mkdir(parents=True)
        _write_kittify_config(
            tmp_path,
            [{"name": "a", "local_path": str(pack_a)}],
        )

        policy = load_org_charter_policies(tmp_path)

        assert isinstance(policy, OrgCharterPolicy)
        assert policy.interview_defaults == {}
        assert policy.required_directives == []

    def test_merge_interview_defaults_precedence(self, tmp_path: Path) -> None:
        """Two packs with overlapping interview_defaults: last pack wins."""
        pack_a = tmp_path / "packs" / "a"
        pack_b = tmp_path / "packs" / "b"
        _write_org_charter(
            pack_a,
            """
            interview_defaults:
              human_in_command: true
              shared_key: "from-a"
            """,
        )
        _write_org_charter(
            pack_b,
            """
            interview_defaults:
              shared_key: "from-b"
              new_key: "only-in-b"
            """,
        )
        _write_kittify_config(
            tmp_path,
            [
                {"name": "a", "local_path": str(pack_a)},
                {"name": "b", "local_path": str(pack_b)},
            ],
        )

        policy = load_org_charter_policies(tmp_path)

        assert policy.interview_defaults["human_in_command"] is True
        assert policy.interview_defaults["shared_key"] == "from-b"  # b wins
        assert policy.interview_defaults["new_key"] == "only-in-b"

    def test_merge_required_directives_union(self, tmp_path: Path) -> None:
        """Two packs with overlapping required_directives: union, no dupes."""
        pack_a = tmp_path / "packs" / "a"
        pack_b = tmp_path / "packs" / "b"
        _write_org_charter(
            pack_a,
            """
            required_directives:
              - dir-1
              - shared
            """,
        )
        _write_org_charter(
            pack_b,
            """
            required_directives:
              - shared
              - dir-2
            """,
        )
        _write_kittify_config(
            tmp_path,
            [
                {"name": "a", "local_path": str(pack_a)},
                {"name": "b", "local_path": str(pack_b)},
            ],
        )

        policy = load_org_charter_policies(tmp_path)

        assert policy.required_directives == ["dir-1", "shared", "dir-2"]

    def test_load_org_charter_policies_unset_env_var_propagates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``OrgPackEnvVarUnsetError`` must propagate out of ``load_org_charter_policies``.

        The narrowed ``except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError): raise``
        site in the function body guarantees this; this test kills the mutation
        that would widen the handler back to a bare ``except Exception: continue``.
        """
        from charter.offering.drg.org_pack_config import OrgPackEnvVarUnsetError  # noqa: PLC0415

        monkeypatch.delenv("SPEC_KITTY_ORG_CHARTER_UNSET_VAR", raising=False)
        _write_kittify_config(
            tmp_path,
            [{"name": "missing-env-pack", "local_path": "${SPEC_KITTY_ORG_CHARTER_UNSET_VAR}/pack"}],
        )

        with pytest.raises(OrgPackEnvVarUnsetError):
            load_org_charter_policies(tmp_path)

    def test_merge_governance_policies_dedup(self, tmp_path: Path) -> None:
        """Identical (field, value) policies are deduplicated to one."""
        pack_a = tmp_path / "packs" / "a"
        pack_b = tmp_path / "packs" / "b"
        _write_org_charter(
            pack_a,
            """
            governance_policies:
              - field: "autonomous_mode"
                value: "disallowed"
                enforcement: advisory
              - field: "another_field"
                value: "alpha"
                enforcement: advisory
            """,
        )
        _write_org_charter(
            pack_b,
            """
            governance_policies:
              - field: "autonomous_mode"
                value: "disallowed"
                enforcement: advisory
            """,
        )
        _write_kittify_config(
            tmp_path,
            [
                {"name": "a", "local_path": str(pack_a)},
                {"name": "b", "local_path": str(pack_b)},
            ],
        )

        policy = load_org_charter_policies(tmp_path)

        # autonomous_mode appears once even though both packs declare it.
        autonomous_entries = [gp for gp in policy.governance_policies if gp.field == "autonomous_mode"]
        assert len(autonomous_entries) == 1
        # The non-overlapping policy from pack-a survives.
        assert any(gp.field == "another_field" for gp in policy.governance_policies)


# ---------------------------------------------------------------------------
# T050: pre-fill behaviour
# ---------------------------------------------------------------------------


class TestApplyOrgCharterPreFill:
    def test_pre_fill_sets_missing_keys(self, tmp_path: Path) -> None:
        answers_path = tmp_path / "answers.yaml"

        messages = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults={"human_in_command": True},
            required_directives=[],
        )

        assert messages, "Expected at least one pre-fill message"
        yaml = YAML(typ="safe")
        loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
        assert loaded["human_in_command"] is True

    def test_pre_fill_does_not_overwrite(self, tmp_path: Path) -> None:
        """Existing project answer is preserved when org default differs."""
        answers_path = tmp_path / "answers.yaml"
        answers_path.write_text("human_in_command: false\n", encoding="utf-8")

        messages = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults={"human_in_command": True},
            required_directives=[],
        )

        assert messages == []  # nothing changed -> no message
        yaml = YAML(typ="safe")
        loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
        assert loaded["human_in_command"] is False  # project value preserved

    def test_pre_fill_required_directives_union(self, tmp_path: Path) -> None:
        """Existing selected_directives are augmented, not replaced."""
        answers_path = tmp_path / "answers.yaml"
        answers_path.write_text(
            "selected_directives:\n  - dir-a\n",
            encoding="utf-8",
        )

        messages = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults={},
            required_directives=["dir-b"],
        )

        assert messages, "Expected pre-selection message"
        yaml = YAML(typ="safe")
        loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
        assert loaded["selected_directives"] == ["dir-a", "dir-b"]

    def test_pre_fill_required_directives_no_duplicate(self, tmp_path: Path) -> None:
        """When org directive already present, no change occurs."""
        answers_path = tmp_path / "answers.yaml"
        answers_path.write_text(
            "selected_directives:\n  - dir-a\n",
            encoding="utf-8",
        )

        messages = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults={},
            required_directives=["dir-a"],
        )

        assert messages == []
        yaml = YAML(typ="safe")
        loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
        assert loaded["selected_directives"] == ["dir-a"]

    def test_pre_fill_idempotent_rerun(self, tmp_path: Path) -> None:
        """Second run is a no-op (no further writes, no further messages)."""
        answers_path = tmp_path / "answers.yaml"
        interview_defaults: dict[str, str | bool] = {"human_in_command": True}
        required_directives = ["dir-a"]

        first = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults=interview_defaults,
            required_directives=required_directives,
        )
        second = apply_org_charter_pre_fill_to_answers(
            answers_path=answers_path,
            interview_defaults=interview_defaults,
            required_directives=required_directives,
        )

        assert first, "First call should apply pre-fill"
        assert second == [], "Second call should be a no-op"

    def test_apply_org_charter_pre_fill_no_packs_is_noop(self, tmp_path: Path) -> None:
        """No packs configured -> empty list, no answers file created."""
        messages = apply_org_charter_pre_fill(tmp_path)

        assert messages == []
        assert not (tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml").exists()

    def test_apply_org_charter_pre_fill_with_pack(self, tmp_path: Path) -> None:
        """End-to-end: configured pack with charter -> answers.yaml written."""
        pack = tmp_path / "packs" / "security"
        _write_org_charter(
            pack,
            """
            interview_defaults:
              human_in_command: true
            required_directives:
              - sec-001
            """,
        )
        _write_kittify_config(tmp_path, [{"name": "security", "local_path": str(pack)}])

        messages = apply_org_charter_pre_fill(tmp_path)

        assert messages
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()
        yaml = YAML(typ="safe")
        loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
        assert loaded["human_in_command"] is True
        assert "sec-001" in loaded["selected_directives"]


# ---------------------------------------------------------------------------
# In-memory interview pre-fill (FR-026)
# ---------------------------------------------------------------------------


class _FakeInterview:
    """Minimal stand-in for CharterInterview with the two mutable surfaces used by the pre-fill helper."""

    def __init__(
        self,
        answers: dict[str, str] | None = None,
        selected_directives: list[str] | None = None,
    ) -> None:
        self.answers: dict[str, str] = dict(answers or {})
        self.selected_directives: list[str] = list(selected_directives or [])


class TestApplyOrgCharterToInterview:
    """In-memory pre-fill mutates the dataclass non-destructively (FR-026)."""

    def test_no_packs_returns_empty_messages_and_does_not_mutate(self, tmp_path: Path) -> None:
        interview = _FakeInterview(answers={"existing": "keep"})
        messages = apply_org_charter_to_interview(interview, tmp_path)
        assert messages == []
        assert interview.answers == {"existing": "keep"}
        assert interview.selected_directives == []

    def test_no_charter_in_packs_returns_empty(self, tmp_path: Path) -> None:
        pack = tmp_path / "packs" / "no-charter"
        pack.mkdir(parents=True)
        _write_kittify_config(tmp_path, [{"name": "no-charter", "local_path": str(pack)}])

        interview = _FakeInterview()
        messages = apply_org_charter_to_interview(interview, tmp_path)
        assert messages == []

    def test_fills_missing_answers_and_adds_required_directives(self, tmp_path: Path) -> None:
        pack = tmp_path / "packs" / "security"
        _write_org_charter(
            pack,
            """
            interview_defaults:
              human_in_command: true
              autonomous_mode: disallowed
            required_directives:
              - sec-001
              - sec-002
            """,
        )
        _write_kittify_config(tmp_path, [{"name": "security", "local_path": str(pack)}])

        interview = _FakeInterview()
        messages = apply_org_charter_to_interview(interview, tmp_path)

        assert interview.answers["human_in_command"] == "True"
        assert interview.answers["autonomous_mode"] == "disallowed"
        assert interview.selected_directives == ["sec-001", "sec-002"]
        assert any("Pre-filled 2 interview default" in m for m in messages)
        assert any("Pre-selected 2 directive" in m for m in messages)

    def test_existing_answers_are_preserved(self, tmp_path: Path) -> None:
        """An answer already set by the user is never overwritten by org defaults."""
        pack = tmp_path / "packs" / "security"
        _write_org_charter(
            pack,
            """
            interview_defaults:
              human_in_command: false
              autonomous_mode: disallowed
            """,
        )
        _write_kittify_config(tmp_path, [{"name": "security", "local_path": str(pack)}])

        interview = _FakeInterview(answers={"human_in_command": "True"})
        messages = apply_org_charter_to_interview(interview, tmp_path)

        # User's "True" survives; only the missing key was added.
        assert interview.answers["human_in_command"] == "True"
        assert interview.answers["autonomous_mode"] == "disallowed"
        assert any("Pre-filled 1 interview default" in m for m in messages)

    def test_existing_required_directives_not_duplicated(self, tmp_path: Path) -> None:
        pack = tmp_path / "packs" / "security"
        _write_org_charter(
            pack,
            """
            required_directives:
              - sec-001
              - sec-002
            """,
        )
        _write_kittify_config(tmp_path, [{"name": "security", "local_path": str(pack)}])

        interview = _FakeInterview(selected_directives=["sec-001", "DIRECTIVE_010"])
        messages = apply_org_charter_to_interview(interview, tmp_path)

        # sec-001 already present, only sec-002 is appended; order preserved.
        assert interview.selected_directives == ["sec-001", "DIRECTIVE_010", "sec-002"]
        assert any("Pre-selected 1 directive" in m for m in messages)

    def test_multi_pack_declaration_order_wins(self, tmp_path: Path) -> None:
        """When two packs declare the same key, the later pack's value wins (FR-006)."""
        pack_a = tmp_path / "packs" / "a"
        pack_b = tmp_path / "packs" / "b"
        _write_org_charter(
            pack_a,
            """
            interview_defaults:
              autonomous_mode: pack-a-value
            """,
        )
        _write_org_charter(
            pack_b,
            """
            interview_defaults:
              autonomous_mode: pack-b-value
            """,
        )
        _write_kittify_config(
            tmp_path,
            [
                {"name": "a", "local_path": str(pack_a)},
                {"name": "b", "local_path": str(pack_b)},
            ],
        )

        interview = _FakeInterview()
        messages = apply_org_charter_to_interview(interview, tmp_path)

        assert interview.answers["autonomous_mode"] == "pack-b-value"
        assert messages

    def test_idempotent_second_run_is_noop(self, tmp_path: Path) -> None:
        pack = tmp_path / "packs" / "security"
        _write_org_charter(
            pack,
            """
            interview_defaults:
              human_in_command: true
            required_directives:
              - sec-001
            """,
        )
        _write_kittify_config(tmp_path, [{"name": "security", "local_path": str(pack)}])

        interview = _FakeInterview()
        first = apply_org_charter_to_interview(interview, tmp_path)
        second = apply_org_charter_to_interview(interview, tmp_path)

        assert first
        assert second == []
        assert interview.answers == {"human_in_command": "True"}
        assert interview.selected_directives == ["sec-001"]


# ---------------------------------------------------------------------------
# T050: charter context JSON block
# ---------------------------------------------------------------------------


class TestContextJsonOrgCharter:
    def test_context_json_org_charter_absent(self, tmp_path: Path) -> None:
        """No org roots -> {present: false, packs: []}."""
        block = load_org_charter_json_block(None)

        assert block == {"present": False, "packs": []}

        block_empty = load_org_charter_json_block([])
        assert block_empty == {"present": False, "packs": []}

    def test_context_json_org_charter_present(self, tmp_path: Path) -> None:
        """Org root with org-charter.yaml -> present=true with pack entry."""
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            org_name: "Acme Security"
            required_directives:
              - sec-001
            governance_policies:
              - field: "autonomous_mode"
                value: "disallowed"
                enforcement: advisory
            """,
        )

        block = load_org_charter_json_block([pack])

        assert block["present"] is True
        assert len(block["packs"]) == 1
        entry = block["packs"][0]
        assert entry["pack_name"] == "Acme Security"
        assert "sec-001" in entry["required_directives"]
        assert entry["governance_policies"]
        assert entry["governance_policies"][0]["source"] == "org"


# ---------------------------------------------------------------------------
# Schema model surface
# ---------------------------------------------------------------------------


class TestOrgCharterPolicyModel:
    def test_empty_policy_is_valid(self) -> None:
        policy = OrgCharterPolicy()
        assert policy.schema_version == 2  # bumped by #3732 (charter_pack_id)
        assert policy.extends is None
        assert policy.org_name is None
        assert policy.interview_defaults == {}
        assert policy.required_directives == []
        assert policy.governance_policies == []

    def test_governance_policy_defaults_to_advisory(self) -> None:
        gp = GovernancePolicy(field="x", value=True)
        assert gp.enforcement == "advisory"

    def test_governance_policy_accepts_bool_value(self) -> None:
        gp = GovernancePolicy(field="human_in_command", value=True)
        assert gp.value is True

    def test_unknown_field_rejected(self) -> None:
        """extra='forbid' on the model — unknown keys raise ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrgCharterPolicy.model_validate({"unknown_field": "x"})

    def test_schema_version_accepts_int(self) -> None:
        """WP09 T053: ``schema_version`` is an ``int`` on the model."""
        policy = OrgCharterPolicy.model_validate({"schema_version": 1})
        assert policy.schema_version == 1
        assert isinstance(policy.schema_version, int)

    def test_schema_version_coerces_string(self) -> None:
        """WP09 T053: existing YAML stores ``"1"``; the validator coerces to int."""
        policy = OrgCharterPolicy.model_validate({"schema_version": "1"})
        assert policy.schema_version == 1
        assert isinstance(policy.schema_version, int)

    def test_schema_version_rejects_non_numeric_string(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OrgCharterPolicy.model_validate({"schema_version": "not-a-number"})

    def test_extends_defaults_to_none(self) -> None:
        """WP09 T054: ``extends`` is optional and defaults to ``None``."""
        policy = OrgCharterPolicy()
        assert policy.extends is None

    def test_extends_accepts_string(self) -> None:
        policy = OrgCharterPolicy.model_validate({"extends": "base-pack"})
        assert policy.extends == "base-pack"


# ---------------------------------------------------------------------------
# WP09 T060: extends: chain resolution, merge semantics, error classes
# ---------------------------------------------------------------------------


def _policy(name: str | None = None, **kwargs: object) -> OrgCharterPolicy:
    """Convenience: build an :class:`OrgCharterPolicy` for chain tests.

    ``name`` is unused (the pack-set key is set by the caller); kwargs
    flow straight into ``OrgCharterPolicy.model_validate`` so test
    intent stays close to the raw field shape.
    """
    return OrgCharterPolicy.model_validate(kwargs)


class TestResolveChain:
    def test_single_pack_no_extends(self) -> None:
        pack_set = {"A": _policy(required_directives=["a"])}
        chain = _resolve_chain("A", pack_set)
        assert len(chain) == 1
        assert chain[0].required_directives == ["a"]

    def test_simple_extends_pair(self) -> None:
        pack_set = {
            "A": _policy(required_directives=["a"]),
            "B": _policy(extends="A", required_directives=["b"]),
        }
        chain = _resolve_chain("B", pack_set)
        # Base-first ordering: A then B.
        assert [p.required_directives for p in chain] == [["a"], ["b"]]

    def test_depth_two_chain(self) -> None:
        pack_set = {
            "A": _policy(required_directives=["a"]),
            "B": _policy(extends="A", required_directives=["b"]),
            "C": _policy(extends="B", required_directives=["c"]),
        }
        chain = _resolve_chain("C", pack_set)
        assert [p.required_directives for p in chain] == [["a"], ["b"], ["c"]]

    def test_cycle_two_packs(self) -> None:
        pack_set = {
            "A": _policy(extends="B", required_directives=["a"]),
            "B": _policy(extends="A", required_directives=["b"]),
        }
        with pytest.raises(OrgCharterCycleError) as exc:
            _resolve_chain("A", pack_set)
        # Cycle path includes the repeated node so operators see the loop.
        assert "A" in exc.value.cycle_path
        assert "B" in exc.value.cycle_path
        assert exc.value.cycle_path[-1] == exc.value.cycle_path[0] or len(exc.value.cycle_path) >= 2

    def test_self_reference(self) -> None:
        pack_set = {"A": _policy(extends="A", required_directives=["a"])}
        with pytest.raises(OrgCharterCycleError) as exc:
            _resolve_chain("A", pack_set)
        assert exc.value.cycle_path == ["A", "A"]

    def test_missing_base_raises(self) -> None:
        pack_set = {
            "B": _policy(extends="nonexistent", required_directives=["b"]),
        }
        with pytest.raises(OrgCharterExtensionError) as exc:
            _resolve_chain("B", pack_set)
        assert exc.value.missing_pack == "nonexistent"
        assert exc.value.chain == ["B"]


class TestMergeChain:
    def test_union_required_directives(self) -> None:
        chain = [
            _policy(required_directives=["a", "b"]),
            _policy(required_directives=["b", "c"]),
        ]
        merged = _merge_chain(chain)
        assert merged.required_directives == ["a", "b", "c"]

    def test_union_required_toolguides(self) -> None:
        chain = [
            _policy(required_toolguides=["tg-1"]),
            _policy(required_toolguides=["tg-2"]),
        ]
        merged = _merge_chain(chain)
        assert merged.required_toolguides == ["tg-1", "tg-2"]

    def test_interview_defaults_per_key_replacement(self) -> None:
        chain = [
            _policy(interview_defaults={"foo": "base", "bar": "base"}),
            _policy(interview_defaults={"foo": "overlay"}),
        ]
        merged = _merge_chain(chain)
        # Overlay key wins; unmentioned key inherits from base.
        assert merged.interview_defaults == {"foo": "overlay", "bar": "base"}

    def test_merged_result_has_no_extends(self) -> None:
        chain = [_policy(extends=None), _policy(extends="base-name")]
        merged = _merge_chain(chain)
        assert merged.extends is None

    def test_schema_version_mismatch_raises(self) -> None:
        chain = [
            _policy(schema_version=2, required_directives=["a"]),
            _policy(schema_version=3, required_directives=["b"]),
        ]
        with pytest.raises(ValueError, match="schema_version mismatch"):
            _merge_chain(chain)

    def test_schema_versions_1_and_2_share_a_chain(self) -> None:
        """#3732: version 2 only adds the retired-field rejection, so 1 and 2 may mix."""
        chain = [
            _policy(schema_version=1, required_directives=["a"]),
            _policy(schema_version=2, required_directives=["b"]),
        ]
        merged = _merge_chain(chain)
        assert merged.schema_version == 2
        assert merged.required_directives == ["a", "b"]

    def test_empty_chain_returns_default_policy(self) -> None:
        merged = _merge_chain([])
        assert merged.schema_version == 2
        assert merged.required_directives == []

    def test_org_name_last_non_empty_wins(self) -> None:
        chain = [
            _policy(org_name="Base"),
            _policy(org_name=None),
            _policy(org_name="Overlay"),
        ]
        merged = _merge_chain(chain)
        assert merged.org_name == "Overlay"


class TestFoldPolicies:
    """Direct coverage of the extracted ``_fold_policies`` (#1894).

    Pins the schema_version parameter in both modes, proving the strict
    vs lenient delta is now an explicit decision rather than silent drift.
    """

    def test_empty_returns_default_policy(self) -> None:
        assert _fold_policies([]).schema_version == 2

    def test_strict_matching_versions_carry_version(self) -> None:
        merged = _fold_policies(
            [_policy(schema_version=2), _policy(schema_version=2)],
            strict_schema_version=True,
        )
        assert merged.schema_version == 2

    def test_strict_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="schema_version mismatch"):
            _fold_policies(
                [_policy(schema_version=1), _policy(schema_version=3)],
                strict_schema_version=True,
            )

    def test_lenient_last_truthy_wins_no_raise(self) -> None:
        # Lenient mode does NOT enforce equality: differing versions fold,
        # last truthy wins (the legacy / cross-pack behaviour — #1894 NOTE).
        merged = _fold_policies(
            [_policy(schema_version=1), _policy(schema_version=2)],
            strict_schema_version=False,
        )
        assert merged.schema_version == 2

    def test_lenient_default_is_lenient(self) -> None:
        # Default parameter value preserves the legacy lenient semantics.
        merged = _fold_policies(
            [_policy(schema_version=1), _policy(schema_version=3)],
        )
        assert merged.schema_version == 3

    def test_fold_unions_and_dedups_like_sites(self) -> None:
        merged = _fold_policies(
            [
                _policy(
                    required_directives=["a", "b"],
                    interview_defaults={"foo": "base", "bar": "base"},
                ),
                _policy(
                    required_directives=["b", "c"],
                    interview_defaults={"foo": "overlay"},
                ),
            ]
        )
        assert merged.required_directives == ["a", "b", "c"]
        assert merged.interview_defaults == {"foo": "overlay", "bar": "base"}
        assert merged.extends is None


class TestLegacyPathFoldParity:
    """FR parity: the legacy ``config.yaml`` path is lenient on schema_version.

    Proves the legacy loader does NOT raise on a version mismatch across
    packs (the pre-extraction None-guard behaviour), distinct from the
    strict extends-chain path — the latent #1894 inconsistency, preserved.
    """

    def test_legacy_path_lenient_on_version_mismatch(self, tmp_path: Path) -> None:
        pack_a = tmp_path / "packs" / "a"
        pack_b = tmp_path / "packs" / "b"
        _write_org_charter(pack_a, "schema_version: 1\nrequired_directives: [x]\n")
        _write_org_charter(pack_b, "schema_version: 2\nrequired_directives: [y]\n")
        _write_kittify_config(
            tmp_path,
            [
                {"name": "a", "local_path": str(pack_a)},
                {"name": "b", "local_path": str(pack_b)},
            ],
        )

        # No PackContext → legacy config.yaml path. Differing versions
        # must NOT raise; last truthy (2) wins, directives union.
        merged = load_org_charter_policies(tmp_path)
        assert merged.schema_version == 2
        assert merged.required_directives == ["x", "y"]


class TestBuildPackSet:
    def test_indexes_packs_by_directory_name(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        pack_a = tmp_path / "corp-baseline"
        _write_org_charter(
            pack_a,
            """
            schema_version: 1
            org_name: "Corp"
            required_directives:
              - core-001
            """,
        )
        pack_b = tmp_path / "team-overlay"
        _write_org_charter(
            pack_b,
            """
            schema_version: 1
            extends: "corp-baseline"
            required_directives:
              - team-001
            """,
        )

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(pack_a, pack_b),
            org_pack_names=("corp-baseline", "team-overlay"),
            repo_root=tmp_path,
        )

        pack_set = _build_pack_set(ctx)
        assert set(pack_set.keys()) == {"corp-baseline", "team-overlay"}
        assert pack_set["team-overlay"].extends == "corp-baseline"

    def test_skips_packs_without_org_charter(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        # First pack ships an org-charter.yaml; second is bare.
        pack_a = tmp_path / "alpha"
        _write_org_charter(pack_a, "schema_version: 1\n")
        pack_b = tmp_path / "bravo"
        pack_b.mkdir(parents=True)

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(pack_a, pack_b),
            org_pack_names=("alpha", "bravo"),
            repo_root=tmp_path,
        )

        pack_set = _build_pack_set(ctx)
        assert set(pack_set.keys()) == {"alpha"}


class TestLoadOrgCharterPoliciesWithPackContext:
    def test_extends_chain_merges_via_pack_context(self, tmp_path: Path) -> None:
        """WP09 T061-sig + T062-chain: ``PackContext`` drives chain resolution."""
        from charter.activation.pack_context import PackContext

        base = tmp_path / "base-pack"
        _write_org_charter(
            base,
            """
            schema_version: 1
            required_directives:
              - base-001
            interview_defaults:
              human_in_command: true
              security_review: "Required"
            """,
        )
        overlay = tmp_path / "overlay-pack"
        _write_org_charter(
            overlay,
            """
            schema_version: 1
            extends: "base-pack"
            required_directives:
              - overlay-001
            interview_defaults:
              security_review: "Optional"
            """,
        )

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(base, overlay),
            org_pack_names=("base-pack", "overlay-pack"),
            repo_root=tmp_path,
        )

        merged = load_org_charter_policies(tmp_path, pack_context=ctx)

        assert "base-001" in merged.required_directives
        assert "overlay-001" in merged.required_directives
        # Per-key replacement: overlay wins for security_review,
        # base preserved for human_in_command.
        assert merged.interview_defaults["security_review"] == "Optional"
        assert merged.interview_defaults["human_in_command"] is True

    def test_backward_compat_pack_without_extends(self, tmp_path: Path) -> None:
        """Packs without ``extends:`` still merge as before (FR-001 backward compat)."""
        from charter.activation.pack_context import PackContext

        pack_a = tmp_path / "flat-a"
        _write_org_charter(
            pack_a,
            """
            schema_version: 1
            required_directives:
              - a-001
            """,
        )
        pack_b = tmp_path / "flat-b"
        _write_org_charter(
            pack_b,
            """
            schema_version: 1
            required_directives:
              - b-001
            """,
        )

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(pack_a, pack_b),
            org_pack_names=("flat-a", "flat-b"),
            repo_root=tmp_path,
        )

        merged = load_org_charter_policies(tmp_path, pack_context=ctx)
        assert merged.required_directives == ["a-001", "b-001"]

    def test_empty_pack_context_returns_default(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(),
            org_pack_names=(),
            repo_root=tmp_path,
        )
        merged = load_org_charter_policies(tmp_path, pack_context=ctx)
        assert merged == OrgCharterPolicy()

    def test_cycle_propagates(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        pack_a = tmp_path / "A"
        _write_org_charter(
            pack_a,
            """
            schema_version: 1
            extends: "B"
            """,
        )
        pack_b = tmp_path / "B"
        _write_org_charter(
            pack_b,
            """
            schema_version: 1
            extends: "A"
            """,
        )

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(pack_a, pack_b),
            org_pack_names=("A", "B"),
            repo_root=tmp_path,
        )
        with pytest.raises(OrgCharterCycleError):
            load_org_charter_policies(tmp_path, pack_context=ctx)

    def test_missing_base_propagates(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        pack = tmp_path / "child"
        _write_org_charter(
            pack,
            """
            schema_version: 1
            extends: "ghost-pack"
            """,
        )
        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(pack,),
            org_pack_names=("child",),
            repo_root=tmp_path,
        )
        with pytest.raises(OrgCharterExtensionError):
            load_org_charter_policies(tmp_path, pack_context=ctx)

    def test_schema_version_mismatch_propagates(self, tmp_path: Path) -> None:
        from charter.activation.pack_context import PackContext

        base = tmp_path / "base"
        _write_org_charter(
            base,
            """
            schema_version: 2
            """,
        )
        overlay = tmp_path / "overlay"
        _write_org_charter(
            overlay,
            """
            schema_version: 3
            extends: "base"
            """,
        )

        ctx = PackContext(
            activated_kinds=frozenset({"directives"}),
            activated_mission_types=frozenset({"software-dev"}),
            pack_roots=(base, overlay),
            org_pack_names=("base", "overlay"),
            repo_root=tmp_path,
        )
        with pytest.raises(ValueError, match="schema_version mismatch"):
            load_org_charter_policies(tmp_path, pack_context=ctx)


class TestOrgCharterErrorClasses:
    def test_cycle_error_includes_path(self) -> None:
        err = OrgCharterCycleError(["A", "B", "A"])
        assert err.cycle_path == ["A", "B", "A"]
        assert "A → B → A" in str(err)

    def test_extension_error_includes_chain_and_missing(self) -> None:
        err = OrgCharterExtensionError("ghost", ["A", "B"])
        assert err.missing_pack == "ghost"
        assert err.chain == ["A", "B"]
        assert "ghost" in str(err)
        assert "A → B" in str(err)
