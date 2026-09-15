"""Integration tests for ``init``/``upgrade`` ToolSurfaceContract wiring (T040).

These tests exercise the *real* CLI wiring (FR-001/FR-002): they invoke the
checkout-local ``specify_cli`` package as a subprocess — never a direct call to
``run_surface_repair`` — so a regression that disconnects ``init``/``upgrade``
from the repair service is caught here even though the function itself still
works in isolation.

Drift policy:
  - FR-003 missing  -> auto-created during init/upgrade (no prompt)
  - FR-004 stale    -> auto-repaired during init/upgrade (no prompt)
  - FR-006 drifted  -> ``--yes`` (non-interactive) reports only and exits
    non-zero; it MUST NOT overwrite the user's edits (NFR-007)
  - FR-008 idempotent: a second consecutive run reports zero changes
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .integration._compat_support import run_spec_kitty

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox]


def _init_claude_project(root: Path) -> None:
    """Run ``init --ai claude --non-interactive`` in *root* (real CLI wiring)."""
    result = run_spec_kitty(
        "init", "--ai", "claude", "--non-interactive", cwd=root
    )
    assert result.returncode == 0, (
        f"init failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _agent_profile_states(root: Path) -> set[str]:
    result = run_spec_kitty(
        "doctor", "tool-surfaces", "--kind", "agent-profile", "--json", cwd=root
    )
    payload = result.json()
    return {surface["state"] for surface in payload["surfaces"]}


def test_init_creates_missing_profile_dirs(tmp_path: Path) -> None:
    """``init`` creates missing native agent profile dirs via the CLI (FR-001)."""
    assert not (tmp_path / ".claude" / "agents").exists()

    _init_claude_project(tmp_path)

    agents_dir = tmp_path / ".claude" / "agents"
    assert agents_dir.exists(), ".claude/agents/ must be created by init"
    profiles = list(agents_dir.glob("*.md"))
    assert profiles, ".claude/agents/ must contain at least one .md profile"
    for profile in profiles:
        assert profile.read_text(encoding="utf-8").startswith("---"), (
            f"{profile.name} must carry YAML frontmatter"
        )

    # doctor reports no missing/stale/drifted agent profiles.
    states = _agent_profile_states(tmp_path)
    assert states <= {"present", "not_applicable"}, (
        f"unexpected agent-profile states after init: {states}"
    )


def test_upgrade_recreates_deleted_profile_dirs(tmp_path: Path) -> None:
    """``upgrade`` re-creates missing profile dirs even on the up-to-date path.

    FR-002 regression guard: when no migrations are pending (project already at
    the current version) the surface-repair service must still run. Deleting
    ``.claude/agents/`` and re-running ``upgrade --yes`` must heal it.
    """
    _init_claude_project(tmp_path)
    agents_dir = tmp_path / ".claude" / "agents"
    before = {p.name for p in agents_dir.glob("*.md")}
    assert before, "init must have produced profile files"

    # Prime the up-to-date path: the first upgrade applies the wiring marker so
    # the second upgrade exercises the "already up to date" branch.
    first = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert first.returncode == 0, first.stderr

    import shutil

    shutil.rmtree(agents_dir)
    assert not agents_dir.exists()

    second = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert second.returncode == 0, second.stderr
    assert agents_dir.exists(), "upgrade must re-create deleted .claude/agents/"
    after = {p.name for p in agents_dir.glob("*.md")}
    assert after == before, "re-created profile set must match the original"


def test_upgrade_repairs_stale_manifest(tmp_path: Path) -> None:
    """``upgrade`` auto-repairs a stale (truncated) command-skill manifest (FR-030)."""
    import json

    # codex is a command-skill agent, so its config produces the manifest.
    init_result = run_spec_kitty(
        "init", "--ai", "claude,codex", "--non-interactive", cwd=tmp_path
    )
    assert init_result.returncode == 0, init_result.stderr
    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical_count = len(manifest["entries"])
    assert canonical_count > 1, "init should yield a multi-entry manifest"

    # Degrade: drop all but one entry (simulates an rc44-era short manifest).
    manifest["entries"] = manifest["entries"][:1]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    repaired = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(repaired["entries"]) == canonical_count, (
        "stale manifest must be repaired back to the canonical entry count"
    )


def test_upgrade_with_yes_does_not_overwrite_drifted(tmp_path: Path) -> None:
    """``--yes`` must report-only on drift and exit non-zero (FR-006/NFR-007)."""
    _init_claude_project(tmp_path)

    # Prime the up-to-date path so the wiring marker exists.
    run_spec_kitty("upgrade", "--yes", cwd=tmp_path)

    agents_dir = tmp_path / ".claude" / "agents"
    custom_content = "# Hand-modified agent\n\nCustom content.\n"
    drifted_path: Path | None = None
    for md in sorted(agents_dir.glob("*.md")):
        md.write_text(custom_content, encoding="utf-8")
        drifted_path = md
        break
    assert drifted_path is not None, "no managed profile files found after init"

    result = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    # FR-006: non-interactive upgrade exits non-zero when unresolved drift exists.
    assert result.returncode != 0, "--yes must exit non-zero on unresolved drift"
    # NFR-007: the drifted file is preserved verbatim.
    assert drifted_path.read_text(encoding="utf-8") == custom_content, (
        "drifted file must not be overwritten by --yes"
    )


def test_upgrade_refreshes_stale_orientation_block_same_version(tmp_path: Path) -> None:
    """``upgrade`` refreshes a stale ``.claude/CLAUDE.md`` version stamp (#2265).

    Reproduces the exact repro: a project already at the current version whose
    orientation block still carries an older init-time version. The always-on
    surface-repair leg must rewrite the block to the installed version even on
    the "already up to date" path — not only when a version-gated migration
    happens to fire.
    """
    import re

    _init_claude_project(tmp_path)
    # Prime the up-to-date path so the wiring marker exists and no migrations pend.
    first = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert first.returncode == 0, first.stderr

    claude_md = tmp_path / ".claude" / "CLAUDE.md"
    original = claude_md.read_text(encoding="utf-8")
    assert "<!-- spec-kitty:orientation -->" in original, "init must stamp an orientation block"

    # Degrade only the version stamp, leaving the block markers intact so the
    # in-place section rewrite is exercised.
    staled = re.sub(r"\*\*Spec Kitty v[^*]+\*\*", "**Spec Kitty v0.0.1-legacy**", original, count=1)
    assert staled != original, "test setup must actually change the version stamp"
    claude_md.write_text(staled, encoding="utf-8")

    second = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert second.returncode == 0, second.stderr

    refreshed = claude_md.read_text(encoding="utf-8")
    assert "0.0.1-legacy" not in refreshed, "stale version stamp must be refreshed"
    assert "**Spec Kitty v" in refreshed
    assert refreshed.count("<!-- spec-kitty:orientation -->") == 1, "block must not be duplicated"


def test_second_upgrade_is_idempotent(tmp_path: Path) -> None:
    """A second consecutive ``upgrade`` reports zero changes (FR-008/NFR-006)."""
    _init_claude_project(tmp_path)

    first = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert first.returncode == 0, first.stderr

    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    second = run_spec_kitty("upgrade", "--yes", cwd=tmp_path)
    assert second.returncode == 0, second.stderr
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before, "second upgrade must not change any file bytes"


@pytest.mark.parametrize("agents", ["codex", "codex,vibe", "vibe,codex"])
def test_init_command_bytes_agree_with_final_config(tmp_path: Path, agents: str) -> None:
    """#3920: first init renders final activation, once per physical skill."""
    import hashlib
    import json
    import os
    import sys
    from collections import Counter

    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active
    from specify_cli import __version__
    from specify_cli.skills import command_installer, command_renderer
    from tests.upgrade.preview_support import write_observer
    from tests.upgrade.preview_support.process import run_process

    project = tmp_path / "project"
    project.mkdir()
    assert not is_spdd_reasons_active(project), "absent config remains inactive"
    log = tmp_path / "writes.jsonl"
    result = run_process(
        [sys.executable, str(write_observer.__file__), str(log), "record", "cli", "init", "--ai", agents, "--non-interactive"],
        project,
        dict(os.environ, SPECIFY_REPO_ROOT=str(project)),
    )
    result.require_success()
    assert is_spdd_reasons_active(project), "fresh final config enables built-ins"
    manifest = json.loads((project / ".kittify/command-skills-manifest.json").read_text())
    entries = manifest["entries"]
    assert len(entries) == len(command_installer.CANONICAL_COMMANDS)
    assert len({entry["path"] for entry in entries}) == len(entries)
    for entry in entries:
        assert entry["agents"] == sorted(agents.split(","))
        actual = (project / entry["path"]).read_bytes()
        assert entry["content_hash"] == hashlib.sha256(actual).hexdigest()  # noqa: TID251 -- independent file-integrity checksum
        command = Path(entry["path"]).parent.name.removeprefix("spec-kitty.")
        if command in command_installer.PROMPT_BACKED_COMMANDS:
            rendered = (
                command_renderer.render(
                    command_installer._resolve_template(project, command),
                    agents.split(",")[0],
                    __version__,
                    repo_root=project,
                )
                .to_skill_md()
                .encode()
            )
            assert actual == rendered, f"init/final-config render disagreement: {command}"
    assert b"### REASONS Guidance" in (project / ".agents/skills/spec-kitty.plan/SKILL.md").read_bytes(), (
        "independent content pin must not accept two inactive renders"
    )

    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0] == {"installed_before_cli": True}
    replacements = Counter(row["args"][1] for row in rows[1:] if row["event"] == "os.rename")
    writes = Counter(row["args"][0] for row in rows[1:] if row["event"] == "open")
    for entry in entries:
        target = str(project / entry["path"])
        assert replacements[target] == 1, f"duplicate physical replacement: {target}"
        assert writes[target + ".tmp"] == 1, f"duplicate physical write: {target}"
        assert writes[target] == 0, f"unexpected direct write: {target}"


