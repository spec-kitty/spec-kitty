"""Tests for WP06/T027+T029: spec-kitty charter list command.

Covers FR-004, FR-005, FR-006, FR-007:
- All-None state: all 9 rows show built-in message
- Explicit activations: correct IDs displayed
- --show-available flag: third column with available-but-not-activated items
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]

#: All 9 kind names in display order.
_ALL_KINDS = [
    "directive",
    "tactic",
    "styleguide",
    "toolguide",
    "paradigm",
    "procedure",
    "agent-profile",
    "mission-step-contract",
    "mission-type",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_project_root(tmp_path: Path) -> Path:
    """A project with empty config.yaml (no activation keys other than the
    provisioned mission-type authority).

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def project_with_directive(tmp_path: Path) -> Path:
    """A project with activated_directives: [python-style-guide] in config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config_data = (
        "activated_directives:\n  - python-style-guide\n"
        "mission_type_activations:\n  - software-dev\n"
    )
    (kittify / "config.yaml").write_text(config_data, encoding="utf-8")
    return tmp_path


def _invoke_list(project_root: Path, *args: str) -> Result:
    """Invoke charter list with --repo-root."""
    return runner.invoke(
        charter_app,
        ["list", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# test_list_all_none_shows_builtin_message
# ---------------------------------------------------------------------------


class TestListAllNone:
    def test_all_none_shows_builtin_message(self, empty_project_root: Path) -> None:
        """All 9 rows show '(All built-ins' when no explicit activation keys exist."""
        result = _invoke_list(empty_project_root)
        assert result.exit_code == 0, result.output
        assert "All built-ins" in result.output

    def test_all_nine_kinds_present_in_output(self, empty_project_root: Path) -> None:
        """All 9 kind names appear in the table."""
        result = _invoke_list(empty_project_root)
        assert result.exit_code == 0, result.output
        for kind in _ALL_KINDS:
            assert kind in result.output, f"Expected kind '{kind}' in output"

    def test_table_title_present(self, empty_project_root: Path) -> None:
        """The table title 'Charter Activation State' appears in output."""
        result = _invoke_list(empty_project_root)
        assert result.exit_code == 0, result.output
        assert "Charter Activation State" in result.output


# ---------------------------------------------------------------------------
# test_list_shows_explicit_activations
# ---------------------------------------------------------------------------


class TestListExplicitActivations:
    def test_shows_activated_directive(self, project_with_directive: Path) -> None:
        """Row for directive shows python-style-guide when it's in activated_directives."""
        result = _invoke_list(project_with_directive)
        assert result.exit_code == 0, result.output
        assert "python-style-guide" in result.output

    def test_empty_set_shows_restriction_message(self, tmp_path: Path) -> None:
        """A kind with an empty list shows the explicit-restriction message."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        # Empty list for directive → explicit restriction
        (kittify / "config.yaml").write_text(
            "activated_directives: []\nmission_type_activations:\n  - software-dev\n",
            encoding="utf-8",
        )
        result = _invoke_list(tmp_path)
        assert result.exit_code == 0, result.output
        assert "explicit restriction" in result.output.lower() or "Nothing activated" in result.output


# ---------------------------------------------------------------------------
# test_list_show_available_includes_doctrine_entries
# ---------------------------------------------------------------------------


class TestListShowAvailable:
    def test_show_available_adds_third_column(self, empty_project_root: Path) -> None:
        """--show-available causes a third column to appear."""
        result = _invoke_list(empty_project_root, "--show-available")
        assert result.exit_code == 0, result.output
        assert "Available (not activated)" in result.output

    def test_show_available_without_flag_has_no_third_column(
        self, empty_project_root: Path
    ) -> None:
        """Without --show-available, the third column is absent."""
        result = _invoke_list(empty_project_root)
        assert result.exit_code == 0, result.output
        assert "Available (not activated)" not in result.output

    @pytest.mark.doctrine
    def test_show_available_lists_doctrine_entries(self, empty_project_root: Path) -> None:
        """--show-available calls list_available and shows doctrine entries not activated."""
        # Mock list_available to return a known set
        with patch(
            "charter.activation.pack_manager.ActiveCharterManager.list_available",
            return_value=frozenset(["doctrine-entry-1", "doctrine-entry-2"]),
        ):
            result = _invoke_list(empty_project_root, "--show-available")
        assert result.exit_code == 0, result.output
        # Doctrine entries should appear in the "Available" column
        assert "doctrine-entry-1" in result.output or "doctrine-entry-2" in result.output

    def test_show_available_hides_already_activated(self, project_with_directive: Path) -> None:
        """Already-activated artifacts don't appear in the 'Available' column."""
        with patch(
            "charter.activation.pack_manager.ActiveCharterManager.list_available",
            return_value=frozenset(["python-style-guide", "other-directive"]),
        ):
            result = _invoke_list(project_with_directive, "--show-available")
        assert result.exit_code == 0, result.output
        # other-directive is available and not activated → should appear in available column
        output = result.output
        assert "other-directive" in output


