"""Integration tests for the public ``spec-kitty dispatch`` surface."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import Result
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from charter.activation.pack_context import PackContext
from glossary.chokepoint import GlossaryObservationBundle
from glossary.models import ConflictType, SemanticConflict, SenseRef, Severity, TermSurface
from specify_cli import app as cli_app
from specify_cli.invocation.modes import ModeOfWork, derive_mode
from specify_cli.invocation.writer import EVENTS_DIR, InvocationWriter

pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"


class ArgvCliRunner(CliRunner):
    def invoke(  # type: ignore[override]
        self,
        app: Typer,
        args: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result:
        argv = ["spec-kitty", *(list(args) if args is not None and not isinstance(args, str) else [])]
        with patch.object(sys, "argv", argv):
            return super().invoke(app, args, **kwargs)


runner = ArgvCliRunner()

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"

_MISSING_CTX = MagicMock()
_MISSING_CTX.mode = "missing"
_MISSING_CTX.text = ""


def _setup_project(tmp_path: Path) -> Path:
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    return tmp_path


def _write_configured_charter(project: Path) -> None:
    """Write a project charter that is genuinely routable (not empty-for-dispatch).

    WP02/#3064, updated for NFR-004/#3104: ``resolve_generic_fallback`` reads
    the REAL project charter on disk (not any mocked ``ProfileRegistry``). A
    project fixture with no charter configured at all is genuinely
    "empty charter" and would now auto-route to ``generic-agent`` -- tests
    exercising the mocked-router auto-route path need a charter the NEW
    bundle-presence + org-pack-safe predicate (``specify_cli.invocation.
    empty_charter.is_charter_empty``) treats as routable, so they keep
    proving router behaviour, not the empty-charter fallback (which has its
    own dedicated tests below).

    The predicate drops non-routing dimensions (``activated_directives``
    included) -- a directive-only config.yaml no longer suffices. This writes
    both an ``activated_directives`` key (kept for fixture-history parity;
    exercises no bearing on the predicate) AND a compiled-bundle presence
    stub at ``.kittify/charter/charter.yaml`` (presence-only per the
    predicate contract -- content is a near-empty placeholder, never
    inspected), which is what actually makes ``is_charter_empty`` return
    ``False`` here.
    """
    kittify = project / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump({"activated_directives": ["028-efficient-local-tooling"]}, fh)
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text("{}\n", encoding="utf-8")


def _make_mock_registry(profile_specs: list[dict[str, object]]) -> MagicMock:
    from charter.offering.agent_profiles.profile import Role

    mock_profiles = []
    for spec in profile_specs:
        profile = MagicMock()
        profile.profile_id = spec["profile_id"]
        profile.role = Role(str(spec["role_value"]))
        profile.routing_priority = spec.get("routing_priority", 50)
        profile.name = spec.get("name", spec["profile_id"])

        specialization = MagicMock()
        specialization.domain_keywords = spec.get("domain_keywords", [])
        profile.specialization_context = specialization

        collaboration = MagicMock()
        collaboration.canonical_verbs = spec.get("collab_verbs", [])
        profile.collaboration = collaboration

        mock_profiles.append(profile)

    registry = MagicMock()
    registry.list_all.return_value = mock_profiles

    def _get(profile_id: str) -> object | None:
        return next((profile for profile in mock_profiles if profile.profile_id == profile_id), None)

    def _resolve(profile_id: str) -> object:
        from specify_cli.invocation.errors import ProfileNotFoundError

        profile = _get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id, [p.profile_id for p in mock_profiles])
        return profile

    registry.get.side_effect = _get
    registry.resolve.side_effect = _resolve
    return registry


def _implementer_registry() -> MagicMock:
    return _make_mock_registry(
        [
            {
                "profile_id": "implementer-fixture",
                "role_value": "implementer",
                "routing_priority": 50,
                "name": "Implementer (fixture)",
                "domain_keywords": ["implement", "build", "code"],
            }
        ]
    )


def _high_severity_bundle() -> GlossaryObservationBundle:
    conflict = SemanticConflict(
        term=TermSurface("lane"),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=1.0,
        candidate_senses=[
            SenseRef(surface="lane", scope="spec_kitty_core", definition="Execution lane", confidence=1.0),
            SenseRef(surface="lane", scope="team_domain", definition="Worktree lane", confidence=1.0),
        ],
        context="request_text",
    )
    return GlossaryObservationBundle(
        matched_urns=("glossary:d93244e7",),
        high_severity=(conflict,),
        all_conflicts=(conflict,),
        tokens_checked=3,
        duration_ms=1.5,
        error_msg=None,
    )


def _run(project: Path, args: list[str], *, ctx: MagicMock = _COMPACT_CTX) -> Result:
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch("specify_cli.invocation.executor.build_charter_context", return_value=ctx),
    ):
        return runner.invoke(cli_app, args)


def _run_with_registry(project: Path, args: list[str], registry: MagicMock) -> Result:
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch("specify_cli.cli.commands.dispatch.ProfileRegistry", return_value=registry),
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
    ):
        return runner.invoke(cli_app, args)


def _invoke_json(project: Path, args: list[str], *, ctx: MagicMock = _COMPACT_CTX) -> dict[str, Any]:
    result = _run(project, args, ctx=ctx)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _read_op_record(project: Path, invocation_id: str) -> list[dict[str, Any]]:
    path = InvocationWriter(project).invocation_path(invocation_id)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_dispatch_with_profile_opens_task_execution_op(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)

    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
    )

    record = _read_op_record(project, str(envelope["invocation_id"]))[0]
    assert envelope["status"] == "open"
    assert envelope["governance_context_text"] == "compact governance context"
    assert envelope["close_contract"]["evidence_flag"] == "--evidence"
    assert record["mode_of_work"] == "task_execution"
    assert record["profile_id"] == "implementer-fixture"
    assert record["request_text"] == "implement the feature"


def test_dispatch_auto_routes_and_writes_single_started_record(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the payment module", "--json"],
        _implementer_registry(),
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    events = _read_op_record(project, str(envelope["invocation_id"]))
    assert envelope["profile_id"] == "implementer-fixture"
    assert envelope["router_confidence"] == "canonical_verb"
    assert [event["event"] for event in events] == ["started"]


def test_dispatch_no_charter_still_opens_record(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)

    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
        ctx=_MISSING_CTX,
    )

    record = _read_op_record(project, str(envelope["invocation_id"]))[0]
    assert envelope["governance_context_available"] is False
    assert record["governance_context_available"] is False


def test_dispatch_rich_output_includes_governance_and_close_contract(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
        patch("glossary.chokepoint.GlossaryChokepoint.run", return_value=_high_severity_bundle()),
    ):
        result = runner.invoke(
            cli_app,
            ["dispatch", "implement the feature", "--profile", "implementer-fixture"],
        )

    assert result.exit_code == 0, result.output
    flat = result.output.replace("\n", " ")
    assert "High-severity terminology conflicts detected before this invocation." in result.output
    assert result.output.index("lane (ambiguous)") < result.output.index("compact governance context")
    assert "This Op is OPEN" in flat
    assert "profile-invocation complete" in flat
    assert "git add" not in flat


def test_dispatch_missing_profile_exits_1_with_routing_error(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)

    result = _run(
        project,
        ["dispatch", "implement", "--profile", "nonexistent-profile", "--json"],
    )

    assert result.exit_code == 1
    error_obj = json.loads(result.output)
    assert error_obj["error"] == "routing_failed"
    assert error_obj["error_code"] == "PROFILE_NOT_FOUND"
    assert "spec-kitty profiles list" in error_obj["suggestion"]


def test_only_dispatch_is_registered_as_standalone_opener() -> None:
    assert runner.invoke(cli_app, ["dispatch", "--help"]).exit_code == 0
    for removed_command in ("do", "ask", "advise"):
        assert runner.invoke(cli_app, [removed_command, "--help"]).exit_code != 0


# ---------------------------------------------------------------------------
# #6990 — ``dispatch --brief``: reference the governance payload instead of
# re-embedding it. The full text stays one printed fetch command away.
# ---------------------------------------------------------------------------

_BRIEF_FULL_TEXT = "compact governance context"


def _brief_fetch_command(envelope: dict[str, Any]) -> str:
    """The exact command the brief reference prints, built from the envelope."""
    return (
        f"spec-kitty charter context --action {envelope['action']} "
        f"--profile {envelope['profile_id']} --json --no-mark-loaded"
    )


def test_dispatch_brief_json_replaces_text_with_reference(tmp_path: Path) -> None:
    """FR-001/FR-002: --brief nulls the text and names an exact fetch command."""
    project = _setup_project(tmp_path)
    full = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
    )
    brief = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json", "--brief"],
    )

    assert brief["governance_context_text"] is None
    assert brief["governance_context_reference"] == {
        "digest": full["governance_context_hash"],
        "bytes": len(_BRIEF_FULL_TEXT.encode("utf-8")),
        "lines": 1,
        "fetch_command": _brief_fetch_command(full),
    }
    # Everything except the text/reference pair is unchanged (C-003).
    for key in (
        "profile_id",
        "profile_friendly_name",
        "action",
        "router_confidence",
        "governance_context_hash",
        "governance_context_available",
        "recommendation",
        "status",
    ):
        assert brief[key] == full[key], key
    # ``close_contract.command`` names this run's Op id, so compare its shape.
    assert set(brief["close_contract"]) == set(full["close_contract"])
    assert brief["close_contract"]["outcomes"] == full["close_contract"]["outcomes"]


def test_dispatch_brief_console_prints_digest_and_fetch_command(tmp_path: Path) -> None:
    """Console brief mode prints the reference, not the ~24 KB panel."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json", "--brief"],
    )
    expected_command = _brief_fetch_command(envelope)

    result = _run(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--brief"],
    )

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert _BRIEF_FULL_TEXT not in result.output
    assert "not re-embedded" in flat
    assert "Governance context: digest" in flat
    assert expected_command in flat
    # The open-Op close hint is not part of the payload and still prints.
    assert "This Op is OPEN" in flat


