"""gate-read-surface-completion closeout (#2107 residual / FR-004 / FR-009) —
the ``research`` (Phase 0) command reads AND scaffolds its planning artifacts via
the kind-aware seam (``resolve_planning_read_dir``), not the coord-aware
``resolve_feature_dir_for_slug``.

The residual (paula closeout, N+1 a third time after map-requirements and
finalize-tasks): ``research`` bound ``feature_dir = resolve_feature_dir_for_slug``
(COORD-aware → the materialized ``-coord`` husk under coordination topology), then

* READ: validated ``feature_dir / "plan.md"`` via ``validate_plan_filled(strict=True)``
  — so on a coord-topology mission it validated the husk's (stale / template /
  absent) ``coord/plan.md`` instead of the authored primary ``plan.md``; and
* WRITE: scaffolded ``research.md`` / ``data-model.md`` / the research CSV stubs
  onto the husk — re-introducing the primary↔coord split that #2106 eliminated.

``plan.md`` / ``research.md`` / ``data-model.md`` are all PRIMARY-partition kinds
(``MissionArtifactKind.{FINALIZED_EXECUTION_PLAN,RESEARCH,DATA_MODEL}``) that live
with their mission on the primary ``target_branch`` for EVERY topology since #2106.
The fix routes BOTH the read and the scaffold write through the kind-aware seam so
they converge on the primary surface.

Discipline (NFR-002 / standing memory):

* Driven through the **pre-existing entry point** — the REAL ``research`` command
  (``cli.app``), NOT ``resolve_planning_read_dir`` directly.
* The composed ``<slug>-<mid8>`` PRIMARY fixture is MANDATORY: a bare-slug primary
  dir is canonicalized and would mask the coord/primary divergence (false green).
  We use a real 26-char Crockford ULID + its real 8-char mid8 and a materialized
  coord husk that carries an UNFILLED template ``plan.md`` and NO research artifacts.
* RED is non-vacuous and revert-proof: against pre-fix code (``feature_dir`` bound
  from ``resolve_feature_dir_for_slug``) the command validates the husk's UNFILLED
  ``plan.md`` and blocks with a ``PlanValidationError`` exit, and would scaffold the
  research artifacts onto the husk. Post-fix it reads the FILLED primary plan,
  advances, and scaffolds onto the primary dir.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import research as research_mod

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"
MID8 = MISSION_ID[:8]  # "01KVW9B0"
SLUG = "gate-read-surface-completion"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

# A substantive, FILLED plan (no template markers) — the authored primary truth.
FILLED_PLAN = """\
# Implementation Plan — Gate Read Surface Completion

## Technical Context
Language/Version: Python 3.11
Primary Dependencies: typer, rich
Storage: filesystem

## Architecture
The research command routes planning reads + writes through the kind-aware seam.
"""

# An UNFILLED plan — >= MIN_MARKERS_TO_REMOVE (5) template markers present. This is
# what sits on the COORD husk; pre-fix ``research`` validated THIS and blocked.
UNFILLED_PLAN = """\
# Implementation Plan — [FEATURE]

