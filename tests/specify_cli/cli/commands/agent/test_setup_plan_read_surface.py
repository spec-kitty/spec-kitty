"""WP02 (gate-read-surface-completion / FR-001 / #2107) — ``setup_plan`` reads its
PLANNING artifacts (spec.md / plan.md) via the WP01 kind-aware chokepoint
(``_planning_read_dir``, ``kind=SPEC``) instead of the coord-aware ``feature_dir``.

The driver bug (#2107): on a coord-topology / protected-primary mission the
spec.md was authored on the PRIMARY ``target_branch`` dir (since #2106), while
``setup_plan``'s ``feature_dir`` came from the coord-aware ``_find_feature_directory``
(→ the materialized ``-coord`` husk). Reading ``feature_dir / "spec.md"`` therefore
resolved the coord husk — which has no spec.md — and ``setup_plan`` blocked with
``SPEC_FILE_MISSING``. The fix re-points the PLANNING read onto WP01's
``_planning_read_dir`` chokepoint (SPEC is a PRIMARY-partition kind → the primary
dir for ALL topologies), so the read converges on the real authored truth.

Discipline (reviewer-renata post-tasks squad + standing memory):

* Tests run through the **pre-existing entry point** — the real ``setup-plan``
  command (``mission_mod.app``), NOT ``_planning_read_dir`` / ``resolve_planning_read_dir``
  directly. That would test the seam, not the re-point.
* The composed ``<slug>-<mid8>`` PRIMARY fixture is MANDATORY: a bare-slug primary
  dir is canonicalized and would mask the coord/primary divergence — a false green
  (NFR-002). We use a real 26-char Crockford ULID + its real 8-char mid8 and a
  materialized coord husk whose mission dir lacks spec.md.
* RED is non-vacuous: monkeypatching ``_planning_read_dir`` back to the coord-aware
  resolver (the pre-WP02 behaviour of reading off ``feature_dir``) makes the real
  ``setup-plan`` command block with ``SPEC_FILE_MISSING``; the live seam routing
  reads the PRIMARY spec and advances. Reverting the production read to the
  topology resolver MUST turn the GREEN assertions RED.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import mission as mission_mod
from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity: a real 26-char Crockford ULID + its 8-char mid8.
MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"
MID8 = MISSION_ID[:8]  # "01KVW9B0"
SLUG = "gate-read-surface-completion"
SLUG_WITH_MID8 = f"{SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

# A committed, substantive primary spec — clears the #846 entry gate so the only
# thing standing between RED and GREEN is WHICH surface the read resolves.
PRIMARY_SPEC = """\
# Spec — Gate Read Surface Completion

## Functional Requirements

| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Gate read | setup-plan reads spec.md from the primary surface. | High | Open |
"""


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True, text=True)


def _init_repo(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp02@example.test")
    _git(repo_root, "config", "user.name", "WP02 Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    from specify_cli.migration.backfill_topology import _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _seed_coord_topology(repo_root: Path) -> tuple[Path, Path]:
    """Seed a COORD-topology mission: PRIMARY truth + a coord husk with NO spec.md.

    Returns ``(primary_dir, coord_husk_dir)``. The composed ``<slug>-<mid8>``
    primary dir carries a committed substantive spec.md; the materialized ``-coord``
    husk mission dir has meta.json but NO spec.md (the #2106 divergence: spec moved
    to primary). The spec is committed on the PRIMARY ``HEAD`` so the #846 commit
    gate passes once the read resolves PRIMARY.
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
    (primary_dir / "spec.md").write_text(PRIMARY_SPEC, encoding="utf-8")
    # Commit the primary spec onto primary HEAD (the #846 committed-AND-substantive gate).
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "author primary spec")

    coord_husk_dir = repo_root / ".worktrees" / f"{SLUG_WITH_MID8}-coord" / "kitty-specs" / SLUG_WITH_MID8
    # Husk carries meta.json but NO spec.md — reading spec off the husk fails.
    _write_meta(coord_husk_dir, meta)
    return primary_dir, coord_husk_dir


