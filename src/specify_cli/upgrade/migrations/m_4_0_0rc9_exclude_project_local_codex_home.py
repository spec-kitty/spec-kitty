"""Migration: keep a project-local Codex home out of git in every clone (#7729).

``4.0.0rc8_narrow_agent_gitignore`` replaced the whole-folder agent lines with
Spec Kitty's own files. A project whose ``.codex/`` is also a Codex home
(``CODEX_HOME=<project>/.codex``, advice Spec Kitty once gave) then had its
personal Codex state shown as untracked.

The committed agent-files block now ignores the Codex home state that is never
team config (``agent_utils.codex_home.CODEX_HOME_STATE_ENTRIES``). What the
block cannot decide is ``.codex/config.toml``: shared config in a plain project
folder, personal config in a Codex home. That is decided here, per clone: when
this clone's ``.codex/`` is a Codex home and git shows files from it, the
project's ``.codex/`` is added to the clone's common-dir ``.git/info/exclude``
(never committed) as a rule anchored at the project, so a sibling project's
team ``.codex/`` in the same repository stays visible. Files already committed
there stay tracked.

The effect lives outside version control, so the migration is clone-local: it
is pending in every clone until it has excluded a Codex home there. On the
upgrade path a clone without one is not settled (``detect()`` is False, so the
run records nothing that settles it) and is checked again on its next upgrade.
A clone seeded by ``spec-kitty init`` is the exception: the init seed records
every clone-local step whose ``detect()`` is False as done, so a Codex home that
appears there later is covered by the committed block only (``config.toml``
stays visible; tracked in #7782). An operator's own higher-precedence rule that
un-ignores ``.codex/`` (``!.codex/`` in a ``.gitignore``) wins over the exclude
rule: the step warns and succeeds rather than failing every upgrade. A narrower
negation (``!.codex/config.toml``) is pre-empted by the folder rule, since git
does not descend into an excluded folder; the note names ``git add -f``. Listing the other
agent-folder files git now shows is ``4.0.0rc9_report_newly_visible_agent_files``.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError, status_entries
from kernel.git_topology import GitTopologyError, git_toplevel_uncached
from specify_cli.agent_utils.codex_home import CODEX_DIR, is_codex_home
from specify_cli.core.git_ops import exclude_from_git_index, git_exclude_file, is_git_repo

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc9_exclude_project_local_codex_home"

_EXCLUSION_NOTE = (
    "This clone's .codex/ folder is a Codex home (CODEX_HOME state found), so it was added to .git/info/exclude "
    "to keep its personal files out of git in this clone only. Files already committed under .codex/ stay tracked; "
    "use 'git add -f' to add a new team file there."
)


def codex_dir_from_root(project_path: Path) -> str | None:
    """The project's ``.codex/`` as a path relative to the repository top level, or ``None`` outside a repository."""
    try:
        top = git_toplevel_uncached(project_path)
        prefix = project_path.resolve().relative_to(top).as_posix()
    except (GitTopologyError, OSError, ValueError):
        return None
    return CODEX_DIR if prefix == "." else f"{prefix}/{CODEX_DIR}"


def _visible_codex_files(project_path: Path, codex_dir: str) -> list[str]:
    """Untracked, unignored files git shows under the project's ``.codex/`` (repository-root paths)."""
    try:
        entries = status_entries(project_path, pathspecs=[CODEX_DIR], untracked="all", optional_locks=False)
    except (GitCommandError, OSError, ValueError):
        return []
    return sorted(path for path in (entry.path.as_posix() for entry in entries if entry.xy == "??") if path.startswith(codex_dir))


def _exposed_codex_home(project_path: Path) -> tuple[str, list[str]] | None:
    """``(codex dir from root, visible files)`` when this clone's Codex home shows files, else ``None``."""
    if not (project_path / CODEX_DIR).is_dir() or not is_codex_home(project_path):
        return None
    codex_dir = codex_dir_from_root(project_path)
    if codex_dir is None:
        return None
    visible = _visible_codex_files(project_path, codex_dir)
    return (codex_dir, visible) if visible else None


def _exclude_has_rule(project_path: Path, rule: str) -> bool:
    """Whether the common-dir ``info/exclude`` holds *rule* as a line of its own."""
    exclude_file = git_exclude_file(project_path)
    if exclude_file is None:
        return False
    try:
        return rule in {line.strip() for line in exclude_file.read_text(encoding="utf-8").splitlines()}
    except OSError:
        return False


def _overridden_warning(rule: str, visible: list[str]) -> str:
    return (
        f"Added {rule} to .git/info/exclude, but a rule of your own in a .gitignore un-ignores this clone's Codex home, "
        f"so git still shows {len(visible)} file(s) there, for example {visible[0]}. Spec Kitty keeps your rule; "
        "remove it, or add your own ignore rule for the personal Codex files, before you stage everything."
    )


@MigrationRegistry.register
class ExcludeProjectLocalCodexHomeMigration(BaseMigration):
    """Exclude a Codex-home ``.codex/`` in this clone's ``.git/info/exclude`` (#7729)."""

    migration_id = MIGRATION_ID
    description = "Keep a project-local Codex home out of git in every clone (#7729)"
    target_version = "4.0.0rc9"
    clone_local_effect = True  # effect is .git/info/exclude, never a committed file

    def detect(self, project_path: Path) -> bool:
        """Whether this clone's ``.codex/`` is a Codex home that git shows files from."""
        return is_git_repo(project_path) and _exposed_codex_home(project_path) is not None

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not is_git_repo(project_path):
            return False, "Not a git repository"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not is_git_repo(project_path):
            return MigrationResult(success=True, changes_made=["Skipped: not a git repository"])
        exposed = _exposed_codex_home(project_path)
        if exposed is None:
            return MigrationResult(success=True, changes_made=["No Codex home to exclude in this clone"])

        codex_dir, _visible = exposed
        rule = f"/{codex_dir}"
        if dry_run:
            return MigrationResult(success=True, changes_made=[f"Would add {rule} to .git/info/exclude (this clone's .codex/ is a Codex home)"])

        exclude_from_git_index(project_path, [rule])
        if not _exclude_has_rule(project_path, rule):
            return MigrationResult(success=False, errors=[f"Could not write {rule} to .git/info/exclude; this clone's Codex home files stay visible"])
        still_visible = _visible_codex_files(project_path, codex_dir)
        if still_visible:
            # The rule is written, so a higher-precedence rule of the operator's own (``!.codex/`` in a
            # .gitignore) un-ignores the folder. Respect it: warn once and do not fail every upgrade.
            return MigrationResult(
                success=True,
                changes_made=[f"Added {rule} to .git/info/exclude (this clone's .codex/ is a Codex home)"],
                warnings=[_overridden_warning(rule, still_visible)],
                manual_review_required=True,
            )
        return MigrationResult(
            success=True,
            changes_made=[f"Added {rule} to .git/info/exclude (this clone's .codex/ is a Codex home)"],
            warnings=[_EXCLUSION_NOTE],
        )
