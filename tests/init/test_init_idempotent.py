"""T1.5 — Regression tests: init idempotency on re-run.

Verifies:
- Running init twice in the same directory exits 0 (idempotent).
- The second run does NOT silently merge or overwrite state.
- A clear "Already initialized" message appears (in the injected console output).
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]


def test_initialized_clone_diagnoses_missing_codex_skills(monkeypatch, tmp_path):
    """An initialized clone can lack every gitignored command skill (#4425)."""
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [codex]\n", encoding="utf-8")
    mission = tmp_path / "kitty-specs/existing/spec.md"
    mission.parent.mkdir(parents=True)
    mission.write_text("Keep existing mission", encoding="utf-8")
    third_party = tmp_path / ".agents/skills/custom/SKILL.md"
    third_party.parent.mkdir(parents=True)
    third_party.write_text("Keep custom skill", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--non-interactive"])
    assert result.exit_code == 1
    assert "spec-kitty agent config sync --create-missing --keep-orphaned" in " ".join(buf.getvalue().split())
    assert not (tmp_path / ".agents/skills/spec-kitty.specify").exists()
    assert config.read_text() == "agents:\n  available: [codex]\n"
    assert mission.read_text() == "Keep existing mission"
    assert third_party.read_text() == "Keep custom skill"


def test_initialized_clone_manual_recovery_and_repeat(monkeypatch, tmp_path):
    import subprocess
    from specify_cli.cli.commands.agent.config import app as config_app

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [codex]\n")
    monkeypatch.chdir(tmp_path)
    app, _ = _make_app_with_buf()
    assert _run(app, ["init", "--non-interactive"]).exit_code == 1
    recovered = CliRunner().invoke(config_app, ["sync", "--create-missing", "--keep-orphaned"])
    assert recovered.exit_code == 0, recovered.output
    for command in ("specify", "plan", "tasks"):
        assert (tmp_path / f".agents/skills/spec-kitty.{command}/SKILL.md").stat().st_size > 0
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    for _ in range(2):
        assert _run(app, ["init", "--non-interactive"]).exit_code == 0
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize("selection", [["--ai", "codex"], ["--ai", "CODEX;codex"]])
def test_initialized_clone_explicit_selection_repairs_and_repeats(monkeypatch, tmp_path, selection):
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [codex]\n")
    monkeypatch.chdir(tmp_path)
    app, _ = _make_app_with_buf()
    assert _run(app, ["init", "--non-interactive", *selection]).exit_code == 0
    for command in ("specify", "plan", "tasks"):
        assert (tmp_path / f".agents/skills/spec-kitty.{command}/SKILL.md").stat().st_size > 0
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    for _ in range(2):
        assert _run(app, ["init", "--non-interactive", *selection]).exit_code == 0
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


@pytest.mark.parametrize(
    "selection,expected",
    [
        ("codex", "spec-kitty agent config add codex"),
        ("invalid", "Invalid AI assistant(s)"),
        (",;", "--ai flag did not contain any valid agent identifiers"),
    ],
)
def test_initialized_clone_rejects_unconfigured_selection(monkeypatch, tmp_path, selection, expected):
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [claude]\n")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", selection, "--non-interactive"])
    assert result.exit_code == 1
    assert expected in " ".join(buf.getvalue().split())
    assert config.read_text() == "agents:\n  available: [claude]\n"
    assert not (tmp_path / ".agents").exists()


