"""Doctor coverage for command-skill manifest drift."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli.cli.commands.doctor as doctor_mod
from specify_cli.cli.commands import _command_surface_doctor as doctor_surface
from specify_cli.cli.commands.doctor import app
from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.pack_skill_drift import KIND_DRIFT, KIND_MISSING, KIND_STALE, PackSkillFinding
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _write_config(repo_root: Path, *agents: str) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    lines = ["agents:", "  available:"]
    lines.extend(f"    - {agent}" for agent in agents)
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _invoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *args: str,
):
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: tmp_path)
    return runner.invoke(app, ["skills", *args])


def _payload(output: str) -> dict[str, object]:
    return json.loads(output)


def test_skills_reports_missing_manifest_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")

    deleted = tmp_path / ".agents" / "skills" / "spec-kitty.tasks" / "SKILL.md"
    deleted.unlink()

    result = _invoke(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 1
    data = _payload(result.output)
    assert data["ok"] is False
    assert data["gaps"] == [".agents/skills/spec-kitty.tasks/SKILL.md"]
    assert data["uninstalled_agents"] == []


def test_skills_fix_repairs_partial_codex_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")

    for command in command_installer.CANONICAL_COMMANDS:
        if command == "specify":
            continue
        skill_md = tmp_path / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md"
        skill_md.unlink()

    result = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert result.exit_code == 0
    data = _payload(result.output)
    assert data["ok"] is True
    assert data["gaps"] == []
    assert data["entries"] == len(command_installer.CANONICAL_COMMANDS)
    manifest = manifest_store.load(tmp_path)
    assert len(manifest.entries) == len(command_installer.CANONICAL_COMMANDS)
    for command in command_installer.CANONICAL_COMMANDS:
        assert (tmp_path / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md").is_file()


def test_skills_fix_installs_configured_command_agent_without_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")

    before = _invoke(tmp_path, monkeypatch, "--json")
    assert before.exit_code == 1
    assert _payload(before.output)["uninstalled_agents"] == ["codex"]

    fixed = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert fixed.exit_code == 0
    data = _payload(fixed.output)
    assert data["ok"] is True
    assert data["manifest_agents"] == ["codex"]
    assert data["entries"] == len(command_installer.CANONICAL_COMMANDS)


def test_skills_fix_refuses_unmanaged_canonical_orphan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    custom = tmp_path / ".agents" / "skills" / "spec-kitty.specify" / "SKILL.md"
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("CUSTOM LOCAL SKILL\n", encoding="utf-8")

    result = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert result.exit_code == 1
    data = _payload(result.output)
    assert data["ok"] is False
    assert ".agents/skills/spec-kitty.specify/SKILL.md" in data["orphans"]
    assert data["repair_errors"] == ["Refusing --fix while unmanaged spec-kitty skill files exist."]
    assert custom.read_text(encoding="utf-8") == "CUSTOM LOCAL SKILL\n"


def test_skills_fix_refuses_when_managed_file_drifted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")
    drifted = tmp_path / ".agents" / "skills" / "spec-kitty.specify" / "SKILL.md"
    drifted.write_text(
        drifted.read_text(encoding="utf-8") + "\n# local edit\n",
        encoding="utf-8",
    )
    missing = tmp_path / ".agents" / "skills" / "spec-kitty.tasks" / "SKILL.md"
    missing.unlink()

    result = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert result.exit_code == 1
    data = _payload(result.output)
    assert data["gaps"] == [".agents/skills/spec-kitty.tasks/SKILL.md"]
    assert data["drift"] == [".agents/skills/spec-kitty.specify/SKILL.md"]
    assert data["repaired_agents"] == []
    assert data["repair_errors"] == ["Refusing --fix while managed skill files have edited-file drift."]
    assert not missing.exists()


def test_skills_fix_repairs_stale_twelve_skill_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")
    for command in command_installer.CANONICAL_COMMANDS:
        (tmp_path / ".agents" / "skills" / f"spec-kitty.{command}" / "SKILL.md").unlink()

    stale_package = "spec-kitty.legacy-opener"
    stale = tmp_path / ".agents" / "skills" / stale_package / "SKILL.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("stale opener\n", encoding="utf-8")
    manifest = manifest_store.load(tmp_path)
    manifest.upsert(
        manifest_store.ManifestEntry(
            path=f".agents/skills/{stale_package}/SKILL.md",
            content_hash=manifest_store.fingerprint_file(stale),
            agents=("codex",),
            installed_at="2024-01-01T00:00:00+00:00",
            spec_kitty_version="3.2.0a4",
        )
    )
    manifest_store.save(tmp_path, manifest)

    result = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert result.exit_code == 0
    data = _payload(result.output)
    assert data["ok"] is True
    assert data["entries"] == len(command_installer.CANONICAL_COMMANDS)
    assert data["stale"] == []
    assert data["pruned"] == [f".agents/skills/{stale_package}/SKILL.md"]
    assert not stale.exists()


def test_skills_json_errors_are_machine_parseable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: None)

    result = runner.invoke(app, ["skills", "--json"])

    assert result.exit_code == 2
    assert _payload(result.output)["error"]["code"] == "not_in_project"


def test_skills_json_config_errors_are_machine_parseable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("agents: [\n", encoding="utf-8")

    result = _invoke(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 2
    assert _payload(result.output)["error"]["code"] == "config_error"
    assert result.stderr == ""


def test_skills_json_manifest_errors_are_machine_parseable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    manifest_path.write_text("{", encoding="utf-8")

    result = _invoke(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 2
    assert _payload(result.output)["error"]["code"] == "manifest_error"
    assert result.stderr == ""


def test_skills_json_suppresses_forward_compat_manifest_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    command_installer.install(tmp_path, "codex")
    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["future"] = True
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    result = _invoke(tmp_path, monkeypatch, "--json")

    assert result.exit_code == 0
    assert _payload(result.output)["ok"] is True
    assert result.stderr == ""


def test_skills_reports_and_repairs_missing_vibe_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "vibe")
    command_installer.install(tmp_path, "vibe")

    before = _invoke(tmp_path, monkeypatch, "--json")
    assert before.exit_code == 1
    assert _payload(before.output)["vibe_config_missing"] is True

    fixed = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert fixed.exit_code == 0
    data = _payload(fixed.output)
    assert data["ok"] is True
    assert data["vibe_config_missing"] is False
    assert data["repaired_vibe_config"] is True
    assert (tmp_path / ".vibe" / "config.toml").is_file()


def test_skills_fix_refuses_symlinked_skill_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, "codex")
    outside = tmp_path.parent / f"{tmp_path.name}-outside-doctor-symlink"
    outside.mkdir()
    protected = outside / "SKILL.md"
    protected.write_text("DO_NOT_OVERWRITE\n", encoding="utf-8")
    skills_root = tmp_path / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    (skills_root / "spec-kitty.analyze").symlink_to(outside, target_is_directory=True)

    result = _invoke(tmp_path, monkeypatch, "--fix", "--json")

    assert result.exit_code == 1
    data = _payload(result.output)
    assert data["repair_errors"]
    assert data["unsafe"] == [".agents/skills/spec-kitty.analyze/SKILL.md"]
    assert protected.read_text(encoding="utf-8") == "DO_NOT_OVERWRITE\n"


def test_doctor_skills_json_error_schema_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#1965: ``doctor skills --json`` is deterministic regardless of ambient state.

    Determinism comes from the ``paths.py`` resolver fix (#1965), NOT from
    test-local ``monkeypatch`` of ``locate_project_root``. Before the fix, the
    Tier-1 ``SPECIFY_REPO_ROOT`` branch *silently ignored* an existing path that
    lacked ``.kittify/`` and fell through to a Tier-2 walk-up. From an arbitrary
    cwd that walk-up climbs into whatever checkout (or polluted ``/tmp``) lives
    above the test, leaking ambient ``~/.claude``/repo state into the result —
    the exact flakiness #1965 describes.

    After the fix, an existing-directory ``SPECIFY_REPO_ROOT`` is authoritative
    even without ``.kittify/``: the resolver returns it directly, the walk-up
    never runs, and ``doctor skills`` reports against that controlled empty
    root. The payload is therefore byte-stable no matter what ``~/.claude`` or
    cwd holds.

    This test touches only ``SPECIFY_REPO_ROOT`` and cwd — proving the resolver
    itself is deterministic. The asserted schema is the *frozen* full
    ``doctor skills --json`` envelope: it must stay byte-identical (every key AND
    value, exact-match — never loosened to ``in``, never with a dropped key).
    """
    # Existing directory with NO .kittify/ → the resolver fix must honour it
    # authoritatively (drops the old `.kittify`-present precondition).
    controlled_root = tmp_path / "controlled-empty-root"
    controlled_root.mkdir()
    (controlled_root / ".claude").mkdir()  # one configured tool folder keeps ``tool_folders`` empty
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(controlled_root))
    # Run from an unrelated cwd to prove resolution does NOT depend on it.
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["skills", "--json"])

    assert result.exit_code == 0
    # FROZEN ENVELOPE — exact byte-identical match (do not loosen).
    # ``canonical_commands`` is the one derived value: the literal census of
    # that set lives in tests/specify_cli/skills/test_command_installer.py, and
    # a second literal here went stale when a command was removed.
    assert _payload(result.output) == {
        "configured_agents": [],
        "manifest_agents": [],
        "entries": 0,
        "canonical_commands": len(command_installer.CANONICAL_COMMANDS),
        "drift": [],
        "gaps": [],
        "orphans": [],
        "stale": [],
        "unsafe": [],
        "uninstalled_agents": [],
        "vibe_config_missing": False,
        "repaired_agents": [],
        "repaired_paths": [],
        "pruned": [],
        "repaired_vibe_config": False,
        "repair_errors": [],
        # Additive (#5193 / #5694): pack-skill drift, stale, orphaned and unresolvable
        # findings. Empty for a project with no pack skill.
        "pack_skills": [],
        # Additive (#5801): ``no_tool_folder`` finding; empty when any configured tool folder exists.
        "tool_folders": [],
        "ok": True,
        "slash_commands": {
            "configured_agents": [],
            "gaps": [],
            "repaired": [],
            "errors": [],
            "ok": True,
        },
    }