def test_dispatch_brief_composes_with_dry_run(tmp_path: Path) -> None:
    """--dry-run --brief: same substitution, still nothing written."""
    project = _setup_project(tmp_path)
    result = _run(
        project,
        [
            "dispatch",
            "implement the feature",
            "--profile",
            "implementer-fixture",
            "--dry-run",
            "--json",
            "--brief",
        ],
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "dry_run"
    assert envelope["governance_context_text"] is None
    assert envelope["governance_context_reference"]["bytes"] == len(_BRIEF_FULL_TEXT.encode("utf-8"))
    assert "close_contract" not in envelope
    assert not (project / EVENTS_DIR).exists() or not list((project / EVENTS_DIR).glob("*.jsonl"))


def test_dispatch_without_brief_still_embeds_full_text(tmp_path: Path) -> None:
    """FR-004/SC-003 ratchet: the same-fixture control -- no --brief, no change."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
    )

    assert envelope["governance_context_text"] == _BRIEF_FULL_TEXT
    assert "governance_context_reference" not in envelope


def test_dispatch_brief_leaves_ambiguous_dry_run_payload_untouched(tmp_path: Path) -> None:
    """No resolved profile/action -> no governance text -> nothing to reference."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the feature", "--dry-run", "--json", "--brief"],
        _tied_implementers_registry(),
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["router_confidence"] == "ambiguous"
    assert "governance_context_reference" not in envelope


