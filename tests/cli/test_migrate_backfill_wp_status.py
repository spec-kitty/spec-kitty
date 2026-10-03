"""Acceptance tests for ``spec-kitty migrate backfill-wp-status`` (#5579, WP02).

The CLI is the operator surface over WP01's repair (``apply_wp_status_backfill``):
it seeds the lane events a Mission's ``tasks/WP*.md`` files lack so the reduced
snapshot counts every WP. These tests drive the real typer app through
``CliRunner`` over a throw-away repo under ``tmp_path`` (never the checkout the
tests live in).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import migrate_cmd
from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.status.reducer import materialize_snapshot

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"
_CMD = "backfill-wp-status"
_ID_ONE = "01JMISSIONULID0000000000C1"
_ID_TWO = "01KOTHERMISSIONULID00000C2"
_SLUG_ONE = "alpha-mission-01JMISSI"
_SLUG_TWO = "beta-mission-01KOTHER"
_THREE = ("WP01", "WP02", "WP03")
_SEED_AT = "2026-01-02T03:04:05+00:00"
_REAL_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Run inside ``tmp_path`` and never let the real repo be located."""
    assert not tmp_path.resolve().is_relative_to(_REAL_REPO_ROOT)
    scratch = tmp_path / "cwd"
    scratch.mkdir()
    monkeypatch.chdir(scratch)
    yield


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    (tasks_dir / f"{wp_id}-demo.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Demo {wp_id}\nexecution_mode: code_change\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )


def _planned_row(slug: str, mission_id: str, wp_id: str, event_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "mission_slug": slug,
        "mission_id": mission_id,
        "wp_id": wp_id,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": _SEED_AT,
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }


def _mission(
    repo: Path,
    slug: str,
    mission_id: str,
    *,
    wp_ids: tuple[str, ...] = _THREE,
    seeded: tuple[str, ...] = ("WP01",),
    meta_extra: dict[str, Any] | None = None,
) -> Path:
    """Create ``kitty-specs/<slug>`` with *wp_ids* files and ``planned`` events for *seeded*."""
    feature_dir = repo / "kitty-specs" / slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    meta: dict[str, Any] = {"mission_id": mission_id, "mission_slug": slug, "mission_type": "software-dev"}
    meta.update(meta_extra or {})
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for wp_id in wp_ids:
        _write_wp_file(tasks_dir, wp_id)
    if seeded:
        rows = [_planned_row(slug, mission_id, wp_id, f"01AAAAAAAAAAAAAAAAAAAAAAB{index}") for index, wp_id in enumerate(seeded, start=1)]
        (feature_dir / "status.events.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
    return feature_dir


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".kittify").mkdir(parents=True)
    return root


def _invoke(repo_root: Path, *args: str) -> Any:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_LOCATE, lambda *_a, **_k: repo_root)
        return runner.invoke(migrate_app, [_CMD, *args])


def _json(result: Any) -> dict[str, Any]:
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def _tree_bytes(root: Path) -> dict[str, bytes]:
    """Bytes of every file under *root*, so a stray dry-run write ANYWHERE is caught.

    Only the per-Mission status lock is excluded: the writer takes it even on a
    dry-run, before planning. It is an empty runtime file, not Mission state (in a
    real checkout it lives under the git common dir, outside the working tree and
    version control; in this non-git fixture it degrades to
    ``<root>/.kittify/spec-kitty-locks/``).
    """
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file() and not p.name.endswith(".status.lock")}


def _write_manifest(path: Path, missions: dict[str, Any] | None = None, *, raw: str | None = None) -> Path:
    if raw is None:
        lines = ["missions:"]
        for slug, entry in (missions or {}).items():
            lines.append(f"  {slug}:")
            reason = entry.get("reason") if isinstance(entry, dict) else None
            if reason is not None:
                lines.append(f"    reason: {json.dumps(reason)}")
        raw = "\n".join(lines) + "\n"
    path.write_text(raw, encoding="utf-8")
    return path


def _lane_of(feature_dir: Path, wp_id: str) -> str:
    return str(materialize_snapshot(feature_dir).work_packages[wp_id]["lane"])


