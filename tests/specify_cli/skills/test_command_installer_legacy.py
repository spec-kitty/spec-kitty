"""Legacy dotted command skills and canonical-path collisions (#6475, FR-004 / FR-019 / FR-020).

Every repair path that prepares the command batch -- ``install`` (init, agent config,
``doctor skills --fix``), ``prune_stale`` (``doctor skills --fix``), ``remove`` and the provider's
``prepare_commands(prune=True)`` (tool-surface repair, upgrade) -- applies one legacy rule:

* a legacy ``.agents/skills/spec-kitty.<cmd>/SKILL.md`` manifest entry whose file still has the
  recorded bytes is deleted (its folder only when then empty);
* an edited one is kept, its entry dropped, and a ``legacy_kept`` warning names it.

A file Spec Kitty does not own at a canonical ``spec-kitty-<cmd>`` path is skipped with a
``collision`` warning while the rest of the batch installs. The pytest twin of
``tests/scenarios/init/command-skill-collision.feature``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.command_installer import (
    CANONICAL_COMMANDS,
    COLLISION,
    LEGACY_KEPT,
    InstallerError,
    apply_commands,
    install,
    install_warnings,
    prepare_commands,
    prune_stale,
    remove,
    verify,
)
from specify_cli.skills.command_skill_names import command_skill_rel_path, legacy_command_skill_rel_path
from specify_cli.skills.manifest_store import ManifestEntry
from specify_cli.skills.ownership import is_projected_skills_path
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, Disposition, OperationRoot, OwnerAssessment

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_EDITED = b"my own edits to the plan skill\n"
_OLD_RENDER = b"---\nname: spec-kitty.{cmd}\n---\nan older release's rendering\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("agents:\n  available:\n    - codex\n    - vibe\n", encoding="utf-8")
    return tmp_path


def _seed_legacy(repo: Path, commands: tuple[str, ...] = CANONICAL_COMMANDS, *, agents: tuple[str, ...] = ("codex",)) -> None:
    """Lay out what a pre-#6475 release installed: dotted folders recorded in the manifest."""
    manifest = manifest_store.load(repo)
    for command in commands:
        rel = legacy_command_skill_rel_path(command)
        content = _OLD_RENDER.replace(b"{cmd}", command.encode())
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest.upsert(ManifestEntry(rel, manifest_store.fingerprint(content), agents, "2026-01-01T00:00:00+00:00", "3.2.0"))
    manifest_store.save(repo, manifest)


def _manifest_paths(repo: Path) -> set[str]:
    return {entry.path for entry in manifest_store.load(repo).entries}


def _edit_legacy(repo: Path, command: str = "plan") -> Path:
    path = repo / legacy_command_skill_rel_path(command)
    path.write_bytes(_EDITED)
    return path


def _canonical_rels() -> set[str]:
    return {command_skill_rel_path(command) for command in CANONICAL_COMMANDS}


def _provider_prepare(repo: Path, *, adopt_only: bool = False) -> OwnerAssessment:
    inputs = AssessmentInputs(OperationRoot("project", "project", repo), consent=ApplyConsent(automatic=True))
    return prepare_commands(inputs, ("codex",), prune=not adopt_only, adopt_only=adopt_only)


# ---------------------------------------------------------------------------
# Owned legacy skills are retired
# ---------------------------------------------------------------------------


def test_install_deletes_unmodified_legacy_skills_and_records_only_hyphen_paths(repo: Path) -> None:
    _seed_legacy(repo)

    report = install(repo, "codex")

    assert sorted(report.legacy_removed) == sorted(legacy_command_skill_rel_path(c) for c in CANONICAL_COMMANDS)
    assert report.legacy_kept == []
    assert not list((repo / ".agents/skills").glob("spec-kitty.*"))
    assert _manifest_paths(repo) == _canonical_rels()
    assert all((repo / rel).is_file() for rel in _canonical_rels())


def test_legacy_folder_with_a_user_file_keeps_the_folder(repo: Path) -> None:
    _seed_legacy(repo, ("plan",))
    extra = repo / ".agents/skills/spec-kitty.plan/notes.md"
    extra.write_text("mine\n", encoding="utf-8")

    install(repo, "codex")

    assert extra.read_text(encoding="utf-8") == "mine\n"
    assert not (repo / legacy_command_skill_rel_path("plan")).exists()


