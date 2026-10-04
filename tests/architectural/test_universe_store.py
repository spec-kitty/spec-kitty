"""Contract tests for the keyed on-disk store behind ``collect_universe()``.

Mission ``shared-collection-and-shard-recapture-01M42V58`` WP01 (FR-001..FR-007, FR-010,
FR-012, NFR-004, C-003). Every refusal row of ``contracts/collection-store.md`` is pinned by a
test that carries a paired positive control on the same fixture, so a guard that never fires and
a guard that always fires are both caught.

No test here performs a real collection: the collector is a counting fake. The real repository
is touched only to time the key computation (NFR-004) and to observe what a fresh pytest session
sets in its environment.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from kernel.locks import LockAcquireTimeout, machine_file_lock
from tests.architectural import _fast_tier_gate as ftg
from tests.architectural import _gate_coverage as gc
from tests.architectural import _live_uniqueness as lu
from tests.architectural import _universe_store as us
from tests.architectural import test_fast_tier_marker_completeness as fast_tier_gate

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

Records = list[dict[str, Any]]

_FLOOR = us.SANITY_FLOOR
_DEPS = "deps-digest-0"
_INTERP = ("cpython", 3, 12, 1)
_NO_ENV: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _universe(size: int = _FLOOR, tag: str = "a") -> Records:
    return [
        {
            "nodeid": f"tests/sample/test_{tag}.py::test_case_{index}",
            "relpath": f"tests/sample/test_{tag}.py",
            "markers": ["fast"],
        }
        for index in range(size)
    ]


class Collector:
    """A counting fake for the fresh-collection helper."""

    def __init__(self, records: Records | None = None) -> None:
        self.records = records if records is not None else _universe()
        self.calls = 0

    def __call__(self) -> Records:
        self.calls += 1
        copy: Records = json.loads(json.dumps(self.records))
        return copy


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_file(repo: Path, relative: str, text: str) -> None:
    target = repo / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"change {relative}")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "store-test@example.invalid")
    _git(root, "config", "user.name", "Store Test")
    (root / ".gitignore").write_text(".pytest_cache/\n", encoding="utf-8")
    _commit_file(root, "tracked.txt", "one\n")
    return root


@pytest.fixture
def report(tmp_path: Path) -> Path:
    return tmp_path / "reuse-report.jsonl"


def _last_report(report: Path) -> dict[str, Any]:
    lines = report.read_text(encoding="utf-8").splitlines()
    assert lines, "expected at least one report line"
    parsed: dict[str, Any] = json.loads(lines[-1])
    return parsed


def _request(
    repo: Path,
    collector: Collector,
    report: Path,
    **overrides: Any,
) -> tuple[Records, dict[str, Any]]:
    """One ``collect_through_store`` call; returns the records and the report line it wrote."""
    kwargs: dict[str, Any] = {
        "root_override": False,
        "environ": {us.REPORT_ENV_VAR: str(report)},
        "dependencies": _DEPS,
        "interpreter": _INTERP,
        "platform": "linux",
    }
    kwargs.update(overrides)
    records = us.collect_through_store(repo, collector, **kwargs)
    return records, _last_report(report)


def _store_files(repo: Path) -> dict[str, bytes]:
    store = us.store_dir(repo)
    if not store.exists():
        return {}
    return {path.name: path.read_bytes() for path in sorted(store.glob("*.json"))}


def _key(repo: Path, **overrides: Any) -> str:
    kwargs: dict[str, Any] = {
        "environ": _NO_ENV,
        "dependencies": _DEPS,
        "interpreter": _INTERP,
        "platform": "linux",
    }
    kwargs.update(overrides)
    key = us.collection_key(repo, **kwargs)
    assert key is not None
    return key


def _edit_record(repo: Path, mutate: Any) -> None:
    (path,) = us.store_dir(repo).glob("*.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# The key (FR-001, FR-002, D-01, D-02)
# ---------------------------------------------------------------------------


def test_key_changes_when_the_committed_tree_changes(repo: Path) -> None:
    before = _key(repo)
    assert _key(repo) == before, "control: the same checkout must give the same key"

    _commit_file(repo, "docs/elsewhere.md", "a file outside tests/\n")

    assert _key(repo) != before


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"interpreter": ("cpython", 3, 13, 0)}, id="interpreter-version"),
        pytest.param({"interpreter": ("pypy", 3, 12, 1)}, id="interpreter-implementation"),
        pytest.param({"platform": "darwin"}, id="platform"),
        pytest.param({"dependencies": "deps-digest-1"}, id="installed-distributions"),
        pytest.param({"environ": {"SPEC_KITTY_RUN_QUARANTINE": "1"}}, id="spec-kitty-switch"),
        pytest.param({"environ": {"SPEC_KITTY_A_FUTURE_SWITCH": "on"}}, id="new-spec-kitty-switch"),
        pytest.param({"environ": {"PYTEST_ADDOPTS": "-m slow"}}, id="pytest-addopts"),
    ],
)
def test_key_changes_with_the_collecting_environment(repo: Path, change: dict[str, Any]) -> None:
    assert _key(repo) == _key(repo), "control: the baseline key is stable"

    assert _key(repo, **change) != _key(repo)


def test_key_changes_with_the_value_of_a_switch(repo: Path) -> None:
    assert _key(repo, environ={"SPEC_KITTY_RUN_QUARANTINE": "1"}) != _key(repo, environ={"SPEC_KITTY_RUN_QUARANTINE": "0"})


@pytest.mark.parametrize(
    "name",
    [
        "PYTEST_CURRENT_TEST",
        "PYTEST_XDIST_WORKER",
        "PYTEST_XDIST_WORKER_COUNT",
        "SK_GATE_DUMP",
        "SK_GATE_REPO",
        us.REPORT_ENV_VAR,
        "HOME",
        "SPEC_KITTY_REAL_HOME_FOR_TESTS",
        "SPEC_KITTY_ENABLE_SAAS_SYNC",
        "SPEC_KITTY_TEST_VENV",
    ],
)
def test_key_ignores_per_process_and_session_variables(repo: Path, name: str) -> None:
    baseline = _key(repo)

    assert _key(repo, environ={name: "worker-specific-value"}) == baseline
    assert _key(repo, environ={"SPEC_KITTY_RUN_QUARANTINE": "1", name: "x"}) == _key(repo, environ={"SPEC_KITTY_RUN_QUARANTINE": "1"}), (
        "control: a real switch next to the ignored name still counts"
    )


def test_key_is_none_when_git_cannot_answer(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()

    assert us.collection_key(not_a_repo, environ=_NO_ENV, dependencies=_DEPS, interpreter=_INTERP, platform="linux") is None


# ---------------------------------------------------------------------------
# The operator env file (``.kittify/.kitty.env``) must not make the key depend on who loaded it
# ---------------------------------------------------------------------------

_SWITCH = "SPEC_KITTY_EXAMPLE_SWITCH"


@pytest.fixture
def operator_repo(repo: Path, canonical_home: None) -> Path:
    """A clean checkout whose ``.kittify/.kitty.env`` is git-ignored, as in the real repository.

    ``canonical_home`` points the home tier of the loader at an empty directory, so the test
    never reads the operator's real ``<state-root>/.kitty.env``.
    """
    (repo / ".kittify").mkdir()
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text(".kittify/.kitty.env\n", encoding="utf-8")
    return repo


def _set_env_file(repo: Path, value: str | None) -> None:
    path = repo / ".kittify" / ".kitty.env"
    if value is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(f"{_SWITCH}={value}\n", encoding="utf-8")


def test_key_does_not_depend_on_who_loaded_the_operator_env_file(operator_repo: Path) -> None:
    _set_env_file(operator_repo, "1")
    plain_process = _key(operator_repo, environ={})
    process_that_imported_specify_cli = _key(operator_repo, environ={_SWITCH: "1"})

    assert plain_process == process_that_imported_specify_cli

    _set_env_file(operator_repo, "2")
    assert _key(operator_repo, environ={}) != plain_process, "control: another value in the file is another key"
    _set_env_file(operator_repo, None)
    assert _key(operator_repo, environ={}) != plain_process, "control: no file is another key"
    assert _key(operator_repo, environ={_SWITCH: "1"}) == process_that_imported_specify_cli, "control: the real value still counts"


def test_a_real_environment_value_wins_over_the_env_file(operator_repo: Path) -> None:
    _set_env_file(operator_repo, "1")
    real_value_wins = _key(operator_repo, environ={_SWITCH: "2"})

    _set_env_file(operator_repo, None)
    assert real_value_wins == _key(operator_repo, environ={_SWITCH: "2"}), "setdefault: the file value 1 never replaces the real 2"
    assert real_value_wins != _key(operator_repo, environ={_SWITCH: "1"}), "control: the two values key differently"


def test_the_overlay_never_mutates_the_environment_it_was_given(operator_repo: Path) -> None:
    _set_env_file(operator_repo, "1")
    given: dict[str, str] = {}

    _key(operator_repo, environ=given)

    assert given == {}


def test_an_unreadable_env_file_bypasses_the_store_instead_of_crashing(operator_repo: Path, report: Path) -> None:
    (operator_repo / ".kittify" / ".kitty.env").mkdir()  # present but unreadable: a directory, not a file
    collector = Collector()

    records, line = _request(operator_repo, collector, report)

    assert collector.calls == 1
    assert records == collector.records
    assert (line["outcome"], line["reason"]) == (us.BYPASSED, us.ENV_FILE_UNREADABLE)
    assert ".kitty.env" in line["detail"]
    assert _store_files(operator_repo) == {}


# ---------------------------------------------------------------------------
# Reuse and the refusals (contract table, row for row)
# ---------------------------------------------------------------------------


def test_clean_checkout_collects_once_then_reuses(repo: Path, report: Path) -> None:
    collector = Collector()

    first, line = _request(repo, collector, report)
    assert (line["outcome"], line["reason"]) == ("collected", "no-record")
    assert line["key"] == _key(repo, environ={us.REPORT_ENV_VAR: str(report)})

    second, line = _request(repo, collector, report)
    assert line["outcome"] == "reused"
    assert line["reason"] is None
    assert collector.calls == 1
    assert second == first == collector.records


@pytest.mark.parametrize("kind", ["modified-tracked", "untracked"])
def test_dirty_checkout_neither_reads_nor_writes_the_store(repo: Path, report: Path, kind: str) -> None:
    collector = Collector()
    _request(repo, collector, report)
    stored_before = _store_files(repo)
    assert len(stored_before) == 1, "control: a clean checkout stores one record"

    if kind == "modified-tracked":
        (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
        dirty_name = "tracked.txt"
    else:
        (repo / "new_test_file.py").write_text("x = 1\n", encoding="utf-8")
        dirty_name = "new_test_file.py"

    _, line = _request(repo, collector, report)

    assert (line["outcome"], line["reason"]) == ("bypassed", "dirty-checkout")
    assert line["key"] is None
    assert dirty_name in line["dirty_paths"]
    assert collector.calls == 2, "the store was not read, so the collector ran again"
    assert _store_files(repo) == stored_before, "the store was not written"

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "make the change official")
    _, line = _request(repo, collector, report)
    assert (line["outcome"], line["reason"]) == ("collected", "no-record"), "control: once committed the store is used"
    assert _request(repo, collector, report)[1]["outcome"] == "reused"


def test_dirty_paths_in_the_report_are_capped_at_five(repo: Path, report: Path) -> None:
    for index in range(8):
        (repo / f"untracked_{index}.txt").write_text("x\n", encoding="utf-8")

    _, line = _request(repo, Collector(), report)

    assert line["reason"] == "dirty-checkout"
    assert len(line["dirty_paths"]) == 5


def test_repo_root_override_bypasses_the_store(repo: Path, report: Path) -> None:
    collector = Collector()
    _request(repo, collector, report)
    stored_before = _store_files(repo)
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "control: without the override the record is reused"
    calls_before = collector.calls

    other = Collector(_universe(tag="other"))
    records, line = _request(repo, other, report, root_override=True)

    assert (line["outcome"], line["reason"]) == ("bypassed", "root-override")
    assert records == other.records, "the stored record for the real root is not returned"
    assert other.calls == 1
    assert collector.calls == calls_before
    assert _store_files(repo) == stored_before, "the stored record is not replaced"


def test_unsupported_platform_bypasses_the_store(repo: Path, report: Path) -> None:
    collector = Collector()

    records, line = _request(repo, collector, report, platform="win32")

    assert (line["outcome"], line["reason"]) == ("bypassed", "unsupported-platform")
    assert records == collector.records
    assert _store_files(repo) == {}
    assert _request(repo, collector, report, platform="linux")[1]["outcome"] == "collected", "control: linux stores"


@pytest.mark.parametrize(
    "failure",
    [OSError("read-only store"), LockAcquireTimeout(path="store.lock")],
    ids=["os-error", "lock-timeout"],
)
def test_unusable_lock_falls_back_to_a_fresh_collection(repo: Path, report: Path, failure: Exception) -> None:
    collector = Collector()

    def broken_lock(path: Path, *, blocking: bool, timeout_s: float | None) -> Any:
        raise failure

    records, line = _request(repo, collector, report, lock_factory=broken_lock)

    assert (line["outcome"], line["reason"]) == ("bypassed", "unsupported-platform")
    assert type(failure).__name__ in line["detail"]
    assert records == collector.records
    assert _store_files(repo) == {}
    assert _request(repo, collector, report)[1]["outcome"] == "collected", "control: a working lock stores"


def test_lock_is_requested_blocking_with_a_wait_above_the_collection_timeout(repo: Path, report: Path) -> None:
    seen: dict[str, Any] = {}

    def spy_lock(path: Path, *, blocking: bool, timeout_s: float | None) -> Any:
        seen.update(path=path, blocking=blocking, timeout_s=timeout_s)
        return machine_file_lock(path, blocking=blocking, timeout_s=timeout_s)

    _request(repo, Collector(), report, lock_factory=spy_lock)

    assert seen["blocking"] is True
    assert seen["timeout_s"] is not None
    assert seen["timeout_s"] > 900, "above the 900 s collection timeout, or waiting workers would give up first"
    assert seen["path"].parent == us.store_dir(repo)
    assert seen["path"].suffix != ".json", "the lock file must never be mistaken for a record"


@pytest.mark.parametrize(
    "corruption",
    ["unreadable-json", "wrong-schema", "count-mismatch", "empty-records", "below-floor", "records-not-a-list"],
)
def test_invalid_record_is_replaced_by_a_fresh_collection(repo: Path, report: Path, corruption: str) -> None:
    collector = Collector()
    _request(repo, collector, report)
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "control: the valid record is reused"
    assert collector.calls == 1

    (path,) = us.store_dir(repo).glob("*.json")
    if corruption == "unreadable-json":
        path.write_text("{this is not json", encoding="utf-8")
    elif corruption == "wrong-schema":
        _edit_record(repo, lambda data: data.update(schema=us.SCHEMA + 1))
    elif corruption == "count-mismatch":
        _edit_record(repo, lambda data: data.update(count=data["count"] + 1))
    elif corruption == "empty-records":
        _edit_record(repo, lambda data: data.update(records=[], count=0))
    elif corruption == "below-floor":
        _edit_record(repo, lambda data: data.update(records=data["records"][: _FLOOR - 1], count=_FLOOR - 1))
    else:
        _edit_record(repo, lambda data: data.update(records="oops"))

    records, line = _request(repo, collector, report)

    assert (line["outcome"], line["reason"]) == ("collected", "invalid-record")
    assert records == collector.records
    assert collector.calls == 2
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "the file was replaced with a valid record"
    assert collector.calls == 2


def test_a_record_whose_inner_key_differs_from_its_file_name_is_invalid(repo: Path, report: Path) -> None:
    collector = Collector()
    _request(repo, collector, report)
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "control: the untouched record is reused"

    _edit_record(repo, lambda data: data.update(key="f" * 64))
    _, line = _request(repo, collector, report)

    assert (line["outcome"], line["reason"]) == ("collected", "invalid-record")
    assert collector.calls == 2
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "the file was replaced with a record that carries its own key"


@pytest.mark.parametrize("field", ["commit", "tree"])
def test_origin_mismatch_is_replaced_by_a_fresh_collection(repo: Path, report: Path, field: str) -> None:
    collector = Collector()
    _request(repo, collector, report)
    assert _request(repo, collector, report)[1]["outcome"] == "reused", "control: a matching origin is reused"

    _edit_record(repo, lambda data: data.update({field: "0" * 40}))
    _, line = _request(repo, collector, report)

    assert (line["outcome"], line["reason"]) == ("collected", "origin-mismatch")
    assert collector.calls == 2
    assert _request(repo, collector, report)[1]["outcome"] == "reused"


def test_failed_collection_raises_unchanged_and_stores_nothing(repo: Path, report: Path) -> None:
    ok = Collector()
    _request(repo, ok, report)
    seeded = _store_files(repo)
    _commit_file(repo, "tracked.txt", "two\n")  # new key, so the failing call has to collect

    def failing() -> Records:
        raise RuntimeError("gate-coverage collection did not complete cleanly")

    lines_before = report.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="gate-coverage collection did not complete cleanly"):
        us.collect_through_store(
            repo,
            failing,
            root_override=False,
            environ={us.REPORT_ENV_VAR: str(report)},
            dependencies=_DEPS,
            interpreter=_INTERP,
            platform="linux",
        )

    assert _store_files(repo) == seeded, "the failed run neither added nor evicted a record"
    assert report.read_text(encoding="utf-8") == lines_before, "a failure writes no report line"
    _request(repo, ok, report)
    assert len(_store_files(repo)) == 1, "control: a successful collection writes a record"
    assert _store_files(repo) != seeded


def test_a_universe_below_the_floor_is_returned_but_never_stored(repo: Path, report: Path) -> None:
    tiny = Collector(_universe(_FLOOR - 1))

    records, line = _request(repo, tiny, report)

    assert records == tiny.records
    assert line["outcome"] == "collected"
    assert _store_files(repo) == {}
    assert _request(repo, Collector(), report)[1]["outcome"] == "collected", "control: a full universe is stored"
    assert len(_store_files(repo)) == 1


def _commits_a_new_file(repo: Path) -> Collector:
    """A collector that commits a new file while it "collects" (the developer committed meanwhile)."""

    class Committing(Collector):
        def __call__(self) -> Records:
            _commit_file(repo, "added_while_collecting.txt", "new\n")
            return super().__call__()

    return Committing()


def _edits_a_tracked_file(repo: Path) -> Collector:
    """A collector that leaves an uncommitted edit behind while it "collects"."""

    class Editing(Collector):
        def __call__(self) -> Records:
            (repo / "tracked.txt").write_text("edited while collecting\n", encoding="utf-8")
            return super().__call__()

    return Editing()


@pytest.mark.parametrize(
    ("make_collector", "named"),
    [
        pytest.param(_commits_a_new_file, "commit", id="committed-meanwhile"),
        pytest.param(_edits_a_tracked_file, "tracked.txt", id="edited-meanwhile"),
    ],
)
def test_a_collection_the_checkout_moved_under_is_returned_but_not_stored(repo: Path, report: Path, make_collector: Any, named: str) -> None:
    unchanged = Collector()
    _, control = _request(repo, unchanged, report)
    assert (control["outcome"], control.get("detail")) == ("collected", None), "control: an unchanged checkout stores"
    assert len(_store_files(repo)) == 1
    shutil.rmtree(us.store_dir(repo))

    moving = make_collector(repo)
    records, line = _request(repo, moving, report)

    assert records == moving.records, "the caller still gets the freshly collected universe"
    assert line["outcome"] == "collected"
    assert line["detail"].startswith("not stored"), "the pre-step reads this prefix as a failure"
    assert named in line["detail"]
    assert _store_files(repo) == {}, "a collection of the new content must not be stored under the old commit and tree"


def _lock_after(change: Any) -> Any:
    """A lock factory that runs ``change`` while "waiting" for the lock, then takes the real lock."""

    def factory(path: Path, *, blocking: bool, timeout_s: float | None) -> Any:
        change()
        return machine_file_lock(path, blocking=blocking, timeout_s=timeout_s)

    return factory


@pytest.mark.parametrize("variant", ["control-unchanged", "committed-meanwhile", "edited-meanwhile"])
def test_a_record_the_checkout_moved_away_from_during_the_lock_wait_is_not_reused(repo: Path, report: Path, variant: str) -> None:
    old = Collector(_universe(tag="old"))
    assert _request(repo, old, report)[1]["outcome"] == "collected"
    old_key = _last_report(report)["key"]

    def change() -> None:
        if variant == "committed-meanwhile":
            _commit_file(repo, "added_while_waiting.txt", "new\n")
        elif variant == "edited-meanwhile":
            (repo / "tracked.txt").write_text("edited while waiting\n", encoding="utf-8")

    fresh = Collector(_universe(tag="new"))
    records, line = _request(repo, fresh, report, lock_factory=_lock_after(change))

    if variant == "control-unchanged":
        assert (line["outcome"], line["key"]) == ("reused", old_key)
        assert records == old.records
        return
    assert records == fresh.records, "the caller must get the universe of the checkout it is now in"
    assert fresh.calls == 1
    if variant == "committed-meanwhile":
        assert line["outcome"] == "collected"
        assert line["key"] not in (None, old_key), "the record is looked up under the key of the new tree"
    else:
        assert (line["outcome"], line["reason"]) == ("bypassed", "dirty-checkout")
        assert "tracked.txt" in line["dirty_paths"]


def test_writing_a_record_evicts_every_other_key(repo: Path, report: Path) -> None:
    collector = Collector()
    _request(repo, collector, report)
    (first,) = _store_files(repo)
    _request(repo, collector, report, environ={us.REPORT_ENV_VAR: str(report), "SPEC_KITTY_RUN_QUARANTINE": "1"})
    assert len(_store_files(repo)) == 1, "a second key replaced the first"
    assert first not in _store_files(repo)

    _commit_file(repo, "tracked.txt", "three\n")
    _request(repo, collector, report)

    assert len(_store_files(repo)) == 1
    (only,) = _store_files(repo)
    assert only == f"{_key(repo, environ={us.REPORT_ENV_VAR: str(report)})}.json"


def test_record_file_has_the_documented_shape(repo: Path, report: Path) -> None:
    collector = Collector()
    _request(repo, collector, report)

    (path,) = us.store_dir(repo).glob("*.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD", "HEAD^{tree}"], check=True, capture_output=True, text=True)
    commit, tree = head.stdout.split()

    assert set(data) == {"schema", "key", "commit", "tree", "created_at", "count", "records"}
    assert data["schema"] == us.SCHEMA
    assert (data["commit"], data["tree"]) == (commit, tree)
    assert data["count"] == len(data["records"]) == len(collector.records)
    assert path.stem == data["key"]


def test_store_location_is_git_ignored_in_the_real_repository() -> None:
    probe = us.store_dir(gc.REPO_ROOT) / "record.json"

    result = subprocess.run(
        ["git", "-C", str(gc.REPO_ROOT), "check-ignore", "-q", str(probe)],
        check=False,
        capture_output=True,
    )

    assert result.returncode == 0, "the store must live in a git-ignored place or it dirties the checkout"


# ---------------------------------------------------------------------------
# The report line (FR-010)
# ---------------------------------------------------------------------------


def test_no_report_variable_means_no_report_file(repo: Path, tmp_path: Path) -> None:
    collector = Collector()

    records = us.collect_through_store(
        repo,
        collector,
        root_override=False,
        environ={},
        dependencies=_DEPS,
        interpreter=_INTERP,
        platform="linux",
    )

    assert records == collector.records
    assert not list(tmp_path.glob("*.jsonl"))


def test_report_lines_are_appended_with_the_documented_fields(repo: Path, report: Path) -> None:
    collector = Collector()
    _request(repo, collector, report)
    _request(repo, collector, report, environ={us.REPORT_ENV_VAR: str(report), "PYTEST_CURRENT_TEST": "tests/gate/test_x.py::test_y (call)"})

    lines = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()]

    assert [line["outcome"] for line in lines] == ["collected", "reused"]
    for line in lines:
        assert {"outcome", "reason", "key", "caller", "seconds"} <= set(line)
        assert isinstance(line["seconds"], float)
    assert lines[0]["caller"] == "direct"
    assert lines[1]["caller"] == "tests/gate/test_x.py"


def test_report_caller_can_be_named_explicitly(repo: Path, report: Path) -> None:
    _, line = _request(repo, Collector(), report, caller="prestep")

    assert line["caller"] == "prestep"


# ---------------------------------------------------------------------------
# Production wiring (the real ``collect_universe`` wrapper)
# ---------------------------------------------------------------------------


def test_collect_universe_wrapper_uses_the_store(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = Collector()
    monkeypatch.setattr(gc, "REPO_ROOT", repo)
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda _repo: fresh())
    monkeypatch.setenv(us.REPORT_ENV_VAR, str(report))

    first = gc.collect_universe()
    assert _last_report(report)["outcome"] == "collected"
    second = gc.collect_universe()
    assert _last_report(report)["outcome"] == "reused"

    assert fresh.calls == 1
    assert first == second == fresh.records


def test_collect_universe_wrapper_bypasses_for_an_explicit_root(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = Collector()
    seen: list[Path] = []

    def fake_fresh(path: Path) -> Records:
        seen.append(path)
        return fresh()

    monkeypatch.setattr(gc, "_collect_universe_fresh", fake_fresh)
    monkeypatch.setenv(us.REPORT_ENV_VAR, str(report))

    gc.collect_universe(repo_root=repo)

    assert seen == [repo]
    assert (_last_report(report)["outcome"], _last_report(report)["reason"]) == ("bypassed", "root-override")
    assert _store_files(repo) == {}


def test_collect_universe_wrapper_can_label_its_caller(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = Collector()
    monkeypatch.setattr(gc, "REPO_ROOT", repo)
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda _repo: fresh())
    monkeypatch.setenv(us.REPORT_ENV_VAR, str(report))

    gc.collect_universe(caller="prestep")
    assert _last_report(report)["caller"] == "prestep"

    gc.collect_universe()
    assert _last_report(report)["caller"].endswith("test_universe_store.py"), "control: an unlabelled call keeps the caller derived from the running test"


# ---------------------------------------------------------------------------
# Planted violations on both paths (SC-007)
# ---------------------------------------------------------------------------


@pytest.fixture
def wired(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """``collect_universe`` of the real wrapper over a fake universe: returns the ``collected`` and ``reused`` results."""

    def request(universe: Records) -> tuple[Records, Records]:
        shutil.rmtree(us.store_dir(repo), ignore_errors=True)  # each request starts with nothing stored
        fresh = Collector(universe)
        monkeypatch.setattr(gc, "REPO_ROOT", repo)
        monkeypatch.setattr(gc, "_collect_universe_fresh", lambda _repo: fresh())
        monkeypatch.setenv(us.REPORT_ENV_VAR, str(report))
        first = gc.collect_universe()
        assert _last_report(report)["outcome"] == "collected"
        second = gc.collect_universe()
        assert _last_report(report)["outcome"] == "reused"
        assert fresh.calls == 1
        return first, second

    return request


def _padded(planted: Records) -> Records:
    """The planted records plus enough innocuous ones to clear the store's sanity floor."""
    padding = _universe(_FLOOR, tag="padding")
    for record in padding:
        record["relpath"] = "tests/padding/test_padding.py"
    return [*planted, *padding]


