"""T023 (WP04, #2532) — focused unit tests for the extracted leaf/pure seams.

Each seam module is imported from its NEW home (not re-exported through
``charter.activation.context``) so these tests pin the seam itself, independent of the
FR-009 preserved-surface re-export. Complements
``tests/charter/test_context_bootstrap_markers.py`` (which proves the composed
end-to-end behaviour is unchanged) by exercising each moved unit directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation._catalog_miss import CatalogMissCause
from charter.activation.charter_md_parsing import _extract_policy_summary, _find_section_start
from charter.activation.context_renderers.artifact_bodies import (
    _format_full_artifact_payload_body,
    _format_inline_agent_profile_body,
    _format_inline_directive_body,
    _format_inline_paradigm_body,
    _format_inline_procedure_body,
    _format_inline_step_contract_body,
    _format_inline_styleguide_body,
    _format_inline_tactic_body,
    _format_inline_toolguide_body,
    _format_profile_directive_code,
    _jsonable_artifact_value,
)
from charter.activation.context_renderers.catalog_diagnosis import (
    _available_catalog_ids,
    _diagnose_catalog_miss,
)
from charter.activation.context_state import (
    KITTIFY_DIRNAME,
    _MIN_EFFECTIVE_DEPTH,
    _ContextStateBundle,
    _load_state,
    _mark_action_loaded,
    _prepare_context_state,
    _write_state,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]


# ---------------------------------------------------------------------------
# catalog_diagnosis.py
# ---------------------------------------------------------------------------


class _ListAllRepo:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def list_all(self) -> list[object]:
        return [type("Item", (), {"id": i})() for i in self._ids]


class _ScopeFilteredRepo:
    scope_filtered_ids = frozenset({"filtered-artifact"})
    _active_languages = ["python"]

    def list_all(self) -> list[object]:
        return []


class TestAvailableCatalogIds:
    def test_none_repository_returns_empty(self) -> None:
        assert _available_catalog_ids(None) == []

    def test_list_all_ids_are_returned(self) -> None:
        repo = _ListAllRepo(["alpha", "beta"])
        assert _available_catalog_ids(repo) == ["alpha", "beta"]

    def test_items_dict_fallback(self) -> None:
        class _StubRepo:
            _items = {"gamma": object(), "delta": object()}

        ids = _available_catalog_ids(_StubRepo())
        assert set(ids) == {"gamma", "delta"}

    def test_lister_exception_falls_back_gracefully(self) -> None:
        class _RaisingRepo:
            def list_all(self) -> list[object]:
                raise RuntimeError("boom")

            _items: dict[str, object] = {}

        assert _available_catalog_ids(_RaisingRepo()) == []


class TestDiagnoseCatalogMiss:
    def test_missing_artifact_when_no_close_match(self) -> None:
        repo = _ListAllRepo(["completely-unrelated-name"])
        diagnosis = _diagnose_catalog_miss("zzz-nonexistent-zzz", repo)
        assert diagnosis.cause is CatalogMissCause.MISSING_ARTIFACT

    def test_scope_filtered_takes_precedence_over_fuzzy_match(self) -> None:
        diagnosis = _diagnose_catalog_miss("filtered-artifact", _ScopeFilteredRepo())
        assert diagnosis.cause is CatalogMissCause.SCOPE_FILTERED

    def test_none_repository_is_missing_artifact(self) -> None:
        diagnosis = _diagnose_catalog_miss("anything", None)
        assert diagnosis.cause is CatalogMissCause.MISSING_ARTIFACT


# ---------------------------------------------------------------------------
# artifact_bodies.py
# ---------------------------------------------------------------------------


class TestFormatProfileDirectiveCode:
    def test_bare_numeral_normalises_to_canonical_form(self) -> None:
        assert _format_profile_directive_code("10") == "DIRECTIVE_010"

    def test_canonical_form_passes_through(self) -> None:
        assert _format_profile_directive_code("DIRECTIVE_010") == "DIRECTIVE_010"

    def test_non_numeric_code_returned_verbatim(self) -> None:
        assert _format_profile_directive_code("weird-code") == "weird-code"


class TestJsonableArtifactValue:
    def test_primitives_pass_through(self) -> None:
        assert _jsonable_artifact_value("x") == "x"
        assert _jsonable_artifact_value(1) == 1
        assert _jsonable_artifact_value(None) is None

    def test_set_is_sorted_deterministically(self) -> None:
        result = _jsonable_artifact_value({"b", "a", "c"})
        assert result == ["a", "b", "c"]

    def test_nested_dict_drops_none_values(self) -> None:
        result = _jsonable_artifact_value({"a": 1, "b": None})
        assert result == {"a": 1}

    def test_object_with_dunder_dict_skips_private_attrs(self) -> None:
        class _Obj:
            def __init__(self) -> None:
                self.public = "visible"
                self._private = "hidden"

        result = _jsonable_artifact_value(_Obj())
        assert result == {"public": "visible"}

    def test_full_payload_body_renders_json_lines(self) -> None:
        class _Artifact:
            def __init__(self) -> None:
                self.id = "DIRECTIVE_001"

        lines = _format_full_artifact_payload_body(_Artifact())
        assert lines[0] == "    Full artifact:"
        # The rest round-trips as valid JSON once the fixed indent is stripped.
        body = "\n".join(line.removeprefix("      ") for line in lines[1:])
        assert json.loads(body) == {"id": "DIRECTIVE_001"}

    def test_full_payload_body_empty_for_non_dict_payload(self) -> None:
        assert _format_full_artifact_payload_body("just-a-string") == []


class TestFormatInlineBodies:
    """Each formatter degrades gracefully when its attributes are absent."""

    def test_directive_body_renders_populated_fields(self) -> None:
        directive = type(
            "D",
            (),
            {
                "intent": "Keep boundaries clean",
                "scope": "All modules",
                "procedures": ["Do X"],
                "integrity_rules": ["Never Y"],
                "validation_criteria": ["Check Z"],
            },
        )()
        lines = _format_inline_directive_body(directive)
        assert "    Intent: Keep boundaries clean" in lines
        assert "      - Do X" in lines

    def test_directive_body_empty_object_yields_no_lines(self) -> None:
        assert _format_inline_directive_body(object()) == []

    def test_styleguide_body_renders_scope_enum_value(self) -> None:
        styleguide = type(
            "S",
            (),
            {"title": "Style", "scope": type("Scope", (), {"value": "python"})(), "principles": ["p1"]},
        )()
        lines = _format_inline_styleguide_body(styleguide)
        assert "    Scope: python" in lines

    def test_paradigm_body(self) -> None:
        paradigm = type("P", (), {"name": "DDD", "summary": "Domain modeling"})()
        assert _format_inline_paradigm_body(paradigm) == [
            "    Name: DDD",
            "    Summary: Domain modeling",
        ]

    def test_tactic_body_with_steps(self) -> None:
        step = type("Step", (), {"title": "Step one"})()
        tactic = type("T", (), {"name": "TDD", "purpose": "quality", "steps": [step]})()
        lines = _format_inline_tactic_body(tactic)
        assert "      - Step one" in lines

    def test_toolguide_body(self) -> None:
        toolguide = type("TG", (), {"title": "Ruff", "tool": "ruff", "summary": "lint"})()
        assert _format_inline_toolguide_body(toolguide) == [
            "    Title: Ruff",
            "    Tool: ruff",
            "    Summary: lint",
        ]

    def test_procedure_body_with_entry_exit(self) -> None:
        procedure = type(
            "Proc",
            (),
            {
                "name": "Onboard",
                "purpose": "bring agent up to speed",
                "entry_condition": "new agent",
                "exit_condition": "profile loaded",
                "steps": [],
            },
        )()
        lines = _format_inline_procedure_body(procedure)
        assert "    Entry condition: new agent" in lines
        assert "    Exit condition: profile loaded" in lines

    def test_agent_profile_body_renders_roles(self) -> None:
        role = type("Role", (), {"value": "implementer"})()
        profile = type("AP", (), {"name": "pedro", "purpose": "implement", "roles": [role]})()
        lines = _format_inline_agent_profile_body(profile)
        assert "    Roles: implementer" in lines

    def test_step_contract_body_renders_step_with_explicit_id(self) -> None:
        with_id = type("Step", (), {"id": "T001", "description": "do thing"})()
        contract = type(
            "Contract",
            (),
            {"action": "implement", "mission": "software-dev", "steps": [with_id]},
        )()
        lines = _format_inline_step_contract_body(contract)
        assert "    Action: implement" in lines
        assert "    Mission: software-dev" in lines
        assert "      - T001: do thing" in lines

    def test_step_contract_body_falls_back_to_bare_description_without_id(self) -> None:
        without_id = type("Step", (), {"description": "do other thing"})()
        contract = type(
            "Contract", (), {"action": "review", "mission": "software-dev", "steps": [without_id]}
        )()
        lines = _format_inline_step_contract_body(contract)
        assert "      - do other thing" in lines


# ---------------------------------------------------------------------------
# charter_md_parsing.py
# ---------------------------------------------------------------------------


class TestExtractPolicySummary:
    def test_extracts_bullets_under_policy_summary_heading(self) -> None:
        content = "# Charter\n\n## Policy Summary\n\n- Intent: ship value\n- Testing: pytest\n\n## Next Section\n- not included\n"
        assert _extract_policy_summary(content) == ["Intent: ship value", "Testing: pytest"]

    def test_falls_back_to_first_bullets_when_heading_absent(self) -> None:
        content = "# Charter\n\n- loose bullet one\n- loose bullet two\n"
        assert _extract_policy_summary(content) == ["loose bullet one", "loose bullet two"]

    def test_fallback_caps_at_eight_items(self) -> None:
        content = "\n".join(f"- item {i}" for i in range(12))
        assert _extract_policy_summary(content) == [f"item {i}" for i in range(8)]


class TestFindSectionStart:
    def test_returns_index_of_matching_heading(self) -> None:
        lines = ["# Charter", "", "## Policy Summary", "- x"]
        assert _find_section_start(lines, "## Policy Summary") == 2

    def test_returns_none_when_heading_absent(self) -> None:
        assert _find_section_start(["# Charter"], "## Policy Summary") is None


# ---------------------------------------------------------------------------
# context_state.py
# ---------------------------------------------------------------------------


class TestContextStateBookkeeping:
    def test_load_state_defaults_when_missing(self, tmp_path: Path) -> None:
        state = _load_state(tmp_path / "context-state.json")
        assert state == {"schema_version": "1.0.0", "actions": {}}

    def test_load_state_defaults_on_corrupt_json(self, tmp_path: Path) -> None:
        path = tmp_path / "context-state.json"
        path.write_text("{not json", encoding="utf-8")
        assert _load_state(path) == {"schema_version": "1.0.0", "actions": {}}

    def test_write_then_load_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "sub" / "context-state.json"
        state = {"schema_version": "1.0.0", "actions": {"implement": "2026-01-01T00:00:00Z"}}
        _write_state(path, state)
        assert _load_state(path) == state

    def test_mark_action_loaded_persists_timestamp(self, tmp_path: Path) -> None:
        path = tmp_path / "context-state.json"
        state: dict[str, object] = {"schema_version": "1.0.0", "actions": {}}
        _mark_action_loaded(state, path, "implement")
        reloaded = _load_state(path)
        actions = reloaded["actions"]
        assert isinstance(actions, dict)
        assert "implement" in actions

    def test_mark_action_loaded_matches_pre_migration_golden_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC-004 persisted-artifact golden (kernel-clock-single-door WP07).

        Captured from the PRE-migration tree (before ``context_state.py``
        routed onto the door): under a frozen instant of
        ``2026-11-02T14:15:16.654321+00:00``, the raw
        ``datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`` call this
        function used to make persisted the literal timestamp
        ``2026-11-02T14:15:16Z`` into ``context-state.json``. This test
        freezes the door's ``DEFAULT_CLOCK`` (the seam the migrated call now
        reads through via ``now_utc_stamp()``) to that exact instant and
        asserts the persisted bytes this WP's migrated code writes are
        byte-identical to that pre-migration golden.
        """
        import kernel.clock as clock_module
        from kernel.clock import UTC, FrozenClock, datetime as door_datetime

        fixed = door_datetime(2026, 11, 2, 14, 15, 16, 654321, tzinfo=UTC)
        monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=fixed))

        path = tmp_path / "context-state.json"
        state: dict[str, object] = {"schema_version": "1.0.0", "actions": {}}
        _mark_action_loaded(state, path, "implement")

        reloaded = _load_state(path)
        actions = reloaded["actions"]
        assert isinstance(actions, dict)
        assert actions["implement"] == "2026-11-02T14:15:16Z"

    def test_prepare_context_state_first_load_uses_min_effective_depth(
        self, tmp_path: Path
    ) -> None:
        bundle = _prepare_context_state(tmp_path, "implement", None)
        assert isinstance(bundle, _ContextStateBundle)
        assert bundle.first_load is True
        assert bundle.effective_depth == _MIN_EFFECTIVE_DEPTH
        assert bundle.state_path == tmp_path / KITTIFY_DIRNAME / "charter" / "context-state.json"

    def test_prepare_context_state_explicit_depth_wins(self, tmp_path: Path) -> None:
        bundle = _prepare_context_state(tmp_path, "implement", 5)
        assert bundle.effective_depth == 5

    def test_prepare_context_state_repeat_load_uses_depth_one(self, tmp_path: Path) -> None:
        state_path = tmp_path / KITTIFY_DIRNAME / "charter" / "context-state.json"
        _write_state(state_path, {"schema_version": "1.0.0", "actions": {"implement": "x"}})
        bundle = _prepare_context_state(tmp_path, "implement", None)
        assert bundle.first_load is False
        assert bundle.effective_depth == 1