# ---------------------------------------------------------------------------
# registration / help
# ---------------------------------------------------------------------------


def test_command_is_registered_with_the_four_canonical_options() -> None:
    result = runner.invoke(migrate_app, [_CMD, "--help"])

    assert result.exit_code == 0, result.output
    for flag in ("--mission", "--dry-run", "--evidence-manifest", "--json"):
        assert flag in result.output
    assert "--feature" not in result.output


def test_help_states_the_manifest_must_be_complete_on_the_first_live_run() -> None:
    result = runner.invoke(migrate_app, [_CMD, "--help"])
    flat = " ".join(result.output.split())

    assert "complete on the first live run" in flat
    assert "spec-kitty migrate backfill-wp-status" in flat


# ---------------------------------------------------------------------------
# dry-run / live / idempotence
# ---------------------------------------------------------------------------


def test_dry_run_reports_the_plan_and_writes_nothing(repo: Path) -> None:
    feature_dir = _mission(repo, _SLUG_ONE, _ID_ONE)
    _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    before = _tree_bytes(repo)

    result = _invoke(repo, "--dry-run", "--json")

    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["dry_run"] is True
    assert payload["summary"]["events_seeded"] == 0
    assert payload["summary"]["events_would_seed"] == 2 + 3
    assert _tree_bytes(repo) == before
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01"}


def test_live_run_seeds_every_missing_wp_and_a_second_run_appends_nothing(repo: Path) -> None:
    one = _mission(repo, _SLUG_ONE, _ID_ONE)
    two = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())

    first = _invoke(repo, "--json")

    assert first.exit_code == 0, first.output
    assert _json(first)["summary"]["events_seeded"] == 5
    assert set(materialize_snapshot(one).work_packages) == set(_THREE)
    assert set(materialize_snapshot(two).work_packages) == set(_THREE)
    assert (two / "status.events.jsonl").is_file()
    after_first = _tree_bytes(repo)

    second = _invoke(repo, "--json")

    assert second.exit_code == 0, second.output
    summary = _json(second)["summary"]
    assert summary["events_seeded"] == 0 and summary["events_would_seed"] == 0
    assert _tree_bytes(repo) == after_first


def test_mission_option_scopes_the_run_and_leaves_other_missions_untouched(repo: Path) -> None:
    one = _mission(repo, _SLUG_ONE, _ID_ONE)
    two = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())

    result = _invoke(repo, "--mission", _SLUG_ONE, "--json")

    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["summary"]["scanned"] == 1
    assert [row["slug"] for row in payload["missions"]] == [_SLUG_ONE]
    assert set(materialize_snapshot(one).work_packages) == set(_THREE)
    assert not (two / "status.events.jsonl").exists()


def test_mission_option_accepts_a_mid8_handle(repo: Path) -> None:
    one = _mission(repo, _SLUG_ONE, _ID_ONE)

    result = _invoke(repo, "--mission", _ID_ONE[:8], "--json")

    assert result.exit_code == 0, result.output
    assert set(materialize_snapshot(one).work_packages) == set(_THREE)


@pytest.mark.parametrize("json_mode", [False, True])
def test_unknown_mission_handle_exits_1_and_writes_nothing(repo: Path, json_mode: bool) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)
    before = _tree_bytes(repo)

    result = _invoke(repo, "--mission", "no-such-mission", *(["--json"] if json_mode else []))

    assert result.exit_code == 1, result.output
    assert _tree_bytes(repo) == before
    if json_mode:
        assert _json(result)["success"] is False


# ---------------------------------------------------------------------------
# selector branches (review R2-R4)
# ---------------------------------------------------------------------------