def test_planted_unmarked_fast_tier_test_is_caught_on_the_collected_and_the_reused_path(wired: Any) -> None:
    root = ftg.fast_tier_dirs()[0]
    marked = {"nodeid": f"{root}/test_planted.py::test_marked", "relpath": f"{root}/test_planted.py", "markers": ["fast"]}
    unmarked = {"nodeid": f"{root}/test_planted.py::test_unmarked", "relpath": f"{root}/test_planted.py", "markers": []}

    clean_collected, clean_reused = wired(_padded([marked]))
    for universe in (clean_collected, clean_reused):
        fast_tier_gate.test_every_fast_tier_dir_test_carries_a_vocabulary_marker(universe)  # control: a clean universe passes

    planted_collected, planted_reused = wired(_padded([marked, unmarked]))
    for universe in (planted_collected, planted_reused):
        with pytest.raises(AssertionError, match="must carry an explicit tier marker"):
            fast_tier_gate.test_every_fast_tier_dir_test_carries_a_vocabulary_marker(universe)


def _two_jobs_over(path: str) -> list[lu.LiveJob]:
    gates = [gc.Gate("ci-planted.yml", job, None, paths=[path], marker_expr=None, runs_on="ubuntu-24.04") for job in ("planted-one", "planted-two")]
    return lu.group_jobs(gates, [])


