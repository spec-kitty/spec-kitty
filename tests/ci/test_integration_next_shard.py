"""``scripts/ci/integration_next_shard.py`` selects one deterministic, LPT-balanced file shard (#7456)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci import integration_next_shard as shard

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "ci" / "integration_next_shard.py"


def _tree(tmp_path: Path, names: dict[str, str]) -> Path:
    for rel in names:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return tmp_path


def _timings(tmp_path: Path, durations: dict[str, float]) -> Path:
    path = tmp_path / "timings.json"
    path.write_text(json.dumps({"battery_file_durations": {shard.SUITE: durations}}), encoding="utf-8")
    return path


def test_load_file_durations_reads_only_the_suite_table(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"battery_file_durations": {shard.SUITE: {"a.py": 2, "b.py": 3.5}, "architectural": {"c.py": 9}}}), encoding="utf-8")
    assert shard.load_file_durations(path) == {"a.py": 2.0, "b.py": 3.5}


@pytest.mark.parametrize(
    "payload", [None, [], {}, {"battery_file_durations": []}, {"battery_file_durations": {"other": {}}}, {"battery_file_durations": {shard.SUITE: []}}]
)
def test_load_file_durations_tolerates_a_missing_or_malformed_table(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "t.json"
    if payload is not None:
        path.write_text(json.dumps(payload), encoding="utf-8")
    assert shard.load_file_durations(path) == {}


def test_the_committed_timings_cover_the_live_tree() -> None:
    durations = shard.load_file_durations()
    from scripts.ci.shard_select import enumerate_base_files

    files = set(enumerate_base_files(shard.ROOTS, root=_REPO_ROOT))
    assert set(durations) <= files, f"stale timing keys: {sorted(set(durations) - files)[:5]}"
    assert len(files - set(durations)) <= len(files) // 10, (
        "the committed timings no longer cover the tree; recapture with capture_shard_timings.py --suite integration_next"
    )


def test_the_heaviest_files_are_spread_over_distinct_shards() -> None:
    durations = shard.load_file_durations()
    heaviest = sorted(durations, key=durations.__getitem__, reverse=True)[: shard.SHARD_COUNT]
    parts = shard.plan_shards(sorted(durations), durations, shard.SHARD_COUNT).parts
    owners = {next(key for key, owned in parts.items() if file in owned) for file in heaviest}
    assert len(owners) == shard.SHARD_COUNT


def test_shard_files_selects_the_shard_and_is_stable(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"tests/integration/test_a.py": "", "tests/integration/test_b.py": "", "tests/next/test_c.py": "", "tests/next/conftest.py": ""})
    timings = _timings(tmp_path, {"tests/integration/test_a.py": 10.0, "tests/integration/test_b.py": 1.0, "tests/next/test_c.py": 1.0})
    first, partition = shard.shard_files("1/2", root=root, timings_path=timings)
    second, _ = shard.shard_files("2/2", root=root, timings_path=timings)
    assert first == ("tests/integration/test_a.py",)
    assert second == ("tests/integration/test_b.py", "tests/next/test_c.py")
    assert set(first).isdisjoint(second)
    assert partition.loads == {"1/2": 10.0, "2/2": 2.0}


def test_untimed_new_file_is_owned_exactly_once_and_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path, {"tests/integration/test_a.py": "", "tests/integration/test_new.py": ""})
    timings = _timings(tmp_path, {"tests/integration/test_a.py": 5.0, "tests/integration/stale.py": 1.0})
    codes = [shard.main(["--shard", f"{n}/2", "--out", str(tmp_path / f"o{n}"), "--root", str(root), "--timings", str(timings)]) for n in (1, 2)]
    owned = [(tmp_path / f"o{n}").read_text(encoding="utf-8").split() for n in (1, 2)]
    assert codes == [0, 0] and sorted(sum(owned, [])) == ["tests/integration/test_a.py", "tests/integration/test_new.py"]
    assert "median" in capsys.readouterr().out


def test_main_writes_one_path_per_line_and_creates_the_parent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path, {"tests/integration/test_a.py": "", "tests/next/test_c.py": ""})
    out = tmp_path / "deep" / "dir" / "shard.args"
    assert shard.main(["--shard", "1/1", "--out", str(out), "--root", str(root), "--timings", str(tmp_path / "none.json")]) == 0
    assert out.read_text(encoding="utf-8") == "tests/integration/test_a.py\ntests/next/test_c.py\n"
    assert "shard 1/1 owns 2 of 2 files" in capsys.readouterr().out


def test_an_empty_shard_fails_closed_without_writing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path, {"tests/integration/test_a.py": ""})
    out = tmp_path / "empty.args"
    assert shard.main(["--shard", "2/2", "--out", str(out), "--root", str(root), "--timings", str(tmp_path / "none.json")]) == shard.EXIT_NO_TESTS
    assert not out.exists()
    assert "::error::integration-next-shard: shard 2/2 owns no test file" in capsys.readouterr().out


def test_an_empty_universe_fails_closed(tmp_path: Path) -> None:
    assert shard.main(["--shard", "1/2", "--out", str(tmp_path / "x"), "--root", str(tmp_path), "--timings", str(tmp_path / "none.json")]) == shard.EXIT_NO_TESTS


@pytest.mark.parametrize("spec", ["0/4", "5/4", "1", "a/b", "1/0"])
def test_a_malformed_shard_is_a_usage_error(tmp_path: Path, spec: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert shard.main(["--shard", spec, "--out", str(tmp_path / "x")]) == shard.EXIT_USAGE
    assert "::error::integration-next-shard:" in capsys.readouterr().out


def test_the_script_runs_under_a_bare_python_and_documents_itself() -> None:
    """The nightly runs it with the runner's own ``python3`` (no repo root on ``sys.path``)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    result = subprocess.run([sys.executable, "-I", str(_SCRIPT), "--help"], capture_output=True, text=True, env=env, check=False, cwd="/")
    assert result.returncode == 0, result.stderr
    assert "--shard" in result.stdout and "--out" in result.stdout
