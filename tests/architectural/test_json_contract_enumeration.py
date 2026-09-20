"""G0/G1: registered JSON boundaries, frozen triage, and real empty results.

This is deliberately a command-contract test, not an implementation-shape test.
Resolved Click metadata preserves Typer binding and every registration alias.
"""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner, Result
from typer.main import get_command

pytestmark = pytest.mark.architectural


def walk_commands(command: click.Command, path: str = "", ancestors: tuple[int, ...] = ()) -> Iterator[tuple[str, click.Command]]:
    """Ancestor-only cycle protection keeps aliases of the same group visible."""
    assert id(command) not in ancestors, f"Command graph cycle at {path}"
    yield path, command
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            yield from walk_commands(child, f"{path} {name}".strip(), (*ancestors, id(command)))


def json_commands(root: click.Command) -> dict[str, click.Command]:
    return {
        path: command
        for path, command in walk_commands(root)
        if any(isinstance(p, click.Option) and "--json" in p.opts and isinstance(p.type, click.types.BoolParamType) for p in command.params)
    }


@pytest.fixture(scope="module")
def graph() -> click.Command:
    # Do not inherit pytest argv or a live-work reduced registration surface.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["spec-kitty"])
        import specify_cli

        return get_command(specify_cli.app)


@pytest.fixture()
def outside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["spec-kitty"])
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "runtime"))
    (tmp_path / "home").mkdir()
    return tmp_path


def assert_json_result(result: Result, *, adopted: bool, exit_code: int) -> Any:
    assert result.exit_code == exit_code, (result.output, repr(result.exception))
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
    assert "Usage:" not in result.stderr, result.stderr
    assert "Traceback" not in result.output, result.output
    payload = json.loads(result.stdout)
    if adopted:
        assert isinstance(payload, dict) and payload.get("ok") is False, payload
        error = payload.get("error")
        assert isinstance(error, dict), payload
        assert isinstance(error.get("code"), str) and error["code"], payload
        assert isinstance(error.get("message"), str) and error["message"], payload
    return payload


def test_real_zero_wp_status(graph: click.Command, outside: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(outside)], check=True)
    (outside / ".kittify").mkdir()
    (outside / ".kittify/config.yaml").write_text("{}\n", encoding="utf-8")
    slug = "empty-contract-01M2NQCB"
    mission = outside / "kitty-specs" / slug
    (mission / "tasks").mkdir(parents=True)
    (mission / "meta.json").write_text(json.dumps({"mission_slug": slug, "mission_type": "software-dev", "target_branch": "main"}), encoding="utf-8")
    from tests.architectural.test_cli_placeholder_output import isolate_global_io

    isolate_global_io(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "agent", "tasks", "status", "--json"])
    result = CliRunner().invoke(graph, ["agent", "tasks", "status", "--mission", slug, "--json"])
    payload = assert_json_result(result, adopted=False, exit_code=0)
    assert "error" not in payload
    assert payload["total_wps"] == 0 and payload["work_packages"] == [] and payload["stale_verdicts"] == []


