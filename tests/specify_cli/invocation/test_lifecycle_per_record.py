"""One file per Op lifecycle record (#7003).

Every Mission PR used to append to the one shared ``kitty-ops/lifecycle.jsonl``,
so two PRs in the merge queue conflicted at its end and the second was dropped.
A record now lands in its own ``kitty-ops/lifecycle/<ulid>.json`` file, which no
other branch ever writes. The legacy log stays readable, never written.

Read order (pinned here): the legacy log's lines in insertion order first, then
the per-record files sorted by (``at`` as UTC, ulid).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kernel.clock import UTC, datetime as _dt_datetime, timedelta as _dt_timedelta
from kernel.event_log_append import EventLogAppendError
from specify_cli.invocation.lifecycle import (
    LIFECYCLE_LOG_RELATIVE_PATH,
    LIFECYCLE_RECORDS_RELATIVE_DIR,
    append_lifecycle_record,
    compute_pairing_rate,
    doctor_orphan_report,
    find_latest_unpaired_started,
    find_orphans,
    group_by_action,
    lifecycle_log_path,
    lifecycle_records_dir,
    read_lifecycle_records,
    write_paired_completion,
    write_started,
)
from specify_cli.invocation.record import ProfileInvocationPhase, ProfileInvocationRecord

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION = "01HMISSION0000000000000000"


def _at(seconds: int) -> _dt_datetime:
    return _dt_datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC) + _dt_timedelta(seconds=seconds)


def _record(
    canonical: str,
    phase: ProfileInvocationPhase,
    seconds: int,
    *,
    mission: str = _MISSION,
) -> ProfileInvocationRecord:
    return ProfileInvocationRecord(
        canonical_action_id=canonical,
        phase=phase,
        at=_at(seconds),
        agent="claude",
        mission_id=mission,
        wp_id="WP01",
        reason="boom" if phase == "failed" else None,
    )


def _write_legacy(repo_root: Path, records: list[ProfileInvocationRecord]) -> Path:
    """Write a legacy ``lifecycle.jsonl`` the way the old append did."""
    path: Path = lifecycle_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.to_json_line() + "\n" for r in records), encoding="utf-8")
    return path


def _record_files(repo_root: Path) -> list[Path]:
    return sorted(lifecycle_records_dir(repo_root).glob("*.json"))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_the_layout_constants_name_the_legacy_log_and_the_record_directory(tmp_path: Path) -> None:
    assert Path("kitty-ops") / "lifecycle.jsonl" == LIFECYCLE_LOG_RELATIVE_PATH
    assert Path("kitty-ops") / "lifecycle" == LIFECYCLE_RECORDS_RELATIVE_DIR
    assert lifecycle_records_dir(tmp_path) == tmp_path / "kitty-ops" / "lifecycle"


def test_each_record_lands_in_its_own_ulid_named_file(tmp_path: Path) -> None:
    started = write_started(tmp_path, canonical_action_id="implement::do", agent="claude", mission_id=_MISSION, at=_at(0))
    write_paired_completion(tmp_path, started=started, phase="completed", at=_at(1))

    files = _record_files(tmp_path)
    assert len(files) == 2
    for path in files:
        # A 26-character Crockford ULID stem: sortable, no colon (Windows-safe).
        assert len(path.stem) == 26 and path.stem.isalnum() and path.stem.isupper()
        assert path.read_text(encoding="utf-8").count("\n") == 1
    assert not lifecycle_log_path(tmp_path).exists()


def test_append_returns_the_record_file_holding_exactly_the_record_line(tmp_path: Path) -> None:
    record = _record("implement::do", "started", 0)
    path = append_lifecycle_record(tmp_path / "nested", record)
    assert path.parent == lifecycle_records_dir(tmp_path / "nested")
    assert path.read_text(encoding="utf-8") == record.to_json_line() + "\n"


def test_the_legacy_log_is_never_written(tmp_path: Path) -> None:
    legacy = _write_legacy(tmp_path, [_record("old::one", "started", 0)])
    before = legacy.read_bytes()
    write_started(tmp_path, canonical_action_id="new::one", agent="claude", mission_id=_MISSION, at=_at(5))
    assert legacy.read_bytes() == before


def test_a_record_file_is_never_rewritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Append-only: a name collision refuses instead of adding a second record to a file."""
    import specify_cli.invocation.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "_new_record_id", lambda: "01ARZ3NDEKTSV4RRFFQ69G5FAV")
    first = append_lifecycle_record(tmp_path, _record("a::1", "started", 0))
    before = first.read_bytes()
    with pytest.raises(EventLogAppendError):
        append_lifecycle_record(tmp_path, _record("a::2", "started", 1))
    assert first.read_bytes() == before


