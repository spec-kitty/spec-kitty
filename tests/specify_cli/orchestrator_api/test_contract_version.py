"""WP07 (design-phase-orchestrator-api-01M1HE6M) -- CONTRACT_VERSION bump to
1.4.0.

(Superseded: the pin below now reads ``1.10.0`` after ``consolidate-mission`` gained the
pre-merge approved-bound refusal and its ``data.preflight_error_code`` (#5668); it read
``1.9.0`` after the failure envelope's ``data`` gained ``teardown_error_code`` (#5613), and
``1.8.0`` after WP06 of requirement-id-grammar-01M3NRCA made the ``tasks`` verb's pass-through
``data`` additive (``parsed_spec_ids`` / ``rejected_requirement_refs`` /
``success_criteria_coverage``) and the ``plan`` verb's ``data`` additive
(``requirement_id_warnings``) plus remapped its previously-unregistered
delegate error codes onto the closed ``PLAN_SETUP_FAILED`` envelope with
``data.reason``; the 1.4.0 narrative is kept as the WP's historical record.
It was previously superseded to ``1.5.0`` by the ``tasks`` pass-through
``planning_commit`` object (#4141), then to ``1.6.0`` by the
``planning_commit.action`` vocabulary gaining ``"repinned"`` (#4827), then to
``1.7.0`` by ``accept-mission`` applying the host readiness verdict (#4934).)

``CONTRACT_VERSION`` is currently ``"1.3.0"`` (envelope.py:28), so this test
is authentically RED before this WP's change: it pins the new value AND that
``envelope.py``'s changelog comment block names all 11 new verbs added by
WP03-WP06/WP08, by their literal Typer command names, matching the existing
1.1.0/1.2.0/1.3.0 changelog-comment precedent already in that file.

``orchestrator_api`` commands always emit JSON (module docstring: "Output is
always JSON (no prose mode)") -- there is no ``--json`` flag on
``contract-version`` itself to pass.

This only inspects an in-memory Typer response and re-reads ``envelope.py``'s
own source text -- no fixture-mission, no real git operations -- so it is
marked ``pytest.mark.fast`` (matching ``test_commands_fail_closed.py``'s
convention, ``pytest.ini:25``).
"""

from __future__ import annotations

import inspect
import json

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api import envelope as envelope_module
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

# The 11 verbs added across WP03 (specify/plan/tasks), WP04
# (check-prerequisites/record-analysis), WP05 (open/resolve/defer/cancel-
# decision), WP06 (design-status), and WP08 (answer-decision) -- literal
# Typer ``@app.command(name=...)`` strings, enumerated from the shipped
# source (``src/specify_cli/orchestrator_api/commands.py``), not taken on
# faith from any planning document.
_NEW_VERBS = (
    "specify",
    "plan",
    "tasks",
    "check-prerequisites",
    "record-analysis",
    "open-decision",
    "resolve-decision",
    "defer-decision",
    "cancel-decision",
    "design-status",
    "answer-decision",
)


def test_contract_version_response_reports_1_10_0() -> None:
    result = runner.invoke(app, ["contract-version"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is True
    assert envelope["data"]["api_version"] == "1.10.0"
    assert envelope["contract_version"] == "1.10.0"


def test_min_provider_version_unchanged() -> None:
    """NFR-001: the version bump is purely additive -- MIN_PROVIDER_VERSION
    must NOT move."""
    assert envelope_module.MIN_PROVIDER_VERSION == "0.1.0"


def test_changelog_comment_names_all_eleven_new_verbs() -> None:
    """A mismatched/missing verb name in the changelog comment is exactly
    the documentation-vs-code drift this WP exists to prevent (Reviewer
    Guidance, WP07 task file)."""
    source = inspect.getsource(envelope_module)
    changelog_start = source.index("# 1.1.0:")
    changelog_end = source.index('CONTRACT_VERSION = "1.10.0"')
    changelog_block = source[changelog_start:changelog_end]

    missing = [verb for verb in _NEW_VERBS if verb not in changelog_block]
    assert not missing, f"changelog comment is missing verb name(s): {missing}"