def test_planted_same_tier_overlap_is_caught_on_the_collected_and_the_reused_path(wired: Any) -> None:
    planted = [{"nodeid": f"tests/planted/test_dup.py::test_{index}", "relpath": "tests/planted/test_dup.py", "markers": ["fast"]} for index in range(3)]
    elsewhere = {"nodeid": "tests/elsewhere/test_one.py::test_only", "relpath": "tests/elsewhere/test_one.py", "markers": ["fast"]}
    overlapping = _two_jobs_over("tests/planted")
    disjoint = lu.group_jobs(
        [
            gc.Gate("ci-planted.yml", "planted-one", None, paths=["tests/planted"], marker_expr=None, runs_on="ubuntu-24.04"),
            gc.Gate("ci-planted.yml", "planted-two", None, paths=["tests/elsewhere"], marker_expr=None, runs_on="ubuntu-24.04"),
        ],
        [],
    )

    for universe in wired(_padded([*planted, elsewhere])):
        records = {record["nodeid"]: record for record in universe}
        control = lu.pairwise_overlaps(disjoint, lu.selected_by_job(disjoint, universe))
        assert not lu.uncovered_overlaps(control, (), disjoint, records), "control: disjoint jobs must not be reported"
        found = lu.pairwise_overlaps(overlapping, lu.selected_by_job(overlapping, universe))
        assert lu.uncovered_overlaps(found, (), overlapping, records), "the planted duplicate selection was not reported"


