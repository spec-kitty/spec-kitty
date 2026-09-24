"""WP04 (FR-003 / C-IC03) — ``decision`` single read-path authority.

These tests pin the #8 live symptom and its fix:

* ``decision open`` and ``decision verify`` MUST resolve mission handles through
  the **single** canonical read-path authority (``resolve_action_context`` /
  ``resolve_mission_read_path``) — there is no private escape-walk second
  authority asserting the resolved path stays under ``repo_root/kitty-specs/``.
* On an unresolvable coord topology the failure MUST surface as a **structured
  typed diagnostic** carrying the resolver's real ``code`` — never an uncaught
  Python/Rich traceback (the live #8 symptom).
* The ``_SAFE_SLUG_RE`` traversal-rejection on the **raw operator token** stays:
  validate the input boundary, trust the resolver's output (DIR-031).

Topology-true fixtures only (NFR-002): full 26-char ULID ``mission_id`` and the
``coordination_branch``-declared topology from ``research/live-repro.md#8``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent import app as agent_app
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _materialize_coord_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

# Production-shaped identity: a real 26-char Crockford-base32 ULID and the
# matching human slug embedding its mid8, mirroring the debbie-coord repro.
MISSION_ID = "01KV8NPCDEBBIE0REPRO0COORD"
MID8 = MISSION_ID[:8]  # "01KV8NPC"
SLUG = f"read-path-coord-repro-{MID8.lower()}"
COORD_BRANCH = f"kitty/mission-{SLUG}-coord"


# ---------------------------------------------------------------------------
# Fixtures — topology-true, real git repo (the rev-parse deleted-branch probe
# only fires R3 in a genuine repository).
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    _git(repo, "config", "user.email", "t@t.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)


def _write_meta(mission_dir: Path, *, coordination_branch: str | None) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"mission_id": MISSION_ID, "mission_slug": SLUG}
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _coord_declared_no_worktree(tmp_path: Path) -> Path:
    """The repro #8 topology: meta declares a coord branch, but neither the
    coord branch nor the coord worktree are materialized → fail-closed."""
    _init_repo(tmp_path)
    _write_meta(tmp_path / "kitty-specs" / SLUG, coordination_branch=COORD_BRANCH)
    return tmp_path


def _coord_materialized(tmp_path: Path) -> Path:
    """A resolvable coord topology: the coord worktree dir tree exists on disk
    (``resolve_mission_read_path`` is pure-path), so the handle resolves."""
    _init_repo(tmp_path)
    # Primary dir declares the coordination branch (read-path mediation).
    _write_meta(tmp_path / "kitty-specs" / SLUG, coordination_branch=COORD_BRANCH)
    # Materialize the coord worktree's mission dir so the resolver returns it.
    coord_mission_dir = tmp_path / ".worktrees" / f"{SLUG}-{MID8}-coord" / "kitty-specs" / f"{SLUG}-{MID8}"
    _write_meta(coord_mission_dir, coordination_branch=COORD_BRANCH)
    return tmp_path


def _invoke(args: list[str], cwd: Path) -> object:
    old_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        # catch_exceptions=True so an UNCAUGHT resolver error is captured as a
        # traceback (result.exception) — the live #8 symptom we assert against —
        # instead of bubbling out of the test and aborting collection.
        return runner.invoke(agent_app, args, catch_exceptions=True)
    finally:
        os.chdir(old_cwd)


def _assert_no_raw_traceback(result: object) -> None:
    """The #8 symptom is an *uncaught* resolver exception surfacing as a Rich
    traceback. A clean ``typer.Exit`` / ``SystemExit`` (the structured-error
    exit) is NOT a traceback — the CLI handled the error and emitted a payload.
    """
    exc = result.exception  # type: ignore[attr-defined]
    assert exc is None or isinstance(exc, SystemExit), f"uncaught resolver traceback (the #8 symptom): {exc!r}"


def _parse_json_lines(output: str) -> list[dict]:  # type: ignore[type-arg]
    return [json.loads(line) for line in output.splitlines() if line.strip()]


_ESCAPE_MSG = "Mission path would escape kitty-specs/"


def _open_args(mission: str) -> list[str]:
    return [
        "decision",
        "open",
        "--mission",
        mission,
        "--flow",
        "plan",
        "--input-key",
        "approach",
        "--question",
        "Which approach?",
        "--options",
        '["a","b"]',
        "--step-id",
        "step-1",
        "--json",
    ]


# ---------------------------------------------------------------------------
# T020 Case A — decision open resolves a valid coord-aware handle (success)
# ---------------------------------------------------------------------------


def test_open_resolves_coord_aware_handle(tmp_path: Path) -> None:
    """C-IC03: a valid coord-aware handle MUST succeed through the single
    canonical authority — no escape-string, no raw traceback."""
    repo = _coord_materialized(tmp_path)

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result = _invoke(_open_args(SLUG), cwd=repo)

    _assert_no_raw_traceback(result)
    assert result.exit_code == 0, f"open failed: {result.output!r}"  # type: ignore[attr-defined]
    assert _ESCAPE_MSG not in result.output  # type: ignore[attr-defined]
    payload = _parse_json_lines(result.output)[-1]  # type: ignore[attr-defined]
    assert payload["contract"] == "decision_open_v2"


# ---------------------------------------------------------------------------
# T020 Case B — raw traversal token is still rejected (_SAFE_SLUG_RE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["../evil", "../../etc/passwd", "foo/../bar"])
def test_open_rejects_traversal_token(tmp_path: Path, token: str) -> None:
    repo = _coord_declared_no_worktree(tmp_path)
    result = _invoke(_open_args(token), cwd=repo)
    # typer.BadParameter → exit code 2, and the validation message names the
    # offending token. The resolver must NEVER be reached for a traversal token.
    assert result.exit_code != 0  # type: ignore[attr-defined]
    assert "must match" in result.output or token in result.output  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# T020 Case C — open surfaces a STRUCTURED typed error, not a traceback
# ---------------------------------------------------------------------------


def test_open_structured_error_on_unresolvable_coord(tmp_path: Path) -> None:
    """Repro #8: on the coord-declared-no-worktree topology the resolver raises
    (COORDINATION_BRANCH_DELETED). The CLI MUST render a structured ``--json``
    error carrying the real ``code`` — NOT an uncaught Rich traceback."""
    repo = _coord_declared_no_worktree(tmp_path)

    result = _invoke(_open_args(SLUG), cwd=repo)

    _assert_no_raw_traceback(result)
    assert result.exit_code == 1  # type: ignore[attr-defined]
    payloads = _parse_json_lines(result.output)  # type: ignore[attr-defined]
    assert payloads, f"expected a structured JSON error, got: {result.output!r}"  # type: ignore[attr-defined]
    payload = payloads[-1]
    assert payload.get("code") == "COORDINATION_BRANCH_DELETED"
    assert _ESCAPE_MSG not in result.output  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# T043 Case D — decision verify surfaces a STRUCTURED typed error (M5)
# ---------------------------------------------------------------------------


def _verify_args(mission: str) -> list[str]:
    return ["decision", "verify", "--mission", mission, "--json"]


def test_verify_structured_error_on_unresolvable_coord(tmp_path: Path) -> None:
    """M5: ``cmd_verify`` calls ``resolve_mission_read_path`` directly at its own
    seam; on the coord-declared-no-worktree topology that raises
    ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound`` subclass). The
    CLI MUST render a structured typed diagnostic (real ``error_code``), not an
    uncaught traceback — the same #8 class deleted on ``open``."""
    repo = _coord_declared_no_worktree(tmp_path)

    result = _invoke(_verify_args(SLUG), cwd=repo)

    _assert_no_raw_traceback(result)
    assert result.exit_code == 1  # type: ignore[attr-defined]
    payloads = _parse_json_lines(result.output)  # type: ignore[attr-defined]
    assert payloads, f"expected a structured JSON error, got: {result.output!r}"  # type: ignore[attr-defined]
    payload = payloads[-1]
    assert payload.get("code") == "COORDINATION_BRANCH_DELETED"