def test_dispatch_brief_leaves_unavailable_governance_alone(tmp_path: Path) -> None:
    """C-002: never hide text that the printed fetch command cannot reproduce."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json", "--brief"],
        ctx=_MISSING_CTX,
    )

    assert envelope["governance_context_available"] is False
    assert "governance_context_reference" not in envelope


def test_dispatch_brief_keeps_the_text_under_the_empty_charter_fallback(tmp_path: Path) -> None:
    """C-002 edge: the fallback render is NOT reproducible by ``charter context``.

    ``dispatch`` renders with ``suppress_project_resolver=True`` under the
    empty-charter fallback (executor), and ``charter context`` has no equivalent
    flag, so its text would be a superset. Brief mode must keep the real text
    embedded instead of printing a reference that resolves to something else.
    """
    project = _setup_project(tmp_path)
    envelope = _invoke_json(project, ["dispatch", "implement the payment module", "--json", "--brief"])

    assert envelope["empty_charter_fallback"] is True
    assert envelope["governance_context_text"] == _BRIEF_FULL_TEXT
    assert "governance_context_reference" not in envelope


def test_brief_fetch_command_uses_payload_action_not_request_verb(tmp_path: Path) -> None:
    """The action is derived (role default verb), so the command must read the
    payload's own ``action`` -- a request-verb guess would name a different grain."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "please review the feature", "--profile", "implementer-fixture", "--json", "--brief"],
    )

    assert envelope["governance_context_reference"]["fetch_command"] == _brief_fetch_command(envelope)
    assert "please review" not in envelope["governance_context_reference"]["fetch_command"]


def test_entry_command_mode_mapping_only_has_dispatch_for_standalone_openers() -> None:
    assert derive_mode("dispatch") is ModeOfWork.TASK_EXECUTION
    for removed_command in ("do", "ask", "advise"):
        with pytest.raises(KeyError):
            derive_mode(removed_command)


def test_dispatch_writes_single_jsonl_file(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
    )
    jsonl = [p for p in (project / EVENTS_DIR).glob("*.jsonl") if p.name != "ops-index.jsonl"]
    assert len(jsonl) == 1
    assert jsonl[0].stem == str(envelope["invocation_id"])


