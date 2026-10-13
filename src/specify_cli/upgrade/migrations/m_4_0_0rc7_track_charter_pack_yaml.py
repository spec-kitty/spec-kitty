"""Migration: keep the project pack's ``pack.yaml`` trackable after the cutover (#6076).

The charter-pack cutover (:mod:`m_4_0_0rc6_charter_pack_cutover`) rewrites a
consumer's retired project-layer ignore rules (a blanket ``**`` rule plus a
``!…/graph.yaml`` allow-rule) into ``.kittify/charter-packs/**`` +
a sibling ``graph.yaml`` allow-rule but adds no allow-rule for ``pack.yaml``. The later
:mod:`m_4_0_0rc7_pack_level_backfill` then writes
``.kittify/charter-packs/pack.yaml``, which the blanket ``.kittify/charter-packs/**``
rule ignores — so the pack's ``pack_level`` never reaches other contributors
and each clone mints its own ``pack_id``.

The cutover now emits the allow-rule going forward, but a consumer that already
ran the cutover (at ``4.0.0rc6``/``4.0.0rc7``) is past it: the cutover is
``runs_first`` and re-selects only on *legacy* state, which a post-cutover
project no longer has. This standalone migration heals that population —
*where the blanket ``.kittify/charter-packs/**`` rule is present and
``!.kittify/charter-packs/pack.yaml`` is absent, add the allow-rule* — sharing
the single placement/idempotency authority in
:mod:`_charter_pack_gitignore` with the cutover.

It targets ``4.0.0rc7`` so a project already on an rc7 build is reached through
the registry's same-version ``detect()`` path (:meth:`MigrationRegistry.get_applicable`),
and a project below rc7 is reached through the ordinary version window.

Guards (``.gitignore`` safety mirrors the cutover's own step and
:data:`specify_cli.gitignore_manager`): a symlinked/unreadable ``.gitignore`` is
never followed and is left for the operator to handle by hand (non-fatal — this
is a cosmetic allow-rule backfill, not worth failing a whole upgrade over); a
readable file that is *known* to need the rule but cannot be written is a loud
failure. ``never mkdir``: a project with no ``.gitignore`` is a clean no-op.
"""

from __future__ import annotations

from pathlib import Path

from kernel.charter_pack_paths import PROJECT_PACK_ROOT_POSIX
from specify_cli.gitignore_manager import (
    GitignorePathError,
    is_gitignore_path_ignored,
    read_gitignore_text,
    write_gitignore_text,
)

from ..registry import MigrationRegistry
from ._charter_pack_gitignore import (
    CHARTER_PACK_YAML_ALLOW_RULE,
    ensure_pack_yaml_allow_rule,
    needs_pack_yaml_allow_rule,
)
from .base import BaseMigration, MigrationResult

__all__ = ["TrackCharterPackYamlMigration"]

_GITIGNORE = ".gitignore"
_PACK_YAML = f"{PROJECT_PACK_ROOT_POSIX}/pack.yaml"


@MigrationRegistry.register
class TrackCharterPackYamlMigration(BaseMigration):
    """Add ``!.kittify/charter-packs/pack.yaml`` where the blanket ignore rule hides it."""

    migration_id = "4.0.0rc7_track_charter_pack_yaml"
    description = "Track charter-pack pack.yaml: add its allow-rule where the blanket ignore rule hides it (#6076)"
    target_version = "4.0.0rc7"

    @staticmethod
    def _gitignore(project_path: Path) -> Path:
        return project_path / _GITIGNORE

    def detect(self, project_path: Path) -> bool:
        # A symlinked/unsafe .gitignore raises GitignorePathError, which the
        # registry treats as a fail-closed selection (``_detect_fail_closed``) —
        # the same contract the sibling gitignore-backfill migrations rely on.
        # Letting it propagate (rather than swallowing it to ``False``) keeps the
        # same-version rc7 population consistent with the version-window
        # population, which reaches ``apply()`` without consulting ``detect()``;
        # ``apply()`` then surfaces the non-fatal "add it by hand" warning for
        # both, instead of silently skipping the rc7 case.
        try:
            text = read_gitignore_text(self._gitignore(project_path))
        except OSError:
            # An unreadable .gitignore (e.g. a directory) fails closed like the
            # symlink case: select the migration so apply() surfaces the warning.
            return True
        return text is not None and needs_pack_yaml_allow_rule(text)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        path = self._gitignore(project_path)
        try:
            text = read_gitignore_text(path)
        except (GitignorePathError, OSError) as exc:
            # Non-fatal: leave the unsafe .gitignore untouched and tell the
            # operator, rather than failing the whole upgrade over a cosmetic
            # allow-rule backfill they can add by hand.
            return MigrationResult(
                success=True,
                changes_made=[],
                warnings=[f"{_GITIGNORE} could not be read safely ({exc}); add {CHARTER_PACK_YAML_ALLOW_RULE} by hand if needed"],
            )
        if text is None or not needs_pack_yaml_allow_rule(text):
            return MigrationResult(success=True, changes_made=[])

        lines, changed = ensure_pack_yaml_allow_rule(text.splitlines(keepends=True))
        if not changed:
            return MigrationResult(success=True, changes_made=[])

        if dry_run:
            return MigrationResult(success=True, changes_made=[f"Would add {CHARTER_PACK_YAML_ALLOW_RULE} to {_GITIGNORE}"])

        try:
            write_gitignore_text(path, "".join(lines))
        except (GitignorePathError, OSError) as exc:
            # The rule is known to be needed here, so a failed write is a loud
            # failure (mirrors the cutover's own gitignore-write handling).
            return MigrationResult(success=False, errors=[f"{_GITIGNORE} could not be written ({exc}); make it writable, then run `spec-kitty upgrade` again"])

        result = MigrationResult(success=True, changes_made=[f"Added {CHARTER_PACK_YAML_ALLOW_RULE} to {_GITIGNORE}"])
        if is_gitignore_path_ignored(project_path, _PACK_YAML) is True:
            # A later rule (e.g. a `.kittify/` line) still ignores the file.
            result.warnings.append(f"{_PACK_YAML} is still ignored by another {_GITIGNORE} rule; check your {_GITIGNORE} so it can be committed")
        return result
