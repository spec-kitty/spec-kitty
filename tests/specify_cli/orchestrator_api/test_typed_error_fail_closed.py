"""orchestrator-api read-path resolution on an EMPTY coord topology.

REMEDIATED for the single-authority topology cleanup (#2070, FR-004 / WP04
Option B). These tests live on the **external automation** surface
(``specify_cli.orchestrator_api.commands``) and exercise the
``_resolve_mission_dir`` read-path seam for a coord-declared mission whose
coordination worktree is materialized-but-empty.

Earlier (pre-mission) these tests pinned a ``topology is None`` fail-closed
band-aid: the seam was expected to raise ``StatusReadPathNotFound`` for this
fixture. The single-authority cleanup **absorbs** ``topology`` at the read-path
boundary (``classify_from_meta``) — a readable coord-declared meta classifies to
a CONCRETE ``MissionTopology``, and the EMPTY coord state then resolves to the
authoritative PRIMARY checkout (the loud warning lives at the surface) rather
than failing closed. The genuine fail-closed guarantees survive elsewhere
(corrupt/unreadable meta, a genuine absence under ``require_exists=True``, and
the #1848 ``CoordinationBranchDeleted`` data-loss carve-out) — they are simply
no longer reached for this readable EMPTY-coord case.

The fixtures stay **topology-true** (NFR-002): a real 26-char ULID
``mission_id``, a primary checkout declaring ``coordination_branch``, and a
materialized ``-coord`` worktree whose mission dir is empty.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.orchestrator_api import commands as orch
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

# Full 26-char ULID — realistic mission identity (NFR-002: no fabricated short ids).
_MISSION_ID = "01KV8NPCQ9ZX3R7W2M5T8H4FBD"
_MID8 = _MISSION_ID[:8]  # "01KV8NPC"
_HUMAN_SLUG = "read-path-error-fidelity-adoption"
_MISSION_SLUG = f"{_HUMAN_SLUG}-{_MID8}"
_COORD_BRANCH = f"kitty/mission-{_MISSION_SLUG}"


def _seed_coord_topology(tmp_path: Path) -> tuple[Path, Path]:
    """Build a real coord topology with a stale primary surface.

    The primary checkout carries the mission dir + ``meta.json`` declaring
    ``coordination_branch`` and the real ULID ``mission_id``; the ``-coord``
    worktree is materialized but its mission dir is empty. Reading the primary
    in this window exposes stale status — the exact hazard the ``bool(mid8)``
    fail-closed guard exists to refuse.

    Returns ``(repo_root, primary_mission_dir)``.
    """
    repo_root = tmp_path / "repo"
    primary = repo_root / "kitty-specs" / _MISSION_SLUG
    primary.mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "slug": _MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "coordination_branch": _COORD_BRANCH,
        "status_phase": 2,
    }
    (primary / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Stale primary status surface (would be read if the guard were suppressed).
    (primary / "status.events.jsonl").write_text("", encoding="utf-8")
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Stale\ndependencies: []\n---\n",
        encoding="utf-8",
    )

    # Materialize the coord worktree (declared topology) but DO NOT create the
    # mission dir inside it — that is the stale/empty hazard window.
    coord_root = CoordinationWorkspace.worktree_path(repo_root, _MISSION_SLUG, _MID8)
    coord_root.mkdir(parents=True)

    return repo_root, primary


def test_resolve_seam_resolves_primary_on_empty_coord_topology(tmp_path: Path) -> None:
    """Single-authority topology cleanup (FR-004 / WP04 Option B): an EMPTY coord
    worktree resolves PRIMARY, not a fail-closed raise.

    REMEDIATED from the retired ``topology is None`` husk-arm contract. This
    fixture declares ``coordination_branch`` with a real ULID ``mission_id`` but
    its ``topology`` field is absent, so the read-path BOUNDARY now classifies it
    on-read (``classify_from_meta``) into a CONCRETE ``MissionTopology`` (FR-004).
    The coord worktree root exists but its mission dir does not — the EMPTY
    transient state (C-005). Under the single-authority model the PRIMARY checkout
    is authoritative for the EMPTY state (WP04 Option B; the loud warning lives at
    the surface), so the resolver returns the primary mission dir instead of the
    pre-mission ``topology is None`` band-aid raise. The genuine fail-closed
    guarantees are preserved elsewhere — corrupt/unreadable meta
    (``topology is None``), a genuine absence under ``require_exists=True``, and
    the #1848 ``CoordinationBranchDeleted`` data-loss carve-out — they are simply
    no longer triggered for a readable, classified coord-declared mission whose
    coord surface is merely empty.
    """
    repo_root, primary = _seed_coord_topology(tmp_path)

    resolved = orch._resolve_mission_dir(repo_root, _MISSION_SLUG)

    # Single-authority: the PRIMARY checkout is the authoritative surface for the
    # EMPTY coord state — no fail-closed raise, no stale-coord husk.
    assert resolved == primary, (
        "EMPTY coord topology must resolve to the PRIMARY checkout under the "
        f"single-authority model (FR-004 / WP04 Option B); got {resolved}"
    )
    assert ".worktrees" not in str(resolved), (
        "must not route into the empty coord worktree"
    )
    assert primary.exists()


def test_mission_state_endpoint_reads_primary_on_empty_coord_topology(
    tmp_path: Path,
) -> None:
    """Single-authority topology cleanup (FR-004 / WP04 Option B): the endpoint
    reads PRIMARY status for an EMPTY coord topology rather than failing closed.

    REMEDIATED from the retired pre-mission contract (which expected the endpoint
    to surface ``STATUS_READ_PATH_NOT_FOUND`` for this fixture). Under the
    single-authority model a readable coord-declared mission is classified on-read
    into a CONCRETE topology and the EMPTY coord state resolves to the PRIMARY
    checkout (the authoritative surface). The endpoint therefore succeeds, reading
    the primary status surface (here: the seeded WP01 in ``planned``), instead of
    consulting the now-dead ``topology is None`` fail-closed husk-arm.

    The M2 typed-error pass-through machinery (``StatusReadPathNotFound`` →
    ``error_code`` + candidates, never flattened to ``MISSION_NOT_FOUND``) remains
    in ``_resolve_mission_dir_or_fail`` and is still load-bearing for the paths
    that DO raise (corrupt/unreadable meta, ``CoordinationBranchDeleted``); it is
    simply not triggered by a readable EMPTY-coord fixture anymore.
    """
    repo_root, _ = _seed_coord_topology(tmp_path)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            ["mission-state", "--mission", _MISSION_SLUG],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is True, (
        "single-authority: EMPTY coord topology reads PRIMARY and succeeds; "
        f"envelope={envelope}"
    )
    assert envelope["error_code"] is None
    # The status came from the PRIMARY surface (the seeded WP01).
    data = envelope["data"]
    assert data["mission_slug"] == _MISSION_SLUG
    wp_ids = {wp["wp_id"] for wp in data["work_packages"]}
    assert "WP01" in wp_ids


def test_genuine_not_found_still_emits_mission_not_found(tmp_path: Path) -> None:
    """Regression guard: a mission that genuinely does not exist (no coord
    topology, no fail-closed window) still emits ``MISSION_NOT_FOUND`` — the fix
    raises fidelity for the fail-closed path WITHOUT reclassifying ordinary
    not-found into the typed code.
    """
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            ["mission-state", "--mission", "999-does-not-exist"],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP03 (design-phase-orchestrator-api-01M1HE6M / T013): specify/plan/tasks
# typed-error fidelity. Kept ``fast`` (no real git I/O): the duplicate-mission
# case mocks the delegate directly rather than racing a real ULID mid8
# collision (see test_specify_plan_tasks_verbs.py's real e2e Scenario 4 for
# the genuine, deterministically-frozen end-to-end proof of the same path).
# ---------------------------------------------------------------------------


def test_specify_duplicate_mission_classifies_to_structured_error_code(
    tmp_path: Path,
) -> None:
    """#3861: the delegate's TYPED duplicate signal (``error_code`` carried in
    the ``--json`` error payload by ``MissionAlreadyExistsError``'s emission in
    ``mission_create._run_create_core_phase``) is consumed verbatim by the
    orchestrator-api ``specify`` verb and surfaced as the structured
    ``MISSION_ALREADY_EXISTS`` code.
    """
    import typer

    def _fake_duplicate(slug: str, mission_type: str | None, topology: object) -> None:
        print(
            json.dumps(
                {
                    "error": (
                        "A mission named 'wp03-dup-classify' of type "
                        "'software-dev' already exists and is not abandoned "
                        "(#4033)."
                    ),
                    "error_code": "MISSION_ALREADY_EXISTS",
                }
            )
        )
        raise typer.Exit(1)

    with patch(
        "specify_cli.cli.commands.lifecycle._create_mission_for_specify_json",
        side_effect=_fake_duplicate,
    ):
        result = runner.invoke(
            app,
            [
                "specify",
                "--mission",
                "wp03-dup-classify",
                "--mission-type",
                "software-dev",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_ALREADY_EXISTS"
    assert "message" in envelope["data"]


def test_specify_duplicate_prose_without_typed_code_is_not_already_exists(
    tmp_path: Path,
) -> None:
    """#3861 regression pin: classification consumes ONLY the delegate's typed
    ``error_code``. A bare ``{"error": ...}`` payload whose PROSE happens to
    carry the old duplicate markers ("nothing to commit", "empty changeset",
    "already exists") but carries NO typed code now classifies as the generic
    ``MISSION_CREATE_FAILED`` -- under the retired substring heuristic this
    exact payload was misclassified as ``MISSION_ALREADY_EXISTS``, so a
    message-wording change in ``create_mission`` could silently flip the
    reported failure code. Wording can no longer mislabel in either
    direction.
    """
    import typer

    def _fake_prose_only(slug: str, mission_type: str | None, topology: object) -> None:
        print(
            json.dumps(
                {
                    "error": (
                        "meta.json commit failed: safe_commit: nothing to "
                        "commit for destination_ref='wp03-work' (empty changeset)"
                    )
                }
            )
        )
        raise typer.Exit(1)

    with patch(
        "specify_cli.cli.commands.lifecycle._create_mission_for_specify_json",
        side_effect=_fake_prose_only,
    ):
        result = runner.invoke(
            app,
            [
                "specify",
                "--mission",
                "wp03-dup-prose",
                "--mission-type",
                "software-dev",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_CREATE_FAILED"
    assert "message" in envelope["data"]


def test_plan_against_nonexistent_mission_emits_mission_not_found(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "plan",
                "--mission",
                "999-does-not-exist",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_tasks_against_nonexistent_mission_emits_mission_not_found(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "tasks",
                "--mission",
                "999-does-not-exist",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP04 (design-phase-orchestrator-api-01M1HE6M / T015): check-prerequisites/
# record-analysis typed-error fidelity. Kept ``fast`` (no real git I/O): the
# mission fixture below carries no ``.git`` dir, so record-analysis's
# dirty-tree preflight no-ops (``is_git_repo`` is False) and both verbs reach
# their mission-resolution / body-validation logic directly. Real end-to-end
# artifact-verification proof lives in
# ``test_check_prerequisites_record_analysis.py``.
# ---------------------------------------------------------------------------

_WP04_MISSION_SLUG = "wp04-typed-error-mission"


def _seed_wp04_mission(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal, real (non-git) mission dir carrying spec/plan/tasks."""
    repo_root = tmp_path / "repo"
    mission_dir = repo_root / "kitty-specs" / _WP04_MISSION_SLUG
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_slug": _WP04_MISSION_SLUG,
        "slug": _WP04_MISSION_SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "status_phase": 2,
    }
    (mission_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (mission_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    return repo_root, mission_dir


def test_check_prerequisites_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            ["check-prerequisites", "--mission", "999-does-not-exist"],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_record_analysis_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "record-analysis",
                "--mission",
                "999-does-not-exist",
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_record_analysis_empty_body_is_structured_not_bare(tmp_path: Path) -> None:
    """Malformed input (an empty submitted report body) fails closed with a
    structured, distinct error_code -- never a bare exception."""
    repo_root, _mission_dir = _seed_wp04_mission(tmp_path)
    empty_file = tmp_path / "empty-report.md"
    empty_file.write_text("   \n", encoding="utf-8")

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "record-analysis",
                "--mission",
                _WP04_MISSION_SLUG,
                "--input-file",
                str(empty_file),
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "RECORD_ANALYSIS_EMPTY_BODY"


def test_record_analysis_missing_input_file_is_structured_not_bare(tmp_path: Path) -> None:
    """A nonexistent --input-file fails closed with a structured error_code."""
    repo_root, _mission_dir = _seed_wp04_mission(tmp_path)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "record-analysis",
                "--mission",
                _WP04_MISSION_SLUG,
                "--input-file",
                str(tmp_path / "does-not-exist.md"),
                "--policy",
                json.dumps(
                    {
                        "orchestrator_id": "test-orch",
                        "orchestrator_version": "0.0.1",
                        "agent_family": "claude",
                        "approval_mode": "full_auto",
                        "sandbox_mode": "workspace_write",
                        "network_mode": "none",
                        "dangerous_flags": [],
                    }
                ),
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "RECORD_ANALYSIS_INPUT_FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP05 (design-phase-orchestrator-api-01M1HE6M / T027): open-decision/
# resolve-decision/defer-decision/cancel-decision typed-error fidelity, per
# verb -- same MISSION_NOT_FOUND-against-nonexistent-mission pattern as
# plan/tasks/check-prerequisites/record-analysis above. These reuse the
# SAME shared ``_resolve_mission_dir_or_fail`` seam (unmodified by WP05), so
# the coverage here confirms the new verbs are wired to it correctly rather
# than re-proving the seam itself.
# ---------------------------------------------------------------------------

_WP05_POLICY = json.dumps(
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


def test_open_decision_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "open-decision",
                "--mission",
                "999-does-not-exist",
                "--origin",
                "specify",
                "--input-key",
                "k",
                "--question",
                "q?",
                "--step-id",
                "s1",
                "--actor",
                "test-agent",
                "--policy",
                _WP05_POLICY,
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_resolve_decision_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "resolve-decision",
                "--mission",
                "999-does-not-exist",
                "--decision-id",
                "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "--final-answer",
                "5",
                "--actor",
                "test-agent",
                "--policy",
                _WP05_POLICY,
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_defer_decision_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "defer-decision",
                "--mission",
                "999-does-not-exist",
                "--decision-id",
                "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "--rationale",
                "need more info",
                "--actor",
                "test-agent",
                "--policy",
                _WP05_POLICY,
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


def test_cancel_decision_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "cancel-decision",
                "--mission",
                "999-does-not-exist",
                "--decision-id",
                "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "--rationale",
                "no longer relevant",
                "--actor",
                "test-agent",
                "--policy",
                _WP05_POLICY,
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP06 (design-phase-orchestrator-api-01M1HE6M / T032): design-status typed-
# error fidelity -- same MISSION_NOT_FOUND-against-nonexistent-mission
# pattern as every read-only verb above. Confirms design-status is wired to
# the SAME shared ``_resolve_mission_dir_or_fail`` seam rather than
# re-proving the seam itself. No --policy is required for design-status
# (read-only, matches list-ready's own contract), so unlike the WP05 block
# above there is no companion POLICY_METADATA_REQUIRED case to mirror.
# ---------------------------------------------------------------------------


def test_design_status_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "design-status",
                "--mission",
                "999-does-not-exist",
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# WP08 (design-phase-orchestrator-api-01M1HE6M / T041): answer-decision
# typed-error fidelity -- same MISSION_NOT_FOUND-against-nonexistent-mission
# pattern as every mutating verb above. Confirms answer-decision is wired to
# the SAME shared ``_resolve_mission_dir_or_fail`` seam (existence gate FIRST,
# before any run-snapshot resolution) rather than re-proving the seam itself.
# ---------------------------------------------------------------------------


def test_answer_decision_against_nonexistent_mission_emits_mission_not_found(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "kitty-specs").mkdir(parents=True)

    with patch.object(orch, "_get_main_repo_root", return_value=repo_root):
        result = runner.invoke(
            app,
            [
                "answer-decision",
                "--mission",
                "999-does-not-exist",
                "--agent",
                "test-agent",
                "--answer",
                "approve",
                "--result",
                "success",
                "--policy",
                _WP05_POLICY,
            ],
            catch_exceptions=False,
        )

    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is False
    assert envelope["error_code"] == "MISSION_NOT_FOUND"