# ---------------------------------------------------------------------------
# WP02/#3064 — empty-charter generic-agent routing fallback + warning
# ---------------------------------------------------------------------------
#
# These use the REAL ProfileRegistry/ActionRouter (no mocked registry): the
# fixture project from `_setup_project` carries no `.kittify/config.yaml`,
# which is a genuinely empty charter under the composite predicate
# (research.md Decision 3), and `generic-agent`/`architect-alphonso` are real
# shipped built-in profiles so resolution needs no mock.


def test_dispatch_empty_charter_auto_routes_to_generic_agent(tmp_path: Path) -> None:
    """No --profile hint, wholly-empty charter -> pins generic-agent (Decision 2/3)."""
    project = _setup_project(tmp_path)

    envelope = _invoke_json(project, ["dispatch", "implement the payment module", "--json"])

    assert envelope["profile_id"] == "generic-agent"
    assert envelope["router_confidence"] == "generic_fallback"
    assert envelope["action"] == "implement"
    assert envelope["empty_charter_fallback"] is True


def test_dispatch_empty_charter_rich_output_shows_warning_panel(tmp_path: Path) -> None:
    """The one-shot warning (Decision 5) renders in the rich (non-JSON) path.

    The wording is honest about what applying a preset does and does not do
    (#3064 follow-up): it must not promise a working dispatch route --
    applying a preset only records activations in config.yaml, and an
    unmatched request may still need an explicit --profile.
    """
    project = _setup_project(tmp_path)

    result = _run(project, ["dispatch", "implement the payment module"])

    assert result.exit_code == 0, result.output
    assert "Empty Charter" in result.output
    assert "generic-agent" in result.output
    assert "charter activate --preset minimal" in result.output
    # The retired spelling (#3732) must not come back.
    assert "charter pack apply" not in result.output
    # Honest caveat: applying a preset is not a promise of a working dispatch.
    assert "--profile" in result.output


def test_dispatch_explicit_profile_bypasses_empty_charter_fallback(tmp_path: Path) -> None:
    """An explicit --profile hint resolves the specialist normally under an empty
    charter -- the fallback pre-check only engages on the no-hint auto-route
    branch (research.md Decision 2); it must never override an explicit hint.
    """
    project = _setup_project(tmp_path)

    envelope = _invoke_json(
        project,
        ["dispatch", "design the system architecture", "--profile", "architect-alphonso", "--json"],
    )

    assert envelope["profile_id"] == "architect-alphonso"
    assert envelope["empty_charter_fallback"] is False

    result = _run(project, ["dispatch", "design the system architecture", "--profile", "architect-alphonso"])
    assert result.exit_code == 0, result.output
    assert "Empty Charter" not in result.output


def test_dispatch_empty_charter_still_routes_despite_empty_mission_type_activation(
    tmp_path: Path,
) -> None:
    """Dispatch routing is independent of mission-type activation.

    WP04 (C-A1) retired the "absence admits all built-ins" convenience
    default for ``mission_type_activations`` specifically (#2657): an absent
    or empty key now reads as ``frozenset()``, not "all built-in mission
    types." The actionable fail-closed for that empty set lives at the
    mission-create / mission-type-use boundary
    (``specify_cli.core.mission_creation.create_mission_core``) -- a
    dimension ``spec-kitty dispatch`` never touches. Dispatch routes purely
    through the ``ProfileRegistry`` / ``ActionRouter`` (proven by the
    empty-charter generic-agent fallback tests above); it has no dependency
    on mission-type activation at all. So under the very same empty-charter
    repo those tests exercise: mission-type activation is genuinely empty
    (not "all built-ins"), AND dispatch still functions end-to-end via its
    profile-routing fallback.
    """
    project = _setup_project(tmp_path)

    pack_context = PackContext.from_config(project)
    assert pack_context.activated_mission_types == frozenset()
    assert "software-dev" not in pack_context.activated_mission_types

    envelope = _invoke_json(project, ["dispatch", "implement the payment module", "--json"])

    assert envelope["profile_id"] == "generic-agent"
    assert envelope["router_confidence"] == "generic_fallback"
    assert envelope["empty_charter_fallback"] is True


# ---------------------------------------------------------------------------
# WP1/#3840 — `dispatch --dry-run` flag + payload shape
#
# Correctness property this section exists for: a dry-run call writes
# NOTHING -- no kitty-ops/ file, no ops-index.jsonl line, no
# .kittify/events/glossary/*.jsonl file, no SaaS propagator submit. Every
# absence is proven by a directory/file-count snapshot, never inferred from
# the returned payload alone (silent success is this repo's dominant failure
# mode -- SPEC-KITTY-LEDGER.md).
# ---------------------------------------------------------------------------