def test_ambiguous_mid8_handle_is_a_structured_error_with_no_silent_fallback(repo: Path) -> None:
    _mission(repo, "gamma-mission", "01JSAMEMXXXXXXXXXXXXXXXXA1")
    _mission(repo, "delta-mission", "01JSAMEMXXXXXXXXXXXXXXXXB2", seeded=())
    before = _tree_bytes(repo)

    human = _invoke(repo, "--mission", "01JSAMEM")
    machine = _invoke(repo, "--mission", "01JSAMEM", "--json")

    assert human.exit_code == 1 and machine.exit_code == 1
    payload = _json(machine)
    assert payload["success"] is False and payload["error_code"] == "MISSION_AMBIGUOUS"
    assert "gamma-mission" in payload["error"] and "delta-mission" in payload["error"]
    assert _tree_bytes(repo) == before


def test_legacy_mission_without_mission_id_resolves_by_exact_directory_name(repo: Path) -> None:
    """The identity resolver cannot index a Mission with no ``mission_id``; its exact dir name still works."""
    legacy = _mission(repo, "legacy-mission", _ID_ONE, meta_extra={"mission_id": None})
    other = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())

    result = _invoke(repo, "--mission", "legacy-mission", "--json")

    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert [row["slug"] for row in payload["missions"]] == ["legacy-mission"]
    assert set(materialize_snapshot(legacy).work_packages) == set(_THREE)
    assert not (other / "status.events.jsonl").exists()


@pytest.mark.parametrize("near_miss", ["legacy-missio", "Legacy-Mission", "legacy-mission/"])
def test_near_miss_of_a_legacy_directory_name_is_not_found(repo: Path, near_miss: str) -> None:
    _mission(repo, "legacy-mission", _ID_ONE, meta_extra={"mission_id": None})
    before = _tree_bytes(repo)

    result = _invoke(repo, "--mission", near_miss, "--json")

    assert result.exit_code == 1, result.output
    assert _json(result)["error_code"] == "MISSION_NOT_FOUND"
    assert _tree_bytes(repo) == before


def test_selector_escaping_kitty_specs_is_rejected_with_a_structured_error(repo: Path, tmp_path: Path) -> None:
    """A Mission dir symlinked outside ``kitty-specs/`` resolves, but the writer's containment check refuses it."""
    outside = tmp_path / "outside" / "kitty-specs" / "evil"
    _mission(tmp_path / "outside", "evil", _ID_ONE)
    (repo / "kitty-specs").mkdir()
    (repo / "kitty-specs" / "evil").symlink_to(outside, target_is_directory=True)
    before = _tree_bytes(tmp_path / "outside")

    human = _invoke(repo, "--mission", "evil")
    machine = _invoke(repo, "--mission", "evil", "--json")

    assert human.exit_code == 1 and machine.exit_code == 1
    payload = _json(machine)
    assert payload["success"] is False and payload["error_code"] == "MISSION_SELECTOR_REJECTED"
    assert "outside kitty-specs" in payload["error"]
    assert _tree_bytes(tmp_path / "outside") == before


@pytest.mark.parametrize("json_mode", [False, True])
def test_outside_a_project_exits_1(json_mode: bool) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_LOCATE, lambda *_a, **_k: None)
        result = runner.invoke(migrate_app, [_CMD, *(["--json"] if json_mode else [])])

    assert result.exit_code == 1
    if json_mode:
        assert _json(result)["error_code"] == "NO_PROJECT_ROOT"


# ---------------------------------------------------------------------------
# evidence manifest (T008)
# ---------------------------------------------------------------------------


