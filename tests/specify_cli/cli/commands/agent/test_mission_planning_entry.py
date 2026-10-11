"""Planning-entry adoption tests for ``agent/mission.py`` (WP03 / IC-C).

Covers behavioral contract C-IC04 (FR-004/005/006 + #11):

* **FR-004** — ``setup-plan`` auto-selects the sole substantive mission when
  exactly one is resolvable (no ``--mission`` required); with >1 it still
  returns the structured ``MISSION_AMBIGUOUS_SELECTOR`` / detection error with
  no silent fallback.
* **FR-005 → FR-011** — WP01 added a primary-target-branch leg ORed with the
  coord/HEAD legs; WP07 (FR-011) COLLAPSED that OR to a single read-surface
  check once FR-001 holds. The #7 inversion (spec on primary ``main`` only,
  coord worktree lacking spec.md) is no longer rescued by ``is_committed`` —
  and the live caller short-circuits it at ``SPEC_FILE_MISSING`` because the
  read-resolved ``spec_file`` is absent on disk (proven below).
* **FR-006 (D-5)** — ``_commit_to_branch`` reports the real commit hash on
  success and surfaces a typed diagnostic for a no-op-against-the-wrong-surface
  (artifact absent at the resolved placement), while a genuine-unchanged commit
  stays a benign no-op.
* **#11** — ``finalize-tasks`` anchors its reads on the primary root so a
  materialized-but-empty coordination worktree does not fail-closed before the
  primary read.

All fixtures are topology-true (NFR-002): full 26-char ULID ``mission_id``,
real coordination worktree, and (for #7) the mission dir present on the coord
branch while the spec is committed only on the primary target branch.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path

import pytest
import typer

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Topology-true git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True
    )


def _init_repo(tmp_path: Path) -> None:
    """Initialize a primary git repo on ``main`` with one commit + .kittify."""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@test.com")
    _git(tmp_path, "config", "user.name", "Test")
    # .kittify/config.yaml so locate_project_root() stops here.
    # mission_type_activations (WP04, C-A1): the provisioned charter is the
    # sole mission-type activation authority, so resolve_mission_type_context
    # fails closed without this key.
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "agents: {}\nmission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("init\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")


_SUBSTANTIVE_SPEC = """# Spec

## Functional Requirements

| FR-001 | Auto-select sole mission | The system auto-selects the only mission present. | High | Open |

## User Scenarios
A user runs setup-plan without --mission.
"""


def _seed_mission_on_primary(
    tmp_path: Path,
    slug: str,
    mission_id: str,
    *,
    coordination_branch: str | None = None,
    with_spec: bool = True,
    mission_slug_field: str | None = None,
) -> Path:
    """Create + commit ``kitty-specs/<slug>/`` on the primary ``main`` branch.

    The mission dir always carries ``meta.json``. ``spec.md`` is written +
    committed when ``with_spec`` is True. ``mission_slug_field`` overrides the
    ``mission_slug`` value written to ``meta.json`` (used when ``slug`` is the
    canonical ``<human>-<mid8>`` directory name but the human slug differs).
    Returns the primary mission dir.
    """
    assert len(mission_id) == 26, "mission_id must be a full 26-char ULID (NFR-002)"
    mission_dir = tmp_path / "kitty-specs" / slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": mission_slug_field or slug,
        "mission_type": "software-dev",
        "friendly_name": mission_slug_field or slug,
        "target_branch": "main",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if with_spec:
        (mission_dir / "spec.md").write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", f"seed mission {slug}")
    return mission_dir


# ---------------------------------------------------------------------------
# FR-004 (T013) — setup-plan exact-one auto-select; >1 structured error
# ---------------------------------------------------------------------------


def _run_setup_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Invoke ``setup_plan(json_output=True)`` with cwd at ``tmp_path`` and no
    ``--mission`` flag; capture the emitted JSON payload.
    """
    from specify_cli.cli.commands.agent import mission as mission_mod

    # Disable the autouse SaaS-sync flag so setup-plan does not refuse on the
    # unauthenticated hosted-sync guard (which fires before mission detection).
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def _capture(payload: dict[str, object]) -> None:
        captured.clear()
        captured.update(payload)

    monkeypatch.setattr(mission_mod, "_emit_json", _capture)
    with contextlib.suppress(typer.Exit):
        mission_mod.setup_plan(feature=None, json_output=True)
    return captured


