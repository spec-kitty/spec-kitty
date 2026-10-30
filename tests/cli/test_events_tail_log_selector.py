"""CLI tests for `spec-kitty events tail`'s ``--log`` selector and ``--json`` flip (#6611).

WP02 of mission ``events-tail-multi-log-and-json-01M66F8A``. Mirrors
``tests/cli/test_events_tail.py``'s mounting/mocking discipline (throwaway root
Typer app so ``tail`` stays an explicit subcommand; autouse surface-mocking
fixture; per-test ``resolve_mission_handle`` patching — patch target is always
the IMPORTING module, never ``selector_resolution``).

Deterministic termination: every invocation passes ``--once`` or a small
``--max-events`` — never a bare unbounded stream.

Marker/CI discipline: module-level ``pytestmark = [pytest.mark.fast]``
(collected by ``fast-tests-cli``, ``-m "fast and not windows_ci"``).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner, Result

from specify_cli.cli.commands import events as events_cli
from specify_cli.context.mission_resolver import ResolvedMission

pytestmark = [pytest.mark.fast]

runner = CliRunner()

MISSION_SLUG = "002-log-selector-fixture"
MISSION_ID = "01LOGSELECTORFIXTURE000000A"

_root_app = typer.Typer()
_root_app.add_typer(events_cli.app, name="events")


def _invoke(*args: str, repo_root: Path | None = None) -> Result:
    """Invoke `events tail`. Pass ``repo_root`` to pin ``SPECIFY_REPO_ROOT``
    (hermetic repo-root resolution for the project-scoped kinds)."""
    env = {"SPECIFY_REPO_ROOT": str(repo_root)} if repo_root is not None else None
    return runner.invoke(_root_app, ["events", *args], env=env)


@pytest.fixture(autouse=True)
def _surface_is_the_handed_dir() -> Iterator[None]:
    """Hermetic surface resolution: the resolved surface IS the handed mission
    dir. Tests that need a failing-closed surface patch it again in-body."""
    with patch.object(
        events_cli,
        "resolve_surface_dir_or_typed_error",
        side_effect=lambda _repo_root, _slug, *, on_missing_meta: on_missing_meta,
    ):
        yield


def _resolved(repo_root: Path) -> ResolvedMission:
    return ResolvedMission(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MISSION_ID[:8],
        feature_dir=repo_root / "kitty-specs" / MISSION_SLUG,
    )


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


_DECISION_ROWS = [
    {"event_type": "decision_recorded", "timestamp": "2026-10-30T13:00:00Z", "payload": {"decision_id": "D1"}},
    {"event_type": "decision_recorded", "timestamp": "2026-10-30T13:01:00Z", "payload": {"decision_id": "D2"}},
]


def _surface(repo_root: Path) -> Path:
    return _resolved(repo_root).feature_dir


def _write_run(repo_root: Path, run_id: str, *, mtime: float, mission_id: str | None, mission_slug: str | None) -> Path:
    from runtime.next.run_index import runs_root

    run_dir = runs_root(repo_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot: dict[str, Any] = {"run_id": run_id, "mission_key": "software-dev"}
    if mission_id is not None:
        snapshot["mission_id"] = mission_id
    if mission_slug is not None:
        snapshot["mission_slug"] = mission_slug
    (run_dir / "state.json").write_text(json.dumps(snapshot), encoding="utf-8")
    journal = run_dir / "run.events.jsonl"
    _write_rows(journal, [{"type": "run_step", "run": run_id}])
    os.utime(journal, (mtime, mtime))
    return journal


# ---------------------------------------------------------------------------
# T005 — red-first defect reproductions for #6611 (kept as regressions).
# On pre-mission main: (1) `--log` is an unknown option (exit 2); (2) `--json`
# has no observable effect (default output == --json output).
# ---------------------------------------------------------------------------


def test_log_decisions_streams_rows_as_json(tmp_path: Path) -> None:
    """Contract row 1: `--log decisions --once --json` streams decision rows."""
    _write_rows(_surface(tmp_path) / "decisions.events.jsonl", _DECISION_ROWS)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "decisions",
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    parsed = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert [p["payload"]["decision_id"] for p in parsed] == ["D1", "D2"]


def test_default_output_differs_from_json_output(tmp_path: Path) -> None:
    """Contract row 2: without `--json` the output is human, not JSON lines."""
    _write_rows(_surface(tmp_path) / "decisions.events.jsonl", _DECISION_ROWS)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        human = _invoke("tail", "--mission", MISSION_SLUG, "--log", "decisions", "--once", repo_root=tmp_path)
        machine = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "decisions",
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert human.exit_code == 0, human.output
    assert machine.exit_code == 0, machine.output
    assert human.stdout != machine.stdout
    # The human lines are NOT JSON.
    for line in human.stdout.splitlines():
        if line.strip():
            with pytest.raises(json.JSONDecodeError):
                json.loads(line)


# ---------------------------------------------------------------------------
# T008 — the behavioral battery (contract rows 3–10).
# ---------------------------------------------------------------------------


def test_status_kind_json_is_byte_identical_to_prechange_shape(tmp_path: Path) -> None:
    """NFR-004: `--log status --once --json` keeps the pre-#6611 output shape —
    the reader-injected cursor keys included, same json.dumps serialization."""
    rows = [{"event_id": "evt-1", "wp_id": "WP01"}, {"event_id": "evt-2", "wp_id": "WP02"}]
    log_path = _write_rows(_surface(tmp_path) / "status.events.jsonl", rows)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "status",
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    # Frozen expected literals: exactly what the pre-#6611 command emitted for
    # this fixture — the row plus the reader-injected cursor keys appended in
    # the reader's own order (tail_offset = byte offset after the line,
    # tail_invariant = SHA-256 of the raw line). This pins NFR-004 against any
    # future reordering or reframing, not just against invalid JSON.
    import hashlib

    expected_lines: list[str] = []
    offset = 0
    with log_path.open("rb") as fh:
        for row in rows:
            raw = fh.readline()
            offset += len(raw)
            expected = dict(row)
            expected["tail_offset"] = offset
            # TID251: file-integrity checksum, mirroring tail_reader's own sanctioned use
            expected["tail_invariant"] = hashlib.sha256(raw).hexdigest()  # noqa: TID251
            expected_lines.append(json.dumps(expected))
    assert lines == expected_lines


@pytest.mark.parametrize(
    ("kind", "relative"),
    [
        ("status", Path("kitty-specs") / MISSION_SLUG / "status.events.jsonl"),
        ("decisions", Path("kitty-specs") / MISSION_SLUG / "decisions.events.jsonl"),
        ("mission", Path("kitty-specs") / MISSION_SLUG / "mission-events.jsonl"),
        ("glossary", Path(".kittify") / "events" / "glossary" / f"{MISSION_ID}.events.jsonl"),
        ("ops", Path("kitty-ops") / "lifecycle.jsonl"),
        ("canonical", Path(".kittify") / "canonical-events.jsonl"),
    ],
)
def test_every_kind_tails_its_canonical_path(tmp_path: Path, kind: str, relative: Path) -> None:
    """Contract: table-driven — each kind reads rows from its canonical path."""
    marker = f"row-for-{kind}"
    _write_rows(tmp_path / relative, [{"event_id": marker, "kind": kind}])
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            kind,
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    parsed = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert [p["event_id"] for p in parsed] == [marker]


def test_log_run_tails_the_newest_run_journal(tmp_path: Path) -> None:
    """Contract row 4: two runs for the mission — the newer journal wins."""
    older = _write_run(tmp_path, "01RUNOLD0000000000000000000001", mtime=1_000, mission_id=MISSION_ID, mission_slug=MISSION_SLUG)
    newer = _write_run(tmp_path, "01RUNNEW0000000000000000000002", mtime=9_000, mission_id=MISSION_ID, mission_slug=MISSION_SLUG)
    assert newer != older
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "run",
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    parsed = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert [p["run"] for p in parsed] == ["01RUNNEW0000000000000000000002"]


def test_log_run_refuses_when_only_other_missions_have_runs(tmp_path: Path) -> None:
    """Contract row 5: typed `run_log_unavailable` refusal, exit 1, empty stdout."""
    _write_run(tmp_path, "01RUNFOREIGN0000000000000000003", mtime=5_000, mission_id="01FOREIGNMISSION000000000Z", mission_slug="other-mission")
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "run",
            "--once",
            repo_root=tmp_path,
        )
    assert result.exit_code == 1
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "run_log_unavailable"


def test_log_run_resume_validates_against_the_selected_run_journal(tmp_path: Path) -> None:
    """Mission-review finding 3b: `--log run` + bad `--from-offset` refuses
    with invalid_resume_offset AFTER run resolution succeeds."""
    _write_run(tmp_path, "01RUNRESUME000000000000000000009", mtime=5_000, mission_id=MISSION_ID, mission_slug=MISSION_SLUG)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "run",
            "--once",
            "--from-offset",
            "999999",
            repo_root=tmp_path,
        )
    assert result.exit_code == 2
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "invalid_resume_offset"


def test_decisions_kind_still_refuses_on_failing_status_surface(tmp_path: Path) -> None:
    """Mission-review finding 3c: contract row 10's decisions half — the
    COORD-partition refusal applies to decisions too, not only status."""
    from specify_cli.coordination.surface_resolver import StatusReadPathNotFound

    def _fail_closed(*_args: Any, **_kwargs: Any) -> Path:
        raise StatusReadPathNotFound(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            mid8=MISSION_ID[:8],
            coord_candidate=tmp_path / "coord",
            primary_candidate=tmp_path / "primary",
        )

    with (
        patch.object(events_cli, "resolve_surface_dir_or_typed_error", side_effect=_fail_closed),
        patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)),
    ):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "decisions",
            "--once",
            repo_root=tmp_path,
        )
    assert result.exit_code == 1
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "status_surface_unavailable"


@pytest.mark.parametrize("kind", ["glossary", "ops", "canonical"])
def test_missing_log_prints_nothing_and_exits_zero(tmp_path: Path, kind: str) -> None:
    """Contract row 6: an absent ledger is an empty stream, not an error
    (each project-scoped kind asserted, mission-review finding 3a)."""
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            kind,
            "--once",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    assert result.stdout == ""


def test_project_scoped_kind_ignores_a_failing_status_surface(tmp_path: Path) -> None:
    """Contract row 10 (lazy surface resolution): a closed status surface never
    blocks a project-scoped kind."""
    _write_rows(tmp_path / "kitty-ops" / "lifecycle.jsonl", [{"type": "op_started"}])
    from specify_cli.coordination.surface_resolver import StatusReadPathNotFound

    def _fail_closed(*_args: Any, **_kwargs: Any) -> Path:
        raise StatusReadPathNotFound(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            mid8=MISSION_ID[:8],
            coord_candidate=tmp_path / "coord",
            primary_candidate=tmp_path / "primary",
        )

    with (
        patch.object(events_cli, "resolve_surface_dir_or_typed_error", side_effect=_fail_closed),
        patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)),
    ):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "ops",
            "--once",
            "--json",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout.splitlines()[0])["type"] == "op_started"


def test_status_kind_still_refuses_on_failing_status_surface(tmp_path: Path) -> None:
    """Contract row 10: the COORD-partition kinds keep the typed refusal."""
    from specify_cli.coordination.surface_resolver import StatusReadPathNotFound

    def _fail_closed(*_args: Any, **_kwargs: Any) -> Path:
        raise StatusReadPathNotFound(
            repo_root=tmp_path,
            mission_slug=MISSION_SLUG,
            mid8=MISSION_ID[:8],
            coord_candidate=tmp_path / "coord",
            primary_candidate=tmp_path / "primary",
        )

    with (
        patch.object(events_cli, "resolve_surface_dir_or_typed_error", side_effect=_fail_closed),
        patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)),
    ):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "status",
            "--once",
            repo_root=tmp_path,
        )
    assert result.exit_code == 1
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "status_surface_unavailable"


def test_resume_offset_validates_against_the_selected_log(tmp_path: Path) -> None:
    """Contract row 7: `--from-offset` validates against the SELECTED log."""
    _write_rows(_surface(tmp_path) / "decisions.events.jsonl", _DECISION_ROWS)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "decisions",
            "--once",
            "--from-offset",
            "999999",
            repo_root=tmp_path,
        )
    assert result.exit_code == 2
    assert result.stdout == ""
    stderr_body = json.loads(result.stderr)
    assert stderr_body["error"] == "invalid_resume_offset"


def test_from_invariant_alone_is_a_usage_error_for_any_kind() -> None:
    """Contract row 9: the usage check precedes file access for every kind."""
    result = _invoke(
        "tail",
        "--mission",
        "does-not-matter",
        "--log",
        "decisions",
        "--once",
        "--from-invariant",
        "deadbeef",
    )
    assert result.exit_code == 2
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"] == "usage_error"


def test_unknown_log_kind_is_a_usage_error_before_any_file_access(tmp_path: Path) -> None:
    """Contract row 8: `--log bogus` → Typer choice violation, exit 2."""
    with patch.object(events_cli, "resolve_mission_handle", side_effect=AssertionError("must not resolve")):
        result = _invoke("tail", "--mission", MISSION_SLUG, "--log", "bogus", "--once")
    assert result.exit_code == 2
    assert result.stdout == ""


def test_human_mode_renders_the_deterministic_line(tmp_path: Path) -> None:
    """Human default: the renderer's exact line (contract's human shape)."""
    rows = [{"event_type": "decision_recorded", "timestamp": "2026-10-30T13:00:00Z", "payload": {"decision_id": "D1"}}]
    _write_rows(_surface(tmp_path) / "decisions.events.jsonl", rows)
    with patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(tmp_path)):
        result = _invoke(
            "tail",
            "--mission",
            MISSION_SLUG,
            "--log",
            "decisions",
            "--once",
            repo_root=tmp_path,
        )
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == ['2026-10-30T13:00:00Z decision_recorded {"decision_id": "D1"}']


def test_human_mode_renders_log_truncated_as_warning_line() -> None:
    """The `log_truncated` signal renders as its own warning line, not JSON.

    The signal's SHAPE is owned and pinned by the core reader's own tests
    (tail_reader); this exercises the shell's RENDER branch for it by driving
    the stream seam with the exact envelope the core emits (FR-005/FR-007).
    A cold `--from-offset` resume cannot trigger it by construction — the
    FR-013 validator refuses an out-of-range offset BEFORE streaming — so the
    live-stream seam is the honest entry point here.
    """
    signal = {
        "type": "log_truncated",
        "reason": "size_shrink",
        "detected_at_offset": 128,
        "tail_offset": 0,
        "tail_invariant": "0" * 64,
    }
    with (
        patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(Path("/tmp"))),
        patch.object(events_cli, "tail_events", return_value=iter([signal])),
    ):
        result = _invoke("tail", "--mission", "does-not-matter", "--log", "status", "--max-events", "1")
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == ["log truncated (size_shrink) at offset 128 — resynced from offset 0"]
    # The same signal in --json mode stays the machine envelope.
    with (
        patch.object(events_cli, "resolve_mission_handle", return_value=_resolved(Path("/tmp"))),
        patch.object(events_cli, "tail_events", return_value=iter([signal])),
    ):
        machine = _invoke("tail", "--mission", "does-not-matter", "--log", "status", "--json")
    assert json.loads(machine.stdout.splitlines()[0])["type"] == "log_truncated"