def test_manifest_marks_a_mission_finished_and_records_the_reason(repo: Path, tmp_path: Path) -> None:
    one = _mission(repo, _SLUG_ONE, _ID_ONE)
    two = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    manifest = _write_manifest(tmp_path / "evidence.yaml", {_SLUG_TWO: {"reason": "PR #4242 merged 2026-09-01; dossier landed"}})

    result = _invoke(repo, "--evidence-manifest", str(manifest), "--json")

    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["summary"]["finished_missions"] == 1
    assert all(_lane_of(two, wp) == "done" for wp in _THREE)
    assert _lane_of(one, "WP02") == "planned"
    row = next(r for r in payload["missions"] if r["slug"] == _SLUG_TWO)
    assert "PR #4242 merged 2026-09-01" in row["terminal_reason"]
    assert payload["manifest"]["entries"] == 1 and payload["manifest"]["unused"] == []


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("missions:\n  {slug}:\n    reason: ''\n", id="empty-reason"),
        pytest.param("missions:\n  {slug}:\n    reason: '   '\n", id="blank-reason"),
        pytest.param("missions:\n  {slug}: {}\n", id="missing-reason"),
        pytest.param("missions:\n  {slug}:\n    reason: 7\n", id="non-string-reason"),
        pytest.param("missions:\n  {slug}:\n    reason: ok\n    extra: nope\n", id="unknown-entry-key"),
        pytest.param("missions:\n  {slug}: just a string\n", id="entry-not-a-mapping"),
        pytest.param("missions:\n  no-such-mission-01ZZZZZZ:\n    reason: because\n", id="slug-does-not-resolve"),
        pytest.param("missions:\n  42:\n    reason: because\n", id="slug-key-not-a-string"),
        pytest.param("missions: []\n", id="missions-not-a-mapping"),
        pytest.param("- not\n- a\n- mapping\n", id="top-level-not-a-mapping"),
        pytest.param("other: {}\n", id="unknown-top-level-key"),
        pytest.param("missions: {unclosed\n", id="invalid-yaml"),
        pytest.param("", id="empty-file"),
    ],
)
@pytest.mark.parametrize("json_mode", [False, True])
def test_invalid_manifest_fails_closed_before_anything_is_written(repo: Path, tmp_path: Path, raw: str, json_mode: bool) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)
    _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    manifest = _write_manifest(tmp_path / "evidence.yaml", raw=raw.replace("{slug}", _SLUG_TWO))
    before = _tree_bytes(repo)

    result = _invoke(repo, "--evidence-manifest", str(manifest), *(["--json"] if json_mode else []))

    assert result.exit_code == 1, result.output
    assert _tree_bytes(repo) == before
    if json_mode:
        payload = _json(result)
        assert payload["success"] is False and payload["error"]


def test_missing_manifest_file_fails_closed(repo: Path, tmp_path: Path) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)
    before = _tree_bytes(repo)

    result = _invoke(repo, "--evidence-manifest", str(tmp_path / "absent.yaml"))

    assert result.exit_code == 1, result.output
    assert _tree_bytes(repo) == before


def test_manifest_slug_is_validated_even_when_scoped_to_another_mission(repo: Path, tmp_path: Path) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)
    manifest = _write_manifest(tmp_path / "evidence.yaml", {"typo-mission": {"reason": "PR #1 merged"}})
    before = _tree_bytes(repo)

    result = _invoke(repo, "--mission", _SLUG_ONE, "--evidence-manifest", str(manifest))

    assert result.exit_code == 1, result.output
    assert _tree_bytes(repo) == before


def test_manifest_entry_for_a_mission_with_nothing_to_seed_is_warned_about(repo: Path, tmp_path: Path) -> None:
    """Evidence supplied on a LATER run is a no-op (WPs already seeded ``planned``); say so."""
    two = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    first = _invoke(repo, "--json")
    assert first.exit_code == 0, first.output
    manifest = _write_manifest(tmp_path / "evidence.yaml", {_SLUG_TWO: {"reason": "PR #7 merged"}})

    human = _invoke(repo, "--evidence-manifest", str(manifest))
    machine = _invoke(repo, "--evidence-manifest", str(manifest), "--json")

    assert human.exit_code == 0 and machine.exit_code == 0
    flat = " ".join(human.output.split())
    assert "WARNING" in flat and _SLUG_TWO in flat and "complete on the first live run" in flat
    assert _json(machine)["manifest"]["unused"] == [{"mission": _SLUG_TWO, "reason": "nothing to seed"}]
    assert all(_lane_of(two, wp) == "planned" for wp in _THREE)


def test_manifest_entry_outside_the_mission_scope_is_reported_unused(repo: Path, tmp_path: Path) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)
    _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    manifest = _write_manifest(tmp_path / "evidence.yaml", {_SLUG_TWO: {"reason": "PR #7 merged"}})

    result = _invoke(repo, "--mission", _SLUG_ONE, "--evidence-manifest", str(manifest), "--json")

    assert result.exit_code == 0, result.output
    assert _json(result)["manifest"]["unused"] == [{"mission": _SLUG_TWO, "reason": "not in scope"}]