def test_init_preserves_unknown_command_bytes_and_no_proof(tmp_path: Path) -> None:
    """#3920: delaying installation cannot authorize an unknown canonical name."""
    import json

    from tests.upgrade.preview_support.snapshot import snapshot

    victim = tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md"
    victim.parent.mkdir(parents=True)
    victim.write_bytes(b"# Authored plan\nNot a shipped command.\n")
    victim.chmod(0o400)
    before = snapshot({"custom": victim})
    result = run_spec_kitty("init", "--ai", "codex,vibe", "--non-interactive", cwd=tmp_path)
    assert "unexpected_collision" in result.stdout + result.stderr
    assert snapshot({"custom": victim}) == before
    manifest_path = tmp_path / ".kittify/command-skills-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        assert all(entry["path"] != victim.relative_to(tmp_path).as_posix() for entry in manifest["entries"])


@pytest.mark.parametrize("pointed", [False, True])
def test_init_preserves_authored_disabled_config(tmp_path: Path, pointed: bool) -> None:
    """#3920: authored config is still the idempotency boundary, not re-init."""
    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active
    from tests.upgrade.preview_support.snapshot import snapshot

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    disabled = "activated_paradigms: []\nactivated_tactics: []\nactivated_directives: []\n"
    config = "# Keep authored settings\nmission_type_activations: []\ncustom: retained\n"
    if pointed:
        (kittify / "authored.yaml").write_text(disabled)
        config += "charter: .kittify/authored.yaml\n"
    else:
        config += disabled
    (kittify / "config.yaml").write_text(config)
    assert not is_spdd_reasons_active(tmp_path)
    before = snapshot({"project": tmp_path})
    result = run_spec_kitty("init", "--ai", "codex,vibe", "--non-interactive", cwd=tmp_path)
    # #4425: report the unconfigured selection, without re-initializing or
    # changing the user's explicit doctrine/charter choices.
    assert result.returncode == 1, result.stderr
    assert "spec-kitty agent config add codex vibe" in " ".join(result.stdout.split())
    assert snapshot({"project": tmp_path}) == before
    assert not is_spdd_reasons_active(tmp_path)


