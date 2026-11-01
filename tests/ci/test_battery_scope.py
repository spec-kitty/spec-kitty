"""``scripts/ci/battery_scope.py`` (#6994): which gates one heavy battery leg runs for a diff.

The selection authority is ``gate_selection.select_battery_gates`` (its property is proven in
``tests/architectural/test_battery_scan_scope_routing.py``); these tests pin the CLI around it:
the diff read, the per-leg intersection, the ``$GITHUB_OUTPUT`` lines and the fail-safe paths.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ci import battery_scope as bs

pytestmark = [pytest.mark.fast]

_CLOCK_BANS = frozenset({"tests/architectural/test_clock_import_ban.py", "tests/architectural/test_clock_call_ban.py"})
_SCRIPT = "scripts/release/extract_changelog.py"  # imported by no battery file, so its diff is scoped
_PARTS = ("1/2", "2/2")


@pytest.mark.parametrize("paths", [None, ["src/specify_cli/status/store.py"], [_SCRIPT, "scripts/ci/gate_selection.py"]])
def test_no_diff_or_a_code_diff_runs_the_whole_leg(paths: list[str] | None) -> None:
    assert bs.decide(paths, part="1/2") == (bs.FULL, frozenset())


def test_full_mode_runs_the_whole_leg() -> None:
    assert bs.decide([_SCRIPT], part="1/2", mode="full") == (bs.FULL, frozenset())


def test_a_scripts_only_diff_scopes_both_legs_to_gates_that_include_the_clock_bans() -> None:
    answers = [bs.decide([_SCRIPT], part=part) for part in _PARTS]
    assert {mode for mode, _ in answers} == {bs.SCOPED}
    first, second = (gates for _, gates in answers)
    assert not first & second, "each selected gate runs in exactly one leg"
    assert first | second >= _CLOCK_BANS
    assert len(first | second) < 20, "a scripts-only diff must not run the battery wholesale"


def test_an_out_of_scope_diff_runs_nothing() -> None:
    assert bs.decide(["acceptance-jvm/build.gradle"], part="1/2") == (bs.SCOPED, frozenset())


def test_output_lines_full_and_scoped(tmp_path: Path) -> None:
    out = tmp_path / "gates.txt"
    assert bs.output_lines(bs.FULL, frozenset(), out) == ["mode=full", "run=true", "gates_file="]
    assert not out.exists()
    assert bs.output_lines(bs.SCOPED, frozenset({"b.py", "a.py"}), out) == ["mode=scoped", "run=true", f"gates_file={out}"]
    assert out.read_text(encoding="utf-8") == "a.py\nb.py\n"
    assert bs.output_lines(bs.SCOPED, frozenset(), out)[1] == "run=false"


@pytest.mark.parametrize("base", ["", "0" * 40])
def test_a_missing_or_null_base_has_no_diff(base: str) -> None:
    assert bs.changed_paths(base, "HEAD") is None


def test_an_unknown_base_has_no_diff() -> None:
    assert bs.changed_paths("f" * 40, "HEAD") is None


def test_the_diff_of_a_real_range_is_read(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.strip()

    git("init", "-q")
    git("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "--allow-empty", "-m", "base")
    base = git("rev-parse", "HEAD")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "head")
    assert bs.changed_paths(base, git("rev-parse", "HEAD"), repo=tmp_path) == ["scripts/x.py"]


def test_main_fails_safe_to_the_whole_leg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("selection broke")

    monkeypatch.setattr(bs, "decide", boom)
    assert bs.main(["select", "--base", "a", "--head", "b", "--battery-part", "1/2", "--out", str(tmp_path / "g.txt")]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["mode=full", "run=true", "gates_file="]
    assert "running the whole leg" in captured.err


def test_main_writes_a_scoped_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bs, "changed_paths", lambda *_args, **_kwargs: [_SCRIPT])
    out = tmp_path / "g.txt"
    assert bs.main(["select", "--base", "a", "--head", "b", "--battery-part", "1/2", "--out", str(out)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "mode=scoped" and lines[2] == f"gates_file={out}"
