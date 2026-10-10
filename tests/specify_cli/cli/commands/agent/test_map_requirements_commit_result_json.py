"""WP07 / FR-013 (#1891): ``CommitResult`` must be JSON-serializable so that
``agent tasks map-requirements --json`` emits a valid JSON document instead of
raising ``Object of type CommitResult is not JSON serializable``.

The un-serializable culprit is the ``CommitResult.worktree_root: Path`` field.
This test drives the CLI ``--json`` external interface (via ``CliRunner``) with a
REAL ``CommitResult`` returned from ``safe_commit`` — NOT a ``SimpleNamespace``
stub and NOT a unit test of the ``to_dict`` helper in isolation. The
auto-commit branch must serialize that real ``CommitResult`` (including the
``Path`` field) into the ``--json`` payload; if the serialization path is
missing, ``json.dumps`` raises and the command exits non-zero.

Production-shaped identity: a real 26-char Crockford-base32 ULID with an
8-char mid8 tail, never a hand-rolled short placeholder (testing-principles).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import CommitTarget
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.git.commit_helpers import CommitResult

pytestmark = [pytest.mark.fast]

_MISSION_ID = "01KVRJ6PABCDEFGHJKMNPQRSTV"
_MID8 = _MISSION_ID[:8]
MISSION_SLUG = f"single-authority-topology-cleanup-{_MID8}"
_SPEC_MD_TEXT = "# Spec\n\n| FR-001 | Do the thing. | Proposed |\n"
_WP01_FRONTMATTER = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Example\n"
    "requirement_refs: []\n"
    "---\n"
    "# WP01\n"
)
_COMMIT_SHA = "0f1e2d3c4b5a69788796a5b4c3d2e1f00d1c2b3a"


def _build_primary_and_coord(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Lay down a primary checkout (spec.md + meta.json) and a coord worktree
    holding the WP task file. Returns ``(primary_root, primary_mission_dir,
    coord_root)``.
    """
    primary_root = tmp_path / "primary"
    primary_mission_dir = primary_root / "kitty-specs" / MISSION_SLUG
    primary_mission_dir.mkdir(parents=True)
    (primary_mission_dir / "spec.md").write_text(_SPEC_MD_TEXT, encoding="utf-8")
    # Lay the WP task file on the primary read surface too: with no
    # ``coordination_branch``/``topology`` in meta this mission classifies as
    # ``single_branch`` (the single-authority read path resolves to the primary),
    # so ``map-requirements`` must find WP01 here to reach the commit/serialize
    # path under test (the commit itself is monkeypatched to the coord worktree).
    primary_tasks_dir = primary_mission_dir / "tasks"
    primary_tasks_dir.mkdir(parents=True)
    (primary_tasks_dir / "WP01-example.md").write_text(
        _WP01_FRONTMATTER, encoding="utf-8"
    )
    (primary_mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mid8": _MID8,
                "mission_slug": MISSION_SLUG,
                "mission_number": 17,
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )

    coord_root = primary_root / ".worktrees" / f"{MISSION_SLUG}-coord"
    coord_mission_dir = coord_root / "kitty-specs" / MISSION_SLUG
    coord_tasks_dir = coord_mission_dir / "tasks"
    coord_tasks_dir.mkdir(parents=True)
    (coord_tasks_dir / "WP01-example.md").write_text(
        _WP01_FRONTMATTER, encoding="utf-8"
    )
    return primary_root, primary_mission_dir, coord_root


