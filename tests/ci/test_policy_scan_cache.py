"""Cache reuse must preserve the live collection policy's content boundary."""

from pathlib import Path

import pytest
import yaml

from scripts.ci.policy_scan_cache import cache_key
from tests.ci._gh_expr import evaluate
from tests._support.wall_clock_assertions import find_wall_clock_assertion_violations_cached


@pytest.mark.parametrize("event", ["push", "schedule", "workflow_dispatch", "pull_request", "pull_request_target", "merge_group", "workflow_run"])
@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/heads/topic", "refs/pull/7/merge"])
def test_cross_run_policy_cache_is_never_read_or_written_from_a_pr(event: str, ref: str) -> None:
    root = Path(__file__).resolve().parents[2]
    action = yaml.safe_load((root / ".github/actions/policy-scan-cache/action.yml").read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    assert len(steps) == 2
    context = {"github.event_name": event, "github.ref": ref, "github.event.repository.default_branch": "main"}
    permitted = event in {"push", "schedule", "workflow_dispatch"} and ref == "refs/heads/main"
    for step in steps:
        assert evaluate(step["if"], context) is permitted


def _tree(root: Path) -> None:
    (root / "tests/_support").mkdir(parents=True)
    (root / "tests/test_probe.py").write_text("def test_probe(): assert True\n", encoding="utf-8")
    (root / "tests/_support/helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    for path in ("uv.lock", "pytest.ini", "pyproject.toml"):
        (root / path).write_text("initial", encoding="utf-8")


def test_policy_cache_is_content_not_commit_keyed(tmp_path: Path) -> None:
    _tree(tmp_path)
    before = cache_key(tmp_path)
    (tmp_path / "unrelated-source.py").write_text("changed", encoding="utf-8")
    assert cache_key(tmp_path) == before


@pytest.mark.parametrize("missing", ["uv.lock", "pytest.ini", "pyproject.toml"])
def test_policy_cache_refuses_missing_inputs(tmp_path: Path, missing: str) -> None:
    _tree(tmp_path)
    (tmp_path / missing).unlink()
    with pytest.raises(ValueError, match="missing policy-cache input"):
        cache_key(tmp_path)


def test_policy_cache_refuses_empty_tree(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="empty test tree"):
        cache_key(tmp_path)


def test_live_policy_still_validates_and_reports_cold_warm_and_mutated_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "test_probe.py"
    source.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")
    cache = tmp_path / "cache"
    monkeypatch.setenv("CI", "true")
    assert find_wall_clock_assertion_violations_cached([source], cache) == []
    assert "cache_hit=False" in capsys.readouterr().err
    assert find_wall_clock_assertion_violations_cached([source], cache) == []
    assert "cache_hit=True" in capsys.readouterr().err
    source.write_text("import time\ndef test_bad(): assert time.time() > 0\n", encoding="utf-8")
    violations = find_wall_clock_assertion_violations_cached([source], cache)
    assert len(violations) == 1
    assert violations[0].call == "time.time()"
    assert "cache_hit=False" in capsys.readouterr().err


def test_scanner_itself_invalidates_a_different_interpreter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from tests._support import wall_clock_assertions as scanner

    source = tmp_path / "test_probe.py"
    source.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")
    cache = tmp_path / "cache"
    monkeypatch.setenv("CI", "true")
    assert scanner.find_wall_clock_assertion_violations_cached([source], cache) == []
    capsys.readouterr()
    with monkeypatch.context() as changed_runtime:
        changed_runtime.setattr(scanner.sys, "version", "different interpreter")
        assert scanner.find_wall_clock_assertion_violations_cached([source], cache) == []
    assert "cache_hit=False" in capsys.readouterr().err


def test_policy_cache_invalidates_helpers_configs_lock_and_runtime(tmp_path: Path) -> None:
    _tree(tmp_path)
    for path in ("tests/test_probe.py", "tests/_support/helper.py", "uv.lock", "pytest.ini", "pyproject.toml"):
        before = cache_key(tmp_path)
        target = tmp_path / path
        target.write_text(target.read_text(encoding="utf-8") + "\n# modified\n", encoding="utf-8")
        assert cache_key(tmp_path) != before
    assert cache_key(tmp_path, runtime="one") != cache_key(tmp_path, runtime="two")


def test_policy_cache_detects_added_removed_and_renamed_sources(tmp_path: Path) -> None:
    _tree(tmp_path)
    before = cache_key(tmp_path)
    path = tmp_path / "tests/new_helper.py"
    path.write_text("VALUE = 2", encoding="utf-8")
    assert cache_key(tmp_path) != before
    added = cache_key(tmp_path)
    path.rename(tmp_path / "tests/other_helper.py")
    assert cache_key(tmp_path) != added
    (tmp_path / "tests/other_helper.py").unlink()
    assert cache_key(tmp_path) == before
