"""#3763 — the CLI claim seam exits structured on a self-heal failure.

``workflow.py``'s ``implement`` calls the shared claim-ancestry gate
post-materialization. Before #3763, a failure of the gate's recheck
self-heal escaped as a raw exception (the command's generic handler printed
the bare message with no error code). The gate now translates it to
``AncestryNotEstablishedError``; this test drives the real Typer command and
asserts the refusal renders the structured ``ANCESTRY_NOT_ESTABLISHED``
envelope and exits 1.

Reuses the light ``workflow_repo`` harness from
``test_agent_action_implement_base.py`` (non-git root, minted worktree,
patched create-path dispatch): only the gate's two collaborators are
replaced, so the real gate and the real CLI seam run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

import specify_cli.lanes.implement_support as implement_support
from specify_cli.cli.commands.agent import workflow
from specify_cli.lanes.implement_support import AncestryCheckResult
from tests.specify_cli.cli.commands.agent.test_agent_action_implement_base import (
    _MISSION_SLUG,
    _WP_ID,
    _capture_create_dispatch,
)
from tests.specify_cli.cli.commands.agent import (
    test_agent_action_implement_base as _implement_base,
)

# pytest resolves the ``workflow_repo`` fixture through this module's
# namespace; binding the base module's fixture here registers it for the
# tests below (same registration a conftest would provide).
workflow_repo = _implement_base.workflow_repo

pytestmark = pytest.mark.fast


def _invoke() -> Result:
    return CliRunner().invoke(
        workflow.app,
        ["implement", _WP_ID, "--mission", _MISSION_SLUG, "--agent", "test-agent"],
    )


def test_self_heal_failure_exits_structured(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_create_dispatch(monkeypatch, workflow_repo)

    monkeypatch.setattr(
        implement_support,
        "check_claim_ancestry",
        lambda *args, **kwargs: AncestryCheckResult(ok=False, missing_refs=("bogus-ref",)),
    )

    def _fail_heal(*args: object, **kwargs: object) -> None:
        raise RuntimeError("self-heal exploded")

    monkeypatch.setattr(implement_support, "reenter_lane_self_heal", _fail_heal)

    result = _invoke()

    assert result.exit_code == 1, result.stdout
    assert "ANCESTRY_NOT_ESTABLISHED" in result.stdout, result.stdout


def test_ancestry_refusal_still_names_missing_refs(workflow_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the pre-existing not-ok path (heal succeeds, recheck still
    fails) keeps its own refusal text — the #3763 wrap only owns the
    self-heal-failure case."""
    _capture_create_dispatch(monkeypatch, workflow_repo)

    monkeypatch.setattr(
        implement_support,
        "check_claim_ancestry",
        lambda *args, **kwargs: AncestryCheckResult(ok=False, missing_refs=("bogus-ref",)),
    )
    monkeypatch.setattr(implement_support, "reenter_lane_self_heal", lambda *args, **kwargs: None)

    result = _invoke()

    assert result.exit_code == 1, result.stdout
    assert "ancestry could not be established after self-heal" in result.stdout
    assert "bogus-ref" in result.stdout