# ---------------------------------------------------------------------------
# Concurrency (FR-005): two processes, one collection
# ---------------------------------------------------------------------------


def _nonblocking_lock(path: Path, *, blocking: bool, timeout_s: float | None) -> Any:
    return machine_file_lock(path, blocking=False, timeout_s=None)


def _concurrent_worker(
    repo_text: str,
    count_file_text: str,
    use_blocking_lock: bool,
    barrier: Any,
    result_queue: Any,
) -> None:
    repo = Path(repo_text)
    count_file = Path(count_file_text)

    def slow_collect() -> Records:
        with count_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
        time.sleep(2.0)
        return _universe()

    barrier.wait(timeout=60)
    records = us.collect_through_store(
        repo,
        slow_collect,
        root_override=False,
        environ={},
        dependencies=_DEPS,
        interpreter=_INTERP,
        platform="linux",
        lock_factory=machine_file_lock if use_blocking_lock else _nonblocking_lock,
    )
    result_queue.put(records)


def _run_two_processes(repo: Path, count_file: Path, *, use_blocking_lock: bool) -> list[Records]:
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    workers = [
        context.Process(
            target=_concurrent_worker,
            args=(str(repo), str(count_file), use_blocking_lock, barrier, queue),
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=120) for _ in workers]
    for worker in workers:
        worker.join(timeout=60)
        assert worker.exitcode == 0
    return results


