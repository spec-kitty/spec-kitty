"""Shape conformance tests for orchestrator-api responses against 3.0.0 contract.

Tests that CLI command output uses mission-era naming (mission_slug not
mission_slug), returns correct error codes, and rejects legacy commands/flags.

Run: python -m pytest tests/contract/test_orchestrator_api.py -v
"""

from __future__ import annotations

import importlib
import inspect
import json
import pkgutil
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.git.commit_helpers import SafeCommitBackstopError, SafeCommitError
from specify_cli import orchestrator_api
from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION

pytestmark = [pytest.mark.contract, pytest.mark.fast]

runner = CliRunner()


def _make_mission(tmp_path: Path, mission_slug: str = "099-test-mission") -> tuple[Path, Path]:
    """Create a minimal mission directory with tasks and meta.json.

    Returns (repo_root, mission_dir).
    """
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / mission_slug
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n"
            f"lane: planned\ndependencies: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )

    meta = {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Test Mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-03-18T00:00:00+00:00",
        "status_phase": 2,
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return repo_root, mission_dir


def _invoke(args: list[str], repo_root: Path) -> tuple[dict, int]:
    """Invoke orchestrator-api subcommand with mocked repo root.

    Returns (parsed_json, exit_code).
    """
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo_root,
    ):
        result = runner.invoke(app, args, catch_exceptions=False)

    # Parse the JSON output (first line of stdout)
    output = result.output.strip()
    if output:
        envelope = json.loads(output.split("\n")[0])
    else:
        envelope = {}
    return envelope, result.exit_code


