"""Unit tests for ``scripts/ci/memory_sampler.py`` (WP11, NFR-005).

The sampler records the peak of ``MemTotal - MemAvailable`` over a CI job and
prints one parseable report line. These tests pin its behaviour with fake
``/proc`` and cgroup trees under ``tmp_path`` (never the real ``/proc``), and
avoid wall-clock assertions: every wait is bounded by an iteration count.

The module is loaded by file path (``scripts/ci`` has no ``__init__.py``),
mirroring ``tests/ci/test_release_nightly_gate.py``.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "memory_sampler.py"
_SCRIPT_MODULE_NAME = "memory_sampler"

_KIB = 1024
_GIB = 1024**3
_CGROUP_LINE = "0::/system.slice/x.scope\n"
_CGROUP_REL = Path("system.slice") / "x.scope"

#: Populated by the autouse ``_memory_sampler_module`` fixture below.
mod: ModuleType


@pytest.fixture(scope="module", autouse=True)
def _memory_sampler_module() -> Iterator[ModuleType]:
    """Load the script once for this module's tests.

    ``@dataclass`` resolves its module through ``sys.modules``, so the module
    must be registered before ``exec_module`` runs. A module-scoped
    ``MonkeyPatch.context()`` undoes that registration afterwards.
    """
    global mod
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_SCRIPT_MODULE_NAME, _SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _SCRIPT_MODULE_NAME, module)
        spec.loader.exec_module(module)
        mod = module
        yield module


class FakeProc:
    """Paths of a fake ``/proc`` + ``/sys`` tree rooted in ``tmp_path``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.proc = root / "proc"
        self.sys_root = root

    def write_meminfo(self, total_kb: int, available_kb: int) -> None:
        self.proc.mkdir(parents=True, exist_ok=True)
        (self.proc / "meminfo").write_text(
            f"MemTotal:       {total_kb} kB\nMemFree:          1234 kB\nMemAvailable:   {available_kb} kB\nBuffers:           100 kB\n",
            encoding="utf-8",
        )

    def write_cgroup(self, line: str = _CGROUP_LINE, peak: str | None = None) -> None:
        (self.proc / "self").mkdir(parents=True, exist_ok=True)
        (self.proc / "self" / "cgroup").write_text(line, encoding="utf-8")
        if peak is not None:
            peak_dir = self.root / "sys" / "fs" / "cgroup" / _CGROUP_REL
            peak_dir.mkdir(parents=True, exist_ok=True)
            (peak_dir / "memory.peak").write_text(peak, encoding="utf-8")


@pytest.fixture
def fake_proc(tmp_path: Path) -> FakeProc:
    fake = FakeProc(tmp_path)
    fake.write_meminfo(total_kb=16 * 1024 * 1024, available_kb=12 * 1024 * 1024)
    return fake


def _state(**overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "baseline_bytes": 1 * _GIB,
        "peak_bytes": 3 * _GIB,
        "samples": 4,
        "elapsed_seconds": 12.34,
        "source": "meminfo",
        "pid": 4242,
    }
    fields.update(overrides)
    return mod.SamplerState(**fields)


# ---------------------------------------------------------------------------
# Pure layer
# ---------------------------------------------------------------------------


def test_parse_meminfo_reads_total_and_available_in_bytes() -> None:
    text = "Cached:  5 kB\nMemTotal:   16384   kB\nMemFree: 1 kB\nMemAvailable:\t  8192 kB\nSwapTotal: 9 kB\n"
    info = mod.parse_meminfo(text)
    assert info == mod.MemInfo(total_bytes=16384 * _KIB, available_bytes=8192 * _KIB)


@pytest.mark.parametrize(
    "text",
    [
        "MemTotal: 100 kB\nMemFree: 50 kB\n",  # no MemAvailable: never guess from MemFree
        "MemAvailable: 100 kB\n",  # no MemTotal
        "MemTotal: lots kB\nMemAvailable: 1 kB\n",  # non-integer
        "",
    ],
)
def test_parse_meminfo_without_memavailable_is_unavailable(text: str) -> None:
    assert mod.parse_meminfo(text) is None


