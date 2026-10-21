"""``scripts/ci/validate_agent_skills.py``: the Agent Skills validator CI check (#6475, FR-015, SC-001).

Every test but one is offline: the reference validator is reached through an
injected command runner. The one test that runs the real ``skills-ref`` uses
``uvx --offline`` and is skipped when ``uvx`` or a cached ``skills-ref==0.1.1``
is unavailable (the per-worker test HOME starts with an empty uv cache, so point
``UV_CACHE_DIR`` at a warm cache to run it), so this module never needs the network.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts.ci import validate_agent_skills as vas
from specify_cli.skills.skill_frontmatter import _validate_skill_frontmatter

pytestmark = pytest.mark.fast

_LONG_NAME = "a" * 65
_GOOD = "---\nname: {name}\ndescription: Does a thing.\n---\n\n# Body\n"
_DOTTED = "---\nname: spec-kitty.plan\ndescription: Plan.\n---\n"
_EXTRA_KEY = "---\nname: spec-kitty-plan\ndescription: Plan.\nuser-invocable: true\n---\n"
_LONG = f"---\nname: {_LONG_NAME}\ndescription: Long.\n---\n"


def _skill(root: Path, folder: str, text: str) -> Path:
    skill_dir = root / folder
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
    return skill_dir


class _FakeReference:
    """A command runner standing in for ``uvx ... skills_ref``: answers from a fixed mapping."""

    def __init__(self, errors: dict[str, list[str]] | None = None, code: int = 0, stdout: str | None = None) -> None:
        self.errors = errors or {}
        self.code = code
        self.stdout = stdout
        self.calls: list[list[str]] = []

    def __call__(self, argv: Sequence[str]) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        folders = list(argv[list(argv).index(vas._REFERENCE_PROGRAM) + 1 :])
        out = self.stdout if self.stdout is not None else json.dumps({folder: self.errors.get(Path(folder).name, []) for folder in folders})
        return self.code, out, "boom" if self.code else ""


class _Mirror(_FakeReference):
    """A reference that agrees with the in-repo mirror (the real validator's behaviour on these inputs)."""

    def __call__(self, argv: Sequence[str]) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        folders = list(argv[list(argv).index(vas._REFERENCE_PROGRAM) + 1 :])
        return 0, json.dumps({folder: _validate_skill_frontmatter(Path(folder)) for folder in folders}), ""


# --- collection ------------------------------------------------------------------------------


def test_discover_classifies_shared_and_native_roots(tmp_path: Path) -> None:
    _skill(tmp_path / ".agents" / "skills", "a", _GOOD.format(name="a"))
    _skill(tmp_path / ".claude" / "skills", "b", _GOOD.format(name="b"))
    _skill(tmp_path / ".kittify" / "backup", "c", _GOOD.format(name="c"))  # not a skills root

    targets = vas.discover_skill_dirs(tmp_path, "project")

    assert [(t.label, t.shared) for t in targets] == [("project:.agents/skills/a", True), ("project:.claude/skills/b", False)]


def test_shipped_skills_are_projected_for_the_shared_root(tmp_path: Path) -> None:
    source = tmp_path / "src"
    _skill(source, "spk-load", '---\nname: spk-load\ndescription: Load.\nargument-hint: "[x]"\n---\n')

    targets = vas.project_shipped_skills(source, tmp_path / "out")

    assert [(t.label, t.shared) for t in targets] == [("shipped:spk-load", True)]
    projected = (tmp_path / "out" / "spk-load" / "SKILL.md").read_text(encoding="utf-8")
    assert "\nargument-hint" not in projected and "metadata:" in projected
    assert _validate_skill_frontmatter(targets[0].skill_dir) == []


def test_isolated_env_points_home_and_xdg_into_scratch(tmp_path: Path) -> None:
    env = vas.isolated_env(tmp_path, {"HOME": "/real", "XDG_CACHE_HOME": "/cache", "PATH": "/bin"})
    assert env["HOME"] == str(tmp_path)
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / ".config")
    assert env["XDG_DATA_HOME"] == str(tmp_path / ".local/share")
    assert env["XDG_STATE_HOME"] == str(tmp_path / ".local/state")
    assert env["XDG_CACHE_HOME"] == "/cache" and env["PATH"] == "/bin"


def test_init_command_runs_the_shared_and_a_native_agent() -> None:
    assert vas.init_command("py") == ["py", "-m", "specify_cli", "init", ".", "--ai", "codex,claude", "--non-interactive"]