class TestMissionStateResponse:
    """Validate mission-state command output shape."""

    def test_response_contains_mission_slug(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        assert envelope["success"] is True
        data = envelope["data"]
        assert "mission_slug" in data, "Response must contain 'mission_slug'"
        assert data["mission_slug"] == "099-test-mission"

    def test_response_does_not_contain_mission_slug(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        data = envelope["data"]
        for forbidden in orchestrator_api_contract["forbidden_payload_fields"]:
            assert forbidden not in data, f"Forbidden field '{forbidden}' found in response data"

    def test_command_field_uses_mission_era_name(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(["mission-state", "--mission", "099-test-mission"], repo_root)

        assert "command" in envelope
        # Command should reference mission-state, not feature-state
        assert "mission-state" in envelope["command"]
        assert "feature-state" not in envelope["command"]


class TestMissionNotFoundError:
    """Validate that not-found errors use MISSION_NOT_FOUND."""

    def test_error_code_is_mission_not_found(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["mission-state", "--mission", "999-nonexistent"],
            repo_root,
        )

        assert envelope["success"] is False
        assert envelope["error_code"] == "MISSION_NOT_FOUND"

    def test_error_code_is_not_feature_not_found(self, tmp_path, orchestrator_api_contract):
        repo_root, _ = _make_mission(tmp_path)
        envelope, _ = _invoke(
            ["mission-state", "--mission", "999-nonexistent"],
            repo_root,
        )

        for forbidden_code in orchestrator_api_contract["forbidden_error_codes"]:
            assert envelope["error_code"] != forbidden_code, (
                f"Error code '{forbidden_code}' is forbidden by contract"
            )


class TestAcceptMissionNotReady:
    """Validate accept-mission returns MISSION_NOT_READY when WPs incomplete."""

    def test_mission_not_ready_error(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["accept-mission", "--mission", "099-test-mission", "--actor", "test-agent"],
            repo_root,
        )

        assert envelope["success"] is False
        assert envelope["error_code"] == "MISSION_NOT_READY"


class TestForbiddenCommands:
    """Validate that legacy feature-era command names are rejected."""

    def test_feature_state_is_unknown_command(self, tmp_path):
        """Invoking 'feature-state' must fail -- it is not a valid subcommand."""
        repo_root, _ = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["feature-state", "--mission", "099-test-mission"])

        # Must fail with non-zero exit code
        assert result.exit_code != 0, "feature-state should not be a valid command"


class TestForbiddenFlags:
    """Validate that --feature flag is rejected, --mission works."""

    def test_mission_flag_works(self, tmp_path):
        repo_root, _ = _make_mission(tmp_path)
        envelope, code = _invoke(
            ["mission-state", "--mission", "099-test-mission"],
            repo_root,
        )
        assert envelope.get("success") is True

    def test_feature_flag_is_rejected(self, tmp_path):
        """--feature flag must not be accepted by mission-state."""
        repo_root, _ = _make_mission(tmp_path)

        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=repo_root,
        ):
            result = runner.invoke(app, ["mission-state", "--feature", "099-test-mission"])

        # Must fail with non-zero exit code since --feature is not a valid option
        assert result.exit_code != 0, "--feature flag should not be accepted"


class TestAllowedCommandNames:
    """Cross-check that allowed commands from contract exist as app subcommands."""

    def test_allowed_commands_are_registered(self, orchestrator_api_contract):
        """Every command in the contract must be a registered subcommand."""
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        allowed_commands = set(orchestrator_api_contract["allowed_commands"])
        for cmd_name in allowed_commands:
            assert cmd_name in registered, f"Allowed command '{cmd_name}' is not registered in orchestrator-api app"

    def test_registered_commands_are_contract_allowed(self, orchestrator_api_contract):
        """Every registered subcommand must be declared in the contract.

        The inverse of test_allowed_commands_are_registered: without it, a new
        command can register on the surface without ever entering
        upstream_contract.json (the artifact external consumers validate
        against) — #2338's resolve-workspace was the first live instance.
        """
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        allowed_commands = set(orchestrator_api_contract["allowed_commands"])
        undeclared = registered - allowed_commands
        assert not undeclared, (
            f"Registered orchestrator-api command(s) missing from upstream_contract.json "
            f"allowed_commands: {sorted(undeclared)}"
        )

    def test_commands_register_in_help_order(self):
        """``--help`` lists the verbs in registration order; the sets alone do not pin it."""
        assert [info.name for info in app.registered_commands] == [
            "contract-version",
            "mission-state",
            "list-ready",
            "resolve-workspace",
            "start-implementation",
            "start-review",
            "transition",
            "append-history",
            "accept-mission",
            "consolidate-mission",
            "specify",
            "plan",
            "tasks",
            "check-prerequisites",
            "record-analysis",
            "open-decision",
            "resolve-decision",
            "defer-decision",
            "cancel-decision",
            "answer-decision",
            "design-status",
            "artifact-read",
            "artifact-submit",
            "design-validate",
            "design-context",
            "interview-record",
            "next",
        ]

    def test_forbidden_commands_are_not_registered(self, orchestrator_api_contract):
        """No forbidden command from the contract may be registered."""
        import typer.main

        group = typer.main.get_group(app)
        registered = set(group.commands.keys()) if hasattr(group, "commands") else set()

        for forbidden_cmd in orchestrator_api_contract["forbidden_commands"]:
            assert forbidden_cmd not in registered, (
                f"Forbidden command '{forbidden_cmd}' is registered in orchestrator-api app"
            )


class TestAllowedErrorCodes:
    """Cross-check emitted orchestrator-api failure codes against the contract."""

    def test_literal_failure_codes_are_contract_allowed(self, orchestrator_api_contract):
        # The verbs live in per-concern modules behind the ``commands`` facade, so the
        # scan must cover every module of the package, not the facade alone.
        source = "\n".join(
            inspect.getsource(importlib.import_module(f"{orchestrator_api.__name__}.{module.name}"))
            for module in pkgutil.iter_modules(orchestrator_api.__path__)
        )
        emitted = set(
            re.findall(
                r"_fail\(\s*[^,]+,\s*[\"']([A-Z0-9_]+)[\"']",
                source,
                flags=re.DOTALL,
            )
        )
        # Floor: a contract code that only a concern module emits. Naming one real
        # code (rather than a count) keeps the scan from going vacuous again without
        # breaking each time a code is legitimately added or retired.
        assert "MISSION_NOT_FOUND" in emitted
        allowed = set(orchestrator_api_contract["allowed_error_codes"])
        assert emitted <= allowed

    def test_safe_commit_failure_codes_are_contract_allowed(self, orchestrator_api_contract):
        # Walk every descendant, not only direct subclasses: a refinement such as
        # a ``SafeCommitRecoveryFailed`` child carries its own code too.
        emitted = {SafeCommitError.error_code, SafeCommitBackstopError.error_code}
        pending = list(SafeCommitError.__subclasses__())
        while pending:
            cls = pending.pop()
            emitted.add(cls.error_code)
            pending.extend(cls.__subclasses__())
        for code in (
            "SAFE_COMMIT_PATH_LOOP",
            "SAFE_COMMIT_INDEX_DELETION_CONFLICT",
            "SAFE_COMMIT_INDEX_RESIDUE",
            "SAFE_COMMIT_DIRECTORY_ARGUMENT",
        ):
            assert code in emitted
        allowed = set(orchestrator_api_contract["allowed_error_codes"])
        assert emitted <= allowed


# ---------------------------------------------------------------------------
# The documented enumerations of ``allowed_error_codes``
#
# ``allowed_error_codes`` is the authority. Two prose surfaces enumerate it for a
# human reader, and until #7035 nothing compared them: the API reference list was
# 22 codes behind and the shipped operator skill's table 23. A registration PR
# could therefore ship a code and leave both docs silently wrong, and a docs edit
# could list a code the CLI never emits.
#
# Each surface carries ONE explicit region, delimited by the anchors below, and
# the guard reads only that region. The region exists because the surrounding
# prose legitimately names codes from *other* namespaces (``preflight_error_code``,
# ``teardown_error_code``, origin freshness) that are not contract entries; a
# whole-section scan would demand them in the contract. See
# kitty-specs/orchestrator-error-code-prose-guard-01M6EJQS/research.md D-1/D-2.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

_BEGIN_ANCHOR = "<!-- orchestrator-error-codes:begin -->"
_END_ANCHOR = "<!-- orchestrator-error-codes:end -->"

#: (surface path as reported in a failure, region kind, file). Adding a surface
#: means adding its anchor pair and one row here; nothing else about the guard
#: changes. The first element is the repo-relative path, because it is what the
#: failure message hands to whoever has to fix the drift.
_ENUMERATION_SURFACES: tuple[tuple[str, str, Path], ...] = tuple(
    (
        relative,
        kind,
        _REPO_ROOT / relative,
    )
    for relative, kind in (
        ("docs/api/orchestrator-api.md", "bullets"),
        (
            "src/charter/offering/skills/spec-kitty-orchestrator-api-operator"
            "/references/orchestrator-api-contract.md",
            "table",
        ),
    )
)

_ENUMERATION_SURFACE_IDS = ("api-reference", "operator-skill-reference")

_BULLET_ENTRY = re.compile(r"^- `(?P<code>[A-Z][A-Z0-9_]*)`")
_TABLE_ENTRY = re.compile(r"^\| `(?P<code>[A-Z][A-Z0-9_]*)` \|")
_TABLE_HEADER = re.compile(r"^\| *Error [Cc]ode *\|")
_TABLE_SEPARATOR = re.compile(r"^\|[-: |]+\|$")
_HTML_COMMENT = re.compile(r"^<!--.*-->$")


class ProseEnumerationError(AssertionError):
    """A documented enumeration cannot be read as the enumeration it claims to be."""


def _parse_enumeration_entries(text: str, kind: str) -> list[str]:
    """Return the code entries of a surface's anchored enumeration, in document order.

    Fails closed: a missing or duplicated anchor, a region with no entries, or a
    line inside the region that is not a recognisable entry all raise, so deleting
    an anchor (or replacing a list with prose) cannot silently disable the guard.
    """
    lines = text.splitlines()
    begins = [index for index, line in enumerate(lines) if line.strip() == _BEGIN_ANCHOR]
    ends = [index for index, line in enumerate(lines) if line.strip() == _END_ANCHOR]
    if len(begins) != 1 or len(ends) != 1:
        raise ProseEnumerationError(
            f"expected exactly one {_BEGIN_ANCHOR!r} and one {_END_ANCHOR!r}; "
            f"found {len(begins)} begin and {len(ends)} end anchor(s)"
        )
    if begins[0] > ends[0]:
        raise ProseEnumerationError(f"{_END_ANCHOR!r} appears before {_BEGIN_ANCHOR!r}")

    entries: list[str] = []
    for number in range(begins[0] + 1, ends[0]):
        line = lines[number].strip()
        if not line or _HTML_COMMENT.match(line):
            continue
        entry = _BULLET_ENTRY.match(line) if kind == "bullets" else _TABLE_ENTRY.match(line)
        if entry is not None:
            entries.append(entry.group("code"))
            continue
        if kind == "table" and (_TABLE_HEADER.match(line) or _TABLE_SEPARATOR.match(line)):
            continue
        raise ProseEnumerationError(
            f"line {number + 1} inside the enumeration region is not a {kind} entry: {lines[number]!r}"
        )

    if not entries:
        raise ProseEnumerationError(
            "the enumeration region holds no code entries; an empty region cannot agree with the contract"
        )
    return entries


def _assert_enumeration_matches_contract(
    entries: list[str],
    allowed: set[str],
    surface: str,
) -> None:
    """Assert one surface's entries are exactly *allowed*, reporting both directions.

    A single assertion names sorted ``missing`` and ``unexpected`` lists so a
    registration PR gets its to-do list from the failure, and a docs PR learns
    which entry it invented.
    """
    enumerated = set(entries)
    duplicated = sorted(code for code in enumerated if entries.count(code) > 1)
    missing = sorted(allowed - enumerated)
    unexpected = sorted(enumerated - allowed)
    problems = []
    if missing:
        problems.append(f"registered but not documented: {missing}")
    if unexpected:
        problems.append(f"documented but not registered: {unexpected}")
    if duplicated:
        problems.append(f"listed more than once: {duplicated}")
    assert not problems, (
        f"{surface}: the documented error-code enumeration disagrees with "
        f"orchestrator_api.allowed_error_codes ({len(allowed)} codes) — " + "; ".join(problems)
    )


class TestProseErrorCodeEnumerations:
    """Keep the two documented enumerations exactly equal to ``allowed_error_codes``."""

    @pytest.mark.parametrize(("surface", "kind", "path"), _ENUMERATION_SURFACES, ids=_ENUMERATION_SURFACE_IDS)
    def test_surface_enumerates_the_contract_exactly(self, orchestrator_api_contract, surface, kind, path):
        entries = _parse_enumeration_entries(path.read_text(encoding="utf-8"), kind)
        # Same-region positive control: a probe that read nothing cannot pass as
        # "agreement", because this floor names a code every surface has always had.
        assert "USAGE_ERROR" in entries, f"{surface}: parsed region does not even hold USAGE_ERROR"
        _assert_enumeration_matches_contract(entries, set(orchestrator_api_contract["allowed_error_codes"]), surface)
    def test_a_newly_registered_code_is_reported_per_surface(self, orchestrator_api_contract):
        """A code added to the contract but not to a surface must fail naming both.

        This runs the same parse and the same assertion the real test uses, with
        the contract widened in memory — the positive control for the negative
        path above.
        """
        allowed = set(orchestrator_api_contract["allowed_error_codes"]) | {"SYNTHETIC_UNREGISTERED_CODE"}
        for surface, kind, path in _ENUMERATION_SURFACES:
            entries = _parse_enumeration_entries(path.read_text(encoding="utf-8"), kind)
            with pytest.raises(AssertionError) as failure:
                _assert_enumeration_matches_contract(entries, allowed, surface)
            assert "SYNTHETIC_UNREGISTERED_CODE" in str(failure.value)
            assert surface in str(failure.value)

    @pytest.mark.parametrize(
        "text",
        [
            "- `USAGE_ERROR`\n",
            f"{_BEGIN_ANCHOR}\n- `USAGE_ERROR`\n{_END_ANCHOR}\n{_BEGIN_ANCHOR}\n- `USAGE_ERROR`\n{_END_ANCHOR}\n",
        ],
    )
    def test_anchor_count_fail_closed(self, text):
        with pytest.raises(ProseEnumerationError, match="expected exactly one"):
            _parse_enumeration_entries(text, "bullets")

    def test_empty_region_fails_closed(self):
        text = f"{_BEGIN_ANCHOR}\n\n<!-- nothing here yet -->\n{_END_ANCHOR}\n"
        with pytest.raises(ProseEnumerationError, match="no code entries"):
            _parse_enumeration_entries(text, "bullets")

    def test_unreadable_line_in_region_fails_closed(self):
        text = f"{_BEGIN_ANCHOR}\n- `USAGE_ERROR`\nThe codes above are illustrative.\n{_END_ANCHOR}\n"
        with pytest.raises(ProseEnumerationError, match="is not a bullets entry"):
            _parse_enumeration_entries(text, "bullets")

    def test_bullet_annotation_does_not_add_an_entry(self):
        """A parenthetical that names another code annotates, it does not enumerate."""
        text = f"{_BEGIN_ANCHOR}\n- `SAFE_COMMIT_INDEX_RESIDUE` (a `SAFE_COMMIT_RECOVERY_FAILED` refinement)\n{_END_ANCHOR}\n"
        assert _parse_enumeration_entries(text, "bullets") == ["SAFE_COMMIT_INDEX_RESIDUE"]

    def test_table_description_does_not_add_an_entry(self):
        text = (
            f"{_BEGIN_ANCHOR}\n"
            "| Error Code | Commands | Description |\n"
            "|---|---|---|\n"
            "| `USAGE_ERROR` | all | Also see `MISSION_NOT_FOUND` |\n"
            f"{_END_ANCHOR}\n"
        )
        assert _parse_enumeration_entries(text, "table") == ["USAGE_ERROR"]