# ---------------------------------------------------------------------------
# Read order
# ---------------------------------------------------------------------------


def test_legacy_lines_come_first_in_insertion_order_then_records_by_at(tmp_path: Path) -> None:
    # The legacy lines are deliberately out of ``at`` order: insertion order wins there.
    _write_legacy(tmp_path, [_record("legacy::b", "started", 50), _record("legacy::a", "started", 40)])
    # New records written out of ``at`` order: (at, ulid) order wins here.
    append_lifecycle_record(tmp_path, _record("new::late", "started", 30))
    append_lifecycle_record(tmp_path, _record("new::early", "started", 10))

    ids = [r.canonical_action_id for r in read_lifecycle_records(tmp_path)]
    assert ids == ["legacy::b", "legacy::a", "new::early", "new::late"]


def test_records_with_the_same_at_are_ordered_by_ulid(tmp_path: Path) -> None:
    directory = lifecycle_records_dir(tmp_path)
    directory.mkdir(parents=True)
    later = _record("tie::later-ulid", "started", 0)
    earlier = _record("tie::earlier-ulid", "started", 0)
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB0.json").write_text(later.to_json_line() + "\n", encoding="utf-8")
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json").write_text(earlier.to_json_line() + "\n", encoding="utf-8")

    ids = [r.canonical_action_id for r in read_lifecycle_records(tmp_path)]
    assert ids == ["tie::earlier-ulid", "tie::later-ulid"]


def test_a_naive_at_sorts_as_utc_beside_an_aware_one(tmp_path: Path) -> None:
    naive = ProfileInvocationRecord(
        canonical_action_id="naive::x",
        phase="started",
        at=_dt_datetime(2026, 11, 1, 12, 0, 5),
        agent="claude",
        mission_id=_MISSION,
    )
    append_lifecycle_record(tmp_path, _record("aware::y", "started", 10))
    append_lifecycle_record(tmp_path, naive)
    append_lifecycle_record(tmp_path, _record("aware::x", "started", 0))

    ids = [r.canonical_action_id for r in read_lifecycle_records(tmp_path)]
    assert ids == ["aware::x", "naive::x", "aware::y"]


def test_the_latest_unpaired_started_compares_a_naive_legacy_at_as_utc(tmp_path: Path) -> None:
    """A legacy line with no offset beside an aware record must not raise when picking the latest."""
    naive_legacy = ProfileInvocationRecord(
        canonical_action_id="legacy::naive",
        phase="started",
        at=_dt_datetime(2026, 11, 1, 12, 0, 30),
        agent="claude",
        mission_id=_MISSION,
    )
    path = lifecycle_log_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(naive_legacy.to_json_line().replace("+00:00", "") + "\n", encoding="utf-8")
    append_lifecycle_record(tmp_path, _record("new::aware", "started", 10))

    records = read_lifecycle_records(tmp_path)
    assert {r.at.tzinfo is None for r in records} == {True, False}
    latest = find_latest_unpaired_started(records, agent="claude", mission_id=_MISSION)
    assert latest is not None and latest.canonical_action_id == "legacy::naive"


def test_corrupt_record_files_are_skipped_like_corrupt_lines(tmp_path: Path) -> None:
    append_lifecycle_record(tmp_path, _record("good::one", "started", 0))
    directory = lifecycle_records_dir(tmp_path)
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB1.json").write_text("not json\n", encoding="utf-8")
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB2.json").write_text('{"missing": "fields"}\n', encoding="utf-8")
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB3.json").write_bytes(b"\xff\xfe")
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB4.json").write_text("", encoding="utf-8")
    (directory / "01ARZ3NDEKTSV4RRFFQ69G5FB5.json").mkdir()
    (directory / "notes.txt").write_text(_record("ignored::txt", "started", 0).to_json_line(), encoding="utf-8")

    ids = [r.canonical_action_id for r in read_lifecycle_records(tmp_path)]
    assert ids == ["good::one"]