def _tied_implementers_registry() -> MagicMock:
    """Two implementer profiles, equal routing_priority, no domain keywords.

    Mirrors tests/specify_cli/invocation/test_router.py's
    test_router_ambiguity_two_profiles_same_score fixture shape -- both
    candidates tie on the canonical-verb match, so route() raises
    ROUTER_AMBIGUOUS after the priority tiebreaker fails to separate them.
    """
    return _make_mock_registry(
        [
            {
                "profile_id": "implementer-a",
                "role_value": "implementer",
                "routing_priority": 50,
                "domain_keywords": [],
            },
            {
                "profile_id": "implementer-b",
                "role_value": "implementer",
                "routing_priority": 50,
                "domain_keywords": [],
            },
        ]
    )


def _snapshot_dir(path: Path) -> list[str]:
    """Sorted file-name listing of *path*, or [] if it does not exist.

    Treats "directory absent" and "directory present but empty" as the same
    unchanged state (SC-002's explicit requirement).
    """
    if not path.exists():
        return []
    return sorted(p.name for p in path.iterdir())


def test_dry_run_writes_nothing_to_kitty_ops(tmp_path: Path) -> None:
    """SC-001: N dry-run calls leave kitty-ops/ byte-identical (file count +
    ops-index.jsonl line count)."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    ops_dir = project / EVENTS_DIR
    index_path = ops_dir / "ops-index.jsonl"
    before_files = _snapshot_dir(ops_dir)
    before_index_lines = index_path.read_text(encoding="utf-8").splitlines() if index_path.exists() else []

    for _ in range(3):
        result = _run_with_registry(
            project,
            ["dispatch", "implement the payment module", "--dry-run", "--json"],
            _implementer_registry(),
        )
        assert result.exit_code == 0, result.output

    after_files = _snapshot_dir(ops_dir)
    after_index_lines = index_path.read_text(encoding="utf-8").splitlines() if index_path.exists() else []
    assert after_files == before_files
    assert after_index_lines == before_index_lines


def test_dry_run_suppresses_glossary_event_write(tmp_path: Path) -> None:
    """SC-002: dry-run on unrecognized tokens writes no glossary event file.

    The fixture project ships no `.kittify/glossaries/*.yaml` seed, so every
    token in the request is unrecognized by the index -- the exact scenario
    that would persist a TermCandidateObserved event under real dispatch.
    The in-memory scan still runs (glossary_observations is populated); only
    the persisted write is suppressed.
    """
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    glossary_events_dir = project / ".kittify" / "events" / "glossary"
    before = _snapshot_dir(glossary_events_dir)

    envelope: dict[str, Any] = {}
    for _ in range(3):
        result = _run_with_registry(
            project,
            ["dispatch", "implement the frobnicator payment module", "--dry-run", "--json"],
            _implementer_registry(),
        )
        assert result.exit_code == 0, result.output
        envelope = json.loads(result.output)

    after = _snapshot_dir(glossary_events_dir)
    assert after == before
    assert envelope["glossary_observations"] is not None
    assert envelope["glossary_observations"]["tokens_checked"] > 0


def test_dry_run_does_not_submit_to_saas_propagator(tmp_path: Path) -> None:
    """Third named suppressed-write surface: the SaaS propagator's submit()
    is never called across N --dry-run invocations."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    mock_propagator = MagicMock()
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch("specify_cli.cli.commands.dispatch.ProfileRegistry", return_value=_implementer_registry()),
        patch("specify_cli.cli.commands.dispatch.InvocationSaaSPropagator", return_value=mock_propagator),
        patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX),
    ):
        for _ in range(3):
            result = runner.invoke(cli_app, ["dispatch", "implement the payment module", "--dry-run", "--json"])
            assert result.exit_code == 0, result.output

    mock_propagator.submit.assert_not_called()