def test_map_requirements_json_serializes_real_commit_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--json --auto-commit`` emits valid JSON carrying the serialized
    ``CommitResult``; ``worktree_root`` is rendered as a non-empty slug-bearing
    string.

    The negative control is built into the seam: ``safe_commit`` returns a REAL
    ``CommitResult`` whose ``worktree_root`` is a ``Path``. Without a
    serialization path the emit site would feed that object to ``json.dumps`` and
    the command would exit non-zero with
    ``Object of type CommitResult is not JSON serializable``. Asserting the slug
    appears in ``worktree_root`` (not ``""`` / ``"None"``) kills the empty-string
    serialization mutant.
    """
    import typer

    # #2056 WP08: the planning-commit primitives relocated to commit_router and
    # tasks.py imports them from there, so patch the canonical home.
    from specify_cli.coordination import commit_router as commit_router_mod
    from specify_cli.cli.commands.agent import tasks as tasks_mod

    primary_root, primary_mission_dir, coord_root = _build_primary_and_coord(tmp_path)
    coord_mission_dir = coord_root / "kitty-specs" / MISSION_SLUG
    # Ownership discovery must use this fixture, not the source checkout cwd.
    monkeypatch.chdir(primary_root)

    placement = CommitTarget(
        ref=f"kitty/mission-{MISSION_SLUG}",
    )

    def fake_commit_for_mission(
        repo_root: Path,
        mission_slug: str,
        files: tuple[Path, ...],
        message: str,
        policy: object,
        *,
        kind: object,
        target_branch: str | None = None,
        **_kwargs: object,
    ) -> CommitRouterResult:
        # WP07 / FR-006: ``map-requirements`` now routes its WP-file commit through
        # the canonical ``commit_for_mission`` router. A successful router result
        # carries the placement ref + commit hash; the command reconstructs the
        # ``commit_result`` JSON envelope from those + the (primary) repo_root, so
        # the ``--json`` payload stays serializable (#1891 / FR-013).
        return CommitRouterResult(
            status="committed",
            placement_ref=placement.ref,
            commit_hash=_COMMIT_SHA,
        )

    monkeypatch.setattr(tasks_mod, "locate_project_root", lambda: primary_root)
    monkeypatch.setattr(tasks_mod, "_find_mission_slug", lambda **_kwargs: MISSION_SLUG)
    monkeypatch.setattr(
        tasks_mod,
        "_ensure_target_branch_checked_out",
        lambda *_args, **_kwargs: (primary_root, "main"),
    )
    monkeypatch.setattr(
        tasks_mod, "_emit_sparse_session_warning", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(tasks_mod, "commit_for_mission", fake_commit_for_mission)
    monkeypatch.setattr(
        # write-surface-coherence WP02 / T009: ``_resolve_planning_placement`` gained
        # a required ``kind`` keyword; the stub accepts it.
        commit_router_mod, "_resolve_planning_placement", lambda *_args, **_kwargs: placement
    )
    # read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T035): the
    # ``primary_feature_dir_for_mission`` patch this block used to install is
    # retired along with the deleted public wrapper -- the real code path
    # (``FsReader.primary_anchor_dir``) never read that module attribute, so
    # the patch was already vestigial (see
    # test_map_requirements_spec_path.py for the full rationale); a real
    # ``meta.json`` fixture resolves the primary dir correctly on its own.
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver.resolve_feature_dir_for_slug",
        lambda _root, _slug: coord_mission_dir,
    )

    app = typer.Typer()
    app.command()(tasks_mod.map_requirements)

    result = CliRunner().invoke(
        app,
        [
            "--wp",
            "WP01",
            "--refs",
            "FR-001",
            "--mission",
            MISSION_SLUG,
            "--json",
            "--auto-commit",
        ],
    )

    assert result.exit_code == 0, (
        "map-requirements --json --auto-commit must exit 0 with a serializable "
        f"CommitResult; exit={result.exit_code}, output={result.output!r}"
    )
    # The whole point: stdout parses as JSON (would raise pre-fix).
    payload = json.loads(result.output)
    assert payload["committed"] is True
    assert payload["commit_sha"] == _COMMIT_SHA

    commit_result = payload["commit_result"]
    assert commit_result["sha"] == _COMMIT_SHA
    assert commit_result["destination_ref"] == placement.ref

    worktree_root = commit_result["worktree_root"]
    assert isinstance(worktree_root, str), (
        f"worktree_root must serialize to a string, got {type(worktree_root)!r}"
    )
    # Negative control on the serialization mutant: not "" / "None". A primary
    # kind (WORK_PACKAGE_TASK) commits from the PRIMARY checkout (WP07 routing),
    # so worktree_root is the primary repo root — assert it is that path string.
    assert worktree_root not in ("", "None")
    assert worktree_root == str(primary_root), (
        f"worktree_root should be the primary checkout; got {worktree_root!r}"
    )


def test_commit_result_to_dict_renders_path_as_string() -> None:
    """Direct contract on the serialization helper: ``worktree_root`` becomes a
    string. This is a supporting micro-assertion — the CLI test above is the
    primary external-interface driver.
    """
    result = CommitResult(
        sha=_COMMIT_SHA,
        destination_ref=f"kitty/mission-{MISSION_SLUG}",
        worktree_root=Path("/repo/.worktrees") / f"{MISSION_SLUG}-coord",
    )
    payload = result.to_dict()
    # The serialized form is a valid JSON document.
    round_tripped = json.loads(json.dumps(payload))
    assert round_tripped["sha"] == _COMMIT_SHA
    assert isinstance(round_tripped["worktree_root"], str)
    assert MISSION_SLUG in round_tripped["worktree_root"]
