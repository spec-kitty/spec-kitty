"""Mission-level behavioral verification for write-surface-coherence (WP07 / T028-T030).

* T028 — flattened-regression proof (NFR-001 / SC-003): under a flattened /
  single-branch topology BOTH a planning commit and a status commit land on
  ``target_branch`` — identical to pre-mission behavior — and the existing
  flattened planning suite stays green.
* T029 — FR-007 end-to-end requirement mapping (SC-001): a coordination-topology
  mission whose planning artifacts live on the PRIMARY surface drives
  ``finalize-tasks --validate-only`` to 100% requirements mapped with ZERO manual
  coordination-worktree steps.
* T030 — FR-008 protected-primary refusal (G-4 / DECISION 6): a coord-topology
  mission whose ``target_branch`` is protected (``main``) refuses a primary-kind
  commit — and the refusal takes the CORRECT shape per path: the ``commit_router``
  returns ``CommitRouterResult(status="no_op_wrong_surface")`` while ``safe_commit``
  RAISES ``ProtectedBranchRefused``. BOTH refusal texts name the feature-branch
  remedy and never mention "coordination worktree".

Realistic identity throughout: real 26-char ULID ``mission_id``, real 8-char
``mid8``, real ``<slug>-<mid8>`` mission dirs.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner
from ulid import ULID

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    resolve_placement_only,
    resolve_topology,
    routes_through_coordination,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FLAT_TARGET_BRANCH = "feat/write-surface-coherence"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(tmp_path: Path, *, head_branch: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", head_branch)
    _git(repo, "config", "user.email", "wsc@example.com")
    _git(repo, "config", "user.name", "WSC Suite")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project: wsc\n", encoding="utf-8")
    return repo


# ---------------------------------------------------------------------------
# T028 — flattened-regression proof (NFR-001 / SC-003)
# ---------------------------------------------------------------------------


def test_flattened_topology_both_commits_land_on_target_branch(tmp_path: Path) -> None:
    """NFR-001 / G-3: under a flattened mission a planning commit AND a status
    commit both resolve/land on ``target_branch`` — unchanged from pre-mission.

    A single-branch mission has NO coordination split, so ``SPEC`` (planning) and
    ``STATUS_STATE`` (status) BOTH resolve to the one ``target_branch`` ref. The
    planning commit is exercised end-to-end (real ``commit_for_mission``); the
    status placement is asserted via the real resolver. This is the existing
    flattened behaviour the mission must not regress.

    Existing flattened planning suite cross-reference (must stay green):
    ``tests/specify_cli/cli/commands/test_wp06_sc2_paused_mission_blockers.py``
    (``TestImplementClaimNoPlanningArtifactSplit`` — flattened placement has no
    coord split).
    """
    repo = _make_repo(tmp_path, head_branch=_FLAT_TARGET_BRANCH)
    mission_id = str(ULID())
    mid8 = mission_id[:8].lower()
    slug = f"write-surface-flat-{mid8}"
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    # No coordination_branch + topology single_branch ⇒ flattened (no coord split).
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_slug": slug,
                "target_branch": _FLAT_TARGET_BRANCH,
                "topology": "single_branch",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed flattened mission")

    # Precondition: the real resolver sees a coord-LESS topology.
    assert not routes_through_coordination(resolve_topology(repo, slug))

    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )

    # Planning commit lands on target_branch (real commit).
    spec_path = feature_dir / "spec.md"
    spec_path.write_text("# Spec edited\n", encoding="utf-8")
    spec_result = commit_for_mission(
        repo, slug, (spec_path,), "flat: spec", policy, kind=MissionArtifactKind.SPEC
    )
    assert spec_result.status == "committed", spec_result.diagnostic
    assert spec_result.placement_ref == _FLAT_TARGET_BRANCH

    # Status placement resolves to the SAME single branch (no coord split).
    status_ref = resolve_placement_only(
        repo, slug, kind=MissionArtifactKind.STATUS_STATE
    ).ref
    assert status_ref == _FLAT_TARGET_BRANCH, (
        "flattened mission split status off the single branch — a coord split was "
        "fabricated where none exists (NFR-001 regression)"
    )


# ---------------------------------------------------------------------------
# T029 — FR-007 end-to-end requirement mapping (SC-001)
# ---------------------------------------------------------------------------

_T029_MISSION_ID = str(ULID())
_T029_MID8 = _T029_MISSION_ID[:8].lower()


def _scaffold_coord_mission_with_mapping(repo: Path, *, target_branch: str) -> str:
    """A coord-topology mission with planning artifacts (spec FRs + WP refs) on PRIMARY.

    The new contract: planning artifacts live on the primary surface, so finalize
    reads them with 100% requirement mapping and zero manual coordination steps.
    """
    slug = f"write-surface-map-{_T029_MID8}"
    feature_dir = repo / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    coordination_branch = f"kitty/mission-{slug}"

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": _T029_MISSION_ID,
                "mid8": _T029_MID8,
                "target_branch": target_branch,
                "coordination_branch": coordination_branch,
                "topology": "coord",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / ".gitignore").write_text(
        ".worktrees/\n.kittify/sync-state.json\n", encoding="utf-8"
    )
    branch_strategy = (
        f"Planning artifacts for this mission were generated on {target_branch}. "
        f"During /spec-kitty.implement this WP may branch from a dependency-specific "
        f"base, but completed changes must merge back into {target_branch} unless the "
        f"human explicitly redirects the landing branch."
    )
    (tasks_dir / "WP01-task.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP01\n"
        "dependencies: []\n"
        "requirement_refs:\n"
        "- FR-001\n"
        "- FR-002\n"
        "tracker_refs: []\n"
        f"planning_base_branch: {target_branch}\n"
        f"merge_target_branch: {target_branch}\n"
        f"branch_strategy: {branch_strategy}\n"
        "subtasks: []\n"
        "history: []\n"
        "authoritative_surface: src/module_wp01/\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        "- src/module_wp01/**\n"
        "tags: []\n"
        "---\n\n# WP01\n\n## Activity Log\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | First requirement | Mapped. | proposed |\n"
        "| FR-002 | Second requirement | Mapped. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed coord mission with mapping")
    _git(repo, "branch", coordination_branch)
    return slug


def _run_finalize_validate_only(repo: Path, mission_slug: str) -> Result:
    from specify_cli.cli.commands.agent.mission import app

    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.run_git_preflight",
            return_value=type("P", (), {"passed": True})(),
        ),
    ):
        return CliRunner().invoke(
            app,
            ["finalize-tasks", "--mission", mission_slug, "--validate-only", "--json"],
            catch_exceptions=False,
        )


def test_fr007_finalize_validate_only_reports_full_mapping(tmp_path: Path) -> None:
    """SC-001: planning artifacts on PRIMARY → finalize reports 100% requirements
    mapped, ZERO manual coordination-worktree steps.

    The mission is coord-topology (``coordination_branch`` set), but with the new
    contract its planning artifacts (spec FRs + WP requirement_refs) live on the
    primary surface, so ``finalize-tasks --validate-only`` reads them in-place and
    finds every functional requirement mapped — no operator must copy artifacts
    into a coordination worktree first.
    """
    repo = _make_repo(tmp_path, head_branch=_FLAT_TARGET_BRANCH)
    mission_slug = _scaffold_coord_mission_with_mapping(
        repo, target_branch=_FLAT_TARGET_BRANCH
    )

    # The mission really routes through coordination …
    assert routes_through_coordination(resolve_topology(repo, mission_slug))

    result = _run_finalize_validate_only(repo, mission_slug)

    # … yet finalize succeeds with full mapping (exit 0) — no manual coord step.
    assert result.exit_code == 0, f"finalize --validate-only failed:\n{result.output}"
    payload = json.loads(result.output.strip().splitlines()[-1])
    # A failed mapping would carry ``unmapped_functional_requirements``; success
    # never emits that key as a non-empty list.
    assert payload.get("unmapped_functional_requirements", []) == [], payload
    assert payload.get("missing_requirement_refs_wps", []) == [], payload


# ---------------------------------------------------------------------------
# T030 — FR-008 protected-primary refusal (G-4 / DECISION 6)
# ---------------------------------------------------------------------------

_TOPIC_BRANCH_REMEDY = "topic branch"
_COORD_WORKTREE_PHRASE = "coordination worktree"


@dataclass(frozen=True)
class _ProtectedCoordMission:
    repo_root: Path
    mission_slug: str
    feature_dir: Path


def _build_protected_coord_mission(tmp_path: Path) -> _ProtectedCoordMission:
    """Coord-topology mission whose ``target_branch`` is protected (``main``)."""
    repo = _make_repo(tmp_path, head_branch="main")
    mission_id = str(ULID())
    mid8 = mission_id[:8].lower()
    slug = f"write-surface-protected-{mid8}"
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_slug": slug,
                "target_branch": "main",
                "coordination_branch": f"kitty/mission-{slug}",
                "topology": "coord",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed protected coord mission")
    _git(repo, "branch", f"kitty/mission-{slug}")
    return _ProtectedCoordMission(
        repo_root=repo.resolve(), mission_slug=slug, feature_dir=feature_dir
    )


def test_fr008_router_returns_no_op_wrong_surface(tmp_path: Path) -> None:
    """DECISION 6: the ``commit_router`` REFUSAL is a RETURNED result, not a raise.

    A primary-kind (``SPEC``) commit on a protected primary ``target_branch``
    returns ``CommitRouterResult(status="no_op_wrong_surface")``; the diagnostic
    names the topic-branch remedy and never mentions the coordination worktree
    (no coord-transit fallback — C-002 / D-3 / FR-008).
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    mission = _build_protected_coord_mission(tmp_path)
    policy = ProtectionPolicy(
        protected_branches=frozenset({"main", "master"}), operator_hatch_active=False
    )
    spec_path = mission.feature_dir / "spec.md"
    spec_path.write_text("# Spec edited\n", encoding="utf-8")

    result = commit_for_mission(
        mission.repo_root,
        mission.mission_slug,
        (spec_path,),
        "protected: spec",
        policy,
        kind=MissionArtifactKind.SPEC,
    )

    assert result.status == "no_op_wrong_surface"
    diagnostic = result.diagnostic or ""
    assert _TOPIC_BRANCH_REMEDY in diagnostic, diagnostic
    assert _COORD_WORKTREE_PHRASE not in diagnostic, diagnostic


def test_fr008_safe_commit_raises_protected_branch_refused(tmp_path: Path) -> None:
    """DECISION 6: the ``safe_commit`` bypass path RAISES ``ProtectedBranchRefused``.

    The other refusal shape: a direct ``safe_commit`` to the protected primary
    branch raises ``ProtectedBranchRefused`` whose message names the topic-branch
    remedy and never mentions the coordination worktree. Asserting both shapes
    against the path that produces each is the FR-008 full-surface check; conflating
    them (raise on the router / result on safe_commit) yields a false pass/fail.
    """
    from specify_cli.git.commit_helpers import ProtectedBranchRefused, safe_commit

    mission = _build_protected_coord_mission(tmp_path)
    spec_path = mission.feature_dir / "spec.md"
    spec_path.write_text("# Spec edited\n", encoding="utf-8")

    with pytest.raises(ProtectedBranchRefused) as exc_info:
        safe_commit(
            repo_root=mission.repo_root,
            worktree_root=mission.repo_root,
            target=CommitTarget(ref="main"),
            message="protected: spec",
            paths=(spec_path,),
        )

    message = str(exc_info.value)
    assert _TOPIC_BRANCH_REMEDY in message, message
    assert _COORD_WORKTREE_PHRASE not in message, message
