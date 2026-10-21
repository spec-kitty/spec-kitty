"""Which ``.agents/skills/`` paths are spec-kitty-projected, and which are a team's own (#5964).

``.agents/skills/`` is a shared root: a team's own committed skills live beside the command
skills spec-kitty projects there. Anything that untracks or commits deletions under that root
asks this module whether a path is spec-kitty's to touch. A path counts as projected only
when it matches the stable canonical command-skill pattern or a skills manifest records it as
installed; everything else is team content and must be preserved.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from specify_cli.skills import manifest_store
from specify_cli.skills.command_installer import is_canonical_rel_path, is_legacy_rel_path
from specify_cli.skills.manifest import load_manifest as load_skills_manifest
from specify_cli.skills.manifest_errors import ManifestError

#: Shared skills projection root, project-relative POSIX with a trailing slash.
SKILLS_ROOT_PREFIX = ".agents/skills/"


def manifest_owned_skills_paths(project_path: Path) -> set[str]:
    """Project-relative POSIX paths either skills manifest records as spec-kitty-installed.

    Reads the two installer manifests that are the standing ownership authority
    (C-001): ``.kittify/command-skills-manifest.json`` (``manifest_store``) and
    ``.kittify/skills-manifest.json`` (``skills.manifest``). An unreadable or
    absent manifest contributes nothing, so a path it would otherwise claim
    stays tracked -- fail-closed toward preserving user content (#5964).
    """
    owned: set[str] = set()
    with contextlib.suppress(ManifestError):
        owned.update(entry.path for entry in manifest_store.load(project_path).entries)
    skills_manifest = load_skills_manifest(project_path)
    if skills_manifest is not None:
        owned.update(entry.installed_path for entry in skills_manifest.entries)
    return owned


def is_projected_skills_path(rel_posix: str, manifest_owned: set[str]) -> bool:
    """Whether a ``.agents/skills/`` path is spec-kitty-projected and safe to *untrack*.

    A deletion predicate only: projected means the stable canonical command-skill pattern
    ``.agents/skills/spec-kitty-<command>/SKILL.md`` (the single authority is
    :func:`~specify_cli.skills.command_installer.is_canonical_rel_path`), a path a skills
    manifest records as installed, or the pre-#6475 dotted path
    ``.agents/skills/spec-kitty.<command>/SKILL.md`` of a canonical command (never another
    dotted name). Everything else is a team's own committed skill sharing the prefix, and
    must stay tracked.

    Both callers remove a path from the index: the shipped 3.2.5 gitignore backfill
    (``git rm --cached``, frozen, so its call cannot change) and the upgrade commit that
    carries that untrack (``upgrade/autocommit.py``). There is deliberately no
    ``for_deletion`` switch (WP09 rework, squad m2): a dotted path is never spec-kitty's to
    *write or keep managing*, so a future caller asking that question needs its own predicate
    that excludes legacy paths, rather than a default that silently admits them.
    """
    if is_canonical_rel_path(rel_posix) or rel_posix in manifest_owned:
        return True
    return bool(is_legacy_rel_path(rel_posix))