def test_absent_legacy_file_only_drops_the_entry(repo: Path) -> None:
    _seed_legacy(repo, ("plan",))
    (repo / legacy_command_skill_rel_path("plan")).unlink()

    report = install(repo, "codex")

    assert report.legacy_removed == [legacy_command_skill_rel_path("plan")]
    assert legacy_command_skill_rel_path("plan") not in _manifest_paths(repo)


def test_second_install_after_migration_changes_nothing(repo: Path) -> None:
    _seed_legacy(repo)
    _edit_legacy(repo)
    install(repo, "codex")
    manifest_before = (repo / ".kittify/command-skills-manifest.json").read_bytes()

    report = install(repo, "codex")

    assert report.legacy_removed == report.legacy_kept == []
    assert (repo / ".kittify/command-skills-manifest.json").read_bytes() == manifest_before
    assert (repo / legacy_command_skill_rel_path("plan")).read_bytes() == _EDITED


def test_partial_earlier_run_with_both_forms_converges(repo: Path) -> None:
    install(repo, "codex")
    _seed_legacy(repo, ("plan", "tasks"))

    report = install(repo, "codex")

    assert sorted(report.legacy_removed) == sorted(legacy_command_skill_rel_path(c) for c in ("plan", "tasks"))
    assert len(report.already_installed) == len(CANONICAL_COMMANDS)
    assert _manifest_paths(repo) == _canonical_rels()


# ---------------------------------------------------------------------------
# Edited legacy skills survive every repair path
# ---------------------------------------------------------------------------


def _assert_edited_legacy_kept(repo: Path, path: Path) -> None:
    assert path.read_bytes() == _EDITED
    assert legacy_command_skill_rel_path("plan") not in _manifest_paths(repo)
    assert not any(command_installer.is_legacy_rel_path(p) for p in _manifest_paths(repo))


def test_edited_legacy_kept_through_install_with_warning(repo: Path) -> None:
    _seed_legacy(repo)
    edited = _edit_legacy(repo)

    report = install(repo, "codex")

    _assert_edited_legacy_kept(repo, edited)
    rel = legacy_command_skill_rel_path("plan")
    assert report.legacy_kept == [rel]
    [warning] = install_warnings(report)
    assert rel in warning and "no longer managed" in warning


def test_edited_legacy_kept_through_prune_stale(repo: Path) -> None:
    _seed_legacy(repo)
    edited = _edit_legacy(repo)

    pruned = prune_stale(repo)

    _assert_edited_legacy_kept(repo, edited)
    assert legacy_command_skill_rel_path("plan") not in pruned
    assert legacy_command_skill_rel_path("tasks") in pruned
    assert not (repo / legacy_command_skill_rel_path("tasks")).exists()


def test_edited_legacy_kept_through_provider_prepare_with_prune(repo: Path) -> None:
    _seed_legacy(repo)
    edited = _edit_legacy(repo)

    assessment = _provider_prepare(repo)
    rel = legacy_command_skill_rel_path("plan")
    assert assessment.complete, assessment.diagnostics
    assert [(d.path, d.state) for d in assessment.dispositions if d.state == LEGACY_KEPT] == [(rel, LEGACY_KEPT)]
    assert not any(effect.path == rel for effect in assessment.effects), "an edited legacy file is never a delete effect"
    result = apply_commands(assessment, assessment.consent)

    assert result.outcome == "applied"
    _assert_edited_legacy_kept(repo, edited)
    assert _manifest_paths(repo) == _canonical_rels()


def test_edited_legacy_kept_through_remove_of_its_last_owner(repo: Path) -> None:
    _seed_legacy(repo, agents=("codex",))
    edited = _edit_legacy(repo)

    report = remove(repo, "codex")

    _assert_edited_legacy_kept(repo, edited)
    assert report.legacy_kept == [legacy_command_skill_rel_path("plan")]
    assert legacy_command_skill_rel_path("plan") not in report.deref
    assert install_warnings(report)
    assert not (repo / legacy_command_skill_rel_path("tasks")).exists()  # unmodified, last owner gone