def test_used_bytes_is_total_minus_available() -> None:
    info = mod.MemInfo(total_bytes=16 * _GIB, available_bytes=10 * _GIB)
    assert mod.used_bytes(info) == 6 * _GIB


def test_peak_tracking_keeps_the_maximum_and_the_baseline() -> None:
    first = mod.initial_state(pid=7)
    assert first.samples == 0
    assert first.source == "unavailable"

    s1 = mod.update(first, 2 * _GIB, 0.0)
    s2 = mod.update(s1, 5 * _GIB, 1.0)
    s3 = mod.update(s2, 3 * _GIB, 2.0)

    assert s3.baseline_bytes == 2 * _GIB
    assert s3.peak_bytes == 5 * _GIB
    assert s3.peak_bytes - s3.baseline_bytes == 3 * _GIB
    assert s3.samples == 3
    assert s3.elapsed_seconds == 2.0
    assert s3.source == "meminfo"
    assert s3.pid == 7
    # immutable: earlier values are untouched by later updates
    assert (first.samples, s1.peak_bytes, s2.samples) == (0, 2 * _GIB, 2)
    with pytest.raises(AttributeError):
        s3.peak_bytes = 0


def test_state_json_round_trip_and_shape_validation() -> None:
    state = _state()
    assert mod.from_json(mod.to_json(state)) == state
    for bad in ("not json", "[]", '{"baseline_bytes": 1}', json.dumps({**json.loads(mod.to_json(state)), "samples": "x"})):
        assert mod.from_json(bad) is None


def test_cgroup_peak_path_from_unified_hierarchy_line(tmp_path: Path) -> None:
    path = mod.cgroup_peak_path(_CGROUP_LINE, tmp_path)
    assert path == tmp_path / "sys" / "fs" / "cgroup" / "system.slice" / "x.scope" / "memory.peak"


@pytest.mark.parametrize(
    "line",
    ["", "12:memory:/docker/abc\n1:name=systemd:/x\n", "0::/../../etc\n"],
)
def test_cgroup_peak_path_rejects_non_unified_or_escaping_lines(tmp_path: Path, line: str) -> None:
    assert mod.cgroup_peak_path(line, tmp_path) is None


def test_cgroup_peak_absent_or_unreadable_is_none(tmp_path: Path) -> None:
    assert mod.read_int_file(tmp_path / "missing") is None
    garbage = tmp_path / "garbage"
    garbage.write_text("max\n", encoding="utf-8")
    assert mod.read_int_file(garbage) is None
    assert mod.read_int_file(tmp_path) is None  # a directory is unreadable, not an error
    good = tmp_path / "good"
    good.write_text("987654321\n", encoding="utf-8")
    assert mod.read_int_file(good) == 987654321


def test_render_report_line_contract() -> None:
    lines = mod.render_report(_state(), 777, warn_bytes=10 * _GIB, error_bytes=12 * _GIB)
    assert lines == [f"peak_rss_bytes={3 * _GIB} source=meminfo baseline_bytes={1 * _GIB} delta_bytes={2 * _GIB} samples=4 elapsed_s=12.3 cgroup_peak_bytes=777"]

    na = mod.render_report(_state(), None, warn_bytes=10 * _GIB, error_bytes=12 * _GIB)
    assert na[0].endswith("cgroup_peak_bytes=na")

    empty = mod.render_report(mod.initial_state(pid=0), None, warn_bytes=10 * _GIB, error_bytes=12 * _GIB)
    assert empty[0] == "peak_rss_bytes=0 source=unavailable baseline_bytes=0 delta_bytes=0 samples=0 elapsed_s=0.0 cgroup_peak_bytes=na"


