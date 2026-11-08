"""ATDD acceptance tests for ``spec-kitty migrate backfill-runtime-state`` (WP01 / US1).

Drives the real command via ``typer.testing.CliRunner`` over real fixture corpora:

* US1.1 — ``--dry-run`` reports would-seed counts, writes 0 events / 0 flips, exit 0;
* US1.2 — a real run flips ``status_phase="1"`` only for passing missions, exit 0, and
  the reduced snapshot matches the OLD reader (the library verify, re-run here);
* US1.3 — a REAL fault-injected corrupt deterministic seed records that mission's failure, exits
  non-zero, names the mismatch, and leaves ``status_phase`` untouched (per-mission
  best-effort: sibling missions still flip);
* US1.4 — a re-run seeds nothing and flips nothing (idempotent), exit 0.

No verify is mocked — every fault is a real divergent seed exercised through the real
library verify over a real event log.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.migration.backfill_runtime_state import backfill_runtime_state
from tests.unit.migration._backfill_fixture import build_mission, corrupt_seed_value

pytestmark = [pytest.mark.integration]

runner = CliRunner()

_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"


def _invoke(repo_root: Path, args: list[str]) -> Result:
    with patch(_LOCATE, return_value=repo_root):
        return runner.invoke(migrate_app, ["backfill-runtime-state", *args])


def _inject_conflicting_seed(feature_dir: Path) -> None:
    """Corrupt the canonical assignee seed payload under its deterministic ID."""
    corrupt_seed_value(
        feature_dir,
        field_name="assignee",
        slot_name="assignee",
        value="EVIL-DIVERGENT",
    )


def test_command_registered_in_help() -> None:
    result = runner.invoke(migrate_app, ["--help"])
    assert result.exit_code == 0
    assert "backfill-runtime-state" in result.stdout


def test_missing_project_root_errors() -> None:
    with patch(_LOCATE, return_value=None):
        result = runner.invoke(migrate_app, ["backfill-runtime-state"])
    assert result.exit_code == 1


# --- US1.1: dry-run reports counts, writes nothing ---------------------------


def test_dry_run_reports_counts_and_writes_nothing(tmp_path: Path) -> None:
    # Two healthy legacy missions — a dry-run must NOT frame either as "failed"
    # just because verify is not-ok pre-seed.
    fd_a = build_mission(tmp_path, slug="alpha")
    fd_b = build_mission(tmp_path, slug="beta")
    events_before = (fd_a / "status.events.jsonl").read_bytes()
    meta_before = (fd_a / "meta.json").read_bytes()

    result = _invoke(tmp_path, ["--dry-run", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"]["seeded"] > 0
    assert payload["summary"]["would_seed"] == 2
    assert payload["summary"]["flipped"] == 0
    # A healthy legacy corpus reports 0 "failed" in dry-run (verify-not-ok pre-seed
    # is "would seed (verify pending)", not a failure) and emits no mismatch wall.
    assert payload["summary"]["failed"] == 0
    assert all(r["failed"] is False for r in payload["results"])
    assert all(r["mismatches"] == [] for r in payload["results"])
    # Zero events, zero flips: byte-stable.
    assert (fd_a / "status.events.jsonl").read_bytes() == events_before
    assert (fd_a / "meta.json").read_bytes() == meta_before
    assert "status_phase" not in json.loads((fd_b / "meta.json").read_text())


# --- US1.2: real run flips only passing missions, matches OLD reader ---------


def test_real_run_flips_and_matches_old_reader(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)

    result = _invoke(tmp_path, ["--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["flipped"] == 1
    assert payload["summary"]["failed"] == 0
    assert payload["results"][0]["verify_ok"] is True
    assert json.loads((feature_dir / "meta.json").read_text())["status_phase"] == "1"


# --- US1.3: fault injection -> best-effort failure, untouched, exit non-zero --


def test_fault_injected_conflict_exits_nonzero_and_leaves_phase_untouched(tmp_path: Path) -> None:
    bad = build_mission(tmp_path, slug="bad-mission")
    good = build_mission(tmp_path, slug="good-mission")
    backfill_runtime_state(bad)  # legit seeds first
    _inject_conflicting_seed(bad)  # REAL corruption
    bad_meta_before = (bad / "meta.json").read_bytes()

    result = _invoke(tmp_path, ["--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["failed"] == 1
    by_slug = {r["slug"]: r for r in payload["results"]}
    assert by_slug["bad-mission"]["verify_ok"] is False
    assert by_slug["bad-mission"]["mismatches"]
    # status_phase untouched for the failed mission...
    assert (bad / "meta.json").read_bytes() == bad_meta_before
    assert "status_phase" not in json.loads(bad_meta_before)
    # ...but the sibling still flipped (per-mission best-effort).
    assert by_slug["good-mission"]["flipped"] is True
    assert json.loads((good / "meta.json").read_text())["status_phase"] == "1"


# --- US1.4: idempotent re-run --------------------------------------------------


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    first = _invoke(tmp_path, [])
    assert first.exit_code == 0
    events_after = (feature_dir / "status.events.jsonl").read_bytes()
    meta_after = (feature_dir / "meta.json").read_bytes()

    result = _invoke(tmp_path, ["--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["seeded"] == 0
    assert (feature_dir / "status.events.jsonl").read_bytes() == events_after
    assert (feature_dir / "meta.json").read_bytes() == meta_after


# --- #3212: a mission it flips must be REPORTED as flipped -------------------


def _build_no_seed_state_mission(tmp_path: Path, *, slug: str = "no-state") -> Path:
    """Event-log evidence, zero seedable legacy frontmatter state (#3212).

    The exact corpus shape from the issue: the mission HAS runtime evidence
    (real transitions in ``status.events.jsonl``) but no legacy frontmatter /
    checkbox state to seed, so the run seeds 0 events and still flips — which
    the summary used to report as ``Flipped: 0 / Skipped (already migrated): 1``.
    """
    return build_mission(
        tmp_path,
        slug=slug,
        with_claim=False,
        with_review=False,
        with_history=False,
        assignee="",
        tracker_refs=(),
        with_subtasks=False,
    )


def test_no_seed_state_mission_summary_reports_it_flipped(tmp_path: Path) -> None:
    fd = _build_no_seed_state_mission(tmp_path)

    result = _invoke(tmp_path, [])

    assert result.exit_code == 0
    assert re.search(r"Flipped\s*:\s*1\b", result.stdout), result.stdout
    assert not re.search(r"Skipped \(already migrated\)\s*:\s*[1-9]", result.stdout)
    assert json.loads((fd / "meta.json").read_text())["status_phase"] == "1"


def test_summary_reports_already_migrated_only_when_nothing_was_written(tmp_path: Path) -> None:
    _build_no_seed_state_mission(tmp_path)
    assert _invoke(tmp_path, []).exit_code == 0  # the flip

    rerun = _invoke(tmp_path, [])

    assert rerun.exit_code == 0
    assert re.search(r"Flipped\s*:\s*0\b", rerun.stdout), rerun.stdout
    assert re.search(r"Skipped \(already migrated\)\s*:\s*1\b", rerun.stdout)


def test_dry_run_summary_reports_would_flip(tmp_path: Path) -> None:
    fd = _build_no_seed_state_mission(tmp_path)

    result = _invoke(tmp_path, ["--dry-run"])

    assert result.exit_code == 0
    assert re.search(r"Would flip\s*:\s*1\b", result.stdout), result.stdout
    # A pending flip is no longer previewed as "already migrated".
    assert not re.search(r"Skipped \(already migrated\)\s*:\s*[1-9]", result.stdout)
    assert "status_phase" not in json.loads((fd / "meta.json").read_text())


def test_dry_run_over_migrated_corpus_previews_no_flip(tmp_path: Path) -> None:
    _build_no_seed_state_mission(tmp_path)
    assert _invoke(tmp_path, []).exit_code == 0

    result = _invoke(tmp_path, ["--dry-run"])

    assert result.exit_code == 0
    assert re.search(r"Would flip\s*:\s*0\b", result.stdout), result.stdout
    assert re.search(r"Skipped \(already migrated\)\s*:\s*1\b", result.stdout)


# --- #4044: dry-run "Skipped (already migrated)" must not hide a would-fail mission ---


def _inject_phantom_wp_row(feature_dir: Path) -> None:
    """Hand-inject an annotation seed row for a WP with no legacy file (#4044).

    The corrupt-input shape the fail-closed verify exists to catch: the reduced
    snapshot carries runtime state (``assignee``) for ``WP99``, but no
    ``tasks/WP99*.md`` row exists — a phantom / injected entry. A live run
    FAILS such a mission (verify not ok); a dry-run used to launder it into
    "Skipped (already migrated)" because it would neither flip nor seed.
    """
    events_path = feature_dir / "status.events.jsonl"
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    rows.append(
        {
            "event_id": "01BBBBBBBBBBBBBBBBBBBBBBB9",
            "kind": "annotation",
            "wp_id": "WP99",
            "at": "2026-01-02T05:00:00+00:00",
            "actor": "migration",
            "delta": {"assignee": "ghost"},
        }
    )
    events_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_dry_run_does_not_label_would_fail_mission_already_migrated(tmp_path: Path) -> None:
    fd = _build_no_seed_state_mission(tmp_path, slug="phantom")
    _inject_phantom_wp_row(fd)

    result = _invoke(tmp_path, ["--dry-run"])

    assert result.exit_code == 0
    # The phantom fails verify, so nothing here would flip...
    assert re.search(r"Would flip\s*:\s*0\b", result.stdout), result.stdout
    # ...and it is NOT already migrated — the label must not claim it is. A
    # live run over the same corpus reports this mission as Failed (#4044).
    assert re.search(r"Skipped \(already migrated\)\s*:\s*0\b", result.stdout), result.stdout
    assert "status_phase" not in json.loads((fd / "meta.json").read_text())

    # Contrast: the LIVE run fails loudly on the same corrupt input — the
    # dry-run summary must not have framed it as benignly skipped.
    live = _invoke(tmp_path, [])
    assert live.exit_code == 1
    assert re.search(r"Failed\s*:\s*1\b", live.stdout), live.stdout
    assert "phantom" in live.stdout
    assert "WP99: snapshot carries runtime state but no legacy WP row exists" in live.stdout


def test_json_payload_distinguishes_flipped_from_already_migrated(tmp_path: Path) -> None:
    _build_no_seed_state_mission(tmp_path)

    first = json.loads(_invoke(tmp_path, ["--json"]).stdout)
    assert first["summary"]["flipped"] == 1
    assert first["summary"]["already_migrated"] == 0
    assert first["results"][0]["flipped"] is True
    assert first["results"][0]["already_migrated"] is False
    assert first["results"][0]["seeded_count"] == 0  # flipped with zero seeds

    rerun = json.loads(_invoke(tmp_path, ["--json"]).stdout)
    assert rerun["summary"]["flipped"] == 0
    assert rerun["summary"]["already_migrated"] == 1
    assert rerun["results"][0]["flipped"] is False
    assert rerun["results"][0]["already_migrated"] is True
    assert rerun["results"][0]["verify_ok"] is True  # the raw verdict stays

    dry = json.loads(_invoke(tmp_path, ["--dry-run", "--json"]).stdout)
    assert dry["summary"]["would_flip"] == 0  # nothing left for a live run to write
    assert dry["summary"]["already_migrated"] == 1


# --- scoping + INV-5 -----------------------------------------------------------


def test_single_mission_scope_flips_only_that_mission(tmp_path: Path) -> None:
    target = build_mission(tmp_path, slug="scoped", mission_id="01SCOPEDMISSION00000000AAA")
    other = build_mission(tmp_path, slug="untouched", mission_id="01UNTOUCHEDMISSION0000BBBB")

    result = _invoke(tmp_path, ["--mission", "scoped", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [r["slug"] for r in payload["results"]] == ["scoped"]
    assert json.loads((target / "meta.json").read_text())["status_phase"] == "1"
    assert "status_phase" not in json.loads((other / "meta.json").read_text())


def test_mission_handle_resolves_by_mid8_and_full_ulid(tmp_path: Path) -> None:
    """--mission accepts mission_id / mid8 / slug via the canonical resolver (T002)."""
    mission_id = "01JQ8T5N0X6RZV9K2WYB3CD4EF"
    feature_dir = build_mission(tmp_path, slug="042-demo", mission_id=mission_id)
    mid8 = mission_id[:8]

    for handle in (mission_id, mid8, "042-demo"):
        result = _invoke(tmp_path, ["--mission", handle, "--json"])
        assert result.exit_code == 0, f"handle {handle!r} failed to resolve"
        payload = json.loads(result.stdout)
        assert [r["slug"] for r in payload["results"]] == ["042-demo"], handle

    assert json.loads((feature_dir / "meta.json").read_text())["status_phase"] == "1"


def test_unknown_mission_handle_exits_nonzero(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs").mkdir()
    result = _invoke(tmp_path, ["--mission", "does-not-exist"])
    # resolve_mission_handle prints + sys.exit(2)s on an unknown handle.
    assert result.exit_code != 0


def test_no_kitty_specs_is_clean_noop(tmp_path: Path) -> None:
    result = _invoke(tmp_path, ["--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total"] == 0


def test_no_repo_root_event_write_via_cli(tmp_path: Path) -> None:
    build_mission(tmp_path)
    result = _invoke(tmp_path, [])
    assert result.exit_code == 0
    assert not (tmp_path / "status.events.jsonl").exists()
    assert not (tmp_path / "meta.json").exists()