# Frozen, reviewed G0 inventory; additions MUST be classified explicitly.
# Each tuple is (valid parsed arguments, exit code, real fixture).
# Read-only total-result cases are marked total, not mislabeled as error arms.
ADOPTED: dict[str, tuple[tuple[str, ...], int, str]] = {
    "agent tasks status": ((), 1, "outside"),
    "archive create": (("missing", "--by", "missing", "--reason", "missing"), 2, "outside"),
    "archive list": ((), 2, "outside"),
    "charter mission-type list": ((), 1, "badconfig"),
    "context info": ((), 1, "outside"),
    "context list": ((), 1, "outside"),
    "context mission-resolve": (("--wp", "missing"), 1, "outside"),
    "context mission-show": (("--context", "missing"), 1, "outside"),
    "dashboard": ((), 1, "outside"),
    "doctor command-files": ((), 1, "outside"),
    "doctor contracts": ((), 2, "outside"),
    "doctor coordination": ((), 1, "outside"),
    "doctor cutover": ((), 1, "outside"),
    "doctor doctrine": ((), 1, "outside"),
    "doctor env-file": ((), 1, "outside"),
    "doctor identity": ((), 1, "outside"),
    "doctor invocation-pairing": ((), 1, "outside"),
    "doctor mission-state": (("--audit",), 1, "outside"),
    "doctor mission-type": ((), 1, "outside"),
    "doctor ops": ((), 1, "outside"),
    "doctor provenance": ((), 1, "outside"),
    "doctor review-cycle-reconcile": ((), 1, "outside"),
    "doctor shim-registry": ((), 2, "outside"),
    "doctor skills": ((), 2, "outside"),
    "doctor state-roots": ((), 1, "outside"),
    "doctor tool-surfaces": ((), 2, "outside"),
    "doctor topology": ((), 1, "outside"),
    "doctor workspaces": ((), 1, "outside"),
    "doctrine mission-type list": ((), 1, "badconfig"),
    "glossary conflicts": (("--strictness", "invalid"), 1, "outside"),
    "glossary list": ((), 1, "outside"),
    "glossary validate": (("missing",), 2, "outside"),
    "materialize": ((), 1, "outside"),
    "mission close": ((), 1, "outside"),
    "mission follow-up": (("missing", "--pr", "1"), 1, "outside"),
    "mission list": ((), 1, "badconfig"),
    "mission reopen": (("missing", "--reason", "missing"), 1, "outside"),
    "mission run": (("missing", "--mission", "missing"), 1, "outside"),
    "mission show": (("missing",), 1, "outside"),
    "mission-type close": ((), 1, "outside"),
    "mission-type follow-up": (("missing", "--pr", "1"), 1, "outside"),
    "mission-type list": ((), 1, "badconfig"),
    "mission-type reopen": (("missing", "--reason", "missing"), 1, "outside"),
    "mission-type run": (("missing", "--mission", "missing"), 1, "outside"),
    "mission-type show": (("missing",), 1, "outside"),
    "verify-setup": ((), 1, "outside"),
}

PARSEABLE: dict[str, tuple[tuple[str, ...], int, str]] = {
    "accept": ((), 1, "outside"),
    "agent acceptance-verdict": (("--mission", "missing"), 2, "outside"),
    "agent check-prerequisites": ((), 1, "outside"),
    "agent context resolve": (("--action", "missing"), 1, "outside"),
    "agent issue-verdict": (("--mission", "missing", "--issue", "1", "--verdict", "in-mission", "--actor", "missing"), 1, "outside"),
    "agent mission accept": ((), 1, "outside"),
    "agent mission acceptance-verdict": (("--mission", "missing"), 2, "outside"),
    "agent mission branch-context": ((), 1, "outside"),
    "agent mission check-prerequisites": ((), 1, "outside"),
    "agent mission create": (("missing",), 1, "outside"),
    "agent mission finalize-tasks": ((), 1, "outside"),
    "agent mission record-analysis": ((), 1, "outside"),
    "agent mission setup-plan": ((), 1, "outside"),
    "agent status emit": (("missing", "--to", "missing", "--actor", "missing"), 1, "outside"),
    "agent status materialize": ((), 1, "outside"),
    "agent status migrate": ((), 1, "outside"),
    "agent status reconcile": ((), 1, "outside"),
    "agent status validate": ((), 1, "outside"),
    "agent tasks add-history": (("missing", "--note", "missing"), 1, "outside"),
    "agent tasks check-terminability": ((), 1, "outside"),
    "agent tasks finalize-tasks": ((), 1, "outside"),
    "agent tasks list-tasks": ((), 1, "outside"),
    "agent tasks map-requirements": ((), 1, "outside"),
    "agent tasks mark-status": (("missing", "--status", "missing"), 1, "outside"),
    "agent tasks move-task": (("missing", "--to", "missing"), 1, "outside"),
    "agent tasks validate-workflow": (("missing",), 1, "outside"),
    "agent tracer-append": (("--mission", "missing", "--category", "missing", "--entry", "missing", "--actor", "missing"), 1, "outside"),
    "auth doctor": ((), 1, "outside"),
    "charter bundle validate": ((), 2, "outside"),
    "charter context": ((), 1, "outside"),
    "charter generate": ((), 1, "outside"),
    "charter interview": ((), 1, "outside"),
    "charter lint": ((), 1, "outside"),
    "charter list": ((), 1, "badconfig"),
    "charter pack apply": (("missing",), 1, "outside"),
    "charter pack list": ((), 0, "total"),
    "charter pack path": (("missing",), 1, "outside"),
    "charter resynthesize": ((), 1, "outside"),
    "charter status": ((), 1, "outside"),
    "charter sync": ((), 1, "outside"),
    "charter synthesize": ((), 1, "outside"),
    "doctor bytecode": ((), 1, "corrupt-bytecode"),
    "doctor channel": ((), 0, "total"),
    "doctrine asset list": ((), 0, "total"),
    "doctrine asset path": (("missing",), 1, "outside"),
    "doctrine pack assemble": (("missing", "missing"), 1, "outside"),
    "doctrine pack validate": (("missing",), 1, "outside"),
    "implement": (("missing",), 2, "outside"),
    "issue-matrix migrate": ((), 1, "outside"),
    "lint": (("missing.py",), 1, "outside"),
    "migrate backfill-provenance": (("--dry-run",), 1, "badmatrix"),
    "migrate charter-encoding": (("--dry-run",), 1, "badencoding"),
    "moments status": ((), 0, "total"),
    "plan": ((), 1, "outside"),
    "reconcile": (("--mission", "missing"), 2, "outside"),
    "safe-commit": (("missing", "--message", "missing"), 1, "outside"),
    "spec-commit": (("missing", "--message", "missing"), 1, "outside"),
    "specify": (("missing",), 1, "outside"),
    "tasks": ((), 1, "outside"),
    "tracker providers": ((), 0, "total"),
    "upgrade": (("--project", "--dry-run"), 1, "outside"),
    "zeitgeist operability drill-timeout": ((), 0, "loopback-refused"),
    "zeitgeist outbox list": ((), 0, "total"),
}

