"""Red-first regression: ``spec-kitty research`` must honour the owned checkout.

Issue #5882 (owned-single-branch analog of the coord-topology #2683): the
``research`` command has **no owned selector** and resolves its project/mission
root through ``find_repo_root`` / ``get_project_root_or_exit``, both of which
follow a linked owned checkout's ``.git`` pointer back to the PRIMARY repo root.
Run from an owned single-branch checkout, ``research`` therefore either

* scaffolds its four assets (``research.md``, ``data-model.md``, the two research
  CSV stubs) into the PRIMARY ``kitty-specs/<slug>/`` when the primary holds a
  (stale) same-slug copy -- silently redirecting authoring into an unowned,
  dirty primary; or
* refuses ``Mission not found`` when the primary has no copy -- the owned mission
  is simply unreachable by ``research``.

Every sibling owned-single-branch lifecycle/authoring command (``setup-plan``,
``record-analysis``, ``check-prerequisites``, ``decision``, ``map-requirements``,
``finalize-tasks``, ``charter generate``) already threads a validated
``OwnedCheckout`` through to its writes (PR #6002, #5277). ``research`` was never
wired. These tests reproduce the gap through the REAL ``research`` entry point
and pin the target behaviour:

1. ``research --mission <handle> --owned-checkout <P>`` is accepted and scaffolds
   into ``P/kitty-specs/<slug>/`` -- never into R (pre-fix: ``No such option:
   --owned-checkout``, exit 2).
2. ``research --mission <handle>`` run from inside an owned checkout auto-adopts
   that checkout (mirroring ``record-analysis`` / ``setup-plan``) and leaves R
   byte-for-byte unchanged even when R holds a stale same-slug copy (pre-fix: the
   four assets land in R).

Discipline: driven through the pre-existing ``research`` command with REAL root
resolution (``find_repo_root`` is NOT patched), so the production worktree->
primary walk is exercised. The shipped research templates are seeded under
``<root>/.kittify/templates/`` (the canonical resolver's LEGACY tier) in both R
and P so the scaffold actually writes -- #4926 otherwise suppresses a 0-byte
fabrication when no template resolves, which would mask placement.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import research as research_mod
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_RESEARCH_ASSETS = (
    Path("research.md"),
    Path("data-model.md"),
    Path("research") / "evidence-log.csv",
    Path("research") / "source-register.csv",
)


def _seed_research_templates(root: Path) -> None:
    """Seed the shipped research templates under the LEGACY resolver tier."""
    templates_dir = root / ".kittify" / "templates"
    (templates_dir / "research").mkdir(parents=True, exist_ok=True)
    (templates_dir / "research-template.md").write_text("# Research\n\nSeeded.\n", encoding="utf-8")
    (templates_dir / "data-model-template.md").write_text("# Data Model\n\nSeeded.\n", encoding="utf-8")
    (templates_dir / "research" / "evidence-log.csv").write_text("timestamp,source_type,citation,key_finding,confidence,notes\n", encoding="utf-8")
    (templates_dir / "research" / "source-register.csv").write_text("source_id,citation,url,accessed_date,relevance,status\n", encoding="utf-8")


def _invoke_research(args: list[str], *, cwd: Path, home: Path) -> object:
    """Run the REAL ``research`` command with real root resolution from ``cwd``."""
    app = typer.Typer()
    app.command(name="research")(research_mod.research)
    runner = CliRunner()
    prior = os.getcwd()
    os.chdir(cwd)
    try:
        with mock.patch.dict(
            os.environ,
            {"SPEC_KITTY_ENABLE_SAAS_SYNC": "0", "SPEC_KITTY_HOME": str(home), "HOME": str(home)},
        ):
            return runner.invoke(app, args, catch_exceptions=False)
    finally:
        os.chdir(prior)


def test_research_accepts_owned_checkout_and_scaffolds_into_owned(
    owned_checkouts: OwnedCheckouts,
    r_snapshot,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    """``research --owned-checkout P`` scaffolds into P and never touches R."""
    r_root = owned_checkouts.repository_root
    p_root = owned_checkouts.owned_root
    _seed_research_templates(p_root)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)

    before = r_snapshot.take()
    result = _invoke_research(
        ["--mission", owned_checkouts.mission_slug, "--owned-checkout", str(p_root)],
        cwd=r_root,
        home=home,
    )

    assert result.exit_code == 0, result.output
    owned_mission_dir = p_root / "kitty-specs" / owned_checkouts.mission_slug
    for rel in _RESEARCH_ASSETS:
        assert (owned_mission_dir / rel).exists(), f"{rel} not scaffolded into the owned checkout"
    # R must be byte-for-byte unchanged: no research artifacts, no stray mission dir.
    r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_research_from_owned_cwd_does_not_redirect_into_dirty_primary(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Callable[..., Path],
    r_snapshot,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    """Flagless ``research`` run from inside P auto-adopts P; R's stale copy is untouched."""
    r_root = owned_checkouts.repository_root
    p_root = owned_checkouts.owned_root
    stale_root_copy()  # R now holds a same-slug, filled-plan copy research could redirect into
    _seed_research_templates(r_root)
    _seed_research_templates(p_root)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)

    before = r_snapshot.take()
    result = _invoke_research(
        ["--mission", owned_checkouts.mission_slug],
        cwd=p_root,
        home=home,
    )

    assert result.exit_code == 0, result.output
    # The owned checkout received the artifacts...
    owned_mission_dir = p_root / "kitty-specs" / owned_checkouts.mission_slug
    assert (owned_mission_dir / "research.md").exists()
    # ...and the dirty primary was never written into.
    r_snapshot.assert_unchanged(before, r_snapshot.take())
