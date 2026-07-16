"""Copy a template tree into PACK_PATH honouring ``.templateignore``."""

from __future__ import annotations

import fnmatch
import shutil
from dataclasses import dataclass
from pathlib import Path

# Always excluded from PACK_PATH, even when `.templateignore` is absent or
# omits them. Keep both `.git` and `.git/` so directory and bare-name forms match.
BUILT_IN_EXCLUDES: tuple[str, ...] = (".git", ".git/", ".templateignore")
TEMPLATEIGNORE_NAME = ".templateignore"


@dataclass(frozen=True, slots=True)
class IgnoreRules:
    """Compiled ignore patterns for template copy."""

    patterns: tuple[str, ...]

    def matches(self, rel_posix: str) -> bool:
        """Return True when *rel_posix* (relative, ``/``-separated) is excluded."""
        rel = rel_posix.removeprefix("./")
        return any(_pattern_matches(pattern, rel) for pattern in self.patterns)


def load_ignore_rules(template_root: Path) -> IgnoreRules:
    """Load ``.templateignore`` from *template_root* and union built-ins."""
    patterns: list[str] = list(BUILT_IN_EXCLUDES)
    ignore_file = template_root / TEMPLATEIGNORE_NAME
    if ignore_file.is_file():
        for raw in ignore_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    return IgnoreRules(patterns=tuple(patterns))


def copy_template_tree(source_root: Path, destination: Path, rules: IgnoreRules) -> None:
    """Copy *source_root* into *destination*, excluding ignored paths."""
    destination.mkdir(parents=True, exist_ok=True)
    for path in source_root.rglob("*"):
        rel_path = path.relative_to(source_root)
        rel = rel_path.as_posix()
        # Hard exclude: never copy VCS metadata even if ignore file is incomplete
        if ".git" in rel_path.parts:
            continue
        if rules.matches(rel) or _any_parent_ignored(rel, rules):
            continue
        target = destination / rel_path
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _any_parent_ignored(rel: str, rules: IgnoreRules) -> bool:
    parts = rel.split("/")
    for i in range(1, len(parts)):
        parent = "/".join(parts[:i])
        if rules.matches(parent) or rules.matches(parent + "/"):
            return True
    return False


def _pattern_matches(pattern: str, rel: str) -> bool:
    """gitignore-like subset via ``fnmatch`` on relative POSIX paths."""
    pat = pattern.strip()
    if not pat:
        return False
    # Directory pattern: match the dir itself and everything under it
    if pat.endswith("/"):
        base = pat.rstrip("/")
        if rel == base or rel.startswith(base + "/"):
            return True
        return fnmatch.fnmatch(rel, pat.rstrip("/")) or fnmatch.fnmatch(
            rel, pat + "*"
        )
    if fnmatch.fnmatch(rel, pat):
        return True
    # Match basename-only patterns (e.g. ``*.pyc``)
    if "/" not in pat.rstrip("/"):
        return fnmatch.fnmatch(Path(rel).name, pat)
    return False