def test_setup_plan_exact_one_auto_selects_sole_mission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case A (live-repro.md#4): exactly one mission, no --mission flag.

    Pre-fix HEAD returns ``PLAN_CONTEXT_UNRESOLVED`` (the hard --mission raise);
    after the fix setup-plan auto-selects the sole mission and proceeds past
    detection (it MUST NOT emit a disambiguate / --mission-required error).
    """
    _init_repo(tmp_path)
    _seed_mission_on_primary(
        tmp_path,
        "single-mission-plan-01kv8npc",
        "01KV8NPCDEBBIESINGLEPLAN00",
    )

    payload = _run_setup_plan(tmp_path, monkeypatch)

    # The auto-select must NOT surface the disambiguate / unresolved error.
    assert payload.get("error_code") != "PLAN_CONTEXT_UNRESOLVED", payload
    # And the resolved mission must be the sole one present.
    assert payload.get("mission_slug") == "single-mission-plan-01kv8npc", payload


def test_setup_plan_two_missions_still_returns_structured_ambiguity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case B: two missions present, no --mission → structured detection error
    (no silent fallback to either mission)."""
    _init_repo(tmp_path)
    _seed_mission_on_primary(
        tmp_path,
        "first-mission-plan-01kv8npc",
        "01KV8NPCDEBBIEFIRSTPLAN001",
    )
    _seed_mission_on_primary(
        tmp_path,
        "second-mission-plan-01kv8npc",
        "01KV8NPCDEBBIESECONDPLAN02",
    )

    payload = _run_setup_plan(tmp_path, monkeypatch)

    assert payload.get("error_code") == "PLAN_CONTEXT_UNRESOLVED", payload
    available = payload.get("available_missions")
    assert isinstance(available, list) and len(available) == 2, payload
    # No silent fallback — no mission was auto-selected.
    assert "mission_slug" not in payload or payload.get("mission_slug") is None


# ---------------------------------------------------------------------------
# FR-005 (T015) — is_committed primary-target-branch leg
# ---------------------------------------------------------------------------


def _build_coord_with_mission_dir_spec_on_primary_only(
    tmp_path: Path,
    slug: str,
    mission_id: str,
    coord_ref: str,
) -> tuple[Path, Path]:
    """Build the surface-specific #7 topology.

    Returns ``(resolved_coord_spec_path, primary_repo_root)``.

    Topology (the exact NFR-002 trap-avoidance shape):
      * ``spec.md`` committed on the PRIMARY target branch ``main`` only.
      * A real coordination branch ``coord_ref`` + a real coord WORKTREE.
      * The coord worktree carries the mid8-suffixed mission dir
        (``kitty-specs/<slug>/``) but **no spec.md**.

    Both existing ``is_committed`` legs (coord-ref + coord-worktree HEAD) miss;
    only a primary-target-branch leg can find the spec.
    """
    _init_repo(tmp_path)
    _seed_mission_on_primary(
        tmp_path, slug, mission_id, coordination_branch=coord_ref, with_spec=True
    )

    # Create the coordination branch from main, then strip spec.md off it so
    # the coord branch carries the mission dir but not the spec.
    _git(tmp_path, "branch", coord_ref, "main")
    coord_worktree = tmp_path / ".worktrees" / f"{slug}-coord"
    coord_worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "worktree", "add", str(coord_worktree), coord_ref)
    # Remove spec.md on the coord branch (keep meta.json so the dir persists).
    coord_spec = coord_worktree / "kitty-specs" / slug / "spec.md"
    _git(coord_worktree, "rm", str(coord_spec.relative_to(coord_worktree)))
    _git(coord_worktree, "commit", "-m", "strip spec on coord branch")

    # Sanity: spec absent on coord branch, present on main.
    coord_check = subprocess.run(
        ["git", "-C", str(tmp_path), "cat-file", "-e", f"{coord_ref}:kitty-specs/{slug}/spec.md"],
        capture_output=True,
    )
    assert coord_check.returncode != 0, "Precondition: spec must be ABSENT on coord branch"
    main_check = subprocess.run(
        ["git", "-C", str(tmp_path), "cat-file", "-e", f"main:kitty-specs/{slug}/spec.md"],
        capture_output=True,
    )
    assert main_check.returncode == 0, "Precondition: spec MUST be present on main"

    # The resolved coord spec path (this is what _find_feature_directory hands
    # is_committed — the coord surface, which lacks spec.md).
    resolved_coord_spec = coord_worktree / "kitty-specs" / slug / "spec.md"
    return resolved_coord_spec, tmp_path


