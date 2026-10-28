"""Local event-log retention engine (#6610; ADR 2026-10-13-2 D-3 Confirmation).

A fixture project with a completed and an open Mission carries every surface the
registry marks ``ledger_retention`` or ``rebuildable``: run directories, per-Mission
glossary logs, derived Mission views and the Op index, plus committed files that
must never move. ``now`` is injected; ages come from file modification times set
with ``os.utime``. No sleeps.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kernel.event_log_append import event_log_lock_path
from kernel.locks import machine_file_lock
from runtime.next import run_index
from runtime.next.run_lock import run_cursor_lock
from specify_cli.core.ledger_retention import RetentionLimits
from specify_cli.state import contract, retention
from specify_cli.state.contract import CleanupPolicy, RetentionRule
from specify_cli.state.retention import (
    KIND_CACHE,
    KIND_MISSION_LOG,
    KIND_RUN,
    REASON_COMPLETED,
    REASON_LOCK_HELD,
    REASON_MISSION_NOT_FOUND,
    REASON_MISSION_OPEN,
    REASON_REBUILDABLE,
    REASON_WITHIN_KEEP_RUNS,
    REASON_YOUNGER_THAN_MAX_AGE,
    RetentionPlan,
    RetentionPolicyDriftError,
    UnsafeRetentionPathError,
    apply_retention,
    scan_retention,
)


NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
DONE_SLUG = "001-done-mission"
DONE_ID = "01DONE0000000000000000000A"
OPEN_SLUG = "002-open-mission"
OPEN_ID = "01OPEN0000000000000000000B"
UNKNOWN_ID = "01GONE0000000000000000000C"
GLOSSARY_DIR = Path(".kittify/events/glossary")
LIMITS_NO_KEEP = RetentionLimits(keep_runs=0, max_age_days=30, source="default")
TRACKED_FILES = (
    f"kitty-specs/{DONE_SLUG}/meta.json",
    f"kitty-specs/{DONE_SLUG}/status.events.jsonl",
    f"kitty-specs/{OPEN_SLUG}/meta.json",
    "kitty-ops/01OPS000000000000000000000.jsonl",
)


# ---------------------------------------------------------------------------
# Fixture project
# ---------------------------------------------------------------------------


def _set_age(path: Path, age_days: float) -> None:
    stamp = (NOW - timedelta(days=age_days)).timestamp()
    targets = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    for target in targets:
        os.utime(target, (stamp, stamp))


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _mission(repo: Path, slug: str, mission_id: str, *, merged: bool) -> Path:
    meta: dict[str, object] = {"mission_id": mission_id, "mission_slug": slug, "slug": slug, "mission_type": "software-dev"}
    if merged:
        meta["merged_at"] = "2026-09-01T00:00:00+00:00"
    feature_dir = repo / "kitty-specs" / slug
    _write(feature_dir / "meta.json", json.dumps(meta, indent=2))
    return feature_dir


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A git-initialised project with one completed and one open Mission."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    done = _mission(tmp_path, DONE_SLUG, DONE_ID, merged=True)
    _mission(tmp_path, OPEN_SLUG, OPEN_ID, merged=False)
    _write(done / "status.events.jsonl", '{"event_id": "01X", "wp_id": "WP01"}\n')
    _write(tmp_path / "kitty-ops" / "01OPS000000000000000000000.jsonl", '{"event": "started"}\n')
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "add", "kitty-specs", "kitty-ops"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "fixture"],
        check=True,
    )
    return tmp_path


def _run(repo: Path, *, slug: str | None, mission_id: str | None, age_days: float) -> Path:
    run_dir = run_index.runs_root(repo) / uuid.uuid4().hex
    state: dict[str, object] = {"run_id": run_dir.name}
    if slug is not None:
        state["mission_slug"] = slug
    if mission_id is not None:
        state["mission_id"] = mission_id
    _write(run_dir / "state.json", json.dumps(state))
    _write(run_dir / "run.events.jsonl", '{"event_type": "MissionRunStarted"}\n')
    _write(run_dir / "mission_template_frozen.yaml", "mission: software-dev\n")
    _set_age(run_dir, age_days)
    return run_dir


def _glossary_log(repo: Path, stem: str, age_days: float) -> Path:
    log = _write(repo / GLOSSARY_DIR / f"{stem}.events.jsonl", '{"event_type": "TermCaptured"}\n')
    _set_age(log, age_days)
    return log


def _index(repo: Path, entries: dict[str, Path]) -> None:
    run_index.save_index(repo, {key: {"run_dir": str(run_dir), "run_id": run_dir.name} for key, run_dir in entries.items()})


def _read_index(repo: Path) -> dict[str, object]:
    return run_index.read_index_file(run_index.feature_runs_path(repo))


def _tree_digest(repo: Path) -> dict[str, bytes | None]:
    """Every path under the project (except ``.git``) with its bytes; ``None`` for a directory."""
    digest: dict[str, bytes | None] = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo)
        if rel.parts[0] == ".git":
            continue
        digest[rel.as_posix()] = path.read_bytes() if path.is_file() else None
    return digest


def _by_path(plan_items: list[retention.RetentionItem], repo: Path) -> dict[str, retention.RetentionItem]:
    return {item.path.relative_to(repo).as_posix(): item for item in plan_items}


def _rel(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


# ---------------------------------------------------------------------------
# Scan: verdicts
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
def test_newest_keep_runs_are_kept_and_the_rest_of_an_old_completed_mission_are_candidates(project: Path) -> None:
    runs = [_run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=40 + i * 0.01) for i in range(25)]
    plan = scan_retention(project, RetentionLimits(), now=NOW)
    items = _by_path(plan.items, project)
    newest, oldest = runs[:20], runs[20:]
    for run_dir in newest:
        item = items[_rel(run_dir, project)]
        assert (item.verdict, item.reason, item.kind) == ("kept", REASON_WITHIN_KEEP_RUNS, KIND_RUN)
    for run_dir in oldest:
        item = items[_rel(run_dir, project)]
        assert (item.verdict, item.reason, item.mission) == ("candidate", REASON_COMPLETED, DONE_SLUG)
        assert item.age_days == pytest.approx(40 + runs.index(run_dir) * 0.01)
    assert {_rel(i.path, project) for i in plan.candidates if i.kind == KIND_RUN} == {_rel(r, project) for r in oldest}


@pytest.mark.unit
@pytest.mark.fast
def test_a_run_started_by_the_real_writer_becomes_a_candidate(project: Path) -> None:
    """DS-H1: ``next`` records no Mission in ``state.json``; the run index links it."""
    from runtime.next import runtime_bridge_io

    run_ref = runtime_bridge_io.get_or_start_run(DONE_SLUG, project, "software-dev")
    run_dir = Path(run_ref.run_dir)
    snapshot = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert (snapshot.get("mission_id"), snapshot.get("mission_slug")) == (None, None)
    _set_age(run_dir, 60)

    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    item = _by_path(plan.items, project)[_rel(run_dir, project)]
    assert (item.verdict, item.reason, item.mission) == ("candidate", REASON_COMPLETED, DONE_SLUG)

    result = apply_retention(project, plan)
    assert [i.path for i in result.deleted] == [run_dir]
    assert result.removed_index_entries == [DONE_ID]
    assert DONE_ID not in _read_index(project)


@pytest.mark.unit
@pytest.mark.fast
def test_a_run_linked_only_through_the_index_resolves_its_mission(project: Path) -> None:
    run_dir = run_index.runs_root(project) / uuid.uuid4().hex
    _write(run_dir / "state.json", json.dumps({"run_id": run_dir.name, "inputs": {"mission_slug": DONE_SLUG}}))
    _write(run_dir / "run.events.jsonl", '{"event_type": "MissionRunStarted"}\n')
    _set_age(run_dir, 60)
    run_index.save_index(
        project,
        {DONE_ID: {"run_dir": str(run_dir), "run_id": run_dir.name, "mission_id": DONE_ID, "mission_slug": DONE_SLUG}},
    )
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert (item.verdict, item.reason, item.mission) == ("candidate", REASON_COMPLETED, DONE_SLUG)


@pytest.mark.unit
@pytest.mark.fast
def test_runs_beyond_keep_runs_but_younger_than_max_age_are_kept(project: Path) -> None:
    for i in range(20):
        _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=1 + i * 0.1)
    old_but_young = [_run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=10 + i * 0.1) for i in range(5)]
    plan = scan_retention(project, RetentionLimits(), now=NOW)
    items = _by_path(plan.items, project)
    for run_dir in old_but_young:
        assert items[_rel(run_dir, project)].reason == REASON_YOUNGER_THAN_MAX_AGE
    assert [i for i in plan.candidates if i.kind == KIND_RUN] == []


@pytest.mark.unit
@pytest.mark.fast
def test_old_run_of_an_open_mission_is_kept(project: Path) -> None:
    run_dir = _run(project, slug=OPEN_SLUG, mission_id=OPEN_ID, age_days=90)
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert (item.verdict, item.reason, item.mission) == ("kept", REASON_MISSION_OPEN, OPEN_SLUG)


@pytest.mark.unit
@pytest.mark.fast
def test_run_whose_mission_resolves_nowhere_is_kept(project: Path) -> None:
    unknown = _run(project, slug="999-elsewhere", mission_id=UNKNOWN_ID, age_days=90)
    anonymous = _run(project, slug=None, mission_id=None, age_days=90)
    corrupt = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=90)
    (corrupt / "state.json").write_text("{not json", encoding="utf-8")
    _set_age(corrupt, 90)
    items = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)
    for run_dir in (unknown, anonymous, corrupt):
        item = items[_rel(run_dir, project)]
        assert (item.verdict, item.reason, item.mission) == ("kept", REASON_MISSION_NOT_FOUND, None)


@pytest.mark.unit
@pytest.mark.fast
def test_run_resolves_its_mission_by_slug_when_the_id_is_absent(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=None, age_days=90)
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert (item.reason, item.mission) == (REASON_COMPLETED, DONE_SLUG)


@pytest.mark.unit
@pytest.mark.fast
def test_glossary_logs_follow_their_mission_and_non_mission_logs_are_never_listed(project: Path) -> None:
    done_log = _glossary_log(project, DONE_ID, 40)
    open_log = _glossary_log(project, OPEN_ID, 40)
    unknown_log = _glossary_log(project, UNKNOWN_ID, 40)
    cli_log = _glossary_log(project, "_cli", 400)
    renderer_log = _glossary_log(project, "_renderer", 400)
    items = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)

    done = items[_rel(done_log, project)]
    assert (done.verdict, done.reason, done.kind, done.mission, done.surface) == (
        "candidate",
        REASON_COMPLETED,
        KIND_MISSION_LOG,
        DONE_SLUG,
        "glossary_fallback_events",
    )
    assert items[_rel(open_log, project)].reason == REASON_MISSION_OPEN
    assert items[_rel(unknown_log, project)].reason == REASON_MISSION_NOT_FOUND
    assert _rel(cli_log, project) not in items
    assert _rel(renderer_log, project) not in items


@pytest.mark.unit
@pytest.mark.fast
def test_glossary_logs_are_ranked_within_their_own_kind(project: Path) -> None:
    _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=1)
    done_log = _glossary_log(project, DONE_ID, 40)
    limits = RetentionLimits(keep_runs=1, max_age_days=30)
    item = _by_path(scan_retention(project, limits, now=NOW).items, project)[_rel(done_log, project)]
    # The run does not push the log out of the newest-1 of ITS kind.
    assert item.reason == REASON_WITHIN_KEEP_RUNS


@pytest.mark.unit
@pytest.mark.fast
def test_derived_views_and_ops_index_are_rebuildable_regardless_of_age(project: Path) -> None:
    derived = _write(project / ".kittify" / "derived" / DONE_SLUG / "lifecycle.json", "{}").parent
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", '{"invocation_id": "x"}\n')
    _set_age(derived, 0)
    _set_age(ops_index, 0)
    items = _by_path(scan_retention(project, RetentionLimits(), now=NOW).items, project)
    for path, surface in ((derived, "derived_mission_views"), (ops_index, "op_invocation_index")):
        item = items[_rel(path, project)]
        assert (item.verdict, item.reason, item.kind, item.surface) == ("candidate", REASON_REBUILDABLE, KIND_CACHE, surface)
    # The derived view names its Mission when the slug resolves.
    assert items[_rel(derived, project)].mission == DONE_SLUG


@pytest.mark.unit
@pytest.mark.fast
def test_an_empty_project_scans_to_an_empty_plan(tmp_path: Path) -> None:
    plan = scan_retention(tmp_path, RetentionLimits(), now=NOW)
    assert plan.items == []
    assert plan.to_dict(tmp_path)["candidates"] == []


@pytest.mark.unit
@pytest.mark.fast
def test_scan_defaults_now_to_the_kernel_clock(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=0)
    os.utime(run_dir / "state.json", (time.time(), time.time()))
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP).items, project)[_rel(run_dir, project)]
    assert item.reason == REASON_YOUNGER_THAN_MAX_AGE


# ---------------------------------------------------------------------------
# Preview changes nothing; serialization
# ---------------------------------------------------------------------------


def _full_fixture(repo: Path) -> dict[str, Path]:
    done_run = _run(repo, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    open_run = _run(repo, slug=OPEN_SLUG, mission_id=OPEN_ID, age_days=60)
    young_run = _run(repo, slug=DONE_SLUG, mission_id=DONE_ID, age_days=2)
    _index(repo, {f"{DONE_SLUG}:software-dev": done_run, f"{OPEN_SLUG}:software-dev": open_run, "young": young_run})
    done_log = _glossary_log(repo, DONE_ID, 60)
    _write(done_log.with_name(done_log.name + ".lock"), "")
    _write(done_log.with_name(done_log.name + ".torn"), "partial")
    _write(open_run / "state.json.lock", "")
    open_log = _glossary_log(repo, OPEN_ID, 60)
    cli_log = _glossary_log(repo, "_cli", 600)
    derived = _write(repo / ".kittify" / "derived" / DONE_SLUG / "lifecycle.json", "{}").parent
    ops_index = _write(repo / "kitty-ops" / "ops-index.jsonl", '{"invocation_id": "x"}\n')
    return {
        "done_run": done_run,
        "open_run": open_run,
        "young_run": young_run,
        "done_log": done_log,
        "open_log": open_log,
        "cli_log": cli_log,
        "derived": derived,
        "ops_index": ops_index,
    }


@pytest.mark.unit
@pytest.mark.fast
def test_preview_changes_nothing(project: Path) -> None:
    _full_fixture(project)
    before = _tree_digest(project)
    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert plan.candidates
    assert _tree_digest(project) == before


@pytest.mark.unit
@pytest.mark.fast
def test_plan_serializes_to_the_contract_shape(project: Path) -> None:
    paths = _full_fixture(project)
    payload = scan_retention(project, LIMITS_NO_KEEP, now=NOW).to_dict(project)
    assert set(payload) == {"applied", "limits", "candidates", "kept", "deleted", "failed", "removed_index_entries"}
    assert payload["applied"] is False
    assert payload["limits"] == {"keep_runs": 0, "max_age_days": 30, "source": "default"}
    assert (payload["deleted"], payload["failed"], payload["removed_index_entries"]) == ([], [], [])
    candidate = next(c for c in payload["candidates"] if c["path"] == _rel(paths["done_run"], project))
    assert candidate == {
        "surface": "runtime_run_event_log",
        "kind": "run",
        "path": _rel(paths["done_run"], project),
        "mission": DONE_SLUG,
        "age_days": pytest.approx(60),
        "reason": REASON_COMPLETED,
    }
    json.dumps(payload)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
def test_apply_deletes_only_candidates_and_keeps_the_index_consistent(project: Path) -> None:
    paths = _full_fixture(project)
    tracked_before = {name: (project / name).read_bytes() for name in TRACKED_FILES}

    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    result = apply_retention(project, plan)

    deleted = {_rel(item.path, project) for item in result.deleted}
    assert deleted == {_rel(paths[k], project) for k in ("done_run", "done_log", "derived", "ops_index")}
    assert result.failed == []
    assert result.kept_at_apply == []
    for key in ("done_run", "done_log", "derived", "ops_index"):
        assert not paths[key].exists(), key
    for key in ("open_run", "young_run", "open_log", "cli_log"):
        assert paths[key].exists(), key

    index = _read_index(project)
    assert set(index) == {f"{OPEN_SLUG}:software-dev", "young"}
    assert result.removed_index_entries == [f"{DONE_SLUG}:software-dev"]

    for name, content in tracked_before.items():
        assert (project / name).read_bytes() == content, name
    status = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "--", "kitty-specs", "kitty-ops"], capture_output=True, text=True, check=True)
    # Only the ignored-tier ops-index (untracked) could ever show; it is gone now.
    assert status.stdout == ""

    # Lock files survive; only the deleted run's own state.json.lock went with its directory.
    assert paths["done_log"].with_name(paths["done_log"].name + ".lock").exists()
    assert paths["done_log"].with_name(paths["done_log"].name + ".torn").exists()
    assert (paths["open_run"] / "state.json.lock").exists()

    payload = result.to_dict(project)
    assert payload["applied"] is True
    assert {d["path"] for d in payload["deleted"]} == deleted
    assert payload["removed_index_entries"] == [f"{DONE_SLUG}:software-dev"]


@pytest.mark.unit
@pytest.mark.fast
def test_index_entries_outside_the_repo_are_left_alone(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    run_index.write_index_file(
        run_index.feature_runs_path(project),
        {
            "mine": {"run_dir": _rel(run_dir, project)},
            "foreign": {"run_dir": "/somewhere/else/.kittify/runtime/runs/abc"},
            "malformed": "not-a-mapping",
            "no-dir": {"run_id": "x"},
        },
    )
    result = apply_retention(project, scan_retention(project, LIMITS_NO_KEEP, now=NOW))
    assert result.removed_index_entries == ["mine"]
    assert set(_read_index(project)) == {"foreign", "malformed", "no-dir"}


@pytest.mark.unit
@pytest.mark.fast
def test_held_run_cursor_lock_keeps_the_run_at_apply_time(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    _index(project, {"mine": run_dir})
    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert [i.reason for i in plan.items] == [REASON_COMPLETED]

    with run_cursor_lock(run_dir):
        result = apply_retention(project, plan)

    assert result.deleted == []
    assert [(i.verdict, i.reason) for i in result.kept_at_apply] == [("kept", REASON_LOCK_HELD)]
    assert run_dir.is_dir()
    assert set(_read_index(project)) == {"mine"}
    assert result.to_dict(project)["kept"][0]["reason"] == REASON_LOCK_HELD


@pytest.mark.unit
@pytest.mark.fast
def test_held_run_cursor_lock_is_reported_in_preview(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    with run_cursor_lock(run_dir):
        plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert [(i.verdict, i.reason) for i in plan.items] == [("kept", REASON_LOCK_HELD)]


@pytest.mark.unit
@pytest.mark.fast
def test_held_event_log_lock_keeps_the_ops_index_and_glossary_log(project: Path) -> None:
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", '{"invocation_id": "x"}\n')
    done_log = _glossary_log(project, DONE_ID, 60)
    with machine_file_lock(event_log_lock_path(ops_index)), machine_file_lock(event_log_lock_path(done_log)):
        plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
        items = _by_path(plan.items, project)
        assert items[_rel(ops_index, project)].reason == REASON_LOCK_HELD
        assert items[_rel(done_log, project)].reason == REASON_LOCK_HELD

    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert {i.reason for i in plan.items} == {REASON_REBUILDABLE, REASON_COMPLETED}
    with machine_file_lock(event_log_lock_path(ops_index)), machine_file_lock(event_log_lock_path(done_log)):
        result = apply_retention(project, plan)
    assert result.deleted == []
    assert {i.reason for i in result.kept_at_apply} == {REASON_LOCK_HELD}
    assert ops_index.exists()
    assert done_log.exists()


@pytest.mark.unit
@pytest.mark.fast
def test_a_failed_deletion_is_recorded_and_the_rest_proceed(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _full_fixture(project)
    real_remove_tree = retention._remove_tree

    def _flaky_remove_tree(path: Path) -> None:
        if path == paths["derived"]:
            raise OSError("disk says no")
        real_remove_tree(path)

    monkeypatch.setattr(retention, "_remove_tree", _flaky_remove_tree)
    result = apply_retention(project, scan_retention(project, LIMITS_NO_KEEP, now=NOW))

    assert [(f.item.path, f.error) for f in result.failed] == [(paths["derived"], "disk says no")]
    assert paths["derived"].is_dir()
    assert not paths["done_run"].exists()
    assert not paths["ops_index"].exists()
    failed = result.to_dict(project)["failed"]
    assert failed == [
        {
            "surface": "derived_mission_views",
            "kind": "cache",
            "path": _rel(paths["derived"], project),
            "mission": DONE_SLUG,
            "age_days": pytest.approx(failed[0]["age_days"]),
            "reason": REASON_REBUILDABLE,
            "error": "disk says no",
        }
    ]


# ---------------------------------------------------------------------------
# FR-013: the registry's cleanup policy is the only selector
# ---------------------------------------------------------------------------


def _with_rule(monkeypatch: pytest.MonkeyPatch, surface_name: str, rule: RetentionRule) -> None:
    surfaces = tuple(
        dataclasses.replace(s, cleanup_policy=CleanupPolicy(rule, s.cleanup_policy.cleanup_command)) if s.name == surface_name else s
        for s in contract.STATE_SURFACES
    )
    monkeypatch.setattr(contract, "STATE_SURFACES", surfaces)


@pytest.mark.unit
@pytest.mark.fast
def test_scope_follows_the_registry_policy(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    done_log = _glossary_log(project, DONE_ID, 60)
    assert _rel(done_log, project) in _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)

    _with_rule(monkeypatch, "glossary_fallback_events", RetentionRule.MANUAL)
    assert scan_retention(project, LIMITS_NO_KEEP, now=NOW).items == []


@pytest.mark.unit
@pytest.mark.fast
def test_a_pruning_rule_without_a_collector_is_registry_drift(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_rule(monkeypatch, "runtime_feature_index", RetentionRule.REBUILDABLE)
    with pytest.raises(RetentionPolicyDriftError, match="runtime_feature_index"):
        scan_retention(project, RetentionLimits(), now=NOW)


@pytest.mark.unit
@pytest.mark.fast
def test_a_partial_run_family_selection_is_registry_drift(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_rule(monkeypatch, "runtime_frozen_template", RetentionRule.MANUAL)
    with pytest.raises(RetentionPolicyDriftError, match="runtime_frozen_template"):
        scan_retention(project, RetentionLimits(), now=NOW)


@pytest.mark.unit
@pytest.mark.fast
def test_a_collector_under_the_wrong_rule_is_registry_drift(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_rule(monkeypatch, "op_invocation_index", RetentionRule.LEDGER_RETENTION)
    with pytest.raises(RetentionPolicyDriftError, match="op_invocation_index"):
        scan_retention(project, RetentionLimits(), now=NOW)


# ---------------------------------------------------------------------------
# Defence in depth and helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize(
    "relative",
    [
        f"kitty-specs/{DONE_SLUG}/status.events.jsonl",
        "kitty-ops/01OPS000000000000000000000.jsonl",
        ".kittify/runtime/runs",
        ".kittify/runtime/feature-runs.json",
        ".kittify/events",
        ".kittify/config.yaml",
        "../outside",
    ],
)
def test_the_path_guard_refuses_anything_outside_the_local_tier(project: Path, relative: str) -> None:
    with pytest.raises(UnsafeRetentionPathError):
        retention._assert_deletable(project, project / relative)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize(
    "relative",
    [".kittify/runtime/runs/abc", f".kittify/events/glossary/{DONE_ID}.events.jsonl", f".kittify/derived/{DONE_SLUG}", "kitty-ops/ops-index.jsonl"],
)
def test_the_path_guard_allows_the_local_tier(project: Path, relative: str) -> None:
    retention._assert_deletable(project, project / relative)


@pytest.mark.unit
@pytest.mark.fast
def test_a_guard_refusal_is_recorded_as_a_failure(project: Path) -> None:
    tracked = project / TRACKED_FILES[1]
    rogue = retention.RetentionItem(
        surface="glossary_fallback_events", kind=KIND_MISSION_LOG, path=tracked, mission=DONE_SLUG, age_days=90.0, verdict="candidate", reason=REASON_COMPLETED
    )
    result = apply_retention(project, RetentionPlan(limits=RetentionLimits(), items=[rogue]))
    assert [f.item for f in result.failed] == [rogue]
    assert tracked.exists()


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("mission_id", [DONE_ID, "a/b\\c d:e", "ok_id-1.2", "ünï"])
def test_glossary_log_stem_matches_the_glossary_writer(mission_id: str) -> None:
    from glossary.events import _sanitize_mission_id

    assert retention._glossary_log_stem(mission_id) == _sanitize_mission_id(mission_id)


# ---------------------------------------------------------------------------
# NFR-001: preview speed
# ---------------------------------------------------------------------------


@pytest.mark.timing
def test_preview_over_a_thousand_runs_is_under_two_seconds(project: Path) -> None:
    for i in range(1000):
        _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=1 + (i % 90))
    started = time.perf_counter()
    plan = scan_retention(project, RetentionLimits(), now=NOW)
    elapsed = time.perf_counter() - started
    assert len(plan.items) == 1000
    assert plan.candidates
    assert elapsed < 2.0, f"preview over 1,000 runs took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Edge branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
def test_an_empty_run_dir_ages_by_its_own_mtime_and_names_no_mission(project: Path) -> None:
    run_dir = run_index.runs_root(project) / "empty"
    run_dir.mkdir(parents=True)
    stamp = (NOW - timedelta(days=50)).timestamp()
    os.utime(run_dir, (stamp, stamp))
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert item.age_days == pytest.approx(50)
    assert item.reason == REASON_MISSION_NOT_FOUND


@pytest.mark.unit
@pytest.mark.fast
def test_a_non_mapping_run_snapshot_names_no_mission(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    (run_dir / "state.json").write_text("[1, 2]", encoding="utf-8")
    _set_age(run_dir, 60)
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert item.reason == REASON_MISSION_NOT_FOUND


@pytest.mark.unit
@pytest.mark.fast
def test_a_corrupt_mission_meta_reads_as_open(project: Path) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=None, age_days=60)
    (project / "kitty-specs" / DONE_SLUG / "meta.json").write_text("{corrupt", encoding="utf-8")
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert (item.reason, item.mission) == (REASON_MISSION_OPEN, DONE_SLUG)


@pytest.mark.unit
@pytest.mark.fast
def test_an_uncomputable_event_log_lock_reads_as_held(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", "{}\n")

    def _no_git(_anchor: Path) -> Path:
        raise OSError("git could not be invoked")

    monkeypatch.setattr(retention, "event_log_lock_path", _no_git)
    plan = scan_retention(project, RetentionLimits(), now=NOW)
    assert [(i.path, i.reason) for i in plan.items] == [(ops_index, REASON_LOCK_HELD)]


@pytest.mark.unit
@pytest.mark.fast
def test_a_candidate_of_an_unknown_surface_is_refused_at_apply(project: Path) -> None:
    target = _write(project / ".kittify" / "derived" / "x" / "lifecycle.json", "{}").parent
    rogue = retention.RetentionItem(
        surface="mystery_surface", kind=KIND_CACHE, path=target, mission=None, age_days=1.0, verdict="candidate", reason=REASON_REBUILDABLE
    )
    result = apply_retention(project, RetentionPlan(limits=RetentionLimits(), items=[rogue]))
    assert [f.item for f in result.failed] == [rogue]
    assert "mystery_surface" in result.failed[0].error
    assert target.is_dir()


@pytest.mark.unit
@pytest.mark.fast
def test_a_path_outside_the_project_serializes_as_given(tmp_path: Path) -> None:
    item = retention.RetentionItem(surface="s", kind=KIND_CACHE, path=Path("/elsewhere/x"), mission=None, age_days=1.234, verdict="kept", reason=REASON_LOCK_HELD)
    assert item.to_dict(tmp_path)["path"] == "/elsewhere/x"
    assert item.to_dict(tmp_path)["age_days"] == 1.23


# ---------------------------------------------------------------------------
# Review cycle 1 fixes: identity, index shape, symlinks, scan robustness
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.fast
def test_a_recorded_unknown_mission_id_never_falls_back_to_the_slug(project: Path) -> None:
    """FR-008: a run of a Mission on another branch whose slug collides with a local one is kept."""
    run_dir = _run(project, slug=DONE_SLUG, mission_id=UNKNOWN_ID, age_days=90)
    malformed = _run(project, slug=DONE_SLUG, mission_id=None, age_days=90)
    _write(malformed / "state.json", json.dumps({"mission_slug": DONE_SLUG, "mission_id": 123}))
    _set_age(malformed, 90)
    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    for kept in (run_dir, malformed):
        item = _by_path(plan.items, project)[_rel(kept, project)]
        assert (item.verdict, item.reason, item.mission) == ("kept", REASON_MISSION_NOT_FOUND, None)
    apply_retention(project, plan)
    assert run_dir.is_dir()
    assert malformed.is_dir()


@pytest.mark.unit
@pytest.mark.fast
def test_a_recorded_mission_id_resolves_by_id_not_by_slug(project: Path) -> None:
    run_dir = _run(project, slug=OPEN_SLUG, mission_id=DONE_ID, age_days=90)
    item = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)[_rel(run_dir, project)]
    assert (item.reason, item.mission) == (REASON_COMPLETED, DONE_SLUG)


@pytest.mark.unit
@pytest.mark.fast
def test_a_non_mapping_run_index_does_not_abort_apply(project: Path) -> None:
    paths = _full_fixture(project)
    index_path = run_index.feature_runs_path(project)
    index_path.write_text("[1, 2, 3]", encoding="utf-8")
    result = apply_retention(project, scan_retention(project, LIMITS_NO_KEEP, now=NOW))
    assert result.failed == []
    assert result.removed_index_entries == []
    assert not paths["done_run"].exists()
    assert not paths["derived"].exists()
    assert not paths["ops_index"].exists()
    assert index_path.read_text(encoding="utf-8") == "[1, 2, 3]"


def _outside_target(tmp_path_factory: pytest.TempPathFactory) -> Path:
    outside = tmp_path_factory.mktemp("outside")
    _write(outside / "state.json", json.dumps({"mission_slug": DONE_SLUG, "mission_id": DONE_ID}))
    _write(outside / "keep.txt", "precious")
    _write(outside / "lifecycle.json", "{}")
    _set_age(outside, 90)
    return outside


@pytest.mark.unit
@pytest.mark.fast
def test_symlinked_items_are_never_collected(project: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    outside = _outside_target(tmp_path_factory)
    outside_log = _write(outside / "log.events.jsonl", "{}\n")
    _set_age(outside_log, 90)
    run_link = run_index.runs_root(project) / "linked-run"
    run_link.parent.mkdir(parents=True, exist_ok=True)
    run_link.symlink_to(outside, target_is_directory=True)
    log_link = project / GLOSSARY_DIR / f"{DONE_ID}.events.jsonl"
    log_link.parent.mkdir(parents=True, exist_ok=True)
    log_link.symlink_to(outside_log)
    derived_link = project / ".kittify" / "derived" / DONE_SLUG
    derived_link.parent.mkdir(parents=True, exist_ok=True)
    derived_link.symlink_to(outside, target_is_directory=True)
    ops_link = project / "kitty-ops" / "ops-index.jsonl"
    ops_link.symlink_to(outside_log)
    before = sorted(p.name for p in outside.iterdir())

    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert plan.items == []
    apply_retention(project, plan)

    assert sorted(p.name for p in outside.iterdir()) == before
    assert not (outside / "state.json.lock").exists()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "precious"
    assert all(link.is_symlink() for link in (run_link, log_link, derived_link, ops_link))


@pytest.mark.unit
@pytest.mark.fast
def test_an_item_that_vanishes_mid_scan_is_skipped(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gone = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=90)
    kept = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=91)
    gone_log = _glossary_log(project, DONE_ID, 90)
    real_newest_mtime = retention._newest_mtime

    def _vanishing(path: Path) -> float:
        if path in (gone, gone_log):
            raise FileNotFoundError(path)
        return real_newest_mtime(path)

    monkeypatch.setattr(retention, "_newest_mtime", _vanishing)
    items = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)
    assert set(items) == {_rel(kept, project)}


@pytest.mark.unit
@pytest.mark.fast
def test_a_file_vanishing_inside_a_run_dir_skips_that_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=90)
    real_scandir = os.scandir

    def _scandir(path: str | os.PathLike[str]) -> object:
        if Path(path) == run_dir:
            raise FileNotFoundError(path)
        return real_scandir(path)

    with monkeypatch.context() as patch:
        patch.setattr(os, "scandir", _scandir)
        plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert plan.items == []


class _BrokenProbe:
    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path

    def __enter__(self) -> None:
        raise PermissionError(13, "lock file not accessible", str(self.lock_path))

    def __exit__(self, *_exc: object) -> None:
        return None


@pytest.mark.unit
@pytest.mark.fast
def test_a_lock_probe_oserror_reads_as_held(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", "{}\n")
    done_log = _glossary_log(project, DONE_ID, 90)
    for log in (ops_index, done_log):
        _write(event_log_lock_path(log), "")

    def _broken(lock_path: Path, **_kwargs: object) -> _BrokenProbe:
        return _BrokenProbe(lock_path)

    monkeypatch.setattr(retention, "machine_file_lock", _broken)
    items = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)
    assert {path: item.reason for path, item in items.items()} == {
        _rel(ops_index, project): REASON_LOCK_HELD,
        _rel(done_log, project): REASON_LOCK_HELD,
    }


@pytest.mark.unit
@pytest.mark.fast
def test_a_failed_run_tree_removal_is_reported_with_its_path(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _full_fixture(project)
    real_remove_tree = retention._remove_tree

    def _flaky_remove_tree(path: Path) -> None:
        if path == paths["done_run"]:
            raise PermissionError(13, "open handle", str(path))
        real_remove_tree(path)

    monkeypatch.setattr(retention, "_remove_tree", _flaky_remove_tree)
    result = apply_retention(project, scan_retention(project, LIMITS_NO_KEEP, now=NOW))

    assert [f.item.path for f in result.failed] == [paths["done_run"]]
    assert str(paths["done_run"]) in result.failed[0].error
    assert result.to_dict(project)["failed"][0]["path"] == _rel(paths["done_run"], project)
    assert paths["done_run"].is_dir()
    # ADR D-3 trade-off: the index entry is dropped first, so it never names a run that is gone.
    assert f"{DONE_SLUG}:software-dev" not in _read_index(project)
    assert not paths["derived"].exists()


# ---------------------------------------------------------------------------
# Review cycle 2 fix: a symlinked lock file reads as held, never crashes
# ---------------------------------------------------------------------------


def _symlink_lock(lock_path: Path, outside: Path, *, dangling: bool) -> Path:
    """Plant *lock_path* as a symlink to a file outside the project (existing or dangling)."""
    target = outside / f"{lock_path.name}.target"
    if not dangling:
        _write(target, "")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.symlink_to(target)
    return target


def _assert_target_untouched(target: Path, *, dangling: bool) -> None:
    if dangling:
        assert not target.exists()
    else:
        assert target.read_text(encoding="utf-8") == ""


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling"])
def test_a_symlinked_run_lock_reads_as_held_in_preview(project: Path, tmp_path_factory: pytest.TempPathFactory, dangling: bool) -> None:
    linked = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    other = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=90)
    target = _symlink_lock(linked / "state.json.lock", tmp_path_factory.mktemp("outside"), dangling=dangling)

    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    items = _by_path(plan.items, project)
    assert (items[_rel(linked, project)].verdict, items[_rel(linked, project)].reason) == ("kept", REASON_LOCK_HELD)
    assert items[_rel(other, project)].reason == REASON_COMPLETED

    result = apply_retention(project, plan)
    assert [i.path for i in result.deleted] == [other]
    assert result.failed == []
    assert linked.is_dir()
    assert (linked / "state.json.lock").is_symlink()
    _assert_target_untouched(target, dangling=dangling)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling"])
def test_a_symlinked_event_log_lock_reads_as_held_in_preview(project: Path, tmp_path_factory: pytest.TempPathFactory, dangling: bool) -> None:
    outside = tmp_path_factory.mktemp("outside")
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", '{"invocation_id": "x"}\n')
    done_log = _glossary_log(project, DONE_ID, 60)
    targets = [_symlink_lock(event_log_lock_path(log), outside, dangling=dangling) for log in (ops_index, done_log)]

    items = _by_path(scan_retention(project, LIMITS_NO_KEEP, now=NOW).items, project)
    for log in (ops_index, done_log):
        assert (items[_rel(log, project)].verdict, items[_rel(log, project)].reason) == ("kept", REASON_LOCK_HELD)
    for target in targets:
        _assert_target_untouched(target, dangling=dangling)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling"])
def test_a_run_lock_symlinked_after_the_preview_is_kept_at_apply_and_the_loop_continues(
    project: Path, tmp_path_factory: pytest.TempPathFactory, dangling: bool
) -> None:
    a = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=60)
    b = _run(project, slug=DONE_SLUG, mission_id=DONE_ID, age_days=90)
    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert [i.path for i in plan.candidates] == [a, b]
    target = _symlink_lock(a / "state.json.lock", tmp_path_factory.mktemp("outside"), dangling=dangling)

    result = apply_retention(project, plan)

    assert [(i.path, i.verdict, i.reason) for i in result.kept_at_apply] == [(a, "kept", REASON_LOCK_HELD)]
    assert [i.path for i in result.deleted] == [b]
    assert result.failed == []
    assert a.is_dir()
    assert not b.exists()
    _assert_target_untouched(target, dangling=dangling)


@pytest.mark.unit
@pytest.mark.fast
@pytest.mark.parametrize("dangling", [False, True], ids=["existing-target", "dangling"])
def test_an_event_log_lock_symlinked_after_the_preview_is_kept_at_apply_and_the_loop_continues(
    project: Path, tmp_path_factory: pytest.TempPathFactory, dangling: bool
) -> None:
    outside = tmp_path_factory.mktemp("outside")
    done_log = _glossary_log(project, DONE_ID, 60)
    derived = _write(project / ".kittify" / "derived" / DONE_SLUG / "lifecycle.json", "{}").parent
    ops_index = _write(project / "kitty-ops" / "ops-index.jsonl", '{"invocation_id": "x"}\n')
    plan = scan_retention(project, LIMITS_NO_KEEP, now=NOW)
    assert [i.path for i in plan.candidates] == [done_log, derived, ops_index]
    targets = [_symlink_lock(event_log_lock_path(log), outside, dangling=dangling) for log in (done_log, ops_index)]

    result = apply_retention(project, plan)

    assert [(i.path, i.reason) for i in result.kept_at_apply] == [
        (done_log, REASON_LOCK_HELD),
        (ops_index, REASON_LOCK_HELD),
    ]
    assert [i.path for i in result.deleted] == [derived]
    assert result.failed == []
    assert done_log.exists()
    assert ops_index.exists()
    for target in targets:
        _assert_target_untouched(target, dangling=dangling)