def _run_setup_plan(repo_root: Path, coord_husk_dir: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Invoke the REAL ``setup-plan`` command (pre-existing entry point).

    ``_find_feature_directory`` is patched to return the COORD husk — exactly what
    the coord-aware resolver does for a coord-topology mission. This is the surface
    the PRE-WP02 code read its spec.md off. ``_planning_read_dir`` is deliberately
    left UNPATCHED so the production fix runs for real (resolving PRIMARY). Git
    preflight / branch context are stubbed (synthetic main), matching the canonical
    setup-plan integration harness.
    """
    runner = CliRunner()

    def _fake_show_branch_context(_repo_root: Path, _slug: str, _json: bool) -> tuple[str, str]:
        return ("main", "main")

    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    # Neutralize the FR-011 SaaS auth gate: this test targets the spec-read
    # surface, not hosted-sync auth. With SAAS sync enabled in the ambient env
    # setup-plan would refuse with SAAS_SYNC_UNAUTHENTICATED before ever reaching
    # the spec read, masking the divergence we assert on.
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    with (
        patch.object(mission_mod, "locate_project_root", return_value=repo_root),
        patch.object(mission_mod, "_enforce_git_preflight"),
        patch.object(mission_mod, "_find_feature_directory", return_value=coord_husk_dir),
        patch.object(
            mission_mod,
            "_show_branch_context",
            side_effect=_fake_show_branch_context,
        ),
        patch.object(mission_mod, "get_current_branch", return_value="main"),
        patch.object(mission_mod, "_resolve_feature_target_branch", return_value="main"),
    ):
        result = runner.invoke(
            mission_mod.app,
            ["setup-plan", "--json", "--mission", SLUG_WITH_MID8],
            catch_exceptions=False,
        )

    output = result.output.strip()
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1, f"no JSON in output: {output!r}"
    payload: dict[str, object] = json.loads(output[start : end + 1])
    return payload


# --------------------------------------------------------------------------- #
# T006 — red-first repro through the REAL setup-plan entry point.
# --------------------------------------------------------------------------- #
def test_setup_plan_reads_primary_spec_for_coord_topology(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GREEN: real ``setup-plan`` reads the PRIMARY spec for a coord-topology mission.

    The coord husk has NO spec.md; pre-WP02 this blocked with ``SPEC_FILE_MISSING``.
    With the read re-pointed onto ``_planning_read_dir`` (SPEC → PRIMARY) the command
    finds the substantive committed primary spec and advances past the spec gate
    (it does NOT report ``SPEC_FILE_MISSING``).
    """
    _primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    payload = _run_setup_plan(tmp_path, coord_husk_dir, monkeypatch)

    assert payload.get("error_code") != "SPEC_FILE_MISSING", payload
    # The spec gate cleared: setup-plan reached the plan-scaffolding stage. With a
    # committed substantive primary spec it does not block on spec at all.
    assert payload.get("error_code") != "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED", payload


def test_setup_plan_red_when_planning_read_reverts_to_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuous RED: revert the PLANNING read to the coord-aware resolver and the
    real ``setup-plan`` command blocks with ``SPEC_FILE_MISSING`` (reads the husk).

    This proves the WP02 re-point is load-bearing — reverting ``setup_plan``'s read
    from ``_planning_read_dir`` back to the topology-routed ``feature_dir`` surface
    (the coord husk) reintroduces the #2107 failure. It is the anti-mutant guard:
    a mutant that restores ``resolve_handle_to_read_path`` / ``_find_feature_directory``
    for the spec read MUST turn this RED.
    """
    _primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    def _coord_routed(_repo_root: Path, mission_slug: str, *, artifact_type: str) -> Path:
        # The pre-WP02 behaviour: the PLANNING read resolves the coord-aware dir
        # (the materialized husk), NOT the primary surface.
        husk: Path = candidate_feature_dir_for_mission(_repo_root, mission_slug)
        return husk

    monkeypatch.setattr(mission_mod, "_planning_read_dir", _coord_routed)

    payload = _run_setup_plan(tmp_path, coord_husk_dir, monkeypatch)

    assert payload.get("error_code") == "SPEC_FILE_MISSING", payload


# --------------------------------------------------------------------------- #
# T008 — anti-mutant (planning read == target_branch primary) + flattened regression.
# --------------------------------------------------------------------------- #
def test_setup_plan_planning_read_resolves_primary_target_branch(
    tmp_path: Path,
) -> None:
    """Anti-mutant: the PLANNING read dir == the PRIMARY ``target_branch`` dir.

    Reverting the production read to ``resolve_handle_to_read_path`` /
    ``_find_feature_directory`` (the coord husk) MUST turn this RED — the resolved
    planning read dir is the primary composed ``<slug>-<mid8>`` dir, never the
    materialized ``-coord`` husk.
    """
    primary_dir, coord_husk_dir = _seed_coord_topology(tmp_path)

    resolved = mission_mod._planning_read_dir(tmp_path, SLUG_WITH_MID8, artifact_type="spec")

    assert resolved.resolve() == primary_dir.resolve()
    assert resolved.resolve() != coord_husk_dir.resolve()
    assert (resolved / "spec.md").read_text(encoding="utf-8") == PRIMARY_SPEC


def test_setup_plan_flattened_mission_reads_primary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Flattened-regression (NFR-001): a single-branch mission reads the primary spec.

    No coordination branch / husk — ``setup-plan`` reads ``target_branch/spec.md``
    exactly as today, advancing past the spec gate.
    """
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
    (primary_dir / "spec.md").write_text(PRIMARY_SPEC, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "author primary spec (flattened)")

    # In a flattened mission the coord-aware resolver returns the primary dir itself.
    payload = _run_setup_plan(tmp_path, primary_dir, monkeypatch)

    assert payload.get("error_code") != "SPEC_FILE_MISSING", payload
    assert payload.get("error_code") != "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED", payload