def test_verify_rejects_traversal_token(tmp_path: Path) -> None:
    """T023: the shared ``_SAFE_SLUG_RE`` rejection holds on ``verify`` too."""
    repo = _coord_declared_no_worktree(tmp_path)
    result = _invoke(_verify_args("../evil"), cwd=repo)
    assert result.exit_code != 0  # type: ignore[attr-defined]
    assert "must match" in result.output or "../evil" in result.output  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# T009 (#4966) — MATERIALIZED status-only husk: ``meta.json`` resolves via
# PRIMARY, not the coord husk. Independent of the ``_coord_materialized``
# fixture above (WP04's), which copies ``meta.json`` into the coord worktree
# too and so never exercises this bug. Here the coord worktree is genuinely
# materialised (real ``CoordinationWorkspace.resolve``-backed git worktree,
# ``kitty-specs/<slug>/`` exists on it) but carries ONLY
# ``status.events.jsonl`` -- "and nothing else"
# (``specify_cli/coordination/coherence.py:168``) -- no ``meta.json``, no
# ``decisions/``.
# ---------------------------------------------------------------------------

_HUSK_WORK_BRANCH = "decision-ledger-husk-work"
_HUSK_SLUG = "decision-ledger-husk"


def _husk_materialized_coord_mission(tmp_path: Path) -> str:
    """Build a coord-topology mission with a MATERIALIZED status-only husk.

    ``meta.json`` lives ONLY on the PRIMARY checkout (real mission creation via
    ``create_mission_core``, mirroring the golden-path fixtures). The coord
    worktree is genuinely materialised on disk via the SAME canonical
    ``CoordinationWorkspace.resolve`` writers use, and its
    ``kitty-specs/<slug>/`` dir is populated with ONLY ``status.events.jsonl``
    -- never ``meta.json``, never ``decisions/`` -- so this is the true
    #4966 MATERIALIZED-husk locus, not the fully-mirrored fixture WP04 pinned
    above.

    Returns the mission slug (the primary and coord dirs share this name).
    """
    _init_git_repo(tmp_path, branch=_HUSK_WORK_BRANCH)
    result = _create_mission(tmp_path, _HUSK_SLUG, MissionTopology.COORD)
    coord_root = _materialize_coord_worktree(tmp_path, result)
    coord_mission_dir = coord_root / "kitty-specs" / result.mission_slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")

    assert not (coord_mission_dir / "meta.json").exists(), "fixture invariant: the husk must NOT carry meta.json"
    assert not (coord_mission_dir / "decisions").exists(), "fixture invariant: the husk must NOT carry a decisions/ ledger dir"
    assert (result.feature_dir / "meta.json").exists(), "fixture invariant: meta.json must live on PRIMARY"
    # Explicit annotation: under the project's ``follow_imports = "skip"`` mypy
    # config, ``MissionCreationResult.mission_slug`` (cross-module) widens to
    # ``Any`` — re-narrow it here (matches the established pattern elsewhere,
    # e.g. ``resolution.py``'s ``PlacementSeam.read_dir`` callers).
    mission_slug: str = result.mission_slug
    return mission_slug


