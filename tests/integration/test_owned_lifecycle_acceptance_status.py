"""Acceptance tests: owned-checkout ``agent tasks status`` / ``agent mission setup-plan`` (WP09).

owned-checkout-lifecycle-authority WP09 (FR-004, FR-005, FR-007, FR-020,
NFR-002, US1). Red-first (C-007): reproduces O1/O2 and US1-AS1/US1-AS2
through the pre-existing entry points (``agent tasks status`` /
``agent mission setup-plan``) before any WP09 fix.

Observed base (pre-WP09) behaviour, recorded from a real run against this
lane's pre-T045/T046 commit in a scratch detached worktree:

* O1 (flagless ``status --mission H --json`` from cwd = P, no stale copy in
  R): ``MISSION_NOT_FOUND`` -- the handle resolves against R, which has no
  mission at all yet (this base row activates the stale copy afterward, so
  the "no stale copy" case is the pre-``stale_root_copy`` fixture state,
  where R genuinely has no mission).
* O1 with ``stale_root_copy`` active (R holds WP01-WP05 under the SAME
  mission id): exit 0, but the board lists R's WP01-WP05 -- R's committed
  copy wins over P (the fail-open FR-007 defect).
* O1-flag / US1-AS1 (``--owned-checkout P --mission H --json`` from cwd = R):
  exit 2, "No such option: --owned-checkout" -- the flag does not exist yet.
* O2 (flagless ``setup-plan --mission H --json`` from cwd = P, plan.md
  removed): ``PLAN_CONTEXT_UNRESOLVED``-shaped failure -- the handle
  resolves against R, which cannot find the mission at all.
* O2-flag / US1-AS2 (``--owned-checkout P --mission H --json`` from cwd = R):
  exit 2, "No such option: --owned-checkout".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _clear_repo_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


def _payload(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(result.output)
    assert isinstance(data, dict), f"expected a JSON object, got {type(data).__name__}: {result.output!r}"
    return data


def _fix_owned_files_contradiction(owned_checkouts: OwnedCheckouts, wp_ids: tuple[str, ...] = ("WP01", "WP02")) -> None:
    """Give each ``code_change`` WP a non-empty ``owned_files`` list.

    The fixture's default WP files (``_write_mission``) declare
    ``owned_files: []`` with ``execution_mode: code_change`` --
    ``finalize-tasks`` refuses that combination as an authoring
    contradiction. Per-test fixture-state addition (T044 latitude), not a
    ``conftest.py`` edit.
    """
    from tests.integration.conftest import _git

    for wp_id in wp_ids:
        wp_file = owned_checkouts.mission_dir / "tasks" / f"{wp_id}-owned.md"
        text = wp_file.read_text(encoding="utf-8")
        surface = f"{wp_id.lower()}.py"
        text = text.replace("authoritative_surface: app.py", f"authoritative_surface: {surface}")
        text = text.replace("owned_files: []", f"owned_files: [{surface}]\ncreate_intent:\n  - {surface}")
        wp_file.write_text(text, encoding="utf-8")
    _git(owned_checkouts.owned_root, "add", "kitty-specs")
    _git(owned_checkouts.owned_root, "commit", "-qm", "give code_change WPs an owned file")


def _write_tasks_md_sections(owned_checkouts: OwnedCheckouts, wp_ids: tuple[str, ...] = ("WP01", "WP02")) -> None:
    """Give ``tasks.md`` a section per WP so ``finalize-tasks`` can match coverage.

    The fixture's default ``tasks.md`` (``_write_mission``) is a bare stub
    with no WP sections; ``finalize-tasks`` hard-fails closed
    (``missing_wp_sections``) rather than finalizing an unverifiable lane
    map. Per-test fixture-state addition (T044 latitude), not a
    ``conftest.py`` edit.
    """
    from tests.integration.conftest import _git

    tasks_md = owned_checkouts.mission_dir / "tasks.md"
    body = "# Tasks\n\n" + "\n\n".join(f"## {wp_id}\n\nOwned fixture task." for wp_id in wp_ids) + "\n"
    tasks_md.write_text(body, encoding="utf-8")
    _git(owned_checkouts.owned_root, "add", str(tasks_md.relative_to(owned_checkouts.owned_root)))
    _git(owned_checkouts.owned_root, "commit", "-qm", "add tasks.md WP sections")


def _finalize(owned_checkouts: OwnedCheckouts, handle: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Finalize WP01-WP02 in P via the existing, working FR-022 entry point.

    ``--owned-checkout``'s claim validation resolves the "real" primary via
    ``get_main_repo_root(locate_project_root())``, which is cwd-derived, so
    cwd must already be inside R (or its worktrees) before this call -- the
    caller's OWN test cwd is restored by pytest's ``monkeypatch`` teardown,
    so this leaves cwd at ``repository_root``; callers that need a different
    cwd chdir again afterward.
    """
    monkeypatch.chdir(owned_checkouts.repository_root)
    runner = CliRunner()
    result = runner.invoke(
        mission_app,
        [
            "finalize-tasks",
            "--owned-checkout",
            str(owned_checkouts.owned_root),
            "--mission",
            handle,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return result


def _activate_mission_type(root: Path, *, mission_type: str = "software-dev") -> None:
    """Add ``mission_type_activations`` to ``root``'s OWN checked-out ``.kittify/config.yaml``.

    ``existing_mission_types`` (FR-006 activation gate) reads this key with
    no implicit "all built-ins" backfill: an unprovisioned fixture repo (this
    suite never runs ``spec-kitty init``) activates NOTHING, so
    ``setup-plan``'s mission-type-aware template resolution hard-fails with
    ``UnknownMissionTypeError`` before ever reaching the owned-checkout logic
    this WP changes. This is a per-test fixture-state addition (T044's own
    "prepare additional fixture state inside the tests" latitude), not a
    ``conftest.py`` edit -- ``root``'s branch may differ from another
    checkout sharing the same ``.git`` common dir (P and R sit on distinct
    branches), so each checkout that needs template resolution gets its own
    commit.
    """
    from tests.integration.conftest import _git

    config_path = root / ".kittify" / "config.yaml"
    text = config_path.read_text(encoding="utf-8")
    if "mission_type_activations" not in text:
        config_path.write_text(f"{text}mission_type_activations: [{mission_type}]\n", encoding="utf-8")
        _git(root, "add", ".kittify/config.yaml")
        _git(root, "commit", "-qm", f"activate {mission_type} mission type")


def _status(*args: str) -> Any:
    return CliRunner().invoke(tasks_app, ["status", *args])


def _setup_plan(*args: str) -> Any:
    return CliRunner().invoke(mission_app, ["setup-plan", *args])


# ---------------------------------------------------------------------------
# O1 / FR-004 / US1-AS1: ``agent tasks status``.
# ---------------------------------------------------------------------------


def test_o1_flagless_status_from_p_lists_only_p_wps(
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target: flagless ``status`` from P lists only P's WP01-WP02, R untouched."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    monkeypatch.chdir(owned_checkouts.owned_root)

    before = r_snapshot.take()
    result = _status("--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    ids = sorted(wp["id"] for wp in payload["work_packages"])
    assert ids == ["WP01", "WP02"], payload
    assert payload.get("stale_repository_root_copy") is None
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_o1_flag_status_lists_only_p_wps_with_stale_copy_named(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US1-AS1 (target): ``--owned-checkout P`` from cwd=R lists P's WP01-WP02 and names R's stale copy."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    before = r_snapshot.take()
    result = _status(
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    ids = sorted(wp["id"] for wp in payload["work_packages"])
    assert ids == ["WP01", "WP02"], payload
    stale = payload.get("stale_repository_root_copy")
    assert stale is not None
    assert Path(stale["path"]).resolve() == r_copy_dir.resolve()
    r_snapshot.assert_unchanged(before, r_snapshot.take())


def test_o1_flag_status_no_stale_copy_gives_null(
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-stale-copy sibling: ``stale_repository_root_copy`` is ``null``, not absent."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root)

    result = _status(
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "stale_repository_root_copy" in payload
    assert payload["stale_repository_root_copy"] is None


def test_us1_as1_human_mode_warns_on_stderr(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US1-AS1 human mode: the stale-copy warning renders; the board still lists only P's WPs."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    stale_root_copy()
    monkeypatch.chdir(owned_checkouts.repository_root)

    result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug)
    assert result.exit_code == 0, result.output
    combined = (result.stdout or "") + (result.stderr or "")
    assert "stale copy" in combined.lower(), combined
    assert "WP01" in combined and "WP02" in combined, combined


def _move_task(owned_root: Any, wp_id: str, to: str, mission_slug: str) -> Any:
    return CliRunner().invoke(
        tasks_app,
        ["move-task", wp_id, "--to", to, "--owned-checkout", str(owned_root), "--mission", mission_slug],
    )


def test_t045_step5_owned_in_progress_wp_renders_owned_checkout_workspace_kind(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T045 step 5, row 1 (review cycle 1 issue 2): an owned WP moved to
    ``in_progress`` (via ``move-task --owned-checkout P``, FR-022) renders
    ``status --owned-checkout P --json`` with ``workspace_kind ==
    "owned_checkout"`` and no error."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root)

    move_result = _move_task(owned_checkouts.owned_root, "WP01", "doing", owned_checkouts.mission_slug)
    assert move_result.exit_code == 0, move_result.output

    result = _status(
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    wp01 = next(wp for wp in payload["work_packages"] if wp["id"] == "WP01")
    assert wp01["lane"] == "in_progress", wp01
    assert wp01["workspace_kind"] == "owned_checkout", wp01


def test_t045_step5_stale_copy_lane_mismatch_reports_p_lane(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T045 step 5, row 2 (review cycle 1 issue 2): with ``stale_root_copy``
    where R's own copy has WP01 in a DIFFERENT lane, ``status
    --owned-checkout P`` reports P's lane, never R's."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root)

    move_result = _move_task(owned_checkouts.owned_root, "WP01", "doing", owned_checkouts.mission_slug)
    assert move_result.exit_code == 0, move_result.output

    # R's stale copy is a DIFFERENT lane composition (WP01 stays "planned"
    # there -- stale_root_copy's own status.events.jsonl is never touched by
    # the move-task call above, which only writes P's log).
    stale_root_copy()

    result = _status(
        "--owned-checkout",
        str(owned_checkouts.owned_root),
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
    )
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    wp01 = next(wp for wp in payload["work_packages"] if wp["id"] == "WP01")
    assert wp01["lane"] == "in_progress", wp01


def test_control_a_non_owned_mission_status_shape_unchanged(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control (a): a non-owned, R-only mission's ``status`` payload has NO owned key.

    Beyond key absence, the non-owned payload's top-level shape equals an
    owned run's shape minus the single additive ``stale_repository_root_copy``
    key (WP08's additive-only envelope rule).
    """
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    r_root = owned_checkouts.repository_root
    monkeypatch.chdir(r_root)
    from tests.integration.conftest import _git, _write_mission, _write_single_lane_manifest

    owned_result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert owned_result.exit_code == 0, owned_result.output
    owned_payload = _payload(owned_result)

    other_slug = "r-only-fixture-01M2D9FF"
    other_id = "01M2D9FF000000000000000001"
    mission_dir = r_root / "kitty-specs" / other_slug
    _write_mission(mission_dir, mission_id=other_id, slug=other_slug, topology="single_branch", target_branch="main", wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=other_slug, mission_id=other_id, target_branch="main", wp_ids=("WP01",))
    _git(r_root, "add", ".")
    _git(r_root, "commit", "-qm", "r-only mission")

    result = _status("--mission", other_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "stale_repository_root_copy" not in payload, payload
    assert set(payload) == set(owned_payload) - {"stale_repository_root_copy"}, (sorted(payload), sorted(owned_payload))
    assert payload["mission_slug"] == other_slug
    assert [wp["id"] for wp in payload["work_packages"]] == ["WP01"]


def test_control_d_nfr002_owned_status_resolves_ownership_once(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-002: an owned ``status`` run resolves ownership exactly once."""
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root)

    calls: list[int] = []
    import specify_cli.core.checkout_ownership as ownership_mod

    original = ownership_mod.resolve_ownership_claim

    def _counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(ownership_mod, "resolve_ownership_claim", _counting)

    result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    assert len(calls) == 1, calls


def _seed_r_unrelated_active_mission(owned_checkouts: OwnedCheckouts) -> str:
    """Seed R with its own active mission, UNRELATED to the owned mission in P.

    Used to prove the #4677 R-scoped sole-active-mission default never leaks
    across an owned/foreign-checkout boundary (review cycle 1 issue 4).
    """
    from tests.integration.conftest import _git, _write_mission, _write_single_lane_manifest

    r_root = owned_checkouts.repository_root
    other_slug = "r-only-unrelated-01M4ISS4"
    other_id = "01M4ISS4000000000000000001"
    mission_dir = r_root / "kitty-specs" / other_slug
    _write_mission(mission_dir, mission_id=other_id, slug=other_slug, topology="single_branch", target_branch="main", wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=other_slug, mission_id=other_id, target_branch="main", wp_ids=("WP01",))
    _git(r_root, "add", ".")
    _git(r_root, "commit", "-qm", "r-only unrelated active mission")
    return other_slug


def test_issue4_owned_checkout_flag_without_mission_gives_handle_required_refusal(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review cycle 1 issue 4, case 1: ``--owned-checkout P`` without ``--mission``,
    with R holding its own unrelated active mission, must give the
    "--owned-checkout requires an explicit --mission" refusal -- never
    silently substitute R's sole active mission and resolve it against P.
    """
    other_slug = _seed_r_unrelated_active_mission(owned_checkouts)
    monkeypatch.chdir(owned_checkouts.repository_root)

    result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--json")

    assert result.exit_code != 0, result.output
    payload = _payload(result)
    assert payload.get("ok") is False, payload
    assert payload["error"]["code"] == "FEATURE_CONTEXT_UNRESOLVED", payload
    assert "requires an explicit --mission" in payload["error"]["message"], payload
    assert other_slug not in result.output, result.output


def test_issue4_flagless_status_from_p_without_mission_never_shows_r_unrelated_mission(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review cycle 1 issue 4, case 2 (tightened in cycle 2): flagless ``status`` from cwd=P
    without ``--mission``, with R holding its own unrelated active mission, must
    refuse with the ordinary ``mission_required`` error -- it must neither
    render R's mission nor succeed at all.
    """
    other_slug = _seed_r_unrelated_active_mission(owned_checkouts)
    monkeypatch.chdir(owned_checkouts.owned_root)

    result = _status("--json")

    assert result.exit_code == 1, result.output
    payload = _payload(result)
    assert payload.get("ok") is False, payload
    assert "--mission <slug> is required" in json.dumps(payload), payload
    assert other_slug not in json.dumps(payload.get("work_packages", "")), payload


def _bare_status_defaults_to(slug: str, cwd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(cwd)
    result = _status("--json")
    assert result.exit_code == 0, result.output
    assert _payload(result)["mission_slug"] == slug


def test_issue4_4677_bare_status_in_lane_worktree_defaults_to_sole_mission(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 item 1: #4677 still holds in a LANE worktree of R (cwd != R)."""
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree
    from tests.integration.conftest import _git

    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    lane_path, lane_branch = predict_lane_worktree(owned_checkouts.repository_root, slug, "lane-a")
    _git(owned_checkouts.repository_root, "worktree", "add", "-qb", lane_branch, str(lane_path))
    _bare_status_defaults_to(slug, lane_path, monkeypatch)


def test_issue4_4677_bare_status_in_coordination_worktree_defaults_to_sole_mission(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 item 1: #4677 still holds in a COORDINATION worktree of R."""
    from tests.integration.conftest import _git

    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    coord_path = owned_checkouts.repository_root / ".worktrees" / f"{slug}-coord"
    _git(owned_checkouts.repository_root, "worktree", "add", "-qb", f"codex/{slug}-coord", str(coord_path))
    _bare_status_defaults_to(slug, coord_path, monkeypatch)


def test_issue4_bare_status_from_p_under_worktrees_never_shows_r_mission(make_owned_checkouts: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """An owned P placed under ``R/.worktrees`` (classified LANE_WORKTREE, the carrier-contract trap) is still an owned candidate."""
    checkouts = make_owned_checkouts(placement="under_worktrees")
    slug = _seed_r_unrelated_active_mission(checkouts)
    monkeypatch.chdir(checkouts.owned_root)
    result = _status("--json")
    assert result.exit_code == 1, result.output
    assert "--mission <slug> is required" in result.output
    assert slug not in result.output


def test_issue4_4677_bare_status_in_stale_lane_worktree_defaults_to_sole_mission(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 3: a stale lane under ``.worktrees`` (not in lanes.json) owns nothing -> #4677 default."""
    from tests.integration.conftest import _git

    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    stale = owned_checkouts.repository_root / ".worktrees" / f"{slug}-lane-stale"
    _git(owned_checkouts.repository_root, "worktree", "add", "-qb", "stale-lane-branch", str(stale))
    _bare_status_defaults_to(slug, stale, monkeypatch)


def test_issue4_4677_bare_status_in_plain_linked_checkout_defaults_to_sole_mission(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 3: a plain linked checkout of R (``git worktree add ../hotfix``, no claim) owns nothing -> #4677 default."""
    from tests.integration.conftest import _git

    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    hotfix = owned_checkouts.repository_root.parent / "hotfix"
    _git(owned_checkouts.repository_root, "worktree", "add", "-qb", "hotfix-branch", str(hotfix))
    _bare_status_defaults_to(slug, hotfix, monkeypatch)


def test_issue4_4677_bare_status_in_repository_root_defaults_to_sole_mission(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    _bare_status_defaults_to(slug, owned_checkouts.repository_root, monkeypatch)


# ---------------------------------------------------------------------------
# O2 / FR-005 / US1-AS2: ``agent mission setup-plan``.
# ---------------------------------------------------------------------------


_SUBSTANTIVE_PLAN_BODY = "# Plan\n\n## Technical Context\n**Language/Version**: Python 3.11\n**Primary Dependencies**: typer, pydantic\n"


def _remove_plan(owned_checkouts: OwnedCheckouts) -> None:
    """Remove the committed scaffolded plan.md, then leave an UNCOMMITTED substantive one in its place.

    ``_scaffold_plan_template`` no-ops when ``plan_file`` already exists
    (C-007), so a plan.md that satisfies the software-dev
    ``_PLAN_FIELD_DECLARATIONS`` shape (Technical Context +
    Language/Version + a peer field) reaches ``_commit_plan_if_substantive``
    unmodified and gets committed -- a bare pristine scaffold (what a
    ``git rm`` alone would produce, since ``setup-plan`` would then write a
    fresh template copy) is a DIFFERENT, separately-tested edge case
    (T046's own "Scaffold-only plan: no commit" note), not this row's O2/
    US1-AS2 target.
    """
    from tests.integration.conftest import _git

    plan_file = owned_checkouts.mission_dir / "plan.md"
    _git(owned_checkouts.owned_root, "rm", "-q", str(plan_file.relative_to(owned_checkouts.owned_root)))
    _git(owned_checkouts.owned_root, "commit", "-qm", "remove scaffolded plan.md")
    plan_file.write_text(_SUBSTANTIVE_PLAN_BODY, encoding="utf-8")


def test_o2_flagless_setup_plan_from_p_commits_in_p(
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target: flagless ``setup-plan`` from P creates+commits plan.md in P; R unchanged."""
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.owned_root)

    before = r_snapshot.take()
    from tests.integration.conftest import _git

    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")

    result = _setup_plan("--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("result") != "error", (payload, result.output)

    head_after = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    assert head_after != head_before, payload
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD~1") == head_before, "expected exactly one new commit in P"
    touched = _git(owned_checkouts.owned_root, "log", "-1", "--name-only", "--pretty=format:")
    assert f"kitty-specs/{owned_checkouts.mission_slug}/plan.md" in touched, touched
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_o2_flag_setup_plan_from_r_commits_in_p(
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US1-AS2 (target): ``--owned-checkout P`` from cwd=R commits plan.md in P; R unchanged."""
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)

    before = r_snapshot.take()
    from tests.integration.conftest import _git

    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")

    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("result") != "error", payload

    head_after = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    assert head_after != head_before
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD~1") == head_before, "expected exactly one new commit in P"
    touched = _git(owned_checkouts.owned_root, "log", "-1", "--name-only", "--pretty=format:")
    assert f"kitty-specs/{owned_checkouts.mission_slug}/plan.md" in touched, touched
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_o2_setup_plan_owned_arm_never_calls_non_owned_resolution_seams(
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review cycle 1 issue 3 -- setup-plan arm: an owned run must never reach
    ``_resolve_setup_plan_feature_dir``, ``mission._show_branch_context``,
    ``mission._planning_read_dir`` or ``resolve_checkout_identity`` (each
    patched to raise). A real end-to-end owned ``setup-plan`` run still
    succeeds, proving every one of those R-side seams is genuinely skipped,
    not merely unreached by coincidence of this fixture's shape.
    """
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.owned_root)

    import specify_cli.cli.commands.agent.mission as _mission_module
    import specify_cli.cli.commands.agent.mission_setup_plan as _setup_plan_module

    def _raise(name: str) -> Any:
        def _inner(*args: object, **kwargs: object) -> None:
            raise AssertionError(f"owned arm must not call {name}")

        return _inner

    monkeypatch.setattr(
        _setup_plan_module,
        "_resolve_setup_plan_feature_dir",
        _raise("_resolve_setup_plan_feature_dir"),
    )
    monkeypatch.setattr(_mission_module, "_show_branch_context", _raise("mission._show_branch_context"))
    monkeypatch.setattr(_mission_module, "_planning_read_dir", _raise("mission._planning_read_dir"))
    monkeypatch.setattr(_setup_plan_module, "resolve_checkout_identity", _raise("resolve_checkout_identity"))

    result = _setup_plan("--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("result") != "error", (payload, result.output)


def test_control_b_non_owned_setup_plan_shape_unchanged(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control (b): a non-owned, R-only mission's ``setup-plan`` succeeds, base keys unchanged."""
    r_root = owned_checkouts.repository_root
    monkeypatch.chdir(r_root)
    from tests.integration.conftest import _git, _write_mission, _write_single_lane_manifest

    other_slug = "r-only-fixture-02M2D9FF"
    other_id = "02M2D9FF000000000000000001"
    mission_dir = r_root / "kitty-specs" / other_slug
    _write_mission(mission_dir, mission_id=other_id, slug=other_slug, topology="single_branch", target_branch="main", wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=other_slug, mission_id=other_id, target_branch="main", wp_ids=("WP01",))
    (mission_dir / "plan.md").unlink()
    _git(r_root, "add", ".")
    _git(r_root, "commit", "-qm", "r-only mission, no plan")
    _activate_mission_type(r_root)

    result = _setup_plan("--mission", other_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "stale_repository_root_copy" not in payload, payload


# ---------------------------------------------------------------------------
# Review cycle 1 issue 6: the remaining T044 rows (stale-copy O1/O2, FR-004
# handle forms, NFR-001 cwd matrix, NFR-002 counts, T046 spec/scaffold legs).
# ---------------------------------------------------------------------------


def _prepare_status(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_tasks_md_sections(owned_checkouts)
    _fix_owned_files_contradiction(owned_checkouts)
    _finalize(owned_checkouts, owned_checkouts.mission_slug, monkeypatch)


def _count_ownership_claims(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    import specify_cli.core.checkout_ownership as ownership_mod

    original = ownership_mod.resolve_ownership_claim

    def _counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(ownership_mod, "resolve_ownership_claim", _counting)
    return calls


def _arm_get_main_repo_root_after_mint(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Arm ``get_main_repo_root`` to fail once the owned fact has been minted (review cycle 2, item 3).

    The minter legitimately calls ``get_main_repo_root``, so the pin is armed
    by wrapping ``_owned_checkout.resolve_owned_or_adopt`` and only trips on
    calls made AFTER a fact exists. Every module alias of the function is
    patched (not just ``specify_cli.core.paths``), and each armed call is both
    raised AND recorded: several owned-path callers swallow exceptions
    (``except Exception: logger.debug``), so the returned hit list -- asserted
    empty by the caller -- is what makes the pin non-vacuous.
    """
    import sys

    import specify_cli.cli.commands._owned_checkout as owned_checkout_module
    import specify_cli.core.paths as paths_module

    original = paths_module.get_main_repo_root
    state = {"armed": False}
    hits: list[str] = []

    def _guarded(*args: Any, **kwargs: Any) -> Any:
        if state["armed"]:
            hits.append(repr(args[:1]))
            raise AssertionError("owned arm called get_main_repo_root after the fact was minted")
        return original(*args, **kwargs)

    for module in list(sys.modules.values()):
        if getattr(module, "get_main_repo_root", None) is original:
            monkeypatch.setattr(module, "get_main_repo_root", _guarded)

    real_resolve = owned_checkout_module.resolve_owned_or_adopt

    def _arming_resolve(*args: Any, **kwargs: Any) -> Any:
        fact = real_resolve(*args, **kwargs)
        if fact is not None:
            state["armed"] = True
        return fact

    monkeypatch.setattr(owned_checkout_module, "resolve_owned_or_adopt", _arming_resolve)
    return hits


def test_armed_get_main_repo_root_pin_setup_plan(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 item 2/3: an end-to-end owned setup-plan (real git fixture, commits plan.md) never reaches ``get_main_repo_root`` after minting."""
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    hits = _arm_get_main_repo_root_after_mint(monkeypatch)
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    assert _payload(result).get("result") != "error"
    assert hits == [], hits


@pytest.mark.parametrize("cwd_kind", ["repository_root", "owned_checkout"])
def test_armed_get_main_repo_root_pin_status(owned_checkouts: OwnedCheckouts, cwd_kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 2 item 3: an end-to-end owned status (flagged from R, flagless from P) never reaches ``get_main_repo_root`` after minting."""
    _prepare_status(owned_checkouts, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root if cwd_kind == "repository_root" else owned_checkouts.owned_root)
    hits = _arm_get_main_repo_root_after_mint(monkeypatch)
    args = ["--mission", owned_checkouts.mission_slug, "--json"]
    if cwd_kind == "repository_root":
        args = ["--owned-checkout", str(owned_checkouts.owned_root), *args]
    result = _status(*args)
    assert result.exit_code == 0, result.output
    assert sorted(wp["id"] for wp in _payload(result)["work_packages"]) == ["WP01", "WP02"]
    assert hits == [], hits


def test_o1_flagless_status_from_p_with_stale_copy_lists_p_and_names_copy(
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O1 (flagless) with R holding a stale WP01-WP05 copy: P's WPs win, the copy is named, R untouched."""
    _prepare_status(owned_checkouts, monkeypatch)
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.owned_root)

    before = r_snapshot.take()
    result = _status("--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert sorted(wp["id"] for wp in payload["work_packages"]) == ["WP01", "WP02"], payload
    assert Path(payload["stale_repository_root_copy"]["path"]).resolve() == r_copy_dir.resolve()
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_fr004_status_accepts_every_handle_form(owned_checkouts: OwnedCheckouts, owned_handle: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: slug, mid8 and full mission_id all resolve to the same owned mission."""
    _prepare_status(owned_checkouts, monkeypatch)
    monkeypatch.chdir(owned_checkouts.repository_root)
    result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_handle, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["mission_slug"] == owned_checkouts.mission_slug, payload
    assert sorted(wp["id"] for wp in payload["work_packages"]) == ["WP01", "WP02"], payload


def test_fr004_setup_plan_accepts_every_handle_form(owned_checkouts: OwnedCheckouts, owned_handle: str, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004 for setup-plan: every handle form commits plan.md in P, exactly once."""
    from tests.integration.conftest import _git

    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    before = r_snapshot.take()
    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_handle, "--json")
    assert result.exit_code == 0, result.output
    assert _payload(result).get("result") != "error"
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD~1") == head_before
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_nfr001_status_from_every_cwd_leaves_r_unchanged(
    owned_checkouts: OwnedCheckouts, owned_cwd: Path, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-001: an owned status run is byte-clean for R from cwd = R, P and an unrelated sibling."""
    _prepare_status(owned_checkouts, monkeypatch)
    monkeypatch.chdir(owned_cwd)
    before = r_snapshot.take()
    result = _status("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    assert sorted(wp["id"] for wp in _payload(result)["work_packages"]) == ["WP01", "WP02"]
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_nfr001_setup_plan_from_every_cwd_leaves_r_unchanged(
    owned_checkouts: OwnedCheckouts, owned_cwd: Path, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-001 for setup-plan, across the same cwd matrix."""
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_cwd)
    before = r_snapshot.take()
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    assert _payload(result).get("result") != "error"
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_nfr002_owned_setup_plan_resolves_ownership_once(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    calls = _count_ownership_claims(monkeypatch)
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    assert len(calls) == 1, calls


def _seed_r_only_mission(owned_checkouts: OwnedCheckouts, slug: str, mission_id: str, *, drop_plan: bool = False) -> None:
    from tests.integration.conftest import _git, _write_mission, _write_single_lane_manifest

    r_root = owned_checkouts.repository_root
    mission_dir = r_root / "kitty-specs" / slug
    _write_mission(mission_dir, mission_id=mission_id, slug=slug, topology="single_branch", target_branch="main", wp_ids=("WP01",))
    _write_single_lane_manifest(mission_dir, mission_slug=slug, mission_id=mission_id, target_branch="main", wp_ids=("WP01",))
    if drop_plan:
        (mission_dir / "plan.md").unlink()
    _git(r_root, "add", ".")
    _git(r_root, "commit", "-qm", f"r-only mission {slug}")


def test_nfr002_non_owned_runs_resolve_no_ownership_claim(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002 (non-owned): status and setup-plan on an R-only mission never resolve an ownership claim."""
    _seed_r_only_mission(owned_checkouts, "r-only-nfr2-01M2D9F2", "01M2D9F2000000000000000001", drop_plan=True)
    _activate_mission_type(owned_checkouts.repository_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    calls = _count_ownership_claims(monkeypatch)
    assert _status("--mission", "r-only-nfr2-01M2D9F2", "--json").exit_code == 0
    assert _setup_plan("--mission", "r-only-nfr2-01M2D9F2", "--json").exit_code == 0
    assert calls == [], calls


def test_o2_flagless_setup_plan_from_p_with_stale_copy_commits_in_p(
    owned_checkouts: OwnedCheckouts, stale_root_copy: Any, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O2 (flagless) with a stale copy in R: plan.md lands in P (one commit), R's copy untouched, FR-007 key present."""
    from tests.integration.conftest import _git

    r_copy_dir = stale_root_copy()
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.owned_root)
    before = r_snapshot.take()
    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    result = _setup_plan("--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("result") != "error", payload
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD~1") == head_before
    assert Path(payload["stale_repository_root_copy"]["path"]).resolve() == r_copy_dir.resolve()
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_o2_flag_setup_plan_no_stale_copy_reports_null(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007 (no copy): the JSON key is present and ``null`` for setup-plan."""
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert "stale_repository_root_copy" in payload and payload["stale_repository_root_copy"] is None, payload


def test_o2_flag_setup_plan_human_mode_warns_about_stale_copy(owned_checkouts: OwnedCheckouts, stale_root_copy: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007 human mode: the stale-copy warning renders; the plan is still scaffolded in P."""
    stale_root_copy()
    _remove_plan(owned_checkouts)
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug)
    assert result.exit_code == 0, result.output
    combined = (result.stdout or "") + (result.stderr or "")
    assert "stale copy" in combined.lower(), combined
    assert (owned_checkouts.mission_dir / "plan.md").exists()


def test_t046_non_substantive_spec_blocks_without_commit(owned_checkouts: OwnedCheckouts, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """T046: a committed but non-substantive spec.md in P blocks setup-plan (exit 0, blocked payload), no commit anywhere."""
    from tests.integration.conftest import _git

    (owned_checkouts.mission_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(owned_checkouts.owned_root, "add", ".")
    _git(owned_checkouts.owned_root, "commit", "-qm", "non-substantive spec")
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    before = r_snapshot.take()
    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["result"] == "blocked" and payload["error_code"] == "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED", payload
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD") == head_before
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


def test_t046_scaffold_only_creates_plan_in_p_without_commit(owned_checkouts: OwnedCheckouts, r_snapshot: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """T046: a pristine scaffold is created in P (not R), reported ``scaffold_only``, and NOT committed."""
    from tests.integration.conftest import _git

    plan_file = owned_checkouts.mission_dir / "plan.md"
    _git(owned_checkouts.owned_root, "rm", "-q", str(plan_file.relative_to(owned_checkouts.owned_root)))
    _git(owned_checkouts.owned_root, "commit", "-qm", "remove scaffolded plan.md")
    _activate_mission_type(owned_checkouts.owned_root)
    monkeypatch.chdir(owned_checkouts.repository_root)
    before = r_snapshot.take()
    head_before = _git(owned_checkouts.owned_root, "rev-parse", "HEAD")
    result = _setup_plan("--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload.get("scaffold_only") is True, payload
    assert plan_file.exists()
    assert not (owned_checkouts.repository_root / "kitty-specs" / owned_checkouts.mission_slug / "plan.md").exists()
    assert _git(owned_checkouts.owned_root, "rev-parse", "HEAD") == head_before
    r_snapshot.assert_unchanged(before, r_snapshot.take(), tolerate_status_mutex_for=owned_checkouts.mission_slug)


# ---------------------------------------------------------------------------
# Review cycle 4: the #4677 default path must cost a CONSTANT number of git
# calls and resolve zero ownership claims for non-owned checkouts (NFR-002).
# ---------------------------------------------------------------------------

_MANY_MISSIONS = 60
_MAX_GIT_SUBPROCESSES = 40


def _seed_many_missions(owned_checkouts: OwnedCheckouts, active_slug: str) -> None:
    """Add ``_MANY_MISSIONS`` merged (completed) missions next to R's one active mission, committed on R's branch."""
    import json as _json

    from tests.integration.conftest import _git

    specs = owned_checkouts.repository_root / "kitty-specs"
    for index in range(_MANY_MISSIONS):
        mission_dir = specs / f"merged-{index:03d}-01M4MANY"
        mission_dir.mkdir(parents=True)
        meta = {"mission_slug": mission_dir.name, "mission_type": "software-dev", "target_branch": "main", "merged_at": "2026-01-01T00:00:00+00:00"}
        (mission_dir / "meta.json").write_text(_json.dumps(meta), encoding="utf-8")
    assert (specs / active_slug).is_dir()
    _git(owned_checkouts.repository_root, "add", ".")
    _git(owned_checkouts.repository_root, "commit", "-qm", "many merged missions")


def _count_git_subprocesses(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record every ``git`` subprocess started (``subprocess.run`` and friends all go through ``Popen``)."""
    import subprocess as _subprocess

    calls: list[Any] = []
    real_popen: Any = _subprocess.Popen

    def _popen(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, (list, tuple)) and cmd and str(cmd[0]) == "git":
            calls.append(cmd)
        return real_popen(cmd, *args, **kwargs)

    monkeypatch.setattr(_subprocess, "Popen", _popen)
    return calls


@pytest.mark.parametrize("kind", ["lane", "plain_linked"])
def test_issue4_cycle4_default_path_cost_is_constant_and_claim_free(owned_checkouts: OwnedCheckouts, kind: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bare status from a lane / plain linked checkout with many missions: constant git calls, zero claim resolutions."""
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree
    from tests.integration.conftest import _git

    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    _seed_many_missions(owned_checkouts, slug)
    if kind == "lane":
        cwd, branch = predict_lane_worktree(owned_checkouts.repository_root, slug, "lane-a")
    else:
        cwd, branch = owned_checkouts.repository_root.parent / "hotfix", "hotfix-branch"
    _git(owned_checkouts.repository_root, "worktree", "add", "-qb", branch, str(cwd))
    monkeypatch.chdir(cwd)
    claims = _count_ownership_claims(monkeypatch)
    git_calls = _count_git_subprocesses(monkeypatch)

    result = _status("--json")

    assert result.exit_code == 0, result.output
    assert _payload(result)["mission_slug"] == slug
    assert claims == [], f"non-owned run resolved {len(claims)} ownership claims"
    assert len(git_calls) <= _MAX_GIT_SUBPROCESSES, f"{len(git_calls)} git subprocesses with {_MANY_MISSIONS} missions"


def test_issue4_cycle4_owned_p_with_many_missions_still_refuses(owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pre-filter must not lose the owned row: P (its branch matches its mission target) is still refused with mission_required."""
    slug = _seed_r_unrelated_active_mission(owned_checkouts)
    _seed_many_missions(owned_checkouts, slug)
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _status("--json")
    assert result.exit_code == 1, result.output
    assert "--mission <slug> is required" in result.output
    assert slug not in result.output
