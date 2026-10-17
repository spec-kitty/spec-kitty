"""#6320: ``agent issue-verdict`` must honour the validated owned-checkout fact.

Mirrors ``test_owned_acceptance_authority_6023``: an owned-only ``single_branch``
mission lives in its owned checkout P, never in the repository root R. The
verdict must land in P's ``issue-matrix.json``; an owned fact that resolves no
mission must still refuse fail-closed (NFR-001), never fall back to R.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app
from tests.integration.test_explicit_checkout_commands import SLUG
from tests.integration.test_explicit_checkout_commands import checkouts as checkouts  # noqa: F401 -- pytest fixture

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
_ISSUE = "#6320"


def _verdict(*extra: str, mission: str = SLUG):
    return runner.invoke(
        agent_app,
        ["issue-verdict", "--mission", mission, "--issue", _ISSUE, "--verdict", "fixed", "--actor", "codex", "--evidence-ref", "PR #1", "--json", *extra],
    )


def _rows(root: Path) -> dict:
    return json.loads((root / "kitty-specs" / SLUG / "issue-matrix.json").read_text(encoding="utf-8"))


def test_owned_checkout_flag_records_verdict_in_owned_matrix(checkouts) -> None:  # noqa: F811
    primary, owned, _sibling = checkouts
    res = _verdict("--owned-checkout", str(owned))
    assert res.exit_code == 0, res.output
    assert _ISSUE in json.dumps(_rows(owned))
    assert not (primary / "kitty-specs" / SLUG).exists(), "verdict must not leak into the repository root"


def test_flagless_adoption_from_inside_owned_checkout_records(checkouts, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    _primary, owned, _sibling = checkouts
    monkeypatch.chdir(owned)
    res = _verdict()
    assert res.exit_code == 0, res.output
    assert _ISSUE in json.dumps(_rows(owned))


def test_owned_fact_resolving_no_mission_still_refuses(checkouts) -> None:  # noqa: F811
    primary, owned, _sibling = checkouts
    res = _verdict("--owned-checkout", str(owned), mission="no-such-mission-01ZZZZZZ")
    assert res.exit_code != 0, res.output
    assert not (primary / "kitty-specs").exists() or not list((primary / "kitty-specs").glob("*/issue-matrix.json"))
    assert not list((owned / "kitty-specs").glob("no-such-mission*"))