@pytest.mark.parametrize("agents", ["codex", "codex,vibe"])
@pytest.mark.parametrize("authored_after_fault", [False, True])
def test_init_retry_recovers_real_config_save_interruption(tmp_path: Path, agents: str, authored_after_fault: bool) -> None:
    """#3920: retry finishes new delivery, without rewriting persisted config."""
    import hashlib
    import json
    import sys
    from collections import Counter

    from charter.offering.spdd_reasons.activation import is_spdd_reasons_active
    from specify_cli.skills import command_installer
    from tests.upgrade.preview_support import write_observer
    from tests.upgrade.preview_support.process import child_environment, run_process
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged
    from .integration._compat_support import project_root

    project = tmp_path / "project"
    project.mkdir()
    fault = """
import importlib, sys
module = importlib.import_module("specify_cli.cli.commands.init")
print("INIT_SOURCE", module.__file__, flush=True)
original = module.save_agent_config
def interrupted(*args, **kwargs):
    original(*args, **kwargs)
    print("REAL_CONFIG_SAVE_INTERRUPTED", flush=True)
    raise KeyboardInterrupt("after real config persistence")
module.save_agent_config = interrupted
from specify_cli import main
sys.argv = ["spec-kitty", "init", "--ai", sys.argv[1], "--non-interactive"]
main()
"""
    env = child_environment(tmp_path / "sandbox")
    lane = project_root()
    env["PYTHONPATH"] = str(lane / "src") + ":" + str(lane)
    env["SPECIFY_REPO_ROOT"] = str(project)
    first = run_process([sys.executable, "-c", fault, agents], project, env)
    assert first.returncode == 130, first.stdout + first.stderr
    assert "REAL_CONFIG_SAVE_INTERRUPTED" in first.stdout
    assert str(lane / "src/specify_cli/cli/commands/init.py") in first.stdout
    config = project / ".kittify/config.yaml"
    assert config.is_file()
    if authored_after_fault:
        # An interruption token must not authorize replacing later authored input.
        config.write_text(
            "# Authored after interruption\nagents:\n  available: [codex]\nactivated_paradigms: []\nactivated_tactics: []\nactivated_directives: []\n",
            encoding="utf-8",
        )
    before = snapshot({"config": config})
    log = tmp_path / "retry-writes.jsonl"
    retry = run_process(
        [sys.executable, str(write_observer.__file__), str(log), "record", "cli", "init", "--ai", agents, "--non-interactive"],
        project,
        env,
    )
    retry.require_success()
    manifest = project / ".kittify/command-skills-manifest.json"
    assert manifest.is_file(), "retry left the interrupted command delivery absent"
    entries = json.loads(manifest.read_text())["entries"]
    assert len(entries) == len(command_installer.CANONICAL_COMMANDS)
    assert len(list((project / ".agents/skills").glob("spec-kitty.*/SKILL.md"))) == len(command_installer.CANONICAL_COMMANDS)
    owners = ["codex"] if authored_after_fault else sorted(agents.split(","))
    for entry in entries:
        assert entry["agents"] == owners
        assert entry["content_hash"] == hashlib.sha256((project / entry["path"]).read_bytes()).hexdigest()  # noqa: TID251 -- independent checksum
    assert_unchanged(before, snapshot({"config": config}))
    assert is_spdd_reasons_active(project) is not authored_after_fault
    plan = (project / ".agents/skills/spec-kitty.plan/SKILL.md").read_bytes()
    assert (b"### REASONS Guidance" in plan) is not authored_after_fault
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    replacements = Counter(row["args"][1] for row in rows[1:] if row["event"] == "os.rename")
    writes = Counter(row["args"][0] for row in rows[1:] if row["event"] == "open")
    for entry in entries:
        target = str(project / entry["path"])
        assert replacements[target] == 1 and writes[target + ".tmp"] == 1
        assert writes[target] == 0
    finished = snapshot({"project": project})
    again = run_process([sys.executable, "-m", "specify_cli", "init", "--ai", agents, "--non-interactive"], project, env)
    if authored_after_fault and "vibe" in agents.split(","):
        assert again.returncode == 1
        assert "spec-kitty agent config add vibe" in " ".join(again.stdout.split())
    else:
        assert again.returncode == 0 and "Already initialized" in again.stdout
    assert_unchanged(finished, snapshot({"project": project}))