def test_two_processes_with_nothing_stored_collect_exactly_once(repo: Path, tmp_path: Path) -> None:
    count_file = tmp_path / "collections.txt"

    first, second = _run_two_processes(repo, count_file, use_blocking_lock=True)

    assert len(count_file.read_text(encoding="utf-8").splitlines()) == 1
    assert first == second == _universe()


def test_without_the_blocking_lock_both_processes_collect(repo: Path, tmp_path: Path) -> None:
    """Paired control: with a non-blocking lock the loser collects for itself, so the lock is what serialises."""
    count_file = tmp_path / "collections.txt"

    first, second = _run_two_processes(repo, count_file, use_blocking_lock=False)

    assert len(count_file.read_text(encoding="utf-8").splitlines()) == 2
    assert first == second == _universe()


# ---------------------------------------------------------------------------
# NFR-004 and the pre-step/test agreement
# ---------------------------------------------------------------------------


def test_key_computation_is_fast_on_the_real_repository() -> None:
    started = time.perf_counter()
    state = us.checkout_state(gc.REPO_ROOT)
    assert state is not None
    key = us.compute_key(state.tree, environ=os.environ)
    elapsed = time.perf_counter() - started

    assert key
    assert elapsed < 1.0, f"key computation took {elapsed:.2f}s, the budget is 1s (NFR-004)"


