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


# ---------------------------------------------------------------------------
# Prose-only exemption (#6999, operator ruling 2026-11-01): a proven prose-only
# diff still skips the battery as a whole, but the heavy gates that DECLARE the
# paths it touches must run. The prose verdict is an input (`--prose-only`),
# never re-derived here.
# ---------------------------------------------------------------------------

#: The declared `scripts/**` scanners a prose-only `scripts/release/` diff must keep: both clock
#: bans plus the guidance/retired-subsystem scanners. Named so the pin states the user-visible
#: value, not just "some set".
_PROSE_SCRIPT_SCANNERS = frozenset(
    {
        "tests/architectural/test_clock_call_ban.py",
        "tests/architectural/test_clock_import_ban.py",
        "tests/architectural/test_first_party_hosts_are_owned.py",
        "tests/architectural/test_no_deprecated_doctrine_command_in_guidance.py",
        "tests/architectural/test_no_retired_subsystems.py",
    }
)


def test_a_prose_only_scripts_diff_runs_the_declared_scanners_across_both_legs() -> None:
    answers = [bs.decide([_SCRIPT], part=part, prose_only=True) for part in _PARTS]
    assert {mode for mode, _ in answers} == {bs.SCOPED}, "a prose-only diff is never the whole leg"
    first, second = (gates for _, gates in answers)
    assert not first & second, "each selected gate runs in exactly one leg"
    assert first | second == _PROSE_SCRIPT_SCANNERS, "every declared scanner of the touched path runs, and no other gate"
    assert first | second >= _CLOCK_BANS


def test_a_prose_only_code_diff_never_widens_to_the_whole_battery() -> None:
    """Same fixture, both verdicts: prose narrows, code stays fail-closed whole-battery."""
    src_path = "src/specify_cli/cli/help_text.py"

    assert bs.decide([src_path], part="1/2") == (bs.FULL, frozenset())
    assert bs.decide([src_path], part="1/2", prose_only=True) == (bs.SCOPED, frozenset())


def test_a_prose_only_battery_code_helper_touch_does_not_force_the_whole_battery() -> None:
    """`prose_only` proves no executable change, so the helper rule must not widen it."""
    helper = "scripts/ci/gate_selection.py"

    assert bs.decide([helper], part="1/2") == (bs.FULL, frozenset())
    mode, gates = bs.decide([helper], part="1/2", prose_only=True)
    assert mode == bs.SCOPED
    assert gates <= _PROSE_SCRIPT_SCANNERS
    assert _CLOCK_BANS & (_PROSE_SCRIPT_SCANNERS & gates) or gates == frozenset()


def test_prose_only_does_not_change_the_fail_safe() -> None:
    """No trustworthy diff base is still the whole leg, prose verdict or not (NFR-001)."""
    assert bs.decide(None, part="1/2", prose_only=True) == (bs.FULL, frozenset())
    assert bs.decide(None, part="1/2") == (bs.FULL, frozenset())


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("TRUE", True), (" true ", True), ("false", False), ("", False), ("yes", False)])
def test_the_prose_only_flag_reads_the_prose_scan_output(raw: str, expected: bool) -> None:
    assert bs._flag(raw) is expected


def test_main_passes_the_prose_verdict_to_the_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: list[bool] = []
    real_decide = bs.decide

    def spy(*args: object, **kwargs: object) -> tuple[str, frozenset[str]]:
        seen.append(bool(kwargs.get("prose_only")))
        return real_decide(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(bs, "decide", spy)
    monkeypatch.setattr(bs, "changed_paths", lambda *_args, **_kwargs: [_SCRIPT])
    out = tmp_path / "g.txt"
    assert bs.main(["select", "--base", "a", "--head", "b", "--prose-only", "true", "--battery-part", "1/2", "--out", str(out)]) == 0
    assert seen == [True]
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "mode=scoped"
    assert out.read_text(encoding="utf-8").splitlines() and set(out.read_text(encoding="utf-8").splitlines()) <= _PROSE_SCRIPT_SCANNERS


# ---------------------------------------------------------------------------
# The prose-scan companion output (#6999): the battery `if:` must not name the
# `changes.arch_scan_scope` group a second time, or the #6994 planted control
# (drop the group's OR term) goes vacuous. The companion is the same parsed
# glob list, read by the job that already holds the diff.
# ---------------------------------------------------------------------------


def test_matches_declared_scan_scope_answers_for_the_router_group() -> None:
    from scripts.ci import gate_selection as gs

    assert gs.matches_declared_scan_scope([_SCRIPT]) is True, "scripts/release/** is a declared scan scope"
    assert gs.matches_declared_scan_scope(["docs/guides/anything.md"]) is True, "docs/** is a declared scan scope"
    assert gs.matches_declared_scan_scope(["acceptance-jvm/build.gradle"]) is False
    assert gs.matches_declared_scan_scope([]) is False
    assert gs.matches_declared_scan_scope([_SCRIPT, "acceptance-jvm/build.gradle"]) is True


def test_the_workflow_wiring_carries_the_prose_verdict_and_its_companion() -> None:
    """Static wiring pin (#6999): the plumbing between prose-scan, the battery `if:` and the step."""
    import yaml

    workflow = yaml.safe_load(bs._REPO_ROOT.joinpath(".github/workflows/ci-router.yml").read_text(encoding="utf-8"))
    prose_scan = workflow["jobs"]["prose-scan"]
    heavy = workflow["jobs"]["architectural-heavy"]

    assert prose_scan["outputs"]["prose_only"] == "${{ steps.scan.outputs.prose_only }}"
    assert prose_scan["outputs"]["scan_scope_match"] == "${{ steps.scan.outputs.scan_scope_match }}"
    scan_step = next(step for step in prose_scan["steps"] if step.get("id") == "scan")
    assert "matches_declared_scan_scope" in str(scan_step["run"]), "the companion must come from the single authority"
    assert 'echo "scan_scope_match=' in str(scan_step["run"])

    condition = str(heavy["if"])
    assert "needs.prose-scan.outputs.scan_scope_match == 'true'" in condition
    assert condition.count("needs.changes.outputs.arch_scan_scope") == 1, (
        "the battery if: must name the arch_scan_scope group exactly once, or the #6994 planted control goes vacuous"
    )

    scope_step = next(step for step in heavy["steps"] if step.get("id") == "scope")
    assert scope_step["env"]["PROSE_ONLY"] == "${{ needs.prose-scan.outputs.prose_only }}"
    assert '--prose-only "${PROSE_ONLY:-false}"' in str(scope_step["run"])