@pytest.mark.parametrize("damage", ["bytes", "schema", "boolean-schema", "agents", "duplicates", "symlink", "changed-selection"])
def test_init_pending_command_record_preserves_unsafe_inputs(tmp_path: Path, damage: str) -> None:
    """A reserved recovery path is not permission to replace arbitrary bytes."""
    import importlib
    import json
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    init = importlib.import_module("specify_cli.cli.commands.init")
    (tmp_path / ".kittify").mkdir()
    init._start_command_delivery(tmp_path, ["codex", "vibe"])
    record = tmp_path / ".kittify/init-command-skills.pending.json"
    if damage == "bytes":
        record.write_bytes(b"authored, not a recovery record")
    elif damage == "schema":
        record.write_text(json.dumps({"schema_version": 2, "agents": ["codex"]}))
    elif damage == "boolean-schema":
        record.write_text(json.dumps({"schema_version": True, "agents": ["codex", "vibe"]}))
    elif damage == "agents":
        record.write_text(json.dumps({"schema_version": 1, "agents": ["foreign"]}))
    elif damage == "duplicates":
        record.write_text(json.dumps({"schema_version": 1, "agents": ["codex", "codex"]}))
    elif damage == "symlink":
        target = tmp_path / "foreign"
        target.write_bytes(record.read_bytes())
        record.unlink()
        record.symlink_to(target)
    before = snapshot({"project": tmp_path})
    with pytest.raises(ValueError):
        init._start_command_delivery(tmp_path, ["codex"] if damage == "changed-selection" else ["codex", "vibe"])
    assert_unchanged(before, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("case", ["all-removed", "unknown-skill", "runtime-guard", "unsaved-selection", "completed"])
def test_init_pending_command_recovery_boundaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    """Exercise real owners beneath the recovery boundary, not fake installers."""
    import importlib
    import io
    from rich.console import Console
    from specify_cli.core.agent_config import AgentConfig, save_agent_config
    from specify_cli.gitignore_manager import GitignoreManager
    from specify_cli.skills import command_installer, manifest_store
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    init = importlib.import_module("specify_cli.cli.commands.init")
    monkeypatch.setattr(init, "_console", Console(file=io.StringIO()))
    (tmp_path / ".kittify").mkdir()
    initial = snapshot({"project": tmp_path})
    init._start_command_delivery(tmp_path, [])
    assert_unchanged(initial, snapshot({"project": tmp_path}))
    init._start_command_delivery(tmp_path, ["codex", "vibe"])
    pending = snapshot({"project": tmp_path})
    init._start_command_delivery(tmp_path, ["vibe", "codex"])
    assert_unchanged(pending, snapshot({"project": tmp_path}))
    assert not (tmp_path / ".kittify/config.yaml").exists()
    save_agent_config(tmp_path, AgentConfig(available=[] if case == "all-removed" else ["codex", "vibe"]))
    record = tmp_path / ".kittify/init-command-skills.pending.json"
    assert GitignoreManager(tmp_path).protect_all_agents().success
    custom = tmp_path / "custom"
    custom.write_bytes(b"foreign bytes")
    if case == "runtime-guard":
        ignore = tmp_path / ".gitignore"
        ignore.unlink()
        ignore.symlink_to(custom)
    elif case == "unknown-skill":
        custom = tmp_path / ".agents/skills/spec-kitty.plan/SKILL.md"
        custom.parent.mkdir(parents=True)
        custom.write_bytes(b"unknown plan")
        custom.chmod(0o400)
    elif case == "unsaved-selection":
        (tmp_path / ".kittify/config.yaml").write_text("project: {}\n")
    elif case == "completed":
        for agent in ("codex", "vibe"):
            command_installer.install(tmp_path, agent)
    config_before = snapshot({"config": tmp_path / ".kittify/config.yaml"})
    custom_before = snapshot({"custom": custom})
    if case in {"unknown-skill", "runtime-guard", "unsaved-selection"}:
        with pytest.raises(ValueError):
            init._resume_command_delivery(tmp_path)
        assert record.is_file()
        assert not manifest_store.load(tmp_path).entries
    else:
        commands_before = snapshot({"commands": tmp_path / ".agents"})
        assert init._resume_command_delivery(tmp_path)
        assert not record.exists()
        assert_unchanged(commands_before, snapshot({"commands": tmp_path / ".agents"}))
        assert not init._resume_command_delivery(tmp_path)
    assert_unchanged(config_before, snapshot({"config": tmp_path / ".kittify/config.yaml"}))
    assert_unchanged(custom_before, snapshot({"custom": custom}))


def test_init_runtime_protection_precedes_pending_command_record(tmp_path: Path) -> None:
    """Real fresh init refuses a foreign ignore link before publishing config."""
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    target = tmp_path / "authored-ignore"
    target.write_bytes(b"foreign ignore content")
    link = tmp_path / ".gitignore"
    link.symlink_to(target)
    before = snapshot({"link": link, "target": target})
    result = run_spec_kitty("init", "--ai", "codex,vibe", "--non-interactive", cwd=tmp_path)
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (tmp_path / ".kittify/config.yaml").exists()
    assert not (tmp_path / ".kittify/init-command-skills.pending.json").exists()
    assert_unchanged(before, snapshot({"link": link, "target": target}))