def test_generate_project_runs_git_init_then_spec_kitty_init(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def run(argv: Sequence[str]) -> tuple[int, str, str]:
        calls.append(list(argv))
        return 0, "", ""

    project, home = vas.generate_project(tmp_path, run)

    assert (project, home) == (tmp_path / "project", tmp_path / "home")
    assert project.is_dir() and home.is_dir()
    assert calls[0] == ["git", "init", "-q"] and calls[1][-3:] == ["--ai", "codex,claude", "--non-interactive"]


def test_generate_project_refuses_a_failed_init(tmp_path: Path) -> None:
    with pytest.raises(vas.EnvironmentPreparationError, match="exited 3: nope"):
        vas.generate_project(tmp_path, lambda argv: (3, "", "nope"))


# --- validation: the seeded bad skills fail, a good one passes (T033) -----------------------


@pytest.mark.parametrize(
    ("folder", "text", "message"),
    [
        ("spec-kitty.plan", _DOTTED, "contains invalid characters"),
        ("spec-kitty-plan", _EXTRA_KEY, "Unexpected fields in frontmatter: user-invocable"),
        (_LONG_NAME, _LONG, "exceeds 64 character limit (65 chars)"),
    ],
)
def test_seeded_bad_shared_skill_fails_the_aggregate(tmp_path: Path, folder: str, text: str, message: str) -> None:
    good = vas.SkillTarget("project:.agents/skills/good", _skill(tmp_path, "good", _GOOD.format(name="good")), shared=True)
    bad = vas.SkillTarget(f"project:.agents/skills/{folder}", _skill(tmp_path, folder, text), shared=True)

    verdicts = vas.evaluate([good, bad], _Mirror())

    assert [v.failed for v in verdicts] == [False, True]
    assert not verdicts[1].disagreement
    report = vas.render_report(verdicts)
    assert f"FAIL {bad.label}" in report and message in report
    assert report.endswith("validated=2 shared=2 native=0 failed=1")


def test_good_skills_pass(tmp_path: Path) -> None:
    targets = [vas.SkillTarget(f"t:{n}", _skill(tmp_path, n, _GOOD.format(name=n)), shared=True) for n in ("one", "two")]
    verdicts = vas.evaluate(targets, _Mirror())
    assert not any(v.failed for v in verdicts)
    assert vas.render_report(verdicts) == "Agent Skills validation (skills-ref==0.1.1): validated=2 shared=2 native=0 failed=0"


def test_a_reference_only_violation_fails_as_a_disagreement(tmp_path: Path) -> None:
    target = vas.SkillTarget("t:one", _skill(tmp_path, "one", _GOOD.format(name="one")), shared=True)
    (verdict,) = vas.evaluate([target], _FakeReference({"one": ["something the mirror misses"]}))
    assert verdict.failed and verdict.disagreement
    assert "validators disagree" in vas.render_report([verdict])
    assert "skills-ref: something the mirror misses" in vas.render_report([verdict])


def test_an_in_repo_only_violation_fails_as_a_disagreement(tmp_path: Path) -> None:
    target = vas.SkillTarget("t:x", _skill(tmp_path, "spec-kitty.plan", _DOTTED), shared=True)
    (verdict,) = vas.evaluate([target], _FakeReference())
    assert verdict.failed and verdict.disagreement


def test_native_root_keeps_claude_keys_and_skips_the_reference(tmp_path: Path) -> None:
    native = vas.SkillTarget("project:.claude/skills/spec-kitty-plan", _skill(tmp_path, "spec-kitty-plan", _EXTRA_KEY), shared=False)
    reference = _FakeReference()

    (verdict,) = vas.evaluate([native], reference)

    assert not verdict.failed and verdict.reference is None
    assert reference.calls == []  # no shared folder: the reference is not run at all
    assert vas.render_report([verdict]).endswith("validated=1 shared=0 native=1 failed=0")


def test_native_root_still_refuses_a_dotted_name(tmp_path: Path) -> None:
    native = vas.SkillTarget("project:.claude/skills/spec-kitty.plan", _skill(tmp_path, "spec-kitty.plan", _DOTTED), shared=False)
    (verdict,) = vas.evaluate([native], _FakeReference())
    assert verdict.failed and not verdict.disagreement


# --- the reference call ----------------------------------------------------------------------


def test_reference_command_pins_skills_ref_and_passes_every_folder(tmp_path: Path) -> None:
    argv = vas.reference_command([tmp_path / "a", tmp_path / "b"], uvx="uvx")
    assert argv[:3] == ["uvx", "--from", "skills-ref==0.1.1"]
    assert argv[-2:] == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert "from skills_ref import validate" in vas._REFERENCE_PROGRAM


def test_run_reference_refuses_a_failed_run(tmp_path: Path) -> None:
    with pytest.raises(vas.EnvironmentPreparationError, match="exited 1: boom"):
        vas.run_reference([tmp_path], _FakeReference(code=1))


@pytest.mark.parametrize(("stdout", "message"), [("", "no JSON mapping"), ("not json", "no JSON result"), ("[]", "no JSON mapping"), ("{}", "skipped 1 folder")])
def test_run_reference_refuses_output_that_does_not_cover_every_folder(tmp_path: Path, stdout: str, message: str) -> None:
    with pytest.raises(vas.EnvironmentPreparationError, match=message):
        vas.run_reference([tmp_path], _FakeReference(stdout=stdout))


def test_parse_reference_output_reads_the_last_line(tmp_path: Path) -> None:
    stdout = "noise\n" + json.dumps({str(tmp_path): ["e"]})
    assert vas.parse_reference_output(stdout, [tmp_path]) == {tmp_path: ("e",)}


# --- entry point -----------------------------------------------------------------------------


def test_main_without_uvx_is_an_environment_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert vas.main([]) == 2
    assert "uvx is not on PATH" in capsys.readouterr().err


def _patch_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str, folder: str) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/uvx")
    monkeypatch.setattr(vas, "collect_targets", lambda _w, _s: [vas.SkillTarget(f"t:{folder}", _skill(tmp_path, folder, text), shared=True)])
    monkeypatch.setattr(vas, "_subprocess_runner", lambda: _Mirror())