# The same key expression runs in the plain subprocess and inside the pytest session.
_KEY_EXPR = f'us.compute_key("tree-0", dependencies={_DEPS!r}, interpreter={_INTERP!r}, platform="linux")'

_PROBE = f"""
import json, os
from tests.architectural import _universe_store as us

def test_probe():
    report = {{
        "session_names": sorted(name for name in os.environ if name.startswith("SPEC_KITTY_")),
        "key": {_KEY_EXPR},
    }}
    with open(os.environ["PROBE_OUT"], "w", encoding="utf-8") as handle:
        json.dump(report, handle)
"""

_PLAIN = f"from tests.architectural import _universe_store as us\nprint({_KEY_EXPR})\n"


def _stripped_environment() -> dict[str, str]:
    env = {name: value for name, value in os.environ.items() if not name.startswith(("SPEC_KITTY_", "PYTEST_", "SK_GATE_"))}
    env["PYTHONPATH"] = os.pathsep.join([str(gc.REPO_ROOT), str(gc.REPO_ROOT / "src")])
    return env


def test_a_pytest_session_and_a_plain_pre_step_compute_the_same_key(tmp_path: Path) -> None:
    """The case that decides whether reuse can ever happen.

    A CI pre-step is a plain ``python -m`` process; the tests that later call ``collect_universe()``
    run inside a pytest session whose ``conftest.py`` writes ``SPEC_KITTY_*`` variables of its own,
    and which imports ``specify_cli`` and so seeds the operator env file. Compute the key in a plain
    subprocess and inside a fresh pytest session, both launched from the same stripped environment
    (no ``SPEC_KITTY_*`` or ``PYTEST_*``) and the same cwd, and require the two keys to be equal.
    It holds with or without an operator env file on this machine. A new session-set variable that
    is not excluded fails this test.
    """
    probe = tmp_path / "test_probe.py"
    probe.write_text(_PROBE, encoding="utf-8")
    out = tmp_path / "probe.json"
    session_env = {**_stripped_environment(), "PROBE_OUT": str(out)}

    plain = subprocess.run(
        [sys.executable, "-c", _PLAIN],
        cwd=gc.REPO_ROOT,
        env=_stripped_environment(),
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(probe),
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(gc.REPO_ROOT),
            "-c",
            str(gc.REPO_ROOT / "pytest.ini"),
            "-p",
            "tests.conftest",
        ],
        cwd=gc.REPO_ROOT,
        env=session_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    observed = json.loads(out.read_text(encoding="utf-8"))

    assert observed["session_names"], "the probe saw no session-set variables, so it would prove nothing"
    assert plain.stdout.strip() == observed["key"], (
        f"the session sets {observed['session_names']}: any of them that is neither in the exclusion constant "
        f"{sorted(us.ENV_EXCLUDED_NAMES)} nor seeded from the operator env file reaches the key, "
        "so no pre-step key can match a test's key"
    )