Branch: [###-feature-name] | Date: [DATE] | Spec: [link]

## Technical Context
Language/Version: [e.g., Python 3.11 or NEEDS CLARIFICATION]
Constitution Check: [Gates determined based on charter file]
Structure: [Document the selected structure and reference real paths]
"""


def _git(repo_root: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True
    )


def _init_repo(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "research@example.test")
    _git(repo_root, "config", "user.name", "Research Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")
    # A generic template so the artifacts this file's tests use as a
    # placement/routing signal actually get created — mission
    # ownership-boundary-overwrite-hardening-01M35ER3/#4926 stopped
    # ``research`` from fabricating a 0-byte research.md when NO template
    # resolves at all, which this fixture's typeless/``software-dev`` mission
    # otherwise never has. These tests are about primary-vs-coord placement
    # and handle canonicalization, not the fabrication policy, so a real
    # generic template preserves their original intent.
    templates_dir = repo_root / ".kittify" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (templates_dir / "research.md").write_text(
        "# Research\n\nSeeded template content.\n", encoding="utf-8"
    )
    (templates_dir / "data-model.md").write_text(
        "# Data Model\n\nSeeded template content.\n", encoding="utf-8"
    )
    research_templates_dir = templates_dir / "research"
    research_templates_dir.mkdir(parents=True, exist_ok=True)
    (research_templates_dir / "evidence-log.csv").write_text(
        "timestamp,source_type,citation,key_finding,confidence,notes\n", encoding="utf-8"
    )
    (research_templates_dir / "source-register.csv").write_text(
        "source_id,citation,url,accessed_date,relevance,status\n", encoding="utf-8"
    )


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    from specify_cli.migration.backfill_topology import _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_coord_topology(repo_root: Path) -> tuple[Path, Path]:
    """Seed a COORD-topology mission: PRIMARY filled plan + a coord husk with an
    UNFILLED template plan and NO research artifacts.

    Returns ``(primary_dir, coord_husk_dir)``.
    """
    from mission_runtime import MissionTopology

    _init_repo(repo_root)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "coordination_branch": COORD_BRANCH,
        "topology": MissionTopology.COORD.value,
    }
    primary_dir = repo_root / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "plan.md").write_text(FILLED_PLAN, encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "author primary plan")

    coord_husk_dir = (
        repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord" / "kitty-specs" / SLUG_WITH_MID8
    )
    _write_meta(coord_husk_dir, meta)
    # The husk carries an UNFILLED template plan — pre-fix research validated this.
    (coord_husk_dir / "plan.md").write_text(UNFILLED_PLAN, encoding="utf-8")
    return primary_dir, coord_husk_dir


def _run_research(repo_root: Path, mission_handle: str = SLUG_WITH_MID8):  # type: ignore[no-untyped-def]
    """Invoke the REAL ``research`` command (pre-existing entry point).

    ``find_repo_root`` / ``get_project_root_or_exit`` are patched to the fixture
    root. The seam (``resolve_planning_read_dir``) runs for real against the
    on-disk fixture — the production fix is exercised, not stubbed. (The dossier
    sync this harness used to neutralize retired with the sync transport.)

    ``mission_handle`` defaults to the canonical ``<slug>-<mid8>`` directory name;
    pass a bare ``MID8`` to exercise the #2122 handle→slug canonicalization path.
    """
    import typer

    # A minimal app carrying ONLY the research command — the pre-existing entry
    # point — so the root callback's global asset repair / project preflight does
    # not run. Mirrors the setup_plan red-first harness (``mission_mod.app``).
    app = typer.Typer()
    app.command(name="research")(research_mod.research)
    runner = CliRunner()

    _prev_saas = os.environ.get("SPEC_KITTY_ENABLE_SAAS_SYNC")
    os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    try:
        with (
            patch.object(research_mod, "find_repo_root", return_value=repo_root),
            patch.object(
                research_mod, "get_project_root_or_exit", return_value=repo_root
            ),
        ):
            # A single-command typer app omits the command name from argv.
            result = runner.invoke(
                app,
                ["--mission", mission_handle],
                catch_exceptions=False,
            )
    finally:
        if _prev_saas is not None:
            os.environ["SPEC_KITTY_ENABLE_SAAS_SYNC"] = _prev_saas
    return result


# --------------------------------------------------------------------------- #
# Red-first: read arm — the FILLED primary plan is consulted, not the husk's
# UNFILLED template plan (which would block).
# --------------------------------------------------------------------------- #
def test_research_reads_primary_plan_for_coord_topology(tmp_path: Path) -> None:
    """GREEN: real ``research`` validates the FILLED PRIMARY plan and advances.

    The coord husk holds an UNFILLED template plan; pre-fix ``research`` validated
    that and exited with a ``PlanValidationError`` block. With the read re-pointed
    onto the seam (FINALIZED_EXECUTION_PLAN → PRIMARY) the filled primary plan
    clears the gate.
    """
    _primary_dir, _coord_husk_dir = _seed_coord_topology(tmp_path)

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    # The plan-validation block message must NOT appear (it would on the husk plan).
    assert "appears to be unfilled" not in result.output, result.output


# --------------------------------------------------------------------------- #
# Red-first: write arm — research artifacts are scaffolded onto PRIMARY, not coord.
# --------------------------------------------------------------------------- #
def test_research_scaffolds_onto_primary_for_coord_topology(tmp_path: Path) -> None:
    """GREEN: ``research`` scaffolds research.md / data-model.md / CSV stubs onto
    the PRIMARY dir, never the coord husk (the write twin of the #2107 residual).
    """
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    result = _run_research(tmp_path)
    assert result.exit_code == 0, result.output

    for rel in ("research.md", "data-model.md"):
        assert (primary_dir / rel).exists(), f"{rel} missing on PRIMARY surface"
        assert not (coord_husk_dir / rel).exists(), (
            f"{rel} leaked onto the COORD husk (write-twin regression)"
        )
    # CSV stubs also land on primary.
    assert (primary_dir / "research" / "evidence-log.csv").exists()
    assert not (coord_husk_dir / "research" / "evidence-log.csv").exists()


# --------------------------------------------------------------------------- #
# Red-first (#2122): a BARE MID8 handle must canonicalize to the slug before the
# PRIMARY-partition planning read composes ``kitty-specs/<value>`` literally.
# Pre-fix the bare ``MID8`` was joined as ``kitty-specs/<mid8>/`` (handle-blind
# primary arm) → the read missed the real primary plan; the FILLED primary plan
# was never consulted and the artifacts scaffolded onto a wrong/non-existent dir.
# --------------------------------------------------------------------------- #
def test_research_resolves_bare_mid8_handle_to_primary_slug(tmp_path: Path) -> None:
    """GREEN: ``research --mission <mid8>`` resolves the FILLED primary plan and
    scaffolds onto the canonical primary dir (not ``kitty-specs/<mid8>``)."""
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    # Drive the REAL command with a BARE mid8 handle (not the full slug).
    result = _run_research(tmp_path, mission_handle=MID8)

    assert result.exit_code == 0, result.output
    assert "appears to be unfilled" not in result.output, result.output
    # Artifacts land on the canonical PRIMARY dir, never on a literal
    # ``kitty-specs/<mid8>`` dir nor the coord husk.
    for rel in ("research.md", "data-model.md"):
        assert (primary_dir / rel).exists(), f"{rel} missing on PRIMARY surface"
        assert not (coord_husk_dir / rel).exists(), (
            f"{rel} leaked onto the COORD husk (#2122 regression)"
        )
    assert not (tmp_path / "kitty-specs" / MID8).exists(), (
        "research composed a literal kitty-specs/<mid8> dir (handle-blind primary arm)"
    )


# --------------------------------------------------------------------------- #
# Flattened-mission regression (NFR-001): no coordination branch → primary truth.
# --------------------------------------------------------------------------- #
def test_research_flattened_mission_reads_and_scaffolds_primary(tmp_path: Path) -> None:
    """A flattened/single-branch mission reads + scaffolds on ``target_branch`` —
    identical to pre-mission behavior."""
    from mission_runtime import MissionTopology

    _init_repo(tmp_path)
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_slug": SLUG_WITH_MID8,
        "topology": MissionTopology.SINGLE_BRANCH.value,
    }
    primary_dir = tmp_path / "kitty-specs" / SLUG_WITH_MID8
    _write_meta(primary_dir, meta)
    (primary_dir / "plan.md").write_text(FILLED_PLAN, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "author primary plan (flattened)")

    result = _run_research(tmp_path)

    assert result.exit_code == 0, result.output
    assert "appears to be unfilled" not in result.output, result.output
    assert (primary_dir / "research.md").exists()
    assert (primary_dir / "data-model.md").exists()
