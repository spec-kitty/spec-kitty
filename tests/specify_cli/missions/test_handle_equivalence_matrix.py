"""Handle-equivalence matrix for mission handle canonicalization (F-001).

Acceptance criterion (PR #1850 / mission 01KTPKST F-001 closeout): the full
``<slug>-<mid8>`` slug, a bare ``mid8``, and a numeric prefix handle must
produce IDENTICAL ``mission_slug``, ``mission_id``, ``coordination_branch``,
status surface paths, and placement (ref AND kind) — never a wrong-but-plausible
``kitty-specs/<mid8>/`` path, never a ``legacy-<mid8>`` identity.

Pre-fix, canonicalization stopped inside the read resolver: downstream
compositions (``primary_feature_dir_for_mission`` re-anchors, identity reads,
the ``_find_mission_slug`` boundary short-circuits) kept consuming the RAW
operator handle, so a mid8 handle yielded ``kitty-specs/<mid8>/`` surfaces,
``legacy-<mid8>`` identity, and a COORDINATION→FLATTENED placement flip.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import Result

from mission_runtime import (
    MissionArtifactKind,
    resolve_action_context,
    resolve_placement_only,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.surface_resolver import (
    resolve_status_surface,
    resolve_status_surface_with_anchor,
)
from specify_cli.status import MissionStatus

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Mission A — canonical suffix-named directory, flattened topology.
_MISSION_ID = "01KTPKST0000000000000000AB"
_MID8 = _MISSION_ID[:8]  # "01KTPKST"
_FULL_SLUG = f"083-my-feature-{_MID8}"

# Mission B — coord topology (declared coordination_branch, worktree not yet
# materialized: the pre-materialization window the placement flip hits).
_COORD_MISSION_ID = "01KTC88R0000000000000000CD"
_COORD_MID8 = _COORD_MISSION_ID[:8]  # "01KTC88R"
_COORD_SLUG = f"091-coord-feature-{_COORD_MID8}"
_COORD_BRANCH = f"kitty/mission-{_COORD_SLUG}"

# Mission C — backfilled identity: directory name carries NO -mid8 suffix
# (the `spec-kitty migrate backfill-identity` shape). Recomposing
# ``<slug>-<mid8>`` from the canonical pair double-suffixes and misses.
_BACKFILLED_MISSION_ID = "01KTNMER0000000000000000EF"
_BACKFILLED_MID8 = _BACKFILLED_MISSION_ID[:8]  # "01KTNMER"
_BACKFILLED_SLUG = "084-backfilled-mission"

_TARGET_BRANCH = "feat/non-protected-work"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _seed_mission(
    repo_root: Path,
    *,
    slug: str,
    mission_id: str,
    coordination_branch: str | None = None,
) -> Path:
    feature_dir = repo_root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": mission_id,
        "mission_slug": slug,
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "friendly_name": slug,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    event = {
        "actor": "claude",
        "at": "2026-06-11T00:00:00+00:00",
        "event_id": "01HXYZABCDEFGHJKMNPQRSTVWX",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": slug,
        "force": False,
        "from_lane": "planned",
        "reason": None,
        "review_ref": None,
        "to_lane": "claimed",
        "wp_id": "WP01",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(event) + "\n", encoding="utf-8"
    )
    return feature_dir


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text(
        "project:\n  uuid: matrix-project-uuid-1234\n"
        "agents:\n  available:\n    - claude\n",
        encoding="utf-8",
    )
    _seed_mission(r, slug=_FULL_SLUG, mission_id=_MISSION_ID)
    _seed_mission(
        r,
        slug=_COORD_SLUG,
        mission_id=_COORD_MISSION_ID,
        coordination_branch=_COORD_BRANCH,
    )
    _seed_mission(r, slug=_BACKFILLED_SLUG, mission_id=_BACKFILLED_MISSION_ID)
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "fixture")
    # Mission B declares a coordination_branch. Real mission creation runs the
    # structural ``ensure_coordination_branch`` step (missions/_create.py) BEFORE
    # the first status write, so a declared coord branch always exists in git
    # during the create→first-write window (#1889 row R2). The branch is created
    # here to model that contract; otherwise the resolver correctly classifies a
    # declared-but-absent branch as R3 (deleted, #1848 carve-out).
    _git(r, "branch", _COORD_BRANCH)
    return r


# ---------------------------------------------------------------------------
# Status surface parity — never kitty-specs/<mid8>/status.events.jsonl
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_status_surface_identical_across_handle_forms(repo: Path, handle: str) -> None:
    baseline = resolve_status_surface_with_anchor(repo, _FULL_SLUG)
    resolved = resolve_status_surface_with_anchor(repo, handle)
    assert resolved.surface_path == baseline.surface_path, (
        f"handle {handle!r} must resolve the SAME status surface as the full "
        f"slug — never the wrong-but-plausible kitty-specs/{handle}/ path"
    )
    assert resolved.primary_anchor == baseline.primary_anchor


@pytest.mark.parametrize("handle", [_COORD_SLUG, _COORD_MID8, "091"])
def test_coord_status_surface_identical_across_handle_forms(
    repo: Path, handle: str
) -> None:
    baseline = resolve_status_surface_with_anchor(repo, _COORD_SLUG)
    resolved = resolve_status_surface_with_anchor(repo, handle)
    assert resolved.surface_path == baseline.surface_path
    assert resolved.primary_anchor == baseline.primary_anchor


# ---------------------------------------------------------------------------
# Placement parity — ref AND kind (the #1784 COORDINATION→FLATTENED flip class)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_flattened_placement_identical_across_handle_forms(
    repo: Path, handle: str
) -> None:
    # STATUS_STATE (topology-routed kind) keeps the handle-invariance property
    # under the now-required kind (write-surface-coherence WP02 / T031): a
    # flattened mission routes to target_branch for any kind.
    baseline = resolve_placement_only(
        repo, _FULL_SLUG, kind=MissionArtifactKind.STATUS_STATE
    )
    placement = resolve_placement_only(
        repo, handle, kind=MissionArtifactKind.STATUS_STATE
    )
    assert placement == baseline  # ref-only CommitTarget equality (C-007)
    # FR-001b: routing reads the STORED topology, handle-invariant — a flattened
    # mission never routes through coordination, regardless of handle form.
    assert routes_through_coordination(resolve_topology(repo, handle)) is False
    assert placement.ref == _TARGET_BRANCH


@pytest.mark.parametrize("handle", [_COORD_SLUG, _COORD_MID8, "091"])
def test_coord_placement_never_flips_to_flattened(repo: Path, handle: str) -> None:
    # STATUS_STATE (coord-routed kind): a coord-topology mission keeps resolving
    # the coordination branch under every handle form (write-surface-coherence
    # WP02 / T031). A PRIMARY kind would correctly flip to primary, so the
    # "never flips to flattened" coord-routing property is asserted with the
    # coord-preserving kind.
    placement = resolve_placement_only(repo, handle, kind=MissionArtifactKind.STATUS_STATE)
    assert routes_through_coordination(resolve_topology(repo, handle)) is True, (
        f"handle {handle!r} flipped a coord-topology mission to a coord-less "
        f"surface — planning commits would target {placement.ref!r} instead of "
        "the coordination branch (FR-001b: routing reads the stored topology)"
    )
    assert placement.ref == _COORD_BRANCH


# ---------------------------------------------------------------------------
# Action-context identity parity — never 'legacy-<mid8>' / mid8 'legacy-0'
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_action_context_identity_identical_across_handle_forms(
    repo: Path, handle: str
) -> None:
    baseline = resolve_action_context(repo, action="status", feature=_FULL_SLUG)
    ctx = resolve_action_context(repo, action="status", feature=handle)

    assert ctx.mission_slug == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into mission_slug ({ctx.mission_slug!r})"
    )
    assert ctx.feature_dir == baseline.feature_dir
    assert ctx.target_branch == baseline.target_branch
    assert ctx.identity is not None and baseline.identity is not None
    assert ctx.identity.mission_id == _MISSION_ID
    assert ctx.identity.mid8 == _MID8
    assert ctx.branch_ref == baseline.branch_ref
    assert ctx.status_surface is not None and baseline.status_surface is not None
    assert ctx.status_surface.status_read_dir == baseline.status_surface.status_read_dir
    assert ctx.status_surface.status_write_dir == baseline.status_surface.status_write_dir


@pytest.mark.parametrize("handle", [_BACKFILLED_SLUG, _BACKFILLED_MID8, "084"])
def test_backfilled_mission_handles_resolve_real_directory(
    repo: Path, handle: str
) -> None:
    """A backfilled mission (dir name lacks the -mid8 suffix) must resolve via
    its mid8 / numeric handle — never hard-fail on a double-suffixed
    ``kitty-specs/<slug>-<mid8>`` recomposition."""
    baseline = resolve_action_context(repo, action="status", feature=_BACKFILLED_SLUG)
    ctx = resolve_action_context(repo, action="status", feature=handle)

    assert ctx.mission_slug == _BACKFILLED_SLUG
    assert ctx.feature_dir == baseline.feature_dir
    assert ctx.identity is not None
    assert ctx.identity.mission_id == _BACKFILLED_MISSION_ID

    baseline_surface = resolve_status_surface_with_anchor(repo, _BACKFILLED_SLUG)
    resolved_surface = resolve_status_surface_with_anchor(repo, handle)
    assert resolved_surface.surface_path == baseline_surface.surface_path

    ms = MissionStatus.load(repo_root=repo, mission_slug=handle)
    assert ms.mission_id == _BACKFILLED_MISSION_ID
    assert ms.read_dir == repo / "kitty-specs" / _BACKFILLED_SLUG


# ---------------------------------------------------------------------------
# MissionStatus.load parity — real mission_id, real read dir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_mission_status_load_identical_across_handle_forms(
    repo: Path, handle: str
) -> None:
    baseline = MissionStatus.load(repo_root=repo, mission_slug=_FULL_SLUG)
    ms = MissionStatus.load(repo_root=repo, mission_slug=handle)
    assert ms.mission_id == _MISSION_ID, (
        f"handle {handle!r} must find the real meta.json (mission_id), "
        f"got {ms.mission_id!r}"
    )
    assert ms.mid8 == _MID8
    assert ms.read_dir == baseline.read_dir


# ---------------------------------------------------------------------------
# Exact repro shape from the validated finding (PR #1850, mid8 handle)
# ---------------------------------------------------------------------------


def test_finding_repro_mid8_handle_values(repo: Path) -> None:
    """Pin the six wrong-but-plausible values from the validated finding."""
    surface = resolve_status_surface(repo, _MID8)
    assert surface != repo / "kitty-specs" / _MID8 / "status.events.jsonl"
    assert surface == repo / "kitty-specs" / _FULL_SLUG / "status.events.jsonl"

    ctx = resolve_action_context(repo, action="status", feature=_MID8)
    assert ctx.feature_dir == str(repo / "kitty-specs" / _FULL_SLUG)
    assert ctx.mission_slug == _FULL_SLUG  # not the raw '01KTPKST'
    assert ctx.identity is not None
    assert ctx.identity.mission_id == _MISSION_ID  # never 'legacy-01KTPKST'
    assert ctx.identity.mid8 == _MID8  # never 'legacy-0'
    assert ctx.status_surface is not None
    assert ctx.status_surface.status_read_dir == repo / "kitty-specs" / _FULL_SLUG

    ms = MissionStatus.load(repo_root=repo, mission_slug=_MID8)
    assert ms.mission_id == _MISSION_ID  # not None
    assert ms.read_dir == repo / "kitty-specs" / _FULL_SLUG


# ---------------------------------------------------------------------------
# Boundary canonicalizers — the _find_mission_slug short-circuits must hand
# the canonical directory name downstream, never the raw operator handle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_tasks_find_mission_slug_returns_canonical_name(
    repo: Path, handle: str
) -> None:
    from specify_cli.cli.commands.agent.tasks import _find_mission_slug

    assert _find_mission_slug(explicit_mission=handle, repo_root=repo) == _FULL_SLUG


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_status_find_mission_slug_returns_canonical_name(
    repo: Path, handle: str
) -> None:
    from specify_cli.cli.commands.agent.status import _find_mission_slug

    assert _find_mission_slug(explicit_mission=handle, repo_root=repo) == _FULL_SLUG


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_workflow_find_mission_slug_returns_canonical_name(
    repo: Path, handle: str
) -> None:
    from specify_cli.cli.commands.agent.workflow import _find_mission_slug

    assert _find_mission_slug(explicit_mission=handle, repo_root=repo) == _FULL_SLUG


# ---------------------------------------------------------------------------
# Decision-open parity — index.json, DM artifact, and DecisionPointOpened
# event must carry the canonical mission_slug for every handle form
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_decision_open_persists_canonical_slug_across_handle_forms(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``agent decision open --mission <handle>`` must persist the canonical
    mission_slug — never the raw operator handle — into decisions/index.json,
    the DM artifact, and the DecisionPointOpened event."""
    from typer.testing import CliRunner

    from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED
    from specify_cli.cli.commands.decision import decision_app

    monkeypatch.chdir(repo)
    result = CliRunner().invoke(
        decision_app,
        [
            "open",
            "--mission",
            handle,
            "--flow",
            "specify",
            "--input-key",
            "team_size",
            "--question",
            "How large is the team?",
            "--step-id",
            "step-1",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    response = json.loads(
        [line for line in result.output.splitlines() if line.strip()][-1]
    )
    assert (
        response["recovery"]["idempotency_key"]["mission_slug"] == _FULL_SLUG
    ), f"raw handle {handle!r} leaked into the open-response idempotency key"

    index_path = repo / "kitty-specs" / _FULL_SLUG / "decisions" / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert [entry["mission_slug"] for entry in index["entries"]] == [_FULL_SLUG], (
        f"raw handle {handle!r} leaked into decisions/index.json mission_slug"
    )

    artifact_text = Path(response["artifact_path"]).read_text(encoding="utf-8")
    assert f"- **Mission:** `{_FULL_SLUG}`" in artifact_text, (
        f"raw handle {handle!r} leaked into the DM artifact Mission line"
    )

    events_path = repo / "kitty-specs" / _FULL_SLUG / "status.events.jsonl"
    opened_events = [
        event
        for event in (
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if event.get("event_type") == DECISION_POINT_OPENED
    ]
    assert len(opened_events) == 1
    assert opened_events[0]["payload"]["mission_slug"] == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into the DecisionPointOpened event"
    )


# ---------------------------------------------------------------------------
# Merge resolver parity — _resolve_mission_slug canonicalizes the --mission
# boundary; dry-run mission_slug identical across handle forms
# ---------------------------------------------------------------------------


def _write_lanes_json(repo: Path) -> None:
    lanes = {
        "version": 1,
        "mission_slug": _FULL_SLUG,
        "mission_id": _MISSION_ID,
        "mission_branch": f"kitty/mission-{_FULL_SLUG}",
        "target_branch": _TARGET_BRANCH,
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": ["WP01"],
                "write_scope": [],
                "predicted_surfaces": [],
                "depends_on_lanes": [],
                "parallel_group": 0,
            }
        ],
        "computed_at": "2026-06-11T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
        "planning_artifact_wps": [],
    }
    (repo / "kitty-specs" / _FULL_SLUG / "lanes.json").write_text(
        json.dumps(lanes) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_merge_resolve_mission_slug_returns_canonical_slug(
    repo: Path, handle: str
) -> None:
    from specify_cli.cli.commands.merge import _resolve_mission_slug

    assert _resolve_mission_slug(repo, handle) == _FULL_SLUG, (
        f"merge --mission {handle!r} must canonicalize at the boundary so "
        "downstream compositions (meta_rel f-string, primary_feature_dir) "
        "never consume the raw operator handle"
    )


def test_merge_resolve_mission_slug_preserves_unresolvable_handle(repo: Path) -> None:
    """Handles that resolve to nothing keep their raw form so the historical
    no-lanes / not-found error behaviour downstream is unchanged."""
    from specify_cli.cli.commands.merge import _resolve_mission_slug

    assert _resolve_mission_slug(repo, "no-such-mission") == "no-such-mission"


def test_merge_resolve_mission_slug_fail_closed_window_does_not_raise(
    repo: Path,
) -> None:
    """In the coordination-empty window (coord worktree root materialized, mission
    dir absent) the resolver must NOT leak StatusReadPathNotFound:
    ``merge --abort --mission <handle>`` relies on slug resolution staying
    non-raising to clean up exactly that broken state.

    WP06 (T015 boundary absorption) note: mission B declares a ``coordination_branch``
    but stores NO ``topology`` field. The read boundary now ABSORBS that absent field
    to a concrete COORD topology, so the coord-empty window resolves the existing
    PRIMARY dir (WP04 Option B) rather than raising — the resolver still does NOT
    raise (the load-bearing contract) AND now canonicalizes the bare-mid8 handle to
    the real ``<slug>-<mid8>`` dir name (exactly what ``_resolve_mission_slug`` wants
    downstream: never the raw operator handle). The old ``== _COORD_MID8`` pin was a
    pre-Option-B artifact (the raise→raw-handle fallback) — re-pointed, not retried."""
    from specify_cli.cli.commands.merge import _resolve_mission_slug

    (repo / ".worktrees" / f"{_COORD_SLUG}-coord").mkdir(parents=True)

    # The load-bearing contract: resolution stays non-raising in the coord-empty
    # window (merge --abort cleanup), and canonicalizes to the real dir name.
    assert _resolve_mission_slug(repo, _COORD_SLUG) == _COORD_SLUG
    assert _resolve_mission_slug(repo, _COORD_MID8) == _COORD_SLUG


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_merge_dry_run_mission_slug_identical_across_handle_forms(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer
    from typer.testing import CliRunner

    from specify_cli.cli.commands import merge as merge_mod

    _write_lanes_json(repo)
    monkeypatch.chdir(repo)
    # Isolate the dry-run preview from live git preflight/target validation —
    # the assertion under test is the mission_slug the preview composes.
    monkeypatch.setattr(merge_mod, "find_repo_root", lambda: repo)
    monkeypatch.setattr(merge_mod, "_enforce_git_preflight", lambda *a, **kw: None)
    monkeypatch.setattr(
        merge_mod, "_resolve_target_branch", lambda *a, **kw: (_TARGET_BRANCH, "flag")
    )
    monkeypatch.setattr(merge_mod, "_validate_target_branch", lambda *a, **kw: None)

    app = typer.Typer()
    app.command()(merge_mod.merge)
    result = CliRunner().invoke(app, ["--mission", handle, "--dry-run", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(
        [line for line in result.output.splitlines() if line.strip()][-1]
    )
    assert payload["mission_slug"] == _FULL_SLUG, (
        f"merge --mission {handle!r} --dry-run must report the canonical "
        f"mission_slug, got {payload['mission_slug']!r}"
    )


# ---------------------------------------------------------------------------
# Next resolver parity — next_cmd._resolve_mission_slug canonicalizes the
# --mission boundary so decide_next / get_or_start_run key
# .kittify/runtime/feature-runs.json (and the persisted mission_slug, run dir,
# and run-scoped emitters) by ONE canonical slug — never a split-brain
# duplicate run keyed by the raw operator handle
# ---------------------------------------------------------------------------


def _feature_runs_index(repo: Path) -> dict[str, dict[str, object]]:
    path = repo / ".kittify" / "runtime" / "feature-runs.json"
    index: dict[str, dict[str, object]] = json.loads(
        path.read_text(encoding="utf-8")
    )
    return index


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_next_resolve_mission_slug_returns_canonical_slug(
    repo: Path, handle: str
) -> None:
    from specify_cli.cli.commands.next_cmd import _resolve_mission_slug

    assert _resolve_mission_slug(handle, repo) == _FULL_SLUG, (
        f"next --mission {handle!r} must canonicalize at the boundary so "
        "decide_next / get_or_start_run never key runtime state by the raw "
        "operator handle"
    )


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_next_run_identity_identical_across_handle_forms(
    repo: Path, handle: str
) -> None:
    """``spec-kitty next --mission <handle>`` must reuse the SAME runtime run
    as the full-slug invocation: one feature-runs.json key, one run_id, one
    run dir, canonical persisted mission_slug — never a split-brain duplicate
    run keyed by the raw handle."""
    from runtime.next import runtime_bridge

    from specify_cli.cli.commands.next_cmd import _resolve_mission_slug

    baseline = runtime_bridge.get_or_start_run(_FULL_SLUG, repo, "software-dev")

    slug = _resolve_mission_slug(handle, repo)
    run_ref = runtime_bridge.get_or_start_run(slug, repo, "software-dev")

    assert run_ref.run_id == baseline.run_id, (
        f"next --mission {handle!r} started a NEW run ({run_ref.run_id}) "
        f"instead of reusing the full-slug run ({baseline.run_id})"
    )
    assert run_ref.run_dir == baseline.run_dir

    index = _feature_runs_index(repo)
    # WP05 / FR-016 (C-003): the index is keyed by mission_id; the slug is
    # display-only and a raw handle must leak into neither.
    assert set(index) == {_MISSION_ID}, (
        f"handle {handle!r} leaked a raw-handle key into feature-runs.json: "
        f"{sorted(index)}"
    )
    assert index[_MISSION_ID]["mission_slug"] == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into the persisted mission_slug"
    )
    assert index[_MISSION_ID]["mission_id"] == _MISSION_ID


def test_next_resolve_mission_slug_preserves_unresolvable_handle(
    repo: Path,
) -> None:
    """Handles that resolve to nothing keep their raw form, preserving the
    historical not-found error semantics downstream (decide_next / query
    mode)."""
    from specify_cli.cli.commands.next_cmd import _resolve_mission_slug

    assert _resolve_mission_slug("no-such-mission", repo) == "no-such-mission"


def test_next_resolve_mission_slug_propagates_ambiguity(repo: Path) -> None:
    """C-CTX-4: an ambiguous numeric-prefix handle raises the structured
    MissionSelectorAmbiguous — never a silent pick of one candidate run."""
    from specify_cli.cli.commands.next_cmd import _resolve_mission_slug
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    _seed_mission(
        repo, slug="083-rival-mission", mission_id="01KTZYXW0000000000000000GH"
    )

    with pytest.raises(MissionSelectorAmbiguous):
        _resolve_mission_slug("083", repo)


# ---------------------------------------------------------------------------
# coord-empty Option B parity — MissionStatus.load resolves PRIMARY + loud warning
# for EVERY handle form (WP04 / 01KVN754 / #1716 / FR-003)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_COORD_SLUG, _COORD_MID8, _COORD_MISSION_ID])
def test_coord_empty_window_resolves_primary_with_warning_for_all_handles(
    repo: Path, handle: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Inverted by mission 01KVN754 WP04 (out-of-map linearized edit; WP05 owns
    this file, but the coord-empty cell breaks at THIS boundary).

    The coord-empty window — coord worktree ROOT materialized, mission dir absent,
    primary declares ``coordination_branch`` — previously hard-failed with
    ``CoordAuthorityUnavailable`` for every handle form. Under Option B the
    canonical surface returns the PRIMARY checkout + a loud warning and the
    aggregate inherits PRIMARY, so every handle form resolves the same primary
    mission dir.

    WP08 (#2533) makes the warning conditional on the mission's derived
    topology (a coord mission WITH lanes hitting an unexpected empty coord
    still warns; a solo, no-lanes ``MissionTopology.COORD`` mission does not —
    see ``tests/coordination/test_surface_resolver_solo_coord_primary.py``).
    This call path (``MissionStatus.load`` -> ``resolve_surface_dir_or_typed_
    error`` -> ``resolve_status_surface`` with no threaded topology) hits
    ``resolve_status_surface_with_anchor``'s un-backfilled-legacy tier, which
    derives via ``classify_topology(coord_branch, has_lanes=False)`` — a disk
    ``lanes.json`` is NOT consulted on this leg. So Mission B's ``meta.json``
    (written by the shared ``repo`` fixture with no stored ``topology`` field)
    is patched here with an explicit ``topology: "lanes_with_coord"`` to keep
    deriving the still-warns shape this test pins, without touching the
    shared fixture used by the other tests in this module.
    """
    import logging

    # coord worktree ROOT materialized, but the mission dir inside it is absent.
    (repo / ".worktrees" / f"{_COORD_SLUG}-coord").mkdir(parents=True)
    coord_meta_path = repo / "kitty-specs" / _COORD_SLUG / "meta.json"
    coord_meta = json.loads(coord_meta_path.read_text(encoding="utf-8"))
    coord_meta["topology"] = "lanes_with_coord"
    coord_meta_path.write_text(json.dumps(coord_meta), encoding="utf-8")

    expected_primary = (repo / "kitty-specs" / _COORD_SLUG).resolve()
    with caplog.at_level(
        logging.WARNING, logger="specify_cli.coordination.surface_resolver"
    ):
        ms = MissionStatus.load(repo_root=repo, mission_slug=handle)

    assert ms.read_dir.resolve() == expected_primary
    assert any(
        r.name == "specify_cli.coordination.surface_resolver"
        and r.levelno == logging.WARNING
        for r in caplog.records
    ), "coord-empty Option B must emit a logging.WARNING (no silent fallback)"


# ---------------------------------------------------------------------------
# coord-deleted convergence parity — MissionStatus.load hard-fails
# CoordinationBranchDeleted for EVERY handle form (WP05 / 01KVN754 / #1848 / FR-005)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_COORD_SLUG, _COORD_MID8, _COORD_MISSION_ID])
def test_coord_deleted_hard_fails_for_all_handles(repo: Path, handle: str) -> None:
    """coord-deleted (declared branch DELETED from git, no coord worktree) →
    ``CoordinationBranchDeleted`` for every handle form (WP05 / T023 / T026).

    The fixture declares ``coordination_branch`` AND creates it in git (the #1889
    row R2 create-window contract). Delete the branch to model R3 (#1848): the
    declared branch is gone and no coord worktree exists → data loss. The aggregate
    must propagate ``CoordinationBranchDeleted`` (``COORDINATION_BRANCH_DELETED``)
    VERBATIM for the slug, mid8, AND full-ULID handle forms — never a per-handle
    divergence and never the masked ``CoordAuthorityUnavailable`` re-spelling.
    """
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    _git(repo, "branch", "-D", _COORD_BRANCH)  # R3: declared branch deleted from git

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        MissionStatus.load(repo_root=repo, mission_slug=handle)
    assert excinfo.value.error_code == "COORDINATION_BRANCH_DELETED"


# ---------------------------------------------------------------------------
# Plan interview seam parity — `spec-kitty plan --mission <handle>` must hand
# the CANONICAL mission_slug to run_plan_interview, so the Decision Moments it
# opens persist a canonical mission_slug into decisions/index.json
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_plan_interview_persists_canonical_slug_across_handle_forms(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The explicit ``--mission`` path of ``spec-kitty plan`` must key the
    interview seam by the canonical directory name. Pre-fix it handed the RAW
    selector value (``resolved.canonical_value``) to ``run_plan_interview``,
    which persisted it via ``_dm_service.open_decision(mission_slug=...)``
    into decisions/index.json — while the no-flag autodetect path correctly
    canonicalized via ``_find_feature_directory(...).name``."""
    import typer
    from typer.testing import CliRunner

    from specify_cli.cli.commands import lifecycle
    from specify_cli.widen.models import PrereqState

    monkeypatch.chdir(repo)
    # The seam under test is the interview block's mission-slug derivation;
    # the plan scaffold itself is covered by the lifecycle/widen suites.
    # String form: lifecycle binds `agent.mission as agent_feature` (a
    # non-reexported module alias), so patch the canonical module attribute —
    # the SAME object lifecycle calls through — keeping mypy's
    # no-implicit-reexport check clean.
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.mission.setup_plan", lambda **_kw: None
    )
    # Keep the widen affordance offline (its setup is non-fatal by design).
    monkeypatch.setattr(
        "specify_cli.widen.check_prereqs",
        lambda *_a, **_kw: PrereqState(
            teamspace_ok=False, slack_ok=False, saas_reachable=False
        ),
    )

    app = typer.Typer()
    app.command()(lifecycle.plan)
    n_questions = len(lifecycle.PLAN_WIDEN_QUESTIONS)
    result = CliRunner().invoke(
        app,
        ["--mission", handle],
        input="\n" * n_questions,
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    index_path = repo / "kitty-specs" / _FULL_SLUG / "decisions" / "index.json"
    assert index_path.exists(), (
        f"plan --mission {handle!r} must open the interview Decision Moments "
        "under the canonical mission directory"
    )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["entries"], "expected one Decision Moment per interview question"
    slugs = {entry["mission_slug"] for entry in index["entries"]}
    assert slugs == {_FULL_SLUG}, (
        f"raw handle {handle!r} leaked into decisions/index.json mission_slug: "
        f"{sorted(slugs)}"
    )


# ---------------------------------------------------------------------------
# Custom-mission run parity — `spec-kitty mission run <key> --mission <handle>`
# must canonicalize at the run_cmd boundary so get_or_start_run keys
# .kittify/runtime/feature-runs.json (and the run identity) by ONE canonical
# slug — never a split-brain duplicate run keyed by the raw operator handle
# ---------------------------------------------------------------------------

_CUSTOM_MISSION_KEY = "matrix-custom-run"

_CUSTOM_MISSION_BODY = """\
mission:
  key: matrix-custom-run
  name: Matrix Custom Run
  version: "1.0.0"
steps:
  - id: plan
    title: Plan
    agent_profile: planner
  - id: retrospective
    title: Retrospective
    agent_profile: retro
"""


def _seed_custom_mission(repo: Path) -> None:
    mission_dir = repo / ".kittify" / "missions" / _CUSTOM_MISSION_KEY
    mission_dir.mkdir(parents=True)
    (mission_dir / "mission.yaml").write_text(_CUSTOM_MISSION_BODY, encoding="utf-8")


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_mission_run_identity_identical_across_handle_forms(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from specify_cli.cli.commands import mission_type
    from specify_cli.mission_loader.registry import get_runtime_contract_registry

    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)
    monkeypatch.chdir(repo)
    _seed_custom_mission(repo)

    registry = get_runtime_contract_registry()
    registry.clear()
    try:
        runner = CliRunner()
        baseline = runner.invoke(
            mission_type.app,
            ["run", _CUSTOM_MISSION_KEY, "--mission", _FULL_SLUG, "--json"],
            catch_exceptions=False,
        )
        assert baseline.exit_code == 0, baseline.output
        baseline_payload = json.loads(
            baseline.output[baseline.output.index("{") :]
        )

        # The v1 registry shadow is a process singleton; clear between
        # sequential runs of the same mission_key (the documented contract).
        registry.clear()

        result = runner.invoke(
            mission_type.app,
            ["run", _CUSTOM_MISSION_KEY, "--mission", handle, "--json"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output[result.output.index("{") :])
    finally:
        registry.clear()

    assert payload["mission_slug"] == _FULL_SLUG, (
        f"mission run --mission {handle!r} must report the canonical "
        f"mission_slug, got {payload['mission_slug']!r}"
    )
    assert payload["run_dir"] == baseline_payload["run_dir"], (
        f"mission run --mission {handle!r} started a NEW run instead of "
        "attaching to the full-slug run"
    )

    index = _feature_runs_index(repo)
    # WP05 / FR-016 (C-003): keyed by mission_id; slug is display-only.
    assert set(index) == {_MISSION_ID}, (
        f"handle {handle!r} leaked a raw-handle key into feature-runs.json: "
        f"{sorted(index)}"
    )
    assert index[_MISSION_ID]["mission_slug"] == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into the persisted mission_slug"
    )


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_mission_run_resolver_returns_canonical_slug(repo: Path, handle: str) -> None:
    from specify_cli.cli.commands.mission_type import _resolve_mission_slug

    assert _resolve_mission_slug(repo, handle) == _FULL_SLUG, (
        f"mission run --mission {handle!r} must canonicalize at the boundary "
        "so get_or_start_run never keys runtime state by the raw handle"
    )


def test_mission_run_resolver_preserves_unresolvable_handle(repo: Path) -> None:
    """Handles that resolve to nothing keep their raw form, preserving the
    historical not-found / lazy-meta-creation semantics downstream."""
    from specify_cli.cli.commands.mission_type import _resolve_mission_slug

    assert _resolve_mission_slug(repo, "no-such-mission") == "no-such-mission"


def test_mission_run_resolver_propagates_ambiguity(repo: Path) -> None:
    """C-CTX-4: an ambiguous numeric-prefix handle raises the structured
    MissionSelectorAmbiguous — never a silent pick of one candidate run."""
    from specify_cli.cli.commands.mission_type import _resolve_mission_slug
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    _seed_mission(
        repo, slug="083-rival-mission", mission_id="01KTZYXW0000000000000000GH"
    )

    with pytest.raises(MissionSelectorAmbiguous):
        _resolve_mission_slug(repo, "083")


def test_mission_run_resolver_fail_closed_window_does_not_raise(repo: Path) -> None:
    """In the coordination-empty window (coord worktree root materialized, mission
    dir absent) the resolver must NOT leak StatusReadPathNotFound — non-raising at
    the boundary so the runtime surfaces its own diagnostic downstream.

    WP06 (T015 boundary absorption) note: mission B declares a ``coordination_branch``
    with NO stored ``topology`` field; the read boundary now absorbs that absent field
    to a concrete COORD topology, so the coord-empty window resolves the existing
    PRIMARY dir (WP04 Option B) instead of raising. The resolver still does NOT raise
    (the load-bearing contract) AND now canonicalizes the bare-mid8 handle to the real
    ``<slug>-<mid8>`` dir name. The old ``== _COORD_MID8`` pin was a pre-Option-B
    raise→raw-handle artifact — re-pointed, not retried."""
    from specify_cli.cli.commands.mission_type import _resolve_mission_slug

    (repo / ".worktrees" / f"{_COORD_SLUG}-coord").mkdir(parents=True)

    assert _resolve_mission_slug(repo, _COORD_SLUG) == _COORD_SLUG
    assert _resolve_mission_slug(repo, _COORD_MID8) == _COORD_SLUG


# ---------------------------------------------------------------------------
# MissionContext parity — resolve_context must persist the canonical
# mission_slug and compose authoritative_ref from it (lane_branch_name),
# identical across handle forms
# ---------------------------------------------------------------------------


def _seed_wp01(repo: Path) -> None:
    tasks_dir = repo / "kitty-specs" / _FULL_SLUG / "tasks"
    (tasks_dir / "WP01-test-wp.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test WP\n"
        "lane: planned\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        '- "src/**"\n'
        "---\n"
        "\n"
        "# Work Package: WP01\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_resolve_context_persists_canonical_slug_and_ref_across_handle_forms(
    repo: Path, handle: str
) -> None:
    """``resolve_context`` canonicalizes the DIRECTORY but pre-fix composed the
    persisted MissionContext (``mission_slug`` and the lane-branch
    ``authoritative_ref``) from the RAW handle — a wrong-but-plausible
    ``kitty/mission-<mid8>-…`` ref vs the full-slug invocation."""
    from specify_cli.context import resolve_context

    _write_lanes_json(repo)
    _seed_wp01(repo)

    baseline = resolve_context(
        wp_code="WP01", mission_slug=_FULL_SLUG, agent="claude", repo_root=repo
    )
    ctx = resolve_context(
        wp_code="WP01", mission_slug=handle, agent="claude", repo_root=repo
    )

    assert ctx.mission_slug == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into MissionContext.mission_slug "
        f"({ctx.mission_slug!r})"
    )
    assert ctx.authoritative_ref == baseline.authoritative_ref, (
        f"handle {handle!r} composed authoritative_ref "
        f"{ctx.authoritative_ref!r} != full-slug ref "
        f"{baseline.authoritative_ref!r}"
    )
    assert ctx.mission_id == _MISSION_ID
    assert ctx.target_branch == baseline.target_branch

    persisted = json.loads(
        (repo / ".kittify" / "runtime" / "contexts" / f"{ctx.token}.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted["mission_slug"] == _FULL_SLUG, (
        f"raw handle {handle!r} leaked into the persisted context token payload"
    )
    assert persisted["authoritative_ref"] == baseline.authoritative_ref


def test_resolve_context_unresolvable_handle_raises_feature_not_found(
    repo: Path,
) -> None:
    """Unresolvable handles keep the structured FeatureNotFoundError contract."""
    from specify_cli.context import resolve_context
    from specify_cli.context.errors import FeatureNotFoundError

    _write_lanes_json(repo)
    _seed_wp01(repo)

    with pytest.raises(FeatureNotFoundError):
        resolve_context(
            wp_code="WP01",
            mission_slug="no-such-mission",
            agent="claude",
            repo_root=repo,
        )


# ---------------------------------------------------------------------------
# Mission close --discard parity — close_cmd resolves the DIRECTORY but must
# also re-key the slug before _discard_mission composes lane branch names
# (lane_branch_name(raw, lane_id)) and the .worktrees/ f"{raw}-" prefix match
# ---------------------------------------------------------------------------


def _branch_exists(repo: Path, branch_name: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/heads/{branch_name}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _seed_discardable_lane(repo: Path) -> tuple[str, Path]:
    """Create a real lane branch + detached lane worktree for Mission A.

    The lane worktree is detached so ``git branch -D`` (what
    ``_force_delete_branch_if_exists`` runs) is not blocked by a checkout —
    the seam under test is the NAME composition, not git's checkout guard.
    """
    from specify_cli.lanes.branch_naming import lane_branch_name

    _write_lanes_json(repo)
    lane_branch = lane_branch_name(_FULL_SLUG, "lane-a")
    _git(repo, "branch", lane_branch)
    _git(repo, "branch", f"kitty/mission-{_FULL_SLUG}")
    lane_worktree = repo / ".worktrees" / f"{_FULL_SLUG}-lane-a"
    _git(repo, "worktree", "add", "--detach", str(lane_worktree))
    return lane_branch, lane_worktree


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_mission_close_discard_removes_lane_branch_and_worktree_across_handles(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mission close --discard --mission <handle>`` must delete the SAME lane
    branch and lane worktree for every handle form. Pre-fix, close resolved
    the DIRECTORY canonically but handed the RAW handle to
    ``_discard_mission`` / ``_teardown_coordination_worktree`` —
    ``lane_branch_name(raw, lane_id)`` named a nonexistent branch and the
    ``.worktrees/`` ``f"{raw}-"`` prefix matched nothing, silently leaving
    the lane worktree AND branch behind while reporting success."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands import mission_type

    lane_branch, lane_worktree = _seed_discardable_lane(repo)
    assert _branch_exists(repo, lane_branch)
    assert lane_worktree.exists()

    monkeypatch.chdir(repo)
    result = CliRunner().invoke(
        mission_type.app,
        ["close", "--mission", handle, "--discard", "--force"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    assert not _branch_exists(repo, lane_branch), (
        f"close --discard --mission {handle!r} left lane branch "
        f"{lane_branch!r} behind while reporting success"
    )
    assert not _branch_exists(repo, f"kitty/mission-{_FULL_SLUG}"), (
        f"close --discard --mission {handle!r} left the mission branch behind"
    )
    assert not lane_worktree.exists(), (
        f"close --discard --mission {handle!r} left lane worktree "
        f"{lane_worktree.name!r} behind while reporting success"
    )


def test_mission_close_unresolvable_handle_keeps_structured_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unresolvable handles keep the established structured error contract
    (ActionContextError from resolve_action_context) — re-keying happens only
    after a successful dir resolution and must not soften or reroute it."""
    from typer.testing import CliRunner

    from mission_runtime import ActionContextError
    from specify_cli.cli.commands import mission_type

    monkeypatch.chdir(repo)
    with pytest.raises(ActionContextError, match="no-such-mission"):
        CliRunner().invoke(
            mission_type.app,
            ["close", "--mission", "no-such-mission", "--discard", "--force"],
            catch_exceptions=False,
        )


def test_mission_close_ambiguous_handle_propagates_structured_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-CTX-4: an ambiguous numeric-prefix handle raises a structured ambiguity
    error carrying MISSION_AMBIGUOUS_SELECTOR — never a silent pick of one
    candidate to discard (deleting branches/worktrees of the WRONG mission).

    Mission 01KVGCE8 / FR-005: the ``mission close`` path resolves through the
    ``mission_runtime`` boundary (``resolve_action_context``), which now
    translates the raw ``MissionSelectorAmbiguous`` into an
    ``ActionContextError`` carrying the same ``MISSION_AMBIGUOUS_SELECTOR``
    code. Either form satisfies the no-silent-pick guarantee; assert on the
    stable code rather than the exact exception class.
    """
    from typer.testing import CliRunner

    from mission_runtime import ActionContextError

    from specify_cli.cli.commands import mission_type
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    _seed_mission(
        repo, slug="083-rival-mission", mission_id="01KTZYXW0000000000000000GH"
    )
    monkeypatch.chdir(repo)
    with pytest.raises((MissionSelectorAmbiguous, ActionContextError)) as excinfo:
        CliRunner().invoke(
            mission_type.app,
            ["close", "--mission", "083", "--discard", "--force"],
            catch_exceptions=False,
        )
    code = getattr(excinfo.value, "code", None) or getattr(
        excinfo.value, "error_code", None
    )
    assert code == "MISSION_AMBIGUOUS_SELECTOR", (
        f"ambiguous handle must surface MISSION_AMBIGUOUS_SELECTOR, got {code!r} "
        f"from {type(excinfo.value).__name__}"
    )


# ---------------------------------------------------------------------------
# Research canonical-directory parity — ``research`` re-keys the operator's
# handle onto the resolved directory name (`mission_slug = feature_dir.name`),
# so every handle form lands on one directory. (The consumer that motivated the
# re-key — the dossier-sync trigger keying its SaaS namespace by this slug —
# retired with the sync transport; artifact placement is the surviving
# observable of the same property.)
# ---------------------------------------------------------------------------


def _invoke_research(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> Result:
    import typer
    from typer.testing import CliRunner

    from specify_cli.cli.commands import research as research_mod

    monkeypatch.chdir(repo)
    app = typer.Typer()
    app.command()(research_mod.research)
    return CliRunner().invoke(app, ["--mission", handle], catch_exceptions=False)


@pytest.mark.parametrize("handle", [_FULL_SLUG, _MID8, "083"])
def test_research_lands_on_the_canonical_directory_across_handle_forms(
    repo: Path, handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``research --mission <handle>`` canonicalizes the DIRECTORY via
    resolve_feature_dir_for_slug and then re-keys mission_slug to it — every
    handle form must converge on one directory, never scaffold a second one
    keyed by the raw operator handle."""
    result = _invoke_research(repo, handle, monkeypatch)
    assert result.exit_code == 0, result.output

    canonical = repo / "kitty-specs" / _FULL_SLUG
    assert (canonical / "research.md").is_file(), (
        f"research --mission {handle!r} did not land on the canonical directory {canonical}"
    )
    if handle != _FULL_SLUG:
        assert not (repo / "kitty-specs" / handle).exists(), (
            f"research --mission {handle!r} scaffolded a directory keyed by the raw handle — "
            "the handle was not re-keyed onto feature_dir.name"
        )


def test_research_unresolvable_slug_refuses_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unresolvable slugs are refused, not scaffolded.

    The historical behaviour (pre-#4631/#4736) silently scaffolded a phantom
    ``kitty-specs/<raw-handle>/`` directory and exited 0 — the most-serious
    bug #4631 identified in mission handle resolution. #4736 removed it:
    ``research`` now refuses an unresolvable ``--mission`` handle BEFORE
    writing anything, emitting the canonical ``Mission not found: <handle>``
    (see ``tests/research/test_research_missing_mission.py``, added by the
    same mission) and exiting non-zero, leaving ``kitty-specs/`` untouched.
    """
    result = _invoke_research(repo, "999-brand-new-mission", monkeypatch)
    assert result.exit_code != 0, result.output
    assert "Mission not found: 999-brand-new-mission" in result.output

    feature_dir = repo / "kitty-specs" / "999-brand-new-mission"
    assert not feature_dir.exists()