# ---------------------------------------------------------------------------
# charter list --json (issue #3839)
# ---------------------------------------------------------------------------
#
# The human table already renders already-typed, already-structured data from
# ``ActiveCharterManager`` / ``discover_templates``. ``--json`` reuses the exact
# same manager calls and serializes the same rows -- not a re-derivation. The
# error envelope reuses ``_emit_error`` from ``_common.py`` verbatim: shape is
# ``{"result": "error", "success": false, "error": message}``.


class TestListJson:
    def test_json_flag_emits_valid_json(self, empty_project_root: Path) -> None:
        """``--json`` output parses and carries a "success" envelope with every
        canonical kind (derived from ``CHARTER_KIND_TOKENS``, not a re-declared
        list -- mirrors ``TestKindOrderDerivedFromCanonical`` in
        ``test_charter_list.py``), each with a null ``activated`` (all-built-ins
        state) -- except ``mission-type``, which ``empty_project_root`` seeds
        with an explicit ``mission_type_activations`` (WP04, C-A1: the
        provisioned charter is the sole mission-type activation authority)."""
        from charter.activation.kind_vocabulary import CHARTER_KIND_TOKENS

        result = _invoke_list(empty_project_root, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["result"] == "success", payload
        kinds = {row["kind"]: row for row in payload["kinds"]}
        assert set(kinds) == set(CHARTER_KIND_TOKENS)
        for kind in CHARTER_KIND_TOKENS:
            if kind == "mission-type":
                assert kinds[kind]["activated"] == ["software-dev"], kinds[kind]
                continue
            assert kinds[kind]["activated"] is None, kinds[kind]

    def test_json_no_table_markup_leaks(self, empty_project_root: Path) -> None:
        """``--json`` output must be pure JSON -- no Rich table markup."""
        result = _invoke_list(empty_project_root, "--json")
        assert result.exit_code == 0, result.output
        assert "Charter Activation State" not in result.output
        json.loads(result.output)  # raises if anything but pure JSON

    def test_json_shows_activated_directive(self, project_with_directive: Path) -> None:
        """The activated directive row lists ``python-style-guide`` (same row
        the human table shows, JSON-encoded rather than re-derived)."""
        result = _invoke_list(project_with_directive, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        kinds = {row["kind"]: row for row in payload["kinds"]}
        assert kinds["directive"]["activated"] == ["python-style-guide"]

    def test_json_empty_activation_list_is_empty_list_not_null(
        self, tmp_path: Path
    ) -> None:
        """An explicit empty activation list (restriction) must serialize as
        ``[]``, distinct from the ``null`` "all built-ins" state."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text(
            "activated_directives: []\nmission_type_activations:\n  - software-dev\n",
            encoding="utf-8",
        )
        result = _invoke_list(tmp_path, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        kinds = {row["kind"]: row for row in payload["kinds"]}
        assert kinds["directive"]["activated"] == []

    def test_json_show_available_adds_available_field(
        self, empty_project_root: Path
    ) -> None:
        """``--show-available --json`` adds an ``available`` list per kind,
        reusing ``ActiveCharterManager.list_available`` (same call the human
        table's third column uses)."""
        with patch(
            "charter.activation.pack_manager.ActiveCharterManager.list_available",
            return_value=frozenset(["doctrine-entry-1", "doctrine-entry-2"]),
        ):
            result = _invoke_list(empty_project_root, "--show-available", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        kinds = {row["kind"]: row for row in payload["kinds"]}
        assert sorted(kinds["directive"]["available"]) == [
            "doctrine-entry-1",
            "doctrine-entry-2",
        ]

    def test_json_without_show_available_has_null_available_field(
        self, empty_project_root: Path
    ) -> None:
        """Without ``--show-available``, every row still carries an
        ``available`` key -- it is ``null``, not absent (OP-CONTRACT-003:
        prefer always-present-with-null over conditionally-absent keys, so
        callers can rely on key presence rather than branching on flags)."""
        from charter.activation.kind_vocabulary import CHARTER_KIND_TOKENS

        result = _invoke_list(empty_project_root, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        # Count guard (OP-TESTS-003): a loop over an empty ``kinds`` list would
        # pass this assertion trivially. Pin the exact count actually iterated.
        assert len(payload["kinds"]) == len(CHARTER_KIND_TOKENS), payload["kinds"]
        for row in payload["kinds"]:
            assert "available" in row, row
            assert row["available"] is None, row

    def test_json_all_layers_includes_templates(self, empty_project_root: Path) -> None:
        """``--all --json`` appends the mission-scoped ``templates`` list,
        discovered via the same ``discover_templates`` call the human
        ``--all`` view uses, mission-qualified (FR-025)."""
        result = _invoke_list(empty_project_root, "--all", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        template_ids = {t["template_id"] for t in payload["templates"]}
        assert "software-dev/spec-template.md" in template_ids

    def test_json_all_layers_available_field_carries_layer(
        self, empty_project_root: Path
    ) -> None:
        """``--all --json``'s ``available`` entries are ``{artifact_id, layer}``
        objects, matching the human view's per-layer annotation."""
        result = _invoke_list(empty_project_root, "--all", "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        kinds = {row["kind"]: row for row in payload["kinds"]}
        directive_available = kinds["directive"]["available"]
        assert directive_available, "expected built-in directives to be available"
        entry = directive_available[0]
        assert set(entry) == {"artifact_id", "layer"}

    def test_json_templates_null_without_all(self, empty_project_root: Path) -> None:
        """Without ``--all``, the payload still carries a top-level
        ``templates`` key -- it is ``null``, not absent (OP-CONTRACT-003; the
        template kind is mission-scoped and only populated by the
        layer-aware view, mirroring the human table)."""
        result = _invoke_list(empty_project_root, "--json")
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert "templates" in payload, payload
        assert payload["templates"] is None, payload

    def test_json_all_value_error_routes_through_emit_error(
        self, empty_project_root: Path
    ) -> None:
        """A ``ValueError`` from ``list_available_detailed`` under ``--all
        --json`` must be reported through the shared ``_emit_error`` envelope
        -- not leaked as unstructured stdout text."""
        with patch(
            "charter.activation.pack_manager.ActiveCharterManager.list_available_detailed",
            side_effect=ValueError("boom"),
        ):
            result = _invoke_list(empty_project_root, "--all", "--json")
        assert result.exit_code == 1, result.output
        payload = json.loads(result.output)
        assert payload == {
            "result": "error",
            "success": False,
            "error": "boom",
        }


# ---------------------------------------------------------------------------
# charter list — non-mapping config.yaml guard (issue #3839 MAJOR finding)
# ---------------------------------------------------------------------------
#
# ``charter list``'s own headline path (``ProjectContext.from_repo`` ->
# ``PackContext.from_config`` -> ``pack_context._load_config``) had NO
# exception boundary at all: a non-mapping ``.kittify/config.yaml`` raised
# ``ActiveCharterConfigError`` (a ``KittyInternalConsistencyError``) uncaught,
# through every entry path (plain ``list``, ``--show-available``, ``--all``),
# both ``--json`` and rich-console modes -- exit 1 with EMPTY stdout and a raw
# traceback on stderr. That is exactly the fail-quiet-becomes-traceback
# outcome this mission (SK-16 lineage) exists to close, and this test file
# had no non-mapping case for ``list`` itself before this addition -- that
# gap is exactly what let the regression through.
#
# The full non-mapping space mirrors what the other four guarded readers
# (``charter status``, ``synthesize``, ``resynthesize``,
# ``doctor tool-surfaces``) were verified against: a bare string, a list, an
# int, a float, and a bool top-level YAML document. ``None`` (an empty
# document) is NOT an error -- ``pack_context._load_config`` and
# ``pack_manager._load_config`` both resolve it to ``{}`` -- and is pinned
# separately so the guard is never accidentally widened to reject it too.

#: Non-mapping top-level YAML shapes. Every one of these parses without a
#: YAML error but is not a ``dict``, so ``isinstance(data, dict)`` fails and
#: ``PackContext.from_config`` raises ``ActiveCharterConfigError``.
_NON_MAPPING_CONFIG_YAML: dict[str, str] = {
    "string": "just-a-plain-string-not-a-mapping\n",
    "list": "- a\n- b\n",
    "int": "42\n",
    "float": "3.14\n",
    "bool": "true\n",
}

#: Every ``charter list`` entry path the maintainer's finding named --
#: ``--show-available`` and ``--all`` hit the same unguarded call as plain
#: ``list``, not just the already-guarded ``list_available_detailed`` path
#: reached under ``--all``.
_LIST_ENTRY_PATHS: dict[str, tuple[str, ...]] = {
    "plain": (),
    "show_available": ("--show-available",),
    "all": ("--all",),
}


def _build_non_mapping_config(repo_root: Path, yaml_text: str) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(yaml_text, encoding="utf-8")


@pytest.mark.parametrize("entry_name", sorted(_LIST_ENTRY_PATHS))
@pytest.mark.parametrize("shape_name", sorted(_NON_MAPPING_CONFIG_YAML))
class TestListNonMappingConfigGuard:
    """Every entry path x every non-mapping shape, in both output modes."""

    def test_json_mode_fails_closed_with_parseable_diagnostic(
        self, tmp_path: Path, shape_name: str, entry_name: str
    ) -> None:
        _build_non_mapping_config(tmp_path, _NON_MAPPING_CONFIG_YAML[shape_name])
        result = _invoke_list(
            tmp_path, *_LIST_ENTRY_PATHS[entry_name], "--json"
        )

        assert result.exit_code == 1, (
            f"charter list {_LIST_ENTRY_PATHS[entry_name]} --json must fail "
            f"closed on a non-mapping ({shape_name}) config.yaml; got exit "
            f"{result.exit_code}:\n{result.stdout}"
        )
        assert result.stdout.strip(), (
            "expected JSON on stdout -- empty stdout is the pre-fix symptom "
            "(the raw traceback went to stderr instead)"
        )
        assert "Traceback" not in result.stdout

        payload = json.loads(result.stdout)  # raises if not parseable JSON
        assert payload["result"] == "error", payload
        assert payload["success"] is False, payload

        message = payload["error"]
        # Surface .body, not just str(exc) -- ACTIVE_CHARTER_CONFIG_INVALID
        # alone tells the consumer nothing.
        assert message != "ACTIVE_CHARTER_CONFIG_INVALID", (
            f"diagnostic must carry the .body detail, not the bare code: {payload!r}"
        )
        assert "config.yaml" in message and "mapping" in message, (
            f"diagnostic should name the file and the real problem: {payload!r}"
        )

    def test_rich_console_mode_fails_closed_without_traceback(
        self, tmp_path: Path, shape_name: str, entry_name: str
    ) -> None:
        _build_non_mapping_config(tmp_path, _NON_MAPPING_CONFIG_YAML[shape_name])
        result = _invoke_list(tmp_path, *_LIST_ENTRY_PATHS[entry_name])

        assert result.exit_code == 1, (
            f"charter list {_LIST_ENTRY_PATHS[entry_name]} must fail closed "
            f"on a non-mapping ({shape_name}) config.yaml; got exit "
            f"{result.exit_code}:\n{result.output}"
        )
        assert "Traceback" not in result.output
        assert "config.yaml" in result.output and "mapping" in result.output, (
            f"diagnostic should name the file and the real problem: {result.output!r}"
        )


class TestListNoneConfigResolvesToEmptyMapping:
    """An empty ``.kittify/config.yaml`` (YAML ``None``) is NOT an error --
    both loaders resolve it to ``{}``, distinct from every non-mapping shape
    above."""

    def test_empty_config_file_is_not_an_error(self, tmp_path: Path) -> None:
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("", encoding="utf-8")

        result = _invoke_list(tmp_path, "--json")

        assert result.exit_code == 0, result.stdout
        payload = json.loads(result.stdout)
        assert payload["result"] == "success", payload