def test_report_line_is_parseable_by_a_key_value_split() -> None:
    line = mod.render_report(_state(), 5, warn_bytes=10 * _GIB, error_bytes=12 * _GIB)[0]
    pairs = [token.split("=", 1) for token in line.split(" ")]
    assert tuple(key for key, _ in pairs) == mod.REPORT_KEYS
    values = dict(pairs)
    for key in ("peak_rss_bytes", "baseline_bytes", "delta_bytes", "samples", "cgroup_peak_bytes"):
        assert int(values[key]) >= 0
    assert values["source"] in {"meminfo", "unavailable"}
    assert float(values["elapsed_s"]) >= 0.0


def test_threshold_annotations() -> None:
    """Boundaries are exact: GiB = 1024**3 bytes; warn at >= 10 GiB, error at >= 12 GiB."""
    warn, error = 10 * _GIB, 12 * _GIB

    def annotations(peak: int) -> list[str]:
        lines: list[str] = mod.render_report(_state(peak_bytes=peak), None, warn_bytes=warn, error_bytes=error)
        return lines[1:]

    assert annotations(warn - 1) == []
    at_warn = annotations(warn)
    assert len(at_warn) == 1 and at_warn[0].startswith("::warning title=memory sampler::")
    just_below_error = annotations(error - 1)
    assert len(just_below_error) == 1 and just_below_error[0].startswith("::warning title=memory sampler::")
    at_error = annotations(error)
    assert len(at_error) == 1 and at_error[0].startswith("::error title=memory sampler::")


def test_summary_line_is_a_single_human_line() -> None:
    line = mod.summary_line(_state(), 2 * _GIB)
    assert "\n" not in line
    assert "3.00 GiB" in line and "NFR-005" in line


def test_step_summary_line_appended_when_env_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    summary = tmp_path / "summary.md"
    summary.write_text("existing\n", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(mod.to_json(_state()), encoding="utf-8")
    fake = FakeProc(tmp_path)
    fake.write_meminfo(total_kb=16 * _KIB * _KIB, available_kb=15 * _KIB * _KIB)

    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = ["stop", "--out", str(state_path), "--proc-root", str(fake.proc), "--sys-root", str(fake.sys_root)]
    assert mod.main(argv) == 0
    lines = summary.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "existing"
    assert len(lines) == 2 and "NFR-005" in lines[1]

    monkeypatch.delenv("GITHUB_STEP_SUMMARY")
    before = summary.read_text(encoding="utf-8")
    assert mod.main(argv) == 0
    assert summary.read_text(encoding="utf-8") == before
    capsys.readouterr()


# ---------------------------------------------------------------------------
# Edge layer
# ---------------------------------------------------------------------------


def test_sample_loop_writes_state_atomically(tmp_path: Path, fake_proc: FakeProc) -> None:
    out = tmp_path / "state.json"
    argv = [
        "sample",
        "--out",
        str(out),
        "--interval",
        "0",
        "--max-samples",
        "3",
        "--proc-root",
        str(fake_proc.proc),
    ]
    assert mod.main(argv) == 0
    state = mod.from_json(out.read_text(encoding="utf-8"))
    assert state is not None
    assert state.samples == 3
    assert state.peak_bytes == 4 * _GIB  # 16 GiB total - 12 GiB available
    assert state.source == "meminfo"
    # tmp file + os.replace leaves no partial/temporary sibling behind
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("state.json")) == ["state.json"]