def test_doctor_skills_not_in_project_envelope_frozen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the byte-identical ``not_in_project`` error envelope (NFR-001).

    Complements the resolver-driven determinism test: this freezes the exact
    error-envelope contract emitted when no project root is found, so a later
    refactor cannot silently reshape it.
    """
    monkeypatch.setattr(doctor_mod, "locate_project_root", lambda: None)

    result = runner.invoke(app, ["skills", "--json"])

    assert result.exit_code == 2
    # FROZEN ERROR ENVELOPE — exact byte-identical match (do not loosen).
    assert _payload(result.output) == {
        "ok": False,
        "error": {
            "code": "not_in_project",
            "message": "Not in a spec-kitty project",
        },
    }


# --- pack skills and tool folders --------------------------------------------

PACK_SKILL_ID = "deploy-helper"
PACK_SKILL_RENDERED = "acme-deploy-helper"
PACK_SKILL_CONFIG = "agents:\n  available:\n    - claude\n    - codex\n"


@pytest.fixture
def pack_skill_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    pack = tmp_path / "pack"
    pack.mkdir()
    support.write_skill(pack, PACK_SKILL_ID)
    support.write_org_charter(pack, required_skills=[PACK_SKILL_ID], namespace="acme")
    root = tmp_path / "project"
    root.mkdir()
    support.write_config(root, pack, extra=PACK_SKILL_CONFIG)
    (root / ".claude").mkdir()  # one configured tool folder exists
    monkeypatch.setattr("specify_cli.cli.commands.doctor.locate_project_root", lambda: root)
    return root


def _doctor_skills_json(*args: str) -> tuple[int, dict[str, object]]:
    result = runner.invoke(app, ["skills", "--json", *args])
    return result.exit_code, json.loads(result.output[result.output.index("{") :])


@pytest.mark.integration
def test_required_pack_skill_never_installed_is_reported_missing_then_projected_by_fix(pack_skill_project: Path) -> None:
    code, payload = _doctor_skills_json()
    assert code == 1
    pack_skills = payload["pack_skills"]
    assert isinstance(pack_skills, list) and pack_skills
    assert pack_skills[0]["kind"] == "missing"

    code, payload = _doctor_skills_json("--fix")
    assert (pack_skill_project / ".claude" / "skills" / PACK_SKILL_RENDERED / "SKILL.md").is_file()
    assert payload["repaired_paths"]
    assert not any("/" in agent for agent in payload["repaired_agents"])

    code, payload = _doctor_skills_json()
    assert code == 0, payload
    assert payload["pack_skills"] == []


@pytest.mark.integration
def test_doctor_reports_no_tool_folder_when_no_configured_agent_folder_exists(pack_skill_project: Path) -> None:
    (pack_skill_project / ".claude").rmdir()
    code, payload = _doctor_skills_json()
    assert code == 1
    folders = payload["tool_folders"]
    assert isinstance(folders, list) and folders[0]["kind"] == "no_tool_folder"
    assert sorted(folders[0]["configured_agents"]) == ["claude", "codex"]


@pytest.mark.integration
def test_doctor_reports_no_tool_folder_findings_as_empty_when_one_configured_folder_exists(pack_skill_project: Path) -> None:
    _, payload = _doctor_skills_json()
    assert payload["tool_folders"] == []


@pytest.mark.integration
def test_fix_projects_missing_pack_skills_but_never_repairs_drift(pack_skill_project: Path) -> None:
    _doctor_skills_json("--fix")
    claude = pack_skill_project / ".claude" / "skills" / PACK_SKILL_RENDERED / "SKILL.md"
    claude.chmod(claude.stat().st_mode | stat.S_IWUSR)
    claude.write_text("edited locally\n", encoding="utf-8")
    codex = pack_skill_project / ".agents" / "skills" / PACK_SKILL_RENDERED / "SKILL.md"
    codex.chmod(codex.stat().st_mode | stat.S_IWUSR)
    codex.unlink()

    _, payload = _doctor_skills_json("--fix")

    assert claude.read_text(encoding="utf-8") == "edited locally\n"
    assert codex.is_file()
    assert [item["kind"] for item in payload["pack_skills"]] == [KIND_DRIFT]


def _pack_finding(kind: str) -> PackSkillFinding:
    return PackSkillFinding(kind, PACK_SKILL_RENDERED, f".claude/skills/{PACK_SKILL_RENDERED}/SKILL.md", "")


@pytest.mark.integration
def test_repair_pack_skills_skips_projection_without_missing_findings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(_: Path) -> None:
        raise AssertionError("must not project")

    monkeypatch.setattr("specify_cli.skills.installer.project_pack_skills", _boom)
    findings = (_pack_finding(KIND_DRIFT), _pack_finding(KIND_STALE))
    repaired: list[str] = []
    errors: list[str] = []
    assert doctor_surface._repair_pack_skills(tmp_path, findings, repaired, errors) == findings
    assert repaired == [] and errors == []


@pytest.mark.integration
def test_repair_pack_skills_reports_projection_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _fail(_: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("specify_cli.skills.installer.project_pack_skills", _fail)
    after = (_pack_finding(KIND_STALE),)
    monkeypatch.setattr(doctor_surface, "find_pack_skill_findings", lambda _: after)
    findings = (_pack_finding(KIND_MISSING),)
    repaired: list[str] = []
    errors: list[str] = []
    assert doctor_surface._repair_pack_skills(tmp_path, findings, repaired, errors) == after
    assert repaired == [] and errors == ["pack skill projection failed: disk full"]


@pytest.mark.integration
def test_repair_pack_skills_reports_a_catalog_error_instead_of_crashing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.skills.catalog import PackSkillCatalogError

    def _fail(_: Path) -> None:
        raise PackSkillCatalogError("unresolvable catalog")

    monkeypatch.setattr("specify_cli.skills.installer.project_pack_skills", _fail)
    monkeypatch.setattr(doctor_surface, "find_pack_skill_findings", lambda _: ())
    findings = (_pack_finding(KIND_MISSING),)
    errors: list[str] = []
    assert doctor_surface._repair_pack_skills(tmp_path, findings, [], errors) == ()
    assert errors == ["pack skill projection failed: unresolvable catalog"]
