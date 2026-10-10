"""#5874: orchestrator-api decision verbs retain validated owned-checkout authority.

Companion to ``tests/specify_cli/cli/commands/test_decision_owned_checkout.py``
(the host-CLI side). The repair branch ``codex/5874-owned-decisions`` fixed only
the host ``decision`` commands; this mission's WP01 extends the fix to the
``orchestrator-api`` decision verbs (operator decision D2), so an owned
single_branch mission resolves and writes under the owned checkout here too.
"""

from __future__ import annotations

import contextlib
import json

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from tests.integration.conftest import OwnedCheckouts, make_owned_checkouts, owned_checkouts as _owned_checkouts  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
owned_checkouts = _owned_checkouts
runner = CliRunner()

_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.0.1",
        "agent_family": "claude",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)


def _open_args(c: OwnedCheckouts, key: str) -> list[str]:
    return [
        "open-decision",
        "--mission",
        c.mission_slug,
        "--origin",
        "specify",
        "--input-key",
        key,
        "--question",
        "Which?",
        "--slot-key",
        "specify.discovery",
        "--actor",
        "test",
        "--policy",
        _POLICY,
    ]


def _envelope(output: str) -> dict:
    return json.loads(output.strip().splitlines()[0])


def test_open_resolve_decision_owned_lands_under_owned(owned_checkouts):
    c = owned_checkouts
    with contextlib.chdir(c.owned_root):
        opened = runner.invoke(app, [*_open_args(c, "answer"), "--owned-checkout", str(c.owned_root)])
    assert opened.exit_code == 0, (opened.output, opened.exception)
    env = _envelope(opened.output)
    assert env["success"] is True
    decision_id = env["data"]["decision_id"]
    # Ledger landed under the owned checkout, never the repository root.
    assert (c.mission_dir / "decisions").exists()
    assert not (c.repository_root / "kitty-specs" / c.mission_slug / "decisions").exists()

    with contextlib.chdir(c.owned_root):
        resolved = runner.invoke(
            app,
            [
                "resolve-decision",
                "--mission",
                c.mission_slug,
                "--decision-id",
                decision_id,
                "--final-answer",
                "yes",
                "--actor",
                "test",
                "--policy",
                _POLICY,
                "--owned-checkout",
                str(c.owned_root),
            ],
        )
    assert resolved.exit_code == 0, (resolved.output, resolved.exception)
    assert _envelope(resolved.output)["data"]["status"] == "resolved"


@pytest.mark.parametrize("claim", ["repository_root", "sibling"])
def test_open_decision_wrong_owned_refuses_before_writes(owned_checkouts, claim):
    c = owned_checkouts
    with contextlib.chdir(c.owned_root):
        result = runner.invoke(app, [*_open_args(c, "refuse"), "--owned-checkout", str(getattr(c, claim))])
    assert result.exit_code != 0
    env = _envelope(result.output)
    assert env["success"] is False
    # The real owned refusal code is preserved (verbatim when contract-registered,
    # else in data.unregistered_error_code via the allow-list-guarded fallback).
    blob = json.dumps(env)
    assert "OWNED_" in blob or "FEATURE_CONTEXT_UNRESOLVED" in blob or "MISSION_NOT_FOUND" in blob
    assert not (c.mission_dir / "decisions").exists()