def test_open_resolves_meta_via_primary_on_materialized_status_only_husk(
    tmp_path: Path,
) -> None:
    """AC-D1 (#4966): ``decision open`` on a MATERIALIZED status-only husk must
    resolve ``meta.json`` via PRIMARY -- never ``MISSION_NOT_FOUND``.

    Pre-fix: ``_resolve_mission_id`` routes through ``_mission_dir`` ->
    ``placement_seam(...).read_dir(STATUS_STATE)`` -> the coord husk -> no
    ``meta.json`` there -> ``DecisionError(MISSION_NOT_FOUND)``. This is the
    exact bug that blocked THIS mission's own ``decision open`` during its own
    plan phase (see ``tracer-tooling-friction.md``).
    """
    slug = _husk_materialized_coord_mission(tmp_path)

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        result = _invoke(_open_args(slug), cwd=tmp_path)

    _assert_no_raw_traceback(result)
    payloads = _parse_json_lines(result.output)  # type: ignore[attr-defined]
    assert payloads, f"expected a JSON payload, got: {result.output!r}"  # type: ignore[attr-defined]
    payload = payloads[-1]
    assert payload.get("code") != "MISSION_NOT_FOUND", f"#4966: decision open resolved meta.json through the coord husk instead of PRIMARY: {payload}"
    assert result.exit_code == 0, f"open failed: {result.output!r}"  # type: ignore[attr-defined]
    assert payload["contract"] == "decision_open_v2"
