"""Global owner regressions; public startup wiring is separately owned by WP10."""

from pathlib import Path
from collections.abc import Callable, Mapping
from dataclasses import replace
import shutil
import ast
from contextlib import contextmanager
from collections.abc import Iterator
import inspect
import json
import os
import sys
from typing import Any, cast
from types import SimpleNamespace

import click
from typer.main import get_command

import pytest

from specify_cli.runtime import agent_commands, agent_skills, bootstrap
from specify_cli.skills.registry import SkillRegistry
from tests.upgrade.preview_support.snapshot import Snapshot, assert_unchanged
from tests.upgrade.preview_support.snapshot import net_delta
from tests.upgrade.preview_support.snapshot import snapshot as _raw_snapshot
from specify_cli.runtime.asset_preparation import apply_assets, recheck_assets
from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment
from specify_cli.upgrade.intent import parse_upgrade_intent

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_COLD_INSTALL_SENTINEL_DIR_SUFFIX = "-cold-install"


def _is_cold_install_sentinel_path(relative: str) -> bool:
    """#4756 WP02: the cold-install lock sentinel now resolves as a SIBLING
    of the per-user runtime state root (e.g. ``.kittify-cold-install/
    <hash>.lock``, next to ``.kittify``) instead of a machine-temp file --
    see ``asset_preparation._cold_install_sentinel``'s docstring for why it
    must live there rather than nested inside the managed home tree. It is
    deliberately kept OUT of every owner's OWN declared assessment effects
    (never asset-verified), so this module's dozens of exact, home-rooted
    filesystem snapshots would otherwise see it as unexplained drift on any
    COLD install exercised inside their before/after window. Filtered out
    ONCE here (via the local ``snapshot`` wrapper below) rather than at
    each call site.
    """
    return any(part.endswith(_COLD_INSTALL_SENTINEL_DIR_SUFFIX) for part in relative.split("/"))


def snapshot(roots: Mapping[str, Path]) -> Snapshot:
    """Local wrapper: the independent lstat oracle, minus cold-install sentinel noise.

    ``tests/upgrade/preview_support/snapshot.py`` is a deliberately naive,
    production-import-free oracle (see its own module docstring) -- it must
    not learn this module's specific path scheme. Shadowing the imported
    name here, once, keeps every existing ``snapshot(...)`` call site in
    this file unchanged while filtering consistently.

    Also neutralizes ``mtime_ns`` on each root's OWN entry (relative path
    ``"."``) only -- creating (or releasing/truncating) the sibling
    cold-install sentinel touches the root directory's mtime as an ordinary
    POSIX side effect of gaining a new sibling one level up, even on a
    batch this module's own precondition check goes on to REFUSE (the
    cold-install lock is attempted before that refusal is known, by
    design). Production's own ``AssetPreparation._observation`` already
    discards mtime for every directory node for the identical reason (a
    child's create moves its parent's mtime without being a "real" drift
    signal); this narrows the same reasoning to just the root entry so
    every deeper path in this module's dozens of exactness assertions
    keeps its full, unweakened mtime strictness.
    """
    return {
        key: (replace(node, mtime_ns=None) if key[1] == "." and node.kind == "directory" else node)
        for key, node in _raw_snapshot(roots).items()
        if not _is_cold_install_sentinel_path(key[1])
    }


def _assert_unchanged_tolerating_lock_holder_churn(before: Snapshot, after: Snapshot) -> None:
    """Like ``assert_unchanged``, but tolerates the canonical lock
    primitive's own holder-observability churn (WP04, cross-os-primitive-
    unification): ``kernel.locks.machine_file_lock`` writes a ``LockRecord``
    on every acquire and truncates back to empty on release (G2/G3) --
    ``recheck_assets`` takes this lock even on a batch it is about to
    REFUSE (the under-lock recheck is never skipped, see its own
    docstring), so a ``*.lock`` path's own ``mtime_ns`` legitimately moves
    even though nothing else about it, or any other path, changes. Content
    (``sha256``) and ``mode`` must still match exactly for a ``.lock`` path;
    every non-``.lock`` path is compared exactly, with no tolerance at all.
    """
    changed = [key for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]
    unexplained = [
        key
        for key in changed
        if not (
            key[1].endswith(".lock")
            and (before_node := before.get(key)) is not None
            and (after_node := after.get(key)) is not None
            and replace(before_node, mtime_ns=None) == replace(after_node, mtime_ns=None)
        )
    ]
    assert not unexplained, f"Filesystem changed: {unexplained}"


@pytest.fixture
def owner_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(home / ".config/opencode"))
    return home


@pytest.fixture
def skill_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = tmp_path / "skills"
    skill = source / "spec-kitty"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: spec-kitty\ndescription: Govern work\n---\n# Work\n")
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: SkillRegistry(source))
    return source


def test_existing_runtime_repairs_current_marker_missing_content(
    owner_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "package/missions"
    (source / "software-dev").mkdir(parents=True)
    (source / "software-dev/templates").mkdir()
    (source / "software-dev/templates/spec.md").write_text("# Specification\n")
    (source / "software-dev/mission.yaml").write_text("mission: software-dev\n")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(source))
    cache = owner_home / ".kittify/cache"
    cache.mkdir(parents=True)
    (cache / "version.lock").write_text(bootstrap._get_cli_version())
    bootstrap.ensure_runtime()
    assert (owner_home / ".kittify/missions/software-dev/mission.yaml").is_file()


def test_existing_skills_repair_current_marker_missing_content(
    owner_home: Path,
    skill_source: Path,
) -> None:
    agent_skills.ensure_global_agent_skills()
    missing = owner_home / ".agents/skills/spec-kitty/SKILL.md"
    missing.unlink()
    agent_skills.ensure_global_agent_skills()
    assert missing.is_file(), "Current stamp must not conceal missing required content"


def test_existing_skills_writer_keeps_coordinated_scope_skills_only(owner_home: Path, skill_source: Path) -> None:
    agent_skills.ensure_global_agent_skills()
    assert (owner_home / ".agents/skills/spec-kitty/SKILL.md").is_file()
    cache = owner_home / ".kittify/cache"
    assert (cache / "global_skills-assets.json").is_file()
    assert not (owner_home / ".kittify/missions").exists()
    assert not (cache / "version.lock").exists()
    assert not (cache / "runtime_bootstrap-assets.json").exists()
    assert not (cache / "slash_commands-assets.json").exists()
    assert not agent_commands.get_global_command_dir("claude").exists()
    before = snapshot({"home": owner_home})
    agent_skills.ensure_global_agent_skills()
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_existing_commands_preserve_unknown_prefixed_link(owner_home: Path) -> None:
    output = agent_commands.get_global_command_dir("claude")
    output.mkdir(parents=True)
    target = owner_home / "custom.md"
    target.write_text("custom command\n")
    target.chmod(0o444)
    link = output / "spec-kitty.custom.md"
    link.symlink_to(target)
    before = snapshot({"target": target, "link": link})
    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    assert_unchanged(before, snapshot({"target": target, "link": link}))