@pytest.mark.parametrize("agent", ["codex", "vibe", "pi", "letta"])
@pytest.mark.parametrize("broken", ["empty", "symlink", "directory"])
def test_initialized_clone_rejects_unusable_skills(monkeypatch, tmp_path, agent, broken):
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text(f"agents:\n  available: [{agent}]\n")
    for command in CANONICAL_COMMANDS:
        path = tmp_path / f".agents/skills/spec-kitty.{command}/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Preserve user-edited skill")
    target = tmp_path / ".agents/skills/spec-kitty.specify/SKILL.md"
    target.unlink()
    if broken == "empty":
        target.touch()
    elif broken == "symlink":
        target.symlink_to(config)
    else:
        target.mkdir()
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    assert _run(app, ["init", "--non-interactive"]).exit_code == 1
    assert "config sync" in " ".join(buf.getvalue().split())
    assert (tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md").read_text() == "Preserve user-edited skill"
    assert config.read_text() == f"agents:\n  available: [{agent}]\n"


def _seed_vibe_clone(project: Path) -> None:
    """Seed an initialized vibe clone whose managed skills are present (#4433).

    ``command_installer.install`` builds the shared skill surface and its
    manifest but not the ``.vibe/config.toml`` pointer — the exact asymmetry
    this issue closes: the pointer is an independently missable, gitignored
    part of the surface, present skills notwithstanding.
    """
    import subprocess

    from specify_cli.skills import command_installer

    subprocess.run(["git", "init", "-q", str(project)], check=True)
    config = project / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [vibe]\n", encoding="utf-8")
    command_installer.install(project, "vibe")
    assert not (project / ".vibe/config.toml").exists()


def test_initialized_clone_diagnoses_missing_vibe_skill_path_pointer(monkeypatch, tmp_path):
    """Skills present + vibe pointer absent is a broken surface, not ready (#4433).

    Doctor already treats the ``.vibe/config.toml`` ``skill_paths`` pointer as
    an independently missable part of the vibe command surface; init's
    "Already Initialized" exit 0 must not disagree with it.
    """
    _seed_vibe_clone(tmp_path)
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--non-interactive"])
    assert result.exit_code == 1
    flattened = " ".join(buf.getvalue().split())
    assert "vibe skill-path pointer" in flattened
    assert ".vibe/config.toml" in flattened
    assert "spec-kitty agent config sync --create-missing --keep-orphaned" in flattened
    # Diagnosis only — the missing pointer and project state are untouched.
    assert not (tmp_path / ".vibe/config.toml").exists()
    assert (tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md").is_file()
    assert (tmp_path / ".kittify/config.yaml").read_text() == "agents:\n  available: [vibe]\n"


def test_initialized_clone_vibe_pointer_recovery_and_repeat(monkeypatch, tmp_path):
    """The recommended recovery command clears the pointer gap; init then exits 0."""
    from specify_cli.cli.commands.agent.config import app as config_app

    _seed_vibe_clone(tmp_path)
    monkeypatch.chdir(tmp_path)
    app, _ = _make_app_with_buf()
    assert _run(app, ["init", "--non-interactive"]).exit_code == 1
    recovered = CliRunner().invoke(config_app, ["sync", "--create-missing", "--keep-orphaned"])
    assert recovered.exit_code == 0, recovered.output
    pointer = tmp_path / ".vibe/config.toml"
    assert pointer.is_file()
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    for _ in range(2):
        assert _run(app, ["init", "--non-interactive"]).exit_code == 0
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


def test_initialized_clone_explicit_vibe_restores_pointer_only(monkeypatch, tmp_path):
    """An explicit ``--ai vibe`` restores the pointer surgically (#4433).

    Present managed skills are never re-run through the installer just to
    repair the pointer.
    """
    _seed_vibe_clone(tmp_path)
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = _run(app, ["init", "--non-interactive", "--ai", "vibe"])
    assert result.exit_code == 0, buf.getvalue()
    assert (tmp_path / ".vibe/config.toml").is_file()
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    # The pointer is the only managed-surface addition; protect_all_agents()
    # may also (re)write .gitignore, which is its documented job.
    assert set(after) - set(before) <= {Path(".vibe/config.toml"), Path(".gitignore")}
    assert {k: v for k, v in after.items() if k not in (Path(".vibe/config.toml"), Path(".gitignore"))} == {
        k: v for k, v in before.items() if k != Path(".gitignore")
    }


@pytest.mark.parametrize("agent", ["claude", "qwen", "kilocode"])
def test_initialized_clone_restores_native_agent_skills(monkeypatch, tmp_path, agent):
    """A clone re-run restores the gitignored NATIVE skill root (#4425)."""
    import subprocess

    from specify_cli.core.config import AGENT_SKILL_CONFIG
    from specify_cli.skills.registry import SkillRegistry

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text(f"agents:\n  available: [{agent}]\n", encoding="utf-8")
    mission = tmp_path / "kitty-specs/existing/spec.md"
    mission.parent.mkdir(parents=True)
    mission.write_text("Keep existing mission", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", agent, "--non-interactive"])
    assert result.exit_code == 0, buf.getvalue()
    skills = SkillRegistry.from_package().discover_skills()
    assert skills, "packaged skill registry is empty"
    root = AGENT_SKILL_CONFIG[agent]["skill_roots"][0]
    for skill in skills:
        assert (tmp_path / root / skill.name / "SKILL.md").stat().st_size > 0
    assert config.read_text() == f"agents:\n  available: [{agent}]\n"
    assert mission.read_text() == "Keep existing mission"
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    app2, buf2 = _make_app_with_buf()
    assert _run(app2, ["init", "--ai", agent, "--non-interactive"]).exit_code == 0, buf2.getvalue()
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert after == before


def test_initialized_clone_restore_preserves_user_skills(monkeypatch, tmp_path):
    """The NATIVE restore is additive: existing files are never overwritten (#4425 acceptance 3)."""
    import subprocess

    from specify_cli.skills.registry import SkillRegistry

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [claude]\n", encoding="utf-8")
    third_party = tmp_path / ".claude/skills/custom-tool/SKILL.md"
    third_party.parent.mkdir(parents=True)
    third_party.write_text("Keep custom skill", encoding="utf-8")
    edited = tmp_path / ".claude/skills/spec-kitty/SKILL.md"
    edited.parent.mkdir(parents=True)
    edited.write_text("Keep user-edited skill", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 0, buf.getvalue()
    assert third_party.read_text() == "Keep custom skill"
    assert edited.read_text() == "Keep user-edited skill"
    for skill in SkillRegistry.from_package().discover_skills():
        if skill.name in {"custom-tool", "spec-kitty"}:
            continue
        assert (tmp_path / ".claude/skills" / skill.name / "SKILL.md").stat().st_size > 0


@pytest.mark.parametrize("agent", ["claude", "qwen"])
def test_initialized_clone_restore_rejects_unsafe_roots(monkeypatch, tmp_path, agent):
    """An unsafe per-agent root fails closed without writing anything (#4425)."""
    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text(f"agents:\n  available: [{agent}]\n", encoding="utf-8")
    root = {"claude": ".claude", "qwen": ".qwen"}[agent]
    (tmp_path / root).write_text("not a directory", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--non-interactive"])
    assert result.exit_code == 1
    assert "Initialization incomplete" in " ".join(buf.getvalue().split())
    assert not (tmp_path / ".gitignore").exists()
    assert (tmp_path / root).read_text() == "not a directory"
    assert config.read_text() == f"agents:\n  available: [{agent}]\n"


@pytest.mark.parametrize("agent", ["claude", "qwen", "kilocode"])
@pytest.mark.parametrize("broken", ["empty", "directory", "symlink"])
def test_initialized_clone_rejects_unusable_native_skills(monkeypatch, tmp_path, agent, broken):
    """An unusable existing NATIVE skill file fails explicitly and is preserved (#4425).

    The re-run must verify usability of the complete expected surface, not only
    presence: a SKILL.md that exists but is empty, a directory, or a symlink
    exits 1 naming the affected path instead of reporting the surface verified.
    User-owned content is never overwritten.
    """
    from specify_cli.skills.paths import get_primary_project_skill_root
    from specify_cli.skills.registry import SkillRegistry

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text(f"agents:\n  available: [{agent}]\n")
    skills = SkillRegistry.from_package().discover_skills()
    assert skills
    root_name = get_primary_project_skill_root(agent)
    root = tmp_path / root_name
    for skill in skills:
        path = root / skill.name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Preserve user-owned content")
    target = root / skills[0].name / "SKILL.md"
    target.unlink()
    if broken == "empty":
        target.touch()
    elif broken == "directory":
        target.mkdir()
    else:
        target.symlink_to(config)
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", agent, "--non-interactive"])
    assert result.exit_code == 1
    flattened = " ".join(buf.getvalue().split())
    assert "unusable" in flattened
    assert f"{root_name}/{skills[0].name}/SKILL.md" in flattened
    # The unusable shape is preserved untouched, never overwritten.
    if broken == "empty":
        assert target.is_file() and target.stat().st_size == 0
    elif broken == "directory":
        assert target.is_dir() and not target.is_symlink()
    else:
        assert target.is_symlink()
    assert config.read_text() == f"agents:\n  available: [{agent}]\n"


def test_initialized_clone_unusable_native_blocks_restore_write(monkeypatch, tmp_path):
    """Unusable existing files fail before any additive restore writes (#4425).

    A project with one absent skill AND one unusable skill exits 1 without
    delivering the absent one, so a failing re-run never leaves a half-restored
    surface behind.
    """
    from specify_cli.skills.paths import get_primary_project_skill_root
    from specify_cli.skills.registry import SkillRegistry

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [claude]\n")
    skills = SkillRegistry.from_package().discover_skills()
    assert len(skills) >= 2
    root_name = get_primary_project_skill_root("claude")
    root = tmp_path / root_name
    for skill in skills[1:]:
        path = root / skill.name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Preserve user-owned content")
    broken = root / skills[0].name / "SKILL.md"
    broken.parent.mkdir(parents=True)
    broken.touch()  # present but empty: unusable, preserved
    absent_name = skills[1].name
    (root / absent_name / "SKILL.md").unlink()  # force one genuinely absent skill
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 1
    flattened = " ".join(buf.getvalue().split())
    assert f"{root_name}/{skills[0].name}/SKILL.md" in flattened
    # Nothing was written: the absent skill is still absent, the empty file
    # is still empty, and no gitignore delivery happened.
    assert not (root / absent_name / "SKILL.md").exists()
    assert broken.stat().st_size == 0
    assert config.read_text() == "agents:\n  available: [claude]\n"


def test_initialized_clone_verifies_native_surface_when_complete(monkeypatch, tmp_path):
    """A complete, usable NATIVE surface needs no restore and exits 0 (#4425).

    This is the nothing-needs-installation half of the contract: the complete
    expected set is verified even when nothing is absent.
    """
    from specify_cli.skills.paths import get_primary_project_skill_root
    from specify_cli.skills.registry import SkillRegistry

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("agents:\n  available: [claude]\n")
    skills = SkillRegistry.from_package().discover_skills()
    root_name = get_primary_project_skill_root("claude")
    root = tmp_path / root_name
    for skill in skills:
        path = root / skill.name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("Preserve user-owned content")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app_with_buf()
    result = _run(app, ["init", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 0, buf.getvalue()
    for skill in skills:
        assert (root / skill.name / "SKILL.md").read_text() == "Preserve user-owned content"
    assert config.read_text() == "agents:\n  available: [claude]\n"


def _make_app_with_buf() -> tuple[Typer, io.StringIO]:
    """Return app and the buffer backing the injected console."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, highlight=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, buf


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


# ---------------------------------------------------------------------------
# T1.5: Idempotency check
# ---------------------------------------------------------------------------


def test_init_is_idempotent_on_rerun(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """T1.5: Running init twice exits 0 on both runs (idempotent).

    The second run must NOT silently merge or overwrite state — it exits
    cleanly with an "Already initialized" message in console output.
    """
    # First run — fresh directory
    app1, buf1 = _make_app_with_buf()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result1 = _run(app1, ["init", "--ai", "codex", "--non-interactive"])
    assert result1.exit_code == 0, f"First init failed (exit_code={result1.exit_code})"

    # Record state after first run
    config_path = tmp_path / ".kittify" / "config.yaml"
    assert config_path.exists(), "config.yaml should exist after first init"
    config_content_after_first = config_path.read_text(encoding="utf-8")

    # Second run — already-initialized directory; use a fresh app/buffer
    app2, buf2 = _make_app_with_buf()
    result2 = _run(app2, ["init", "--ai", "codex", "--non-interactive"])

    # Must exit 0 (idempotent path, not fail-fast)
    assert result2.exit_code == 0, f"Second init should exit 0 (idempotent), got {result2.exit_code}."

    # Must emit a clear "already initialized" message in console output (not silent)
    console_out = buf2.getvalue().lower()
    assert "already" in console_out or "initialized" in console_out, (
        f"Second init console output should mention 'already initialized', but got:\n{buf2.getvalue()!r}"
    )

    # Config must be unchanged (no silent merge/overwrite)
    config_content_after_second = config_path.read_text(encoding="utf-8")
    assert config_content_after_first == config_content_after_second, "config.yaml was modified by the second init run — silent merge/overwrite detected."


def test_init_repairs_requested_command_skills_in_initialized_clone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit --ai repairs an ignored agent surface in an initialized clone."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    app1, _ = _make_app_with_buf()
    result1 = _run(app1, ["init", "--ai", "codex", "--non-interactive"])
    assert result1.exit_code == 0, result1.output

    config_path = tmp_path / ".kittify" / "config.yaml"
    config_before = config_path.read_text(encoding="utf-8")
    skills_root = tmp_path / ".agents" / "skills"
    assert skills_root.is_dir()

    # Agent surfaces are intentionally ignored and therefore absent after a clone.
    shutil.rmtree(tmp_path / ".agents")
    assert not skills_root.exists()

    app2, buf2 = _make_app_with_buf()
    result2 = _run(app2, ["init", "--ai", "codex", "--non-interactive"])

    assert result2.exit_code == 0, result2.output
    assert (skills_root / "spec-kitty.plan" / "SKILL.md").is_file()
    assert "command skills installed" in buf2.getvalue().lower()
    assert config_path.read_text(encoding="utf-8") == config_before