def _pid_gone(pid: int) -> bool:
    """True when ``pid`` no longer runs (a zombie awaiting its reaper counts as gone)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return True
    return stat.rsplit(")", 1)[1].split()[0] == "Z"


def _poll(predicate: Callable[[], bool], *, attempts: int = 100, pause: float = 0.02) -> bool:
    for _ in range(attempts):
        if predicate():
            return True
        time.sleep(pause)
    return predicate()


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.ci.memory_sampler", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_start_then_stop_round_trip(tmp_path: Path, fake_proc: FakeProc) -> None:
    out = tmp_path / "ms.json"
    common = ["--out", str(out), "--proc-root", str(fake_proc.proc), "--sys-root", str(fake_proc.sys_root)]

    started = _cli("start", "--interval", "0.05", *common)
    assert started.returncode == 0, started.stderr
    assert started.stdout.startswith("memory_sampler started pid=")
    pid = int((tmp_path / "ms.json.pid").read_text(encoding="utf-8").strip())
    try:
        assert _poll(out.exists), "sampler never wrote its state file"
        stopped = _cli("stop", *common)
    finally:
        if not _pid_gone(pid):
            os.kill(pid, 9)

    assert stopped.returncode == 0, stopped.stderr
    report = [ln for ln in stopped.stdout.splitlines() if ln.startswith("peak_rss_bytes=")]
    assert len(report) == 1
    assert f"peak_rss_bytes={4 * _GIB} source=meminfo" in report[0]
    assert _poll(lambda: _pid_gone(pid)), "sampler child still running after stop"


def test_stop_without_start_degrades_to_a_warning_and_exit_zero(tmp_path: Path, fake_proc: FakeProc) -> None:
    result = _cli("stop", "--out", str(tmp_path / "never-started.json"), "--proc-root", str(fake_proc.proc))
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert sum(ln.startswith("::warning") for ln in lines) == 1
    assert any(ln.startswith("peak_rss_bytes=0 source=unavailable") for ln in lines)


def test_stop_reports_error_annotation_without_failing_the_job(tmp_path: Path, fake_proc: FakeProc, capsys: pytest.CaptureFixture[str]) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(mod.to_json(_state(peak_bytes=13 * _GIB, pid=0)), encoding="utf-8")
    argv = ["stop", "--out", str(state_path), "--proc-root", str(fake_proc.proc), "--sys-root", str(fake_proc.sys_root)]
    assert mod.main(argv) == 0
    out = capsys.readouterr().out
    assert out.count("::error title=memory sampler::") == 1
    assert "::warning title=memory sampler::" not in out


def test_stop_reads_cgroup_peak_when_available(tmp_path: Path, fake_proc: FakeProc, capsys: pytest.CaptureFixture[str]) -> None:
    fake_proc.write_cgroup(peak="123456\n")
    state_path = tmp_path / "state.json"
    state_path.write_text(mod.to_json(_state(pid=0)), encoding="utf-8")
    argv = ["stop", "--out", str(state_path), "--proc-root", str(fake_proc.proc), "--sys-root", str(fake_proc.sys_root)]
    assert mod.main(argv) == 0
    assert "cgroup_peak_bytes=123456" in capsys.readouterr().out


def test_stop_with_corrupt_state_degrades_to_a_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{truncated", encoding="utf-8")
    assert mod.main(["stop", "--out", str(state_path), "--proc-root", str(tmp_path / "nope")]) == 0
    out = capsys.readouterr().out
    assert "::warning" in out and "peak_rss_bytes=0 source=unavailable" in out


def test_start_degrades_to_a_warning_when_spawn_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("no fork for you")

    monkeypatch.setattr(mod.subprocess, "Popen", boom)
    assert mod.main(["start", "--out", str(tmp_path / "ms.json")]) == 0
    assert capsys.readouterr().out.startswith("::warning")


def test_sample_without_meminfo_reports_unavailable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "state.json"
    argv = ["sample", "--out", str(out), "--interval", "0", "--max-samples", "2", "--proc-root", str(tmp_path / "nope")]
    assert mod.main(argv) == 0
    state = mod.from_json(out.read_text(encoding="utf-8"))
    assert state is not None and state.samples == 0 and state.source == "unavailable"
    capsys.readouterr()


def test_module_is_stdlib_only() -> None:
    """The sampler runs on the runner's system ``python3`` before ``uv sync``."""
    tree = ast.parse(_SCRIPT_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])
    assert imported, "expected at least one import"
    assert imported <= set(sys.stdlib_module_names), imported - set(sys.stdlib_module_names)