def test_existing_skills_preserve_unknown_prefixed_tree(
    owner_home: Path,
    skill_source: Path,
) -> None:
    custom = owner_home / ".agents/skills/spec-kitty-custom"
    custom.mkdir(parents=True)
    (custom / "SKILL.md").write_text("# User skill\n")
    (custom / ".ignored").write_bytes(b"sentinel")
    before = snapshot({"custom": custom})
    agent_skills.ensure_global_agent_skills()
    assert_unchanged(before, snapshot({"custom": custom}))


def test_existing_scoped_command_repair_has_no_churn(owner_home: Path) -> None:
    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    before = snapshot({"home": owner_home})
    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    assert_unchanged(before, snapshot({"home": owner_home}))


def _actual_upgrade_command() -> click.Command:
    from specify_cli import _get_app

    root = get_command(_get_app())
    assert isinstance(root, click.Group)
    command = root.get_command(click.Context(root), "upgrade")
    assert command is not None
    return command


@pytest.mark.parametrize(
    ("argv", "available", "mode", "representation"),
    [
        ([], True, "apply", "human"),
        (["--json"], True, "apply", "outcome"),
        (["--project", "--json"], True, "preview", "legacy"),
        (["--dry-run", "--json"], True, "preview", "legacy"),
        (["--cli", "--dry-run", "--json"], True, "guidance", "legacy"),
        ([], False, "guidance", "human"),
        (["--json"], False, "guidance", "legacy"),
        (["--agent-check", "--json"], False, "hidden", "hidden"),
        (["--agent-choice", "later", "--agent-latest", "4.0", "--json"], False, "hidden", "hidden"),
    ],
)
def test_intent_uses_actual_definitions(argv: list[str], available: bool, mode: str, representation: str) -> None:
    intent = parse_upgrade_intent(_actual_upgrade_command(), argv, project_available=available)
    assert (intent.mode, intent.representation, intent.conflicts) == (mode, representation, ())


@pytest.mark.parametrize("argv", [["--target"], ["--unknown"], ["extra"]])
def test_intent_retains_click_usage_errors(argv: list[str]) -> None:
    with pytest.raises(click.UsageError):
        parse_upgrade_intent(_actual_upgrade_command(), argv, project_available=True)


def test_intent_alias_equals_order_and_callback_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    command = _actual_upgrade_command()

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Parse-only intent invoked a callback")

    monkeypatch.setattr(command, "callback", forbidden)
    for param in command.params:
        monkeypatch.setattr(param, "callback", forbidden)
    intent = parse_upgrade_intent(command, ["-v", "--target=not-a-version", "-y", "--dry-run", "--no-worktrees"], project_available=True)
    assert intent.target == "not-a-version"
    assert intent.mode == "preview"
    assert not intent.include_worktrees
    target = next(p for p in command.params if p.name == "target")
    monkeypatch.setattr(target, "default", forbidden)
    with pytest.raises(click.UsageError, match="callable default"):
        parse_upgrade_intent(command, [], project_available=True)


@pytest.mark.parametrize("hidden", [["--agent-check"], ["--agent-latest", "4.0"], ["--agent-choice", "later", "--agent-latest", "4.0"]])
def test_intent_hidden_conflicts_cover_implicit_preview(hidden: list[str]) -> None:
    command = _actual_upgrade_command()
    for ordinary in (["--project", "--json"], ["--cli", "--json"], ["--dry-run"], ["--target", "4.0"]):
        result = parse_upgrade_intent(command, [*ordinary, *hidden], project_available=False)
        assert result.conflicts


def test_intent_full_plan_precedence_uses_public_registration() -> None:
    command = _actual_upgrade_command()
    result = parse_upgrade_intent(command, ["--plan-json", "--json", "--dry-run", "--cli"], project_available=True)
    assert result.representation == "full"
    assert result.conflicts == ("--plan-json and --cli are mutually exclusive",)


def _apply_exact(assessment: OwnerAssessment) -> None:
    assert assessment.complete, assessment.diagnostics
    assert assessment.effects, "A known broken fixture must promise real physical work"
    roots = {assessment.root.root_id: assessment.root.path}
    before = snapshot(roots)
    with recheck_assets(assessment) as diagnostics:
        assert not diagnostics
        result = apply_assets(assessment, replace(assessment.consent, automatic=True))
    assert result.outcome == "applied", result
    actual = net_delta(before, snapshot(roots))
    expected = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in assessment.effects}
    observed = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in actual}
    assert expected == observed
    omitted = next(iter(expected))
    assert expected - {omitted} != observed, "The oracle must reject an omitted physical effect"


@pytest.mark.parametrize("owner", ["runtime", "commands", "skills"])
def test_owner_assessment_is_pure_exact_and_repeat_no_churn(
    owner: str,
    owner_home: Path,
    skill_source: Path,
) -> None:
    assessors: dict[str, Callable[[], OwnerAssessment]] = {
        "runtime": bootstrap.assess_runtime,
        "commands": lambda: agent_commands.assess_global_agent_commands(agent_keys=["claude"]),
        "skills": agent_skills.assess_global_agent_skills,
    }
    before = snapshot({"home": owner_home})
    assessment = assessors[owner]()
    assert_unchanged(before, snapshot({"home": owner_home}))
    _apply_exact(assessment)
    before = snapshot({"home": owner_home})
    second = assessors[owner]()
    assert second.complete and not second.effects
    with recheck_assets(second) as diagnostics:
        assert not diagnostics
        result = apply_assets(second, ApplyConsent(automatic=True))
    assert result.outcome == "skipped"
    assert_unchanged(before, snapshot({"home": owner_home}))