def test_remove_of_one_owner_only_releases_it_from_legacy_entries(repo: Path) -> None:
    """Review cycle 1: a remove-only pass installs nothing, so the other owners keep their skills."""
    _seed_legacy(repo, agents=("codex", "vibe"))
    edited = _edit_legacy(repo)

    report = remove(repo, "vibe")

    assert report.legacy_removed == report.legacy_kept == []
    assert sorted(report.kept) == sorted(legacy_command_skill_rel_path(c) for c in CANONICAL_COMMANDS)
    assert {entry.agents for entry in manifest_store.load(repo).entries} == {("codex",)}
    assert all((repo / legacy_command_skill_rel_path(c)).is_file() for c in CANONICAL_COMMANDS)
    assert edited.read_bytes() == _EDITED


def test_remove_of_an_agent_that_owns_no_legacy_entry_leaves_it_alone(repo: Path) -> None:
    _seed_legacy(repo, ("plan",), agents=("codex",))
    install(repo, "vibe")  # vibe's install migrates codex's legacy entry too (one rule on install)
    _seed_legacy(repo, ("tasks",), agents=("codex",))

    remove(repo, "vibe")

    assert manifest_store.load(repo).find(legacy_command_skill_rel_path("tasks")) is not None
    assert (repo / legacy_command_skill_rel_path("tasks")).is_file()


