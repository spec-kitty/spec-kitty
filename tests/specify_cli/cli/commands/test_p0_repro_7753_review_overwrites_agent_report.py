"""Open P0 reproduction for spec-kitty/spec-kitty#7753.

``spec-kitty review --mission <slug>`` writes its machine report to
``kitty-specs/<slug>/mission-review-report.md`` with an unconditional
``write_text`` (``review/_report.py``), so an agent-written mission review
saved at that path (no ``verdict:`` / ``gates_recorded:`` frontmatter) is
destroyed without warning or backup.

This is an open P0 red-first reproduction (ADR 2026-07-17-1): it is expected
to FAIL until #7753 is fixed, and runs only in the nightly ``p0-repro`` lane.
The fix PR removes the ``p0_repro`` marker.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.specify_cli.cli.commands._review_fixtures import (
    MISSION_SLUG as _MISSION_SLUG,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    build_cli_app as _build_cli_app,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    make_mock_resolved as _make_mock_resolved,
)
from tests.specify_cli.cli.commands._review_fixtures import (
    setup_fixture as _setup_fixture,
)

pytestmark = [pytest.mark.fast, pytest.mark.non_sandbox]

_AGENT_MARKER = "Reviewer: agent-7753-distinctive-reviewer-identity"
_AGENT_REPORT = f"""# Mission Review Report: {_MISSION_SLUG}

{_AGENT_MARKER}

## FR coverage

- FR-001: covered by WP01 (hand-written post-merge finding).

## Verdict

PASS WITH NOTES (agent-authored review, not a machine report).
"""


@pytest.mark.p0_repro(issue=7753)
def test_review_does_not_silently_overwrite_agent_written_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An agent-written mission-review-report.md survives ``spec-kitty review``."""
    repo_root, feature_dir = _setup_fixture(
        tmp_path,
        {"WP01": "done", "WP02": "done"},
    )
    report_path = feature_dir / "mission-review-report.md"
    report_path.write_text(_AGENT_REPORT, encoding="utf-8")

    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.find_repo_root",
        lambda: repo_root,
    )
    resolved = _make_mock_resolved(feature_dir)
    monkeypatch.setattr(
        "specify_cli.cli.commands.review.resolve_mission_handle",
        lambda handle, repo_root: resolved,
    )

    result = CliRunner().invoke(
        _build_cli_app(),
        ["--mission", _MISSION_SLUG],
    )

    # Positive precondition: the command got as far as the report-write
    # decision, so its output names the report (written, refused because one
    # exists, or moved aside). An unrelated early refusal names none of these.
    assert re.search(r"mission-review|backup|\.bak", result.output, re.IGNORECASE), f"review never reached the report-write decision; output:\n{result.output}"

    # The agent's review must survive in ANY file under the repository
    # (left in place, or preserved as a backup anywhere, with any name or
    # extension).
    marker = _AGENT_MARKER.encode()
    surviving = [p for p in repo_root.rglob("*") if p.is_file() and marker in p.read_bytes()]
    assert surviving, (
        "#7753: spec-kitty review destroyed the agent-written "
        "mission-review-report.md with no backup anywhere in the repository.\n"
        f"Exit code: {result.exit_code}\nOutput:\n{result.output}\n"
        f"Report now:\n{report_path.read_text(encoding='utf-8')[:400]}"
    )
