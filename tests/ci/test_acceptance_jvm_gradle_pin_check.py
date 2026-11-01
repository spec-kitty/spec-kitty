"""Unit cases of ``scripts/ci/acceptance_jvm_gradle_pin_check.py`` (#6915, research D-8).

The wrapper loads ``gradle_pin_check.py`` from the pinned ``contract-tools`` extra of spec-kitty-events and runs its
``check_acceptance_jvm(root)``: the released tool's bare run (``check_all``) also scans a ``contracts/`` subproject that core
no longer has. Every case here runs a fake ``gradle_pin_check.py`` the test plants itself; the real downloaded tool runs in
CI only (the nightly ``acceptance-bdd`` job).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.pinned_service_assets import contract_tools_dir, service_cache_root

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "acceptance_jvm_gradle_pin_check.py"

FAKE_TOOL = """
from dataclasses import dataclass, field
from pathlib import Path

calls = []


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def render(self):
        return f"CONTRACT-CHECK gradle_pin_check: {self.code}: {self.subject}: {self.detail}"


@dataclass
class Report:
    findings: list = field(default_factory=list)
    blocked: list = field(default_factory=list)
    counts: dict = field(default_factory=lambda: {"pinned": 2, "compared": 2})

    @property
    def exit_code(self):
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self):
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def check_acceptance_jvm(root):
    calls.append(Path(root))
    report = Report()
    outcome = (Path(root) / "outcome").read_text().strip() if (Path(root) / "outcome").exists() else "clean"
    if outcome == "mismatch":
        report.findings.append(Finding("GRADLE_PIN_MISMATCH", "acceptance-jvm/tools/pins.json", "gradle is 9.0 but pins.json pins 9.1"))
    if outcome == "blocked":
        report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", "acceptance-jvm/tools/pins.json", "unreadable"))
    return report


def check_all(root):
    raise AssertionError("the wrapper must never run the whole-repository scan")
"""


@pytest.fixture
def wrapper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("acceptance_jvm_gradle_pin_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    return module


def _planted_tools(tmp_path: Path) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gradle_pin_check.py").write_text(FAKE_TOOL, encoding="utf-8")
    return tools


def _root(tmp_path: Path, outcome: str | None) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    if outcome is not None:
        (root / "outcome").write_text(outcome, encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("outcome", "code", "rendered"),
    [
        (None, 0, []),
        ("mismatch", 1, ["CONTRACT-CHECK gradle_pin_check: GRADLE_PIN_MISMATCH: acceptance-jvm/tools/pins.json: gradle is 9.0 but pins.json pins 9.1"]),
        ("blocked", 2, ["CONTRACT-CHECK gradle_pin_check: GRADLE_PIN_UNREADABLE: acceptance-jvm/tools/pins.json: unreadable"]),
    ],
    ids=["clean", "mismatch", "blocked"],
)
def test_main_prints_like_the_tool_and_returns_its_exit_code(
    wrapper: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], outcome: str | None, code: int, rendered: list[str]
) -> None:
    root = _root(tmp_path, outcome)
    assert wrapper.main(["--root", str(root), "--tools-root", str(_planted_tools(tmp_path))]) == code
    assert capsys.readouterr().out.splitlines() == [*rendered, "counts: pinned=2 compared=2"]


def test_the_acceptance_jvm_check_gets_the_root_and_the_whole_repository_scan_never_runs(wrapper: ModuleType, tmp_path: Path) -> None:
    root = _root(tmp_path, None)
    tools = _planted_tools(tmp_path)
    tool = wrapper.load_tool(tools)
    assert wrapper.run(root, tool, out=lambda line: None) == 0
    assert tool.calls == [root]


def test_a_tools_root_without_the_tool_cannot_do_its_job(wrapper: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert wrapper.main(["--root", str(_root(tmp_path, None)), "--tools-root", str(empty)]) == wrapper.EXIT_UNAVAILABLE
    assert "gradle_pin_check.py" in capsys.readouterr().err


def test_the_default_tools_root_is_the_pinned_contract_tools_extra(wrapper: ModuleType) -> None:
    assert wrapper.default_tools_root(REPO_ROOT, cache_root=service_cache_root()) == contract_tools_dir()


def test_a_tools_extra_missing_from_the_cache_is_refused_with_its_service_code(wrapper: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(wrapper.ToolsUnavailable) as refused:
        wrapper.default_tools_root(REPO_ROOT, cache_root=tmp_path / "empty-cache")
    assert refused.value.code.startswith("SERVICE_")


def test_main_without_the_pinned_tools_exits_2_naming_the_code(
    wrapper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(repo_root: Path, cache_root: Path | None = None) -> Path:
        raise wrapper.ToolsUnavailable("SERVICE_BINARY_MISSING")

    monkeypatch.setattr(wrapper, "default_tools_root", missing)
    assert wrapper.main(["--root", str(_root(tmp_path, None))]) == wrapper.EXIT_UNAVAILABLE
    assert "SERVICE_BINARY_MISSING" in capsys.readouterr().err