# A plugin that computes the key once collection is over, i.e. with every variable the collected
# modules set at import time already in the environment.
_COLLECTION_PROBE_PLUGIN = f"""
import json, os
from tests.architectural import _universe_store as us

def pytest_collection_finish(session):
    report = {{
        "session_names": sorted(name for name in os.environ if name.startswith("SPEC_KITTY_")),
        "key": {_KEY_EXPR},
        "collected": len(session.items),
    }}
    with open(os.environ["PROBE_OUT"], "w", encoding="utf-8") as handle:
        json.dump(report, handle)
"""


def _consuming_job_targets(leg: str) -> list[str]:
    """The positional arguments of one consuming CI job: a battery leg's files or the module shard directory."""
    if leg == "tests/ci":
        return [leg]
    return sorted(gc.battery_part_files(leg))


@pytest.mark.parametrize("leg", ["1/2", "2/2", "tests/ci"], ids=["battery-1-of-2", "battery-2-of-2", "module-shard-tests-ci"])
def test_the_key_after_collecting_a_consuming_jobs_files_equals_the_pre_step_key(tmp_path: Path, leg: str) -> None:
    """The pre-step key must match what the tests compute in a job that collects real files.

    Some test modules set a ``SPEC_KITTY_*`` variable when they are imported (``scripts/docs/*.py``
    do, and two architectural modules import them), and every worker imports them at collection.
    A probe session that loads only ``tests.conftest`` cannot see that. Collect the file list a
    consuming job really runs, compute the key at ``pytest_collection_finish``, and compare it with
    the key of a plain process started from the same stripped environment.
    """
    (tmp_path / "collection_key_probe.py").write_text(_COLLECTION_PROBE_PLUGIN, encoding="utf-8")
    out = tmp_path / "probe.json"
    plain_env = _stripped_environment()
    session_env = {**plain_env, "PROBE_OUT": str(out), "PYTHONPATH": os.pathsep.join([str(tmp_path), plain_env["PYTHONPATH"]])}

    plain = subprocess.run(
        [sys.executable, "-c", _PLAIN],
        cwd=gc.REPO_ROOT,
        env=plain_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(gc.REPO_ROOT),
            "-c",
            str(gc.REPO_ROOT / "pytest.ini"),
            "-p",
            "collection_key_probe",
            *_consuming_job_targets(leg),
        ],
        cwd=gc.REPO_ROOT,
        env=session_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=240,
    )
    observed = json.loads(out.read_text(encoding="utf-8"))

    assert observed["collected"] > 0, "the probe collected nothing, so it would prove nothing"
    leaked = sorted(name for name in observed["session_names"] if name not in us.ENV_EXCLUDED_NAMES)
    assert plain.stdout.strip() == observed["key"], (
        f"collecting {leg!r} leaves {leaked} in the environment; any of them that is neither excluded from the key "
        "nor seeded from the operator env file reaches the key, so the pre-step key cannot match a test's key in that job"
    )