def test_edited_legacy_is_never_drift_deleted_on_the_derived_surface(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The DERIVED/IGNORED drift-delete branch of ``remove_entry`` must not see a legacy entry."""
    monkeypatch.setattr(command_installer, "_shared_skills_projection_regenerable", lambda: True)
    _seed_legacy(repo)
    edited = _edit_legacy(repo)

    prune_stale(repo)

    assert edited.read_bytes() == _EDITED


def test_adopt_only_leaves_legacy_entries_alone(repo: Path) -> None:
    _seed_legacy(repo)
    _edit_legacy(repo)

    assessment = _provider_prepare(repo, adopt_only=True)

    assert assessment.complete, assessment.diagnostics
    assert not any(command_installer.is_legacy_rel_path(effect.path) for effect in assessment.effects)
    assert not any(d.state == LEGACY_KEPT for d in assessment.dispositions)


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks need privileges on Windows")
def test_legacy_entry_behind_a_link_is_kept(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    _seed_legacy(repo, ("plan",))
    folder = repo / ".agents/skills/spec-kitty.plan"
    outside = tmp_path_factory.mktemp("outside")
    (folder / "SKILL.md").rename(outside / "SKILL.md")
    folder.rmdir()
    folder.symlink_to(outside, target_is_directory=True)

    report = install(repo, "codex")

    assert report.legacy_kept == [legacy_command_skill_rel_path("plan")]
    assert (outside / "SKILL.md").is_file()
    assert folder.is_symlink()


# ---------------------------------------------------------------------------
# Collision at a canonical path
# ---------------------------------------------------------------------------


def test_user_file_at_a_canonical_path_is_skipped_and_the_rest_installs(repo: Path) -> None:
    rel = command_skill_rel_path("plan")
    mine = repo / rel
    mine.parent.mkdir(parents=True)
    mine.write_text("my own plan skill\n", encoding="utf-8")

    report = install(repo, "codex")

    assert mine.read_text(encoding="utf-8") == "my own plan skill\n"
    assert report.collisions == [rel]
    assert report.installed_count == len(CANONICAL_COMMANDS) - 1
    assert _manifest_paths(repo) == _canonical_rels() - {rel}
    [warning] = install_warnings(report)
    assert rel in warning and "spec-kitty doctor skills --fix" in warning
    verified = verify(repo)
    assert verified.collisions == [rel]
    assert rel not in verified.orphans


def test_foreign_folder_without_skill_md_is_a_collision(repo: Path) -> None:
    folder = repo / ".agents/skills/spec-kitty-plan"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("mine\n", encoding="utf-8")

    report = install(repo, "codex")

    assert report.collisions == [command_skill_rel_path("plan")]
    assert not (folder / "SKILL.md").exists()
    assert verify(repo).collisions == [command_skill_rel_path("plan")]


def test_empty_leftover_canonical_folder_is_filled(repo: Path) -> None:
    (repo / ".agents/skills/spec-kitty-plan").mkdir(parents=True)

    report = install(repo, "codex")

    assert report.collisions == []
    assert (repo / command_skill_rel_path("plan")).is_file()


def test_unowned_canonical_bytes_are_adopted_not_a_collision(repo: Path) -> None:
    install(repo, "codex")
    manifest = manifest_store.load(repo)
    manifest.remove_path(command_skill_rel_path("plan"))
    manifest_store.save(repo, manifest)

    report = install(repo, "codex")

    assert report.collisions == []
    assert command_skill_rel_path("plan") in _manifest_paths(repo)


def test_a_directory_at_skill_md_still_refuses(repo: Path) -> None:
    """A directory at the ``SKILL.md`` path keeps the conservative ``preserve`` refusal."""
    (repo / command_skill_rel_path("plan")).mkdir(parents=True)

    with pytest.raises(InstallerError):
        install(repo, "codex")


# ---------------------------------------------------------------------------
# Read-only reporting and ownership
# ---------------------------------------------------------------------------


def test_verify_reports_legacy_entries_and_folders_but_not_as_drift(repo: Path) -> None:
    _seed_legacy(repo, ("plan",))
    _edit_legacy(repo)
    loose = repo / legacy_command_skill_rel_path("tasks")
    loose.parent.mkdir(parents=True)
    loose.write_text("never recorded\n", encoding="utf-8")

    report = verify(repo)

    assert sorted(report.legacy) == sorted(legacy_command_skill_rel_path(c) for c in ("plan", "tasks"))
    assert report.drift == report.stale == report.unsafe == report.orphans == []


def test_user_skills_sharing_the_prefix_are_never_reported_or_touched(repo: Path) -> None:
    mine = repo / ".agents/skills/spec-kitty-mine/SKILL.md"
    dotted = repo / ".agents/skills/spec-kitty.mine/SKILL.md"
    for path in (mine, dotted):
        path.parent.mkdir(parents=True)
        path.write_text("mine\n", encoding="utf-8")

    install(repo, "codex")
    report = verify(repo)

    assert mine.read_text(encoding="utf-8") == dotted.read_text(encoding="utf-8") == "mine\n"
    reported = {*report.orphans, *report.collisions, *report.legacy, *report.stale, *report.unsafe}
    assert not any("spec-kitty-mine" in p or "spec-kitty.mine" in p for p in reported)


def test_verify_reports_a_leftover_legacy_folder_not_a_missing_skill_md(repo: Path) -> None:
    """Review cycle 1: only real paths are reported; a folder with other files is named itself."""
    folder = repo / ".agents/skills/spec-kitty.plan"
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text("mine\n", encoding="utf-8")

    assert verify(repo).legacy == [".agents/skills/spec-kitty.plan/"]


def test_orphan_in_a_canonical_folder_is_still_reported(repo: Path) -> None:
    install(repo, "codex")
    extra = repo / ".agents/skills/spec-kitty-plan/notes.md"
    extra.write_text("x\n", encoding="utf-8")

    assert verify(repo).orphans == [".agents/skills/spec-kitty-plan/notes.md"]


def test_is_projected_accepts_legacy_paths_only_for_deletion() -> None:
    legacy = legacy_command_skill_rel_path("plan")
    assert is_projected_skills_path(command_skill_rel_path("plan"), set(), for_deletion=False)
    assert not is_projected_skills_path(legacy, set(), for_deletion=False)
    assert is_projected_skills_path(legacy, set())  # both shipped callers untrack (deletion)
    assert not is_projected_skills_path(".agents/skills/spec-kitty.mine/SKILL.md", set())
    assert is_projected_skills_path(legacy, {legacy}, for_deletion=False)


@pytest.mark.parametrize("state", [COLLISION, LEGACY_KEPT])
def test_disposition_vocabulary_accepts_the_warning_states(state: str) -> None:
    assert Disposition("command_skills", "project", ".agents/skills/x/SKILL.md", state, "reason").state == state


def test_disposition_vocabulary_still_rejects_unknown_states() -> None:
    with pytest.raises(ValueError, match="Invalid disposition"):
        Disposition("command_skills", "project", None, "skipped", "reason")


# ---------------------------------------------------------------------------
# A-M1: today's render under the legacy name proves ownership too
# ---------------------------------------------------------------------------


def test_legacy_rendering_restores_the_dotted_name_tokens_and_user_input_example() -> None:
    from specify_cli.skills.command_installer import legacy_rendering

    today = (
        b"---\nname: spec-kitty-plan\ndescription: d\n---\n"
        b"Run /spec-kitty-plan, then $spec-kitty-tasks or /skill:spec-kitty-tasks-outline.\n"
        b"Keep /spec-kitty-implement-review and docs/spec-kitty-plan.md as they are.\n"
        b"after `/spec-kitty-<command>` or `$spec-kitty-<command>`\n"
    )

    assert legacy_rendering(today, "plan") == (
        b"---\nname: spec-kitty.plan\ndescription: d\n---\n"
        b"Run /spec-kitty.plan, then $spec-kitty.tasks or /skill:spec-kitty.tasks-outline.\n"
        b"Keep /spec-kitty-implement-review and docs/spec-kitty-plan.md as they are.\n"
        b"after `/spec-kitty.<command>` or `$spec-kitty.<command>`\n"
    )


def test_unedited_legacy_file_with_a_stale_recorded_hash_is_still_retired(repo: Path) -> None:
    """Cross-checkout case: the tracked manifest's hash went stale, the ignored bytes did not."""
    from specify_cli.skills.command_installer import legacy_rendering

    install(repo, "codex")
    fresh = (repo / command_skill_rel_path("plan")).read_bytes()
    rel = legacy_command_skill_rel_path("plan")
    (repo / rel).parent.mkdir(parents=True)
    (repo / rel).write_bytes(legacy_rendering(fresh, "plan"))
    manifest = manifest_store.load(repo)
    manifest.upsert(ManifestEntry(rel, "0" * 64, ("codex",), "2026-01-01T00:00:00+00:00", "3.2.0"))
    manifest_store.save(repo, manifest)

    report = install(repo, "codex")

    assert report.legacy_removed == [rel]
    assert not (repo / rel).exists()


def test_stale_recorded_hash_and_an_older_render_keeps_the_file(repo: Path) -> None:
    """Neither proof holds (recorded hash stale, bytes not today's legacy render): keep it."""
    _seed_legacy(repo, ("plan",))
    rel = legacy_command_skill_rel_path("plan")
    manifest = manifest_store.load(repo)
    entry = manifest.find(rel)
    assert entry is not None
    manifest.upsert(ManifestEntry(rel, "0" * 64, entry.agents, entry.installed_at, entry.spec_kitty_version))
    manifest_store.save(repo, manifest)

    pruned = prune_stale(repo)

    assert rel not in pruned
    assert (repo / rel).is_file()
    assert rel not in _manifest_paths(repo)


# ---------------------------------------------------------------------------
# Operator ruling 2026-10-21: an unrecorded dotted skill is ours only when it is
# exactly the legacy rendering (a clone that pulled an already-migrated manifest)
# ---------------------------------------------------------------------------


def _write_exact_legacy(repo: Path, command: str = "plan") -> Path:
    """Write today's render under the legacy name, with no manifest entry recording it."""
    from specify_cli.skills.command_installer import legacy_rendering

    today = command_installer._render_command_skill(repo, command, "codex", command_installer._get_version())
    path = repo / legacy_command_skill_rel_path(command)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(legacy_rendering(today, command))
    return path


def test_unrecorded_exact_legacy_render_is_retired_by_install(repo: Path) -> None:
    install(repo, "codex")  # a migrated, committed manifest: no dotted entry
    path = _write_exact_legacy(repo)
    rel = legacy_command_skill_rel_path("plan")
    before = verify(repo)
    assert before.legacy == before.legacy_owned == [rel]

    report = install(repo, "codex")

    assert report.legacy_removed == [rel]
    assert report.legacy_kept == report.legacy_unrecorded == []
    assert install_warnings(report) == []
    assert not path.parent.exists()
    assert _manifest_paths(repo) == _canonical_rels()
    after = verify(repo)
    assert after.legacy == after.legacy_owned == []


def test_unrecorded_exact_legacy_render_is_retired_by_the_provider_repair(repo: Path) -> None:
    path = _write_exact_legacy(repo, "tasks")

    assessment = _provider_prepare(repo)
    assert assessment.complete, assessment.diagnostics
    rel = legacy_command_skill_rel_path("tasks")
    assert {effect.path for effect in assessment.effects if effect.after.kind == "absent"} == {rel, Path(rel).parent.as_posix()}
    assert apply_commands(assessment, assessment.consent).outcome == "applied"

    assert not path.parent.exists()
    assert (repo / command_skill_rel_path("tasks")).is_file()


def test_unrecorded_dotted_skill_with_other_bytes_is_kept_with_a_warning(repo: Path) -> None:
    from specify_cli.skills.command_installer import unrecorded_legacy_warning

    path = repo / legacy_command_skill_rel_path("plan")
    path.parent.mkdir(parents=True)
    path.write_bytes(_EDITED)
    rel = legacy_command_skill_rel_path("plan")

    report = install(repo, "codex")

    assert path.read_bytes() == _EDITED
    assert report.legacy_unrecorded == [rel]
    assert report.legacy_removed == report.legacy_kept == []
    assert install_warnings(report) == [unrecorded_legacy_warning(rel)]
    assert verify(repo).legacy_owned == []
    assessment = _provider_prepare(repo)
    [disposition] = [d for d in assessment.dispositions if d.state == LEGACY_KEPT]
    assert command_installer.disposition_warning(disposition.state, disposition.path, disposition.reason) == unrecorded_legacy_warning(rel)


def test_unrecorded_exact_render_with_other_files_keeps_the_folder_with_a_warning(repo: Path) -> None:
    from specify_cli.skills.command_installer import unrecorded_legacy_warning

    path = _write_exact_legacy(repo)
    (path.parent / "notes.md").write_text("mine\n", encoding="utf-8")
    folder = f"{path.parent.relative_to(repo).as_posix()}/"

    report = install(repo, "codex")

    assert not path.exists()
    assert (path.parent / "notes.md").read_text(encoding="utf-8") == "mine\n"
    assert report.legacy_removed == [legacy_command_skill_rel_path("plan")]
    assert report.legacy_unrecorded == [folder]
    assert install_warnings(report) == [unrecorded_legacy_warning(folder)]
    assert verify(repo).legacy == [folder]


def test_recorded_legacy_deleted_from_a_folder_with_other_files_warns_about_the_folder(repo: Path) -> None:
    _seed_legacy(repo, ("plan",))
    extra = repo / ".agents/skills/spec-kitty.plan/notes.md"
    extra.write_text("mine\n", encoding="utf-8")

    report = install(repo, "codex")

    assert report.legacy_unrecorded == [".agents/skills/spec-kitty.plan/"]


@pytest.mark.skipif(os.name == "nt", reason="directory symlinks need privileges on Windows")
def test_unrecorded_exact_render_behind_a_link_is_kept(repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    path = _write_exact_legacy(repo)
    outside = tmp_path_factory.mktemp("outside")
    path.rename(outside / "SKILL.md")
    path.parent.rmdir()
    path.parent.symlink_to(outside, target_is_directory=True)
    rel = legacy_command_skill_rel_path("plan")

    assert verify(repo).legacy_owned == []
    report = install(repo, "codex")

    assert report.legacy_unrecorded == [rel]
    assert (outside / "SKILL.md").is_file()
    assert path.parent.is_symlink()


def test_unrecorded_exact_render_is_left_alone_by_non_installing_preparations(repo: Path) -> None:
    """Only an installing pass retires it: remove, prune and adopt-only install nothing to replace it."""
    install(repo, "codex")
    path = _write_exact_legacy(repo)

    prune_stale(repo)
    remove(repo, "codex")
    assert path.is_file()
    assessment = _provider_prepare(repo, adopt_only=True)
    assert not any(command_installer.is_legacy_rel_path(effect.path) for effect in assessment.effects)
    assert path.is_file()


def test_unrecorded_exact_render_edited_after_preparation_refuses_the_apply(repo: Path) -> None:
    """The bytes the rule read are observed: a change before apply is a precondition failure."""
    path = _write_exact_legacy(repo)
    assessment = _provider_prepare(repo)
    assert assessment.complete, assessment.diagnostics
    path.write_bytes(_EDITED)

    result = apply_commands(assessment, assessment.consent)

    assert result.outcome == "precondition_changed"
    assert path.read_bytes() == _EDITED


def test_dotted_folder_appearing_after_preparation_refuses_the_apply(repo: Path) -> None:
    assessment = _provider_prepare(repo)
    assert assessment.complete, assessment.diagnostics
    _write_exact_legacy(repo)

    assert apply_commands(assessment, assessment.consent).outcome == "precondition_changed"
