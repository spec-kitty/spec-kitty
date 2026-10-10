"""Regression tests for FR-007 (#774): the canonical shape of
``spec-kitty agent decision`` must stay consistent across the CLI surface,
its rendered help, and every documentation/skill/template reference.

The canonical shape is:

    spec-kitty agent decision { open | resolve | defer | cancel | verify | list }

Three invariants, all already correct on ``main`` (verified during
planning of mission ``release-3-2-0a5-tranche-1``, research note R6; the
``list`` subcommand was added on purpose in ``989667221``, #3951, and is
part of the canonical visible surface as of nightly-drift-reds-01M3M14S R5):

1. **CLI shape**: introspection of the agent app shows the ``decision``
   subgroup exposes exactly the six canonical *visible* subcommands.
2. **Help shape**: ``spec-kitty agent decision --help`` lists those six.
3. **Docs/skills/templates**: no surviving non-canonical phrasing exists
   anywhere under ``docs/``, ``.agents/skills/``, the rendered skill
   snapshots, or the mission templates.

The non-canonical regex is anchored on the ``spec-kitty`` prefix so that
prose like "decision documentation requirement" or "decisions about ..."
does not produce false positives.

Note on the ``widen`` subcommand: ``decision_app`` registers a seventh
subcommand named ``widen`` with ``hidden=True``. The contract specifies
the *visible* surface, so we filter to non-hidden subcommands when
asserting set equality.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
from click.testing import CliRunner
from typer.main import get_command

from specify_cli import app as _typer_app
from tests import _click_universe as typer_click
from tests._support.docfx_reports_guard import assert_docfx_does_not_publish_reports

pytestmark = [pytest.mark.unit, pytest.mark.fast]

cli: typer_click.Group = get_command(_typer_app)  # type: ignore[assignment]

# Repository root: this file lives at
#   <repo>/tests/specify_cli/cli/test_decision_command_shape_consistency.py
# so parents[3] points to <repo>.
REPO_ROOT = Path(__file__).resolve().parents[3]

EXPECTED_SUBCOMMANDS = {"open", "resolve", "defer", "cancel", "verify", "list", "repair-runtime-lock"}

# Non-canonical decision-command shapes that must NOT appear anywhere.
# Two alternations, both anchored on the ``spec-kitty`` prefix:
#   1. ``spec-kitty [agent] decisions ...`` (plural) or ``spec-kitty
#      [agent] decision-...`` (kebabed legacy form).
#   2. ``spec-kitty decision ...`` with ANY verb — a missing ``agent`` segment.
#      There is no top-level ``decision`` command, so even a canonical verb
#      (``spec-kitty decision open``) is wrong without ``agent`` (#5258: the
#      former verb lookahead let exactly those through).
NON_CANONICAL_RE = re.compile(
    r"spec-kitty\s+(?:agent\s+)?(?:decisions\b|decision-)"
    r"|"
    r"spec-kitty\s+decision\b",
)

SCAN_ROOTS = (
    "docs",
    ".agents/skills",
    "tests/specify_cli/skills/__snapshots__",
    "src/specify_cli/missions",
)

# Dated report snapshots under docs/reports/ (e.g.
# docs/reports/tracer-friction-recon/2026-09-26/) are immutable point-in-time
# records that legitimately quote retired command shapes on purpose — the
# whole point of the snapshot is to describe the shape as it stood on the
# date it was taken. Rewording them would falsify the historical record.
# docs/reports/ is already classified as an immutable-historical-snapshot
# prefix by ARCHIVE_PATH_PREFIXES in
# tests/architectural/test_no_dead_src_path_literals.py; this mirrors that
# classification for the decision-command-shape guard rather than inventing
# a third, divergent exemption list. See spec.md R6 / #5187
# (nightly-drift-reds-01M3M14S).
REPORT_SNAPSHOT_PREFIX = "docs/reports/"


def test_report_snapshot_prefix_stays_an_archive_classified_prefix() -> None:
    """The exemption is only honest while the archive classification agrees."""
    from tests.architectural.test_no_dead_src_path_literals import ARCHIVE_PATH_PREFIXES

    assert REPORT_SNAPSHOT_PREFIX in ARCHIVE_PATH_PREFIXES

# docs/docfx.json's ``build.content`` globs are what actually gets published
# as live docs. The exemption above is only safe as long as ``reports`` is
# never one of those globs -- otherwise a "point-in-time snapshot" would be
# published as a live doc while still being allowed to quote retired shapes.
DOCFX_CONFIG_PATH = REPO_ROOT / "docs" / "docfx.json"


def _visible_subcommand_names(group: typer_click.Group) -> set[str]:
    """Return the names of subcommands that are NOT hidden."""
    return {
        name
        for name, cmd in group.commands.items()
        if not getattr(cmd, "hidden", False)
    }


def test_agent_decision_subgroup_has_canonical_visible_subcommands() -> None:
    # Duck-type the group navigation rather than ``isinstance(x, click.Group)``:
    # under typer 0.26 / click 8.4 ``TyperGroup`` no longer subclasses
    # ``click.Group`` (its MRO is ``TyperGroup -> Command -> ABC``), so the old
    # isinstance guard is a version-skew false negative. A command group is what
    # exposes ``.commands`` — that is the load-bearing property this test needs.
    agent_grp = cli.commands.get("agent")
    assert agent_grp is not None and hasattr(agent_grp, "commands"), (
        "spec-kitty agent group missing from CLI"
    )
    agent_grp = cast(typer_click.Group, agent_grp)
    decision_grp = agent_grp.commands.get("decision")
    assert decision_grp is not None and hasattr(decision_grp, "commands"), (
        "spec-kitty agent decision subgroup missing from CLI"
    )
    decision_grp = cast(typer_click.Group, decision_grp)
    visible = _visible_subcommand_names(decision_grp)
    assert visible == EXPECTED_SUBCOMMANDS, (
        f"FR-007 regression: visible decision subcommands drifted.\n"
        f"  expected: {sorted(EXPECTED_SUBCOMMANDS)}\n"
        f"  actual:   {sorted(visible)}"
    )


def test_help_output_lists_canonical_subcommands() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli, ["agent", "decision", "--help"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    for sub in EXPECTED_SUBCOMMANDS:
        assert sub in result.output, (
            f"FR-007 regression: subcommand {sub!r} missing from "
            f"`agent decision --help`:\n{result.output}"
        )


def test_repair_runtime_lock_requires_explicit_owned_checkout_claim() -> None:
    result = CliRunner().invoke(cli, ["agent", "decision", "repair-runtime-lock", "--mission", "any-mission"])
    assert result.exit_code != 0
    assert "owned-checkout" in result.output


def test_no_non_canonical_decision_command_shape_in_repo_text() -> None:
    offenders: list[tuple[str, str]] = []
    for rel in SCAN_ROOTS:
        root = REPO_ROOT / rel
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relpath = path.relative_to(REPO_ROOT).as_posix()
            if relpath.startswith(REPORT_SNAPSHOT_PREFIX):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in NON_CANONICAL_RE.finditer(text):
                offenders.append((relpath, match.group(0)))
    assert not offenders, (
        "FR-007 regression: non-canonical decision command shape found:\n  "
        + "\n  ".join(f"{p}: {m!r}" for p, m in offenders)
    )


def test_docs_reports_exemption_is_not_published_as_live_docs() -> None:
    """The docs/reports/ exemption is only safe while docfx never publishes it.

    ``docs/reports/`` snapshots (see ``REPORT_SNAPSHOT_PREFIX`` above) are
    exempted from the non-canonical-shape scan because they are dated,
    immutable point-in-time records. That is only safe as long as
    ``docs/docfx.json`` never turns those snapshots into published, live
    documentation — otherwise a reader would see a "live" page that is
    deliberately allowed to quote retired command shapes. This guard fails
    loudly the moment docfx's build.content actually resolves a
    docs/reports/ path (a **-aware glob match against a probe path, not a
    bare 'reports' substring test -- see
    tests/_support/docfx_reports_guard.py). Shares its implementation with
    the equivalent guard in tests/contract/test_terminology_guards.py via
    that module -- do not re-add a second copy here.
    """
    assert_docfx_does_not_publish_reports(DOCFX_CONFIG_PATH)