def test_main_exits_1_on_a_violation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _patch_main(monkeypatch, tmp_path, _DOTTED, "spec-kitty.plan")
    assert vas.main([]) == 1
    assert "failed=1" in capsys.readouterr().out


def test_main_exits_0_when_every_skill_is_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_main(monkeypatch, tmp_path, _GOOD.format(name="good"), "good")
    assert vas.main([]) == 0


def test_main_reports_a_preparation_error(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/uvx")

    def refuse(_workdir: Path, _shipped: Path) -> list[vas.SkillTarget]:
        raise vas.EnvironmentPreparationError("`spec-kitty init` wrote no skill folder")

    monkeypatch.setattr(vas, "collect_targets", refuse)
    assert vas.main([]) == 2
    assert "wrote no skill folder" in capsys.readouterr().err


def test_collect_targets_refuses_an_init_that_wrote_no_skill(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(vas, "generate_project", lambda workdir: (workdir, workdir))
    with pytest.raises(vas.EnvironmentPreparationError, match="wrote no skill folder"):
        vas.collect_targets(tmp_path, tmp_path / "shipped")


def test_collect_targets_refuses_when_no_generated_skill_is_in_a_shared_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, home = tmp_path / "p", tmp_path / "h"
    _skill(home / ".claude" / "skills", "b", _GOOD.format(name="b"))
    shipped = tmp_path / "src"
    _skill(shipped, "c", _GOOD.format(name="c"))
    monkeypatch.setattr(vas, "generate_project", lambda _workdir: (project, home))
    with pytest.raises(vas.EnvironmentPreparationError, match="no shared-root skill folder"):
        vas.collect_targets(tmp_path / "w", shipped)


def test_collect_targets_refuses_an_empty_shipped_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, home = tmp_path / "p", tmp_path / "h"
    _skill(project / ".agents" / "skills", "a", _GOOD.format(name="a"))
    empty = tmp_path / "moved"
    empty.mkdir()
    monkeypatch.setattr(vas, "generate_project", lambda _workdir: (project, home))
    with pytest.raises(vas.EnvironmentPreparationError, match="no shipped skill found"):
        vas.collect_targets(tmp_path / "w", empty)


def test_collect_targets_orders_generated_before_shipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project, home = tmp_path / "p", tmp_path / "h"
    _skill(project / ".agents" / "skills", "a", _GOOD.format(name="a"))
    _skill(home / ".claude" / "skills", "b", _GOOD.format(name="b"))
    shipped = tmp_path / "src"
    _skill(shipped, "c", _GOOD.format(name="c"))
    monkeypatch.setattr(vas, "generate_project", lambda _workdir: (project, home))

    labels = [t.label for t in vas.collect_targets(tmp_path / "w", shipped)]

    assert labels == ["project:.agents/skills/a", "home:.claude/skills/b", "shipped:c"]


# --- the real reference validator, from the uv cache only ------------------------------------


def _offline_reference_available() -> bool:
    if shutil.which("uvx") is None:
        return False
    probe = subprocess.run(["uvx", "--offline", "--from", vas.REFERENCE_SPEC, "agentskills", "--help"], capture_output=True, check=False)
    return probe.returncode == 0


@pytest.mark.integration
def test_real_skills_ref_agrees_with_the_mirror_on_the_seeded_skills(tmp_path: Path) -> None:
    if not _offline_reference_available():
        # The isolated test HOME has an empty uv cache; export UV_CACHE_DIR to reuse a warm one.
        pytest.skip("uvx or a cached skills-ref==0.1.1 is unavailable (the test never downloads it; set UV_CACHE_DIR)")
    targets = [
        vas.SkillTarget("good", _skill(tmp_path, "good", _GOOD.format(name="good")), shared=True),
        vas.SkillTarget("dotted", _skill(tmp_path, "spec-kitty.plan", _DOTTED), shared=True),
        vas.SkillTarget("extra", _skill(tmp_path, "spec-kitty-plan", _EXTRA_KEY), shared=True),
        vas.SkillTarget("long", _skill(tmp_path, _LONG_NAME, _LONG), shared=True),
    ]

    def offline(argv: Sequence[str]) -> tuple[int, str, str]:
        completed = subprocess.run([argv[0], "--offline", *argv[1:]], capture_output=True, text=True, check=False)
        return completed.returncode, completed.stdout, completed.stderr

    verdicts = vas.evaluate(targets, offline)

    assert [v.failed for v in verdicts] == [False, True, True, True]
    assert not any(v.disagreement for v in verdicts)