def test_no_legacy_log_and_no_directory_reads_empty(tmp_path: Path) -> None:
    assert read_lifecycle_records(tmp_path) == []


# ---------------------------------------------------------------------------
# Mixed corpus: doctor results are unchanged by the layout
# ---------------------------------------------------------------------------


def _corpus() -> list[ProfileInvocationRecord]:
    return [
        _record("specify::do", "started", 0),
        _record("specify::do", "completed", 1),
        _record("plan::do", "started", 2),
        _record("plan::do", "failed", 3),
        _record("implement::do", "started", 4),  # orphan
        _record("implement::do", "started", 5, mission="01HOTHERMISSION00000000000"),
        _record("implement::do", "completed", 6, mission="01HOTHERMISSION00000000000"),
        _record("review::do", "started", 7),  # orphan
    ]


@pytest.mark.parametrize("split", [0, 3, 5, 8])
def test_a_mixed_legacy_and_record_corpus_gives_the_same_doctor_results(tmp_path: Path, split: int) -> None:
    corpus = _corpus()
    all_legacy = tmp_path / "legacy"
    _write_legacy(all_legacy, corpus)
    mixed = tmp_path / "mixed"
    _write_legacy(mixed, corpus[:split])
    for record in corpus[split:]:
        append_lifecycle_record(mixed, record)

    assert read_lifecycle_records(mixed) == read_lifecycle_records(all_legacy) == corpus
    assert doctor_orphan_report(mixed) == doctor_orphan_report(all_legacy)
    report = doctor_orphan_report(mixed)
    assert report["orphan_count"] == 2
    assert report["pairing_rate"] == pytest.approx(3 / 5)
    records = read_lifecycle_records(mixed)
    assert compute_pairing_rate(records) == pytest.approx(3 / 5)
    assert [g.canonical_action_id for g in find_orphans(records)] == ["implement::do", "review::do"]
    assert len(group_by_action(records)) == 5


# ---------------------------------------------------------------------------
# Two branches merge with plain git, no custom merge driver
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def _commit_all(repo: Path, message: str) -> None:
    assert _git(repo, "add", "--all").returncode == 0
    assert _git(repo, "commit", "-q", "-m", message).returncode == 0


@pytest.mark.git_repo
def test_two_branches_each_recording_lifecycle_events_merge_with_plain_git(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q", "-b", "main").returncode == 0
    # A legacy log on the base, as on main today; neither branch touches it.
    _write_legacy(repo, [_record("legacy::base", "started", 0), _record("legacy::base", "completed", 1)])
    _commit_all(repo, "base")

    assert _git(repo, "checkout", "-q", "-b", "mission-a").returncode == 0
    started_a = write_started(repo, canonical_action_id="a::do", agent="claude", mission_id="01HMISSIONA000000000000000", at=_at(10))
    write_paired_completion(repo, started=started_a, phase="completed", at=_at(11))
    _commit_all(repo, "mission a")

    assert _git(repo, "checkout", "-q", "main").returncode == 0
    assert _git(repo, "checkout", "-q", "-b", "mission-b").returncode == 0
    started_b = write_started(repo, canonical_action_id="b::do", agent="claude", mission_id="01HMISSIONB000000000000000", at=_at(20))
    write_paired_completion(repo, started=started_b, phase="completed", at=_at(21))
    _commit_all(repo, "mission b")

    assert _git(repo, "checkout", "-q", "main").returncode == 0
    assert _git(repo, "merge", "-q", "--no-edit", "mission-a").returncode == 0
    merge_b = _git(repo, "-c", "core.attributesFile=/dev/null", "merge", "-q", "--no-edit", "mission-b")
    assert merge_b.returncode == 0, merge_b.stdout + merge_b.stderr
    assert not (repo / ".gitattributes").exists()

    ids = [(r.canonical_action_id, r.phase) for r in read_lifecycle_records(repo)]
    assert ids == [
        ("legacy::base", "started"),
        ("legacy::base", "completed"),
        ("a::do", "started"),
        ("a::do", "completed"),
        ("b::do", "started"),
        ("b::do", "completed"),
    ]
    assert doctor_orphan_report(repo)["orphan_count"] == 0
    # Every record file is one line of JSON.
    for path in _record_files(repo):
        assert json.loads(path.read_text(encoding="utf-8"))["mission_id"].startswith("01HMISSION")