# G0 clarification: total/read-only result commands exercise real result arms.
# Do not invent a domain error or label them nonparseable merely for lacking one.
TOTAL_RESULT_EVIDENCE: dict[str, str] = {
    "charter pack list": "charter/pack.py:69; fixed built-in pack catalog; no modeled domain-error arm",
    "doctor channel": "_channel_doctor.py:63; total environment-channel report; no modeled error arm",
    "doctrine asset list": "_doctrine_asset.py:125; read-only catalog enumeration; empty catalog is a result",
    "moments status": "moments.py:91; effective local policy snapshot; no external operation",
    "tracker providers": "tracker.py:549; fixed provider roster; no modeled domain-error arm",
    "zeitgeist outbox list": "zeitgeist.py:532; local pending-item query; empty collection is success",
    "zeitgeist operability drill-timeout": "zeitgeist.py:690; offline failure drill; transport refusal is structured result data",
}


# Baseline domain failures, not exemptions generated from today's failures.
# All entries tracked by https://github.com/spec-kitty/spec-kitty/issues/4664.
# Evidence names actual production boundary + observed stream/exception.
DEFERRED: dict[str, tuple[tuple[str, ...], str, str]] = {
    "agent decision cancel": (
        ("missing", "--mission", "missing", "--rationale", "missing"),
        "outside",
        "decision.py:401; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent decision defer": (
        ("missing", "--mission", "missing", "--rationale", "missing"),
        "outside",
        "decision.py:353; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent decision list": (
        ("--mission", "missing"),
        "outside",
        "decision.py:545; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent decision open": (
        ("--mission", "missing", "--flow", "missing", "--input-key", "missing", "--question", "missing"),
        "outside",
        "decision.py:217; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent decision resolve": (
        ("missing", "--mission", "missing", "--final-answer", "missing"),
        "outside",
        "decision.py:310; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent decision verify": (
        ("--mission", "missing"),
        "outside",
        "decision.py:449; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "agent profile get": (
        ("missing",),
        "outside",
        "profiles_cmd.py:316; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "agent profile list": (
        (),
        "outside",
        "profiles_cmd.py:130; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "agent profile show": (
        ("missing",),
        "outside",
        "profiles_cmd.py:316; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "agent release prep": (
        ("--channel", "stable"),
        "outside",
        "agent/release.py:100; empty stdout; unhandled FileNotFoundError; Follow-up: #4664",
    ),
    "agent retrospect summary": (
        (),
        "outside",
        "agent_retrospect.py:684; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "agent retrospect synthesize": (
        ("--mission", "missing"),
        "outside",
        "agent_retrospect.py:349; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "agent status doctor": (
        (),
        "outside",
        "agent/status.py:566; human diagnostic on stdout; Follow-up: #4664",
    ),
    "agent status lifecycle": (
        (),
        "outside",
        "agent/status.py:704; human diagnostic on stdout; Follow-up: #4664",
    ),
    "agent tasks list-dependents": (
        ("missing",),
        "outside",
        "agent/tasks.py:1329; missing project prints two concatenated JSON objects to stdout; Follow-up: #4664",
    ),
    "agent tests stale-check": (
        ("--base", "missing"),
        "outside",
        "agent/tests.py:44; empty stdout; unhandled RuntimeError; Follow-up: #4664",
    ),
    "charter pack consistency-check": (
        (),
        "badconfig",
        "charter/pack.py:37; empty stdout; unhandled CharterPackConfigError; Follow-up: #4664",
    ),
    "charter preflight": (
        (),
        "outside",
        "charter_runtime/preflight/cli.py:40; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "cutover-guard": (
        ("--base-ref", "missing"),
        "outside",
        "cutover_guard.py:288; valid --base-ref; missing project emits only stderr diagnostic; Follow-up: #4664",
    ),
    "dispatch": (
        ("missing", "--dry-run"),
        "outside",
        "dispatch.py:369; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "docs query": (
        ("missing",),
        "outside",
        "docs.py:175; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "doctrine regenerate-graph": (
        ("--check",),
        "emptydoctrine",
        "doctrine.py:245; human diagnostic on stdout; Follow-up: #4664",
    ),
    "events tail": (
        ("--mission", "missing"),
        "outside",
        "events.py:64; empty stdout; error JSON on stderr; Follow-up: #4664",
    ),
    "invocations list": (
        (),
        "outside",
        "invocations_cmd.py:377; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "issue-search": (
        ("--provider", "missing", "--query", "missing"),
        "outside",
        "tracker.py:522; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "merge": (
        (),
        "outside",
        "merge.py:525; human diagnostic on stdout; Follow-up: #4664",
    ),
    "migrate backfill-identity": (
        (),
        "outside",
        "migrate_cmd.py:225; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate backfill-merge-commit": (
        ("--mission", "missing", "--merge-commit", "missing"),
        "outside",
        "migrate_cmd.py:375; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate backfill-mission-type": (
        (),
        "outside",
        "migrate_cmd.py:670; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate backfill-runtime-state": (
        (),
        "outside",
        "migrate_cmd.py:1109; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate backfill-topology": (
        (),
        "outside",
        "migrate_cmd.py:570; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate normalize-lifecycle": (
        (),
        "outside",
        "migrate_cmd.py:935; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate rebaseline-dossier-hashes": (
        (),
        "outside",
        "migrate_cmd.py:1184; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate repin-hooks": (
        (),
        "outside",
        "migrate_cmd.py:1251; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "migrate rewrite-opposed-by": (
        ("--pack", "missing", "--dry-run"),
        "outside",
        "migrate_cmd.py:988; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "next": (
        (),
        "outside",
        "next_cmd.py:120; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "profile-invocation complete": (
        ("--invocation-id", "missing", "--outcome", "done"),
        "outside",
        "profile_invocation.py:100; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "profiles get": (
        ("missing",),
        "outside",
        "profiles_cmd.py:316; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "profiles list": (
        (),
        "outside",
        "profiles_cmd.py:130; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "profiles show": (
        ("missing",),
        "outside",
        "profiles_cmd.py:316; empty stdout; unhandled TaskCliError; Follow-up: #4664",
    ),
    "regen": (
        ("--check",),
        "empty-templates",
        "regen.py:165; valid --check; empty template tree raises domain BadParameter before rendering; Follow-up: #4664",
    ),
    "retrospect backfill": (
        (),
        "outside",
        "retrospect.py:600; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "retrospect create": (
        ("--mission", "missing"),
        "outside",
        "retrospect.py:248; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "retrospect summary": (
        (),
        "outside",
        "retrospect.py:901; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "routes": (
        (),
        "outside",
        "routes.py:125; human diagnostic on stdout; Follow-up: #4664",
    ),
    "tracker discover": (
        ("--provider", "missing"),
        "outside",
        "tracker.py:592; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "tracker list-tickets": (
        ("--provider", "missing"),
        "outside",
        "tracker.py:1150; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "tracker map list": (
        (),
        "outside",
        "tracker.py:1100; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "tracker status": (
        (),
        "outside",
        "tracker.py:930; empty stdout; human diagnostic on stderr; Follow-up: #4664",
    ),
    "tracker sync publish": (
        (),
        "outside",
        "tracker.py:1347; empty stdout; unhandled TrackerConfigError; Follow-up: #4664",
    ),
    "tracker sync pull": (
        (),
        "outside",
        "tracker.py:1174; empty stdout; unhandled TrackerConfigError; Follow-up: #4664",
    ),
    "tracker sync push": (
        (),
        "outside",
        "tracker.py:1218; empty stdout; unhandled TrackerConfigError; Follow-up: #4664",
    ),
    "tracker sync run": (
        (),
        "outside",
        "tracker.py:1303; empty stdout; unhandled TrackerConfigError; Follow-up: #4664",
    ),
    "zeitgeist activity": (
        (),
        "outside",
        "zeitgeist.py:289; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist inbox": (
        (),
        "outside",
        "zeitgeist.py:464; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist operability drill-rollback": (
        (),
        "outside",
        "zeitgeist.py:717; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist operability drill-rotation": (
        (),
        "outside",
        "zeitgeist.py:703; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist operability report": (
        (),
        "outside",
        "zeitgeist.py:676; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist outbox show": (
        ("missing",),
        "outside",
        "zeitgeist.py:564; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist read": (
        (),
        "outside",
        "zeitgeist.py:441; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist reply": (
        ("missing", "missing"),
        "outside",
        "zeitgeist.py:405; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist send": (
        ("missing", "missing"),
        "outside",
        "zeitgeist.py:378; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist status": (
        (),
        "outside",
        "zeitgeist.py:157; human diagnostic on stdout; Follow-up: #4664",
    ),
    "zeitgeist watch": (
        (),
        "outside",
        "zeitgeist.py:194; human diagnostic on stdout; Follow-up: #4664",
    ),
}


def assert_inventory(root: click.Command) -> None:
    actual = set(json_commands(root))
    known = set(ADOPTED) | set(PARSEABLE) | set(DEFERRED)
    assert not (set(ADOPTED) & set(PARSEABLE) or set(ADOPTED) & set(DEFERRED) or set(PARSEABLE) & set(DEFERRED))
    assert actual == known, f"Unclassified JSON registrations: {sorted(actual - known)}; removed: {sorted(known - actual)}"
    total_cases = {name for name, (_args, _exit, fixture) in PARSEABLE.items() if fixture in {"total", "loopback-refused"}}
    assert total_cases == set(TOTAL_RESULT_EVIDENCE)
    assert all("Follow-up: #4664" in evidence for _args, _fixture, evidence in DEFERRED.values())


def test_all_json_registrations_are_classified(graph: click.Command) -> None:
    assert_inventory(graph)


def prepare_case(kind: str, directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert kind in {"outside", "total", "badconfig", "badmatrix", "badencoding", "emptydoctrine", "loopback-refused", "corrupt-bytecode"}, kind
    if kind == "corrupt-bytecode":
        # Trusted hash header + invalid marshal body: a real diagnostic finding,
        # independent of this interpreter's installed package cache condition.
        source = directory / "sample.py"
        source.write_text("value = 1\n", encoding="utf-8")
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir()
        cache.write_bytes(importlib.util.MAGIC_NUMBER + (1).to_bytes(4, "little") + bytes(8) + b"invalid marshal")
        monkeypatch.setattr("specify_cli.cli.commands._bytecode_doctor.package_root", lambda: directory)
    elif kind == "badconfig":
        (directory / ".kittify").mkdir()
        (directory / ".kittify/config.yaml").write_text("- invalid-root\n", encoding="utf-8")
    elif kind == "badmatrix":
        mission = directory / "kitty-specs/broken"
        mission.mkdir(parents=True)
        (mission / "acceptance-matrix.json").write_text("{broken", encoding="utf-8")
    elif kind == "badencoding":
        charter = directory / ".kittify/charter"
        charter.mkdir(parents=True)
        (charter / "charter.yaml").write_bytes(bytes(range(256)))
    elif kind == "emptydoctrine":
        # A real invalid pack; only its location is redirected, not validation.
        monkeypatch.setattr("specify_cli.cli.commands.doctrine._doctrine_root", lambda: directory)
    elif kind == "loopback-refused":
        # The command is itself an offline failure drill. Keep its production
        # transport/error handling but avoid opening even a loopback connection.
        def refuse(*_args: Any, **_kwargs: Any) -> None:
            raise ConnectionRefusedError("isolated loopback drill")

        monkeypatch.setattr("socket.socket.connect", refuse)


@pytest.mark.parametrize("path", sorted(set(ADOPTED) | set(PARSEABLE)))
def test_parse_allowlist(graph: click.Command, outside: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    adopted = path in ADOPTED
    args, expected_exit, fixture = (ADOPTED | PARSEABLE)[path]
    prepare_case(fixture, outside, monkeypatch)
    command = json_commands(graph)[path]
    result = CliRunner().invoke(command, [*args, "--json"])
    assert_json_result(result, adopted=adopted, exit_code=expected_exit)
    if adopted:
        human = CliRunner().invoke(command, args)
        assert human.exit_code == expected_exit, (human.output, repr(human.exception))


@pytest.mark.parametrize(
    "path,args",
    [
        ("context list", ()),
        ("context list", ("--orphaned",)),
        ("glossary list", ()),
        ("glossary conflicts", ()),
        ("mission list", ()),
        ("mission-type list", ()),
        ("charter mission-type list", ()),
    ],
)
def test_real_empty_list_results(graph: click.Command, outside: Path, path: str, args: tuple[str, ...]) -> None:
    subprocess.run(["git", "init", "-q", str(outside)], check=True)
    (outside / ".kittify/glossaries").mkdir(parents=True)
    (outside / ".kittify/config.yaml").write_text("mission_type_activations: []\n", encoding="utf-8")
    result = CliRunner().invoke(json_commands(graph)[path], [*args, "--json"])
    assert assert_json_result(result, adopted=False, exit_code=0) == []


def test_root_preserves_json_stream(graph: click.Command, outside: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.architectural.test_cli_placeholder_output import isolate_global_io

    isolate_global_io(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "context", "info", "--json"])
    result = CliRunner().invoke(graph, ["context", "info", "--json"])
    assert_json_result(result, adopted=True, exit_code=1)


@pytest.mark.parametrize("mutation", ["prose", "wrong-envelope"])
def test_output_mutations_fail_same_guard(graph: click.Command, outside: Path, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    command = json_commands(graph)["context info"]
    original = command.callback
    assert original is not None

    def contaminated(*args: Any, **kwargs: Any) -> Any:
        if mutation == "prose":
            click.echo("progress before JSON")
            return original(*args, **kwargs)
        return original(*args, **kwargs)

    if mutation == "wrong-envelope":
        # Mutate the actual boundary's envelope dependency, retaining its
        # production callback, resolver, diagnostic choice and exit behavior.
        monkeypatch.setattr("specify_cli.cli.commands.context.json_error", lambda *_args, **_kwargs: {"error": "legacy flat error"})
    monkeypatch.setattr(command, "callback", contaminated)
    result = CliRunner().invoke(command, ["--json"])
    with pytest.raises((AssertionError, json.JSONDecodeError)):
        assert_json_result(result, adopted=True, exit_code=1)


def test_unclassified_registration_mutation_fails(graph: click.Command, monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(graph, click.Group)
    new_command = click.Command("future", params=[click.Option(["--json"], is_flag=True)])
    monkeypatch.setitem(graph.commands, "future", new_command)
    with pytest.raises(AssertionError, match="Unclassified JSON registrations.*future"):
        assert_inventory(graph)


def test_discovery_uses_flag_types_and_preserves_aliases() -> None:
    command = click.Command("leaf", params=[click.Option(["--json", "arbitrary_python_name"], is_flag=True)])
    misleading = click.Command("not-json", params=[click.Option(["--format", "json_output"]), click.Option(["--json"], type=str)])
    group = click.Group("g", commands={"leaf": command})
    paired = click.Command("paired", params=[click.Option(["--json/--no-json"], default=False)])
    root = click.Group(commands={"first": group, "alias": group, "not-json": misleading, "paired": paired})
    assert set(json_commands(root)) == {"first leaf", "alias leaf", "paired"}
