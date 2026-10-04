"""Contract tests for ``python -m scripts.ci.collect_universe_prestep`` (mission
shared-collection-and-shard-recapture-01M42V58, WP02: FR-010, FR-011, NFR-005, D-07, D-14).

Every command is driven through the real ``main(argv)`` entry point. No test performs a real
collection: the collector is a counting fake, and ``check`` / ``compare`` read fixtures built
here. ``check`` cases carry a paired positive control built by the same helper, so a verdict that
never fails and a verdict that always fails are both caught.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.ci import collect_universe_prestep as prestep
from tests.architectural import _gate_coverage as gc
from tests.architectural import _universe_store as us

pytestmark = pytest.mark.fast

_FLOOR = us.SANITY_FLOOR
_KEY = "k" * 64
_NOTE = "pre-test step did not store a collection; reuse not expected"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _universe(size: int = _FLOOR, tag: str = "a") -> list[dict[str, Any]]:
    return [{"nodeid": f"tests/sample/test_{tag}.py::test_case_{index}", "relpath": f"tests/sample/test_{tag}.py", "markers": ["fast"]} for index in range(size)]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def _no_runner_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the runner's real summary file out of every test: under GitHub Actions the variable
    is set, so ``check`` would append fake tables to it and print differently. A test that wants
    a summary file sets its own."""
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A clean throwaway repository standing in for the repository root checkout."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "prestep-test@example.invalid")
    _git(root, "config", "user.name", "Prestep Test")
    (root / ".gitignore").write_text(".pytest_cache/\n", encoding="utf-8")
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    monkeypatch.setattr(gc, "REPO_ROOT", root)
    monkeypatch.delenv(us.REPORT_ENV_VAR, raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    return root


@pytest.fixture
def report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "reuse-report.jsonl"
    monkeypatch.setenv(us.REPORT_ENV_VAR, str(path))
    return path


def _line(outcome: str, *, caller: str = "tests/gate/test_x.py", reason: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"outcome": outcome, "reason": reason, "key": _KEY, "caller": caller, "seconds": 0.5, **extra}


def _write_report(path: Path, lines: list[dict[str, Any]]) -> None:
    path.write_text("".join(f"{json.dumps(line)}\n" for line in lines), encoding="utf-8")


def _prestep(outcome: str = "collected", **extra: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {"reason": "no-record" if outcome == "collected" else None, **extra}
    return _line(outcome, caller="prestep", **fields)


def _stored_key(repo: Path) -> tuple[str, us.CheckoutState]:
    state = us.checkout_state(repo)
    assert state is not None
    key = us.collection_key(repo)
    assert key is not None
    return key, state


# ---------------------------------------------------------------------------
# key
# ---------------------------------------------------------------------------


def test_key_prints_the_store_key_of_the_clean_checkout(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    expected = us.collection_key(repo)
    assert expected is not None

    code = prestep.main(["key"])

    assert code == 0
    assert capsys.readouterr().out.strip() == expected


def test_key_exits_2_and_prints_nothing_on_a_dirty_checkout(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    control = prestep.main(["key"])  # same fixture, clean: the control
    capsys.readouterr()
    assert control == 0

    (repo / "stray.txt").write_text("untracked\n", encoding="utf-8")
    code = prestep.main(["key"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert "stray.txt" in captured.err


def test_key_with_commit_appends_the_checkout_commit(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The cache key carries the commit too: a record is valid for one commit only, and a cache
    key is immutable, so a key shared by two commits would keep a rejected record forever."""
    state = us.checkout_state(repo)
    key = us.collection_key(repo)
    assert state is not None and key is not None

    code = prestep.main(["key", "--with-commit"])

    assert code == 0
    assert capsys.readouterr().out.strip() == f"{key}-{state.commit}"


def test_the_key_with_commit_changes_when_only_the_commit_changes(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """An empty commit leaves the tree, and so the plain key, unchanged; the key with the commit must change."""
    assert prestep.main(["key"]) == 0
    plain_before = capsys.readouterr().out.strip()
    assert prestep.main(["key", "--with-commit"]) == 0
    with_commit_before = capsys.readouterr().out.strip()

    _git(repo, "commit", "-q", "--allow-empty", "-m", "same tree, new commit")

    assert prestep.main(["key"]) == 0
    assert capsys.readouterr().out.strip() == plain_before
    assert prestep.main(["key", "--with-commit"]) == 0
    assert capsys.readouterr().out.strip() != with_commit_before


def test_key_with_commit_exits_2_and_prints_nothing_on_a_dirty_checkout(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "stray.txt").write_text("untracked\n", encoding="utf-8")

    code = prestep.main(["key", "--with-commit"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""


def test_with_commit_is_a_usage_error_for_any_other_command(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["key", "--with-commit"]) == 0  # control: accepted on `key`
    capsys.readouterr()

    with pytest.raises(SystemExit) as raised:
        prestep.main(["collect", "--with-commit"])

    assert raised.value.code == 2


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def test_collect_calls_the_collector_once_as_the_prestep(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake(repo_root: Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        calls.append({"repo_root": repo_root, **kwargs})
        _write_report(report, [_prestep("reused")])
        return []

    monkeypatch.setattr(gc, "collect_universe", fake)

    assert prestep.main(["collect"]) == 0
    assert calls == [{"repo_root": None, "caller": "prestep"}]


def test_collect_without_a_report_line_is_non_zero(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def silent(repo_root: Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def reporting(repo_root: Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        _write_report(report, [_prestep("reused")])
        return []

    monkeypatch.setattr(gc, "collect_universe", reporting)
    assert prestep.main(["collect"]) == 0, "control: the same collector exits 0 once it writes its line"

    monkeypatch.setattr(gc, "collect_universe", silent)
    capsys.readouterr()
    assert prestep.main(["collect"]) != 0
    assert "no report line" in capsys.readouterr().err


def test_collect_failure_is_non_zero_and_reaches_stderr(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom(repo_root: Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
        raise RuntimeError("gate-coverage collection did not complete cleanly")

    monkeypatch.setattr(gc, "collect_universe", boom)

    assert prestep.main(["collect"]) != 0
    assert "did not complete cleanly" in capsys.readouterr().err


def test_collect_writes_a_first_report_line_labelled_prestep(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fresh_calls: list[Path] = []

    def fresh(target: Path) -> list[dict[str, Any]]:
        fresh_calls.append(target)
        return _universe()

    monkeypatch.setattr(gc, "_collect_universe_fresh", fresh)

    assert prestep.main(["collect"]) == 0
    assert prestep.main(["collect"]) == 0

    lines = [json.loads(text) for text in report.read_text(encoding="utf-8").splitlines()]
    assert [(item["caller"], item["outcome"]) for item in lines] == [("prestep", "collected"), ("prestep", "reused")]
    assert len(fresh_calls) == 1
    printed = [json.loads(text) for text in capsys.readouterr().out.splitlines() if text.startswith("{")]
    assert [item["outcome"] for item in printed] == ["collected", "reused"]


def test_collect_prints_its_outcome_without_a_report_variable_and_leaves_the_environment(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())

    assert prestep.main(["collect"]) == 0

    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (printed["caller"], printed["outcome"]) == ("prestep", "collected")
    assert us.REPORT_ENV_VAR not in os.environ


def test_collect_on_a_dirty_checkout_fails_and_says_why(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    assert prestep.main(["collect"]) == 0, "control: the clean checkout stores and exits 0"
    capsys.readouterr()

    (repo / "stray.txt").write_text("untracked\n", encoding="utf-8")

    assert prestep.main(["collect"]) != 0
    captured = capsys.readouterr()
    assert '"bypassed"' in captured.out
    assert "dirty-checkout" in captured.err
    assert "stray.txt" in captured.err


def test_collect_outside_a_git_checkout_fails_and_says_why(
    tmp_path: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    plain = tmp_path / "not-a-repository"
    plain.mkdir()
    monkeypatch.setattr(gc, "REPO_ROOT", plain)

    assert prestep.main(["collect"]) != 0
    assert "git-unavailable" in capsys.readouterr().err


def test_collect_with_an_unusable_store_fails_and_shows_the_detail(
    repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    assert prestep.main(["collect"]) == 0, "control: the usable store is written and exits 0"
    capsys.readouterr()
    shutil.rmtree(us.store_dir(repo))
    us.store_dir(repo).write_text("a file where the store directory must go\n", encoding="utf-8")

    assert prestep.main(["collect"]) != 0
    err = capsys.readouterr().err
    assert "unsupported-platform" in err
    assert "FileExistsError" in err


def test_collect_that_could_not_store_the_record_fails(repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    assert prestep.main(["collect"]) == 0, "control: a universe at the floor is stored"
    capsys.readouterr()

    shutil.rmtree(repo / ".pytest_cache")
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe(size=10))

    assert prestep.main(["collect"]) != 0
    err = capsys.readouterr().err
    assert "not stored" in err


def test_collect_whose_checkout_moved_during_the_collection_fails(
    repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    assert prestep.main(["collect"]) == 0, "control: an unchanged checkout is stored"
    capsys.readouterr()
    shutil.rmtree(us.store_dir(repo))

    def collect_while_editing(target: Path) -> list[dict[str, Any]]:
        (repo / "tracked.txt").write_text("edited while collecting\n", encoding="utf-8")
        return _universe()

    monkeypatch.setattr(gc, "_collect_universe_fresh", collect_while_editing)

    assert prestep.main(["collect"]) != 0
    err = capsys.readouterr().err
    assert "not stored" in err
    assert "tracked.txt" in err


def test_collect_on_an_unsupported_platform_without_detail_is_acceptable(
    repo: Path, report: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())
    monkeypatch.setattr(sys, "platform", "win32")

    assert prestep.main(["collect"]) == 0
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (printed["outcome"], printed["reason"]) == ("bypassed", "unsupported-platform")
    assert "detail" not in printed


# ---------------------------------------------------------------------------
# check: verdict (pure) and main
# ---------------------------------------------------------------------------

_REUSING = [_prestep("collected"), _line("reused"), _line("reused", caller="tests/gate/test_y.py")]


def test_verdict_passes_when_every_later_request_reused() -> None:
    code, message = prestep.verdict(_REUSING)

    assert code == 0
    assert "reuse" in message


def test_verdict_fails_on_a_later_collection_and_names_it() -> None:
    lines = [*_REUSING, _line("collected", caller="tests/gate/test_z.py", reason="origin-mismatch")]

    code, message = prestep.verdict(lines)

    assert code == 1
    assert "tests/gate/test_z.py" in message
    assert "origin-mismatch" in message


def test_verdict_fails_on_a_later_dirty_checkout_bypass() -> None:
    lines = [*_REUSING, _line("bypassed", reason="dirty-checkout", dirty_paths=["shard_tests.txt"])]

    code, message = prestep.verdict(lines)

    assert code == 1
    assert "dirty-checkout" in message
    assert "shard_tests.txt" in message


@pytest.mark.parametrize("reason", ["unsupported-platform", "git-unavailable"])
def test_verdict_fails_on_any_other_bypass_and_shows_its_detail(reason: str) -> None:
    lines = [*_REUSING, _line("bypassed", reason=reason, detail="LockAcquireTimeout: waited")]

    code, message = prestep.verdict(lines)

    assert code == 1
    assert reason in message
    assert "LockAcquireTimeout" in message


def test_verdict_exempts_a_root_override_bypass() -> None:
    lines = [*_REUSING, _line("bypassed", reason="root-override", caller="tests/gate/test_w.py")]

    assert prestep.verdict(lines)[0] == 0


def test_verdict_reuse_pre_step_also_expects_reuse() -> None:
    lines = [_prestep("reused"), _line("collected", reason="invalid-record")]

    assert prestep.verdict(lines)[0] == 1


@pytest.mark.parametrize(
    "lines",
    [
        [],
        [_line("collected"), _line("collected")],
        [_prestep("bypassed", reason="unsupported-platform"), _line("collected")],
    ],
    ids=["empty", "no-prestep-line", "prestep-genuine-platform-bypass"],
)
def test_verdict_is_fallback_mode_without_a_usable_pre_step_line(lines: list[dict[str, Any]]) -> None:
    code, message = prestep.verdict(lines)

    assert code == 0
    assert _NOTE in message


_BAD_PRESTEPS = {
    "dirty-checkout": _prestep("bypassed", reason="dirty-checkout", dirty_paths=["shard_tests.txt"]),
    "git-unavailable": _prestep("bypassed", reason="git-unavailable"),
    "lock-or-store-failure": _prestep("bypassed", reason="unsupported-platform", detail="LockAcquireTimeout: waited"),
    "root-override": _prestep("bypassed", reason="root-override"),
    "collected-not-stored": _prestep("collected", detail="not stored: below the sanity floor"),
    "collected-checkout-moved": _prestep("collected", detail="not stored: the checkout changed during the collection (commit abc -> def)"),
}


@pytest.mark.parametrize("name", sorted(_BAD_PRESTEPS))
def test_verdict_fails_when_the_pre_step_itself_did_not_store_and_says_why(name: str) -> None:
    bad = _BAD_PRESTEPS[name]
    good = _prestep("reused")
    assert prestep.verdict([good, _line("reused")])[0] == 0, "control: an acceptable pre-step line passes on the same builder"

    code, message = prestep.verdict([bad, _line("collected")])

    assert code == 1
    assert "pre-test step" in message
    assert str(bad["reason"]) in message
    for extra in (bad.get("detail"), *(bad.get("dirty_paths") or [])):
        if extra:
            assert str(extra) in message


@pytest.mark.parametrize("name", sorted(_BAD_PRESTEPS))
def test_check_main_fails_a_pre_step_that_did_not_store(report: Path, name: str) -> None:
    _write_report(report, [_prestep("reused"), _line("reused")])
    assert prestep.main(["check"]) == 0, "control: the acceptable pre-step passes on the same fixture"

    _write_report(report, [_BAD_PRESTEPS[name]])

    assert prestep.main(["check"]) == 1


def test_check_main_accepts_a_genuine_platform_bypass_as_fallback(report: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_report(report, [_prestep("bypassed", reason="unsupported-platform"), _line("collected")])

    assert prestep.main(["check"]) == 0
    assert _NOTE in capsys.readouterr().out


def test_check_main_passes_a_fully_reused_report(report: Path) -> None:
    _write_report(report, _REUSING)

    assert prestep.main(["check"]) == 0


def test_check_main_fails_a_later_collection(report: Path) -> None:
    _write_report(report, [*_REUSING, _line("collected", reason="no-record")])

    assert prestep.main(["check"]) == 1


def test_check_main_fails_a_later_dirty_bypass_but_not_a_root_override(report: Path) -> None:
    _write_report(report, [*_REUSING, _line("bypassed", reason="root-override")])
    assert prestep.main(["check"]) == 0, "control: the exempt bypass passes on the same fixture"

    _write_report(report, [*_REUSING, _line("bypassed", reason="dirty-checkout")])
    assert prestep.main(["check"]) == 1


def test_check_main_is_fallback_mode_without_a_report_file(report: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert not report.exists()

    assert prestep.main(["check"]) == 0
    assert _NOTE in capsys.readouterr().out


def test_check_main_is_fallback_mode_without_a_report_variable(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["check"]) == 0
    assert _NOTE in capsys.readouterr().out


def test_check_main_is_fallback_mode_for_an_empty_report(report: Path) -> None:
    report.write_text("\n\n", encoding="utf-8")

    assert prestep.main(["check"]) == 0


def test_check_main_fails_on_a_malformed_line_and_names_it(report: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_report(report, _REUSING)
    assert prestep.main(["check"]) == 0, "control: the well-formed report passes"

    with report.open("a", encoding="utf-8") as stream:
        stream.write("{this is not json\n")

    assert prestep.main(["check"]) == 1
    assert "line 4" in capsys.readouterr().out


def test_check_main_fails_on_a_line_that_is_not_an_object(report: Path) -> None:
    report.write_text('["reused"]\n', encoding="utf-8")

    assert prestep.main(["check"]) == 1


def test_check_summary_goes_to_the_step_summary_file_when_set(
    report: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _write_report(report, [*_REUSING, _line("bypassed", reason="dirty-checkout", dirty_paths=["a.txt", "b.txt"], detail="x|y")])

    assert prestep.main(["check"]) == 1

    text = summary.read_text(encoding="utf-8")
    assert "| caller | outcome | reason | detail | dirty paths | seconds |" in text
    assert "| prestep | collected | no-record |" in text
    assert "a.txt, b.txt" in text
    assert "x\\|y" in text, "a pipe in a cell must not break the table"
    assert "dirty-checkout" in text
    assert "| caller |" not in capsys.readouterr().out, "the table goes to the summary file, not stdout"


def test_check_summary_goes_to_stdout_otherwise(report: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write_report(report, _REUSING)

    assert prestep.main(["check"]) == 0

    out = capsys.readouterr().out
    assert "| caller | outcome | reason | detail | dirty paths | seconds |" in out
    assert "| tests/gate/test_y.py | reused |" in out


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _store(repo: Path, records: list[dict[str, Any]]) -> None:
    key, state = _stored_key(repo)
    us.write_record(us.store_dir(repo), key, commit=state.commit, tree=state.tree, records=records)


def test_compare_passes_when_the_stored_universe_equals_a_fresh_one(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    stored = _universe()
    _store(repo, stored)
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: list(reversed(stored)))

    assert prestep.main(["compare"]) == 0
    assert str(len(stored)) in capsys.readouterr().out


def test_compare_fails_on_one_differing_record_and_prints_it(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    stored = _universe()
    _store(repo, stored)
    drifted = [dict(item) for item in stored]
    drifted[7]["markers"] = ["slow"]
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: drifted)

    assert prestep.main(["compare"]) == 1
    assert "test_case_7" in capsys.readouterr().out


def test_compare_prints_at_most_twenty_differences(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    stored = _universe()
    _store(repo, stored)
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe(tag="b"))

    assert prestep.main(["compare"]) == 1
    shown = [text for text in capsys.readouterr().out.splitlines() if "tests/sample/" in text]
    assert len(shown) == 20


def test_compare_fails_when_nothing_is_stored(repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: _universe())

    assert prestep.main(["compare"]) == 1
    assert us.NO_RECORD in capsys.readouterr().out


def test_compare_fails_on_a_dirty_checkout(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stored = _universe()
    _store(repo, stored)
    monkeypatch.setattr(gc, "_collect_universe_fresh", lambda target: stored)
    assert prestep.main(["compare"]) == 0, "control: the clean checkout compares equal"

    (repo / "stray.txt").write_text("untracked\n", encoding="utf-8")

    assert prestep.main(["compare"]) == 1


# ---------------------------------------------------------------------------
# consumers: which battery legs hold a test that requests the universe
# ---------------------------------------------------------------------------

_CONSUMER = "tests/architectural/test_consumes_universe.py"
_OTHER = "tests/architectural/test_does_not.py"
# Pinned on purpose: a new file that calls ``collect_universe()`` must be added here (a leg that
# holds it then runs the pre-test step), and a listed file that stops calling it must be removed.
_PINNED_CONSUMERS = frozenset(
    {
        "tests/architectural/test_fast_tier_marker_completeness.py",
        "tests/architectural/test_same_tier_uniqueness.py",
    }
)


@pytest.fixture
def partition(monkeypatch: pytest.MonkeyPatch) -> dict[str, frozenset[str]]:
    """A fake partition: leg 1/2 holds the consumer, leg 2/2 does not. The real one moves with the timings."""
    parts = {"1/2": frozenset({_CONSUMER, _OTHER}), "2/2": frozenset({_OTHER})}

    def part_files(name: str) -> frozenset[str]:
        if name not in parts:
            raise ValueError(f"unknown battery partition {name!r}; the registry defines {sorted(parts)}")
        return parts[name]

    monkeypatch.setattr(gc, "battery_part_files", part_files)
    monkeypatch.setattr(prestep, "universe_consumers", lambda root=None: frozenset({_CONSUMER}))
    return parts


def test_consumers_prints_true_for_a_part_that_holds_a_collecting_test(partition: dict[str, frozenset[str]], capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["consumers", "--battery-part", "1/2"]) == 0
    assert capsys.readouterr().out.strip() == "true"


def test_consumers_prints_false_for_a_part_without_one(partition: dict[str, frozenset[str]], capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["consumers", "--battery-part", "2/2"]) == 0
    assert capsys.readouterr().out.strip() == "false"


def test_consumers_fails_loudly_on_an_unknown_part_and_prints_no_answer(partition: dict[str, frozenset[str]], capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["consumers", "--battery-part", "3/2"]) != 0
    captured = capsys.readouterr()
    assert captured.out.strip() not in {"true", "false"}, "an error must never read as an answer"
    assert "3/2" in captured.err


def test_consumers_fails_on_an_unknown_part_of_the_real_registry(capsys: pytest.CaptureFixture[str]) -> None:
    assert prestep.main(["consumers", "--battery-part", "99/99"]) != 0
    assert capsys.readouterr().out.strip() == ""


def test_consumers_requires_the_part() -> None:
    with pytest.raises(SystemExit) as stopped:
        prestep.main(["consumers"])
    assert stopped.value.code == 2


def test_battery_part_applies_to_the_consumers_command_only() -> None:
    with pytest.raises(SystemExit) as stopped:
        prestep.main(["collect", "--battery-part", "1/2"])
    assert stopped.value.code == 2


def test_the_real_legs_answer_true_or_false_consistently_with_their_files(capsys: pytest.CaptureFixture[str]) -> None:
    consumers = prestep.universe_consumers()
    for part in ("1/2", "2/2"):
        assert prestep.main(["consumers", "--battery-part", part]) == 0
        expected = "true" if gc.battery_part_files(part) & consumers else "false"
        assert capsys.readouterr().out.strip() == expected, part


def _tests_dir(root: Path) -> Path:
    target = root / "tests" / "architectural"
    target.mkdir(parents=True)
    return target


@pytest.mark.parametrize(
    ("body", "consumes"),
    [
        ("from tests.architectural import _gate_coverage as gc\n\ndef test_a():\n    gc.collect_universe()\n", True),
        ("from tests.architectural._gate_coverage import collect_universe\n\ndef test_a():\n    collect_universe(caller='x')\n", True),
        ('"""Mentions collect_universe() in prose only."""\nSNIPPET = "gc.collect_universe()"\n', False),
        ("from tests.architectural import _gate_coverage as gc\n\nCALL = gc.collect_universe\n", False),
        ("def test_a():\n    pass\n", False),
    ],
    ids=["attribute call", "name call", "string and docstring mention", "reference without a call", "no mention"],
)
def test_the_scan_finds_a_call_and_nothing_else(tmp_path: Path, body: str, consumes: bool) -> None:
    (_tests_dir(tmp_path) / "test_sample.py").write_text(body, encoding="utf-8")
    found = prestep.universe_consumers(tmp_path)
    assert found == (frozenset({"tests/architectural/test_sample.py"}) if consumes else frozenset())


def test_the_scan_reads_test_files_of_the_architectural_directory_only(tmp_path: Path) -> None:
    call = "from tests.architectural import _gate_coverage as gc\n\ndef test_a():\n    gc.collect_universe()\n"
    architectural = _tests_dir(tmp_path)
    (architectural / "_helper.py").write_text(call, encoding="utf-8")
    (architectural / "test_universe_store.py").write_text(call, encoding="utf-8")
    (tmp_path / "tests" / "ci").mkdir()
    (tmp_path / "tests" / "ci" / "test_elsewhere.py").write_text(call, encoding="utf-8")
    (architectural / "test_real.py").write_text(call, encoding="utf-8")
    assert prestep.universe_consumers(tmp_path) == {"tests/architectural/test_real.py"}


def test_the_files_that_call_collect_universe_are_the_pinned_set() -> None:
    """Fails when a file starts calling ``collect_universe()`` without being listed, and when a listed file stops."""
    found = prestep.universe_consumers()
    unlisted, stale = sorted(found - _PINNED_CONSUMERS), sorted(_PINNED_CONSUMERS - found)
    assert found == _PINNED_CONSUMERS, f"unlisted callers: {unlisted}; listed files that no longer call it: {stale}"


def test_the_excluded_file_exists_and_only_fakes_the_collector() -> None:
    """The one excluded caller still exists (a rename would hide a real caller) and never collects for real."""
    for relpath in prestep.NOT_CONSUMERS:
        source = (gc.REPO_ROOT / relpath).read_text(encoding="utf-8")
        assert "collect_universe(" in source, f"{relpath} no longer calls collect_universe(); drop it from NOT_CONSUMERS"
        assert '"_collect_universe_fresh"' in source, f"{relpath} must replace the real collector"