# ---------------------------------------------------------------------------
# summary / JSON contract / exit codes (T009)
# ---------------------------------------------------------------------------


def test_json_payload_shape_is_stable(repo: Path) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)

    payload = _json(_invoke(repo, "--json"))

    assert set(payload) == {"dry_run", "result", "mission", "summary", "manifest", "missions"}
    assert payload["result"] == "success" and payload["mission"] is None
    assert set(payload["summary"]) == {
        "scanned",
        "missions_seeded",
        "missions_would_seed",
        "events_seeded",
        "events_would_seed",
        "finished_missions",
        "snapshot_only_missions",
        "malformed_missions",
        "skipped",
        "errors",
    }
    assert set(payload["manifest"]) == {"path", "entries", "unused"}
    assert set(payload["missions"][0]) == {
        "slug",
        "seeded",
        "would_seed",
        "files_only",
        "snapshot_only",
        "malformed",
        "terminal_reason",
        "status_json_refreshed",
        "skip_reason",
        "error",
    }
    assert payload["missions"][0]["files_only"] == ["WP02", "WP03"]


def test_human_summary_names_every_counter(repo: Path) -> None:
    _mission(repo, _SLUG_ONE, _ID_ONE)

    out = " ".join(_invoke(repo).output.split())

    for label in ("Scanned", "Seeded", "Would seed", "Finished", "Snapshot-only", "Errors"):
        assert label in out


def test_snapshot_only_wps_are_reported_but_never_fail_the_run(repo: Path) -> None:
    feature_dir = _mission(repo, _SLUG_ONE, _ID_ONE, wp_ids=("WP01",), seeded=("WP01", "WP09"))

    result = _invoke(repo, "--json")

    assert result.exit_code == 0, result.output
    payload = _json(result)
    assert payload["summary"]["snapshot_only_missions"] == 1
    assert payload["missions"][0]["snapshot_only"] == ["WP09"]
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01", "WP09"}


def test_human_summary_lists_snapshot_only_and_malformed_files(repo: Path) -> None:
    feature_dir = _mission(repo, _SLUG_ONE, _ID_ONE, wp_ids=("WP01",), seeded=("WP01", "WP09"))
    (feature_dir / "tasks" / "WP02-broken.md").write_text("no frontmatter here\n", encoding="utf-8")

    result = _invoke(repo)

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "snapshot-only" in flat and "WP09" in flat
    assert "malformed" in flat and "WP02-broken.md" in flat


def test_per_mission_error_exits_1_but_other_missions_are_still_repaired(repo: Path) -> None:
    broken = _mission(repo, _SLUG_ONE, _ID_ONE)
    good = _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    (broken / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    result = _invoke(repo, "--json")

    assert result.exit_code == 1, result.output
    payload = _json(result)
    assert payload["result"] == "errors_present"
    assert payload["summary"]["errors"] == 1
    assert next(r for r in payload["missions"] if r["slug"] == _SLUG_ONE)["error"]
    assert set(materialize_snapshot(good).work_packages) == set(_THREE)


def test_dry_run_with_a_broken_mission_still_exits_1(repo: Path) -> None:
    broken = _mission(repo, _SLUG_ONE, _ID_ONE)
    (broken / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    assert _invoke(repo, "--dry-run").exit_code == 1


def test_group_level_dry_run_is_forwarded_to_the_subcommand(repo: Path) -> None:
    _mission(repo, _SLUG_TWO, _ID_TWO, seeded=())
    before = _tree_bytes(repo)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(migrate_cmd, "locate_project_root", lambda *_a, **_k: repo)
        result = runner.invoke(migrate_app, ["--dry-run", _CMD, "--json"])

    assert result.exit_code == 0, result.output
    assert _json(result)["dry_run"] is True
    assert _tree_bytes(repo) == before