def test_dry_run_payload_shape(tmp_path: Path) -> None:
    """Dry-run payload carries status/profile_id/action/router_confidence,
    and drops invocation_id/close_contract entirely (nothing to close)."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--dry-run", "--json"],
    )
    assert envelope["status"] == "dry_run"
    assert "invocation_id" not in envelope
    assert "close_contract" not in envelope
    assert envelope["profile_id"] == "implementer-fixture"
    assert envelope["action"]
    assert envelope["router_confidence"] == "exact"


def test_dry_run_profile_hint_returns_exact_confidence(tmp_path: Path) -> None:
    """FR-008: --dry-run --profile <id> mirrors real dispatch's explicit-hint
    behavior minus the writes -- router_confidence exact, alternatives empty."""
    project = _setup_project(tmp_path)
    envelope = _invoke_json(
        project,
        ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--dry-run", "--json"],
    )
    assert envelope["router_confidence"] == "exact"
    assert envelope["alternatives"] == []


def test_dry_run_under_empty_charter_fallback(tmp_path: Path) -> None:
    """FR-010: --dry-run under a wholly-empty charter surfaces the same
    generic-agent fallback signal as real dispatch (research.md Decision 2/3)."""
    project = _setup_project(tmp_path)

    envelope = _invoke_json(project, ["dispatch", "implement the payment module", "--dry-run", "--json"])

    assert envelope["status"] == "dry_run"
    assert envelope["profile_id"] == "generic-agent"
    assert envelope["router_confidence"] == "generic_fallback"
    assert envelope["action"] == "implement"
    assert envelope["empty_charter_fallback"] is True


def test_dry_run_ambiguous_returns_dry_run_payload_not_exit_1(tmp_path: Path) -> None:
    """FR-009: --dry-run on a ROUTER_AMBIGUOUS request does NOT raise -- it
    exits 0 with profile_id/action null, router_confidence "ambiguous", and
    every tied candidate in `alternatives` (each carrying a confidence key)."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the feature", "--dry-run", "--json"],
        _tied_implementers_registry(),
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "dry_run"
    assert envelope["profile_id"] is None
    assert envelope["action"] is None
    assert envelope["router_confidence"] == "ambiguous"
    candidate_ids = {c["profile_id"] for c in envelope["alternatives"]}
    assert candidate_ids == {"implementer-a", "implementer-b"}
    for candidate in envelope["alternatives"]:
        assert candidate["confidence"]


def test_dry_run_no_match_still_raises(tmp_path: Path) -> None:
    """FR-009: ROUTER_NO_MATCH still exits 1 under --dry-run -- no partial
    signal worth reporting."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "help me", "--dry-run", "--json"],
        _implementer_registry(),
    )

    assert result.exit_code == 1
    error_obj = json.loads(result.output)
    assert error_obj["error"] == "routing_failed"
    assert error_obj["error_code"] == "ROUTER_NO_MATCH"


def test_dry_run_unknown_profile_still_raises(tmp_path: Path) -> None:
    """FR-009: an unknown --profile still exits 1 under --dry-run -- there is
    no profile to describe."""
    project = _setup_project(tmp_path)

    result = _run(
        project,
        ["dispatch", "implement", "--profile", "nonexistent-profile", "--dry-run", "--json"],
    )

    assert result.exit_code == 1
    error_obj = json.loads(result.output)
    assert error_obj["error"] == "routing_failed"
    assert error_obj["error_code"] == "PROFILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP2/#3840 — RouterDecision.alternatives threaded onto real dispatch too
# (FR-005, SC-003), and the WP01-002 review finding: --dry-run must respect
# --json/no --json parity with real dispatch (cli-do-output.md's own
# `[--json]` optional-bracket notation), instead of always emitting raw JSON.
# ---------------------------------------------------------------------------


def _tiebreak_registry() -> MagicMock:
    """implementer-fixture wins via routing_priority (pre-WP03); reviewer-fixture
    loses via a domain-keyword-only match on a token ("gizmo") that is not in
    CANONICAL_VERB_MAP, so it is a genuine domain_keyword candidate, not
    verb-shadowed."""
    return _make_mock_registry(
        [
            {
                "profile_id": "implementer-fixture",
                "role_value": "implementer",
                "routing_priority": 80,
                "domain_keywords": [],
            },
            {
                "profile_id": "reviewer-fixture",
                "role_value": "reviewer",
                "routing_priority": 10,
                "domain_keywords": ["gizmo"],
            },
        ]
    )


def test_dispatch_real_alternatives_nonempty_on_two_candidate_tiebreak(tmp_path: Path) -> None:
    """SC-003 (WP2/#3840): real (non-dry-run) dispatch --json on a two-candidate
    request also threads a non-empty alternatives list -- proving the field
    threads onto the real dispatch path, not only dry-run."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement and gizmo the module", "--json"],
        _tiebreak_registry(),
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["profile_id"] == "implementer-fixture"
    assert envelope["alternatives"]
    alt = envelope["alternatives"][0]
    assert alt["profile_id"] == "reviewer-fixture"
    assert alt["confidence"] == "domain_keyword"
    assert alt["action"]
    assert alt["match_reason"]