@pytest.mark.parametrize("change", ["source", "destination", "parent", "environment"])
def test_whole_batch_precondition_refusal_before_writes(
    change: str,
    owner_home: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_skills.ensure_global_agent_skills()
    destination = owner_home / ".agents/skills/spec-kitty/SKILL.md"
    destination.unlink()
    assessment = agent_skills.assess_global_agent_skills()
    assert assessment.effects and assessment.complete
    if change == "source":
        (skill_source / "spec-kitty/SKILL.md").write_text("changed source")
    elif change == "destination":
        destination.write_text("racing user")
    elif change == "parent":
        moved = destination.parent.with_name("saved")
        destination.parent.rename(moved)
        destination.parent.symlink_to(moved, target_is_directory=True)
    else:
        monkeypatch.setenv("SPEC_KITTY_HOME", str(owner_home / "different"))
    before = snapshot({"home": owner_home, "source": skill_source})
    with recheck_assets(assessment) as diagnostics:
        assert diagnostics and diagnostics[0].code == "precondition_changed"
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "precondition_changed" and not result.succeeded
    _assert_unchanged_tolerating_lock_holder_churn(before, snapshot({"home": owner_home, "source": skill_source}))


def test_exact_retired_skill_cleanup_and_edited_sibling_preservation(
    owner_home: Path,
    skill_source: Path,
) -> None:
    for name in ("paula-patterns", "debugger-debbie"):
        source = skill_source / name
        source.mkdir()
        (source / "SKILL.md").write_text(f"---\nname: {name}\ndescription: owned\n---\n# Body\n")
    agent_skills.ensure_global_agent_skills()
    edited = owner_home / ".agents/skills/debugger-debbie/SKILL.md"
    edited.chmod(0o644)
    edited.write_text("user edit")
    for name in ("paula-patterns", "debugger-debbie"):
        shutil.rmtree(skill_source / name)
    assessment = agent_skills.assess_global_agent_skills()
    assert any(e.action == "delete" and "paula-patterns" in e.path for e in assessment.effects)
    before = snapshot({"edited": edited})
    _apply_exact(assessment)
    assert_unchanged(before, snapshot({"edited": edited}))
    assert not (owner_home / ".agents/skills/paula-patterns").exists()
    assert not agent_skills.assess_global_agent_skills().effects


def test_prepared_bytes_and_state_backup_survive_later_clock(
    owner_home: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_skills.ensure_global_agent_skills()
    path = owner_home / ".agents/skills/spec-kitty/SKILL.md"
    path.chmod(0o644)
    path.write_text("user drift at T1")
    monkeypatch.setattr("time.time", lambda: 1_000_000_000.0)
    monkeypatch.setattr("time.time_ns", lambda: 1_000_000_000_000_000_000)
    baseline = agent_skills.assess_global_agent_skills()
    relative = path.relative_to(baseline.root.path).as_posix()
    assessment = agent_skills.assess_global_agent_skills(consent=ApplyConsent(overwrite_paths=(relative,)))
    backups = [e for e in assessment.effects if "/backups/state-" in e.path]
    assert backups

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Apply recollected or rerendered at T2")

    monkeypatch.setattr(agent_skills, "_discover_registry", forbidden)
    monkeypatch.setattr(agent_skills, "_get_cli_version", forbidden)
    monkeypatch.setattr("time.time", lambda: 2_000_000_000.0)
    monkeypatch.setattr("time.time_ns", lambda: 2_000_000_000_000_000_000)
    _apply_exact(assessment)
    backup_files = [e.destination for e in backups if e.after.kind == "file"]
    assert [p.read_bytes() for p in backup_files] == [b"user drift at T1"]


def test_missing_required_registry_is_incomplete_and_pure(owner_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: None)
    before = snapshot({"home": owner_home})
    result = agent_skills.assess_global_agent_skills()
    assert not result.complete and result.diagnostics and not result.effects
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_independent_equivalent_cold_homes_retain_same_asset_bytes(
    tmp_path: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.runtime.asset_preparation import PreparedAssets

    batches = []
    for label in ("first", "second"):
        home = tmp_path / label / "home"
        home.mkdir(parents=True)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
        before = snapshot({"home": home})
        assessment = agent_skills.assess_global_agent_skills()
        assert isinstance(assessment.prepared, PreparedAssets)
        batches.append(tuple((w.effect.path, w.effect.after, w.content) for w in assessment.prepared.writes))
        assert_unchanged(before, snapshot({"home": home}))
        _apply_exact(assessment)
        assert not agent_skills.assess_global_agent_skills().effects
    assert batches[0] == batches[1]


@contextmanager
def _wp01_owner_observer(log: Path) -> Iterator[None]:
    """Bind WP01's exact audit callback at an owner API seam, without copying it.

    WP01 main wraps CLI execution only. Its unmodified nested callback supplies
    this supplemental owner-level observer; this is not public startup evidence.
    """
    from tests.upgrade.preview_support import write_observer

    source = ast.parse(inspect.getsource(write_observer.main))
    record = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == "record")
    module = ast.fix_missing_locations(ast.Module(body=[record], type_ignores=[]))
    active = True
    with log.open("w") as stream:
        scope: dict[str, Any] = {"os": os, "json": json, "Any": Any, "EVENTS": write_observer.EVENTS, "policy": "deny", "descriptor": stream.fileno()}
        exec(compile(module, inspect.getfile(write_observer), "exec"), scope)
        callback = cast(Callable[[str, tuple[Any, ...]], None], scope["record"])

        def bounded(event: str, values: tuple[Any, ...]) -> None:
            if active:
                callback(event, values)

        sys.addaudithook(bounded)
        try:
            yield
        finally:
            active = False


def test_wp01_write_observer_denies_controls_and_all_owner_preparations(
    owner_home: Path,
    skill_source: Path,
    tmp_path: Path,
) -> None:
    control = tmp_path / "denied-control.log"
    with _wp01_owner_observer(control), pytest.raises(PermissionError, match="Observed write attempt"):
        (owner_home / "forbidden").write_text("write-delete must be observed")
    assert json.loads(control.read_text())["event"] == "open"
    assert not (owner_home / "forbidden").exists()
    log = tmp_path / "assessment-observer.log"
    before = snapshot({"home": owner_home})
    with _wp01_owner_observer(log):
        assessments = (
            bootstrap.assess_runtime(),
            agent_commands.assess_global_agent_commands(agent_keys=["claude"]),
            agent_skills.assess_global_agent_skills(),
        )
    assert all(a.complete and a.effects for a in assessments)
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_actual_slash_dispatch_retains_empty_selection_and_caller_root(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.tool_surface.model import SurfacePlan
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.slash_commands import SlashCommandsProvider, slash_command_definition
    from specify_cli.tool_surface.repair import SurfaceRepairService

    project = tmp_path / "project"
    project.mkdir()
    inputs = AssessmentInputs(OperationRoot("project", "project", project))
    definition = slash_command_definition()
    service = SurfaceRepairService((SlashCommandsProvider(),))
    plans = (SurfacePlan("claude", (), "T1", (definition,)),)
    assessments = service.assess(inputs, (), plans=plans)
    assert len(assessments) == 1 and assessments[0].root == inputs.root
    assert assessments[0].complete and assessments[0].effects
    assert all("claude" in effect.logical_owners for effect in assessments[0].effects)
    results = service.apply_assessments(assessments * 2, ApplyConsent(automatic=True))
    assert len(results) == 1 and results[0].outcome == "applied"
    assert not service.assess(inputs, (), plans=plans)[0].effects


def test_late_io_failure_keeps_actual_ids_and_never_stamps(
    owner_home: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.runtime import asset_preparation

    assessment = agent_skills.assess_global_agent_skills()
    original = asset_preparation._write_asset
    written: list[str] = []

    def fail_after_some_content(write: asset_preparation.AssetWrite) -> None:
        if write.effect.after.kind == "file" and written:
            raise OSError("injected disk failure")
        original(write)
        if write.effect.after.kind == "file":
            written.append(write.effect.id)

    monkeypatch.setattr(asset_preparation, "_write_asset", fail_after_some_content)
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "partial" and set(written) <= set(result.succeeded)
    assert result.failed and result.skipped and result.diagnostics[0].message == "injected disk failure"
    assert not (owner_home / ".kittify/cache/agent-skills.lock").exists()
    assert not (owner_home / ".kittify/cache/global_skills-assets.json").exists()


def test_backup_collision_and_owned_link_conversion_preserve_target(
    owner_home: Path,
    skill_source: Path,
) -> None:
    agent_skills.ensure_global_agent_skills()
    path = owner_home / ".agents/skills/spec-kitty/SKILL.md"
    external = owner_home / "external"
    external.write_text("external bytes")
    path.unlink()
    path.symlink_to(external)
    initial = agent_skills.assess_global_agent_skills()
    relative = path.relative_to(initial.root.path).as_posix()
    consent = ApplyConsent(overwrite_paths=(relative,))
    first = agent_skills.assess_global_agent_skills(consent=consent)
    backup = next(e.destination for e in first.effects if "/backups/state-" in e.path and e.after.kind == "symlink")
    state_root = next(p for p in backup.parents if p.name.startswith("state-"))
    state_root.mkdir(parents=True)
    (state_root / "sentinel").write_text("older backup")
    second = agent_skills.assess_global_agent_skills(consent=consent)
    assert any(state_root.name + "-1" in e.path for e in second.effects)
    before = snapshot({"external": external, "old-backup": state_root})
    _apply_exact(second)
    assert path.is_file() and not path.is_symlink()
    assert_unchanged(before, snapshot({"external": external, "old-backup": state_root}))


def test_stale_marker_with_exact_canonical_body_is_repaired(owner_home: Path) -> None:
    import re

    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    target = owner_home / ".claude/commands/spec-kitty.plan.md"
    target.chmod(0o644)
    target.write_bytes(re.sub(rb"spec-kitty-command-version: [^\r\n]+ -->", b"spec-kitty-command-version: 0.0.1 -->", target.read_bytes()))
    inventory = owner_home / ".kittify/cache/slash_commands-assets.json"
    inventory.unlink()
    assessment = agent_commands.assess_global_agent_commands(agent_keys=["claude"])
    assert any(e.destination == target and e.action == "update" for e in assessment.effects)
    _apply_exact(assessment)


def test_cross_release_upgrade_migrates_changed_command_body(owner_home: Path, caplog: pytest.LogCaptureFixture) -> None:
    """#4609: a 3.2.7-era canonical file (old marker + old release's body, no inventory)
    migrates in place to this release's changed canonical output instead of being
    silently preserved as an "Unproven existing asset"."""
    import logging

    caplog.set_level(logging.WARNING, logger="specify_cli.runtime.agent_commands")
    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    target = owner_home / ".claude/commands/spec-kitty.plan.md"
    target.chmod(0o644)
    stale = b"<!-- spec-kitty-command-version: 3.2.7 -->\n# old release canonical body\n"
    target.write_bytes(stale)
    # A pre-4.x install wrote no asset inventory to prove ownership with.
    (owner_home / ".kittify/cache/slash_commands-assets.json").unlink()
    assessment = agent_commands.assess_global_agent_commands(agent_keys=["claude"])
    effect = next(e for e in assessment.effects if e.destination == target)
    assert effect.action == "update"
    assert any(proof.kind == "canonical_content" for proof in effect.ownership)
    assert not [r for r in caplog.records if "could not migrate" in r.getMessage()], "A proven migration must not warn"
    _apply_exact(assessment)
    assert target.read_bytes() != stale, "The old-release file must be replaced by this release's output"
    second = agent_commands.assess_global_agent_commands(agent_keys=["claude"])
    assert second.complete and not second.effects, "The migrated file must land on the no-churn baseline"


@pytest.mark.parametrize("drift", ["edited-current-marker", "no-marker"])
def test_unmigratable_command_file_is_preserved_and_named(
    owner_home: Path,
    caplog: pytest.LogCaptureFixture,
    drift: str,
) -> None:
    """#4609: a canonical-name file that cannot be proven unedited stays preserved
    AND is named in one warning -- never silently left behind."""
    import logging

    caplog.set_level(logging.WARNING, logger="specify_cli.runtime.agent_commands")
    agent_commands.ensure_global_agent_commands(agent_keys=["claude"])
    target = owner_home / ".claude/commands/spec-kitty.plan.md"
    target.chmod(0o644)
    drifted = target.read_bytes() + b"\nuser edit below the current marker\n" if drift == "edited-current-marker" else b"user's own file with no managed marker\n"
    target.write_bytes(drifted)
    before = snapshot({"home": owner_home})
    assessment = agent_commands.assess_global_agent_commands(agent_keys=["claude"])
    assert not any(e.destination == target for e in assessment.effects), "Unproven drift must stay preserved"
    disposition = next(d for d in assessment.dispositions if (d.path or "").endswith("spec-kitty.plan.md"))
    # Inventory-known drift maps to ``consent_required``; unproven files to ``preserve``.
    assert disposition.state in {"preserve", "consent_required"}
    [record] = [r for r in caplog.records if "could not migrate" in r.getMessage()]
    assert "spec-kitty.plan.md" in record.getMessage()
    assert_unchanged(before, snapshot({"home": owner_home}))
    assert target.read_bytes() == drifted


def test_orphan_atomic_artifact_is_incomplete_and_never_changed(owner_home: Path, skill_source: Path) -> None:
    from specify_cli.runtime.generated_writer import generated_temporary_path

    target = owner_home / ".agents/skills/spec-kitty/SKILL.md"
    target.parent.mkdir(parents=True)
    artifact = generated_temporary_path(target)
    artifact.write_bytes(b"unproven ignored content")
    before = snapshot({"home": owner_home})
    assessment = agent_skills.assess_global_agent_skills()
    assert not assessment.complete and "artifact" in assessment.diagnostics[0].message
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "failed"
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_inventory_change_refuses_whole_batch(owner_home: Path, skill_source: Path) -> None:
    agent_skills.ensure_global_agent_skills()
    (owner_home / ".agents/skills/spec-kitty/SKILL.md").unlink()
    assessment = agent_skills.assess_global_agent_skills()
    inventory = owner_home / ".kittify/cache/global_skills-assets.json"
    inventory.write_bytes(inventory.read_bytes() + b"\n")
    before = snapshot({"home": owner_home})
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "precondition_changed" and not result.succeeded
    _assert_unchanged_tolerating_lock_holder_churn(before, snapshot({"home": owner_home}))


def test_source_catalog_addition_refuses_whole_batch(owner_home: Path, skill_source: Path) -> None:
    assessment = agent_skills.assess_global_agent_skills()
    new_skill = skill_source / "new-canonical-skill"
    new_skill.mkdir()
    (new_skill / "SKILL.md").write_text("# Added after assessment\n")
    before = snapshot({"home": owner_home})
    result = apply_assets(assessment, ApplyConsent(automatic=True))
    assert result.outcome == "precondition_changed" and not result.succeeded
    assert_unchanged(before, snapshot({"home": owner_home}))


@pytest.mark.parametrize("through_provider", [False, True])
def test_command_effects_retain_their_physical_agent_owners(owner_home: Path, tmp_path: Path, through_provider: bool) -> None:
    from specify_cli.tool_surface.model import SurfacePlan
    from specify_cli.tool_surface.operations import AssessmentInputs, OperationRoot
    from specify_cli.tool_surface.providers.slash_commands import SlashCommandsProvider, slash_command_definition
    from specify_cli.tool_surface.repair import SurfaceRepairService

    keys = ("claude", "gemini")
    if through_provider:
        project = tmp_path / "project"
        project.mkdir()
        inputs = AssessmentInputs(OperationRoot("project", "project", project))
        definition = slash_command_definition()
        provider = SlashCommandsProvider()
        service = SurfaceRepairService((provider,))
        plans = tuple(SurfacePlan(key, (), "T1", (definition,)) for key in keys)
        statuses = tuple(provider.probe(provider.expand(definition, key, project)[0]) for key in keys)
        assessment = service.assess(inputs, statuses, plans=plans)[0]
        frames = next(observation.value for observation in assessment.inputs_fingerprint if observation.name == "provider_instances")
        assert isinstance(frames, tuple) and frames == tuple((s.instance, s.state) for s in statuses)
        assert frames[0][0] is statuses[0].instance
    else:
        assessment = agent_commands.assess_global_agent_commands(agent_keys=list(keys))
    assert assessment.complete
    for key in keys:
        directory = agent_commands.get_global_command_dir(key)
        files = [effect for effect in assessment.effects if effect.destination.parent == directory and effect.after.kind == "file"]
        assert files
        assert all(effect.logical_owners == (key,) for effect in files)
        if through_provider:
            from specify_cli.tool_surface.status import _surface_id

            expected_ids = tuple(_surface_id(status.instance) for status in statuses if status.instance.owner == key)
            assert all(effect.surface_ids == expected_ids for effect in files)
    if through_provider:
        result = service.apply_assessments((assessment,), ApplyConsent(automatic=True))
        assert result[0].outcome == "applied"
    else:
        _apply_exact(assessment)


def test_installed_skill_catalog_prepares_under_write_denial(owner_home: Path, tmp_path: Path) -> None:
    """Real package/local resolver, not the fixture-selected registry seam."""
    log = tmp_path / "installed-catalog-observer.log"
    before = snapshot({"home": owner_home})
    with _wp01_owner_observer(log):
        assessment = agent_skills.assess_global_agent_skills()
    assert assessment.complete and assessment.effects
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": owner_home}))


def _global_dispatch(assessments: tuple[OwnerAssessment, ...]) -> tuple[Any, ...]:
    from specify_cli.tool_surface.providers.protocol import AssessingSurfaceProvider
    from specify_cli.tool_surface.repair import SurfaceRepairService

    def forbidden_reassessment(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Dispatcher must not reassess retained global assets")

    providers = tuple(
        SimpleNamespace(provider_key=key, assess=forbidden_reassessment, recheck=recheck_assets, apply=apply_assets)
        for key in dict.fromkeys(a.owner_key for a in assessments)
    )
    assert all(isinstance(provider, AssessingSurfaceProvider) for provider in providers)
    return tuple(SurfaceRepairService(providers).apply_assessments(assessments, ApplyConsent(automatic=True)))


def _global_preparation() -> tuple[OwnerAssessment, ...]:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    return (assess_global_assets(),)


def _caller_skill_assessment(registry: SkillRegistry, agents: list[str]) -> OwnerAssessment:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    selection = agent_skills.GlobalSkillSelection(skills=registry.discover_skills(), agent_keys=agents)
    return assess_global_assets(runtime=False, commands=False, skill_selection=selection)


def test_caller_local_registry_selection_reaches_real_global_dispatch(owner_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.skills.installer import install_all_skills

    source = tmp_path / "local-catalog/caller-local/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("---\nname: caller-local\ndescription: Supplied catalog\n---\n# Caller source\n")
    registry = SkillRegistry(source.parent.parent)
    project = tmp_path / "project"
    project.mkdir()
    manifest = install_all_skills(project, ["claude"], registry)
    assert len(manifest.entries) == 1
    assert (owner_home / ".claude/skills/caller-local/SKILL.md").read_bytes() == source.read_bytes()

    cold = tmp_path / "cold-home"
    cold.mkdir()
    monkeypatch.setenv("HOME", str(cold))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(cold / ".kittify"))
    before = snapshot({"home": cold, "source": source.parent.parent})
    log = tmp_path / "selection-observer.log"
    with _wp01_owner_observer(log):
        assessment = _caller_skill_assessment(registry, ["claude"])
    assert assessment.complete, assessment.diagnostics
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": cold, "source": source.parent.parent}))
    destination = cold / ".claude/skills/caller-local/SKILL.md"
    matching = [effect for effect in assessment.effects if effect.destination == destination]
    assert matching, "Existing global preparation omits the caller's canonical registry"
    assert all(set(effect.logical_owners) <= {"claude"} for effect in assessment.effects)
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    assert destination.read_bytes() == source.read_bytes()
    assert not (cold / ".agents").exists()
    assert not (cold / ".kittify/cache/agent-skills.lock").exists()
    expected = {(str(e.destination.relative_to(cold)), e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects}
    actual = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in net_delta(before, snapshot({"home": cold, "source": source.parent.parent}))}
    assert expected == actual
    after = snapshot({"home": cold})
    repeat = _caller_skill_assessment(registry, ["claude"])
    assert repeat.complete and not repeat.effects
    assert_unchanged(after, snapshot({"home": cold}))


def test_real_cold_global_dispatch_exact_and_no_churn(owner_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("SPEC_KITTY_TEMPLATE_ROOT", "SPEC_KITTY_PACKS_ROOT"):
        monkeypatch.delenv(key, raising=False)
    for key, suffix in {
        "USERPROFILE": "",
        "XDG_CACHE_HOME": ".cache",
        "XDG_DATA_HOME": ".local/share",
        "XDG_STATE_HOME": ".local/state",
        "APPDATA": "appdata",
        "LOCALAPPDATA": "localappdata",
    }.items():
        monkeypatch.setenv(key, str(owner_home / suffix))
    roots = {"home": owner_home}
    before = snapshot(roots)
    log = tmp_path / "global-observer.log"
    with _wp01_owner_observer(log):
        assessments = _global_preparation()
    assert all(a.complete and a.effects for a in assessments)
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot(roots))
    results = _global_dispatch(assessments)
    if not all(r.outcome == "applied" for r in results):
        assert_unchanged(before, snapshot(roots))
    assert all(r.outcome == "applied" for r in results), [(r.outcome, r.diagnostics) for r in results]
    expected = {
        (str(e.destination.relative_to(owner_home)), e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for a in assessments for e in a.effects
    }
    actual = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.target, e.after.mode) for e in net_delta(before, snapshot(roots))}
    assert expected == actual
    assert expected - {next(iter(expected))} != actual
    after = snapshot(roots)
    repeat = _global_preparation()
    assert all(a.complete and not a.effects for a in repeat)
    assert all(r.outcome == "skipped" for r in _global_dispatch(repeat))
    assert_unchanged(after, snapshot(roots))


def _selection_catalog(tmp_path: Path) -> SkillRegistry:
    catalog = tmp_path / "caller-catalog"
    for name in ("selected-local", "unselected-local"):
        directory = catalog / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Caller supplied\n---\n# Exact bytes\n")
        (directory / "references").mkdir()
        (directory / "references/guide.txt").write_bytes(b"nested source\r\n")
        (directory / "empty").mkdir()
    return SkillRegistry(catalog)


@pytest.mark.parametrize("agents", [["claude"], ["codex", "vibe", "codex"]])
def test_skill_selection_subset_and_shared_agent_dispatch(owner_home: Path, tmp_path: Path, agents: list[str]) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets
    from specify_cli.skills.paths import get_primary_global_skill_root

    catalog = _selection_catalog(tmp_path)
    selected = catalog.discover_skills()[:1]
    before = snapshot({"home": owner_home})
    log = tmp_path / "subset-observer.log"
    with _wp01_owner_observer(log):
        selection = agent_skills.GlobalSkillSelection(skills=selected, agent_keys=agents)
        assessment = assess_global_assets(runtime=False, commands=False, skill_selection=selection)
    assert assessment.complete, assessment.diagnostics
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": owner_home}))
    assert len({effect.destination for effect in assessment.effects}) == len(assessment.effects)
    assert all(set(effect.logical_owners) == set(agents) for effect in assessment.effects)
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    destination = get_primary_global_skill_root(agents[0])
    assert destination is not None
    assert (destination / "selected-local/references/guide.txt").read_bytes() == b"nested source\r\n"
    assert (destination / "selected-local/empty").is_dir()
    assert not (destination / "unselected-local").exists()
    expected = {(str(e.destination.relative_to(owner_home)), e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects}
    actual = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in net_delta(before, snapshot({"home": owner_home}))}
    assert expected == actual
    assert not (owner_home / ".kittify/cache/agent-skills.lock").exists()


def test_skill_selection_snapshots_mutable_caller_inputs(owner_home: Path, tmp_path: Path) -> None:
    from dataclasses import FrozenInstanceError, fields
    from specify_cli.runtime.asset_preparation import assess_global_assets

    skills = _selection_catalog(tmp_path).discover_skills()[:1]
    agents = ["claude"]
    selection = agent_skills.GlobalSkillSelection(skills=skills, agent_keys=agents)
    original_hash = hash(selection)
    skills[0].references.append(tmp_path / "never-selected")
    skills.clear()
    agents[:] = ["codex"]
    for field in fields(selection):
        with pytest.raises(FrozenInstanceError):
            setattr(selection, field.name, ())
    assert hash(selection) == original_hash
    assessment = assess_global_assets(runtime=False, commands=False, skill_selection=selection)
    assert assessment.complete and assessment.effects
    assert all(set(effect.logical_owners) == {"claude"} for effect in assessment.effects)
    assert all("unselected-local" not in effect.path for effect in assessment.effects)


def test_skill_selection_full_global_dispatch_retains_every_family(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    selection = agent_skills.GlobalSkillSelection(skills=_selection_catalog(tmp_path).discover_skills()[:1], agent_keys=["claude"])
    before = snapshot({"home": owner_home})
    log = tmp_path / "all-families-observer.log"
    with _wp01_owner_observer(log):
        assessment = assess_global_assets(agent_keys=["claude"], skill_selection=selection)
    assert assessment.complete and assessment.effects
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": owner_home}))
    assert {effect.root.root_id for effect in assessment.effects} == {"runtime_bootstrap", "slash_commands", "global_skills"}
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    expected = {(str(e.destination.relative_to(owner_home)), e.action, e.after.kind, e.after.sha256, e.after.mode) for e in assessment.effects}
    actual = {(e.path, e.action, e.after.kind, e.after.sha256, e.after.mode) for e in net_delta(before, snapshot({"home": owner_home}))}
    assert expected == actual
    after = snapshot({"home": owner_home})
    repeat = assess_global_assets(agent_keys=["claude"], skill_selection=selection)
    assert repeat.complete and not repeat.effects
    assert all(result.outcome == "skipped" for result in _global_dispatch((repeat,)))
    assert_unchanged(after, snapshot({"home": owner_home}))


@pytest.mark.parametrize("empty", ["skills", "agents", "wrapper-agent"])
def test_skill_selection_explicit_empty_never_discovers_package(owner_home: Path, tmp_path: Path, empty: str) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    skills = [] if empty == "skills" else _selection_catalog(tmp_path).discover_skills()
    agents = [] if empty == "agents" else ["q"] if empty == "wrapper-agent" else ["claude"]
    before = snapshot({"home": owner_home})
    selection = agent_skills.GlobalSkillSelection(skills=skills, agent_keys=agents)
    assessment = assess_global_assets(runtime=False, commands=False, skill_selection=selection)
    assert assessment.complete and not assessment.effects
    assert all(result.outcome == "skipped" for result in _global_dispatch((assessment,)))
    assert_unchanged(before, snapshot({"home": owner_home}))


@pytest.mark.parametrize("change", ["source", "membership", "destination", "source-parent"])
def test_skill_selection_source_change_refuses_whole_coordinated_batch(owner_home: Path, tmp_path: Path, change: str) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    skill = _selection_catalog(tmp_path).discover_skills()[0]
    selection = agent_skills.GlobalSkillSelection(skills=[skill], agent_keys=["claude"])
    assessment = assess_global_assets(agent_keys=["claude"], skill_selection=selection)
    assert assessment.complete and assessment.effects
    if change == "source":
        skill.skill_md.write_text("Changed source\n")
    elif change == "membership":
        (skill.skill_dir / "new-file").write_text("late source\n")
    elif change == "source-parent":
        moved = tmp_path / "moved-source"
        skill.skill_dir.rename(moved)
        skill.skill_dir.symlink_to(moved, target_is_directory=True)
    else:
        destination = owner_home / ".claude/skills/selected-local/SKILL.md"
        destination.parent.mkdir(parents=True)
        destination.write_text("Concurrent user content\n")
    before = snapshot({"home": owner_home, "source": skill.skill_dir.parent})
    results = _global_dispatch((assessment,))
    assert results and all(result.outcome == "precondition_changed" for result in results)
    assert_unchanged(before, snapshot({"home": owner_home, "source": skill.skill_dir.parent}))


@pytest.mark.parametrize("stale", ["missing-file", "missing-directory", "source-link"])
def test_skill_selection_stale_sources_are_incomplete_without_fallback(owner_home: Path, tmp_path: Path, stale: str) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    skill = _selection_catalog(tmp_path).discover_skills()[0]
    selection = agent_skills.GlobalSkillSelection(skills=[skill], agent_keys=["claude"])
    if stale == "missing-file":
        skill.skill_md.unlink()
    else:
        moved = tmp_path / "moved"
        skill.skill_dir.rename(moved)
        if stale == "source-link":
            skill.skill_dir.symlink_to(moved, target_is_directory=True)
    before = snapshot({"home": owner_home, "source": tmp_path / "caller-catalog"})
    log = tmp_path / "stale-observer.log"
    with _wp01_owner_observer(log):
        assessment = assess_global_assets(runtime=False, commands=False, skill_selection=selection)
    assert not assessment.complete and assessment.diagnostics and not assessment.effects
    assert log.read_bytes() == b""
    assert_unchanged(before, snapshot({"home": owner_home, "source": tmp_path / "caller-catalog"}))


def test_skill_selection_adopts_equal_legacy_then_repairs_changed_source(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.skills.installer import install_all_skills

    registry = _selection_catalog(tmp_path)
    project = tmp_path / "legacy-project"
    project.mkdir()
    install_all_skills(project, ["claude"], registry)
    (owner_home / ".kittify/cache/global_skills-assets.json").unlink()
    adopted = _caller_skill_assessment(registry, ["claude"])
    adopted_results = _global_dispatch((adopted,))
    assert all(result.outcome == "applied" for result in adopted_results), [(result.outcome, result.diagnostics) for result in adopted_results]
    source = registry.discover_skills()[0].skill_md
    source.write_bytes(source.read_bytes().replace(b"Exact bytes", b"Updated source"))
    destination = owner_home / ".claude/skills/selected-local/SKILL.md"
    assessment = _caller_skill_assessment(registry, ["claude"])
    assert any(effect.destination == destination and effect.action == "update" for effect in assessment.effects)
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    assert destination.read_bytes() == source.read_bytes()
    after = snapshot({"home": owner_home})
    repeat = _caller_skill_assessment(registry, ["claude"])
    assert repeat.complete and not repeat.effects
    assert_unchanged(after, snapshot({"home": owner_home}))


def test_skill_selection_does_not_authorize_differing_untracked_content(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.skills.installer import install_all_skills

    registry = _selection_catalog(tmp_path)
    project = tmp_path / "legacy-project"
    project.mkdir()
    install_all_skills(project, ["claude"], registry)
    (owner_home / ".kittify/cache/global_skills-assets.json").unlink()
    destination = owner_home / ".claude/skills/selected-local/SKILL.md"
    before = snapshot({"legacy": destination})
    registry.discover_skills()[0].skill_md.write_text("Different source, not ownership proof\n")
    assessment = _caller_skill_assessment(registry, ["claude"])
    assert assessment.complete
    assert not any(effect.destination == destination for effect in assessment.effects), assessment.effects
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    assert_unchanged(before, snapshot({"legacy": destination}))


def test_skill_selection_preserves_unselected_owned_retired_tree(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets
    from specify_cli.skills.retired import RETIRED_CANONICAL_SKILL_NAMES

    catalog = _selection_catalog(tmp_path)
    skills = catalog.discover_skills()
    retired = sorted(RETIRED_CANONICAL_SKILL_NAMES)[0]
    skills[1] = replace(skills[1], name=retired)
    selection = agent_skills.GlobalSkillSelection(skills=skills, agent_keys=["claude"])
    assessment = assess_global_assets(runtime=False, commands=False, skill_selection=selection)
    assert all(result.outcome == "applied" for result in _global_dispatch((assessment,)))
    preserved = owner_home / ".claude/skills" / retired
    before = snapshot({"unselected": preserved})
    subset = agent_skills.GlobalSkillSelection(skills=skills[:1], agent_keys=["claude"])
    reduced = assess_global_assets(runtime=False, commands=False, skill_selection=subset)
    assert reduced.complete and not reduced.effects
    assert_unchanged(before, snapshot({"unselected": preserved}))


def test_skill_selection_none_keeps_real_default_package_policy(owner_home: Path) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    default = assess_global_assets(runtime=False, commands=False)
    explicit_none = assess_global_assets(runtime=False, commands=False, skill_selection=None)
    assert default.complete and explicit_none.complete
    assert default.effects == explicit_none.effects
    assert len({owner for effect in default.effects for owner in effect.logical_owners}) > 1
    assert any(effect.destination == owner_home / ".kittify/cache/agent-skills.lock" for effect in default.effects)


@pytest.mark.parametrize("invalid", ["name", "markdown", "conflicting-source", "agent"])
def test_skill_selection_invalid_input_is_not_silently_accepted(tmp_path: Path, invalid: str) -> None:
    skill = _selection_catalog(tmp_path).discover_skills()[0]
    skills = [skill]
    agents = ["claude"]
    if invalid == "name":
        skills = [replace(skill, name="../escape")]
    elif invalid == "markdown":
        skills = [replace(skill, skill_md=tmp_path / "unrelated.md")]
    elif invalid == "conflicting-source":
        skills.append(replace(skill, skill_dir=tmp_path / "other", skill_md=tmp_path / "other/SKILL.md"))
    else:
        agents = ["not-an-agent"]
    with pytest.raises(ValueError):
        agent_skills.GlobalSkillSelection(skills=skills, agent_keys=agents)


def test_skill_selection_requires_enabled_skill_family() -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    selection = agent_skills.GlobalSkillSelection(skills=[], agent_keys=[])
    with pytest.raises(ValueError, match="requires skills=True"):
        assess_global_assets(skills=False, skill_selection=selection)


@pytest.mark.parametrize("change", ["source", "destination", "parent", "environment", "inventory"])
def test_coordinated_global_rechecks_every_family_before_writes(
    owner_home: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    assessment = assess_global_assets(agent_keys=["claude"])
    assert assessment.complete and assessment.effects
    if change == "source":
        (skill_source / "spec-kitty/SKILL.md").write_text("changed source")
    elif change == "destination":
        target = owner_home / ".agents/skills/spec-kitty/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("custom occupant")
    elif change == "parent":
        external = owner_home / "external"
        external.mkdir()
        (owner_home / ".claude").symlink_to(external, target_is_directory=True)
    elif change == "inventory":
        cache = owner_home / ".kittify/cache"
        cache.mkdir(parents=True)
        (cache / "global_skills-assets.json").write_text("{}")
    else:
        monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(owner_home / "changed-config"))
    before = snapshot({"home": owner_home})
    result = _global_dispatch((assessment,))[0]
    assert result.outcome == "precondition_changed", result
    assert not result.succeeded and result.diagnostics
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_coordinated_global_retains_shared_ownership_and_duplicate_dispatch(owner_home: Path, skill_source: Path) -> None:
    from specify_cli.runtime.asset_preparation import PreparedAssets, assess_global_assets

    assessment = assess_global_assets(agent_keys=["claude"])
    assert assessment.complete
    prepared = assessment.prepared
    assert isinstance(prepared, PreparedAssets)
    assert len(prepared.lock_paths) == 3
    assert len({e.destination for e in assessment.effects}) == len(assessment.effects)
    assert {e.owner for e in assessment.effects} == {"global_assets"}
    common = next(e for e in assessment.effects if e.destination == owner_home / ".kittify/cache")
    assert {proof.reference.split(":")[0] for proof in common.ownership} == {"runtime_bootstrap", "slash_commands", "global_skills"}
    assert {"runtime_bootstrap", "claude"} <= set(common.logical_owners)
    assert {write.effect for write in prepared.writes} == set(assessment.effects)
    results = _global_dispatch((assessment, assessment))
    assert len(results) == 1 and results[0].outcome == "applied"
    assert set(results[0].succeeded) == {e.id for e in assessment.effects}


def test_separate_cold_global_batches_still_refuse(owner_home: Path, skill_source: Path) -> None:
    batches = (bootstrap.assess_runtime(), agent_commands.assess_global_agent_commands(agent_keys=["claude"]), agent_skills.assess_global_agent_skills())
    before = snapshot({"home": owner_home})
    results = _global_dispatch(batches)
    assert all(r.outcome == "failed" and r.diagnostics for r in results)
    assert_unchanged(before, snapshot({"home": owner_home}))
    assert apply_assets(batches[0], ApplyConsent(automatic=True)).outcome == "applied"
    before = snapshot({"home": owner_home})
    assert all(apply_assets(a, ApplyConsent(automatic=True)).outcome == "precondition_changed" for a in batches[1:])
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_coordinated_global_source_failure_blocks_other_families(owner_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: None)
    before = snapshot({"home": owner_home})
    assessment = assess_global_assets(agent_keys=["claude"])
    assert not assessment.complete and assessment.diagnostics
    assert _global_dispatch((assessment,))[0].outcome == "failed"
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_coordinated_global_partial_failure_does_not_certify_any_family(
    owner_home: Path,
    skill_source: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.runtime import asset_preparation

    assessment = asset_preparation.assess_global_assets(agent_keys=["claude"])
    original = asset_preparation._write_asset

    def fail_skill(write: Any) -> None:
        if write.effect.destination.name == "SKILL.md":
            raise OSError("deliberate skill write failure")
        original(write)

    monkeypatch.setattr(asset_preparation, "_write_asset", fail_skill)
    result = _global_dispatch((assessment,))[0]
    assert result.outcome == "partial" and result.succeeded and result.failed and result.skipped
    assert set(result.succeeded + result.failed + result.skipped) == {e.id for e in assessment.effects}
    assert not tuple((owner_home / ".kittify/cache").glob("*-assets.json"))
    assert not (owner_home / ".kittify/cache/version.lock").exists()
    assert not (owner_home / ".kittify/cache/agent-skills.lock").exists()
    assert not (owner_home / ".kittify/cache/agent-commands.lock").exists()


def test_coordinated_global_selection_is_explicit(owner_home: Path, skill_source: Path) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    selected = assess_global_assets(runtime=False, commands=True, skills=False, agent_keys=["claude"])
    assert selected.complete and selected.effects
    assert all(proof.reference.startswith("slash_commands") for e in selected.effects for proof in e.ownership)
    assert all(e.destination != owner_home / ".kittify/cache/agent-commands.lock" for e in selected.effects)
    assert not assess_global_assets(runtime=False, commands=False, skills=False).complete


def test_managed_tree_uses_portable_directory_mode(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.runtime.asset_preparation import AssetPreparation, global_asset_root

    source = tmp_path / "readonly-package-tree"
    source.mkdir()
    (source / "asset.txt").write_text("asset")
    source.chmod(0o555)
    destination = owner_home / "missions/software-dev"
    prepared = AssetPreparation(
        "runtime_bootstrap",
        global_asset_root("runtime_bootstrap", (owner_home,)),
        owner_home / "cache",
        ".update.lock",
        ApplyConsent(),
    )

    prepared.tree(source, destination, managed_tree=True)

    write = prepared.writes[destination]
    assert write.effect.before.kind == "absent"
    assert write.effect.after.mode == 0o755


def test_skill_tree_uses_portable_directory_mode(owner_home: Path, tmp_path: Path) -> None:
    from specify_cli.runtime.agent_skills import _prepare_skill_tree
    from specify_cli.runtime.asset_preparation import AssetPreparation, global_asset_root

    source = tmp_path / "readonly-skill"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: portable\n---\n")
    source.chmod(0o555)
    destination = owner_home / ".claude/skills/portable"
    prepared = AssetPreparation(
        "global_skills",
        global_asset_root("global_skills", (owner_home,)),
        owner_home / "cache",
        ".skills.lock",
        ApplyConsent(),
    )

    _prepare_skill_tree(prepared, source, destination, "portable")

    write = prepared.writes[destination]
    assert write.effect.before.kind == "absent"
    assert write.effect.after.mode == 0o755


@pytest.mark.parametrize("conflict", ["bytes", "state", "membership", "environment"])
def test_global_builder_refuses_contradictory_family_inputs(owner_home: Path, monkeypatch: pytest.MonkeyPatch, conflict: str) -> None:
    from specify_cli.runtime.asset_preparation import AssetPreparation, _GlobalAssetPreparation, global_asset_root

    consent = ApplyConsent()
    batch = _GlobalAssetPreparation(consent)
    root = global_asset_root("runtime_bootstrap", (owner_home,))
    first = AssetPreparation("runtime_bootstrap", root, owner_home / "cache", ".update.lock", consent)
    first.observe(owner_home, members=True)
    first.asset(owner_home / "shared", b"first", 0o444)
    assessment = first.finish(None, "unused")
    batch.include(first, assessment.effects)
    if conflict == "environment":
        monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(owner_home / "changed"))
    elif conflict == "state":
        (owner_home / "shared").write_text("occupant")
    elif conflict == "membership":
        (owner_home / "unrelated").mkdir()
    second = AssetPreparation("global_skills", root, owner_home / "cache", ".agent-skills.lock", consent)
    second.observe(owner_home, members=True)
    second.asset(owner_home / "shared", b"second" if conflict == "bytes" else b"first", 0o444)
    assessment = second.finish(None, "unused")
    before = snapshot({"home": owner_home})
    with pytest.raises(ValueError, match="Global"):
        batch.include(second, assessment.effects)
    assert_unchanged(before, snapshot({"home": owner_home}))


def test_coordinated_global_observes_healthy_family_locks(owner_home: Path, skill_source: Path) -> None:
    from specify_cli.runtime.asset_preparation import assess_global_assets

    assert _global_dispatch((assess_global_assets(agent_keys=["claude"]),))[0].outcome == "applied"
    command = next(agent_commands.get_global_command_dir("claude").glob("spec-kitty.*"))
    command.unlink()
    lock = owner_home / ".kittify/cache/.update.lock"
    external = owner_home / "external-lock"
    external.write_text("unowned lock target")
    lock.unlink()
    lock.symlink_to(external)
    before = snapshot({"home": owner_home})
    assessment = assess_global_assets(agent_keys=["claude"])
    assert not assessment.complete and assessment.diagnostics
    assert _global_dispatch((assessment,))[0].outcome == "failed"
    assert_unchanged(before, snapshot({"home": owner_home}))
