"""Cross-command pin: every owned refusal in ``--json`` mode is the C2 owned refusal.

#6353 / ADR ``2026-10-27-2`` (FR-015, SC-002, SC-004): one parametrized test
drives the same owned refusal through every in-scope command that has JSON
output and an ``--owned-checkout`` option, and asserts the exact contract of
``contracts/owned-refusal-envelope.md``: exit 1, one JSON object on stdout,
``{"ok": false, "error": {"code", "message"}}`` plus only the optional keys
``data-model.md`` lists for that command, no top-level ``error_code`` and no
write in either checkout.

The trigger every command shares is the cheapest owned refusal there is: the
claim names the repository root checkout, so ownership resolution refuses
with ``OWNED_CHECKOUT_IS_REPOSITORY_ROOT`` before any command body runs.

The same-fixture success control proves the probe reads real command output:
a valid ``--owned-checkout`` on the same fixture prints a success payload.

Out of the JSON matrix (research §1.3), each human-only because the command
has no JSON output: ``agent action implement`` / ``agent action review``
(row 17) and ``research`` (row 18). ``agent check-prerequisites`` (the
top-level alias) has no ``--owned-checkout`` option; its ``agent mission``
form is a parameter. The ``agent decision`` verbs' second owned refusal (the
ledger write-containment ``OWNED_MISSION_PATH_REFUSED`` raised after
resolution) is pinned by
``tests/specify_cli/cli/commands/test_decision_owned_checkout.py::test_owned_escaped_ledger_refuses``;
the move-task owned catch-all and the mark-status in-command owned failure
are pinned by their own command tests.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from specify_cli import app as cli_app
from tests.integration.conftest import OwnedCheckouts, _init_repo, _write_mission, _write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT.value
_SLUG = "owned-c2-01M5ZC20"
_MISSION_ID = "01M5ZC20000000000000000001"
_TARGET = "codex/owned"
_MARK_STATUS_CONTEXT_KEYS = frozenset({"state_applied", "event_ids", "applied_wps", "destination_ref", "status_events_path", "status_snapshot_path", "dirty"})


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture(scope="module")
def c2_checkouts(tmp_path_factory: pytest.TempPathFactory) -> OwnedCheckouts:
    """One module-scoped R/P/S triple, built from the shared integration factory helpers."""
    base = tmp_path_factory.mktemp("owned-c2")
    r_root = base / "primary"
    _init_repo(r_root)
    p_root = base / "owned"
    _git(r_root, "worktree", "add", "-qb", _TARGET, str(p_root))
    sibling = base / "sibling"
    _git(r_root, "worktree", "add", "-qb", "codex/sibling", str(sibling))
    mission_dir = p_root / "kitty-specs" / _SLUG
    wp_ids = ("WP01",)
    _write_mission(mission_dir, mission_id=_MISSION_ID, slug=_SLUG, topology="single_branch", target_branch=_TARGET, wp_ids=wp_ids)
    _write_single_lane_manifest(mission_dir, mission_slug=_SLUG, mission_id=_MISSION_ID, target_branch=_TARGET, wp_ids=wp_ids)
    _git(p_root, "add", ".")
    _git(p_root, "commit", "-qm", "owned mission")
    return OwnedCheckouts(
        repository_root=r_root,
        owned_root=p_root,
        sibling=sibling,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        mid8=_MISSION_ID[:8],
        target_branch=_TARGET,
        mission_dir=mission_dir,
    )


@dataclass(frozen=True)
class RefusalCase:
    """One in-scope command: its argv (``{M}`` = Mission slug, ``{R}`` = claimed checkout)."""

    argv: tuple[str, ...]
    context_keys: frozenset[str] | None = None
    stamps_version: bool = False


_CASES: dict[str, RefusalCase] = {
    "agent issue-verdict": RefusalCase(
        ("agent", "issue-verdict", "--mission", "{M}", "--issue", "#1", "--verdict", "fixed", "--actor", "probe", "--owned-checkout", "{R}", "--json")
    ),
    "agent acceptance-verdict": RefusalCase(
        ("agent", "acceptance-verdict", "--mission", "{M}", "--criterion", "FR-001", "--result", "pass", "--actor", "probe", "--owned-checkout", "{R}", "--json")
    ),
    "agent mission acceptance-verdict": RefusalCase(
        (
            "agent",
            "mission",
            "acceptance-verdict",
            "--mission",
            "{M}",
            "--criterion",
            "FR-001",
            "--result",
            "pass",
            "--actor",
            "probe",
            "--owned-checkout",
            "{R}",
            "--json",
        )
    ),
    "agent context resolve": RefusalCase(
        ("agent", "context", "resolve", "--action", "implement", "--mission", "{M}", "--wp-id", "WP01", "--owned-checkout", "{R}", "--json")
    ),
    "next": RefusalCase(("next", "--mission", "{M}", "--owned-checkout", "{R}", "--json")),
    "agent mission setup-plan": RefusalCase(
        ("agent", "mission", "setup-plan", "--mission", "{M}", "--owned-checkout", "{R}", "--json"),
        context_keys=frozenset({"phase_complete"}),
        stamps_version=True,
    ),
    "agent mission finalize-tasks": RefusalCase(
        ("agent", "mission", "finalize-tasks", "--mission", "{M}", "--owned-checkout", "{R}", "--json"), stamps_version=True
    ),
    "agent mission check-prerequisites": RefusalCase(
        ("agent", "mission", "check-prerequisites", "--mission", "{M}", "--owned-checkout", "{R}", "--json"), stamps_version=True
    ),
    "agent mission record-analysis": RefusalCase(
        ("agent", "mission", "record-analysis", "--mission", "{M}", "--agent", "probe", "--owned-checkout", "{R}", "--json"), stamps_version=True
    ),
    "agent mission create": RefusalCase(("agent", "mission", "create", "c2-probe", "--owned-checkout", "{R}", "--json"), stamps_version=True),
    "agent tasks status": RefusalCase(("agent", "tasks", "status", "--mission", "{M}", "--owned-checkout", "{R}", "--json")),
    "agent tasks move-task": RefusalCase(("agent", "tasks", "move-task", "WP01", "--to", "doing", "--mission", "{M}", "--owned-checkout", "{R}", "--json")),
    "agent tasks mark-status": RefusalCase(
        ("agent", "tasks", "mark-status", "T001", "--status", "done", "--wp", "WP01", "--mission", "{M}", "--owned-checkout", "{R}", "--json"),
        context_keys=_MARK_STATUS_CONTEXT_KEYS,
    ),
    "agent tasks map-requirements": RefusalCase(
        ("agent", "tasks", "map-requirements", "--wp", "WP01", "--refs", "FR-001", "--mission", "{M}", "--owned-checkout", "{R}", "--json")
    ),
    "spec-commit": RefusalCase(
        ("spec-commit", "kitty-specs/{M}/spec.md", "-m", "probe", "--mission", "{M}", "--owned-checkout", "{R}", "--json"),
        context_keys=frozenset({"committed"}),
    ),
    "accept": RefusalCase(("accept", "--mission", "{M}", "--owned-checkout", "{R}", "--json")),
    "agent mission accept": RefusalCase(("agent", "mission", "accept", "--mission", "{M}", "--owned-checkout", "{R}", "--json")),
    "charter generate": RefusalCase(("charter", "generate", "--mission-handle", "{M}", "--owned-checkout", "{R}", "--json")),
    "dispatch": RefusalCase(("dispatch", "probe request", "--owned-checkout", "{R}", "--json")),
    "invocations list": RefusalCase(("invocations", "list", "--owned-checkout", "{R}", "--json")),
    "profile-invocation complete": RefusalCase(
        ("profile-invocation", "complete", "--invocation-id", "01M5ZC20000000000000000099", "--outcome", "done", "--owned-checkout", "{R}", "--json")
    ),
    # repair-runtime-lock has no ``--json`` flag: it always prints JSON.
    "agent decision repair-runtime-lock": RefusalCase(("agent", "decision", "repair-runtime-lock", "--mission", "{M}", "--owned-checkout", "{R}")),
    # The decision verbs print JSON by default (``--json`` is the default).
    "agent decision list": RefusalCase(("agent", "decision", "list", "--mission", "{M}", "--owned-checkout", "{R}")),
}


def _argv(case: RefusalCase, checkouts: OwnedCheckouts, claim: Path) -> list[str]:
    return [token.replace("{M}", checkouts.mission_slug).replace("{R}", str(claim)) for token in case.argv]


def _state(root: Path) -> tuple[str, str]:
    return _git(root, "rev-parse", "HEAD"), _git(root, "status", "--porcelain", "--untracked-files=all")


@contextlib.contextmanager
def _in(root: Path) -> Iterator[None]:
    with contextlib.chdir(root):
        yield


@pytest.mark.parametrize("command", sorted(_CASES))
def test_owned_refusal_is_c2_on_every_json_command(c2_checkouts: OwnedCheckouts, command: str) -> None:
    case = _CASES[command]
    c = c2_checkouts
    before = (_state(c.repository_root), _state(c.owned_root))
    with _in(c.repository_root):
        result = CliRunner().invoke(cli_app, _argv(case, c, c.repository_root))

    assert result.exit_code == 1, (result.stdout, result.stderr, result.exception)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert set(payload["error"]) == {"code", "message"}
    assert payload["error"]["code"] == _CODE
    assert isinstance(payload["error"]["message"], str) and payload["error"]["message"]
    expected_extra = ({"context"} if case.context_keys is not None else set()) | ({"spec_kitty_version"} if case.stamps_version else set())
    assert set(payload) - {"ok", "error"} == expected_extra
    assert "error_code" not in payload
    if case.context_keys is not None:
        assert set(payload["context"]) == case.context_keys
    assert "{" not in result.stderr, result.stderr
    assert (_state(c.repository_root), _state(c.owned_root)) == before


_SUCCESS_CONTROLS: dict[str, tuple[tuple[str, ...], str]] = {
    "agent tasks status": (("agent", "tasks", "status", "--mission", "{M}", "--owned-checkout", "{R}", "--json"), "work_packages"),
    "agent context resolve": (
        ("agent", "context", "resolve", "--action", "implement", "--mission", "{M}", "--wp-id", "WP01", "--owned-checkout", "{R}", "--json"),
        "success",
    ),
    "agent mission check-prerequisites": (
        ("agent", "mission", "check-prerequisites", "--mission", "{M}", "--owned-checkout", "{R}", "--json"),
        "spec_kitty_version",
    ),
}


@pytest.mark.parametrize("command", sorted(_SUCCESS_CONTROLS))
def test_valid_owned_checkout_on_the_same_fixture_succeeds(c2_checkouts: OwnedCheckouts, command: str) -> None:
    """SC-004 / FR-011: the probe sees real output; a valid claim prints no owned refusal."""
    argv, success_key = _SUCCESS_CONTROLS[command]
    c = c2_checkouts
    with _in(c.owned_root):
        result = CliRunner().invoke(cli_app, _argv(RefusalCase(argv), c, c.owned_root))

    assert result.exit_code == 0, (result.stdout, result.stderr, result.exception)
    payload = json.loads(result.stdout)
    assert payload.get("ok") is not False
    assert "error" not in payload
    assert success_key in payload