def test_dispatch_real_alternatives_render_in_rich_console_output(tmp_path: Path) -> None:
    """PR-BOUNDARY-002 (mission dispatch-dry-run-route-only-01M1HKV2): the real
    (Op-opening) rich-console path must render ``RouterDecision.alternatives``
    on a two-candidate tiebreak too, matching what a machine consumer already
    sees in the same call's ``--json`` envelope (see
    test_dispatch_real_alternatives_nonempty_on_two_candidate_tiebreak). Before
    the fix, only the ``--dry-run`` rich renderer printed this block --
    plain ``spec-kitty dispatch "<request>"`` silently dropped it, an unforced
    asymmetry the pre-merge squad's structural-coherence lens caught."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement and gizmo the module"],
        _tiebreak_registry(),
    )

    assert result.exit_code == 0, result.output
    assert "Profile:" in result.output
    assert "Alternatives considered (1):" in result.output
    assert "reviewer-fixture" in result.output
    assert "domain_keyword" in result.output


def test_dry_run_without_json_renders_rich_output_not_raw_json(tmp_path: Path) -> None:
    """WP01-002 review finding: --dry-run without --json must render the rich
    console capsule (parity with real dispatch's json_output branch), not
    raw JSON -- cli-do-output.md's own `[--json]` optional-bracket notation
    implies a non-JSON mode exists."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the payment module", "--dry-run"],
        _implementer_registry(),
    )

    assert result.exit_code == 0, result.output
    assert "Profile:" in result.output
    assert "Dry run" in result.output
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


def test_dry_run_with_json_still_emits_json_envelope(tmp_path: Path) -> None:
    """WP01-002 regression guard: --dry-run --json keeps emitting the raw JSON
    envelope (unchanged from WP01) once the branch starts reading json_output."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the payment module", "--dry-run", "--json"],
        _implementer_registry(),
    )

    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "dry_run"


def test_dry_run_ambiguous_without_json_renders_rich_output(tmp_path: Path) -> None:
    """WP01-002 extends to the ROUTER_AMBIGUOUS dry-run branch too -- also an
    exit-0 "success-shaped" payload (FR-009), so it must respect json_output
    the same way the plain-success branch does."""
    project = _setup_project(tmp_path)
    _write_configured_charter(project)
    result = _run_with_registry(
        project,
        ["dispatch", "implement the feature", "--dry-run"],
        _tied_implementers_registry(),
    )

    assert result.exit_code == 0, result.output
    assert "ambiguous" in result.output.lower()
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)


# ---------------------------------------------------------------------------
# #4123: never-git-init-ed projects (spec-kitty init without git init)
#
# Unlike every other test in this file, these deliberately do NOT patch
# ``build_charter_context`` — the real chain (executor ->
# _resolve_routing_and_context -> build_charter_context ->
# ensure_charter_bundle_fresh -> resolve_canonical_repo_root) is what
# escaped as a raw NotInsideRepositoryError traceback in the field.
# ---------------------------------------------------------------------------


def test_dispatch_non_git_project_exits_1_with_git_init_advice(tmp_path: Path) -> None:
    """Real charter resolution on a non-git project degrades to the
    actionable git-init message instead of a raw traceback (#4123)."""
    project = _setup_project(tmp_path)

    with patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project):
        result = runner.invoke(
            cli_app,
            ["dispatch", "implement the feature", "--profile", "implementer-fixture"],
        )

    assert result.exit_code == 1
    assert "not inside a git repository" in result.output
    assert "git init" in result.output
    # The old failure mode: the exception itself reached the runner.
    from charter.resolution import NotInsideRepositoryError

    assert not isinstance(result.exception, NotInsideRepositoryError)


def test_dispatch_non_git_project_json_envelope_is_parseable(tmp_path: Path) -> None:
    """``--json`` keeps one machine-parseable error envelope on the same
    failure (#4123)."""
    project = _setup_project(tmp_path)

    with patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project):
        result = runner.invoke(
            cli_app,
            ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--json"],
        )

    assert result.exit_code == 1
    error_obj = json.loads(result.output)
    # R22 (#5258, 45303ca90): adopted the canonical `json_error()` contract
    # (`{"ok": False, "error": {"code": ..., "message": ...}}`) instead of the
    # retired flat `{"error": <code>, "message": ...}` shape.
    assert error_obj["ok"] is False
    assert error_obj["error"]["code"] == "git_resolution_failed"
    assert "git init" in error_obj["error"]["message"]


def test_dispatch_dry_run_non_git_project_exits_1_with_git_init_advice(tmp_path: Path) -> None:
    """The --dry-run path shares the same escape route and the same
    actionable exit (#4123)."""
    project = _setup_project(tmp_path)

    with patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project):
        result = runner.invoke(
            cli_app,
            ["dispatch", "implement the feature", "--profile", "implementer-fixture", "--dry-run"],
        )

    assert result.exit_code == 1
    assert "not inside a git repository" in result.output
    assert "git init" in result.output