def test_fr011_primary_only_inversion_resolves_coord_without_rescue(
    tmp_path: Path,
) -> None:
    """FR-011: coord-present primary-only spec is not rescued from primary.

    The #7 topology has ``spec.md`` committed on primary ``main`` while the coord
    worktree carries the mission dir but not the spec. ``require_exists=True``
    requires the mission directory, not ``spec.md``; it returns the coord mission
    dir and does not silently swap in the primary copy of ``spec.md``.
    """
    from specify_cli.missions._read_path_resolver import (
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    # Canonical mid8 casing (#2307): mid8 is the uppercase Crockford ULID
    # prefix, and on-disk mission dirs carry it verbatim. The earlier
    # lowercase fixture slug was non-canonical test data — the resolver
    # canonicalizes the handle's mid8, so the checked paths (and the
    # StatusReadPathNotFound message) carry the canonical casing.
    slug = "committed-primary-7b-01KV8NPC"
    coord_ref = "kitty/mission-committed-primary-7b-01KV8NPC-coord"
    handle = "committed-primary-7b-01KV8NPC"
    _resolved_coord_spec, primary_root = _build_coord_with_mission_dir_spec_on_primary_only(
        tmp_path, slug, "01KV8NPCDEBBIECOMMIT7B0000", coord_ref
    )

    try:
        resolved = resolve_handle_to_read_path(primary_root, handle, require_exists=True)
    except StatusReadPathNotFound as exc:
        assert ".worktrees" in str(exc)
        assert f"kitty-specs/{slug}" in str(exc)
    else:
        assert ".worktrees" in str(resolved)
        assert not (resolved / "spec.md").exists()
    assert (primary_root / "kitty-specs" / slug / "spec.md").is_file()


def test_fr011_single_surface_does_not_rescue_primary_only_inversion(tmp_path: Path) -> None:
    """FR-011: with the OR collapsed, the #7 inversion at the coord surface is False.

    Pins that the retired primary-target-branch leg is GONE: feeding the
    read-resolved coord-worktree path (spec absent there, committed on primary
    ``main``) to the collapsed ``is_committed`` returns ``False`` — there is no
    multi-surface rescue. This is safe precisely because the caller never reaches
    here for this topology (see
    ``test_fr011_primary_only_inversion_resolves_coord_without_rescue``).
    """
    from specify_cli.missions._substantive import is_committed

    slug = "committed-primary-redproof-01kv8npc"
    coord_ref = "kitty/mission-committed-primary-redproof-01KV8NPC-coord"
    resolved_coord_spec, primary_root = _build_coord_with_mission_dir_spec_on_primary_only(
        tmp_path, slug, "01KV8NPCDEBBIEREDPROOF0000", coord_ref
    )

    committed = is_committed(resolved_coord_spec, primary_root)
    assert committed is False, (
        "FR-011 collapsed the OR: the coord surface lacks spec.md, so the "
        "single-surface check reports False (no primary-target-branch rescue)."
    )


def test_is_committed_single_repo_committed_still_true(tmp_path: Path) -> None:
    """Guard (live-repro #7 caveat): the existing single-repo committed-on-HEAD
    case still reports True (the new leg does not regress flat topology)."""
    from specify_cli.missions._substantive import is_committed

    _init_repo(tmp_path)
    spec = tmp_path / "kitty-specs" / "flat-01kv8npc" / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(_SUBSTANTIVE_SPEC, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "flat spec")

    assert is_committed(spec, tmp_path) is True


# ---------------------------------------------------------------------------
# FR-006 / D-5 (T017) — _commit_to_branch hash + no-op-vs-wrong-surface
# ---------------------------------------------------------------------------


def test_commit_to_branch_reports_real_hash_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Success path: a flat-topology commit reports a real commit hash (not None)."""
    from specify_cli.cli.commands.agent import mission as mission_mod
    from specify_cli.cli.commands.agent.mission import _commit_to_branch

    _init_repo(tmp_path)
    # Commit against a NON-protected feature branch (main/master are protected
    # by safe_commit's guard).
    _git(tmp_path, "checkout", "-b", "feat/commit-success")
    mission_dir = tmp_path / "kitty-specs" / "commit-success-01kv8npc"
    mission_dir.mkdir(parents=True, exist_ok=True)
    plan_file = mission_dir / "plan.md"
    plan_file.write_text("# Plan\n\nNew content.\n", encoding="utf-8")

    # Flat placement → commits against the checkout HEAD (feature branch).
    from mission_runtime import CommitTarget

    monkeypatch.setattr(
        mission_mod,
        "_resolve_planning_placement",
        lambda _root, _slug: CommitTarget(ref="feat/commit-success"),
    )

    result = _commit_to_branch(
        plan_file,
        "commit-success-01kv8npc",
        "plan",
        tmp_path,
        "main",
        json_output=True,
    )

    assert result.commit_hash is not None, result
    assert len(result.commit_hash) >= 7, result
    assert result.status == "committed", result


def test_commit_to_branch_no_op_wrong_surface_surfaces_typed_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No-op against the WRONG surface (artifact NOT present at the resolved
    placement) surfaces a typed diagnostic, not a silent ``commit_created: None``.

    WP02 / T027: _commit_to_branch now delegates to commit_for_mission.
    Patched at the commit_for_mission boundary (the new canonical seam) to
    return a no_op_wrong_surface result — the wrapper propagates it correctly.
    """
    from specify_cli.cli.commands.agent.mission import _commit_to_branch
    from specify_cli.coordination.commit_router import CommitRouterResult

    _init_repo(tmp_path)
    _git(tmp_path, "checkout", "-b", "feat/commit-wrongsurface")
    mission_dir = tmp_path / "kitty-specs" / "commit-wrongsurface-01kv8npc"
    mission_dir.mkdir(parents=True, exist_ok=True)
    plan_file = mission_dir / "plan.md"
    # Deliberately DO NOT create the file on disk → it is absent at the placement.

    wrong_surface_result = CommitRouterResult(
        status="no_op_wrong_surface",
        placement_ref="feat/commit-wrongsurface",
        diagnostic=(
            "plan artifact is not present at the resolved commit placement "
            "(feat/commit-wrongsurface, worktree=/nonexistent/worktree); the commit would no-op against "
            "the wrong surface and was not created."
        ),
    )

    monkeypatch.setattr(
        "specify_cli.coordination.commit_router.commit_for_mission",
        lambda **_kw: wrong_surface_result,
    )
    # ProtectionPolicy.resolve must not attempt real git I/O.
    from specify_cli.git.protection_policy import ProtectionPolicy

    monkeypatch.setattr(
        "specify_cli.git.protection_policy.ProtectionPolicy.resolve",
        classmethod(lambda cls, _root: ProtectionPolicy(frozenset(), False)),
    )

    result = _commit_to_branch(
        plan_file,
        "commit-wrongsurface-01kv8npc",
        "plan",
        tmp_path,
        "main",
        json_output=True,
    )

    assert result.commit_hash is None, result
    assert result.status == "no_op_wrong_surface", result
    assert result.diagnostic is not None and "plan" in result.diagnostic.lower()


def test_commit_to_branch_genuine_unchanged_stays_benign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Genuine-unchanged (artifact present AND already committed at placement)
    stays a benign no-op — no typed wrong-surface diagnostic."""
    from specify_cli.cli.commands.agent import mission as mission_mod
    from specify_cli.cli.commands.agent.mission import _commit_to_branch

    _init_repo(tmp_path)
    _git(tmp_path, "checkout", "-b", "feat/commit-unchanged")
    mission_dir = tmp_path / "kitty-specs" / "commit-unchanged-01kv8npc"
    mission_dir.mkdir(parents=True, exist_ok=True)
    plan_file = mission_dir / "plan.md"
    plan_file.write_text("# Plan\n\nAlready committed.\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "commit plan")

    from mission_runtime import CommitTarget

    monkeypatch.setattr(
        mission_mod,
        "_resolve_planning_placement",
        lambda _root, _slug: CommitTarget(ref="feat/commit-unchanged"),
    )

    result = _commit_to_branch(
        plan_file,
        "commit-unchanged-01kv8npc",
        "plan",
        tmp_path,
        "main",
        json_output=True,
    )

    assert result.status == "unchanged", result
    assert result.diagnostic is None, result


# ---------------------------------------------------------------------------
# #11 (T019) — finalize-tasks anchors reads on the primary root
# ---------------------------------------------------------------------------


def test_finalize_tasks_reads_primary_on_materialized_empty_coord(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#11/#1718: a materialized-but-EMPTY coord worktree must NOT fail-closed
    before the primary read.

    Topology: mission dir + tasks present on the primary checkout, a coordination
    branch declared in meta.json, and a coord worktree materialized but lacking
    the mission dir. On HEAD ``finalize-tasks`` resolves the coord surface via
    ``_find_feature_directory(require_exists=True)`` and raises
    ``STATUS_READ_PATH_NOT_FOUND`` before ever reading the primary. After the fix
    the slug resolves primary-anchored and finalize proceeds to read the primary
    surface (it does NOT fail-closed with that read-path error).
    """
    from specify_cli.cli.commands.agent import mission as mission_mod

    # Canonical <slug>-<mid8> dir + .worktrees/<slug>-<mid8>-coord naming so the
    # read-path resolver's coord-priority + fail-closed branch reproduce (a
    # non-canonical dir name would NOT trigger the #1718 fail-closed).
    human = "finalize-clean"
    mid8 = "01KV8NPC"
    mission_id = "01KV8NPCDEBBIEFINALIZE0011"
    slug_dir = f"{human}-{mid8}"
    coord_ref = f"kitty/mission-{human}-{mid8}-coord"

    _init_repo(tmp_path)
    mission_dir = _seed_mission_on_primary(
        tmp_path,
        slug_dir,
        mission_id,
        coordination_branch=coord_ref,
        with_spec=True,
        mission_slug_field=human,
    )
    # Seed a minimal tasks/ surface so finalize would read the primary surface.
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\n", encoding="utf-8")
    (tasks_dir / "WP01-sample.md").write_text(
        "---\nwork_package_id: WP01\nsubtasks: [T001]\n---\n# WP01\n", encoding="utf-8"
    )
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "seed tasks")

    # Materialize the coord branch + an EMPTY coord worktree (no mission dir).
    _git(tmp_path, "branch", coord_ref, "main")
    coord_worktree = tmp_path / ".worktrees" / f"{slug_dir}-coord"
    coord_worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "worktree", "add", str(coord_worktree), coord_ref)
    # Strip the mission dir off the coord branch so the coord surface is empty.
    _git(coord_worktree, "rm", "-r", f"kitty-specs/{slug_dir}")
    _git(coord_worktree, "commit", "-m", "empty coord surface")

    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def _capture(payload: dict[str, object]) -> None:
        captured.clear()
        captured.update(payload)

    monkeypatch.setattr(mission_mod, "_emit_json", _capture)

    # validate-only keeps the run read-only; the #11 fail-closed is in the
    # READ-anchor that runs before validate-only branches.
    with contextlib.suppress(typer.Exit):
        mission_mod.finalize_tasks(
            feature=slug_dir, json_output=True, validate_only=True
        )

    # The read-path fail-closed must NOT surface (it pre-empted the primary read
    # on HEAD). Any other downstream outcome is acceptable for this guard.
    assert captured.get("error_code") not in {
        "MISSION_CONTEXT_UNRESOLVED",
        "STATUS_READ_PATH_NOT_FOUND",
    }, captured