# ---------------------------------------------------------------------------
# #6990 SC-002 — the printed fetch command must reproduce the omitted text
#
# Unlike every other test in this file, this one does NOT mock
# ``build_charter_context``: it renders real governance text for one fixture
# through BOTH real CLI surfaces (``spec-kitty dispatch --brief`` and the
# ``spec-kitty charter context`` command the reference prints) and compares
# them. That is the only way to catch the two call shapes drifting apart —
# the executor passes ``profile=``/``mark_loaded=False``/
# ``suppress_project_resolver=``, the charter CLI passes
# ``profile=``/``mark_loaded=False``/``org_root=None``/``mission_type=None``.
# Dropping ``--profile`` from the printed command (or from the CLI wiring)
# makes the fetched text lose the profile-cited block and this test fails.
# ---------------------------------------------------------------------------

_REAL_RENDER_GRAPH = """\
schema_version: "1.0"
generated_at: "2026-04-13T10:00:00+00:00"
generated_by: "test"
nodes:
  - urn: "action:software-dev/implement"
    kind: action
    label: implement
  - urn: "directive:DIRECTIVE_001"
    kind: directive
    label: Architectural Integrity Standard
edges:
  - source: "action:software-dev/implement"
    target: "directive:DIRECTIVE_001"
    relation: scope
"""


def _write_real_render_project(tmp_path: Path) -> Path:
    """A minimal project whose real charter render includes profile-cited doctrine."""
    project = tmp_path / "repo"
    charter_dir = project / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Project Charter\n\n## Policy Summary\n\n- Intent: deterministic delivery\n", encoding="utf-8")
    (charter_dir / "governance.yaml").write_text(
        "doctrine:\n  template_set: software-dev-default\n  selected_paradigms: []\n  selected_directives: []\n  available_tools: []\n",
        encoding="utf-8",
    )
    (charter_dir / "references.yaml").write_text('schema_version: "1.0.0"\nreferences: []\n', encoding="utf-8")
    (project / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    # Real charter-context resolution shells out to git (bundle freshness), so
    # the fixture must be a repository; ``find_repo_root`` is still patched.
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    return project


@pytest.mark.git_repo
def test_brief_fetch_command_reproduces_the_embedded_text_byte_for_byte(tmp_path: Path) -> None:
    """SC-002/A2: the reference resolves to exactly the text it replaced."""
    import shlex
    from io import StringIO

    from charter.activation.profile_resolution import _reset_agent_profile_cache
    from charter.offering.drg.models import DRGGraph
    from specify_cli.cli.commands.charter import charter_app
    from typer.testing import CliRunner as _CliRunner
    from ruamel.yaml import YAML

    import specify_cli.cli.commands.charter as charter_pkg

    project = _write_real_render_project(tmp_path)
    graph = DRGGraph.model_validate(YAML(typ="safe").load(StringIO(_REAL_RENDER_GRAPH)))
    _reset_agent_profile_cache()

    request = "implement the login handler"
    profile = "python-pedro"
    with (
        patch("specify_cli.cli.commands.dispatch.find_repo_root", return_value=project),
        patch.object(charter_pkg, "find_repo_root", return_value=project),
        patch("charter.offering.drg.loader.load_graph", return_value=graph),
        patch("charter.activation.catalog.resolve_offering_root", return_value=tmp_path),
        patch("charter.offering.drg.validator.assert_valid"),
    ):
        full = json.loads(
            runner.invoke(cli_app, ["dispatch", request, "--profile", profile, "--dry-run", "--json"]).output
        )
        brief = json.loads(
            runner.invoke(cli_app, ["dispatch", request, "--profile", profile, "--dry-run", "--json", "--brief"]).output
        )
        fetch_command = str(brief["governance_context_reference"]["fetch_command"])
        # The profile is what makes the fetched text the omitted text.
        assert "--profile" in fetch_command
        fetched = json.loads(_CliRunner().invoke(charter_app, shlex.split(fetch_command)[2:]).output)

    embedded = full["governance_context_text"]
    # Non-vacuity: a real render with the profile-cited block, not an empty string.
    assert "Profile-Cited Directives" in embedded
    assert embedded == fetched["text"]
    assert brief["governance_context_reference"]["digest"] == full["governance_context_hash"]
    assert brief["governance_context_reference"]["bytes"] == len(embedded.encode("utf-8"))
    # Fetching must not record a first-load for the action it renders.
    assert not (project / ".kittify" / "charter" / "context-state.json").exists()
